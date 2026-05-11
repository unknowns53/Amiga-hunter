"""Rank rendered candidates by CLIP cosine similarity to a reference image.

Why: perceptual hashes (compare_renders.py) only capture overall image
structure. CLIP image embeddings capture *semantic* content — "a head with
an open mouth", "a vehicle", "a ball" — which is what we actually want to
match against ojisan.png.

Usage:
    python compare_renders_clip.py --reference references/ojisan/ojisan.png
    python compare_renders_clip.py --reference ref.png --model ViT-L-14 --top 30

Reads:
    output/candidate_models.csv
    renders/<sha16>/{front,threequarter,side}.png
Writes:
    output/clip_similarity_ranking.csv
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

from PIL import Image

from pipeline.config import OUTPUT_DIR, RENDERS_DIR

log = logging.getLogger("compare_renders_clip")


def resolve_device(requested: str) -> str:
    """Resolve "auto" to "cuda" if available, else "cpu". Honor explicit
    "cuda" / "cpu" requests (cuda will fail loudly if torch lacks CUDA — that
    surfaces the missing wheel rather than silently falling back)."""
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


def encode_image(path: Path, model, preprocess, torch, device):
    """Single-image encode. Kept for the reference image path; bulk render
    encoding goes through encode_images_batch for throughput."""
    img = Image.open(path).convert("RGB")
    tensor = preprocess(img).unsqueeze(0).to(device)
    with torch.no_grad():
        feat = model.encode_image(tensor)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat.cpu().numpy()[0]


class _RenderImageDataset:
    """Defined at module level so DataLoader with num_workers>0 can pickle it
    on Windows (spawn semantics). Imported inside encode_images_batch() via
    name lookup; torch's Dataset is duck-typed, no inheritance needed."""

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
            # None signals failure; collate keeps these in a separate bucket
            # rather than feeding bogus tensors through encode_image().
            return idx, None


def _batch_collate(batch):
    import torch
    ok = [(idx, t) for idx, t in batch if t is not None]
    bad = [idx for idx, t in batch if t is None]
    if not ok:
        return [], bad, None
    idxs = [idx for idx, _ in ok]
    stacked = torch.stack([t for _, t in ok])
    return idxs, bad, stacked


def encode_images_batch(paths, model, preprocess, torch, device,
                        batch_size: int, num_workers: int):
    """Encode a list of image paths in batches; return a list of length N
    aligned with paths, where each entry is a numpy vector or None for failed
    loads.

    Why batched + DataLoader: the CPU-bound preprocess (PIL decode, resize,
    normalize) becomes the bottleneck once we move the model to GPU; running
    it in worker processes lets a DataLoader pipeline keep the GPU fed. On
    CPU-only setups, batching still amortizes per-call model overhead."""
    from torch.utils.data import DataLoader

    dataset = _RenderImageDataset(paths, preprocess)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        num_workers=num_workers,
        collate_fn=_batch_collate,
        pin_memory=(device == "cuda"),
    )

    feats = [None] * len(paths)
    with torch.no_grad():
        for ok_idxs, bad_idxs, batch_t in loader:
            if batch_t is not None:
                batch_t = batch_t.to(device, non_blocking=(device == "cuda"))
                f = model.encode_image(batch_t)
                f = f / f.norm(dim=-1, keepdim=True)
                f_np = f.cpu().numpy()
                for j, idx in enumerate(ok_idxs):
                    feats[idx] = f_np[j]
            for idx in bad_idxs:
                feats[idx] = None  # explicit; redundant but clear
    return feats


