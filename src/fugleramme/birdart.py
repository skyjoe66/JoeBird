"""The bot's settings, edited from the admin page's "AI images" section.

JoeBird's bot (birdart/) generates a plate for any species the frame cannot
draw. Which provider, which model, at what quality, how many attempts, and any
extra wording for the prompt are its settings, and the API keys are secrets.
They live in birdart/state/settings.json - the bot's own, gitignored, mode 600
- not in the frame's settings.json, which is upstream's and travels in the
open. This module is the only thing in the frame that touches that file.

A stored key never reaches the page: the form shows a placeholder, and posting
the placeholder back means "leave it alone", the same rule the detector
password follows. Posting the field blank clears the key.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .config import REPO_ROOT

PATH = REPO_ROOT / "birdart" / "state" / "settings.json"
# The bot's overlay, which serves the gallery; the admin links there with the
# page's own hostname, the way it links to BirdNET-Go.
OVERLAY_PORT = int(os.environ.get("BIRDART_OVERLAY_PORT", "8081"))
KEY_SET = "•" * 8  # what the form shows for a stored key; posting it back keeps the key

PROVIDERS = (("openai", "OpenAI"), ("gemini", "Gemini (experimental)"))
# Where each provider lists its image models, so the field beside the link can be
# filled in from the source rather than from memory.
MODEL_DOCS = {
    "openai": "https://platform.openai.com/docs/models",
    "gemini": "https://ai.google.dev/gemini-api/docs/models",
}
DEFAULT_MODEL = {"openai": "gpt-image-2", "gemini": "imagen-4.0-generate-001"}
QUALITIES = ("low", "medium", "high")
BACKGROUNDS = (("transparent", "transparent"), ("flat", "flat ivory"), ("paper", "textured paper"))
KEYS = ("openai_api_key", "gemini_api_key")

DEFAULTS: dict[str, Any] = {
    "provider": "openai",
    "openai_model": "gpt-image-2",
    "gemini_model": "imagen-4.0-generate-001",
    "quality": "high",
    "attempts": 2,
    "background": "transparent",
    "extra_prompt": "",
    "openai_api_key": "",
    "gemini_api_key": "",
}


def load(path: Path | None = None) -> dict[str, Any]:
    """Stored values over defaults. A missing or broken file is the defaults."""
    path = path or PATH
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}


def changes(form: dict[str, list[str]], current: dict[str, Any]) -> dict[str, Any]:
    """Validated settings from a posted form, over what is stored."""
    out = dict(current)
    got = {k: v[0] for k, v in form.items()}
    provider = got.get("provider", out["provider"])
    out["provider"] = provider if provider in dict(PROVIDERS) else out["provider"]
    quality = got.get("quality", out["quality"])
    out["quality"] = quality if quality in QUALITIES else out["quality"]
    background = got.get("background", out["background"])
    out["background"] = background if background in dict(BACKGROUNDS) else out["background"]
    for field in ("openai_model", "gemini_model"):
        if field in got:
            out[field] = got[field].strip()[:80] or DEFAULT_MODEL[field.split("_")[0]]
    out["extra_prompt"] = got.get("extra_prompt", out["extra_prompt"]).strip()[:2000]
    try:
        out["attempts"] = max(1, min(4, int(got.get("attempts", out["attempts"]))))
    except (TypeError, ValueError):
        pass
    for key in KEYS:
        if key not in got:
            continue
        value = got[key].strip()
        if value == KEY_SET:
            continue  # untouched, so the stored one stands
        out[key] = value  # a new key, or blank to clear it
    return out


def save(data: dict[str, Any], path: Path | None = None) -> None:
    """Write mode 600, whole file at once, so a key is never world-readable
    even for an instant and the bot never reads a half-written file."""
    path = path or PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def key_is_set(data: dict[str, Any], which: str) -> bool:
    """Whether a key exists for a provider - stored here, or for OpenAI, in the
    environment file the bot's unit reads (state/openai.env)."""
    if data.get(f"{which}_api_key"):
        return True
    if which == "openai":
        try:
            env = (PATH.parent / "openai.env").read_text()
            return any(
                line.strip().startswith("OPENAI_API_KEY=") and line.split("=", 1)[1].strip()
                for line in env.splitlines()
            )
        except OSError:
            return False
    return False
