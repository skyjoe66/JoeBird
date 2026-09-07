"""Acquire one species: find a plate, verify it, cut it out, install it.

Each candidate plate is taken all the way through verification before the next
is tried, so a wrong-species plate costs one model call rather than poisoning
the style. Nothing is installed unless the cut-out survives every check.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from PIL import Image

from . import commons, state, vision
from .config import FUGLERAMME, STATE, STYLE, WORK, key_for
from .cutout import CutoutError, cut_file

# Named in the style's ATTRIBUTION.md; a Commons file's exact plate lives in
# manifest.json, while a generated one has no scan to point at.
MAX_CANDIDATES = 6
GENERATE_ATTEMPTS = int(os.environ.get("BIRDART_GENERATE_ATTEMPTS", "2"))
# "openai" generates a plate with the owner's own API key - the point of this
# fork; "commons" hunts Wikimedia for a public-domain one instead.
SOURCE = os.environ.get("BIRDART_SOURCE", "openai").strip().lower()
SOURCE_KEY = "generated" if SOURCE == "openai" else "commons"
MODEL_NAME = os.environ.get("BIRDART_IMAGE_MODEL", "gpt-image-2")
# Prefix marking a failure caused by the setup rather than by the species, so
# the watcher can hold rather than burn that bird's attempts.
CONFIG_ERROR = "config: "


def _tighten(box: dict, frac: float) -> dict:
    """Pull a box in towards its centre, trimming foliage the model left in."""
    cx = (box["x0"] + box["x1"]) / 2
    cy = (box["y0"] + box["y1"]) / 2
    hw = (box["x1"] - box["x0"]) / 2 * (1 - frac)
    hh = (box["y1"] - box["y0"]) / 2 * (1 - frac)
    return {"x0": cx - hw, "y0": cy - hh, "x1": cx + hw, "y1": cy + hh}


def _log(msg: str) -> None:
    print(msg, flush=True)


def _install(png: Path, scientific: str, page_url: str) -> bool:
    """Hand the finished cut-out to the project's own importer."""
    cmd = [
        "uv", "run", "--directory", str(FUGLERAMME),
        "python", "tools/add_bird.py", str(png),
        "--style", STYLE,
        "--key", key_for(scientific),
        "--source", SOURCE_KEY,
    ]
    if page_url:  # a generated plate has no scan to link
        cmd += ["--url", page_url]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        _log(f"    add_bird failed: {(p.stderr or p.stdout).strip()[:200]}")
        return False
    _log(f"    installed: {p.stdout.strip().splitlines()[-1][:120]}")
    _nudge_frame()
    return True


