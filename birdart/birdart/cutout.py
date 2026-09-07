"""Turn a cropped plate region into a transparent, haloed PNG.

This is the mechanical half of `docs/adding-artwork.md`: delete the paper, then
put an #F0ECE5 halo behind what is left. Historical plates sit on flat, pale
paper, which is what makes it tractable without a human tracing the outline.

The background is found by connectivity, not by colour alone: a pixel is paper
only if it is paper-coloured AND reachable from the border without crossing the
bird. That is what stops a white wing patch or a pale breast from being punched
out of the middle of the bird.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage

from .config import HALO_PX, PAPER

MAX_SIDE = 1600  # plates arrive far larger than the 1200px the frame keeps
OPEN_ITERS = 2   # ~4px of thin structure removed: needles and grass, not legs
MAX_FILL = 0.75  # cleanly cut birds sit near 50%; foliage-bound ones exceed 90%
TOLERANCES = (30, 42, 55, 70, 88)  # widened until the background actually lifts


class CutoutError(RuntimeError):
    """The image does not look like a bird on pale paper."""


def _paper_colour(a: np.ndarray) -> np.ndarray:
    """Median of a border band - robust to a signature or a plate number."""
    b = max(2, min(a.shape[0], a.shape[1]) // 100)
    edge = np.concatenate(
        [
            a[:b].reshape(-1, 3),
            a[-b:].reshape(-1, 3),
            a[:, :b].reshape(-1, 3),
            a[:, -b:].reshape(-1, 3),
        ]
    )
    return np.median(edge, axis=0)


def cut(img: Image.Image, tol: int | None = None, halo_px: int = HALO_PX) -> Image.Image:
    """RGB crop in, RGBA cut-out with halo out.

    Paper is not one colour across sources: a clean gallery scan is near-white
    and uniform, while a century-old book plate is yellowed, mottled and printed
    on a page the scanner lit unevenly. A single tolerance therefore either
    leaves the background attached on the tired scans or eats into the bird on
    the clean ones, so widen it step by step and keep the first cut that has a
    bird's silhouette rather than the plate's rectangle.
    """
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)

    # A generated plate can arrive already cut out. Its own alpha is exact, so
    # guessing at a background colour could only make it worse - take the mask
    # as given and go straight to the halo.
    if _has_real_alpha(img):
        return _halo_only(img, halo_px)

    img = img.convert("RGB")
    a = np.asarray(img).astype(np.int16)

    tolerances = [tol] if tol is not None else TOLERANCES
    last: Exception = CutoutError("no tolerance tried")
    for t in tolerances:
        try:
            return _attempt(a, int(t), halo_px)
        except CutoutError as e:
            last = e
    raise last


def _has_real_alpha(img: Image.Image) -> bool:
    """True when the image carries a genuine cut-out, not a token alpha channel.

    A fully opaque RGBA (which is what a normal PNG plate looks like) must go
    down the paper-removal path; only an image that is actually transparent
    somewhere has a mask worth trusting.
    """
    if img.mode not in ("RGBA", "LA", "PA"):
        return False
    alpha = np.asarray(img.convert("RGBA"))[:, :, 3]
    clear = float((alpha < 32).mean())
    return 0.02 < clear < 0.98


def _halo_only(img: Image.Image, halo_px: int) -> Image.Image:
    """Put the paper-coloured halo behind an existing cut-out."""
    rgba = np.asarray(img.convert("RGBA"))
    fg = rgba[:, :, 3] > 128
    fg = ndimage.binary_fill_holes(fg)

    flab, fn = ndimage.label(fg)
    if fn > 1:  # drop stray specks the generator left floating
        sizes = ndimage.sum(fg, flab, range(1, fn + 1))
        keep = {i + 1 for i, s in enumerate(sizes) if s >= 0.02 * sizes.max()}
        fg = np.isin(flab, list(keep))

    halo = ndimage.binary_dilation(
        fg, ndimage.generate_binary_structure(2, 2), iterations=halo_px
    )
    out = np.zeros((*fg.shape, 4), dtype=np.uint8)
    out[halo] = (*PAPER, 255)
    out[fg, :3] = rgba[fg, :3]
    out[fg, 3] = 255
    result = Image.fromarray(out, "RGBA")
    box = result.getbbox()
    return result.crop(box) if box else result


def _attempt(a: np.ndarray, tol: int, halo_px: int) -> Image.Image:
    paper = _paper_colour(a)
    papery = np.sqrt(((a - paper) ** 2).sum(axis=2)) < tol

    # Background = paper-coloured regions connected to the image border.
    lab, n = ndimage.label(papery)
    if n == 0:
        raise CutoutError("no paper-coloured region found")
    border = set(lab[0].tolist()) | set(lab[-1].tolist())
    border |= set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
    border.discard(0)
    if not border:
        raise CutoutError("paper does not reach the border")
    background = np.isin(lab, list(border))

    fg = ~background
    if fg.mean() < 0.02:
        raise CutoutError("almost nothing left after removing paper")
    if fg.mean() > 0.92:
        raise CutoutError("background removal kept nearly the whole frame")

    # Strip thin structure before choosing a blob. Pine needles, grass and twigs
    # are a few pixels wide and touch the bird, so without this the "largest
    # component" is the whole thicket and the cut-out is a rectangle again. A
    # bird's body survives an opening this small; its legs and beak may thin,
    # which the closing below puts back.
    solid = ndimage.binary_opening(fg, structure=np.ones((3, 3)), iterations=OPEN_ITERS)
    if solid.sum() > 0.01 * fg.size:
        fg = solid

    # Keep only the bird's own blob. Detached foliage, the plate number and the
    # engraver's signature are all separate components; taking just the largest
    # is what turns "a piece of the plate" into "a bird".
    flab, fn = ndimage.label(fg)
    if fn > 1:
        sizes = ndimage.sum(fg, flab, range(1, fn + 1))
        fg = flab == (int(np.argmax(sizes)) + 1)

    fg = ndimage.binary_closing(fg, structure=np.ones((3, 3)), iterations=OPEN_ITERS)

    # Close pinholes inside the bird so the halo does not shine through it.
    fg = ndimage.binary_fill_holes(fg)

    halo = ndimage.binary_dilation(fg, ndimage.generate_binary_structure(2, 2), iterations=halo_px)

    # The honest test of a cut-out: does it have a bird's silhouette, or does it
    # fill its own bounding box like a crop of the plate? Measured on the haloed
    # shape, because that is what actually lands on the page. Cleanly cut birds
    # sit near 50%; a bird buried in foliage comes out above 90%. Failing here
    # is right - the caller then tries a cleaner plate rather than installing a
    # rectangle.
    ys, xs = np.nonzero(halo)
    if len(xs) == 0:
        raise CutoutError("nothing left to cut")
    bbox_area = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
    fill = halo.sum() / max(1, bbox_area)
    if fill > MAX_FILL:
        raise CutoutError(f"silhouette fills {fill:.0%} of its box - a rectangle, not a bird")

    out = np.zeros((*fg.shape, 4), dtype=np.uint8)
    out[halo] = (*PAPER, 255)          # halo ring, opaque paper colour
    out[fg, :3] = a[fg]                # the bird itself, original pixels
    out[fg, 3] = 255

    rgba = Image.fromarray(out, "RGBA")
    box = rgba.getbbox()
    return rgba.crop(box) if box else rgba


def cut_file(src: str, dest: str, box: dict | None = None) -> str:
    """Crop to `box` (fractional x0/y0/x1/y1) if given, then cut out."""
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(src)
    if box:
        w, h = im.size
        im = im.crop(
            (int(box["x0"] * w), int(box["y0"] * h), int(box["x1"] * w), int(box["y1"] * h))
        )
    cut(im).save(dest)
    return dest
