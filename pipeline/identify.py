"""Filter scan rows down to LightWave-Object candidates."""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from .config import CANDIDATE_EXTENSIONS, KEYWORDS, OUTPUT_DIR

log = logging.getLogger(__name__)


def is_candidate(row: dict) -> tuple[bool, list[str]]:
    """A file is a candidate if ANY of these holds:
       - extension is in CANDIDATE_EXTENSIONS
       - filename contains a keyword (case-insensitive)
       - binary contains FORM / LWOB / LWO2"""
    reasons: list[str] = []
    name_low = row["name"].lower()
    ext = row.get("ext", "")

    if ext in CANDIDATE_EXTENSIONS:
        reasons.append(f"ext:{ext}")

    matched_kw = next((kw for kw in KEYWORDS if kw in name_low), None)
    if matched_kw:
        reasons.append(f"name:{matched_kw}")

    if row.get("lwo_signature"):
        reasons.append(f"sig:{row['lwo_signature']}")
    else:
        # Loose containment check (catches embedded models / bundled IFFs)
        if str(row.get("has_lwob")).lower() == "true" or row.get("has_lwob") is True:
            reasons.append("contains:LWOB")
        if str(row.get("has_lwo2")).lower() == "true" or row.get("has_lwo2") is True:
            reasons.append("contains:LWO2")
        # Plain FORM only counts when paired with an interesting extension,
        # otherwise every IFF audio sample would trigger.
        if (str(row.get("has_form")).lower() == "true" or row.get("has_form") is True) \
           and ext in {".iff", ".lwo", ".lwob", ""}:
            reasons.append("contains:FORM")

    return (len(reasons) > 0, reasons)


def identify(rows: list[dict]) -> list[dict]:
    candidates: list[dict] = []
    for row in rows:
        ok, reasons = is_candidate(row)
        if ok:
            new_row = dict(row)
            new_row["match_reasons"] = ", ".join(reasons)
            candidates.append(new_row)

    # Sort: stronger signals first
    def score(r: dict) -> int:
        reasons = r.get("match_reasons", "")
        s = 0
        if "sig:LWOB" in reasons: s += 10
        if "sig:LWO2" in reasons: s += 8
        if "contains:LWOB" in reasons: s += 4
        if "ext:.lwo" in reasons or "ext:.lwob" in reasons: s += 5
        if "name:" in reasons: s += 2
        return -s
    candidates.sort(key=score)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "candidate_models.csv"
    if candidates:
        fieldnames = list(candidates[0].keys())
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(candidates)
        log.info("Wrote %s (%d candidates)", csv_path, len(candidates))
    else:
        log.info("No candidates found; %s not written.", csv_path)
    return candidates
