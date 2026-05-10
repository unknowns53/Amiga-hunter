"""Crop reference image to head bbox and place on render-matched background.

Why: the reference image (IMG_2211.png) and Blender renders have different
backgrounds. perceptual-hash distance picks up that delta. By cropping the
reference to its content bbox and pasting onto the same dark-grey canvas
the renders use, we reduce structural noise in the phash distance.

Usage:
    python trim_reference.py
       --in references/IMG_2211.png
       --sample renders/<sha16>/threequarter.png
       --out references/IMG_2211_trimmed.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def detect_bbox(img: Image.Image, alpha_thresh: int = 16, white_thresh: int = 240) -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) bbox of non-background content."""
    if img.mode == "RGBA":
        # Alpha-based detection
        alpha = img.split()[-1]
        bbox = alpha.point(lambda v: 255 if v > alpha_thresh else 0).getbbox()
        if bbox is not None:
            return bbox
    # Fall back to white-background detection on RGB
    rgb = img.convert("RGB")
    px = rgb.load()
    w, h = rgb.size
    # Scan for non-near-white pixels
    L, T, R, B = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if not (r > white_thresh and g > white_thresh and b > white_thresh):
                if x < L: L = x
                if x > R: R = x
                if y < T: T = y
                if y > B: B = y
    return (L, T, R + 1, B + 1)


def sample_background(render_path: Path) -> tuple[int, int, int]:
    """Take the top-left pixel of a render as the background color."""
    img = Image.open(render_path).convert("RGB")
    return img.getpixel((4, 4))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", type=Path, default=Path("references/IMG_2211.png"))
    ap.add_argument("--sample", type=Path, required=True,
                    help="any rendered PNG to sample the background color from")
    ap.add_argument("--out", type=Path, default=Path("references/IMG_2211_trimmed.png"))
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--margin", type=float, default=0.08,
                    help="extra padding around head as fraction of canvas")
    args = ap.parse_args()

    src = Image.open(args.src)
    print(f"Source: {args.src}  mode={src.mode}  size={src.size}")

    bbox = detect_bbox(src)
    print(f"Detected content bbox: {bbox}")
    cropped = src.crop(bbox).convert("RGB")
    cw, ch = cropped.size
    print(f"Cropped size: {cw}x{ch}")

    bg = sample_background(args.sample)
    print(f"Background sampled from {args.sample.name}: {bg}")

    canvas = Image.new("RGB", (args.size, args.size), bg)
    margin_px = int(args.size * args.margin)
    inner = args.size - 2 * margin_px
    scale = min(inner / cw, inner / ch)
    new_w, new_h = int(cw * scale), int(ch * scale)
    resized = cropped.resize((new_w, new_h), Image.LANCZOS)
    paste_x = (args.size - new_w) // 2
    paste_y = (args.size - new_h) // 2
    canvas.paste(resized, (paste_x, paste_y))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.out)
    print(f"Wrote: {args.out}  size={args.size}x{args.size}  bg={bg}")


if __name__ == "__main__":
    main()
