"""Wikimedia Commons: find and fetch a public-domain plate for a species.

Commons rate-limits hard (HTTP 429) when a batch of species is worked through
back to back, so every call retries with a growing pause rather than failing the
whole acquisition.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import USER_AGENT

API = "https://commons.wikimedia.org/w/api.php"

# Licence strings we accept. Anything else (CC BY-SA, unknown, non-free) is
# skipped: the style is redistributable and an unclear licence poisons it.
OK_LICENCE = ("public domain", "cc0", "pd-", "pd ")


def _get(params: dict, tries: int = 5) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except Exception as e:  # 429 and transient network alike
            last = e
            time.sleep(6 * (i + 1))
    raise RuntimeError(f"commons api failed: {last}")


def _licence_ok(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(t.startswith(p) or p in t for p in OK_LICENCE)


def search(query: str, limit: int = 12) -> list[str]:
    res = _get(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srnamespace": 6,
            "srlimit": limit,
            "format": "json",
        }
    )
    return [r["title"] for r in res.get("query", {}).get("search", [])]


# Wikimedia rate-limits originals hard and its own 429 body asks callers to use
# thumbnails instead. A plate is downscaled to 1200px on the way into the style
# anyway, so the full 50MB scan was never worth fetching.
THUMB_WIDTH = 1800


def image_info(titles: list[str]) -> list[dict]:
    """Size, thumbnail URL and licence for each title, biggest first."""
    if not titles:
        return []
    res = _get(
        {
            "action": "query",
            "titles": "|".join(titles[:20]),
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata",
            "iiurlwidth": THUMB_WIDTH,
            "format": "json",
        }
    )
    out = []
    for p in res.get("query", {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii.get("url"):
            continue
        em = ii.get("extmetadata", {}) or {}
        lic = (em.get("LicenseShortName", {}) or {}).get("value", "")
        out.append(
            {
                "title": p.get("title", ""),
                "width": ii.get("width", 0),
                "height": ii.get("height", 0),
                "bytes": ii.get("size", 0),
                # Fetch the thumbnail, but keep the original URL for reference.
                "url": ii.get("thumburl") or ii["url"],
                "original": ii["url"],
                "page": ii.get("descriptionurl", ""),
                "licence": lic,
                "licence_ok": _licence_ok(lic),
            }
        )
    out.sort(key=lambda c: c["width"] * c["height"], reverse=True)
    return out


def candidates(scientific: str, common: str) -> list[dict]:
    """Plates worth considering, best-sourced first.

    The queries run widest-last: a named historical folio gives a clean cut-out,
    a generic species search often gives a photograph, which cuts badly.
    """
    queries = [
        f'Havell Audubon "{common}"',
        f'Audubon "{common}" Havell',
        f'Gould "{common}" birds',
        f'"{scientific}" illustration plate',
        f'"{scientific}" Audubon',
        f'"{common}" lithograph bird plate',
    ]
    seen: dict[str, dict] = {}
    for q in queries:
        try:
            titles = search(q)
        except Exception:
            continue
        if not titles:
            continue
        for c in image_info(titles):
            # Skip PDFs/DjVu book scans and giant files we would only downscale.
            if c["title"].lower().endswith((".pdf", ".djvu", ".tif", ".tiff")):
                continue
            if not c["licence_ok"] or c["bytes"] > 30_000_000 or c["width"] < 700:
                continue
            seen.setdefault(c["title"], c)
        if len(seen) >= 8:
            break
        time.sleep(2)
    return sorted(seen.values(), key=lambda c: c["width"] * c["height"], reverse=True)[:8]


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                dest.write_bytes(r.read())
            return dest
        except urllib.error.HTTPError as e:
            # 429 is a cooldown, not a verdict on this file: back off properly
            # rather than burning the rest of the candidate list against a wall.
            if e.code == 429 and i < 4:
                time.sleep(20 * (i + 1))
                continue
            if i == 4:
                raise
            time.sleep(8 * (i + 1))
        except Exception:
            if i == 4:
                raise
            time.sleep(8 * (i + 1))
    return dest
