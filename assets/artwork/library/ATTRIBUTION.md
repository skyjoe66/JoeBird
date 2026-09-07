# library - attribution and licensing

**Every bird in this folder is AI-generated.** None is a historical plate, and no
part of any was drawn by the artists the style imitates. This fork draws only
what the `birdart` bot generates with the owner's own OpenAI API key, so the
library is the record of what that key has produced.

Each image was made by OpenAI's image model from a prompt asking for a
nineteenth-century natural-history plate: a single anatomically accurate adult
bird in side profile, engraved linework with hand-applied watercolour, on ivory
paper. It was then background-removed, haloed, checked and installed by the bot
through `tools/add_bird.py`, which records it in `manifest.json`.

## What that means in practice

- **Accuracy is not guaranteed.** The plumage, proportions and markings are a
  model's rendering of a species, not an observation of one. Treat these as
  decoration, not as a field guide.
- **Provenance is nil.** There is no plate, no engraver, no holding institution,
  and `manifest.json` carries no source link for these files - only the source
  key pointing here.
- **Licensing: CC0.** To whatever extent the owner of the key that produced
  these images holds rights in them - which varies by jurisdiction and is
  unresolved in several - those rights are waived under
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/); the full text
  is in `LICENSE` beside this file. Use them for anything, no credit required.
  This is a waiver, not a warranty: nobody can grant more than they hold.

## Sources

**generated** - OpenAI image generation, prompted by the `birdart` bot. No
underlying scan, no original work, no attributable artist. Manifest key:
`generated`.

**von Wright** - the five `perches/` branches are the one exception: cut from
the von Wright brothers' *Svenska Fåglar* plates as shipped by upstream
Fugleramme's `classic` style, and retouched. CC BY-SA 4.0; their `manifest.json`
entries link the original scans. They are here so the empty-window state has
something to draw. Manifest key: `vonwright`.
