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

def safe_extract_dir(archive: Path) -> Path:
    """Pick a unique extraction directory (avoid collisions across archives
    that happen to share a stem)."""
    h = hashlib.sha1(str(archive).encode("utf-8")).hexdigest()[:8]
    target = EXTRACTED_DIR / f"{archive.stem}__{h}"
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
    """Extract Amiga disk image (ADF/HDF) via amitools xdftool."""
    xdftool = find_xdftool()
    if not xdftool:
        log.warning("xdftool not found; skipping %s. Install with: pip install amitools",
                    archive.name)
        return False
    try:
        # xdftool <image> unpack <target_dir>
        result = subprocess.run(
            [xdftool, str(archive), "unpack", str(target)],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            log.error("xdftool failed for %s (rc=%d): %s",
                      archive, result.returncode, result.stderr[:500])
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("xdftool timed out for %s", archive)
        return False
    except Exception as e:
        log.error("xdftool exception for %s: %s", archive, e)
        return False


# ---------- dispatch -------------------------------------------------------

def extract_archive(archive: Path) -> bool:
    ext = archive.suffix.lower()
    target = safe_extract_dir(archive)
    log.info("Extracting %s -> %s", archive.name, target.name)

    if ext == ".zip":
        return extract_zip(archive, target)
    if ext in {".lha", ".lzh", ".lzx", ".7z", ".rar", ".tar", ".gz", ".tgz"}:
        return extract_with_7zip(archive, target)
    if ext in {".adf", ".hdf"}:
        return extract_adf_hdf(archive, target)
    # Unknown -> let 7-Zip try.
    log.info("Unknown archive type %s; falling back to 7-Zip.", ext)
    return extract_with_7zip(archive, target)


def extract_all() -> dict:
    """Walk ARCHIVES_DIR, extract every file, return summary."""
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    if not ARCHIVES_DIR.exists():
        ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
        log.warning("Created empty archives dir: %s (drop archives in here).",
                    ARCHIVES_DIR)
        return {"total": 0, "succeeded": 0, "failed": 0}

    archives = [
        p for p in ARCHIVES_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in ARCHIVE_EXTENSIONS
    ]
    succeeded, failed = 0, 0
    for arc in archives:
        if extract_archive(arc):
            succeeded += 1
        else:
            failed += 1
    return {"total": len(archives), "succeeded": succeeded, "failed": failed}
