"""Top-level pipeline orchestrator.

Usage:
    python run_pipeline.py
"""
from __future__ import annotations

import logging
import sys

from pipeline.config import LOGS_DIR, OUTPUT_DIR
from pipeline.extract import extract_all
from pipeline.scan import scan_all
from pipeline.identify import identify


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

    log.info("=== Step 2: Scan extracted files ===")
    rows = scan_all()
    log.info("Scanned: %d files", len(rows))

    log.info("=== Step 3: Identify candidates ===")
    candidates = identify(rows)
    log.info("Candidates: %d", len(candidates))

    log.info("Pipeline finished.")
    log.info("  scan results : %s", OUTPUT_DIR / "scan_results.csv")
    log.info("  candidates   : %s", OUTPUT_DIR / "candidate_models.csv")
    log.info("Next: render thumbnails with Blender:")
    log.info('  blender --background --python blender_render.py')


if __name__ == "__main__":
    main()
