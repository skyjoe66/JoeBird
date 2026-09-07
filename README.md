# JoeBird

A bird picture frame that draws every bird it hears.

A microphone listens. [BirdNET-Go](https://github.com/tphakala/birdnet-go)
names what it hears. The frame renders each species as a nineteenth-century
natural-history plate - engraved line, hand-tinted, on ivory paper - on an
e-ink panel in a picture frame, or on any screen. And when it hears a bird it
has no plate for, it makes one: fetched from a shared library if another
frame has already drawn it, generated with your own OpenAI key if not. Every
picture on the glass was made the same way, so they hang together as one
sheet.

> Built on **[Fugleramme](https://github.com/arnegiacomo/fugleramme)** by
> Arne Giacomo Munthe-Kaas: the frame, the renderer, the admin page and the
> install are his, MIT licensed, and this repository stays a fork so his fixes
> keep flowing in. Fugleramme ships hand-cut historical plates for Northern
> Europe; JoeBird is for everywhere else.

## How it works

```
 USB mic ──▶ BirdNET-Go ──▶ the frame ──▶ e-ink panel / kiosk
  (detector, :8090)         (renders :8080)
                  │              ▲
                  │   heard,     │ installs, redraws
                  ▼   undrawable │
              the bot ──▶ shared library? ──▶ generate ──▶ cut out ──▶ check
              (birdart)     (fetch, free)     (OpenAI)     (halo)   (claude -p)
```

1. **The detector** hears a bird and records it. Its own range filter, set by
   the Pi's latitude and longitude, decides which species are plausible.
2. **The frame** polls the detector, matches each species to a plate in
   `assets/artwork/library/`, packs them onto one page and redraws when the
   birds change. Species with no plate are left off.
3. **The bot** polls the same detector. For a species with no plate it first
   asks the [shared library](https://github.com/skyjoe66/joebird-library) -
   plates other frames have generated, downloaded and hash-checked, no token
   spent. Only on a miss does it generate one, cut the paper away, halo it to
   match the page, have `claude -p` confirm it is that bird with a properly
   formed head, and install it. The frame shows *Building Image of Current
   Species* meanwhile, then redraws.

The library starts with whatever it holds and grows as birds are heard. One
folder, one style, nothing to pick.

## Hardware

A Raspberry Pi 5, an [Inky Impression 13.3"](https://shop.pimoroni.com/products/inky-impression)
(Spectra 6), a USB microphone and an A4 frame. The panel is optional: without
one the frame runs web-only and any screen on the network can show it. Full
parts list and why each part: **[Hardware](docs/hardware.md)**.

## Install

On the Pi, with the hardware attached:

```bash
curl -fsSL https://raw.githubusercontent.com/skyjoe66/joebird/main/install.sh | bash
```

That asks where BirdNET-Go should live and which ports to use, clones this
repository to `~/joebird`, installs the dependencies, and starts the frame as
a service. A fresh system will probably want a reboot. From a blank SD card,
the full **[install guide](docs/install.md)** applies unchanged.

Then the bot, which needs your OpenAI key:

```bash
cd ~/joebird/birdart && uv sync
cp .env.example state/joebird.env && chmod 600 state/joebird.env
$EDITOR state/joebird.env            # OPENAI_API_KEY=...; everything else is documented there

sudo cp ../deploy/birdart-*.service /etc/systemd/system/   # edit the paths and User= first
sudo systemctl daemon-reload
sudo systemctl enable --now birdart-overlay birdart-watcher
```

`deploy/` also holds the Apache site that puts the bot's banner in front of
the frame, and `kiosk.sh`, which opens Chromium full-screen on the Pi's own
display. The bot restarts the frame after each install, so the user it runs as
needs passwordless `sudo` for that one command. **[birdart/README.md](birdart/README.md)**
covers its commands, settings and state.

## Living with it

- **`http://<pi>:8080/`** is the frame; **`/admin`** is the settings page:
  display mode, kiosk size, rotation, how far back to look, species names and
  their language, typeface. All live, no restart.
- **`http://<pi>:8090/`** is BirdNET-Go's own dashboard: detections,
  spectrograms, live audio, its range filter and location.
- **`http://<pi>/birdart/`** is the bot: what it is drawing, what it has tried.
  **`/birdart/gallery`** is every plate it has drawn - reject one with a note and
  it redraws, or send one to the shared library as a pull request.
- The panel's four buttons cycle display modes, toggle names and rotate.

**Cost.** A generation is one image-model call, and each species is generated
at most once - after that it is in your library, and if you contribute it, in
everyone's. A frame that hears forty species in its first month makes at most
forty calls, fewer for anything the shared library already has.

## The shared library

[`skyjoe66/joebird-library`](https://github.com/skyjoe66/joebird-library) is
a plain public repository: `index.json` maps a species to its files and their
sha256, and `birds/` holds the plates. A frame reads it over raw GitHub; any
repository with the same layout works in its place (`BIRDART_LIBRARY`).
Contributing a bird your frame drew is a pull request; the terms are in that
repository's README. Everything in it is CC0.

## Run it without a Pi

Everything but the panel, the buttons and the microphone runs on a
workstation:

```bash
uv sync
uv run fugleramme-fake-detector      # stand-in BirdNET-Go on :8090, generated detections
uv run fugleramme-dev                # the frame on :8080, restarts on save
```

`uv run fugleramme-frame --preview out.png` renders the page once and exits.
`uv run fugleramme-check` says whether a real detector answers everything the
frame needs. The bot's `python -m birdart.simulate` feeds a species in by
hand so the whole path can be watched without waiting for a bird.

## Layout

```
src/fugleramme/    the frame - upstream's renderer, admin and service; one row hidden
assets/artwork/    library/ - every plate the bot has made, plus five perches for an empty page
birdart/           the bot - watcher, generate, cut-out, check, library client, overlay
deploy/            systemd units, the Apache site, kiosk.sh
detector/          BirdNET-Go, containerised; its config and data stay out of git
tools/             add_bird.py (upstream's importer), build_library.py
docs/              upstream's manual: hardware, install, display, operations, troubleshooting
```

## Licensing

The code is **MIT** - Fugleramme's licence, kept, with Arne's copyright
notice as it requires. The generated plates are dedicated to the public
domain under **CC0**; `assets/artwork/library/ATTRIBUTION.md` says exactly
what that dedication can and cannot promise for an AI-generated image. The
five perches are cut from the von Wright brothers' *Svenska Fåglar* and remain
CC BY-SA 4.0.

Fugleramme's own README, with the story of the original frame in a kitchen
window in Bergen, is at [arnegiacomo/fugleramme](https://github.com/arnegiacomo/fugleramme).
