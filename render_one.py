"""Render one specific model by sha256, bypassing the candidate-list loop.

Usage (inside Blender):
    blender --background --python render_one.py -- <sha256>

Looks up the path in output/candidate_models.csv, calls render_model from
blender_render.py. Used to confirm a single high-priority candidate (e.g.
ROMAN.LWO.obj) before committing to a full bulk render.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# Blender's --python argv doesn't add the script's dir to sys.path, so do it here.
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import blender_render as br  # noqa: E402
CANDIDATES_CSV = SCRIPT_DIR / "output" / "candidate_models.csv"
RENDERS_DIR = SCRIPT_DIR / "renders"


def main() -> int:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    if len(argv) != 1:
        print("Usage: blender --background --python render_one.py -- <sha256>")
        return 2
    target_sha = argv[0].strip().lower()

    target_path: Path | None = None
    target_full_sha: str | None = None
    with CANDIDATES_CSV.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            sha = row.get("sha256", "").lower()
            if sha.startswith(target_sha):
                target_path = Path(row["path"])
                target_full_sha = sha
                break
    if target_path is None or target_full_sha is None:
        print(f"sha {target_sha!r} not found in {CANDIDATES_CSV}")
        return 3

    out_dir = RENDERS_DIR / target_full_sha[:16]
    print(f"Rendering: {target_path}")
    print(f"sha256:    {target_full_sha}")
    print(f"out_dir:   {out_dir}")

    br.setup_blender_addons()
    ok = br.render_model(target_path, target_full_sha, out_dir)
    print(f"render_model returned: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