def find_render_dir(sha256: str) -> Path | None:
    if not sha256 or sha256 == "TOO_LARGE":
        return None
    d = RENDERS_DIR / sha256[:16]
    return d if d.exists() else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reference", required=True, type=Path)
    ap.add_argument("--model", default="ViT-B-32",
                    help="open_clip model name (default: ViT-B-32)")
    ap.add_argument("--pretrained", default="laion2b_s34b_b79k",
                    help="open_clip pretrained tag (default: laion2b_s34b_b79k)")
    ap.add_argument("--views", nargs="+", default=["front", "threequarter", "side"])
    ap.add_argument("--candidates-csv", type=Path,
                    default=OUTPUT_DIR / "candidate_models.csv")
    ap.add_argument("--output", type=Path,
                    default=OUTPUT_DIR / "clip_similarity_ranking.csv")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"],
                    help="auto picks cuda if torch.cuda.is_available() else cpu")
    ap.add_argument("--batch-size", type=int, default=64,
                    help="images per CLIP forward pass (CPU: keep small; GPU: 64-256)")
    ap.add_argument("--num-workers", type=int, default=0,
                    help="DataLoader worker procs for image preprocessing (Windows: "
                         "0 is safest; 2-4 helps when GPU is fast)")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    if not args.reference.exists():
        log.error("Reference image not found: %s", args.reference)
        sys.exit(1)
    if not args.candidates_csv.exists():
        log.error("Missing %s; run run_pipeline.py first.", args.candidates_csv)
        sys.exit(1)

    device = resolve_device(args.device)
    model, preprocess, torch = load_clip(args.model, args.pretrained, device)

    log.info("Encoding reference: %s", args.reference)
    ref_vec = encode_image(args.reference, model, preprocess, torch, device)

    with args.candidates_csv.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    # Build a flat list of (row_idx, view, image_path) to encode in one pass.
    # Going row-by-row+view-by-view (the old structure) couldn't batch well
    # because per-row work is mostly disk checks. Flat list maximizes batch
    # utilization on GPU.
    log.info("Comparing %d candidate(s) ...", len(rows))
    encode_jobs: list[tuple[int, str, Path]] = []
    for ri, row in enumerate(rows):
        render_dir = find_render_dir(row.get("sha256") or "")
        if render_dir is None:
            continue
        for view in args.views:
            img_path = render_dir / f"{view}.png"
            if img_path.exists():
                encode_jobs.append((ri, view, img_path))

    log.info("Encoding %d render image(s) in batches of %d (workers=%d) ...",
             len(encode_jobs), args.batch_size, args.num_workers)
    paths = [p for _, _, p in encode_jobs]
    feats = encode_images_batch(paths, model, preprocess, torch, device,
                                args.batch_size, args.num_workers)

    # Stitch per-row similarity scores back together.
    encoded = 0
    per_row_views: dict[int, dict[str, float]] = {}
    for (ri, view, _), vec in zip(encode_jobs, feats):
        if vec is None:
            continue
        sim = float((ref_vec * vec).sum())  # cosine (both L2-normalized)
        per_row_views.setdefault(ri, {})[view] = sim
        encoded += 1

    results: list[dict] = []
    for ri, per_view in per_row_views.items():
        if not per_view:
            continue
        row = rows[ri]
        best_view, best_sim = max(per_view.items(), key=lambda kv: kv[1])
        results.append({
            "sha_prefix": (row.get("sha256") or "")[:16],
            "best_view": best_view,
            "best_similarity": round(best_sim, 4),
            **{f"s_{v}": round(per_view.get(v, float("nan")), 4) for v in args.views},
            "name": row.get("name", ""),
            "source_path": row.get("path", ""),
            "match_reasons": row.get("match_reasons", ""),
        })

    log.info("Encoded %d render image(s)", encoded)
    if not results:
        log.warning("No comparable renders found.")
        return

    # Higher similarity = better match.
    results.sort(key=lambda r: -r["best_similarity"])
    for rank, r in enumerate(results, 1):
        r["rank"] = rank

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["rank"] + [k for k in results[0].keys() if k != "rank"]
    with args.output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    log.info("Wrote %s (%d rows)", args.output, len(results))

    n = min(args.top, len(results))
    log.info("Top %d (higher cosine similarity = closer):", n)
    for r in results[:n]:
        log.info(
            "  #%-3d  s=%.4f  view=%-12s  %s",
            r["rank"], r["best_similarity"], r["best_view"], r["name"],
        )


if __name__ == "__main__":
    main()
