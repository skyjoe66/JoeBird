"""Time the whole path from a bird call to a picture on the glass.

    uv run python -m birdart.timetest            # then play a call, repeatedly
    uv run python -m birdart.timetest --timeout 600

Waits for the detector to log a species it has not logged since the script
started, then stamps every stage as it happens:

    detected    BirdNET-Go approved it (its own timestamp is shown beside ours)
    building    the bot took it on - the "Building Image of Current Species"
                banner is on the glass within one kiosk poll (3 s)
    installed   the plate landed in the library
    redrawn     the frame rendered a new page
    visible     the kiosk's /state token moved - what the eye sees, within 3 s

A species that already has a plate skips building and installed: the frame
draws it as soon as its own poll notices, and that is the number reported.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

from .config import (
    DETECTOR,
    FRAME,
    OVERLAY_PORT,
    STATE,
    USER_AGENT,
    artwork_dir,
    has_artwork,
    key_for,
)

OVERLAY = f"http://127.0.0.1:{OVERLAY_PORT}"
POLL = 0.5


def _get(url: str, timeout: int = 10) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _json(url: str, default):
    try:
        return json.loads(_get(url))
    except Exception:
        return default


def _text(url: str) -> str:
    try:
        return _get(url).decode()
    except Exception:
        return ""


def _detections() -> list[dict]:
    d = _json(f"{DETECTOR}/api/v2/detections/recent?limit=10", [])
    return d if isinstance(d, list) else d.get("data", [])


def _ids(rows: list[dict]) -> set:
    return {r.get("id") or (r.get("date"), r.get("time"), r.get("scientificName")) for r in rows}


def _status() -> dict:
    try:
        return json.loads((STATE / "status.json").read_text())
    except Exception:
        return {}


def _ledger_why(scientific: str) -> str:
    try:
        return json.loads((STATE / "ledger.json").read_text()).get(scientific, {}).get("why", "")
    except Exception:
        return ""


class Clock:
    def __init__(self) -> None:
        self.t0 = time.monotonic()
        self.marks: dict[str, float] = {}

    def mark(self, name: str, note: str = "") -> None:
        t = time.monotonic() - self.t0
        self.marks[name] = t
        since = ""
        if "detected" in self.marks and name != "detected":
            since = f"  (+{t - self.marks['detected']:5.1f}s after detection)"
        print(f"  {t:6.1f}s  {name:<10} {note}{since}", flush=True)


def run(timeout: float) -> int:
    clock = Clock()
    seen = _ids(_detections())
    frame_tok = _text(f"{FRAME}/state")
    kiosk_tok = _text(f"{OVERLAY}/state")
    print(
        f"ready - play the call now (waiting up to {timeout:.0f}s for a new detection)", flush=True
    )

    species = common = None
    key = ""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for r in _detections():
            if _ids([r]) - seen:
                species, common = r.get("scientificName", ""), r.get("commonName", "")
                key = key_for(species)
                clock.mark(
                    "detected",
                    f"{common} ({species}) conf {float(r.get('confidence', 0)):.2f}, "
                    f"BirdNET stamped it {r.get('time', '?')}",
                )
                break
        if species:
            break
        time.sleep(POLL)
    if not species:
        print(
            "no new detection - nothing was approved. Check the analyzer: "
            "docker logs birdnet-go --since 5m | grep -E 'pending|approving|pipeline'"
        )
        return 1

    had = has_artwork(species)
    print(
        f"          {'already in the library' if had else 'no plate yet - the bot should build one'}",
        flush=True,
    )
    files_before = {p.name for p in artwork_dir().glob(f"{key}*.png")}
    want = {"redrawn", "visible"} if had else {"building", "installed", "redrawn", "visible"}
    deadline = time.monotonic() + timeout
    while want and time.monotonic() < deadline:
        if "building" in want and (_status().get("active") or {}).get("scientific") == species:
            clock.mark("building", "banner up on the next kiosk poll (<=3s)")
            want.discard("building")
        if (
            "installed" in want
            and {p.name for p in artwork_dir().glob(f"{key}*.png")} - files_before
        ):
            clock.mark("installed", _ledger_why(species) or "in the library")
            want.discard("installed")
            want.discard("building")
        if (
            "redrawn" in want
            and "installed" not in want
            and (tok := _text(f"{FRAME}/state")) != frame_tok
        ):
            frame_tok = tok
            clock.mark("redrawn", "frame rendered a new page")
            want.discard("redrawn")
        if (
            "visible" in want
            and "redrawn" not in want
            and (tok := _text(f"{OVERLAY}/state")) != kiosk_tok
        ):
            kiosk_tok = tok
            clock.mark("visible", "kiosk token moved - on the glass within 3s")
            want.discard("visible")
        time.sleep(POLL)

    m = clock.marks
    print()
    if want:
        print(f"timed out still waiting for: {', '.join(sorted(want))}")
        if "building" in want and not had:
            print(
                "  the bot never took it - is birdart-watcher running? journalctl -u birdart-watcher -n 20"
            )
        return 1
    d = m["detected"]
    if had:
        print(
            f"RESULT  {common}: existing plate, on the glass {m['visible'] - d:.1f}s after detection"
        )
    else:
        print(
            f"RESULT  {common}: detection -> building {m['building'] - d:.1f}s, "
            f"building -> installed {m['installed'] - m['building']:.1f}s, "
            f"installed -> visible {m['visible'] - m['installed']:.1f}s; "
            f"total {m['visible'] - d:.1f}s"
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--timeout", type=float, default=300, help="seconds to wait at each stage")
    return run(ap.parse_args().timeout)


if __name__ == "__main__":
    sys.exit(main())
