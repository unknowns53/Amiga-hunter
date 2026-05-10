"""Render front / 3-quarter / side thumbnails for each candidate model.

Run inside Blender:
    blender --background --python blender_render.py

Reads:  output/candidate_models.csv
Writes: renders/<sha_prefix>/{front.png, threequarter.png, side.png, info.json}
        logs/render_errors.log
"""
from __future__ import annotations

import csv
import json
import logging
import sys
import traceback
from pathlib import Path

import bpy  # provided by Blender
import mathutils  # provided by Blender

# Anchor everything to this script's directory so it works regardless of cwd.
SCRIPT_DIR = Path(__file__).resolve().parent
CANDIDATES_CSV = SCRIPT_DIR / "output" / "candidate_models.csv"
RENDERS_DIR    = SCRIPT_DIR / "renders"
LOGS_DIR       = SCRIPT_DIR / "logs"
# Checkpoint file: resume from the last attempted candidate index after a
# Blender C-level crash, instead of re-iterating every candidate's idempotency
# check. Saved as JSON so we can validate against the current candidate list
# (count) and invalidate when the pipeline regenerates with a different size.
RESUME_FILE    = RENDERS_DIR / ".resume_index"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
RENDERS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "render.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("render")
ERROR_LOG = LOGS_DIR / "render_errors.log"

# Truncate the per-run error log so it reflects only this run; otherwise
# old failures from a prior Blender version (or different add-on state)
# linger and confuse triage.
ERROR_LOG.write_text("", encoding="utf-8")

# Only these extensions are wired up in import_model(). Filtering candidates
# upfront avoids per-row directory creation, info.json writes, and noisy
# "No importer wired up" log lines for the false-positive bulk
# (no-ext binaries, .info, .iff, .txt, .jpg, etc.).
# .lw is the original 1990s LightWave Object extension on Amiga (the .lwo /
# .lwob spelling is later); same FORM/LWOB format underneath, so the LWO
# importer handles them.
SUPPORTED_EXTENSIONS = {".obj", ".lwo", ".lwob", ".lw", ".3ds"}


# ---------- error logging --------------------------------------------------

def log_error(model_path: str, exc: BaseException) -> None:
    with ERROR_LOG.open("a", encoding="utf-8") as f:
        f.write(f"FAIL {model_path}: {exc}\n")
        f.write(traceback.format_exc())
        f.write("\n")


# ---------- resume checkpoint ----------------------------------------------

