"""Re-rank CLIP top-N candidates by shape similarity instead of semantic
similarity.

Why this exists: CLIP's full-image cosine pulls in any "front-facing male
head with dark hair" with comparable atmosphere; the existing top tier
(NURBNERD/FACE2/CAPTAIN/HEAD_C/etc.) all share that vibe but none of them
match ojisan in actual mesh geometry. Shape-based axes (Canny edges of
foreground crops) are insensitive to color and lighting, so they should
let hair contour, jaw line, nose bridge, mouth opening — the parts we
actually care about — drive the ranking.

Pipeline per candidate:
  1. Read render (front/threequarter/side PNGs).
  2. Build foreground mask by flooding from corners (same logic as
     build_reference_variants.py).
  3. Crop to fg bbox, pad to square, resize to a common 256x256.
  4. Canny edges.
  5. Compare to reference edges (also resized to 256x256 with the same
     square-pad rule) using two metrics:
       - dilated edge IoU  (small dilation tolerates 1-2 px misalignment)
       - symmetric chamfer distance, normalized to [0,1]-ish via 1/(1+d)
  6. Take max over views.

Output: output/shape_similarity_ranking.csv  (rank, sha_prefix, name,
shape_score, iou, chamfer, best_view, source_path).

Defaults to scoring CLIP top 200 (cheap, ~minutes on CPU). Pass --top 0
to score everything ranked by CLIP.

Usage:
    python compare_renders_shape.py
    python compare_renders_shape.py --reference references/ojisan/ojisan_edges.png
    python compare_renders_shape.py --top 500 --output output/shape_full.csv
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from skimage import feature, morphology

ROOT = Path(__file__).resolve().parent
RENDERS_DIR = ROOT / "renders"
OUTPUT_DIR  = ROOT / "output"

# Common comparison size. Bigger = more detail but slower; 256 keeps a
# 1014-candidate pass under a minute.
COMPARE_SIZE = 256
# Dilation radius (pixels) for tolerant IoU. Edges from different renderers
# never line up to the pixel; 2 px lets a slightly wider/narrower jaw still
# count as overlap.
DILATE_R = 2
# Background-color tolerance for foreground extraction (matches
# build_reference_variants.py default).
BG_TOL = 14

# Render views we score per candidate.
VIEWS = ("front", "threequarter", "side")

log = logging.getLogger("shape_rank")


# ---------- foreground mask + crop ---------------------------------------

def foreground_mask(rgb: np.ndarray, bg_color: np.ndarray) -> np.ndarray:
    """Flood from corners using bg_color as the seed, keep what survives."""
    diff = rgb.astype(np.float32) - bg_color[None, None, :].astype(np.float32)
    near_bg = np.sqrt((diff ** 2).sum(axis=-1)) <= BG_TOL
    h, w = near_bg.shape
    seeds = np.zeros_like(near_bg, dtype=bool)
    for y in (0, h - 1):
        for x in (0, w - 1):
            if near_bg[y, x]:
                seeds[y, x] = True
    if not seeds.any():
        # Render filled the canvas? Treat everything as foreground.
        return np.ones_like(near_bg, dtype=bool)
    bg_mask = morphology.reconstruction(
        seeds.astype(np.uint8),
        near_bg.astype(np.uint8),
        method="dilation",
    ).astype(bool)
    fg = ~bg_mask
    if fg.sum() < 64:
        return fg  # Empty render
    fg = morphology.remove_small_objects(fg, min_size=64)
    fg = morphology.remove_small_holes(fg, area_threshold=256)
    return fg


def crop_to_square(rgb: np.ndarray, fg: np.ndarray) -> np.ndarray | None:
    """Crop to fg bbox, blacken background, pad to square, resize to
    COMPARE_SIZE^2. Returns RGB uint8 or None if fg is empty."""
    if not fg.any():
        return None
    ys, xs = np.where(fg)
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    crop = rgb[y0:y1 + 1, x0:x1 + 1].copy()
    crop_mask = fg[y0:y1 + 1, x0:x1 + 1]
    crop[~crop_mask] = 0
    h, w = crop.shape[:2]
    side = max(h, w)
    canvas = np.zeros((side, side, 3), dtype=np.uint8)
    oy = (side - h) // 2
    ox = (side - w) // 2
    canvas[oy:oy + h, ox:ox + w] = crop
    return np.array(
        Image.fromarray(canvas, mode="RGB").resize(
            (COMPARE_SIZE, COMPARE_SIZE), Image.LANCZOS
        )
    )


# ---------- edge map -------------------------------------------------------

def edges_of(rgb_square: np.ndarray) -> np.ndarray:
    gray = (0.299 * rgb_square[..., 0] + 0.587 * rgb_square[..., 1]
            + 0.114 * rgb_square[..., 2]).astype(np.float32) / 255.0
    return feature.canny(gray, sigma=1.5)


def reference_edges_square(ref_path: Path) -> np.ndarray:
    """Load a reference edge map and pad-resize it to the same square frame
    candidates are projected into. The reference is already an edge image
    (uint8, 0/255), so we just threshold + pad + resize."""
    img = np.array(Image.open(ref_path).convert("L"))
    edges = img > 128
    if not edges.any():
        raise RuntimeError(f"reference {ref_path} has no edges")
    ys, xs = np.where(edges)
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    crop = edges[y0:y1 + 1, x0:x1 + 1]
    h, w = crop.shape
    side = max(h, w)
    canvas = np.zeros((side, side), dtype=bool)
    oy = (side - h) // 2
    ox = (side - w) // 2
    canvas[oy:oy + h, ox:ox + w] = crop
    # Resize via PIL (bool -> uint8 -> back).
    pil = Image.fromarray((canvas.astype(np.uint8) * 255), mode="L").resize(
        (COMPARE_SIZE, COMPARE_SIZE), Image.NEAREST
    )
    return np.array(pil) > 128


# ---------- metrics --------------------------------------------------------

def dilate(edges: np.ndarray, r: int) -> np.ndarray:
    if r <= 0:
        return edges
    return morphology.binary_dilation(edges, footprint=morphology.disk(r))


def edge_iou(a: np.ndarray, b: np.ndarray, r: int = DILATE_R) -> float:
    """Symmetric IoU of dilated edge maps."""
    da = dilate(a, r)
    db = dilate(b, r)
    inter = (da & db).sum()
    union = (da | db).sum()
    if union == 0:
        return 0.0
    return float(inter) / float(union)


def chamfer_score(a: np.ndarray, b: np.ndarray) -> float:
    """Symmetric chamfer distance, mapped to (0, 1]: 1 = identical edges,
    smaller = farther. Normalize by image diagonal so values are comparable
    across runs."""
    if not a.any() or not b.any():
        return 0.0
    # Distance from each pixel to nearest "edge" of the other image.
    dist_to_b = distance_transform_edt(~b)
    dist_to_a = distance_transform_edt(~a)
    d_ab = dist_to_b[a].mean()
    d_ba = dist_to_a[b].mean()
    d = 0.5 * (d_ab + d_ba)
    diag = float(np.sqrt(2) * COMPARE_SIZE)
    return 1.0 / (1.0 + d / (diag * 0.05))  # ~half score at 5% of diagonal


# ---------- driver ---------------------------------------------------------

def candidate_views(sha_prefix: str) -> list[tuple[str, Path]]:
    out = []
    base = RENDERS_DIR / sha_prefix
    for v in VIEWS:
        p = base / f"{v}.png"
        if p.exists():
            out.append((v, p))
    return out


def score_render(path: Path, ref_edges: np.ndarray) -> tuple[float, float] | None:
    rgb = np.array(Image.open(path).convert("RGB"))
    bg_color = rgb[0, 0]
    fg = foreground_mask(rgb, bg_color)
    sq = crop_to_square(rgb, fg)
    if sq is None:
        return None
    cand_edges = edges_of(sq)
    return edge_iou(cand_edges, ref_edges), chamfer_score(cand_edges, ref_edges)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clip-csv", type=Path,
                    default=OUTPUT_DIR / "clip_similarity_ranking.csv",
                    help="CLIP ranking CSV to read candidate order from")
    ap.add_argument("--reference", type=Path,
                    default=ROOT / "references" / "ojisan" / "ojisan_head_edges.png",
                    help="reference edge map (must be a Canny-style binary PNG)")
    ap.add_argument("--top", type=int, default=200,
                    help="score the first N rows of CLIP CSV (0 = all)")
    ap.add_argument("--output", type=Path,
                    default=OUTPUT_DIR / "shape_similarity_ranking.csv")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    log.info("Loading reference: %s", args.reference)
    ref_edges = reference_edges_square(args.reference)
    log.info("ref edges: %d pixels (%.2f%%)", ref_edges.sum(),
             100 * ref_edges.mean())

    rows_in = []
    with args.clip_csv.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows_in.append(r)
    if args.top > 0:
        rows_in = rows_in[: args.top]
    log.info("Scoring %d candidate(s) from %s", len(rows_in), args.clip_csv)

    scored: list[dict] = []
    for i, r in enumerate(rows_in, 1):
        sha = r["sha_prefix"]
        views = candidate_views(sha)
        if not views:
            continue
        best_iou = 0.0
        best_chamfer = 0.0
        best_view = ""
        for vname, vpath in views:
            res = score_render(vpath, ref_edges)
            if res is None:
                continue
            iou, ch = res
            score = 0.5 * iou + 0.5 * ch
            if score > 0.5 * best_iou + 0.5 * best_chamfer:
                best_iou, best_chamfer, best_view = iou, ch, vname
        scored.append({
            "sha_prefix": sha,
            "name": r.get("name", ""),
            "clip_rank": r.get("rank", ""),
            "clip_score": r.get("best_similarity", ""),
            "shape_score": f"{0.5 * best_iou + 0.5 * best_chamfer:.4f}",
            "iou": f"{best_iou:.4f}",
            "chamfer": f"{best_chamfer:.4f}",
            "best_view": best_view,
            "source_path": r.get("source_path", ""),
        })
        if i % 25 == 0:
            log.info("  scored %d/%d", i, len(rows_in))

    scored.sort(key=lambda d: float(d["shape_score"]), reverse=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as fh:
        cols = ["rank", "sha_prefix", "name", "shape_score", "iou", "chamfer",
                "best_view", "clip_rank", "clip_score", "source_path"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for i, d in enumerate(scored, 1):
            d["rank"] = i
            w.writerow({k: d.get(k, "") for k in cols})

    log.info("Wrote %s", args.output)
    log.info("Top 30 by shape_score (vs %s):", args.reference.name)
    for i, d in enumerate(scored[:30], 1):
        log.info("  #%-3d  shape=%s  iou=%s  ch=%s  view=%-13s  clip#%s s=%s  %s",
                 i, d["shape_score"], d["iou"], d["chamfer"],
                 d["best_view"], d["clip_rank"], d["clip_score"], d["name"])


if __name__ == "__main__":
    main()
