"""Run blender_render.py in a loop, recovering from EXCEPTION_ACCESS_VIOLATION
crashes by marking the offending render dir as crashed and restarting.

The LWO/3DS importers in Blender 4.x can hit C-level crashes on malformed
files that Python can't catch. Each crash terminates the entire Blender
process. blender_render.py writes a `.render_attempted` sentinel before
import, so once a file has crashed once, subsequent runs skip it. This
wrapper just re-launches Blender until a run completes cleanly or makes
no further progress.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RENDERS_DIR = SCRIPT_DIR / "renders"
BLENDER = r"D:\blender-4.5.9-windows-x64\blender.exe"
RENDER_SCRIPT = SCRIPT_DIR / "blender_render.py"
MAX_PASSES = 200


def mark_crashed_dirs() -> int:
    """Touch .render_attempted in any out_dir that exists but has no
    info.json and fewer than 3 PNGs (i.e. left behind by a crash)."""
    if not RENDERS_DIR.exists():
        return 0
    marked = 0
    for d in RENDERS_DIR.iterdir():
        if not d.is_dir():
            continue
        files = list(d.iterdir())
        sentinel = d / ".render_attempted"
        if sentinel.exists():
            continue
        info = d / "info.json"
        pngs = [f for f in files if f.suffix == ".png"]
        if not files or (not info.exists() and len(pngs) < 3):
            sentinel.touch()
            marked += 1
    return marked


def run_blender() -> int:
    """Launch Blender. Returns its exit code (negative on signal/crash on
    POSIX, large positive on Windows access violation)."""
    cmd = [BLENDER, "--background", "--python", str(RENDER_SCRIPT)]
    print(f"\n--- Launching: {' '.join(cmd)} ---", flush=True)
    proc = subprocess.run(cmd, cwd=SCRIPT_DIR)
    return proc.returncode


def count_sentinels() -> int:
    if not RENDERS_DIR.exists():
        return 0
    return sum(1 for d in RENDERS_DIR.iterdir()
               if d.is_dir() and (d / ".render_attempted").exists())


def count_completed() -> int:
    if not RENDERS_DIR.exists():
        return 0
    return sum(1 for d in RENDERS_DIR.iterdir()
               if d.is_dir() and (d / "info.json").exists()
               and (d / "front.png").exists()
               and (d / "threequarter.png").exists()
               and (d / "side.png").exists())


def main() -> None:
    """Progress is real when the count of attempted-or-completed dirs grows.
    Each crash adds a sentinel (blender_render.py touches it before import);
    each successful render adds info.json + 3 PNGs. Either way the dir set
    expands. If a pass adds nothing new, we're done or stuck."""
    for pass_no in range(1, MAX_PASSES + 1):
        # Sweep up legacy crashed dirs (from runs before sentinel logic existed).
        legacy_marked = mark_crashed_dirs()
        before_sent = count_sentinels()
        before_done = count_completed()
        print(f"\n=== Pass {pass_no}: legacy_marked={legacy_marked} "
              f"sentinels={before_sent} completed={before_done} ===", flush=True)
        rc = run_blender()
        after_sent = count_sentinels()
        after_done = count_completed()
        new_sent = after_sent - before_sent
        new_done = after_done - before_done
        print(f"--- Pass {pass_no} rc={rc} new_sentinels={new_sent} "
              f"new_completed={new_done} ---", flush=True)
        if rc == 0 and new_sent == 0:
            print(f"\n=== All renders complete after {pass_no} pass(es) ===", flush=True)
            return
        if new_sent == 0 and new_done == 0 and legacy_marked == 0:
            print(f"\n=== No progress this pass; aborting ===", flush=True)
            sys.exit(1)
    print(f"\n=== Hit MAX_PASSES={MAX_PASSES}; bailing ===", flush=True)


if __name__ == "__main__":
    main()
