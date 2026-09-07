"""Acquire one species: fetch it from the shared library if it is there, else
generate it; cut it out, check it, install it.

Nothing is installed unless the cut-out survives every check. Generation is the
last resort, not the first: it costs money, and a plate another frame already
paid for is one download away.
"""

from __future__ import annotations

import argparse
import fcntl
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from PIL import Image

from . import library, settings, state, vision
from .config import FUGLERAMME, STATE, STYLE, WORK, key_for
from .cutout import CutoutError, cut_file

# Every image the bot installs is synthetic; this manifest key says so, and the
# library's ATTRIBUTION.md is where it is explained.
SOURCE_KEY = "generated"
# Prefix marking a failure caused by the setup rather than by the species, so
# the watcher can hold rather than burn that bird's attempts.
CONFIG_ERROR = "config: "


def _log(msg: str) -> None:
    print(msg, flush=True)


def _install(png: Path, scientific: str, url: str) -> bool:
    """Hand the finished cut-out to the project's own importer."""
    cmd = [
        "uv",
        "run",
        "--directory",
        str(FUGLERAMME),
        "python",
        "tools/add_bird.py",
        str(png),
        "--style",
        STYLE,
        "--key",
        key_for(scientific),
        "--source",
        SOURCE_KEY,
    ]
    if url:  # a library file has an address worth recording; a fresh generation has none
        cmd += ["--url", url]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
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
            check=False,
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
        opaque = sum(c for v, c in zip(range(256), alpha.histogram(), strict=True) if v > 200)
        if opaque / (w * h) < 0.05:
            _log("    rejected: almost nothing opaque")
            return False
    return True


@contextmanager
def _only_one_at_a_time():
    """Serialise acquisitions across processes.

    The watcher runs continuously and a backfill is started by hand, so both can
    be live at once. Two generations in parallel double the spend for nothing
    and make the banner lie about which bird it means. Waiting is always better
    than racing here.
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
        ok, why = _from_library(scientific, common)
        if ok:
            return True, why
        return _from_openai(scientific, common)


def _from_library(scientific: str, common: str) -> tuple[bool, str]:
    """A plate another frame already generated and shared. Already a finished
    cut-out, so only the cheap sanity check stands between download and install;
    the hash check in `library.fetch` is what makes trusting it reasonable."""
    entries = library.lookup(scientific)
    if not entries:
        return False, "not in the shared library"
    WORK.mkdir(parents=True, exist_ok=True)
    png = WORK / f"{key_for(scientific)}-library.png"
    for entry in entries:
        _log(f"[{scientific}] fetching {entry['file']} from the shared library")
        try:
            url = library.fetch(entry, png)
        except Exception as e:
            _log(f"    fetch failed: {e}")
            continue
        if not _plausible(png):
            continue
        if _install(png, scientific, url):
            return True, f"fetched from the shared library ({entry['file']})"
    return False, "no library file could be used"


def _from_openai(scientific: str, common: str) -> tuple[bool, str]:
    """Generate the plate. Each generation costs money, so the retry budget is
    small and a rejected image is reported rather than looped."""
    from .generate import GenerateError, generate

    WORK.mkdir(parents=True, exist_ok=True)
    key = key_for(scientific)
    raw = WORK / f"{key}-generated.png"
    png = WORK / f"{key}-cutout.png"

    attempts, model = settings.attempts(), settings.model()
    for attempt in range(1, attempts + 1):
        _log(f"[{scientific}] generating a plate with {model} (attempt {attempt}/{attempts})")
        try:
            generate(common, scientific, raw)
        except GenerateError as e:
            # A missing key, a dead credit balance or a refused model is a
            # problem with the setup, not with this bird. Marked so the watcher
            # holds instead of spending the species' attempts - otherwise one
            # misconfiguration parks the entire queue in a couple of minutes.
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
            return True, f"generated with {model}"

    return False, f"no generated image passed inspection in {attempts} attempts"


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
