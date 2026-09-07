# JoeBird

A bird picture frame that draws every bird it hears. BirdNET-Go listens through
a microphone; the frame renders the species it identifies as nineteenth-century
natural-history plates on an e-ink panel or any screen; and for any bird it has
no picture of, JoeBird makes one - fetched from a shared library if another
frame already drew it, generated with your own OpenAI API key if not.

> Built on **[Fugleramme](https://github.com/arnegiacomo/fugleramme)** by
> Arne Giacomo Munthe-Kaas, which is the frame, the renderer, the admin page
> and the install - all of `src/`, `docs/`, `install.sh` and `run.sh` are his
> work, MIT licensed, and this repository stays a fork of it so his fixes keep
> flowing in. What JoeBird adds is below; everything after **How it works** is
> his README, kept as he wrote it.

## What JoeBird changes

- **Every picture is generated, and they all match.** Upstream ships hand-cut
  historical plates for Northern Europe, in styles you pick between. JoeBird
  ships none of that: `assets/artwork/library/` holds only what the bot has
  drawn, in one consistent style, so nothing on the glass looks pasted on. One
  folder, so there is no style to choose and the admin's style row is gone.
- **Birds it cannot draw get drawn.** [`birdart/`](birdart/) watches
  BirdNET-Go. For a species with no plate it first asks the
  [shared library](https://github.com/skyjoe66/joebird-library) - plates other
  frames have already generated, fetched and hash-checked, no token spent - and
  only then generates one, cuts it out, has it checked, and installs it. The
  frame shows *Building Image of Current Species* while that happens.
- **CC0.** The generated plates are dedicated to the public domain; see
  [`library/ATTRIBUTION.md`](assets/artwork/library/ATTRIBUTION.md).

Run it exactly as upstream's install below describes, then follow
[`birdart/README.md`](birdart/README.md) to start the bot with your key.

## How it works

BirdNET-Go listens on a USB mic and records what it identifies. Fugleramme polls the BirdNET-Go api, matches each species to an illustration, then packs them onto a page, and redraws only when the birds change. There's an admin page that lets you configure what to show, and automatic updates and such.

If you already run BirdNET-Go, point the frame at it instead - on the same machine or anywhere else reachable from your network.

## Hardware

A Raspberry Pi 5, an [Inky Impression 13.3"](https://shop.pimoroni.com/products/inky-impression)
(Spectra 6), a USB mic and an A4 frame. Full parts list, alternatives, and why
each part: **[Hardware](docs/hardware.md)**.

## Art

The birds are cut-outs from historic, public-domain natural-history drawings,
hand-curated for this project. Each detected species is matched to its
illustration, background-removed, and packed onto a textured paper page - larger
birds toward the centre, sized by body mass. An empty window shows a bare perch.

Half the point of this project is showing off some amazing public-domain natural-history illustrations: every bird is cut from a real plate, no art is AI-generated (though some has been retouched with AI).

See [Adding artwork](docs/adding-artwork.md) for manual cutout steps.

| No detections | A few visitors | A full garden |
| :---: | :---: | :---: |
| ![No birds detected](docs/assets/empty.png) | ![A few garden birds](docs/assets/few.png) | ![Many garden birds](docs/assets/many.png) |

## Known limitations

- **The artwork covers Northern Europe.** The plates are Scandinavian and
  British, so the Nordics, the British Isles and Germany are well covered. Elsewhere not so much (yet).
- **The mic matters more than the Pi.** Detection is BirdNET-Go's job, and how well it does depends mostly on the mic, where you put it, how many birds are in your area and so on.
- **BirdNET-Go OIDC not supported.** Currently only Basic Authentication (password) is supported. OIDC is in the works.

## Run locally (for development)

```bash
uv sync                                       # set up venv
uv run fugleramme-fake-detector               # stand-in BirdNET-Go on :8090
uv run fugleramme-dev                         # start service on :8080 with hot-reload
```

## Install on a Raspberry Pi

From the pi (assuming you have the hardware up and running):

```bash
curl -fsSL https://raw.githubusercontent.com/arnegiacomo/fugleramme/main/install.sh | bash
```

Asks where BirdNET-Go should live and which ports to use, clones the repo, installs the required deps, and starts the frame as a systemd service. **NB!** Will probably require a reboot on a fresh system.

If the display
stays blank after that, see
[Troubleshooting](docs/troubleshooting.md#panel-stays-blank).

From a blank SD card, see the full [install guide](docs/install.md).

## License

- Code: MIT - see [`LICENSE`](LICENSE).
- Detection ([BirdNET-Go](https://github.com/tphakala/birdnet-go), installed
  separately as a container): CC BY-NC-SA 4.0, non-commercial only. BirdNET model
  by the Cornell Lab of Ornithology and Chemnitz University of Technology,
  taxonomy data powered by eBird.org.
- Bird images: each style folder carries its own terms and sources, and its
  manifest links the plate every file was cut from. `classic` is
  CC BY-SA 4.0 - see
  [`assets/artwork/classic/ATTRIBUTION.md`](assets/artwork/classic/ATTRIBUTION.md).
- Label fonts (`assets/fonts/`): SIL OFL 1.1 - see
  [`assets/fonts/ATTRIBUTION.md`](assets/fonts/ATTRIBUTION.md).
- Bird sizes (`assets/bird_sizes.csv`): body mass from AVONET (Tobias et al.
  2022, Ecology Letters, [doi:10.1111/ele.13898](https://doi.org/10.1111/ele.13898)),
  CC BY 4.0.

## Prebuilt frames

I've built a few of these. If you'd like one rather than building it yourself,
please [get in touch](https://arnegiacomo.dev/).
