"""Shared state between the watcher (writes) and the overlay (reads).

Two small JSON files rather than a database: the overlay must be able to read
the current search cheaply on every frame poll, and both files stay readable by
a human debugging the thing at 2am.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .config import LEDGER_FILE, STATE, STATUS_FILE


def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    os.replace(tmp, path)  # readers never see a half-written file


def _read(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


# ---------------------------------------------------------------- status


def read_status() -> dict:
    return _read(STATUS_FILE, {"active": None, "queue": [], "updated": 0})


def set_status(active: dict | None, queue: list[dict]) -> None:
    _write_atomic(
        STATUS_FILE,
        {"active": active, "queue": queue, "updated": time.time()},
    )


def clear_status() -> None:
    set_status(None, [])


# ---------------------------------------------------------------- ledger


def read_ledger() -> dict:
    return _read(LEDGER_FILE, {})


def note(scientific: str, status: str, why: str = "", common: str = "", source: str = "") -> dict:
    """Record an outcome. `attempts` only grows, so a species that keeps failing
    eventually parks itself instead of blocking the queue forever."""
    led = read_ledger()
    entry = led.get(scientific, {"attempts": 0, "common": common})
    entry["attempts"] = entry.get("attempts", 0) + (1 if status != "done" else 0)
    entry["status"] = status
    entry["why"] = why
    entry["common"] = common or entry.get("common", "")
    # Which backend produced this outcome. Kept so a ledger written by the old
    # Commons hunt is recognised and its failures forgiven; see watcher.parked.
    entry["source"] = source or entry.get("source", "")
    entry["last"] = time.time()
    led[scientific] = entry
    _write_atomic(LEDGER_FILE, led)
    return entry


def ensure_dirs() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
