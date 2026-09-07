"""Settings the frame's admin page writes for the bot, read at the moment of use.

`state/settings.json` is written by the frame's admin (its "AI images" section)
and read here; it beats the environment, which beats the built-in default, so a
unit's Environment= lines and .env.example keep working for an install that
never opens the admin. Read per call, not at import, so a change on the page
reaches the next generation without a restart. The file holds API keys, so it
is created mode 600 and never printed.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .config import STATE

FILE = STATE / "settings.json"

PROVIDERS = ("openai", "gemini")
QUALITIES = ("low", "medium", "high")
BACKGROUNDS = ("transparent", "flat", "paper")
DEFAULT_MODEL = {"openai": "gpt-image-2", "gemini": "imagen-4.0-generate-001"}


def _file() -> dict[str, Any]:
    try:
        data = json.loads(FILE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(name: str, env: str = "", default: Any = "") -> Any:
    """settings.json, else the environment variable, else the default."""
    data = _file()
    if name in data and data[name] not in ("", None):
        return data[name]
    if env and os.environ.get(env, "").strip():
        return os.environ[env].strip()
    return default


def provider() -> str:
    p = str(get("provider", "BIRDART_PROVIDER", "openai")).lower()
    return p if p in PROVIDERS else "openai"


def model() -> str:
    """The model for the active provider: its own field, else its default."""
    p = provider()
    env = {"openai": "BIRDART_IMAGE_MODEL", "gemini": "BIRDART_GEMINI_MODEL"}[p]
    return str(get(f"{p}_model", env, "")).strip() or DEFAULT_MODEL[p]


def quality() -> str:
    q = str(get("quality", "BIRDART_IMAGE_QUALITY", "high")).lower()
    return q if q in QUALITIES else "high"


def background() -> str:
    b = str(get("background", "BIRDART_IMAGE_BACKGROUND", "transparent")).lower()
    return b if b in BACKGROUNDS else "transparent"


def attempts() -> int:
    try:
        return max(1, min(4, int(get("attempts", "BIRDART_GENERATE_ATTEMPTS", 2))))
    except (TypeError, ValueError):
        return 2


def extra_prompt() -> str:
    return str(get("extra_prompt", "BIRDART_EXTRA_PROMPT", "")).strip()


def api_key(which: str) -> str:
    """The stored key for a provider, or "". The OpenAI one also falls back to
    the environment and to state/openai.env, which systemd reads."""
    key = str(get(f"{which}_api_key", "", "")).strip()
    if key:
        return key
    if which == "openai":
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if key:
            return key
        try:
            for line in (STATE / "openai.env").read_text().splitlines():
                if line.strip().startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"")
        except OSError:
            pass
    if which == "gemini":
        return os.environ.get("GEMINI_API_KEY", "").strip()
    return ""
