# JoeBird

Automatic artwork acquisition for [Fugleramme](https://github.com/arnegiacomo/fugleramme).

Fugleramme draws the birds it hears, but only the ones it has illustrations for.
Its bundled artwork covers Northern Europe, so anywhere else the frame shows an
empty perch no matter how much the detector hears. `birdart` closes that gap: it
watches what BirdNET-Go identifies, and for any species the frame cannot draw it
finds a public-domain plate, cuts the bird out, and installs it.

Nothing here is Florida-specific. The species list comes from BirdNET-Go's own
range filter, which follows the Pi's configured latitude and longitude, so the
same install builds Norwegian birds in Bergen and Floridian ones in Gainesville.

## Services

| Unit | What it does |
| --- | --- |
| `birdart-watcher` | Polls the detector; acquires artwork for anything heard but undrawable |
| `birdart-overlay` | Serves `/state` and `/collage.png` in front of the frame, drawing the "Image Search Underway" banner |

```bash
systemctl status birdart-watcher birdart-overlay
journalctl -u birdart-watcher -f
```

## Commands

```bash
cd birdart

# one species, now
uv run python -m birdart.acquire "Cardinalis cardinalis" "Northern Cardinal"

# everything in range that has no picture yet
uv run python -m birdart.backfill --list          # show the work
uv run python -m birdart.backfill --limit 10      # do ten of them

# what the bot is doing and what it has tried
curl -s http://birdnet/birdart/status | python3 -m json.tool
```

## How one acquisition works

1. **Shared library first.** `index.json` from the public library repository is
   checked for the species; a hit is downloaded, its sha256 verified, and it is
   installed. No token spent.
2. **Generate.** Otherwise OpenAI's image model is asked for a nineteenth-century
   natural-history plate of the bird - one adult, side profile, engraved line and
   watercolour on ivory paper - using your own API key.
3. **Cut out.** The paper is removed by connectivity, not colour alone, so a
   white wing patch is not punched out of the middle of the bird, and an
   `#F0ECE5` halo is dilated behind it to match the frame's paper.
4. **Gate.** A cut-out that is tiny, or nearly all halo, is thrown away. What
   survives is flattened onto paper and shown to `claude -p`, which has to agree
   it is that species, whole, with a properly formed head, before it is kept. A
   rejected image costs one more attempt; two rejections and the species waits.
5. **Install** through Fugleramme's own `tools/add_bird.py`, which assigns the
   filename, the next variant number and the `manifest.json` entry, then the
   frame is restarted so it redraws.

## Why the overlay sits in front

Fugleramme is a git checkout that updates itself with `git checkout --force`, so
a patched render loop would be reverted by the next update. Instead Apache sends
just `/state` and `/collage.png` to this service, which fetches them from the
frame and draws the banner over the picture. The admin page and everything else
still go straight to the frame, and nothing in the Fugleramme tree is modified.

The banner has to change the `/state` token as well as the image: the kiosk only
refetches the picture when that token moves, so a banner that left it alone
would never appear.

## State

Kept outside the Fugleramme checkout, where a self-update cannot reach it:

- `state/status.json` - what is being acquired right now; read by the overlay
- `state/ledger.json` - per-species attempts and outcomes
- `work/` - downloaded plates and intermediate cut-outs

## Install

Assumes a working Fugleramme on the same machine.

```bash
git clone https://github.com/skyjoe66/JoeBird.git ~/birdart
cd ~/birdart && uv sync

cp .env.example state/joebird.env
chmod 600 state/joebird.env
$EDITOR state/joebird.env         # API key if generating; every setting is documented there

sudo cp ../deploy/birdart-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now birdart-overlay birdart-watcher
```

To put the banner in front of the frame, merge `../deploy/apache-fugleramme.conf`
into your vhost: it sends `/state` and `/collage.png` to the overlay on 8081 and
everything else straight to the frame on 8080.

The watcher restarts `fugleramme-frame` after each install, so the user it runs
as needs passwordless sudo for that one command.

### Settings

`.env.example` documents every variable with its default; copy it to
`state/joebird.env`, which both units read. The ones you are most likely to
change:

| Variable | Default | Meaning |
| --- | --- | --- |
| `BIRDART_LIBRARY` | the public library | Shared library URL; empty disables |
| `BIRDART_STYLE` | `library` | Folder under `assets/artwork/` to install into; the fork keeps just one |
| `BIRDART_POLL` | `20` | Seconds between checks for newly heard species |
| `BIRDART_MAX_ATTEMPTS` | `3` | Failures before a species is parked |
| `BIRDART_IMAGE_MODEL` | `gpt-image-2` | Generation model |
| `BIRDART_IMAGE_BACKGROUND` | `transparent` | `transparent`, `flat` or `paper` |

## Licensing

**The code** in this repository is MIT - see [LICENSE](LICENSE). That covers the
bot, not the pictures it installs: an Audubon scan and a generated plate each
carry their own terms, and MIT says nothing about either.

**The artwork.** Everything the bot installs is AI-generated and dedicated to
the public domain under CC0; the library's `ATTRIBUTION.md` and `LICENSE` say
so, and `manifest.json` records where each file came from.
