"""
Retarget + Export Pipeline
===========================
For each VRM character x each animation FBX:
  1. Import VRM character
  2. Import animation FBX
  3. Bind (Retarget addon: FBX active, VRM selected, same_bone_names=True)
  4. Visual bake onto VRM armature
  5. Export baked action as armature-only FBX
  6. Clean up

Output structure:
    data/characters/{char_name}/animations/
        Idle.fbx
        Walking.fbx
        ...

Usage:
    blender --background --python scripts/retarget_export.py
    blender --background --python scripts/retarget_export.py -- --char army_man.vrm
    blender --background --python scripts/retarget_export.py -- --char army_man.vrm --anim "Idle.fbx"

Skips existing output FBXs for resume support.
"""

import bpy
import os
import sys
import time
import argparse

# Enable Retarget addon (not auto-loaded in --background mode)
bpy.ops.extensions.package_install(repo_index=0, pkg_id="retarget", enable_on_install=True)
# Also explicitly enable it in case already installed but not enabled
import addon_utils
addon_utils.enable("bl_ext.blender_org.retarget")

# Parse args after "--"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
parser = argparse.ArgumentParser()
parser.add_argument("--char", help="Single VRM filename (e.g. army_man.vrm)")
parser.add_argument("--anim", help="Single animation FBX filename (e.g. Idle.fbx)")
args = parser.parse_args(argv)

# Paths
BASE_DIR = r"C:\dev\loracomp3"
CHAR_DIR = os.path.join(BASE_DIR, "data", "characters", "AvatarSample_B")
ANIMATIONS_DIR = os.path.join(BASE_DIR, "data", "animations")

# All 7 VRM characters (exclude AvatarSample_B — that's the original)
ALL_VRMS = [
    "army_man.vrm",
    "blackdress_girl.vrm",
    "blackjacket_man.vrm",
    "blackshirt_man.vrm",
    "bluedress_girl.vrm",
    "greenhair_girl.vrm",
    "pinkhair_boy.vrm",
]

# All 24 unique animation FBXs used across all 13 configs
ALL_ANIMS = [
    "Armada.fbx",
    "Bencao.fbx",
    "Block.fbx",
    "Falling Back Death.fbx",
    "Getting Up.fbx",
    "Head Hit.fbx",
    "Hook (1).fbx",
    "Hook Punch.fbx",
    "Hook.fbx",
    "Idle.fbx",
    "Illegal Knee.fbx",
    "Kicking.fbx",
    "Knee Jabs To Uppercut.fbx",
    "Martelo 2.fbx",
    "Medium Hit To Head.fbx",
    "Punch To Elbow Combo.fbx",
    "Quad Punch.fbx",
    "Right Hook.fbx",
    "Roundhouse Kick.fbx",
    "Run Forward.fbx",
    "Run To Rolling.fbx",
    "Stomach Hit.fbx",
    "Walking (1).fbx",
    "Walking.fbx",
]


