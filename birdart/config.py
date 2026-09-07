"""Paths and tunables, all overridable by environment so the bot can be pointed
at another checkout or another frame without editing code."""

import os
from pathlib import Path

# Where Fugleramme lives. The bot never writes into the repo except through
# add_bird.py, which is the supported way in.
FUGLERAMME = Path(os.environ.get("FUGLERAMME_DIR", "/home/joe/fugleramme"))
STYLE = os.environ.get("BIRDART_STYLE", "custom")

# Our own state, deliberately outside the repo so a self-update cannot clobber it.
ROOT = Path(os.environ.get("BIRDART_DIR", "/home/joe/birdart"))
WORK = ROOT / "work"
STATE = ROOT / "state"
STATUS_FILE = STATE / "status.json"
LEDGER_FILE = STATE / "ledger.json"

DETECTOR = os.environ.get("BIRDART_DETECTOR", "http://127.0.0.1:8090")
FRAME = os.environ.get("BIRDART_FRAME", "http://127.0.0.1:8080")
OVERLAY_PORT = int(os.environ.get("BIRDART_OVERLAY_PORT", "8081"))

POLL_SECONDS = int(os.environ.get("BIRDART_POLL", "20"))
# A species that fails this many times is parked, so one impossible bird cannot
# spin the queue forever. Cleared by deleting its ledger entry.
MAX_ATTEMPTS = int(os.environ.get("BIRDART_MAX_ATTEMPTS", "3"))
CLAUDE_TIMEOUT = int(os.environ.get("BIRDART_CLAUDE_TIMEOUT", "300"))

# The frame's paper colour: the halo has to match it or the cut-out reads as a
# sticker. Taken from docs/adding-artwork.md.
PAPER = (0xF0, 0xEC, 0xE5)
HALO_PX = int(os.environ.get("BIRDART_HALO_PX", "18"))

USER_AGENT = "fugleramme-birdart/0.1 (automatic artwork acquisition; local Raspberry Pi)"


def artwork_dir(style: str | None = None) -> Path:
    return FUGLERAMME / "assets" / "artwork" / (style or STYLE) / "birds"


def key_for(scientific_name: str) -> str:
    """"Turdus merula" -> "turdus-merula", matching names.normalize upstream."""
    return scientific_name.strip().lower().replace(" ", "-")


def has_artwork(scientific_name: str, style: str | None = None) -> bool:
    """True when the style already holds any variant for this species.

    Only ever one style: artwork in `custom` does nothing for a frame showing
    `generated`, so a species present elsewhere still counts as missing here.
    """
    key = key_for(scientific_name)
    d = artwork_dir(style)
    if not d.is_dir():
        return False
    return any(
        p.stem == key or p.stem.startswith(f"{key}-") and p.stem[len(key) + 1 :].isdigit()
        for p in d.glob("*.png")
    )