def read_resume_index(expected_count: int) -> int:
    """Return the last attempted candidate index from the checkpoint, or 0
    if none / mismatched. Mismatch on count means the candidate list changed
    (pipeline re-ran), so we restart from the beginning."""
    try:
        data = json.loads(RESUME_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return 0
    if data.get("count") != expected_count:
        log.info("Resume checkpoint count=%s mismatches current candidates=%d; "
                 "ignoring.", data.get("count"), expected_count)
        return 0
    return int(data.get("index", 0))


def write_resume_index(i: int, total: int) -> None:
    """Persist progress before each render attempt so a Blender crash leaves
    a recoverable marker. Keep writes resilient — failure here must not abort
    the pass."""
    try:
        RESUME_FILE.write_text(
            json.dumps({"index": i, "count": total}),
            encoding="utf-8",
        )
    except OSError as e:
        log.warning("Couldn't write resume checkpoint: %s", e)


# ---------- addon enabling -------------------------------------------------

def try_enable_addon(name: str) -> bool:
    try:
        bpy.ops.preferences.addon_enable(module=name)
        log.info("Enabled addon: %s", name)
        return True
    except Exception as e:
        log.debug("Addon not available (%s): %s", name, e)
        return False


def setup_blender_addons() -> None:
    """Try to enable importers we'll likely need.
    Names vary across Blender versions and add-on flavors;
    failures here are non-fatal."""
    for n in ["io_import_scene_lwo", "io_scene_lightwave", "io_scene_lwo"]:
        try_enable_addon(n)
    for n in ["io_scene_3ds", "io_import_scene_3ds"]:
        try_enable_addon(n)


# ---------- scene utilities ------------------------------------------------

def clear_scene() -> None:
    # Remove all objects
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    # Purge orphan data blocks
    for collection in (bpy.data.meshes, bpy.data.materials,
                       bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for item in list(collection):
            if item.users == 0:
                collection.remove(item)


def import_model(path: Path) -> bool:
    ext = path.suffix.lower()
    p = str(path)
    try:
        if ext == ".obj":
            if hasattr(bpy.ops.wm, "obj_import"):
                bpy.ops.wm.obj_import(filepath=p)
            else:
                bpy.ops.import_scene.obj(filepath=p)
        elif ext in {".lwo", ".lwob", ".lw"}:
            if hasattr(bpy.ops.import_scene, "lwo"):
                bpy.ops.import_scene.lwo(filepath=p)
            else:
                raise RuntimeError(
                    "LWO importer unavailable. Install a community LWO add-on, "
                    "e.g. https://github.com/nangtani/blender-import-lwo")
        elif ext == ".3ds":
            if hasattr(bpy.ops.import_scene, "autodesk_3ds"):
                bpy.ops.import_scene.autodesk_3ds(filepath=p)
            else:
                raise RuntimeError(
                    "3DS importer unavailable in core Blender 4.x; install community add-on.")
        else:
            raise RuntimeError(f"No importer wired up for extension {ext!r}")
        return True
    except Exception as e:
        log.error("Import failed for %s: %s", path, e)
        log_error(p, e)
        return False


def get_scene_bbox():
    """Return (center_vec, max_dimension) for all mesh objects, or None."""
    coords = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        for v in o.bound_box:
            coords.append(o.matrix_world @ mathutils.Vector(v))
    if not coords:
        return None
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    center = mathutils.Vector((
        (min(xs) + max(xs)) / 2,
        (min(ys) + max(ys)) / 2,
        (min(zs) + max(zs)) / 2,
    ))
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    return center, max(size, 1e-3)


def setup_lighting() -> None:
    bpy.ops.object.light_add(type="SUN", location=(5, -5, 10))
    sun = bpy.context.object
    sun.data.energy = 3.0
    bpy.ops.object.light_add(type="AREA", location=(-5, -3, 5))
    area = bpy.context.object
    area.data.energy = 200.0
    area.data.size = 5.0


def configure_render_engine() -> None:
    scene = bpy.context.scene
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    # Engine name moved across versions: 4.2-4.x calls it BLENDER_EEVEE_NEXT,
    # 5.0+ renamed it back to BLENDER_EEVEE (legacy is BLENDER_EEVEE_LEGACY).
    # Try the 4.x name first, fall back to the 5.x name, then leave default.
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            log.info("Render engine: %s", engine)
            return
        except Exception:
            continue
    log.warning("Falling back to default render engine: %s", scene.render.engine)


def render_view(out_path: Path, cam_offset, center, distance) -> None:
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_obj = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    try:
        offset = mathutils.Vector(cam_offset).normalized() * distance
        cam_obj.location = center + offset
        direction = center - cam_obj.location
        cam_obj.rotation_mode = "QUATERNION"
        cam_obj.rotation_quaternion = direction.to_track_quat("-Z", "Y")
        bpy.context.scene.camera = cam_obj
        bpy.context.scene.render.filepath = str(out_path)
        bpy.ops.render.render(write_still=True)
    finally:
        bpy.data.objects.remove(cam_obj, do_unlink=True)
        if cam_data.users == 0:
            bpy.data.cameras.remove(cam_data)


# ---------- per-model driver -----------------------------------------------

def render_model(path: Path, sha256: str, out_dir: Path) -> bool:
    out_dir.mkdir(parents=True, exist_ok=True)
    info_path = out_dir / "info.json"
    info = {
        "source": str(path),
        "sha256": sha256,
        "ext": path.suffix.lower(),
        "renders": {},
    }

    clear_scene()
    if not import_model(path):
        info["error"] = "import_failed"
        info_path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
        return False

    bbox = get_scene_bbox()
    if bbox is None:
        info["error"] = "no_geometry"
        info_path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
        return False
    center, size = bbox
    distance = max(size * 2.0, 1.0)

    setup_lighting()
    configure_render_engine()

    views = {
        "front":        (0, -1, 0),     # -Y axis
        "threequarter": (1, -1, 0.5),
        "side":         (1, 0, 0),      # +X axis
    }
    for name, offset in views.items():
        out = out_dir / f"{name}.png"
        try:
            render_view(out, offset, center, distance)
            info["renders"][name] = str(out)
        except Exception as e:
            log.error("Render %s failed for %s: %s", name, path, e)
            log_error(str(path), e)
            info["renders"][name] = f"ERROR: {e}"

    info_path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


# ---------- main -----------------------------------------------------------

def main() -> None:
    if not CANDIDATES_CSV.exists():
        log.error("Missing %s; run run_pipeline.py first.", CANDIDATES_CSV)
        return

    setup_blender_addons()

    with CANDIDATES_CSV.open("r", encoding="utf-8") as fh:
        all_rows = list(csv.DictReader(fh))

    candidates = [r for r in all_rows
                  if (r.get("ext") or "").lower() in SUPPORTED_EXTENSIONS]
    skipped = len(all_rows) - len(candidates)
    log.info("Rendering %d candidate(s) (skipped %d unsupported-extension rows)",
             len(candidates), skipped)

    # Idempotency check: skip rows whose render dir already has all 3 views
    # plus a non-error info.json. Crucial because the candidate set keeps
    # growing as we pull more sources, and re-rendering 1000+ models we
    # already have eats hours.
    #
    # Crash-safe sentinel: malformed LWO/3DS files can take down the entire
    # Blender process with EXCEPTION_ACCESS_VIOLATION (a C-level crash that
    # Python try/except cannot catch). Without a marker, the next run hits
    # the same file and crashes again — infinite loop. We touch
    # ".render_attempted" before importing; if a future run sees this
    # sentinel WITHOUT a complete result, we skip the file as a known
    # crasher.
    #
    # Resume checkpoint: even with the sentinel, every restart had to walk
    # the whole candidate list (~5000 rows) doing stat + iterdir on each
    # already-rendered out_dir. For C-crash recovery loops that restart
    # dozens of times, this idempotency walk dominates wall-clock. We now
    # persist the last attempted index before each render and fast-forward
    # past it on restart, dropping the per-pass overhead from ~10s to ~1s.
    expected_views = {"front.png", "threequarter.png", "side.png"}
    resume_from = read_resume_index(len(candidates))
    if resume_from > 0:
        log.info("Resuming from checkpoint index %d/%d (skipping prior attempts)",
                 resume_from, len(candidates))
    success = fail = already = crash_skipped = fast_forward = 0
    for i, row in enumerate(candidates, 1):
        # Fast-forward: previously attempted in this candidate-list version.
        # Disk state (sentinel / info.json) is authoritative for the prior
        # attempt's outcome; we don't need to re-evaluate it here.
        if i <= resume_from:
            fast_forward += 1
            continue

        path = Path(row["path"])
        if not path.exists():
            log.warning("Skipping (file missing): %s", path)
            fail += 1
            write_resume_index(i, len(candidates))
            continue

        sha = row.get("sha256") or ""
        if not sha or sha == "TOO_LARGE":
            sha = f"nohash_{i:05d}"
        out_dir = RENDERS_DIR / sha[:16]

        if out_dir.exists():
            existing = {p.name for p in out_dir.iterdir() if p.is_file()}
            info_path = out_dir / "info.json"
            info_ok = False
            if info_path.exists():
                try:
                    info_ok = "error" not in json.loads(info_path.read_text(encoding="utf-8"))
                except Exception:
                    info_ok = False
            if expected_views.issubset(existing) and info_ok:
                already += 1
                write_resume_index(i, len(candidates))
                continue
            # Sentinel exists but result is incomplete -> previous run crashed
            # mid-import on this file. Don't try again.
            if (out_dir / ".render_attempted").exists():
                log.warning("Skipping (previously crashed Blender): %s", path)
                crash_skipped += 1
                write_resume_index(i, len(candidates))
                continue

        log.info("[%d/%d] %s", i, len(candidates), path.name)
        out_dir.mkdir(parents=True, exist_ok=True)
        sentinel = out_dir / ".render_attempted"
        sentinel.touch()
        # Record progress BEFORE the import so a C-level crash still leaves
        # the checkpoint pointing past this file.
        write_resume_index(i, len(candidates))
        try:
            ok = render_model(path, sha, out_dir)
            if ok:
                success += 1
            else:
                fail += 1
        except Exception as e:
            log.error("Unexpected failure for %s: %s", path, e)
            log_error(str(path), e)
            fail += 1

    log.info("Render summary: success=%d fail=%d already=%d crash_skipped=%d "
             "fast_forward=%d",
             success, fail, already, crash_skipped, fast_forward)


if __name__ == "__main__":
    main()
