"""Convert Amiga-native 3D model formats to OBJ so Blender can import them.

Why this exists: the Aminet `pix/3dobj/` archive set holds the most
interesting human-head models (head.lha, headobj.lha, easyhead.lha,
Glasshead.lha, headmorph.lha) but they are stored in formats — Imagine
TDDD, Real 3D v2, "anim1.4" — that have no Blender importer, community
or otherwise. Without conversion, those models cannot be rendered or
matched against the reference image. This module fills that gap.

Currently implemented:
  - Imagine TDDD  (FORM ... TDDD ... OBJ ... DESC chunks)
  - LightWave LWOB (FORM ... LWOB ... PNTS / POLS / SRFS / SURF chunks)

Planned:
  - Real 3D v2   ("object\\x00..." header)
  - anim1.4      (Real 3D animation/morph container)

Why LWOB needs a custom parser: the community Blender LWO addon
(nangtani/blender-import-lwo) crashes at C-level (EXCEPTION_ACCESS_VIOLATION)
on certain LIGHT-ROM era files such as ROMAN.LWO. We bypass it entirely by
parsing the IFF chunks directly and emitting OBJ — geometry only, materials
discarded.

Usage:
    from pipeline.convert import convert_all
    summary = convert_all()  # walks EXTRACTED_DIR, writes <stem>.obj alongside

The OBJ files land next to the source binary (same directory, same stem)
so the existing scan/identify steps pick them up without needing a
separate output directory.
"""
from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from pathlib import Path

from .config import EXTRACTED_DIR

log = logging.getLogger(__name__)

# Imagine TDDD coordinates are stored as signed 32-bit integers where
# 65536 represents 1.0 unit (i.e. 16.16 fixed-point). This matches what
# we observe in real archives: vertices like 0x000cc0d8 / 65536 ≈ 12.75
# come out at sensible head-model scale.
TDDD_UNIT = 65536.0


@dataclass
class Mesh:
    """One contiguous chunk of geometry — what TDDD calls a DESC and what
    OBJ calls a 'g'roup."""
    name: str
    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, int, int]]  # 0-indexed triangle indices


# ---------- IFF chunk walking ---------------------------------------------

def _is_chunk_name(name: bytes) -> bool:
    """IFF chunk names are 4 ASCII chars, normally uppercase + space/digit."""
    if len(name) != 4:
        return False
    return all(0x20 <= c <= 0x7e for c in name)


def _walk_chunks(buf: bytes):
    """Yield (name, payload) for every IFF-style chunk in buf.

    IFF chunks are: 4-byte name, 4-byte big-endian size, payload, optional
    1-byte pad to keep chunks word-aligned. We bail at the first non-ASCII
    chunk name to handle trailing junk gracefully."""
    i = 0
    n = len(buf)
    while i + 8 <= n:
        name = buf[i:i + 4]
        if not _is_chunk_name(name):
            break
        size = struct.unpack(">I", buf[i + 4:i + 8])[0]
        end = i + 8 + size
        if end > n:
            log.debug("Chunk %r claims %d bytes but only %d remain; stopping",
                      name, size, n - i - 8)
            break
        yield name, buf[i + 8:end]
        # Word alignment.
        i = end + (size & 1)


# ---------- Imagine TDDD parser -------------------------------------------

def _parse_tddd_pnts(payload: bytes) -> list[tuple[float, float, float]]:
    """PNTS: u16 count, then count × 3 × signed 32-bit BE (×1/65536).

    Axis remap: Imagine TDDD uses Z-up with +Y pointing into the screen
    (away from the viewer in front view). Wavefront OBJ assumes Y-up with
    -Z pointing into the screen. We map Imagine (x, y, z) -> OBJ (x, z, -y)
    so that converted heads render upright and front-facing in Blender."""
    if len(payload) < 2:
        return []
    count = struct.unpack(">H", payload[:2])[0]
    expected = 2 + count * 12
    if len(payload) < expected:
        log.warning("PNTS truncated: have %d bytes, need %d for %d vertices",
                    len(payload), expected, count)
        count = (len(payload) - 2) // 12
    coords = struct.unpack(f">{count * 3}i", payload[2:2 + count * 12])
    out: list[tuple[float, float, float]] = []
    for k in range(count):
        x = coords[k * 3 + 0] / TDDD_UNIT
        y = coords[k * 3 + 1] / TDDD_UNIT
        z = coords[k * 3 + 2] / TDDD_UNIT
        # Z-up -> Y-up.
        out.append((x, z, -y))
    return out


