"""Build derivative reference images from references/ojisan/ojisan_trimmed.png.

Per ChatGPT advice (2026-05-10): we cannot grow the reference set from the OP
(static pose -> explosion, no usable extra angles). Instead, *split* the one
reference into multiple comparison axes: head / hair / face / silhouette x
grayscale / edges / binary / mask. The shape-based axes (silhouette, edges)
are intended to break the "atmospheric" bias of CLIP's full-image similarity
and let downstream comparison weight hair/nose/jaw/cheek/mouth geometry.

Outputs: references/ojisan/ojisan_*.png  (alongside the source).

Cropping is heuristic, not anatomical. We:
  1. Build a foreground mask by flooding from the four corners using the
     background-color sample taken at (0,0) ([58,58,58] in the current
     image). Any pixel within tolerance of background AND connected to a
     corner becomes background; everything else is foreground.
  2. Take the foreground bbox; split vertically into HAIR / FACE / TORSO
     bands by fixed proportions (top 22%, next 50%, bottom 28% of the
     bbox height). HEAD = HAIR + FACE.
  3. Mask the original RGB into each band, write bandwise grayscale and
     Canny edge maps.

If you want different splits later, tweak HAIR_FRAC / FACE_FRAC at the
top — no need to re-derive the mask.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from skimage import feature, filters, morphology

REF_DIR = Path(__file__).resolve().parent / "references" / "ojisan"
SOURCE  = REF_DIR / "ojisan_trimmed.png"

# Vertical split fractions of the foreground bbox.
HAIR_FRAC  = 0.22  # top band
FACE_FRAC  = 0.50  # middle band (face proper: brows-chin)
# TORSO is whatever is left at the bottom.

# Background-color tolerance (Euclidean RGB distance from corner sample).
BG_TOL = 14


def load_rgb(path: Path) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    return np.array(img)


def build_foreground_mask(rgb: np.ndarray) -> np.ndarray:
    """Return a (H,W) bool mask: True = foreground.

    Background is whatever shares the corner color AND is connected to one
    of the four corners. Pure thresholding would also kill dark hair, so the
    connectivity step matters."""
    h, w = rgb.shape[:2]
    bg_color = rgb[0, 0].astype(np.float32)
    # float32 to avoid int16 overflow on large channel diffs (e.g.
    # white-skin pixel 255 vs background 58 gives 197^2 * 3 = 116k, well
    # past int16's 32767 limit).
    diff = rgb.astype(np.float32) - bg_color[None, None, :]
    near_bg = np.sqrt((diff ** 2).sum(axis=-1)) <= BG_TOL  # bool

    # Flood from corners: keep only near_bg pixels connected to a corner.
    seeds = np.zeros_like(near_bg, dtype=bool)
    for y in (0, h - 1):
        for x in (0, w - 1):
            if near_bg[y, x]:
                seeds[y, x] = True
    bg_mask = morphology.reconstruction(
        seeds.astype(np.uint8),
        near_bg.astype(np.uint8),
        method="dilation",
    ).astype(bool)
    fg = ~bg_mask
    # Light cleanup: remove specks, fill small holes inside the figure.
    fg = morphology.remove_small_objects(fg, min_size=64)
    fg = morphology.remove_small_holes(fg, area_threshold=256)
    return fg


def bbox_of(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    return ys.min(), ys.max(), xs.min(), xs.max()


def write_gray(arr: np.ndarray, path: Path) -> None:
    Image.fromarray(arr.astype(np.uint8), mode="L").save(path)


def write_rgb(arr: np.ndarray, path: Path) -> None:
    Image.fromarray(arr.astype(np.uint8), mode="RGB").save(path)


def edges_canny(gray: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Return uint8 edge map (255 on edge, 0 elsewhere). If mask given,
    edges outside the mask are zeroed so the silhouette outline doesn't
    bleed into the body shape."""
    edges = feature.canny(gray.astype(float) / 255.0, sigma=1.5)
    if mask is not None:
        edges = edges & mask
    return (edges.astype(np.uint8) * 255)


def main() -> None:
    rgb = load_rgb(SOURCE)
    h, w = rgb.shape[:2]
    fg = build_foreground_mask(rgb)
    y0, y1, x0, x1 = bbox_of(fg)
    bbox_h = y1 - y0 + 1

    # Bands.
    hair_y1 = y0 + int(round(bbox_h * HAIR_FRAC))
    face_y1 = y0 + int(round(bbox_h * (HAIR_FRAC + FACE_FRAC)))
    head_y1 = face_y1  # HEAD = HAIR + FACE
    bands = {
        "hair":  (y0,       hair_y1),
        "face":  (hair_y1,  face_y1),
        "head":  (y0,       head_y1),
        "torso": (face_y1,  y1 + 1),
        "all":   (y0,       y1 + 1),
    }

    # Grayscale of the whole image (background blacked out).
    gray_full = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1]
                 + 0.114 * rgb[..., 2]).astype(np.uint8)
    gray_full = np.where(fg, gray_full, 0)

    # 1) Whole-figure outputs.
    silhouette = (fg.astype(np.uint8) * 255)
    write_gray(silhouette, REF_DIR / "ojisan_silhouette.png")
    write_gray(edges_canny(silhouette, mask=None), REF_DIR / "ojisan_silhouette_edges.png")
    write_gray(gray_full, REF_DIR / "ojisan_grayscale.png")
    write_gray(edges_canny(gray_full, mask=fg), REF_DIR / "ojisan_edges.png")

    # Otsu binary on grayscale (within mask).
    fg_pixels = gray_full[fg]
    if fg_pixels.size > 0:
        thr = filters.threshold_otsu(fg_pixels)
        binary = (gray_full >= thr) & fg
        write_gray((binary.astype(np.uint8) * 255), REF_DIR / "ojisan_binary.png")

    # 2) Per-band outputs (cropped to the band's vertical range, full width
    #    of the foreground bbox).
    for name, (yy0, yy1) in bands.items():
        if yy1 <= yy0:
            continue
        crop = rgb[yy0:yy1, x0:x1 + 1].copy()
        crop_mask = fg[yy0:yy1, x0:x1 + 1]
        # Black out background within the crop.
        crop[~crop_mask] = 0
        write_rgb(crop, REF_DIR / f"ojisan_{name}.png")
        gray_b = (0.299 * crop[..., 0] + 0.587 * crop[..., 1]
                  + 0.114 * crop[..., 2]).astype(np.uint8)
        write_gray(gray_b, REF_DIR / f"ojisan_{name}_gray.png")
        write_gray(edges_canny(gray_b, mask=crop_mask),
                   REF_DIR / f"ojisan_{name}_edges.png")
        sil = (crop_mask.astype(np.uint8) * 255)
        write_gray(sil, REF_DIR / f"ojisan_{name}_silhouette.png")

    # Report.
    print(f"image:           {w} x {h}")
    print(f"foreground bbox: y=[{y0},{y1}]  x=[{x0},{x1}]  h={bbox_h}")
    print(f"band y-cuts:     hair=[{y0},{hair_y1})  face=[{hair_y1},{face_y1})"
          f"  torso=[{face_y1},{y1 + 1})")
    print(f"wrote derivatives to {REF_DIR}")


if __name__ == "__main__":
    main()
