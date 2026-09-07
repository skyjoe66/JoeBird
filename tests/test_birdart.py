"""The bot's settings, as the admin page edits them (fugleramme.birdart)."""

from __future__ import annotations

import json
import os
import re

from test_admin import _page

from fugleramme import birdart
from fugleramme.web import admin


def test_defaults_when_nothing_is_stored(tmp_path):
    s = birdart.load(tmp_path / "missing.json")
    assert s["provider"] == "openai" and s["quality"] == "high" and s["attempts"] == 2


def test_a_posted_key_is_stored_and_the_placeholder_keeps_it(tmp_path):
    path = tmp_path / "settings.json"
    s = birdart.changes(
        {"openai_api_key": ["sk-test-1234567890"], "quality": ["medium"]}, birdart.load(path)
    )
    birdart.save(s, path)
    assert oct(os.stat(path).st_mode & 0o777) == "0o600"
    stored = json.loads(path.read_text())
    assert stored["openai_api_key"] == "sk-test-1234567890" and stored["quality"] == "medium"
    # posting the placeholder back leaves the key alone; posting blank clears it
    s = birdart.changes({"openai_api_key": [birdart.KEY_SET]}, birdart.load(path))
    assert s["openai_api_key"] == "sk-test-1234567890"
    s = birdart.changes({"openai_api_key": [""]}, birdart.load(path))
    assert s["openai_api_key"] == ""


def test_bad_values_are_ignored_not_stored(tmp_path):
    s = birdart.changes(
        {"provider": ["dalle"], "quality": ["ultra"], "attempts": ["99"], "background": ["neon"]},
        birdart.load(tmp_path / "x.json"),
    )
    assert s["provider"] == "openai" and s["quality"] == "high"
    assert s["attempts"] == 4 and s["background"] == "transparent"


def test_the_key_never_reaches_the_page(tmp_path, source, monkeypatch):
    path = tmp_path / "settings.json"
    birdart.save(
        birdart.changes({"openai_api_key": ["sk-live-secret-value"]}, birdart.load(path)), path
    )
    monkeypatch.setattr(birdart, "PATH", path)
    page = _page(tmp_path, source())
    assert "sk-live-secret-value" not in page
    assert re.search(r'name="openai_api_key" value="' + re.escape(birdart.KEY_SET), page)
    assert 'name="section" value="birdart"' in page and 'name="extra_prompt"' in page
    # the model in use is filled in, and each provider links to its model list
    assert 'name="openai_model" value="gpt-image-2"' in page
    assert 'name="gemini_model" value="imagen-4.0-generate-001"' in page
    assert birdart.MODEL_DOCS["openai"] in page and birdart.MODEL_DOCS["gemini"] in page


def test_the_section_renders_with_no_settings_file_at_all(tmp_path, source, monkeypatch):
    monkeypatch.setattr(birdart, "PATH", tmp_path / "nope" / "settings.json")
    page = _page(tmp_path, source())
    assert "$" not in page and 'name="quality"' in page
    assert admin.birdart.KEY_SET not in page  # nothing stored, so no placeholder either
