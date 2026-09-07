"""The daemon: watch what BirdNET-Go hears, acquire what we cannot draw.

Deliberately serial. One acquisition at a time keeps the spend predictable,
keeps the "Building Image of Current Species" banner honest about which bird
it means, and means a runaway queue can be stopped by stopping one service.
"""

from __future__ import annotations

import json
import time
import urllib.request
from urllib.parse import urljoin

from . import rebuild, state
from .acquire import CONFIG_ERROR, acquire
from .config import DETECTOR, MAX_ATTEMPTS, POLL_SECONDS, USER_AGENT, has_artwork

_last_hold: str | None = None


def _log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


# /api/v2/detections is paginated and cached, and the cache goes stale: at
# limit=100 it served a page whose newest row was a day old while a Bald Eagle
# heard minutes earlier was missing from it. /api/v2/detections/recent is what
# the frame itself reads, is not cached, and answers with the newest first.
DETECTION_LIMIT = 100


def heard_species(limit: int = DETECTION_LIMIT) -> list[dict]:
    """Distinct species in the detector's recent history, newest first."""
    url = urljoin(DETECTOR + "/", f"api/v2/detections/recent?limit={limit}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    rows = data if isinstance(data, list) else data.get("data", [])
    out: dict[str, dict] = {}
    for d in rows:
        sci = (d.get("scientificName") or "").strip()
        if sci and sci not in out:
            out[sci] = {"scientific": sci, "common": d.get("commonName") or sci}
    return list(out.values())


def parked(ledger: dict, scientific: str) -> bool:
    """Given up on: failed MAX_ATTEMPTS times. Entries an older version wrote
    against the Commons hunt do not count - that backend is gone, and a species
    it could not find deserves a fresh start with generation."""
    e = ledger.get(scientific)
    if not e or e.get("status") == "done":
        return False
    if (e.get("source") or "commons") == "commons":
        return False
    return e.get("attempts", 0) >= MAX_ATTEMPTS


def missing_species() -> list[dict]:
    """Heard, undrawable, and not already given up on."""
    ledger = state.read_ledger()
    return [
        s
        for s in heard_species()
        if not has_artwork(s["scientific"]) and not parked(ledger, s["scientific"])
    ]


def tick() -> None:
    job = rebuild.pop()
    if job:
        # A rejected plate the owner asked to redraw. Same banner, same checks;
        # the old picture stays up until the new one has passed them.
        state.set_status(job, rebuild.pending())
        _log(f"rebuilding {job['common']} ({job['scientific']})")
        try:
            ok, why = rebuild.run(job)
        except Exception as e:
            ok, why = False, f"unhandled: {e}"
        state.note(job["scientific"], "done" if ok else "failed", why, job["common"], "openai")
        _log(("rebuilt: " if ok else "rebuild failed: ") + f"{job['common']}: {why}")
        state.clear_status()
        return
    todo = missing_species()
    if not todo:
        cur = state.read_status()
        if cur.get("active") or cur.get("queue"):
            state.clear_status()
        return

    active, rest = todo[0], todo[1:]
    state.set_status(active, rest)
    _log(f"acquiring {active['common']} ({active['scientific']}); {len(rest)} more queued")
    try:
        ok, why = acquire(active["scientific"], active["common"])
    except Exception as e:  # never let one bird kill the daemon
        ok, why = False, f"unhandled: {e}"
    if not ok and why.startswith(CONFIG_ERROR):
        # Nothing to do with this bird: the setup is wrong. Say so once and hold
        # without recording an attempt, so fixing the config resumes the queue
        # intact rather than finding every species parked. Logged only when the
        # message changes, or a bad key would fill the journal one line per tick.
        global _last_hold
        detail = why[len(CONFIG_ERROR) :]
        if detail != _last_hold:
            _log(f"holding: {detail}")
            _last_hold = detail
        state.clear_status()
        return
    entry = state.note(
        active["scientific"], "done" if ok else "failed", why, active["common"], "openai"
    )
    _log(("done: " if ok else "failed: ") + f"{active['common']}: {why}")
    if not ok and entry.get("attempts", 0) >= MAX_ATTEMPTS:
        _log(f"parking {active['common']} after {entry['attempts']} attempts")
    # Drop the banner as soon as this bird resolves; the next tick re-raises it
    # if there is more to do, which keeps the frame honest between species.
    state.clear_status()


def main() -> int:
    state.ensure_dirs()
    state.clear_status()
    _log("birdart watcher started")
    while True:
        try:
            tick()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            _log(f"tick error: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
