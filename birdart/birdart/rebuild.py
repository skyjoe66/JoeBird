"""Redraw a plate the owner has rejected, with their note in the prompt.

The gallery (overlay.py, /birdart/gallery) queues a job here; the watcher runs
it between detections so the "Building Image of Current Species" banner shows
as usual. The old plate stays on the glass until the new one has passed every
check: the new image is installed as a further variant first, and only then are
the old files removed and the new one renamed into their place. A rebuild that
fails leaves the library exactly as it was.

The note is kept per species (settings.set_note), so a bird that once needed
"both wings folded" keeps that wording on any later rebuild too.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import settings, state
from .acquire import _nudge_frame, acquire
from .config import FUGLERAMME, STATE, STYLE, artwork_dir, key_for

QUEUE = STATE / "rebuild.json"
_NUMBERED = re.compile(r"-(\d+)$")


def _read() -> list[dict]:
    try:
        jobs = json.loads(QUEUE.read_text()).get("jobs", [])
        return [j for j in jobs if isinstance(j, dict) and j.get("scientific")]
    except (OSError, ValueError, AttributeError):
        return []


def _write(jobs: list[dict]) -> None:
    state._write_atomic(QUEUE, {"jobs": jobs})


def pending() -> list[dict]:
    return _read()


def request(scientific: str, common: str, note: str) -> None:
    """Queue one species; a repeat replaces the earlier request and its note."""
    settings.set_note(scientific, note)
    jobs = [j for j in _read() if j["scientific"] != scientific]
    jobs.append({"scientific": scientific, "common": common or scientific})
    _write(jobs)


def pop() -> dict | None:
    jobs = _read()
    if not jobs:
        return None
    job, rest = jobs[0], jobs[1:]
    _write(rest)
    return job


def files_for(key: str) -> list[Path]:
    """Every variant the library holds for a species key."""
    return sorted(p for p in artwork_dir().glob(f"{key}*.png") if _NUMBERED.sub("", p.stem) == key)


def _replace(key: str, previous: list[Path]) -> None:
    """The new variant becomes <key>.png; the rejected ones go."""
    new = [p for p in files_for(key) if p not in previous]
    if not new:
        return
    fresh = new[-1]
    manifest_path = FUGLERAMME / "assets" / "artwork" / STYLE / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, ValueError):
        manifest = {}
    entry = manifest.pop(f"birds/{fresh.name}", {"source": "generated"})
    for old in previous:
        old.unlink(missing_ok=True)
        manifest.pop(f"birds/{old.name}", None)
    target = fresh.with_name(f"{key}.png")
    fresh.rename(target)
    manifest[f"birds/{target.name}"] = entry
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def run(job: dict) -> tuple[bool, str]:
    """Generate a replacement and swap it in only if it passes."""
    scientific, common = job["scientific"], job.get("common") or job["scientific"]
    key = key_for(scientific)
    previous = files_for(key)
    ok, why = acquire(scientific, common)
    if ok and previous:
        _replace(key, previous)
        _nudge_frame()
    return ok, why
