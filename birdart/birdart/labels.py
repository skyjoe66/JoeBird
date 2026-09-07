"""Resolve a typed bird name to the pair BirdNET-Go would have emitted.

The simulate route takes whatever the user types - "cardinal", "Painted
Bunting", "Passerina ciris" - and has to turn it into the exact scientific name
the detector uses, because that name is the filename, the manifest key and the
label the frame prints. Guessing it is not an option, so everything is matched
against BirdNET's own label list.
"""

from __future__ import annotations

import functools

from .config import FUGLERAMME

LABELS = FUGLERAMME / "assets" / "birdnet_labels_v2.4.txt"


@functools.lru_cache(maxsize=1)
def all_labels() -> list[tuple[str, str]]:
    """[(scientific, common), ...] from "Scientific_Common" lines."""
    out = []
    try:
        for line in LABELS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or "_" not in line:
                continue
            sci, _, common = line.partition("_")
            out.append((sci.strip(), common.strip()))
    except OSError:
        pass
    return out


def resolve(text: str) -> tuple[str, str] | None:
    """The one species this can only mean, or None.

    Deliberately strict. "cardinal" matches Northern Cardinal, Vermilion
    Cardinal, Cardinal Lory and Pyrrhuloxia (Cardinalis sinuatus), and picking
    one by name length gave the Pyrrhuloxia - a confident wrong answer that
    would then be drawn on the frame. Ambiguity is sent back as suggestions
    instead, so the guess is the user's rather than ours.
    """
    q = " ".join(text.strip().split()).lower()
    if not q:
        return None
    labels = all_labels()
    for sci, com in labels:
        if q in (sci.lower(), com.lower()):
            return sci, com
    hits = suggest(text, limit=0)
    return hits[0] if len(hits) == 1 else None


def suggest(text: str, limit: int = 8) -> list[tuple[str, str]]:
    """Matches ranked for a "did you mean" list.

    Common names come first because that is what people type; within each tier
    the shortest name wins, which puts the plain species above compounds.
    """
    q = " ".join(text.strip().split()).lower()
    if not q:
        return []

    def tier(sci: str, com: str) -> int | None:
        s, c = sci.lower(), com.lower()
        if q in (s, c):
            return 0
        if c.startswith(q):
            return 1
        if any(w.startswith(q) for w in c.split()):  # "cardinal" -> Northern Cardinal
            return 2
        if s.startswith(q):
            return 3
        if q in c:
            return 4
        if q in s:
            return 5
        return None

    scored = []
    for sci, com in all_labels():
        t = tier(sci, com)
        if t is not None:
            scored.append((t, len(com), sci, com))
    scored.sort()
    out = [(s, c) for _t, _l, s, c in scored]
    return out[:limit] if limit else out
