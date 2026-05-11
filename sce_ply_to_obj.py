"""Convert Sony Computer Entertainment "rsdform" PLY (header "@PLY940102")
to Wavefront OBJ.

Why: PS Artist Tool / Net Yaroze sample 3D data ship in this Sony-specific
text PLY (not the Stanford PLY). The format is a Reference Surface Data
companion to .RSD/.MAT/.GRP. Blender's stock PLY importer rejects them
because they start with "@PLY940102" instead of "ply\nformat ...".

Layout:
    @PLY940102
    # block counts (v n p)
    <V> <N> <P>
    # vertices
    <x y z>   × V
    # normals
    <nx ny nz> × N
    # polygons
    <P lines of integers>

Polygon line format observed in BASE/BLINK/BOW/BOXER:
    9 ints per line:
        type, v1, v2, v3, 0, n1, n2, n3, 0
    11 ints per line (rare, quads):
        type, v1, v2, v3, v4, 0, n1, n2, n3, n4, 0
    Some entries have type != 0 (texture/material flags) but the vertex
    indices remain in the same slots.

We're only after the geometry for Blender rendering, so we ignore normals,
materials, and texture coordinates — just emit "v" + "f" rows.

Usage:
    python sce_ply_to_obj.py input.ply output.obj
    python sce_ply_to_obj.py --dir <root>     # batch alongside source
"""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

log = logging.getLogger("sce_ply_to_obj")


def parse_sce_ply(text: str):
    """Return (verts, faces). faces are 1-based vertex index tuples."""
    lines = text.splitlines()
    i = 0
    # Header
    if not lines or not lines[0].startswith("@PLY"):
        raise ValueError("not a SCE rsdform PLY (missing @PLY magic)")
    i = 1

    def skip_comments_and_blanks():
        nonlocal i
        while i < len(lines) and (lines[i].strip().startswith("#")
                                  or lines[i].strip() == ""):
            i += 1

    # Block counts
    skip_comments_and_blanks()
    parts = lines[i].split()
    nv, nn, np_ = int(parts[0]), int(parts[1]), int(parts[2])
    i += 1

    # Vertices
    skip_comments_and_blanks()
    verts: list[tuple[float, float, float]] = []
    while len(verts) < nv and i < len(lines):
        s = lines[i].strip()
        if s and not s.startswith("#"):
            tok = s.split()
            verts.append((float(tok[0]), float(tok[1]), float(tok[2])))
        i += 1

    # Normals (skipped)
    skip_comments_and_blanks()
    skipped = 0
    while skipped < nn and i < len(lines):
        s = lines[i].strip()
        if s and not s.startswith("#"):
            skipped += 1
        i += 1

    # Polygons
    skip_comments_and_blanks()
    faces: list[tuple[int, ...]] = []
    seen = 0
    while seen < np_ and i < len(lines):
        s = lines[i].strip()
        if s and not s.startswith("#"):
            toks = s.split()
            try:
                ints = [int(t) for t in toks]
            except ValueError:
                i += 1
                continue
            # Heuristic: 9 ints = triangle (type, v1,v2,v3, 0, n1,n2,n3, 0)
            #           11 ints = quad     (type, v1..v4, 0, n1..n4, 0)
            # 1-based OBJ indices, so add 1 to each.
            if len(ints) == 9:
                f = (ints[1] + 1, ints[2] + 1, ints[3] + 1)
                faces.append(f)
            elif len(ints) == 11:
                f = (ints[1] + 1, ints[2] + 1, ints[3] + 1, ints[4] + 1)
                faces.append(f)
            elif len(ints) >= 4:
                # Fallback: assume slot 1..(len-1)/2 hold vertex indices
                # (vertex-only layout, no normals).
                n_per = (len(ints) - 1) // 2
                if n_per >= 3:
                    f = tuple(ints[1 + k] + 1 for k in range(n_per))
                    faces.append(f)
            seen += 1
        i += 1
    return verts, faces


def write_obj(verts, faces, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="ascii") as f:
        f.write("# Converted from SCE rsdform PLY by sce_ply_to_obj.py\n")
        f.write(f"# Verts: {len(verts)}  Faces: {len(faces)}\n")
        for x, y, z in verts:
            f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for face in faces:
            f.write("f " + " ".join(str(idx) for idx in face) + "\n")


def convert(src: Path, dst: Path) -> tuple[int, int]:
    text = src.read_text(encoding="ascii", errors="replace")
    verts, faces = parse_sce_ply(text)
    write_obj(verts, faces, dst)
    return len(verts), len(faces)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", nargs="?", type=Path)
    ap.add_argument("dst", nargs="?", type=Path)
    ap.add_argument("--dir", type=Path,
                    help="Batch mode: convert every *.PLY/*.ply under root")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    if args.dir:
        plys = sorted(args.dir.rglob("*.[Pp][Ll][Yy]"))
        log.info("Batch converting %d PLY under %s", len(plys), args.dir)
        ok = fail = 0
        for p in plys:
            try:
                head = p.open("rb").read(8)
                if not head.startswith(b"@PLY"):
                    continue  # standard PLY, skip
                obj_dst = p.with_suffix(".sceply.obj")
                if obj_dst.exists():
                    ok += 1
                    continue
                nv, nf = convert(p, obj_dst)
                ok += 1
                log.info("  %s -> %s  (%d verts, %d faces)", p.name, obj_dst.name, nv, nf)
            except Exception as e:
                fail += 1
                log.warning("  FAIL %s: %s", p, e)
        log.info("Done: ok=%d fail=%d", ok, fail)
        return 0

    if not args.src or not args.dst:
        ap.error("src and dst required (or use --dir)")
    nv, nf = convert(args.src, args.dst)
    log.info("Wrote %s: %d verts, %d faces", args.dst, nv, nf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
