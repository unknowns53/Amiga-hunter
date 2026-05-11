"""Convert "Flat DXF" output from StudioPro(TM) 3d 1.5 to Wavefront OBJ.

Why: PlayStation Net Yaroze + PS Artist Tool sample models use a simplified
DXF written by StudioPro 3d 1.5 that contains only an ENTITIES section with
3DFACE primitives (quads, group codes 10-13 / 20-23 / 30-33). Blender's
built-in DXF importer is geared for AutoCAD R12+ and doesn't load these
reliably, but the format is dead simple to parse by hand.

DXF tokens are (group_code, value) pairs. The original files put each token
on its own line, but the on-disc copies we extracted have all tokens jammed
onto one line, separated by tab characters. We accept both: split on tab and
newline, treat the resulting stream as alternating code/value entries.

Each entity is introduced by group code 0 with value == entity name (e.g.
"3DFACE", "SECTION", "ENDSEC", "EOF"). Inside a 3DFACE we expect group
codes 10/20/30 .. 13/23/33 for the 4 vertices.

Usage:
    python dxf3dface_to_obj.py input.dxf output.obj
    python dxf3dface_to_obj.py --dir <root_dir>   # batch convert in-place
"""
from __future__ import annotations
import argparse
import logging
import re
import sys
from pathlib import Path

log = logging.getLogger("dxf3dface_to_obj")


def tokenize(text: str):
    """Yield (group_code, value_str) pairs."""
    # Tabs are used as separators in our on-disc copies; the original spec
    # uses newlines. Splitting on both lets one parser handle both.
    parts = re.split(r"[\t\r\n]+", text)
    parts = [p for p in parts if p != ""]
    it = iter(parts)
    for code in it:
        try:
            val = next(it)
        except StopIteration:
            return
        try:
            yield int(code), val
        except ValueError:
            # Non-integer code -- skip the malformed pair and continue.
            continue


def parse_dxf_3dfaces(text: str):
    """Return list of quads, each a tuple of 4 (x,y,z) tuples."""
    quads = []
    cur_quad: dict[int, float] = {}
    in_3dface = False
    for code, val in tokenize(text):
        if code == 0:
            if in_3dface and len(cur_quad) >= 12:
                # Finalize previous 3DFACE.
                pts = []
                for i in range(4):
                    pts.append((cur_quad[10 + i], cur_quad[20 + i], cur_quad[30 + i]))
                quads.append(pts)
            in_3dface = (val.strip().upper() == "3DFACE")
            cur_quad = {}
        elif in_3dface and code in (10, 11, 12, 13, 20, 21, 22, 23, 30, 31, 32, 33):
            try:
                cur_quad[code] = float(val)
            except ValueError:
                pass
    if in_3dface and len(cur_quad) >= 12:
        pts = []
        for i in range(4):
            pts.append((cur_quad[10 + i], cur_quad[20 + i], cur_quad[30 + i]))
        quads.append(pts)
    return quads


def write_obj(quads, out: Path) -> int:
    """Write quads as an OBJ. Returns vertex count. Welds duplicate verts."""
    verts: list[tuple[float, float, float]] = []
    vmap: dict[tuple, int] = {}
    faces: list[tuple[int, int, int, int]] = []
    for q in quads:
        idxs = []
        for p in q:
            key = (round(p[0], 5), round(p[1], 5), round(p[2], 5))
            i = vmap.get(key)
            if i is None:
                i = len(verts) + 1
                vmap[key] = i
                verts.append(p)
            idxs.append(i)
        # Skip degenerate quads (triangle disguised as quad).
        if idxs[2] == idxs[3]:
            faces.append((idxs[0], idxs[1], idxs[2], idxs[2]))
        else:
            faces.append(tuple(idxs))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="ascii") as f:
        f.write(f"# Converted from StudioPro Flat DXF by dxf3dface_to_obj.py\n")
        f.write(f"# Verts: {len(verts)}  Faces: {len(faces)}\n")
        for x, y, z in verts:
            f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for q in faces:
            if q[2] == q[3]:
                f.write(f"f {q[0]} {q[1]} {q[2]}\n")
            else:
                f.write(f"f {q[0]} {q[1]} {q[2]} {q[3]}\n")
    return len(verts)


def convert(src: Path, dst: Path) -> tuple[int, int]:
    text = src.read_text(encoding="ascii", errors="replace")
    quads = parse_dxf_3dfaces(text)
    nv = write_obj(quads, dst)
    return nv, len(quads)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", nargs="?", type=Path)
    ap.add_argument("dst", nargs="?", type=Path)
    ap.add_argument("--dir", type=Path,
                    help="Batch mode: convert every *.dxf under this directory, "
                         "writing OBJ alongside.")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    if args.dir:
        dxfs = sorted(args.dir.rglob("*.[Dd][Xx][Ff]"))
        log.info("Batch converting %d DXF under %s", len(dxfs), args.dir)
        ok = fail = 0
        for d in dxfs:
            try:
                obj = d.with_suffix(".obj")
                nv, nf = convert(d, obj)
                ok += 1
                log.info("  %s  ->  %s  (%d verts, %d quads)", d.name, obj.name, nv, nf)
            except Exception as e:
                fail += 1
                log.warning("  FAIL %s: %s", d, e)
        log.info("Done: ok=%d fail=%d", ok, fail)
        return 0

    if not args.src or not args.dst:
        ap.error("src and dst required (or use --dir)")
    nv, nf = convert(args.src, args.dst)
    log.info("Wrote %s: %d verts, %d quads", args.dst, nv, nf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
