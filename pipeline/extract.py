"""Archive extraction for zip / lha / lzx / adf / hdf and friends.

Strategy:
- ZIP: stdlib zipfile.
- LHA / LZX / 7Z / RAR: 7-Zip subprocess.
- ADF / HDF (Amiga disk images): amitools `xdftool` subprocess.

Anything else: try 7-Zip as a last resort, log on failure.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional

from .config import ARCHIVE_EXTENSIONS, ARCHIVES_DIR, EXTRACTED_DIR

log = logging.getLogger(__name__)


# ---------- tool discovery -------------------------------------------------

def find_7zip() -> Optional[str]:
    """Locate 7z.exe (Windows) or 7z (Unix). Returns None if not found."""
    cand = shutil.which("7z") or shutil.which("7z.exe")
    if cand:
        return cand
    candidates = [
        os.environ.get("SEVENZIP_PATH"),
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        "/usr/bin/7z",
        "/usr/local/bin/7z",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def find_xdftool() -> Optional[str]:
    """`xdftool` ships with the amitools pip package."""
    return shutil.which("xdftool") or shutil.which("xdftool.exe")


# ---------- helpers --------------------------------------------------------

def compute_extract_dir(archive: Path) -> Path:
    """Compute the canonical extraction directory for an archive without
    creating it. Splitting create from compute lets callers do an
    idempotency check (skip extract if dir already populated)."""
    h = hashlib.sha1(str(archive).encode("utf-8")).hexdigest()[:8]
    return EXTRACTED_DIR / f"{archive.stem}__{h}"


def safe_extract_dir(archive: Path) -> Path:
    """Compute the extraction dir AND ensure it exists. Kept for callers
    that want both."""
    target = compute_extract_dir(archive)
    target.mkdir(parents=True, exist_ok=True)
    return target


# ---------- per-format extractors ------------------------------------------

def extract_zip(archive: Path, target: Path) -> bool:
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(target)
        return True
    except Exception as e:
        log.error("ZIP extract failed for %s: %s", archive, e)
        return False


def extract_with_7zip(archive: Path, target: Path) -> bool:
    sevenzip = find_7zip()
    if not sevenzip:
        log.warning("7-Zip not found; skipping %s. "
                    "Install from https://www.7-zip.org/ or set SEVENZIP_PATH.",
                    archive.name)
        return False
    try:
        result = subprocess.run(
            [sevenzip, "x", "-y", f"-o{target}", str(archive)],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            log.error("7z failed for %s (rc=%d): %s",
                      archive, result.returncode, result.stderr[:500])
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("7z timed out for %s", archive)
        return False
    except Exception as e:
        log.error("7z exception for %s: %s", archive, e)
        return False


def extract_adf_hdf(archive: Path, target: Path) -> bool:
    """Extract Amiga disk image (ADF/HDF) via amitools xdftool.

    Two Windows-specific footguns we work around:

    1) Some Amiga ADFs hold non-ASCII filenames (e.g. German "ß" on the
       'LightWave Objects' disks). On Japanese Windows xdftool prints
       and saves a metadata JSON in the locale codec (cp932), which
       cannot encode those characters and crashes with UnicodeEncodeError.
       Forcing PYTHONUTF8=1 / PYTHONIOENCODING=utf-8 makes Python use
       UTF-8 throughout instead of the locale codec.

    2) Even with PYTHONUTF8=1, xdftool can hit a write that bypasses
       Python's UTF-8 mode and abort *after* extracting the actual
       files. We detect this by checking whether the target dir has
       any files: if extraction succeeded but metadata save failed,
       the LWO/etc payload is fine and we treat it as a partial success.
    """
    xdftool = find_xdftool()
    if not xdftool:
        log.warning("xdftool not found; skipping %s. Install with: pip install amitools",
                    archive.name)
        return False
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(
            [xdftool, str(archive), "unpack", str(target)],
            capture_output=True, text=True, timeout=600, env=env,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            return True
        # Salvage path: count actual extracted files. xdftool's metadata
        # save can crash while leaving the real payload on disk.
        extracted = sum(1 for p in target.rglob("*") if p.is_file())
        if extracted > 0:
            log.info("xdftool partial success for %s: %d files on disk despite "
                     "rc=%d (likely metadata-save crash)",
                     archive.name, extracted, result.returncode)
            return True
        log.error("xdftool failed for %s (rc=%d): %s",
                  archive, result.returncode, (result.stderr or "")[:500])
        return False
    except subprocess.TimeoutExpired:
        log.error("xdftool timed out for %s", archive)
        return False
    except Exception as e:
        log.error("xdftool exception for %s: %s", archive, e)
        return False


# ---------- dispatch -------------------------------------------------------

def extract_archive(archive: Path) -> bool:
    ext = archive.suffix.lower()
    target = compute_extract_dir(archive)

    # Idempotency: if the target directory already exists and contains files,
    # treat the archive as already extracted. This makes re-runs cheap and
    # is essential for the multi-pass loop in extract_all() — without it,
    # every pass would re-unpack everything we already have.
    if target.exists() and any(target.iterdir()):
        log.debug("Already extracted: %s -> %s", archive.name, target.name)
        return True

    target.mkdir(parents=True, exist_ok=True)
    log.info("Extracting %s -> %s", archive.name, target.name)

    if ext == ".zip":
        return extract_zip(archive, target)
    if ext in {".lha", ".lzh", ".lzx", ".7z", ".rar", ".tar", ".gz", ".tgz", ".iso"}:
        return extract_with_7zip(archive, target)
    if ext in {".adf", ".hdf"}:
        return extract_adf_hdf(archive, target)
    # Unknown -> let 7-Zip try.
    log.info("Unknown archive type %s; falling back to 7-Zip.", ext)
    return extract_with_7zip(archive, target)


def _find_archives_under(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in ARCHIVE_EXTENSIONS
    ]


def extract_all(max_passes: int = 5) -> dict:
    """Walk ARCHIVES_DIR (and EXTRACTED_DIR for nested archives), extract
    every file, return summary.

    Why iterative: Internet Archive items often deliver Amiga software as
    .zip wrappers around .adf disk images. The .adf only becomes visible
    after the .zip has been unpacked, so a single pass leaves disk-image
    contents unreached. We loop until a pass discovers no new archives,
    capped at max_passes for safety.
    """
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    if not ARCHIVES_DIR.exists():
        ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
        log.warning("Created empty archives dir: %s (drop archives in here).",
                    ARCHIVES_DIR)
        return {"total": 0, "succeeded": 0, "failed": 0, "passes": 0}

    seen: set[Path] = set()
    total = succeeded = failed = 0
    pass_no = 0

    for pass_no in range(1, max_passes + 1):
        # Look in both archives_raw (the original drop) and extracted/
        # (nested archives revealed by previous passes).
        new_archives = [
            p for p in _find_archives_under(ARCHIVES_DIR) + _find_archives_under(EXTRACTED_DIR)
            if p not in seen
        ]
        if not new_archives:
            break
        log.info("Extract pass %d: %d new archive(s)", pass_no, len(new_archives))
        for arc in new_archives:
            seen.add(arc)
            total += 1
            if extract_archive(arc):
                succeeded += 1
            else:
                failed += 1

    return {"total": total, "succeeded": succeeded, "failed": failed, "passes": pass_no}