def _parse_tddd_edge(payload: bytes) -> list[tuple[int, int]]:
    """EDGE: u16 count, then count × 2 × u16 BE point indices."""
    if len(payload) < 2:
        return []
    count = struct.unpack(">H", payload[:2])[0]
    expected = 2 + count * 4
    if len(payload) < expected:
        count = (len(payload) - 2) // 4
    idx = struct.unpack(f">{count * 2}H", payload[2:2 + count * 4])
    return [(idx[k * 2], idx[k * 2 + 1]) for k in range(count)]


def _parse_tddd_face_indices(payload: bytes) -> list[tuple[int, int, int]]:
    """FACE: u16 count, then count × 3 × u16 BE indices. The indices are
    either point indices (SHAP / older format) or edge indices (SHP2 /
    newer format) — caller decides how to interpret them."""
    if len(payload) < 2:
        return []
    count = struct.unpack(">H", payload[:2])[0]
    expected = 2 + count * 6
    if len(payload) < expected:
        log.warning("FACE truncated: have %d bytes, need %d for %d faces",
                    len(payload), expected, count)
        count = (len(payload) - 2) // 6
    idx = struct.unpack(f">{count * 3}H", payload[2:2 + count * 6])
    return [(idx[k * 3], idx[k * 3 + 1], idx[k * 3 + 2]) for k in range(count)]


def _edges_to_triangle(
    edges: list[tuple[int, int]], e0: int, e1: int, e2: int,
) -> tuple[int, int, int] | None:
    """Convert 3 edge indices (SHP2 face encoding) into a 3-vertex triangle.
    A triangle's 3 edges share endpoints in a specific way: e0=(a,b),
    e1 contains b and c, e2 contains c and a (in either order). Return the
    triangle as (a, b, c) preserving winding from e0."""
    if max(e0, e1, e2) >= len(edges):
        return None
    a, b = edges[e0]
    p, q = edges[e1]
    if   p == b: c = q
    elif q == b: c = p
    elif p == a: a, b = b, a; c = q
    elif q == a: a, b = b, a; c = p
    else:
        return None  # edges not connected
    # Sanity-check the closing edge for completeness.
    r, s = edges[e2]
    if {r, s} != {c, a}:
        return None
    return (a, b, c)


def _parse_tddd_desc(payload: bytes) -> Mesh | None:
    """A DESC chunk holds one sub-object: NAME + (SHAP|SHP2) + PNTS +
    [EDGE] + FACE (+ misc).

    SHAP vs SHP2 is the critical distinction: SHAP files store FACE as
    point indices, SHP2 files store FACE as edge indices and a separate
    EDGE chunk holds the (point, point) pairs. Picking the wrong
    interpretation produces nonsense triangles."""
    name = "object"
    shape_kind: str | None = None  # "SHAP" or "SHP2"
    verts: list[tuple[float, float, float]] = []
    edges: list[tuple[int, int]] = []
    raw_faces: list[tuple[int, int, int]] = []
    for cn, cp in _walk_chunks(payload):
        if cn == b"NAME":
            raw = cp.split(b"\x00", 1)[0]
            try:
                name = raw.decode("latin-1").strip() or "object"
            except Exception:
                name = "object"
        elif cn == b"SHAP":
            shape_kind = "SHAP"
        elif cn == b"SHP2":
            shape_kind = "SHP2"
        elif cn == b"PNTS":
            verts = _parse_tddd_pnts(cp)
        elif cn == b"EDGE":
            edges = _parse_tddd_edge(cp)
        elif cn == b"FACE":
            raw_faces = _parse_tddd_face_indices(cp)
    if not verts or not raw_faces:
        log.debug("DESC %r has no usable geometry (verts=%d faces=%d)",
                  name, len(verts), len(raw_faces))
        return None

    n = len(verts)
    faces: list[tuple[int, int, int]] = []
    # Empirically, TDDD's FACE chunk references EDGE indices whenever an
    # EDGE chunk is present, regardless of the SHAP/SHP2 marker. Some
    # SHAP-marked files (e.g. headobj's c.head.5) still ship an EDGE
    # chunk and faces only resolve correctly through edge indirection.
    # Only fall back to point-indexed FACE when no EDGE chunk exists.
    if edges:
        bad = 0
        for e0, e1, e2 in raw_faces:
            tri = _edges_to_triangle(edges, e0, e1, e2)
            if tri is None or max(tri) >= n:
                bad += 1
                continue
            faces.append(tri)
        if bad:
            log.debug("DESC %r (edge-indexed): %d/%d faces unresolvable",
                      name, bad, len(raw_faces))
    else:
        bad = sum(1 for f in raw_faces if max(f) >= n)
        if bad:
            log.warning("DESC %r (point-indexed): %d/%d faces reference "
                        "out-of-range vertices", name, bad, len(raw_faces))
        faces = [f for f in raw_faces if max(f) < n]

    if not faces:
        return None
    return Mesh(name=name, vertices=verts, faces=faces)


