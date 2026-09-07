"""Generate a plate with OpenAI instead of sourcing one from Wikimedia Commons.

The Commons path is limited by what a century of lithographers happened to draw:
for perhaps a third of species there is no clean single-bird plate at all, and no
amount of better cutting invents one. Generation has no such ceiling.

What it costs is provenance. These images are synthetic, they are nobody's
scan, and the style that holds them says so - see the `generated` style's
ATTRIBUTION.md. They are deliberately kept out of the styles that hold real
historical plates.

The generated plate still goes through the same cut-out and the same visual QA
as a Commons plate. The prompt asks for a single bird on generous ivory paper
margins with no text at all, which is the easiest case the cut-out ever sees -
flat, uniform paper, rather than the mottled century-old scans it keeps failing
on. The frame draws the species caption itself, as it always has.
"""

from __future__ import annotations

import base64
import os
import urllib.request
from pathlib import Path

from .config import ROOT, USER_AGENT

# The user's prompt, verbatim, with the one substitution it asks for.
PROMPT = """Create a realistic, full-color natural-history illustration of a **{common}**.

Before generating the image:

1. Identify the bird's current accepted scientific name.
2. Verify its anatomy, proportions, plumage colors, bill, legs, eyes, and distinctive markings.
3. Include no text of any kind in the image.

Image requirements:

* One anatomically accurate adult bird.
* Full body visible in a graceful side-profile pose.
* Head, bill, wings, tail, legs, and feet entirely within the frame.
* Show the bird in a minimal version of its natural habitat.
* Use a portrait-oriented composition with the bird centered and prominent.
* Add only a few appropriate plants, branches, rocks, or water elements around its feet.
* Leave generous warm ivory paper margins.

Visual style:

* Nineteenth-century Darwin-era natural-history plate.
* Finely engraved linework with delicate, hand-applied watercolor.
* Realistic feather detail and restrained natural colors.
* Subtle aged-paper, ink, and print texture.
* Scholarly museum-archive appearance.
* Neutral specimen lighting.

Avoid:

* Any text, lettering, labels or captions anywhere in the image.
* Photographic appearance.
* Modern digital-art gloss.
* Cartoon or fantasy styling.
* Exaggerated anatomy or colors.
* Cluttered scenery.
* Decorative borders.
* Multiple birds or other animals.
* Cropped anatomy.
* Watermarks or signatures.

Generate the finished image directly without asking follow-up questions."""

MODEL = os.environ.get("BIRDART_IMAGE_MODEL", "gpt-image-2")
SIZE = os.environ.get("BIRDART_IMAGE_SIZE", "1024x1536")  # portrait, as the prompt asks
QUALITY = os.environ.get("BIRDART_IMAGE_QUALITY", "medium")
KEY_FILE = ROOT / "state" / "openai.env"


class GenerateError(RuntimeError):
    pass


def _retry_flat(client, common: str):
    """This model will not do transparency: ask for flat ivory paper instead."""
    return client.images.generate(
        model=MODEL,
        prompt=PROMPT.format(common=common) + _FLAT_PAPER,
        size=SIZE,
        quality=QUALITY,
    )


def api_key() -> str:
    """From the environment, else from the key file systemd also reads.

    Kept in a file rather than the unit so the key never appears in `systemctl
    cat`, `ps`, or this repository.
    """
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    try:
        for line in KEY_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    raise GenerateError(f"no OPENAI_API_KEY in the environment or {KEY_FILE}")


def _client():
    try:
        from openai import OpenAI
    except ImportError as e:  # pragma: no cover - dependency is declared
        raise GenerateError(f"openai package not available: {e}") from e
    return OpenAI(api_key=api_key())


# The prompt asks for aged-paper texture, which is lovely on its own and fatal
# to the cut-out: that texture varies more than any single colour threshold can
# absorb, so the background will not lift until the threshold is wide enough to
# take the bird's pale face with it. Measured on a real plate: below tol 55 the
# paper stays, at 55 the titmouse lost its cheek and eye. Asking for no paper at
# all removes the conflict, and costs nothing - the frame lays the bird on its
# own textured paper regardless.
BACKGROUND = os.environ.get("BIRDART_IMAGE_BACKGROUND", "transparent").strip().lower()

_NO_PAPER = (
    "\n\nBackground:\n\n"
    "* Render the bird and the few elements at its feet on a FULLY TRANSPARENT "
    "background.\n"
    "* No paper, no margins, no page, no texture, no vignette, no backdrop of "
    "any kind behind the subject.\n"
)
_FLAT_PAPER = (
    "\n\nBackground:\n\n"
    "* Use a plain, perfectly smooth, evenly lit ivory background.\n"
    "* No paper grain, no aging, no mottling, no texture and no vignette in the "
    "background - keep it a single uniform colour.\n"
)


def _prompt_for(common: str) -> str:
    body = PROMPT.format(common=common)
    if BACKGROUND == "transparent":
        return body + _NO_PAPER
    if BACKGROUND == "flat":
        return body + _FLAT_PAPER
    return body


def generate(common: str, scientific: str, dest: Path) -> Path:
    """One plate for this species, written to `dest`."""
    client = _client()
    prompt = _prompt_for(common)
    kwargs = {"model": MODEL, "prompt": prompt, "size": SIZE, "quality": QUALITY}
    if BACKGROUND == "transparent":
        # Not every model accepts these; a refusal falls back to asking for flat
        # paper in words, which the cut-out can still handle.
        kwargs |= {"background": "transparent", "output_format": "png"}
    try:
        result = client.images.generate(**kwargs)
    except TypeError:
        result = _retry_flat(client, common)
    except Exception as e:
        msg = str(e)
        if BACKGROUND == "transparent" and (
            "background" in msg or "output_format" in msg or "unsupported" in msg.lower()
        ):
            result = _retry_flat(client, common)
        else:
            raise GenerateError(f"{MODEL} refused: {msg[:200]}") from e

    if not getattr(result, "data", None):
        raise GenerateError("no image returned")
    item = result.data[0]

    dest.parent.mkdir(parents=True, exist_ok=True)
    b64 = getattr(item, "b64_json", None)
    if b64:
        dest.write_bytes(base64.b64decode(b64))
        return dest
    url = getattr(item, "url", None)
    if url:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=180) as r:
            dest.write_bytes(r.read())
        return dest
    raise GenerateError("image had neither b64_json nor url")
