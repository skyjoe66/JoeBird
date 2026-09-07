"""Send a plate to the shared library as a pull request.

The gallery's "Send to library" button lands here. The library is a plain
GitHub repository, so contributing is git: clone it into work/, add the plate,
its manifest line and a rebuilt index.json on a branch, push, open a pull
request. GitHub's `gh` does the authenticated parts - it has to be installed
and logged in (`gh auth login`) as whoever is contributing. A frame that
cannot push to the library pushes the branch to a fork of it, which `gh`
creates on first use; the library's owner pushes straight to a branch there.
Either way the result is a PR the owner reviews, and its URL is remembered so
the gallery can show it.

    uv run python -m birdart.contribute "Agelaius phoeniceus" --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from . import index, library, settings, state
from .config import FUGLERAMME, STATE, STYLE, WORK, key_for

RECORD = STATE / "contributed.json"
# What the gallery shows when gh is missing or logged out - the whole fix, not a hint.
GH_HELP = (
    "GitHub's gh is not installed or not logged in. On the Pi, as the user the bot runs as: "
    "sudo apt install gh && gh auth login   (choose GitHub.com, SSH, and 'Login with a web browser' - "
    "it prints a code to enter at github.com/login/device). Then press Send again. "
    "Other systems: https://github.com/cli/cli#installation. "
    "Or skip gh and send it by hand: the library's README says how - "
    "https://github.com/skyjoe66/joebird-library#contributing-a-bird"
)
CLONE = WORK / "joebird-library"
_NUMBERED = re.compile(r"-(\d+)$")


class ContributeError(RuntimeError):
    pass


def repo() -> str:
    """owner/name of the library repository."""
    r = str(settings.get("library_repo", "BIRDART_LIBRARY_REPO", "skyjoe66/joebird-library"))
    return r.strip().strip("/")


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 300) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    if p.returncode != 0:
        raise ContributeError(f"{' '.join(cmd[:3])}: {(p.stderr or p.stdout).strip()[:300]}")
    return p.stdout.strip()


def _gh_login() -> str:
    try:
        return _run(["gh", "api", "user", "--jq", ".login"], timeout=30)
    except (ContributeError, FileNotFoundError) as e:
        raise ContributeError(GH_HELP) from e


def records() -> dict[str, dict]:
    return state._read(RECORD, {})


def in_library(scientific: str) -> bool:
    """Already served by the shared library, per its index."""
    return bool(library.lookup(scientific))


def _clone() -> Path:
    """A fresh checkout of the library's main, reused across calls."""
    WORK.mkdir(parents=True, exist_ok=True)
    if not (CLONE / ".git").is_dir():
        _run(["gh", "repo", "clone", repo(), str(CLONE), "--", "--depth", "1"], timeout=600)
    _run(["git", "fetch", "--depth", "1", "origin", "main"], cwd=CLONE, timeout=300)
    _run(["git", "checkout", "-q", "-B", "main", "origin/main"], cwd=CLONE)
    return CLONE


def _next_name(lib: Path, key: str) -> str:
    """<key>.png, or the next free -N: an existing species gets a variant."""
    taken = {
        p.name for p in (lib / "birds").glob(f"{key}*.png") if _NUMBERED.sub("", p.stem) == key
    }
    if f"{key}.png" not in taken:
        return f"{key}.png"
    n = 2
    while f"{key}-{n}.png" in taken:
        n += 1
    return f"{key}-{n}.png"


def submit(scientific: str, common: str = "", dry_run: bool = False) -> tuple[bool, str]:
    """Open a PR adding this species' plate. Returns (ok, url or reason)."""
    key = key_for(scientific)
    src = FUGLERAMME / "assets" / "artwork" / STYLE / "birds" / f"{key}.png"
    if not src.is_file():
        return False, f"no plate for {scientific} in the library"
    try:
        manifest = json.loads((src.parent.parent / "manifest.json").read_text())
    except (OSError, ValueError):
        manifest = {}
    entry = manifest.get(f"birds/{src.name}", {"source": "generated"})
    if entry.get("source") != "generated":
        return False, "only generated plates go to the shared library"

    try:
        login = _gh_login()
        lib = _clone()
        name = _next_name(lib, key)
        branch = f"add-{key}-{time.strftime('%Y%m%d-%H%M')}"
        _run(["git", "checkout", "-q", "-b", branch], cwd=lib)
        (lib / "birds").mkdir(exist_ok=True)
        (lib / "birds" / name).write_bytes(src.read_bytes())
        lib_manifest_path = lib / "manifest.json"
        try:
            lib_manifest = json.loads(lib_manifest_path.read_text())
        except (OSError, ValueError):
            lib_manifest = {}
        lib_manifest[f"birds/{name}"] = {"source": "generated"}
        lib_manifest_path.write_text(json.dumps(lib_manifest, indent=2, sort_keys=True) + "\n")
        data = index.build(lib)
        (lib / "index.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

        title = f"Add {common or scientific} ({scientific})" if common else f"Add {scientific}"
        body = (
            f"`birds/{name}` - generated by a JoeBird frame with "
            f"{settings.model()} and approved by its owner.\n\n"
            "Dedicated to the public domain under CC0, like everything in this library."
        )
        ident = ["-c", f"user.name={login}", "-c", f"user.email={login}@users.noreply.github.com"]
        _run(["git", *ident, "add", "-A"], cwd=lib)
        _run(["git", *ident, "commit", "-q", "-m", title + "\n\n" + body], cwd=lib)
        if dry_run:
            files = _run(["git", "show", "--stat", "--oneline", "HEAD"], cwd=lib)
            _run(["git", "checkout", "-q", "main"], cwd=lib)
            _run(["git", "branch", "-q", "-D", branch], cwd=lib)
            return True, f"dry run - would open PR '{title}' on {repo()} from {login}:\n{files}"

        owner = repo().split("/")[0]
        if login.lower() == owner.lower():
            _run(["git", "push", "-q", "-u", "origin", branch], cwd=lib, timeout=600)
            head = branch
        else:
            _run(["gh", "repo", "fork", repo(), "--clone=false"], cwd=lib, timeout=120)
            fork = f"git@github.com:{login}/{repo().split('/')[1]}.git"
            _run(["git", "remote", "remove", "fork"], cwd=lib) if "fork" in _run(
                ["git", "remote"], cwd=lib
            ).split() else None
            _run(["git", "remote", "add", "fork", fork], cwd=lib)
            _run(["git", "push", "-q", "-u", "fork", branch], cwd=lib, timeout=600)
            head = f"{login}:{branch}"
        url = _run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                repo(),
                "--head",
                head,
                "--title",
                title,
                "--body",
                body,
            ],
            cwd=lib,
            timeout=120,
        )
        _run(["git", "checkout", "-q", "main"], cwd=lib)
        rec = records()
        rec[scientific] = {"url": url, "file": name, "when": time.time()}
        state._write_atomic(RECORD, rec)
        return True, url
    except ContributeError as e:
        return False, str(e)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("scientific")
    ap.add_argument("common", nargs="?", default="")
    ap.add_argument("--dry-run", action="store_true", help="do everything but push and open the PR")
    a = ap.parse_args()
    ok, msg = submit(a.scientific, a.common, dry_run=a.dry_run)
    print(("OK: " if ok else "FAILED: ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
