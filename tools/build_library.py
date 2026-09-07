"""Fold every artwork style into one `library/`, so the frame has nothing to choose.

Upstream groups artwork by style and shows one at a time; a bird in `custom/`
does nothing for a frame set to `classic/`. This fork wants the union: whatever
is heard, draw it if any style can. With a single folder under `assets/artwork/`
the picker collapses on its own - `names.resolve` has one answer, button D has
nothing to cycle - so no renderer change is needed.

    uv run python tools/build_library.py                 # classic custom generated -> library
    uv run python tools/build_library.py classic mine    # explicit sources, in priority order

Sources are read in the order given, and that order is the variant order: a
species with a real plate in `classic/` and a synthetic one in `generated/` ends
up as `<key>.png` (real) and `<key>-2.png` (synthetic). Perches are deduplicated
by content. The manifests are merged and re-keyed to the new filenames; an entry
whose source is `generated` is a synthetic image: that key is the marker, and it
is what upstream's add_bird.py preserves when it rewrites the manifest (a boolean
field came back as the string "True"). ATTRIBUTION.md is the sources' own, one
section each, so every manifest key stays named.

To pick up new upstream plates after the source folders are gone from the tree:

    git checkout upstream/main -- assets/artwork/classic
    uv run python tools/build_library.py
    git rm -r -q assets/artwork/classic
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IMAGES = REPO / "assets" / "artwork"
BIRDS, PERCHES = "birds", "perches"
MANIFEST, ATTRIBUTION = "manifest.json", "ATTRIBUTION.md"
# The library is now the bot's own output and the source of truth; this tool
# remains for folding a style folder into it, and defaults to nothing.
DEFAULT_SOURCES: tuple[str, ...] = ()
OUT = "library"
SYNTHETIC_SOURCE = "generated"
_NUMBERED = re.compile(r"-(\d+)$")


def _variant_order(path: Path) -> tuple[int, str]:
    m = _NUMBERED.search(path.stem)
    return (int(m.group(1)) if m else 1, path.name)


def _key(path: Path) -> str:
    return _NUMBERED.sub("", path.stem)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(style: Path) -> dict[str, dict]:
    p = style / MANIFEST
    return json.loads(p.read_text()) if p.exists() else {}


def build(sources: list[Path], final: Path) -> dict[str, int]:
    """Assemble beside `final`, then swap it in. The bot polls the library every
    few seconds and draws whatever it cannot find, so the folder must never be
    seen half-built: an empty library/ mid-rebuild once cost a generated plate."""
    out = final.with_name(final.name + ".building")
    if out.exists():
        shutil.rmtree(out)
    (out / BIRDS).mkdir(parents=True)
    (out / PERCHES).mkdir()
    stats = _assemble(sources, out)
    old = final.with_name(final.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if final.exists():
        final.rename(old)
    out.rename(final)
    if old.exists():
        shutil.rmtree(old)
    return stats


def _assemble(sources: list[Path], out: Path) -> dict[str, int]:

    manifest: dict[str, dict] = {}
    by_key: dict[str, list[tuple[Path, Path]]] = {}  # species -> [(style, file)] in priority order
    for style in sources:
        for f in sorted((style / BIRDS).glob("*.png"), key=_variant_order):
            by_key.setdefault(_key(f), []).append((style, f))

    for key, files in sorted(by_key.items()):
        for n, (style, f) in enumerate(files, start=1):
            name = f"{key}.png" if n == 1 else f"{key}-{n}.png"
            shutil.copy2(f, out / BIRDS / name)
            entry = dict(_manifest(style).get(f"{BIRDS}/{f.name}", {}))
            if entry:
                manifest[f"{BIRDS}/{name}"] = entry

    seen: dict[str, str] = {}
    for style in sources:
        for f in sorted((style / PERCHES).glob("*.png")):
            digest = _sha(f)
            if digest in seen:
                continue
            seen[digest] = f.name
            shutil.copy2(f, out / PERCHES / f.name)
            perch = _manifest(style).get(f"{PERCHES}/{f.name}")
            if perch:
                manifest[f"{PERCHES}/{f.name}"] = dict(perch)

    (out / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    parts = [
        "# library - attribution and licensing\n",
        (
            "Every style this fork ships, folded into one folder so the frame draws any bird\n"
            "it hears that any of them can draw. Each file keeps the terms of the style it\n"
            "came from; `manifest.json` links it to its plate, or names `generated` as its\n"
            "source when there is no plate at all. Nothing here is relicensed by being\n"
            "combined.\n"
        ),
        (
            "**Synthetic images are mixed in with real ones.** An entry whose source is\n"
            f"`{SYNTHETIC_SOURCE}` was produced by an image model, not cut from a scan, and its\n"
            "copyright status is unsettled. Real plates come first in the variant order, so\n"
            "`<key>.png` is a scan wherever one exists.\n"
        ),
        "The sections below are each source style's own ATTRIBUTION.md, unedited.\n",
    ]
    for style in sources:
        text = (style / ATTRIBUTION).read_text() if (style / ATTRIBUTION).exists() else ""
        parts.append(f"\n---\n\n## From `{style.name}/`\n\n" + text.strip() + "\n")
    (out / ATTRIBUTION).write_text("\n".join(parts))

    named = set(re.findall(r"`([^`]+)`", (out / ATTRIBUTION).read_text()))
    orphans = sorted({e["source"] for e in manifest.values() if e.get("source")} - named)
    if orphans:
        sys.exit(f"manifest sources not named in {ATTRIBUTION}: {orphans}")

    return {
        "species": len(by_key),
        "birds": sum(len(v) for v in by_key.values()),
        "perches": len(seen),
        "manifest": len(manifest),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "sources",
        nargs="*",
        default=list(DEFAULT_SOURCES),
        help="style folders under assets/artwork, in priority order",
    )
    args = ap.parse_args()
    sources = [IMAGES / s for s in args.sources if (IMAGES / s / BIRDS).is_dir()]
    if not sources:
        sys.exit(f"no source styles found under {IMAGES} (looked for {args.sources})")
    stats = build(sources, IMAGES / OUT)
    print(
        f"built {OUT}/ from {', '.join(s.name for s in sources)}: "
        f"{stats['species']} species, {stats['birds']} bird files, "
        f"{stats['perches']} perches, {stats['manifest']} manifest entries"
    )


if __name__ == "__main__":
    main()
