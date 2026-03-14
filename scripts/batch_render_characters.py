"""
Batch Render All Sheets for All VRM Characters
================================================
Renders 13 sprite sheets for each VRM character using the fresh FBX pipeline.
No retarget addon needed — VRoid characters share identical bone names.

GPU Rendering (recommended):
    EEVEE is a GPU rasterizer. --background disables GPU access, forcing slow CPU
    software rasterization (~2.5 min/sheet). Launch with `start /min` instead to
    keep GPU access while staying out of the way:

    start /min /wait "" "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --python scripts/batch_render_characters.py -- --char blackdress_girl.vrm

    # start /min  → launches Blender with a minimized window
    # /wait       → blocks until Blender exits (for sequential operation)
    # No --background → EEVEE gets full GPU (OpenGL/Vulkan)

Usage examples:
    # All characters (GPU, minimized):
    start /min /wait "" "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --python scripts/batch_render_characters.py

    # Single character:
    start /min /wait "" "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --python scripts/batch_render_characters.py -- --char blackdress_girl.vrm

    # Start from specific sheet:
    start /min /wait "" "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --python scripts/batch_render_characters.py -- --char blackdress_girl.vrm --start 5

    # Specific character + specific sheet only:
    start /min /wait "" "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --python scripts/batch_render_characters.py -- --char blackdress_girl.vrm --sheet 8

    # CPU fallback (--background, no GPU — slower):
    "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --background --python scripts/batch_render_characters.py -- --char blackdress_girl.vrm
"""

import sys
import os
import time
import types
import argparse

# Parse args after "--"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
parser = argparse.ArgumentParser()
parser.add_argument("--char", help="Single VRM filename (e.g. blackdress_girl.vrm)")
parser.add_argument("--start", type=int, default=1, help="Start from sheet number")
parser.add_argument("--sheet", type=int, help="Render only this sheet number")
args = parser.parse_args(argv)

# Load render pipeline (use separate namespace to avoid __main__ block)
BASE_DIR = r"C:\dev\loracomp3"
_ns = {"__name__": "render_sheet"}
exec(open(os.path.join(BASE_DIR, "scripts", "render_sheet.py")).read(), _ns)
# Pull all names into our module scope
for _k, _v in _ns.items():
    if not _k.startswith("__"):
        globals()[_k] = _v

# Load camera modules
with open(os.path.join(BASE_DIR, "scripts", "camera_hybrid.py")) as f:
    cam_hybrid = types.ModuleType("camera_hybrid")
    exec(f.read(), cam_hybrid.__dict__)

with open(os.path.join(BASE_DIR, "scripts", "camera_perframe_ground.py")) as f:
    cam_pfg = types.ModuleType("camera_perframe_ground")
    exec(f.read(), cam_pfg.__dict__)

# Config paths
CONFIG_DIR = os.path.join(BASE_DIR, "data", "configs")
ALL_CONFIGS = sorted([
    os.path.join(CONFIG_DIR, f) for f in os.listdir(CONFIG_DIR)
    if f.startswith("sheet_") and f.endswith(".json")
])

# Character paths
CHAR_DIR = os.path.join(BASE_DIR, "data", "characters", "AvatarSample_B")
ALL_VRMS = [
    "army_man.vrm",
    "blackdress_girl.vrm",
    "blackjacket_man.vrm",
    "blackshirt_man.vrm",
    "bluedress_girl.vrm",
    "greenhair_girl.vrm",
    "pinkhair_boy.vrm",
]

# Output base
OUTPUT_BASE = os.path.join(BASE_DIR, "data", "renders_final")


