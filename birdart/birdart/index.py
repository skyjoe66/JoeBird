"""Write the shared library's index.json from a folder of finished cut-outs.

    uv run python -m birdart.index /path/to/joebird-library

The folder is a JoeBird `library/` as the frame uses it - `birds/*.png` and a
`manifest.json` - or a checkout of the shared library repository, which has the
same layout. Every file is hashed so a frame can verify what it downloads.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

_NUMBERED = re.compile(r"-(\d+)$")


def build(root: Path) -> dict:
    manifest = {}
    if (root / "manifest.json").exists():
        manifest = json.loads((root / "manifest.json").read_text())
    birds: dict[str, list[dict]] = {}
    for f in sorted((root / "birds").glob("*.png")):
        key = _NUMBERED.sub("", f.stem)
        entry = {
            "file": f"birds/{f.name}",
            "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
            "source": manifest.get(f"birds/{f.name}", {}).get("source", "generated"),
        }
        birds.setdefault(key, []).append(entry)
    return {"version": 1, "license": "CC0-1.0", "birds": birds}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    data = build(root)
    (root / "index.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    n = sum(len(v) for v in data["birds"].values())
    print(f"index.json: {len(data['birds'])} species, {n} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
