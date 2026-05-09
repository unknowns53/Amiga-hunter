"""Rank rendered candidates by perceptual-hash distance to a reference image.

Usage:
    python compare_renders.py --reference references/ojisan.png
    python compare_renders.py --reference ref.png --method dhash --top 30

Reads:
    output/candidate_models.csv
    renders/<sha16>/{front,threequarter,side}.png
Writes:
    output/similarity_ranking.csv
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

import imagehash
from PIL import Image

from pipeline.config import OUTPUT_DIR, RENDERS_DIR

log = logging.getLogger("compare_renders")

HASH_METHODS = {
    "phash": imagehash.phash,
    "dhash": imagehash.dhash,
    "whash": imagehash.whash,
    "average_hash": imagehash.average_hash,
}


def load_image(path: Path) -> Image.Image | None:
    try:
        return Image.open(path).convert("RGB")
    except Exception as e:
        log.warning("Failed to open %s: %s", path, e)
        return None


def find_render_dir(sha256: str) -> Path | None:
    if not sha256 or sha256 == "TOO_LARGE":
        return None
    d = RENDERS_DIR / sha256[:16]
    return d if d.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--reference", required=True, type=Path,
        help="reference image (the おじさん face) to compare against",
    )
    parser.add_argument(
        "--method", default="phash", choices=list(HASH_METHODS.keys()),
        help="perceptual hash method (default: phash)",
    )
    parser.add_argument(
        "--views", nargs="+", default=["front", "threequarter", "side"],
        help="which rendered views to compare",
    )
    parser.add_argument(
        "--candidates-csv", type=Path,
        default=OUTPUT_DIR / "candidate_models.csv",
        help="path to candidate_models.csv from run_pipeline.py",
    )
    parser.add_argument(
        "--output", type=Path,
        default=OUTPUT_DIR / "similarity_ranking.csv",
        help="output ranking CSV",
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="print top N matches to stdout (default: 20)",
    )
    args = parser.parse_args()

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

    ref_img = load_image(args.reference)
    if ref_img is None:
        sys.exit(1)
    hash_fn = HASH_METHODS[args.method]
    ref_hash = hash_fn(ref_img)
    log.info("Reference (%s) hash=%s", args.method, ref_hash)

    with args.candidates_csv.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    log.info("Comparing %d candidate(s)", len(rows))

    results: list[dict] = []
    for row in rows:
        render_dir = find_render_dir(row.get("sha256") or "")
        if render_dir is None:
            continue

        per_view: dict[str, int] = {}
        for view in args.views:
            img_path = render_dir / f"{view}.png"
            if not img_path.exists():
                continue
            img = load_image(img_path)
            if img is None:
                continue
            per_view[view] = ref_hash - hash_fn(img)

        if not per_view:
            continue
        best_view, best_distance = min(per_view.items(), key=lambda kv: kv[1])
        results.append({
            "sha_prefix": (row.get("sha256") or "")[:16],
            "best_view": best_view,
            "best_distance": best_distance,
            **{f"d_{v}": per_view.get(v, "") for v in args.views},
            "name": row.get("name", ""),
            "source_path": row.get("path", ""),
            "match_reasons": row.get("match_reasons", ""),
        })

    if not results:
        log.warning("No comparable renders found. Did you run blender_render.py?")
        return

    results.sort(key=lambda r: r["best_distance"])
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
    log.info("Top %d (lower distance = closer):", n)
    for r in results[:n]:
        log.info(
            "  #%-3d  d=%-3s  view=%-12s  %s",
            r["rank"], r["best_distance"], r["best_view"], r["name"],
        )


if __name__ == "__main__":
    main()
