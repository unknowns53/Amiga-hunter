"""Scan every file under extracted/ and write scan_results.csv."""
from __future__ import annotations

import csv
import hashlib
import logging
import re
from pathlib import Path

from .config import (
    EXTRACTED_DIR, OUTPUT_DIR,
    HEAD_BYTES, SCAN_BYTES, MIN_STRING_LEN, SHA256_MAX_SIZE,
    INTERESTING_TOKENS,
)

log = logging.getLogger(__name__)

# Printable ASCII run, like Unix `strings`.
STRING_RE = re.compile(rb"[\x20-\x7e]{%d,}" % MIN_STRING_LEN)


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_lwo_markers(blob: bytes) -> dict:
    """LightWave Object IFF: 'FORM' at offset 0, 'LWOB'/'LWO2' at offset 8.
    We also do a loose 'contains' check for embedded models."""
    has_form_at0 = blob[:4] == b"FORM"
    has_lwob_at8 = len(blob) >= 12 and blob[8:12] == b"LWOB"
    has_lwo2_at8 = len(blob) >= 12 and blob[8:12] == b"LWO2"
    return {
        "has_form": (b"FORM" in blob),
        "has_lwob": (b"LWOB" in blob),
        "has_lwo2": (b"LWO2" in blob),
        "lwo_signature": (
            "LWOB" if (has_form_at0 and has_lwob_at8) else
            "LWO2" if (has_form_at0 and has_lwo2_at8) else
            ""
        ),
    }


def scan_file(path: Path) -> dict:
    try:
        size = path.stat().st_size
    except OSError as e:
        log.error("stat failed for %s: %s", path, e)
        return {}

    try:
        with path.open("rb") as f:
            blob = f.read(SCAN_BYTES)
    except Exception as e:
        log.error("Read failed for %s: %s", path, e)
        return {}

    head = blob[:HEAD_BYTES]

    # Pull printable strings, then surface only the ones containing a
    # token we care about.
    interesting = set()
    for s in STRING_RE.findall(blob):
        try:
            decoded = s.decode("ascii", errors="replace")
        except Exception:
            continue
        low = decoded.lower()
        for tok in INTERESTING_TOKENS:
            if tok in low:
                # Truncate ridiculously long matches so the CSV stays sane.
                interesting.add(decoded[:120])
                break
    interesting_str = " | ".join(sorted(interesting)[:25])

    markers = detect_lwo_markers(blob)

    sha256 = sha256_of_file(path) if size <= SHA256_MAX_SIZE else "TOO_LARGE"

    return {
        "path": str(path),
        "name": path.name,
        "ext": path.suffix.lower(),
        "size": size,
        "sha256": sha256,
        "head_hex": head.hex(),
        "lwo_signature": markers["lwo_signature"],
        "has_form": markers["has_form"],
        "has_lwob": markers["has_lwob"],
        "has_lwo2": markers["has_lwo2"],
        "interesting_strings": interesting_str,
    }


def scan_all() -> list[dict]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not EXTRACTED_DIR.exists():
        log.warning("No extracted/ directory; nothing to scan.")
        return []

    files = [p for p in EXTRACTED_DIR.rglob("*") if p.is_file()]
    log.info("Scanning %d files...", len(files))

    rows = []
    for i, f in enumerate(files, 1):
        if i % 500 == 0:
            log.info("  scanned %d/%d", i, len(files))
        row = scan_file(f)
        if row:
            rows.append(row)

    csv_path = OUTPUT_DIR / "scan_results.csv"
    if rows:
        fieldnames = list(rows[0].keys())
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        log.info("Wrote %s (%d rows)", csv_path, len(rows))
    else:
        log.info("No files scanned; %s not written.", csv_path)
    return rows
