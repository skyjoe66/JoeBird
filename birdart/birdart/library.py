"""Fetch a plate from the shared JoeBird library before spending a token on one.

Every frame that hears a cardinal would otherwise generate its own. The shared
library is a plain public GitHub repository: `index.json` at its root lists, per
species key, the files it holds and their sha256; the files sit under `birds/`.
Nothing here needs an account or a key, and a library that is unreachable is
treated as empty - generation is always the fallback, never the library.

    BIRDART_LIBRARY=""      disable
    BIRDART_LIBRARY=<url>   another library, same layout

The index is cached in state/ for BIRDART_LIBRARY_TTL seconds so a busy morning
does not hammer GitHub, and a stale cache is used when a refresh fails.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

from .config import STATE, USER_AGENT, key_for

LIBRARY_URL = os.environ.get(
    "BIRDART_LIBRARY", "https://raw.githubusercontent.com/skyjoe66/joebird-library/main"
).rstrip("/")
INDEX_TTL = int(os.environ.get("BIRDART_LIBRARY_TTL", "3600"))
CACHE = STATE / "library-index.json"
TIMEOUT = 30


class LibraryError(RuntimeError):
    pass


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def index(fresh: bool = False) -> dict:
    """The library's index, from cache when fresh, else fetched; {} when there
    is no library or nothing answers and nothing is cached. `fresh` skips the
    cache - the gallery does that on every load, so a merge shows at once."""
    if not LIBRARY_URL:
        return {}
    try:
        if not fresh and CACHE.exists() and time.time() - CACHE.stat().st_mtime < INDEX_TTL:
            return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        pass
    try:
        data = json.loads(_get(f"{LIBRARY_URL}/index.json"))
        STATE.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(data))
        return data
    except Exception:
        try:
            return json.loads(CACHE.read_text()) if CACHE.exists() else {}
        except (OSError, ValueError):
            return {}


def lookup(scientific: str) -> list[dict]:
    """Entries the library holds for this species, best first; [] if none."""
    entries = index().get("birds", {}).get(key_for(scientific), [])
    return [e for e in entries if isinstance(e, dict) and e.get("file") and e.get("sha256")]


def fetch(entry: dict, dest: Path) -> str:
    """Download one entry to `dest`, verify its hash, return the URL it came from."""
    url = f"{LIBRARY_URL}/{entry['file'].lstrip('/')}"
    data = _get(url)
    digest = hashlib.sha256(data).hexdigest()
    if digest != entry["sha256"]:
        raise LibraryError(f"sha256 mismatch for {entry['file']}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return url
