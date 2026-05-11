"""Rank arbitrary 2D image files (BMP / JPG / PNG / TIFF / PCD-converted) by
CLIP cosine similarity to a reference image.

Why a separate entry point: compare_renders_clip.py is wired to
output/candidate_models.csv + renders/<sha16>/{front,threequarter,side}.png
because the rest of the pipeline is about 3D models that we rendered ourselves.
B3 brought in pure 2D image libraries (KHN 3DCG Vol.5/11, KHN Photo Vol.1) —
those don't have a sha16 render directory, they're just bitmaps. This helper
encodes every image under a directory tree directly and reports the top-K.

Usage:
    python clip_2d_image_match.py \
        --reference references/ojisan/ojisan.png \
        --image-root extracted/_b3_khn_3dgraphic_5 \
        --output output/clip_b3_khn5.csv --top 30
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

from PIL import Image

log = logging.getLogger("clip_2d_image_match")

IMG_EXTS = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".pcx", ".tga"}


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def load_clip(model_name: str, pretrained: str, device: str):
    import open_clip
    import torch
    log.info("Loading CLIP %s (%s) on %s ...", model_name, pretrained, device)
    if device == "cuda":
        log.info("  CUDA: %s, %.1f GB free",
                 torch.cuda.get_device_name(0),
                 torch.cuda.mem_get_info(0)[0] / 1e9)
    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    model.eval().to(device)
    return model, preprocess, torch


def encode_single(path: Path, model, preprocess, torch, device):
    img = Image.open(path).convert("RGB")
    t = preprocess(img).unsqueeze(0).to(device)
    with torch.no_grad():
        f = model.encode_image(t)
        f = f / f.norm(dim=-1, keepdim=True)
    return f.cpu().numpy()[0]


class _Dataset:
    def __init__(self, paths, preprocess):
        self.paths = paths
        self.preprocess = preprocess

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        from PIL import UnidentifiedImageError
        p = self.paths[idx]
        try:
            img = Image.open(p).convert("RGB")
            return idx, self.preprocess(img)
        except (OSError, UnidentifiedImageError, ValueError):
            return idx, None


def _collate(batch):
    import torch
    ok = [(i, t) for i, t in batch if t is not None]
    bad = [i for i, t in batch if t is None]
    if not ok:
        return [], bad, None
    return [i for i, _ in ok], bad, torch.stack([t for _, t in ok])


def encode_batch(paths, model, preprocess, torch, device, bs: int, nw: int):
    from torch.utils.data import DataLoader
    ds = _Dataset(paths, preprocess)
    loader = DataLoader(ds, batch_size=bs, num_workers=nw,
                        collate_fn=_collate, pin_memory=(device == "cuda"))
    feats = [None] * len(paths)
    with torch.no_grad():
        for idxs, bad, batch in loader:
            if batch is not None:
                batch = batch.to(device, non_blocking=(device == "cuda"))
                f = model.encode_image(batch)
                f = f / f.norm(dim=-1, keepdim=True)
                arr = f.cpu().numpy()
                for j, i in enumerate(idxs):
                    feats[i] = arr[j]
    return feats


def gather_images(root: Path) -> list[Path]:
    paths = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            paths.append(p)
    paths.sort()
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reference", required=True, type=Path)
    ap.add_argument("--image-root", required=True, type=Path,
                    help="Directory tree to scan for images")
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--model", default="ViT-B-32")
    ap.add_argument("--pretrained", default="laion2b_s34b_b79k")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--num-workers", type=int, default=0)
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    if not args.reference.exists():
        log.error("Reference image not found: %s", args.reference)
        sys.exit(1)
    if not args.image_root.exists():
        log.error("image-root does not exist: %s", args.image_root)
        sys.exit(1)

    device = resolve_device(args.device)
    model, preprocess, torch = load_clip(args.model, args.pretrained, device)

    log.info("Encoding reference: %s", args.reference)
    ref = encode_single(args.reference, model, preprocess, torch, device)

    paths = gather_images(args.image_root)
    log.info("Found %d image(s) under %s", len(paths), args.image_root)
    if not paths:
        log.warning("No images to encode.")
        return

    feats = encode_batch(paths, model, preprocess, torch, device,
                         args.batch_size, args.num_workers)
    results = []
    encoded = 0
    for p, v in zip(paths, feats):
        if v is None:
            continue
        sim = float((ref * v).sum())
        results.append({
            "similarity": round(sim, 4),
            "path": str(p),
        })
        encoded += 1
    log.info("Encoded %d / %d image(s)", encoded, len(paths))

    results.sort(key=lambda r: -r["similarity"])
    for rank, r in enumerate(results, 1):
        r["rank"] = rank

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["rank", "similarity", "path"]
    with args.output.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)
    log.info("Wrote %s (%d rows)", args.output, len(results))

    n = min(args.top, len(results))
    log.info("Top %d (higher cosine similarity = closer):", n)
    for r in results[:n]:
        log.info("  #%-3d  s=%.4f  %s", r["rank"], r["similarity"], r["path"])


if __name__ == "__main__":
    main()
