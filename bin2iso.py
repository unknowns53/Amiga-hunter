"""Convert PlayStation 1 CDROM XA raw BIN images (2352 bytes/sector) to a
plain ISO 9660 image (2048 bytes/sector, user data only).

PS1 dev tool discs in our B2 batch (LightWave 3D 4.0 Japan, Graphic Artist
Tools 1.8 DTL-S220, PlayStation Artist Tool DTL-S250, Net Yaroze SDK
Japan/USA) are all Mode 2 raw images. 7-Zip 26.x cannot mount them as
ISOs because the file system lives inside the 2048-byte user-data region
of each 2352-byte sector. Stripping out the sync + sector header + ECC
yields a vanilla ISO 9660 image that 7-Zip can walk normally.

Sector layout we accept:
  Mode 1 (rare on PS1):  16 bytes header + 2048 user + 288 EDC/ECC = 2352
  Mode 2 Form 1 (data):  16 bytes header + 8 byte subhdr + 2048 user
                         + 280 EDC/ECC = 2352. submode bit 5 = 0.
  Mode 2 Form 2 (audio/streaming): 2324 user data, submode bit 5 = 1.
                         Skipped (not part of ISO 9660 file system).

Usage:
    python bin2iso.py <input.bin> <output.iso>
"""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

SECTOR_RAW = 2352
HEADER = 16          # 12-byte sync + 4-byte sector header
USER_FORM1 = 2048
SUBMODE_OFFSET = 18  # byte 2 of the 8-byte subheader
SUBMODE_FORM2_BIT = 0x20

log = logging.getLogger("bin2iso")


def looks_raw_ps1(buf: bytes) -> bool:
    if len(buf) < HEADER:
        return False
    # 12-byte sync: 00 FF*10 00
    if buf[0] != 0x00 or buf[11] != 0x00:
        return False
    if buf[1:11] != b"\xff" * 10:
        return False
    return True


def convert(src: Path, dst: Path, *, verbose: bool = True) -> tuple[int, int]:
    size = src.stat().st_size
    if size % SECTOR_RAW != 0:
        log.warning("size %d not divisible by 2352, will read up to last full sector", size)
    sectors = size // SECTOR_RAW
    f1 = 0
    f2 = 0
    other = 0
    written = 0
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        first = fin.read(SECTOR_RAW)
        if not looks_raw_ps1(first):
            raise SystemExit(
                f"{src.name}: first sector does not look like a PS1 raw image "
                f"(expected 00 FF*10 00 sync). Refusing to convert."
            )
        fin.seek(0)
        for i in range(sectors):
            buf = fin.read(SECTOR_RAW)
            if not buf or len(buf) < SECTOR_RAW:
                break
            mode = buf[15]
            if mode == 2:
                submode = buf[SUBMODE_OFFSET]
                if submode & SUBMODE_FORM2_BIT:
                    f2 += 1
                    continue
                user = buf[24:24 + USER_FORM1]
                fout.write(user)
                f1 += 1
                written += USER_FORM1
            elif mode == 1:
                user = buf[16:16 + USER_FORM1]
                fout.write(user)
                f1 += 1
                written += USER_FORM1
            else:
                other += 1
                continue
    if verbose:
        log.info(
            "%s -> %s: %d sectors processed, Form1=%d Form2-skipped=%d other=%d, output=%d bytes",
            src.name, dst.name, sectors, f1, f2, other, written,
        )
    return f1, written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    if not args.src.exists():
        print(f"missing src: {args.src}", file=sys.stderr)
        return 2
    args.dst.parent.mkdir(parents=True, exist_ok=True)
    convert(args.src, args.dst, verbose=not args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
