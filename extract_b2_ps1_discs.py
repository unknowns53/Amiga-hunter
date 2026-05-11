"""One-shot helper to convert every PS1 raw image acquired in the B2
acquisition (LightWave PS1, Graphic Artist Tools 1.8, PlayStation
Artist Tool DTL-S250, Net Yaroze Boot/SDK Japan + USA/EU) into a normal
ISO 9660 image and then unpack the file system with 7-Zip into
extracted/ subdirectories that pipeline.scan can walk.

Run once after bin2iso.py + the Net Yaroze USA EU SDK manual extraction
are in place. Idempotent: skips work whose output already exists with a
non-empty contents directory.
"""
from __future__ import annotations
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import bin2iso

ROOT = Path(__file__).resolve().parent
ARCHIVES = ROOT / "archives_raw"
EXTRACTED = ROOT / "extracted"
SEVENZIP = Path(r"C:\Program Files\7-Zip\7z.exe")

log = logging.getLogger("extract_b2_ps1")

# (src_raw_image, output_dir_under_extracted, friendly_label)
JOBS: list[tuple[Path, Path, str]] = [
    (
        EXTRACTED / "Lightwave 3D 4.0 Intell Version Rev. C (Japan).iso__08ac4b96"
                  / "Lightwave 3D 4.0 Intell Version Rev. C (Japan).iso",
        EXTRACTED / "_ps1_lightwave_4_jp",
        "LightWave 3D 4.0 Intell Rev. C Japan",
    ),
    (
        ARCHIVES / "ia" / "redump-id-69352"
                / "PlayStation - Graphic Artist Tools - PC CD-ROM Release 1.8 (Japan).bin",
        EXTRACTED / "_ps1_graphic_artist_tools_1_8_jp",
        "Graphic Artist Tools 1.8 Japan DTL-S220",
    ),
    (
        EXTRACTED / "PlayStation Artist Tool - 2D & 3D Graphics Tool (Japan)_redump__98796286"
                  / "PlayStation Artist Tool - 2D & 3D Graphics Tool (Japan).bin",
        EXTRACTED / "_ps1_artist_tool_2d_3d_jp",
        "PlayStation Artist Tool 2D & 3D Japan DTL-S250",
    ),
    (
        EXTRACTED / "Net Yaroze Software Development Disc (Japan)_redump__cc4954cf"
                  / "Net Yarou ze Kidou Disc - Version 1.0 (Japan).bin",
        EXTRACTED / "_ps1_net_yaroze_kidou_jp",
        "Net Yaroze Kidou Disc 1.0 Japan",
    ),
    (
        EXTRACTED / "Net Yaroze USA EU SDK__manual"
                  / "Net Yaroze Software Development Disc (USA, Europe).bin",
        EXTRACTED / "_ps1_net_yaroze_sdk_usa",
        "Net Yaroze SDK USA/Europe DTL-S3045",
    ),
]

# Net Yaroze Japan SDK (real one, 5.71 MB zip) hasn't been extracted yet because
# pipeline.extract dedup'd against the boot disc. Do that here too so that the
# Japan SDK gets its own scratch directory.
NET_YAROZE_JP_SDK_ZIP = (
    ARCHIVES / "ia" / "net_yaroze_sdk_jp_usa"
            / "Net Yaroze Software Development Disc (Japan)_redump.zip"
)
NET_YAROZE_JP_SDK_DIR = EXTRACTED / "Net Yaroze JP SDK true__manual"


def run_7z(args: list[str]) -> bool:
    cp = subprocess.run([str(SEVENZIP)] + args, capture_output=True, text=True)
    if cp.returncode != 0:
        log.error("7z failed (rc=%d): %s\nstderr: %s", cp.returncode,
                  " ".join(args), cp.stderr[:400])
        return False
    return True


def ensure_jp_sdk_unpacked() -> Path | None:
    """Manually unpack the real Net Yaroze Japan SDK zip if needed and queue
    its .bin for conversion."""
    if not NET_YAROZE_JP_SDK_ZIP.exists():
        log.warning("missing zip: %s", NET_YAROZE_JP_SDK_ZIP)
        return None
    NET_YAROZE_JP_SDK_DIR.mkdir(parents=True, exist_ok=True)
    bins = list(NET_YAROZE_JP_SDK_DIR.glob("*.bin"))
    if not bins:
        log.info("7z extracting %s", NET_YAROZE_JP_SDK_ZIP.name)
        run_7z(["x", str(NET_YAROZE_JP_SDK_ZIP),
                f"-o{NET_YAROZE_JP_SDK_DIR}", "-y"])
        bins = list(NET_YAROZE_JP_SDK_DIR.glob("*.bin"))
    if not bins:
        log.error("no .bin produced in %s", NET_YAROZE_JP_SDK_DIR)
        return None
    return bins[0]


def process(src: Path, out_dir: Path, label: str) -> None:
    if not src.exists():
        log.warning("[%s] missing src: %s", label, src)
        return
    contents = out_dir / "contents"
    iso = out_dir / "cd_image.iso"
    out_dir.mkdir(parents=True, exist_ok=True)
    if contents.exists() and any(contents.iterdir()):
        log.info("[%s] already unpacked at %s, skipping", label, contents)
        return
    if not iso.exists():
        log.info("[%s] bin2iso: %s -> %s", label, src.name, iso.name)
        bin2iso.convert(src, iso, verbose=False)
    log.info("[%s] 7z extracting iso", label)
    contents.mkdir(exist_ok=True)
    if not run_7z(["x", str(iso), f"-o{contents}", "-y"]):
        log.warning("[%s] 7z could not open cd_image.iso as ISO 9660; the "
                    "PS1 image likely contains only a boot executable with "
                    "no normal file system. Leaving raw .iso in place for "
                    "downstream LWO/string scan.", label)
        return
    files = sum(1 for _ in contents.rglob("*") if _.is_file())
    log.info("[%s] extracted %d files into %s", label, files, contents)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    if not SEVENZIP.exists():
        log.error("7-Zip not found at %s", SEVENZIP)
        return 2

    sdk_bin = ensure_jp_sdk_unpacked()
    jobs = list(JOBS)
    if sdk_bin is not None:
        jobs.append((sdk_bin, EXTRACTED / "_ps1_net_yaroze_sdk_jp",
                     "Net Yaroze SDK Japan DTL-S3040"))

    for src, out_dir, label in jobs:
        try:
            process(src, out_dir, label)
        except SystemExit:
            raise
        except Exception as e:
            log.exception("[%s] failed: %s", label, e)

    return 0


if __name__ == "__main__":
    sys.exit(main())
