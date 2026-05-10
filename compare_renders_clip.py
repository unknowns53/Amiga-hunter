"""Rank rendered candidates by CLIP cosine similarity to a reference image.

Why: perceptual hashes (compare_renders.py) only capture overall image
structure. CLIP image embeddings capture *semantic* content — "a head with
an open mouth", "a vehicle", "a ball" — which is what we actually want to
match against IMG_2211.png.

Usage:
    python compare_renders_clip.py --reference references/IMG_2211.png
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


def load_clip(model_name: str, pretrained: str, device: str):
    import open_clip
    import torch
    log.info("Loading CLIP %s (%s) on %s ...", model_name, pretrained, device)
    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    model.eval().to(device)
    return model, preprocess, torch


def encode_image(path: Path, model, preprocess, torch, device):
    img = Image.open(path).convert("RGB")
    tensor = preprocess(img).unsqueeze(0).to(device)
    with torch.no_grad():
        feat = model.encode_image(tensor)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat.cpu().numpy()[0]


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
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
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

    model, preprocess, torch = load_clip(args.model, args.pretrained, args.device)

    log.info("Encoding reference: %s", args.reference)
    ref_vec = encode_image(args.reference, model, preprocess, torch, args.device)

    with args.candidates_csv.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    log.info("Comparing %d candidate(s) ...", len(rows))
    results: list[dict] = []
    encoded = 0
    for row in rows:
        render_dir = find_render_dir(row.get("sha256") or "")
        if render_dir is None:
            continue
        per_view: dict[str, float] = {}
        for view in args.views:
            img_path = render_dir / f"{view}.png"
            if not img_path.exists():
                continue
            try:
                vec = encode_image(img_path, model, preprocess, torch, args.device)
            except Exception as e:
                log.warning("encode failed for %s: %s", img_path, e)
                continue
            sim = float((ref_vec * vec).sum())  # cosine similarity (already L2-normalized)
            per_view[view] = sim
            encoded += 1
        if not per_view:
            continue
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