def render_sheet_for_character(config_path, vrm_path, out_base, animations_dir=None):
    """Render a single sheet for a single character."""
    config = load_config(config_path)
    idx = config['sheet_index']
    config_basename = os.path.splitext(os.path.basename(config_path))[0]

    # Set output paths
    _state['out_dir'] = os.path.join(out_base, f"sheet_{idx:02d}")
    _state['sheet_path'] = os.path.join(out_base, f"{config_basename}.png")
    _state['gif_path'] = os.path.join(out_base, f"{config_basename}.gif")
    _state['scene_path'] = os.path.join(out_base, f"{config_basename}.blend")
    os.makedirs(_state['out_dir'], exist_ok=True)

    # Setup scene with VRM character
    setup_scene_vrm(config, vrm_path, animations_dir=animations_dir)
    setup_lighting()
    setup_render_settings()

    # Camera
    cam_type = config.get('camera', 'standard')
    if cam_type == 'hybrid':
        cam_hybrid.setup_camera_hybrid(
            _state,
            reference_frame=config.get('camera_reference_frame', 1),
            ortho_scale_override=config.get('camera_ortho_scale', None),
            camera_rotations=config.get('camera_rotations', None),
        )
    elif cam_type == 'perframe_ground':
        cam_pfg.setup_camera_perframe_ground(_state)
    else:
        setup_camera()

    # Spring bones
    run_spring_bones()

    # Select frames + render
    frames, expr_map = select_frames(config)
    for b in range(0, 16, 4):
        render_batch(frames, expr_map, b, b + 4)

    assemble_sheet()
    create_gif()


def render_character(char_vrm, start_sheet=1, only_sheet=None):
    """Render all sheets for one character."""
    vrm_path = os.path.join(CHAR_DIR, char_vrm)
    char_name = os.path.splitext(char_vrm)[0]
    out_base = os.path.join(OUTPUT_BASE, char_name)
    os.makedirs(out_base, exist_ok=True)

    # Use pre-retargeted animations if available
    retargeted_dir = os.path.join(BASE_DIR, "data", "characters", char_name, "animations")
    animations_dir = retargeted_dir if os.path.isdir(retargeted_dir) else None

    t0 = time.time()
    completed = []

    for config_path in ALL_CONFIGS:
        import json
        with open(config_path) as f:
            idx = json.load(f)['sheet_index']

        if only_sheet is not None and idx != only_sheet:
            continue
        if idx < start_sheet:
            continue

        # Skip if already rendered
        config_basename = os.path.splitext(os.path.basename(config_path))[0]
        sheet_path = os.path.join(out_base, f"{config_basename}.png")
        if os.path.exists(sheet_path):
            print(f"\n--- Skipping {char_name} sheet {idx:02d} (already exists) ---")
            completed.append(idx)
            continue

        try:
            t1 = time.time()
            render_sheet_for_character(config_path, vrm_path, out_base, animations_dir=animations_dir)
            elapsed = time.time() - t1
            completed.append(idx)
            print(f"\n=== {char_name} sheet {idx:02d} COMPLETE ({elapsed:.0f}s) ===\n")
        except Exception as e:
            print(f"\n!!! {char_name} sheet {idx:02d} FAILED: {e} !!!\n")
            import traceback
            traceback.print_exc()

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"DONE: {char_name} — {len(completed)} sheets in {elapsed:.0f}s")
    print(f"{'=' * 60}\n")
    return completed


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__" or True:  # Always run (Blender --python doesn't set __name__)
    chars = [args.char] if args.char else ALL_VRMS
    grand_t0 = time.time()
    total_sheets = 0

    for char_vrm in chars:
        completed = render_character(
            char_vrm,
            start_sheet=args.start,
            only_sheet=args.sheet,
        )
        total_sheets += len(completed)

    grand_elapsed = time.time() - grand_t0
    print(f"\n{'#' * 60}")
    print(f"GRAND TOTAL: {total_sheets} sheets for {len(chars)} characters in {grand_elapsed:.0f}s")
    print(f"{'#' * 60}")

    # Auto-exit Blender (needed when running without --background)
    import bpy
    bpy.ops.wm.quit_blender()
