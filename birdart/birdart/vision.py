"""The judgement calls, handed to `claude -p`.

Two things in this pipeline are not mechanical: deciding whether a plate really
shows the species we asked for, and picking which single bird on a crowded plate
to cut. Both are given to the model with the image in hand; everything else here
is deterministic.
"""

from __future__ import annotations

import json
import re
import subprocess

from .config import CLAUDE_TIMEOUT

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.S)


def _run(prompt: str, timeout: int = CLAUDE_TIMEOUT) -> str:
    """One non-interactive model call. Read is allowed so it can open the plate."""
    try:
        p = subprocess.run(
            ["claude", "-p", prompt, "--allowedTools", "Read"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def _json(text: str) -> dict | None:
    """The model is asked for bare JSON; tolerate a fence or surrounding prose."""
    if not text:
        return None
    cleaned = _FENCE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    m = re.search(r"\{.*\}", cleaned, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def verify_cutout(path: str, scientific: str, common: str) -> bool | None:
    """Look at the finished cut-out and say whether it is actually a bird.

    The geometric gate in cutout.py catches rectangles, but a wide tolerance can
    also eat a plate down to a dark ragged blob that happens to have a bird-like
    fill ratio. Only looking at the result catches that, so the last word before
    anything is installed belongs to the model.

    None means the model could not be reached - the caller decides whether to
    trust the cut-out on geometry alone.
    """
    prompt = (
        f"Read the image at {path}. It is a cut-out that will be printed on a "
        f"paper-coloured page as an illustration of {common} ({scientific}).\n\n"
        "Judge it as a picture, strictly:\n"
        "- THE HEAD IS THE TEST. You must be able to make out an eye and a "
        "beak, with the face drawn in detail. If the head is a solid dark mass, "
        "a featureless blob, a silhouette, turned fully away, or lost against "
        "the body, answer false - however good the rest of the bird looks.\n"
        "- Is a single recognisable bird visible, with body and tail intact?\n"
        "- Is it free of large blocks of surrounding plate, text, or a second "
        "bird?\n"
        "- Is it a clean illustration rather than a smear, a torn-looking blob "
        "or a fragment?\n\n"
        "Answer false if you would be embarrassed to hang it in a picture "
        "frame. A faceless or damaged bird is much worse than no picture at "
        "all, and a later plate can always be tried.\n\n"
        'Reply with ONLY JSON, no prose and no fence: {"good":true|false,'
        '"why":"<max 12 words>"}'
    )
    data = _json(_run(prompt))
    if not isinstance(data, dict) or "good" not in data:
        return None
    return bool(data["good"])


def inspect_plate(path: str, scientific: str, common: str) -> dict | None:
    """Verify the plate shows this species and bound the one bird to cut.

    Returns {"ok", "x0", "y0", "x1", "y1", "why"} or None if the model could not
    be reached. `ok=False` means "wrong species or unusable", and the caller
    should move to the next candidate rather than cut something wrong.
    """
    prompt = (
        f"Read the image at {path}.\n\n"
        f"It should be a historical natural-history illustration of the bird "
        f"{common} ({scientific}).\n\n"
        "Decide two things:\n"
        "1. Does this image actually depict that species, drawn or painted "
        "(NOT a photograph, NOT a map, NOT a page of text, NOT a different "
        "species)? Historical plates often use old names, so judge by the bird "
        "itself.\n"
        "2. If yes, pick the ONE individual of that species that is most "
        "complete and least overlapped by other birds, and give a TIGHT "
        "bounding box around that bird alone.\n\n"
        "The box should hug the bird - include its tail and any perch directly "
        "under its feet, but exclude surrounding foliage, pine needles, grass "
        "and flowers wherever you can. A box full of vegetation cannot be cut "
        "out and will be thrown away.\n\n"
        "If the plate shows several species, be careful to box the correct one. "
        "If you are not confident it is the right species, say ok=false.\n\n"
        'Reply with ONLY a JSON object, no prose and no markdown fence:\n'
        '{"ok":true|false,"x0":<float>,"y0":<float>,"x1":<float>,"y1":<float>,'
        '"why":"<max 12 words>"}\n'
        "Coordinates are fractions 0-1 of image width and height."
    )
    data = _json(_run(prompt))
    if not isinstance(data, dict) or "ok" not in data:
        return None
    if not data.get("ok"):
        return {"ok": False, "why": str(data.get("why", "rejected"))[:80]}
    try:
        box = {k: float(data[k]) for k in ("x0", "y0", "x1", "y1")}
    except (KeyError, TypeError, ValueError):
        return None
    # A degenerate or inverted box would crop to nothing; treat as no answer.
    if not (0 <= box["x0"] < box["x1"] <= 1 and 0 <= box["y0"] < box["y1"] <= 1):
        return None
    if (box["x1"] - box["x0"]) < 0.02 or (box["y1"] - box["y0"]) < 0.02:
        return None
    box["ok"] = True
    box["why"] = str(data.get("why", ""))[:80]
    return box
