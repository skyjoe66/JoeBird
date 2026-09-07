# Contributing

JoeBird is one person's frame made public. Issues and pull requests are
welcome - fixes, docs and plates most of all.

| You have | Where it goes |
| --- | --- |
| A fix or a doc change | A pull request. No issue needed. |
| A plate your frame generated | A pull request to [joebird-library](https://github.com/skyjoe66/joebird-library) - see its README |
| Something broken | A bug report here |
| An idea, a question, a photo of your frame | Discussions |

Anything that changes the frame itself - `src/fugleramme/` - is usually
better sent upstream to [Fugleramme](https://github.com/arnegiacomo/fugleramme),
where it helps everyone; this fork pulls his `main` regularly. What belongs
here is the bot, the library, the deploy files and this README.

## Running it without a Pi

```bash
uv sync
uv run fugleramme-fake-detector      # stand-in BirdNET-Go on :8090
uv run fugleramme-dev                # :8080, restarts on save
cd birdart && uv sync                # the bot has its own environment
```

Kiosk on `http://localhost:8080/`, admin on `/admin`. The fake serves the same
`/api/v2` endpoints the frame reads; `--auth` and `--down` reproduce a
locked-down and an unreachable station. `uv run fugleramme-check` says whether
a real detector answers everything the frame needs.

The bot can be run one species at a time without a detector at all:

```bash
cd birdart
uv run python -m birdart.acquire "Cardinalis cardinalis" "Northern Cardinal"
```

## Before you open a PR

CI runs these over the whole tree, `birdart/` included:

```bash
uv run ruff format
uv run ruff check
uv run mypy
uv run pytest -q
```

If you touched `pyproject.toml`, commit `uv.lock` with it - CI installs with
`uv sync --locked`. Whether you write the code yourself or with an LLM is up to
you, as long as you can explain and stand behind it.

Commit messages are conventional commits - `feat:`, `fix:`, `docs:`, `chore:`
- so the history reads the same as upstream's.

## Plates

Every plate in a JoeBird library is generated: one adult bird, side profile,
in the style of a nineteenth-century natural-history engraving, on ivory
paper, cut out and haloed by the bot. That is the whole point - the pictures
match because they were all made the same way - so a hand-cut scan, however
lovely, does not belong here. It belongs upstream, where that is the whole
point instead.

The place to contribute a plate is the shared library, not this repository:
your frame drew it, so put it where the next frame can find it before it
spends a token. The steps and the terms (CC0, and that it really is your
frame's generation) are in
[joebird-library's README](https://github.com/skyjoe66/joebird-library#contributing-a-bird).

If a generated bird is wrong - the wrong species, a bad head, a second bird in
the frame - open an issue with the file name. The check that let it through is
in `birdart/vision.py`, and a failure there is worth a test.

## Docs

`docs/` is upstream's manual for building and living with a frame - hardware,
install, the display, operations, troubleshooting - and applies to JoeBird
unchanged. Improvements to it are best sent upstream.

## Licensing

The code is MIT and contributions come in under the same licence; there is no
CLA. Plates in the shared library are CC0, and by contributing one you are
saying it is your frame's generation and you dedicate it accordingly.
