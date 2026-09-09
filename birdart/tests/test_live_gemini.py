"""Live check of the Gemini image path: draw one White Ibis with the key stored
on the admin page. Spends real API credit, so it only runs when asked:

    BIRDART_LIVE=1 birdart/.venv/bin/python -m pytest birdart/tests/test_live_gemini.py -s

The provider is forced to gemini for the test only; settings.json is untouched.
The plate is left at birdart/work/eudocimus-albus-generated.png, named as the
bot names its own work, for a look.
"""

from __future__ import annotations

import os

import pytest
from birdart.config import WORK, key_for

from birdart import generate, settings

SCIENTIFIC, COMMON = "Eudocimus albus", "White Ibis"
OUT = WORK / f"{key_for(SCIENTIFIC)}-generated.png"


@pytest.mark.skipif(
    os.environ.get("BIRDART_LIVE") != "1", reason="set BIRDART_LIVE=1 to spend API credit"
)
def test_gemini_draws_a_white_ibis(monkeypatch):
    if not settings.api_key("gemini"):
        pytest.skip("no Gemini key stored on the admin page")
    monkeypatch.setattr(settings, "provider", lambda: "gemini")
    assert settings.model().startswith(("gemini", "imagen"))

    OUT.unlink(missing_ok=True)
    got = generate.generate(COMMON, SCIENTIFIC, OUT)

    assert got == OUT and OUT.is_file()
    data = OUT.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff", "not a PNG or JPEG"
    assert len(data) > 50_000, f"suspiciously small image: {len(data)} bytes"

    from PIL import Image

    with Image.open(OUT) as im:
        w, h = im.size
    assert h > w, f"expected a portrait plate, got {w}x{h}"
    print(f"\nGemini ({settings.model()}) wrote {OUT} {w}x{h}, {len(data)} bytes")
