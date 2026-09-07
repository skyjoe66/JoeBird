# custom - attribution and licensing

A local style for this frame. Bird plates are cut and edited for this project,
so none is faithful to its scan.

The style as a whole is offered under **CC BY-SA 4.0**, the most restrictive of
the sources below. Adding a source with stricter terms means changing this line.

> Digital restorations, edited for this project.
> [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

`manifest.json` links each file to the plate it came from.

## Sources

**von Wright** - *Svenska Fåglar* by the **von Wright brothers** (Magnus
1805-1868, Wilhelm 1810-1887, Ferdinand 1822-1906), from the Commons category
[Svenska fåglar (von Wright)](https://commons.wikimedia.org/wiki/Category:Svenska_f%C3%A5glar_(von_Wright)):
340 rawpixel plates (CC BY-SA 4.0) and 71 public-domain files. The `perches/`
branches are cut from these and retouched with generative AI.

Used here for the five perches copied from `classic/`, so the empty-window state
works before any bird has been added. This is why the style is CC BY-SA 4.0.
Manifest key: `vonwright`.

**Audubon** - *The Birds of America* by **John James Audubon**
(1827-1838), engraved and hand-coloured by **Robert Havell Jr.**. The plates are
public domain by age (PD-old-100-expired).

Most files here are scans held by the **National Gallery of Art**, donated to
Wikimedia Commons under its open-access project and released **CC0**. A few are
other public-domain scans of the same plates (library and digital-archive
uploads) where the NGA had no copy. `manifest.json` links each file to the exact
scan it came from, so the per-file provenance is the manifest entry, not this
paragraph.

`manifest.json` links each file to the individual plate it was cut from.
Manifest key: `audubon`.

**Commons** - plates sourced automatically from Wikimedia Commons by the
`birdart` bot, cut out and haloed by it, and installed through the project's own
`tools/add_bird.py`. The bot accepts a file only when Commons reports it as
**public domain or CC0**; anything under a share-alike, unclear or non-free
licence is skipped rather than guessed at.

These files carry no per-plate credit line here on purpose: one automated source
key covers many different original works, so the honest record is the
`manifest.json` entry, which links the exact Commons file page for each image
and carries that page's own licence and author metadata.
Manifest key: `commons`.

<!--
Add one entry per source as you add birds, then use its key in `manifest.json`.
`tools/add_bird.py` warns when a manifest source is not named here.

Keys already used by `classic/`, reusable verbatim if you cut from the same
works: gould, vonwright, vonwright-fng, vonwright-rawpixel, dresser, keulemans
-->
