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
    # Tier 3: PC-era NewTek LightWave Content / Companion CDs (2026-05-10 added).
    # Smaller ISOs/RARs that ship with bundled .lwo / .lws sample objects from
    # LightWave 5.x through 9. Ordered roughly by ascending size so cheap items
    # finish first and feed the pipeline early.
    # NOTE: For ojisan (アンシャントロマン 1998), only the v5.x-era discs
    # (bonus 1997, contentcd 1995, applied 5.6, inlw 5.5, LWPowerGuide) and
    # 1997 newtekniques are timeline-plausible. v6+ items (Inside_Lightwave_6,
    # LW8/9 ST, lightwave-v9-texturing-cd, lw70ff) are kept for CLIP-false-
    # positive checks but predate the cutoff and are not real candidates.
    "newtek_bonuscontentforlightwave3d",     # ~25 MB ISO, LightWave 5.x bonus
    "LWPowerGuide",                          # ~61 MB RAR, LightWave Power Guide CD
    "newtek_lightwave3dcontentcd",           # ~91 MB ISO, LightWave 3D Content CD (1995)
    "Inside_Lightwave_6",                    # ~215 MB, Inside LightWave 6 companion
    "LightWave3D8ST",                        # ~251 MB RAR, JP "Super Technique" v8 CD
    "lightwave_3d_applied_5.6_cd",           # ~344 MB, Lightwave 3D Applied 5.6
    "inlw-3d-55",                            # ~446 MB, Inside LightWave 3D 5.5
    "lightwave-v9-texturing-cd",             # ~488 MB, LightWave v9 Texturing companion
    "LightWave3D9ST",                        # ~492 MB, JP "Super Technique" v8.5/9/9.2 CD
    "newtekniquessubscribercontentcd",       # ~493 MB, NewTekniques magazine subscriber CD
    "lw70ff",                                # ~709 MB, LightWave 3D 7.0 Full Final
    # Tier 4: Other PC-era 3D tools, timeline-fitting for 1998 cutoff
    # (2026-05-10 added). Imagine PC, trueSpace, 3DS MAX, 3D Artist mag.
    "imagine-3D-for-DOS",                    # ~4 MB, Imagine 2.0/3.0/4.0 DOS (1995)
    "Caligari_trueSpace-3",                  # ~15 MB, trueSpace 3 (1997)
    "3-d-studio-viz-demo",                   # ~59 MB, 3D Studio VIZ Demo (1996)
    "3dsmax2.5",                             # ~219 MB, 3DS MAX 2.5 (1998, borderline)
    "caligari-truespace2-bible",             # ~643 MB, trueSpace 2 Bible Companion (1996)
    "3d-artist-volume-1",                    # ~2.9 GB, 3D Artist Vol 1 (20 issues, dates unknown)
    # Tier 5: B1 DiscMaster sweep — LightWave compendium / book / magazine CDs
    # released 1997-or-earlier (2026-05-11 added).
    # CRITICAL CUTOFF UPDATE (2026-05-11): user reported that the 1997 game
    # demo of アンシャントロマン already contains the おじさん model, so the
    # source media must have been released BY 1997-12-31 at the latest. This
    # rules out Oh!X 1998 Spring / 1999 Spring (1998-04, 1999), LIGHT-ROM 6
    # (1998-03), LIGHT-ROM 8 (1999), Light ROM Gold (1998 compilation), and
    # Best-of LIGHT-ROM 1-5 (2000 compilation). Light ROM Gold and Best-of
    # are also redundant once we have LIGHT-ROM 1/3/4/5 directly.
    # LIGHT-ROM core series gap-fill (we have lightrom1 already; 3-5 are the
    # remaining timeline-plausible volumes). LIGHT-ROM 5 is best-aligned
    # (1997 release with 1997-dated assets — synchronous with the demo).
    "light-rom-3",                           # ~1.9 GB, LIGHT-ROM 3 (1995, 3 discs)
    "light-rom-4",                           # LIGHT-ROM 4 (1996)
    "lightrom5",                             # LIGHT-ROM 5 (1997, 3 discs) — best timing
    # LightWave magazine and book CDs (1996-1997).
    "lightwavinmagazine_issue02",            # ~266 MB, LightWavin' Magazine Issue 2 (1997-01)
    "LWPRO-Book-CD",                         # The Lightwave 3D Book Tips/Techniques/Objects (1997)
    "US3DEXTREME1",                          # ~599 MB, Ultimate Software Extreme 3D (1996)
    # Tier 6: B2 phase — PS1 official developer tools shipped by SCE / D-Storm
    # in Japan (2026-05-11 added). アンシャントロマン was made by absolute
    # beginners ("日本システム" was set up specifically for this title, all
    # staff were first-time game devs per 楓牙's testimony), so the chance
    # they pulled sample models straight out of Sony's official PS1 Graphic
    # Artist Tools or NewTek's PlayStation LightWave bundle is unusually high.
    # All four are well within the 1997-12-31 cutoff (LightWave 4.0 Rev. C
    # Japan is 1995-1996, Graphic Artist Tools 1.8 predates v2.0 / 1998-11
    # v2.2E, Net Yaroze launched 1996-06 in Japan, Artist Tool 2D&3D DTL-S250
    # is mid-1997 bridge between DTL-S210/S220 1.x and 2.x).
    "LightwaveForPlayStation",               # ~58 MB, LW 3D 4.0 Intell Rev. C Japan (SCE bundle)
    "redump-id-69352",                       # ~23 MB BIN/CUE, Graphic Artist Tools 1.8 Japan DTL-S220
    "NetYarozeSoftwareDevelopmentDiscs",     # ~67+3.6 MB, DTL-S3040 Japan + DTL-S3045 EU/USA
    # NOTE: PlayStation Artist Tool 2D&3D (Japan) DTL-S250 (~15 MB) has no
    # standalone IA identifier; it lives inside ps1_sdks. Handled via a
    # separate curl-and-place step into archives_raw/ia/ps1_artist_tool_dtls250/
    # so the pipeline picks it up without dragging the full 8.3 GB SDK set.
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
