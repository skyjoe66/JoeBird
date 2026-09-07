# library - attribution and licensing

Every style this fork ships, folded into one folder so the frame draws any bird
it hears that any of them can draw. Each file keeps the terms of the style it
came from; `manifest.json` links it to its plate, or marks it `synthetic` when
there is no plate at all. Nothing here is relicensed by being combined.

**Synthetic images are mixed in with real ones.** An entry whose source is
`generated` was produced by an image model, not cut from a scan, and its
copyright status is unsettled. Real plates come first in the variant order, so
`<key>.png` is a scan wherever one exists.

The sections below are each source style's own ATTRIBUTION.md, unedited.


---

## From `classic/`

# classic - attribution and licensing

Hand-coloured 1800s bird plates, cut and edited for this project, so none is
faithful to its scan. The style is offered under **CC BY-SA 4.0**, the most
restrictive of the sources below:

> Digital restorations, edited for this project.
> [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

`manifest.json` links each file to the plate it came from.

## Sources

**von Wright** - *Svenska Fåglar* by the **von Wright brothers** (Magnus
1805-1868, Wilhelm 1810-1887, Ferdinand 1822-1906), from the Commons category
[Svenska fåglar (von Wright)](https://commons.wikimedia.org/wiki/Category:Svenska_f%C3%A5glar_(von_Wright)):
340 rawpixel plates (CC BY-SA 4.0) and 71 public-domain files. The `perches/`
branches are cut from these and retouched with generative AI. Manifest key:
`vonwright`.

**von Wright (FNG)** - the brothers' studies, held by the **Finnish National
Gallery**, from
[rawpixel](https://www.rawpixel.com/art-studio/von%20wright?path=1525%7C%24publicdomain&sort=curated).
CC0. Manifest key: `vonwright-fng`.

**von Wright (rawpixel folio)** - rawpixel's own scans of the folio, (the ones Commons didnt have). CC0. Manifest key: `vonwright-rawpixel`.
 

**Gould** - *The Birds of Europe* by **John Gould** (1832-1837), Volumes 1-5,
from the Commons category
[The Birds of Europe (Gould)](https://commons.wikimedia.org/wiki/Category:The_Birds_of_Europe_(Gould)).
Public domain (PD-old-70-expired). Manifest key: `gould`.

**Gould (Birds of Asia)** - *The Birds of Asia* by **John Gould** and **Richard
Bowdler Sharpe** (1850-1883), Volume 5, plate drawn and lithographed by **John
Gould** and **William Hart**, printed by **Walter**, from the Commons category
[The Birds of Asia (John Gould), Volume 5](https://commons.wikimedia.org/wiki/Category:The_Birds_of_Asia_(John_Gould),_Volume_5).
Public domain (PD-Art, PD-old-100). Manifest key: `gould-asia`.

**Dresser** - *A History of the Birds of Europe* by **H. E. Dresser**
(1871-1881), plates by **J. G. Keulemans**, **Edward Neale**, **Archibald
Thorburn** and **Joseph Wolf**, with **Richard Bowdler Sharpe**, from the
Commons category
[A history of the birds of Europe](https://commons.wikimedia.org/wiki/Category:A_history_of_the_birds_of_Europe).
Scans from the Biodiversity Heritage Library, public domain
(PD-scan / PD-old-70-expired), and Commons uploads offered under CC BY-SA 4.0.
Manifest key: `dresser`.

**Keulemans** - *Onze vogels in huis en tuin* by **J. G. Keulemans**
(1869-1876), from the Biodiversity Heritage Library
[scan on Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Onze_vogels_in_huis_en_tuin_(12238985825).jpg).
Public domain (PD-scan / PD-old-70-expired); the BHL file is also offered under
CC BY 2.0. Manifest key: `keulemans`.


---

## From `custom/`

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


---

## From `generated/`

# generated - attribution and licensing

**The bird illustrations in this style are AI-generated. They are not historical
plates, and no part of them was drawn by the artists the style imitates.**

Each image was produced by OpenAI's image model from a prompt asking for a
nineteenth-century natural-history plate: a single anatomically accurate adult
bird in side profile, engraved linework with hand-applied watercolour, on ivory
paper. They were then background-removed, haloed and installed automatically by
the `birdart` bot.

This style is kept separate from `classic` and `custom` on purpose. Those hold
real scans of real plates, each linked to its source in `manifest.json`;
synthetic images have no such provenance and must not be mixed in with them
where a viewer would assume otherwise.

## What that means in practice

- **Accuracy is not guaranteed.** The plumage, proportions and markings are a
  model's rendering of a species, not an observation of one. Treat these as
  decoration, not as a field guide.
- **Provenance is nil.** There is no plate, no engraver, no holding institution,
  and `manifest.json` carries no source link for these files - only the
  `generated` key pointing here.
- **Licensing is unsettled.** The copyright status of AI-generated images varies
  by jurisdiction and is unresolved in several. Do not redistribute this style
  as though it carried the same clear terms as the public-domain plates in
  `classic`.

## Perches

The `perches/` branches are the exception: they are copied from `classic/`, cut
from **von Wright**'s *Svenska Fåglar* plates and retouched, and remain
CC BY-SA 4.0. They are here so the empty-window state works. Their entries in
`manifest.json` link the original scans. Manifest key: `vonwright`.

## Sources

**generated** - OpenAI image generation, prompted by the `birdart` bot. No
underlying scan, no original work, no attributable artist.
