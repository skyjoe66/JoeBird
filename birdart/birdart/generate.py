"""Generate a plate with an image model - OpenAI, or Gemini's Imagen.

The images are synthetic and the library's ATTRIBUTION.md says so. Which
provider, which model, at what quality, and with what extra instructions are all
settings (`settings.py`), written from the frame's admin page and read at the
moment of each call.

The generated plate still goes through the same cut-out and the same visual QA
as a Commons plate. The prompt asks for a single bird on generous ivory paper
margins with no text at all, which is the easiest case the cut-out ever sees -
flat, uniform paper, rather than the mottled century-old scans it keeps failing
on. The frame draws the species caption itself, as it always has.
"""

from __future__ import annotations

import base64
import urllib.request
from pathlib import Path

from . import settings
from .config import USER_AGENT

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
* Both legs and both feet anatomically visible and correctly attached to the body, each foot with the correct toes, the bird standing naturally on them.
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
* AI artifacts: a missing, extra, fused or floating limb; a bird with only one visible leg; a foot not joined to its leg.
* Watermarks or signatures.

Generate the finished image directly without asking follow-up questions."""

SIZE = "1024x1536"  # portrait, as the prompt asks


class GenerateError(RuntimeError):
    pass


def _retry_flat(client, common: str, scientific: str):
    """This model will not do transparency: ask for flat ivory paper instead."""
    return client.images.generate(
        model=settings.model(),
        prompt=_body(common, scientific) + _FLAT_PAPER,
        size=SIZE,
        quality=settings.quality(),
    )


def api_key() -> str:
    """The OpenAI key: the admin's settings file, else the environment, else
    state/openai.env, which systemd also reads. A file rather than the unit so
    the key never appears in `systemctl cat`, `ps`, or this repository."""
    key = settings.api_key("openai")
    if not key:
        raise GenerateError("no OpenAI API key - set one in the admin page's AI images section")
    return key


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
# Gemini cannot return transparency, and flat ivory is fatal for a white bird:
# the cut-out keys on the border colour, so a White Ibis lost its head, neck
# and breast to the paper (2026-09-08). A saturated green is far from any
# plumage, so the tightest tolerance lifts it cleanly and the bird stays whole.
_CHROMA_KEY = (
    "\n\nBackground:\n\n"
    "* Place the bird and the few elements at its feet on a plain, perfectly "
    "flat, uniform bright green (#00FF00) backdrop, as for chroma keying.\n"
    "* No paper, no margins, no texture, no gradient, no vignette and no shadow "
    "on the backdrop - one solid colour edge to edge.\n"
    "* Keep the bird's own colours natural; no green cast on its plumage.\n"
)


def _body(common: str, scientific: str) -> str:
    """The prompt, plus whatever the owner added on the admin page, plus the
    note they wrote for this species when they asked for it to be redrawn."""
    body = PROMPT.format(common=common)
    extra = settings.extra_prompt()
    if extra:
        body += f"\n\nAdditional instructions:\n\n{extra}\n"
    note = settings.note_for(scientific)
    if note:
        body += f"\n\nA previous attempt at this bird was rejected. This time make sure: {note}\n"
    return body


def _prompt_for(common: str, scientific: str) -> str:
    body = _body(common, scientific)
    bg = settings.background()
    if bg == "transparent":
        return body + _NO_PAPER
    if bg == "flat":
        return body + _FLAT_PAPER
    return body


def generate(common: str, scientific: str, dest: Path) -> Path:
    """One plate for this species, written to `dest`, by whichever provider the
    settings name."""
    if settings.provider() == "gemini":
        return _generate_gemini(common, scientific, dest)
    return _generate_openai(common, scientific, dest)


def _generate_openai(common: str, scientific: str, dest: Path) -> Path:
    client = _client()
    prompt = _prompt_for(common, scientific)
    model, quality, background = settings.model(), settings.quality(), settings.background()
    kwargs = {"model": model, "prompt": prompt, "size": SIZE, "quality": quality}
    if background == "transparent":
        # Not every model accepts these; a refusal falls back to asking for flat
        # paper in words, which the cut-out can still handle.
        kwargs |= {"background": "transparent", "output_format": "png"}
    try:
        result = client.images.generate(**kwargs)
    except TypeError:
        result = _retry_flat(client, common, scientific)
    except Exception as e:
        msg = str(e)
        if background == "transparent" and (
            "background" in msg or "output_format" in msg or "unsupported" in msg.lower()
        ):
            result = _retry_flat(client, common, scientific)
        else:
            raise GenerateError(f"{model} refused: {msg[:200]}") from e

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


def _generate_gemini(common: str, scientific: str, dest: Path) -> Path:
    """Gemini image models through the google-genai SDK. They have no
    transparent output, so the bird is asked for on a chroma-green backdrop and
    the cut-out lifts that instead of paper. Verified live (2026-09-08); image
    models have no free-tier quota, so the key's project needs billing enabled.
    The imagen-* branch only works on Google's Enterprise platform, not with a
    developer key."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise GenerateError(f"google-genai package not available: {e}") from e
    key = settings.api_key("gemini")
    if not key:
        raise GenerateError("no Gemini API key - set one in the admin page's AI images section")
    model = settings.model()
    prompt = _body(common, scientific) + _CHROMA_KEY
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        client = genai.Client(api_key=key)
        if model.startswith("imagen"):
            # Imagen models have their own endpoint.
            result = client.models.generate_images(
                model=model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1, aspect_ratio="3:4", output_mime_type="image/png"
                ),
            )
            images = getattr(result, "generated_images", None) or []
            if not images or not getattr(images[0], "image", None):
                raise GenerateError("no image returned")
            dest.write_bytes(images[0].image.image_bytes)
            return dest
        # gemini-*-flash-image and friends answer through generate_content with an
        # image part in the response.
        result = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        for cand in getattr(result, "candidates", None) or []:
            for part in getattr(getattr(cand, "content", None), "parts", None) or []:
                blob = getattr(part, "inline_data", None)
                if blob is not None and getattr(blob, "data", None):
                    dest.write_bytes(blob.data)
                    return dest
        raise GenerateError("no image part in the response")
    except GenerateError:
        raise
    except Exception as e:
        raise GenerateError(f"{model} refused: {str(e)[:200]}") from e