def clean_scene():
    """Remove all objects and data blocks."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)
    for block in list(bpy.data.armatures):
        bpy.data.armatures.remove(block)
    for block in list(bpy.data.actions):
        bpy.data.actions.remove(block)
    for block in list(bpy.data.cameras):
        bpy.data.cameras.remove(block)
    for block in list(bpy.data.lights):
        bpy.data.lights.remove(block)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block)
    for block in list(bpy.data.images):
        bpy.data.images.remove(block)


def retarget_and_export(vrm_path, anim_fbx_path, output_fbx_path):
    """
    Retarget a single animation onto a VRM character and export as FBX.

    Workaround for Blender's FBX exporter: the exporter uses the current
    pose (not rest pose) for the Model node transform. To get correct rest
    pose in the exported FBX, we push the baked action to NLA, clear the
    active action, and set frame to 0 (before the NLA strip). At frame 0,
    the armature is at rest pose, so the Model node gets correct values.
    The animation is still exported correctly from the NLA evaluation.

    Args:
        vrm_path: Path to .vrm file
        anim_fbx_path: Path to source animation .fbx
        output_fbx_path: Path for exported .fbx
    """
    clean_scene()

    # 1. Import VRM character
    print(f"  Importing VRM: {os.path.basename(vrm_path)}")
    bpy.ops.import_scene.vrm(filepath=vrm_path)

    # Delete empties (VRM colliders)
    for obj in list(bpy.data.objects):
        if obj.type == 'EMPTY':
            bpy.data.objects.remove(obj, do_unlink=True)

    # Find VRM armature
    vrm_arm = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            vrm_arm = obj
            break
    if vrm_arm is None:
        raise RuntimeError("No armature found after VRM import")

    # 2. Import animation FBX
    print(f"  Importing FBX: {os.path.basename(anim_fbx_path)}")
    bpy.ops.import_scene.fbx(filepath=anim_fbx_path)

    # Delete empties (Freestyle crash prevention)
    for obj in list(bpy.data.objects):
        if obj.type == 'EMPTY':
            bpy.data.objects.remove(obj, do_unlink=True)

    # Find FBX armature
    fbx_arm = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj != vrm_arm:
            fbx_arm = obj
            break
    if fbx_arm is None:
        raise RuntimeError("No FBX armature found after import")

    if not fbx_arm.animation_data or not fbx_arm.animation_data.action:
        raise RuntimeError(f"FBX armature has no action: {anim_fbx_path}")

    action = fbx_arm.animation_data.action
    action_end = int(action.frame_range[1])
    print(f"  Source action: {action.name}, frames 1-{action_end}")

    # 3. Bind: FBX = active, VRM = selected
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    vrm_arm.select_set(True)
    fbx_arm.select_set(True)
    bpy.context.view_layer.objects.active = fbx_arm
    try:
        bpy.ops.armature.retarget_constrain_to_armature(same_bone_names=True)
    except (TypeError, RuntimeError) as e:
        # Known bug: operator throws TypeError/RuntimeError at the end because
        # self.current_m is None (bypasses invoke()). Non-blocking — constraints
        # are created successfully before the error.
        if "expected a string enum" in str(e) or "NoneType" in str(e):
            pass
        else:
            raise

    # 4. Bake onto VRM armature
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    vrm_arm.select_set(True)
    bpy.context.view_layer.objects.active = vrm_arm
    bpy.ops.object.mode_set(mode='POSE')

    bpy.ops.nla.bake(
        frame_start=1,
        frame_end=action_end,
        only_selected=False,
        visual_keying=True,
        clear_constraints=True,
        bake_types={'POSE'},
    )

    baked_action = vrm_arm.animation_data.action
    if baked_action is None:
        raise RuntimeError("Bake failed — no action on VRM armature")
    print(f"  Baked action: {baked_action.name}, range {baked_action.frame_range[:]}")

    # 5. Export as FBX with correct rest pose
    bpy.ops.object.mode_set(mode='OBJECT')

    anim_name = os.path.splitext(os.path.basename(anim_fbx_path))[0]
    baked_action.name = anim_name

    # Push action to NLA and clear active action. At frame 0 (before the
    # NLA strip), the armature evaluates to rest pose. The FBX exporter
    # writes the Model node from the current frame → rest pose. Animation
    # is baked from NLA evaluation at frames 1+.
    if vrm_arm.animation_data is None:
        vrm_arm.animation_data_create()
    track = vrm_arm.animation_data.nla_tracks.new()
    track.name = anim_name
    strip = track.strips.new(anim_name, 1, baked_action)
    strip.extrapolation = 'NOTHING'
    vrm_arm.animation_data.action = None
    bpy.context.scene.frame_set(0)

    bpy.ops.object.select_all(action='DESELECT')
    vrm_arm.select_set(True)
    bpy.context.view_layer.objects.active = vrm_arm

    os.makedirs(os.path.dirname(output_fbx_path), exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=output_fbx_path,
        use_selection=True,
        object_types={'ARMATURE'},
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_actions=True,
        bake_anim_use_nla_strips=True,
        bake_anim_force_startend_keying=True,
    )
    print(f"  Exported: {output_fbx_path}")


def process_character(char_vrm, anim_filter=None):
    """Process all animations for one character."""
    char_name = os.path.splitext(char_vrm)[0]
    vrm_path = os.path.join(CHAR_DIR, char_vrm)
    out_dir = os.path.join(BASE_DIR, "data", "characters", char_name, "animations")

    if not os.path.exists(vrm_path):
        print(f"ERROR: VRM not found: {vrm_path}")
        return 0

    anims = ALL_ANIMS
    if anim_filter:
        anims = [a for a in anims if a == anim_filter]
        if not anims:
            print(f"ERROR: Animation not found in list: {anim_filter}")
            return 0

    exported = 0
    skipped = 0
    failed = 0

    for anim_fbx in anims:
        output_path = os.path.join(out_dir, anim_fbx)
        anim_src = os.path.join(ANIMATIONS_DIR, anim_fbx)

        if not os.path.exists(anim_src):
            print(f"  SKIP (source missing): {anim_fbx}")
            skipped += 1
            continue

        if os.path.exists(output_path):
            print(f"  SKIP (exists): {anim_fbx}")
            skipped += 1
            continue

        try:
            t0 = time.time()
            print(f"\n[{char_name}] Retargeting: {anim_fbx}")
            retarget_and_export(vrm_path, anim_src, output_path)
            elapsed = time.time() - t0
            print(f"  Done ({elapsed:.1f}s)")
            exported += 1
        except Exception as e:
            print(f"  FAILED: {anim_fbx} — {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n--- {char_name}: {exported} exported, {skipped} skipped, {failed} failed ---")
    return exported


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__" or True:
    chars = [args.char] if args.char else ALL_VRMS
    grand_t0 = time.time()
    total = 0

    for char_vrm in chars:
        total += process_character(char_vrm, anim_filter=args.anim)

    grand_elapsed = time.time() - grand_t0
    print(f"\n{'#' * 60}")
    print(f"TOTAL: {total} FBXs exported for {len(chars)} characters in {grand_elapsed:.0f}s")
    print(f"{'#' * 60}")