def parse_tddd(data: bytes) -> list[Mesh]:
    """Parse a complete TDDD file and return all sub-meshes found."""
    if data[:4] != b"FORM":
        return []
    form_size = struct.unpack(">I", data[4:8])[0]
    if data[8:12] != b"TDDD":
        return []
    body = data[12:8 + form_size]  # everything after "FORM <size> TDDD"

    meshes: list[Mesh] = []
    # Top-level after TDDD is usually one OBJ container holding multiple
    # DESCs. Walk both layers — if OBJ is missing we still find DESCs.
    def visit(buf: bytes) -> None:
        for cn, cp in _walk_chunks(buf):
            if cn == b"OBJ ":
                visit(cp)
            elif cn == b"DESC":
                m = _parse_tddd_desc(cp)
                if m is not None:
                    meshes.append(m)

    visit(body)
    return meshes


# ---------- LightWave LWOB parser -----------------------------------------

def _parse_lwob_pnts(payload: bytes) -> list[tuple[float, float, float]]:
    """LWOB PNTS: tightly packed float32 BE, 3 per vertex.

    LightWave is left-handed Y-up (X right, Y up, +Z forward).
    Wavefront OBJ is right-handed Y-up (X right, Y up, -Z forward).
    Flip Z so the model faces +Z (toward the viewer in front view)."""
    n = len(payload) // 12
    if n == 0:
        return []
    coords = struct.unpack(f">{n * 3}f", payload[:n * 12])
    out: list[tuple[float, float, float]] = []
    for k in range(n):
        x = coords[k * 3 + 0]
        y = coords[k * 3 + 1]
        z = coords[k * 3 + 2]
        out.append((x, y, -z))
    return out


def _parse_lwob_pols(payload: bytes, n_verts: int) -> list[tuple[int, ...]]:
    """LWOB POLS: stream of polygons.

    Each polygon: u16 BE numverts, numverts × u16 BE point indices,
    i16 BE surface index (signed, negative = detail polygon flag).
    We discard the surface index and keep the raw n-gon for later
    triangulation."""
    polys: list[tuple[int, ...]] = []
    i = 0
    n = len(payload)
    while i + 2 <= n:
        nv = struct.unpack(">H", payload[i:i + 2])[0]
        i += 2
        # Detail-polygon flag: high bit on numverts indicates detail polys
        # follow; LWOB uses negative surface index instead. Be defensive.
        if nv == 0 or nv > 1023:
            log.debug("Suspicious polygon vertex count %d at offset %d", nv, i - 2)
            break
        end = i + nv * 2
        if end + 2 > n:
            log.warning("POLS truncated mid-polygon at %d", i - 2)
            break
        idx = struct.unpack(f">{nv}H", payload[i:end])
        i = end + 2  # skip surface index
        if any(v >= n_verts for v in idx):
            continue
        polys.append(tuple(idx))
    return polys


def _triangulate(poly: tuple[int, ...]) -> list[tuple[int, int, int]]:
    """Fan-triangulate an n-gon. Good enough for convex faces, which is
    what LightWave content discs ship — characters are usually quads."""
    if len(poly) < 3:
        return []
    if len(poly) == 3:
        return [(poly[0], poly[1], poly[2])]
    out: list[tuple[int, int, int]] = []
    a = poly[0]
    for k in range(1, len(poly) - 1):
        out.append((a, poly[k], poly[k + 1]))
    return out


def parse_lwob(data: bytes) -> list[Mesh]:
    """Parse a LWOB file into a single Mesh (LWOB has no sub-object structure)."""
    if data[:4] != b"FORM" or data[8:12] != b"LWOB":
        return []
    form_size = struct.unpack(">I", data[4:8])[0]
    body = data[12:8 + form_size]

    verts: list[tuple[float, float, float]] = []
    raw_polys: list[tuple[int, ...]] = []
    name = "lwob"
    for cn, cp in _walk_chunks(body):
        if cn == b"PNTS":
            verts = _parse_lwob_pnts(cp)
        elif cn == b"POLS":
            # Defer parsing until we know vertex count for bounds check.
            raw_polys_payload = cp
            # Fallback: parse with current verts known (PNTS comes before POLS
            # in well-formed LWOB files, which is the case for ROMAN.LWO).
            raw_polys = _parse_lwob_pols(cp, len(verts) if verts else 1 << 31)

    if not verts or not raw_polys:
        return []

    faces: list[tuple[int, int, int]] = []
    for poly in raw_polys:
        faces.extend(_triangulate(poly))
    if not faces:
        return []
    return [Mesh(name=name, vertices=verts, faces=faces)]


