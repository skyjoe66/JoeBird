"""Build artwork for every species in the detector's range filter, ahead of time.

The watcher is reactive: a bird is heard, then drawn. This is the other half of
the same machine - work through the whole local species list now, so the frame
is ready the first time each bird sings.

Location-independent by construction: the list comes from BirdNET-Go's own range
filter, which is derived from the Pi's configured latitude and longitude. Move
the Pi, and this builds that region's birds instead.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from urllib.parse import urljoin

from . import state
from .acquire import acquire
from .config import DETECTOR, MAX_ATTEMPTS, USER_AGENT, has_artwork
from .watcher import parked


def _log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def range_species() -> list[dict]:
    """Every species the detector considers plausible here, commonest first."""
    url = urljoin(DETECTOR + "/", "api/v2/range/species/list")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return [
        {"scientific": s["scientificName"], "common": s.get("commonName") or s["scientificName"]}
        for s in data.get("species", [])
        if s.get("scientificName")
    ]


def todo() -> list[dict]:
    ledger = state.read_ledger()
    return [
        s
        for s in range_species()
        if not has_artwork(s["scientific"]) and not parked(ledger, s["scientific"])
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="stop after N species (0 = all)")
    ap.add_argument("--list", action="store_true", help="show what would be done, change nothing")
    ap.add_argument("--pause", type=float, default=5.0, help="seconds between species")
    a = ap.parse_args()
    state.ensure_dirs()

    work = todo()
    if a.limit:
        work = work[: a.limit]
    _log(f"{len(work)} species in range without artwork")
    if a.list:
        for s in work:
            print(f"  {s['common']}  ({s['scientific']})")
        return 0

    done = failed = 0
    for i, s in enumerate(work, 1):
        # Same banner the watcher raises, so a backfill is visible on the frame.
        state.set_status(s, work[i:])
        _log(f"[{i}/{len(work)}] {s['common']}")
        try:
            ok, why = acquire(s["scientific"], s["common"])
        except Exception as e:
            ok, why = False, f"unhandled: {e}"
        state.note(s["scientific"], "done" if ok else "failed", why, s["common"], "openai")
        done, failed = done + bool(ok), failed + (not ok)
        _log(("  done" if ok else "  failed: ") + ("" if ok else why))
        time.sleep(a.pause)

    state.clear_status()
    _log(
        f"backfill finished: {done} acquired, {failed} failed "
        f"(failures retry up to {MAX_ATTEMPTS} times on later runs)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