def _nudge_frame() -> None:
    """Make the frame notice the new picture.

    Its render loop redraws when the set of detected birds changes, not when the
    artwork folder does - so a bird acquired after its own detection would sit
    undrawn until some *other* species turned up. Restarting the loop is how the
    project itself applies a change (its self-update does exactly this), and the
    kiosk keeps showing the previous page until the new one is ready.
    """
    try:
        r = subprocess.run(
            ["sudo", "-n", "systemctl", "restart", "fugleramme-frame"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if r.returncode == 0:
            _log("    frame redrawn")
        else:
            _log(f"    could not restart the frame: {(r.stderr or '').strip()[:120]}")
    except Exception as e:
        _log(f"    could not restart the frame: {e}")


def _preview(png: Path) -> Path:
    """The cut-out flattened onto the frame's paper, which is how it will be
    seen. Judging the bare RGBA would mean judging it against a checkerboard."""
    out = png.with_name(png.stem + "-preview.png")
    with Image.open(png) as im:
        im = im.convert("RGBA")
        bg = Image.new("RGB", (im.width + 60, im.height + 60), (250, 249, 246))
        bg.paste(im, (30, 30), im)
        bg.thumbnail((900, 900))
        bg.save(out)
    return out


def _plausible(png: Path) -> bool:
    """A cut-out that is nearly all halo, or tiny, is not a bird."""
    with Image.open(png) as im:
        w, h = im.size
        if w < 120 or h < 120:
            _log(f"    rejected: too small ({w}x{h})")
            return False
        alpha = im.getchannel("A")
        opaque = sum(c for v, c in zip(range(256), alpha.histogram()) if v > 200)
        if opaque / (w * h) < 0.05:
            _log("    rejected: almost nothing opaque")
            return False
    return True


@contextmanager
def _only_one_at_a_time():
    """Serialise acquisitions across processes.

    The watcher runs continuously and a backfill is started by hand, so both can
    be live at once. Two acquisitions in parallel double the load on Commons -
    which already rate-limits us - and make the banner lie about which bird is
    being fetched. Waiting is always better than racing here.
    """
    STATE.mkdir(parents=True, exist_ok=True)
    lock = STATE / "acquire.lock"
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def acquire(scientific: str, common: str) -> tuple[bool, str]:
    """Returns (installed, reason)."""
    with _only_one_at_a_time():
        return _acquire(scientific, common)


def _acquire(scientific: str, common: str) -> tuple[bool, str]:
    if SOURCE == "openai":
        return _from_openai(scientific, common)
    return _from_commons(scientific, common)


def _from_openai(scientific: str, common: str) -> tuple[bool, str]:
    """Generate the plate rather than hunting for one.

    Same cut-out and same visual QA as a Commons plate - the only thing that
    changes is where the picture came from. Each generation costs money, so the
    retry budget is small and a rejected image is reported rather than looped.
    """
    from .generate import GenerateError, generate

    WORK.mkdir(parents=True, exist_ok=True)
    key = key_for(scientific)
    raw = WORK / f"{key}-generated.png"
    png = WORK / f"{key}-cutout.png"

    for attempt in range(1, GENERATE_ATTEMPTS + 1):
        _log(f"[{scientific}] generating a plate (attempt {attempt}/{GENERATE_ATTEMPTS})")
        try:
            generate(common, scientific, raw)
        except GenerateError as e:
            # A missing key, a dead credit balance or a refused model is a
            # problem with the setup, not with this bird. Marked so the watcher
            # holds instead of spending the species' three attempts - otherwise
            # one misconfiguration parks the entire queue in a couple of minutes.
            return False, f"{CONFIG_ERROR}{e}"
        except Exception as e:
            return False, f"generation failed: {e}"

        try:
            # No crop box: the prompt asks for a single bird on ivory paper
            # margins and no text at all, so the whole frame is the subject and
            # the cut-out simply lifts the paper away from the bird.
            cut_file(str(raw), str(png))
        except CutoutError as e:
            _log(f"    cutout failed: {e}")
            continue
        except Exception as e:
            return False, f"cutout error: {e}"

        if not _plausible(png):
            continue
        good = vision.verify_cutout(str(_preview(png)), scientific, common)
        if good is False:
            _log("    generated bird rejected on inspection")
            continue
        if good is None:
            _log("    could not inspect the generated bird; not installing blind")
            continue
        if _install(png, scientific, ""):
            return True, f"generated with {MODEL_NAME}"

    return False, f"no generated image passed inspection in {GENERATE_ATTEMPTS} attempts"


def _from_commons(scientific: str, common: str) -> tuple[bool, str]:
    WORK.mkdir(parents=True, exist_ok=True)
    key = key_for(scientific)
    _log(f"[{scientific}] searching Commons")
    try:
        cands = commons.candidates(scientific, common)
    except Exception as e:
        return False, f"commons search failed: {e}"
    if not cands:
        return False, "no public-domain candidates found"
    _log(f"  {len(cands)} candidate plate(s)")

    for i, c in enumerate(cands[:MAX_CANDIDATES], 1):
        _log(f"  [{i}] {c['title'][:70]} ({c['width']}x{c['height']}, {c['licence']})")
        raw = WORK / f"{key}-cand{i}{Path(c['url'].split('?')[0]).suffix or '.jpg'}"
        try:
            commons.download(c["url"], raw)
        except Exception as e:
            _log(f"    download failed: {e}")
            continue

        verdict = vision.inspect_plate(str(raw), scientific, common)
        if verdict is None:
            _log("    no usable answer from the model")
            continue
        if not verdict.get("ok"):
            _log(f"    rejected by model: {verdict.get('why', '')}")
            continue
        _log(f"    accepted: {verdict.get('why', '')}")

        png = WORK / f"{key}-cutout.png"
        # A box that caught surrounding foliage fails the silhouette test. Rather
        # than discard an otherwise correct plate, try again pulled in towards
        # the bird - that is usually all that stands between a rectangle and a
        # clean cut. Each variant is judged on its own merits, because a tighter
        # box can just as easily cut the bird in half.
        for attempt, box in enumerate((verdict, _tighten(verdict, 0.12), _tighten(verdict, 0.22))):
            try:
                cut_file(str(raw), str(png), box)
            except CutoutError as e:
                _log(f"    cutout {'retry ' if attempt else ''}failed: {e}")
                continue
            except Exception as e:
                _log(f"    cutout error: {e}")
                break
            if not _plausible(png):
                continue

            preview = _preview(png)
            good = vision.verify_cutout(str(preview), scientific, common)
            if good is False:
                _log(f"    cut-out rejected on inspection{' (box -%d%%)' % (12 * attempt) if attempt else ''}")
                continue
            if good is None:
                _log("    could not inspect the cut-out; not installing blind")
                continue
            if attempt:
                _log(f"    cut after tightening the box {attempt}x")
            if _install(png, scientific, c.get("page") or c["url"]):
                return True, c.get("page") or c["title"]

    return False, "no candidate survived verification"


def main() -> int:
    ap = argparse.ArgumentParser(description="Acquire artwork for one species.")
    ap.add_argument("scientific")
    ap.add_argument("common", nargs="?", default="")
    a = ap.parse_args()
    state.ensure_dirs()
    ok, why = acquire(a.scientific, a.common or a.scientific)
    _log(("DONE: " if ok else "FAILED: ") + why)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
