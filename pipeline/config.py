"""Constants and shared paths."""
from __future__ import annotations
from pathlib import Path

# Project root = parent of this package's parent
ROOT = Path(__file__).resolve().parent.parent

ARCHIVES_DIR  = ROOT / "archives_raw"
EXTRACTED_DIR = ROOT / "extracted"
RENDERS_DIR   = ROOT / "renders"
OUTPUT_DIR    = ROOT / "output"
LOGS_DIR      = ROOT / "logs"

# Archive types we attempt to extract
ARCHIVE_EXTENSIONS = {
    ".zip", ".lha", ".lzh", ".lzx",
    ".adf", ".hdf", ".iso",
    ".7z", ".rar", ".tar", ".gz", ".tgz",
}

# Curated Internet Archive item identifiers worth pulling from for Amiga /
# LightWave / Imagine 3D content. Used as defaults by collect_internet_archive.py
# when no --identifier is given. Order roughly reflects search priority.
INTERNET_ARCHIVE_IDENTIFIERS = [
    # Tier 1: LightWave-native object collections (most likely to yield .lwo).
    "CommodoreAmigaApplicationsADF",
    "commodore-amiga-applications-public-domain-adf",
    "video-toaster-v4.0-intstallation-disk",
    # Tier 2: CD-ROM compendiums (massive, ISO format).
    "lightrom1",
]

# Extensions worth flagging as candidate 3D models
CANDIDATE_EXTENSIONS = {".lwo", ".lwob", ".obj", ".geo", ".3ds", ".iff", ".lws"}

# Filename keywords (lowercased substring match)
KEYWORDS = ["head", "face", "man", "male", "human", "person", "bust", "demo", "tutor"]

# IFF / LightWave magic markers we look for inside binaries
LWO_MARKERS = [b"FORM", b"LWOB", b"LWO2"]

# Number of bytes captured for the "head_hex" preview column
HEAD_BYTES = 32

# Maximum bytes scanned per file for marker / string search.
# Most LWO/3DS files are small, so 1 MB is usually enough.
SCAN_BYTES = 1 * 1024 * 1024

# Minimum length for printable-string extraction (Unix `strings` style)
MIN_STRING_LEN = 4

# SHA256 is skipped on files larger than this many bytes (just to keep things snappy)
SHA256_MAX_SIZE = 200 * 1024 * 1024  # 200 MB

# Substrings that, if found in extracted strings, are worth surfacing in the CSV
INTERESTING_TOKENS = [
    "lightwave", "lwob", "lwo2", "newtek", "amiga", "video toaster",
    "head", "face", "man", "male", "human", "person", "bust", "tutor",
    "imagine", "sculpt", "real3d", "videoscape", "aladdin", "inspire",
    "akimoto", "akimotokitsune", "kitsune",
]