# ---------- OBJ writing ----------------------------------------------------

def write_obj(meshes: list[Mesh], path: Path, source: Path | None = None) -> None:
    """Write a Wavefront OBJ. Each mesh becomes a 'g'roup. 1-indexed faces."""
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# Generated by pipeline/convert.py\n")
        if source is not None:
            fh.write(f"# Source: {source}\n")
        offset = 0
        for mesh in meshes:
            safe_name = "".join(c if c.isalnum() or c in "._-" else "_"
                                for c in mesh.name) or "object"
            fh.write(f"\no {safe_name}\n")
            for x, y, z in mesh.vertices:
                fh.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
            for a, b, c in mesh.faces:
                # OBJ is 1-indexed.
                fh.write(f"f {a + 1 + offset} {b + 1 + offset} {c + 1 + offset}\n")
            offset += len(mesh.vertices)


# ---------- Format detection ----------------------------------------------

def detect_format(path: Path) -> str | None:
    """Sniff the first bytes of a file and return a format tag, or None.

    We don't rely on file extension because most Amiga 3D models ship
    extension-less."""
    try:
        with path.open("rb") as fh:
            head = fh.read(32)
    except Exception:
        return None
    if len(head) < 12:
        return None
    if head[:4] == b"FORM" and head[8:12] == b"TDDD":
        return "tddd"
    if head[:4] == b"FORM" and head[8:12] == b"LWOB":
        return "lwob"
    # Real 3D v2 single object: starts with "object\x00..."
    if head[:7] == b"object\x00":
        return "real3d_v2"
    # Real 3D animation: "anim1.4\x00..."
    if head[:8] == b"anim1.4\x00":
        return "real3d_anim"
    return None


# ---------- Driver ---------------------------------------------------------

def convert_file(path: Path) -> Path | None:
    """Convert one source file. Returns the OBJ path on success, else None."""
    fmt = detect_format(path)
    if fmt is None:
        return None

    obj_path = path.with_name(path.name + ".obj")
    if obj_path.exists() and obj_path.stat().st_size > 0:
        log.debug("Already converted: %s", obj_path.name)
        return obj_path

    try:
        data = path.read_bytes()
    except Exception as e:
        log.warning("Cannot read %s: %s", path, e)
        return None

    if fmt == "tddd":
        meshes = parse_tddd(data)
        if not meshes:
            log.info("No geometry in TDDD %s", path.name)
            return None
        write_obj(meshes, obj_path, source=path)
        log.info("TDDD -> OBJ: %s (%d meshes, %d verts, %d faces)",
                 obj_path.name, len(meshes),
                 sum(len(m.vertices) for m in meshes),
                 sum(len(m.faces) for m in meshes))
        return obj_path

    if fmt == "lwob":
        meshes = parse_lwob(data)
        if not meshes:
            log.info("No geometry in LWOB %s", path.name)
            return None
        # Use the source filename as group name (LWOB has no embedded name).
        meshes[0].name = path.stem or "lwob"
        write_obj(meshes, obj_path, source=path)
        log.info("LWOB -> OBJ: %s (%d verts, %d faces)",
                 obj_path.name,
                 sum(len(m.vertices) for m in meshes),
                 sum(len(m.faces) for m in meshes))
        return obj_path

    # Other formats are stubs for now.
    log.debug("Format %s not yet supported: %s", fmt, path.name)
    return None


def convert_all() -> dict:
    """Walk EXTRACTED_DIR and convert every recognized model file."""
    if not EXTRACTED_DIR.exists():
        return {"scanned": 0, "converted": 0, "skipped": 0, "by_format": {}}

    scanned = converted = skipped = 0
    by_format: dict[str, int] = {}
    for p in EXTRACTED_DIR.rglob("*"):
        if not p.is_file():
            continue
        # Skip our own outputs.
        if p.suffix.lower() == ".obj":
            continue
        fmt = detect_format(p)
        if fmt is None:
            continue
        scanned += 1
        by_format[fmt] = by_format.get(fmt, 0) + 1
        result = convert_file(p)
        if result is not None:
            converted += 1
        else:
            skipped += 1
    return {
        "scanned": scanned,
        "converted": converted,
        "skipped": skipped,
        "by_format": by_format,
    }
