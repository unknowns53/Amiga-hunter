"""Top-level pipeline orchestrator.

Usage:
    python run_pipeline.py
"""
from __future__ import annotations

import logging
import sys

from pipeline.config import LOGS_DIR, OUTPUT_DIR
from pipeline.convert import convert_all
from pipeline.extract import extract_all
from pipeline.identify import identify
from pipeline.scan import scan_all


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "pipeline.log"
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> None:
    setup_logging()
    log = logging.getLogger("pipeline")

    log.info("=== Step 1: Extract archives ===")
    summary = extract_all()
    log.info("Extracted: %s", summary)

    log.info("=== Step 2: Convert Amiga-native models to OBJ ===")
    conv_summary = convert_all()
    log.info("Converted: %s", conv_summary)

    log.info("=== Step 3: Scan extracted files ===")
    rows = scan_all()
    log.info("Scanned: %d files", len(rows))

    log.info("=== Step 4: Identify candidates ===")
    candidates = identify(rows)
    log.info("Candidates: %d", len(candidates))

    log.info("Pipeline finished.")
    log.info("  scan results : %s", OUTPUT_DIR / "scan_results.csv")
    log.info("  candidates   : %s", OUTPUT_DIR / "candidate_models.csv")
    log.info("Next: render thumbnails with Blender:")
    log.info('  blender --background --python blender_render.py')


if __name__ == "__main__":
    main()
