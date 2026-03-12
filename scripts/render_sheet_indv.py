"""
Sprite Sheet Render Pipeline (Per-Animation)
=============================================
Imports all animations into sequential NLA on one armature, then renders
each animation independently by muting others and shifting to frame 1.
Spring bones get fresh state per animation -- no carry-over.
Action frames in config map directly to scene frames (strip at frame 1).

Usage via Blender CLI:
    blender --background --python scripts/render_sheet_indv.py -- data/configs/sheet_XX.json

Usage via Blender MCP (step by step):
    exec(open(r"C:\dev\loracomp3\scripts\render_sheet_indv.py").read())
    load_config(r"C:\dev\loracomp3\data\configs\sheet_10_hit_block.json")
    # If scene already has the NLA setup (e.g., loaded from .blend):
    init_from_scene()
    # If starting fresh (kills MCP connection!):
    # setup_scene()
    render_animation(0)   # Mute others, shift to frame 1, render
    render_animation(1)
    render_animation(2)
    render_animation(3)
    assemble_sheet()
    create_gif()

CRITICAL GOTCHAS:
- Camera rotation MUST be (pi/2, 0, -pi/2) for +X facing. +pi/2 renders BLANK.
- Delete ALL empties after every FBX import (Freestyle crash).
- Blender 5.0 engine is 'BLENDER_EEVEE' not 'BLENDER_EEVEE_NEXT'.
- Mma Kick.fbx crashes Freestyle -- avoid entirely.
"""

import bpy
import os
import math
import time
import json
import struct


# ============================================================================
# Global state
# ============================================================================
_state = {
    'config': None,
    'config_path': None,
    'armature': None,
    'meshes': [],
    'face_obj': None,
    'sheet_index': None,
    'sheet_name': None,
    'out_dir': None,
    'sheet_path': None,
    'gif_path': None,
    'scene_path': None,
    # Original NLA strip positions (saved before shifting)
    'strip_positions': {},
}

# Paths
BASE_DIR = r"C:\dev\loracomp3"
ANIMATIONS_DIR = os.path.join(BASE_DIR, "data", "animations")
RENDERS_DIR = os.path.join(BASE_DIR, "data", "renders")
SCENES_DIR = os.path.join(BASE_DIR, "data", "scenes")

# Camera settings
CAM_DEPTH = -2.4
CAM_PADDING = 1.15
CAM_ROTATION = (math.pi / 2, 0, -math.pi / 2)

# Spring bone defaults
SPRING_STIFFNESS = 0.3
SPRING_DAMPING = 0.2
SPRING_REACTION = 2.0
SPRING_MAX_DEG = 45.0


# ============================================================================
# Config loading
# ============================================================================

def load_config(config_path):
    """Load a sprite sheet config JSON."""
    with open(config_path, 'r') as f:
        config = json.load(f)
    _state['config'] = config
    _state['config_path'] = config_path

    idx = config['sheet_index']
    config_basename = os.path.splitext(os.path.basename(config_path))[0]

    _state['sheet_index'] = idx
    _state['sheet_name'] = config_basename
    _state['out_dir'] = os.path.join(RENDERS_DIR, f"sheet_{idx:02d}")
    _state['sheet_path'] = os.path.join(RENDERS_DIR, f"{config_basename}.png")
    _state['gif_path'] = os.path.join(RENDERS_DIR, f"{config_basename}.gif")
    _state['scene_path'] = os.path.join(SCENES_DIR, f"{config_basename}.blend")

    print(f"Loaded config: {config['name']} (sheet {idx})")
    print(f"  Animations: {len(config['animations'])}")
    for anim in config['animations']:
        print(f"    {anim['name']}: {anim['frames']}f from {anim['fbx']}")
    print(f"  Output: {_state['sheet_path']}")
    return config


# ============================================================================
# Scene setup (imports all FBXes into sequential NLA)
# ============================================================================

def setup_scene(config=None):
    """
    Import all FBX files into sequential NLA on one armature.
    WARNING: Calls read_factory_settings — kills MCP connection.
    For MCP, use init_from_scene() with an existing .blend instead.
    """
    if config is None:
        config = _state['config']
    if config is None:
        raise ValueError("No config loaded. Call load_config() first.")

    bpy.ops.wm.read_factory_settings(use_empty=True)

    animations = config['animations']
    scene = bpy.context.scene
    armature = None
    current_frame = 1

    for ai, anim in enumerate(animations):
        fbx_path = os.path.join(ANIMATIONS_DIR, anim['fbx'])
        if not os.path.exists(fbx_path):
            raise FileNotFoundError(f"Animation FBX not found: {fbx_path}")

        print(f"\nImporting {anim['name']} from {anim['fbx']}...")
        bpy.ops.import_scene.fbx(filepath=fbx_path)

        for obj in list(bpy.data.objects):
            if obj.type == 'EMPTY':
                bpy.data.objects.remove(obj, do_unlink=True)

        if ai == 0:
            for obj in bpy.data.objects:
                if obj.type == 'ARMATURE':
                    armature = obj
                    break
            if armature is None:
                raise RuntimeError("No armature found after FBX import")

            action = armature.animation_data.action
            action.name = anim['name']
            action_end = int(action.frame_range[1])

            for slot in action.slots:
                slot.identifier = "OB" + armature.name

            track = armature.animation_data.nla_tracks.new()
            track.name = anim['name']
            strip = track.strips.new(anim['name'], current_frame, action)
            strip.frame_start = current_frame
            strip.frame_end = current_frame + action_end - 1
            strip.extrapolation = 'NOTHING'
            if anim.get('reversed', False):
                strip.use_reverse = True

            print(f"  NLA: {anim['name']} frames {strip.frame_start}-{strip.frame_end}")
            current_frame = int(strip.frame_end) + 1
            armature.animation_data.action = None
        else:
            new_arm = None
            for obj in bpy.data.objects:
                if obj.type == 'ARMATURE' and obj != armature:
                    new_arm = obj
                    break

            if new_arm and new_arm.animation_data and new_arm.animation_data.action:
                action = new_arm.animation_data.action
                action.name = anim['name']
                action_end = int(action.frame_range[1])

                for slot in action.slots:
                    slot.identifier = "OB" + armature.name

                if armature.animation_data is None:
                    armature.animation_data_create()
                track = armature.animation_data.nla_tracks.new()
                track.name = anim['name']
                strip = track.strips.new(anim['name'], current_frame, action)
                strip.frame_start = current_frame
                strip.frame_end = current_frame + action_end - 1
                strip.extrapolation = 'NOTHING'
                if anim.get('reversed', False):
                    strip.use_reverse = True

                print(f"  NLA: {anim['name']} frames {strip.frame_start}-{strip.frame_end}")
                current_frame = int(strip.frame_end) + 1

            for obj in list(bpy.data.objects):
                if obj.type == 'ARMATURE' and obj != armature:
                    bpy.data.objects.remove(obj, do_unlink=True)
            for obj in list(bpy.data.objects):
                if obj.type == 'MESH' and obj.name.endswith('.001'):
                    bpy.data.objects.remove(obj, do_unlink=True)

    if armature.animation_data:
        armature.animation_data.action = None

    _state['armature'] = armature
    _state['meshes'] = [c for c in armature.children if c.type == 'MESH']

    for obj in _state['meshes']:
        if obj.data.shape_keys:
            keys = [k.name for k in obj.data.shape_keys.key_blocks]
            if 'Fcl_ALL_Surprised' in keys:
                _state['face_obj'] = obj
                break

    # Save original strip positions
    _save_strip_positions()

    # Setup lighting and render
    _setup_lighting()
    _setup_render_settings()

    print(f"\n--- NLA Summary ---")
    for track in armature.animation_data.nla_tracks:
        for strip in track.strips:
            print(f"  {track.name}: frames {strip.frame_start}-{strip.frame_end}")
    print(f"Face mesh: {_state['face_obj'].name if _state['face_obj'] else 'None'}")

    return armature


def init_from_scene():
    """
    Initialize _state from an existing Blender scene (MCP-safe).
    Use this when loading from a .blend file instead of setup_scene().
    """
    arm = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            arm = obj
            break
    if arm is None:
        raise RuntimeError("No armature found in scene")

    _state['armature'] = arm
    _state['meshes'] = [c for c in arm.children if c.type == 'MESH']
    _state['face_obj'] = None

    for obj in _state['meshes']:
        if obj.data.shape_keys:
            keys = [k.name for k in obj.data.shape_keys.key_blocks]
            if 'Fcl_ALL_Surprised' in keys:
                _state['face_obj'] = obj
                break

    _save_strip_positions()

    print(f"Initialized from scene: armature={arm.name}")
    print(f"  Meshes: {[m.name for m in _state['meshes']]}")
    print(f"  Face: {_state['face_obj'].name if _state['face_obj'] else 'None'}")
    for track in arm.animation_data.nla_tracks:
        if track.name == 'SpringBoneHair':
            continue
        for strip in track.strips:
            print(f"  NLA: {track.name} frames {strip.frame_start}-{strip.frame_end}")


def _save_strip_positions():
    """Save original NLA strip positions for restore after shifting."""
    arm = _state['armature']
    _state['strip_positions'] = {}
    for track in arm.animation_data.nla_tracks:
        if track.name == 'SpringBoneHair':
            continue
        for strip in track.strips:
            _state['strip_positions'][track.name] = (
                strip.frame_start, strip.frame_end
            )


# ============================================================================
# Lighting & render settings
# ============================================================================

def _setup_lighting():
    """Set up 3-sun lighting (no shadows)."""
    for name, energy, rot in [
        ("Key", 4.0, (30, 0, -20)),
        ("Fill", 2.5, (40, 0, 160)),
        ("Rim", 1.5, (60, 0, 180)),
    ]:
        light = bpy.data.lights.new(f"Sun_{name}", 'SUN')
        light.energy = energy
        light.use_shadow = False
        obj = bpy.data.objects.new(f"Sun_{name}", light)
        bpy.context.scene.collection.objects.link(obj)
        obj.rotation_euler = tuple(math.radians(a) for a in rot)

    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs['Specular IOR Level'].default_value = 0.0
                node.inputs['Roughness'].default_value = 1.0

    print("Lighting: 3 suns, no shadows, specular killed")


def _setup_render_settings():
    """Configure EEVEE render, white background, Freestyle outline."""
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'

    world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
        bg.inputs['Strength'].default_value = 1.0

    scene.render.use_freestyle = True
    vl = scene.view_layers[0]
    vl.use_freestyle = True
    vl.freestyle_settings.sphere_radius = 0

    if vl.freestyle_settings.linesets:
        ls = vl.freestyle_settings.linesets[0]
    else:
        ls = vl.freestyle_settings.linesets.new("OutlineSet")
    ls.select_silhouette = False
    ls.select_border = False
    ls.select_contour = False
    ls.select_crease = False
    ls.select_edge_mark = False
    ls.select_external_contour = True
    ls.select_material_boundary = False
    ls.select_suggestive_contour = False
    ls.select_ridge_valley = False
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("LineStyle")
    ls.linestyle.color = (0, 0, 0)
    ls.linestyle.thickness = 1.0

    print("Render: EEVEE 256x256, Standard, white BG, Freestyle 1px")


# ============================================================================
# Camera
# ============================================================================

def _setup_camera(end_frame, global_bounds=False):
    """Create orthographic camera with per-frame bounding box keyframes."""
    scene = bpy.context.scene
    meshes = _state['meshes']

    # Delete old camera
    for obj in list(bpy.data.objects):
        if obj.type == 'CAMERA':
            bpy.data.objects.remove(obj, do_unlink=True)

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = 'ORTHO'
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    cam_obj.rotation_euler = CAM_ROTATION

    t = time.time()

    if global_bounds:
        g_min_z, g_max_z = float('inf'), float('-inf')
        g_min_y, g_max_y = float('inf'), float('-inf')
        frame_y_centers = {}

        for f in range(1, end_frame + 1):
            scene.frame_set(f)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            min_y, max_y = float('inf'), float('-inf')
            min_z, max_z = float('inf'), float('-inf')
            for mesh_obj in meshes:
                eval_obj = mesh_obj.evaluated_get(depsgraph)
                mesh_data = eval_obj.to_mesh()
                for v in mesh_data.vertices:
                    world_co = eval_obj.matrix_world @ v.co
                    min_y = min(min_y, world_co.y)
                    max_y = max(max_y, world_co.y)
                    min_z = min(min_z, world_co.z)
                    max_z = max(max_z, world_co.z)
                eval_obj.to_mesh_clear()
            frame_y_centers[f] = (min_y + max_y) / 2
            g_min_z = min(g_min_z, min_z)
            g_max_z = max(g_max_z, max_z)
            g_min_y = min(g_min_y, min_y)
            g_max_y = max(g_max_y, max_y)

        center_z = (g_min_z + g_max_z) / 2
        ortho_scale = max(g_max_y - g_min_y, g_max_z - g_min_z) * CAM_PADDING
        cam_obj.data.ortho_scale = ortho_scale
        for f, cy in frame_y_centers.items():
            cam_obj.location = (CAM_DEPTH, cy, center_z)
            cam_obj.keyframe_insert(data_path='location', frame=f)
    else:
        for f in range(1, end_frame + 1):
            scene.frame_set(f)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            min_y, max_y = float('inf'), float('-inf')
            min_z, max_z = float('inf'), float('-inf')
            for mesh_obj in meshes:
                eval_obj = mesh_obj.evaluated_get(depsgraph)
                mesh_data = eval_obj.to_mesh()
                for v in mesh_data.vertices:
                    world_co = eval_obj.matrix_world @ v.co
                    min_y = min(min_y, world_co.y)
                    max_y = max(max_y, world_co.y)
                    min_z = min(min_z, world_co.z)
                    max_z = max(max_z, world_co.z)
                eval_obj.to_mesh_clear()
            center_y = (min_y + max_y) / 2
            center_z = (min_z + max_z) / 2
            ortho_scale = max(max_y - min_y, max_z - min_z) * CAM_PADDING
            cam_obj.location = (CAM_DEPTH, center_y, center_z)
            cam_obj.data.ortho_scale = ortho_scale
            cam_obj.keyframe_insert(data_path='location', frame=f)
            cam_obj.data.keyframe_insert(data_path='ortho_scale', frame=f)

    print(f"  Camera: {end_frame} frames in {time.time()-t:.1f}s")


# ============================================================================
# Spring bones
# ============================================================================

def _find_hair_chains(arm_obj):
    """Find all secondary hair bone chains starting from J_Sec_Hair1_*."""
    chains = []
    for bone in arm_obj.data.bones:
        if bone.name.startswith('J_Sec_Hair1_'):
            chain = []
            current = bone
            while current:
                chain.append(current.name)
                children = [c for c in current.children if 'Sec_Hair' in c.name]
                current = children[0] if children else None
            chains.append(chain)
    return chains


def _remove_spring_bones():
    """Remove existing SpringBoneHair NLA track and action."""
    arm = _state['armature']
    for track in list(arm.animation_data.nla_tracks):
        if track.name == 'SpringBoneHair':
            arm.animation_data.nla_tracks.remove(track)
    if arm.animation_data.action:
        arm.animation_data.action = None


def _run_spring_bones(end_frame):
    """Run spring bone simulation for frames 1 to end_frame with fresh state."""
    arm = _state['armature']
    chains = _find_hair_chains(arm)
    if not chains:
        print("  Spring bones: skipped (no hair chains)")
        return

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')

    head_quats = []
    for frame in range(1, end_frame + 1):
        bpy.context.scene.frame_set(frame)
        head_pbone = arm.pose.bones.get('J_Bip_C_Head')
        if head_pbone is None:
            print("  Spring bones: skipped (no J_Bip_C_Head)")
            bpy.ops.object.mode_set(mode='OBJECT')
            return
        world_mat = arm.matrix_world @ head_pbone.matrix
        head_quats.append(world_mat.to_quaternion())

    state = {}
    for chain in chains:
        for bone_name in chain:
            state[bone_name] = {'ox': 0.0, 'oz': 0.0, 'vx': 0.0, 'vz': 0.0}

    max_rad = math.radians(SPRING_MAX_DEG)
    prev_quat = head_quats[0]
    t = time.time()

    for fi in range(len(head_quats)):
        frame = fi + 1
        bpy.context.scene.frame_set(frame)
        cur_quat = head_quats[fi]
        delta = prev_quat.inverted() @ cur_quat
        delta_euler = delta.to_euler()
        prev_quat = cur_quat

        for chain in chains:
            for ci, bone_name in enumerate(chain):
                pbone = arm.pose.bones[bone_name]
                s = state[bone_name]
                cf = (ci + 1) / len(chain)
                fx = -delta_euler.x * SPRING_REACTION * cf + -s['ox'] * SPRING_STIFFNESS
                fz = -delta_euler.z * SPRING_REACTION * cf + -s['oz'] * SPRING_STIFFNESS
                s['vx'] = s['vx'] * (1.0 - SPRING_DAMPING) + fx
                s['vz'] = s['vz'] * (1.0 - SPRING_DAMPING) + fz
                s['ox'] += s['vx']
                s['oz'] += s['vz']
                limit = max_rad * cf
                s['ox'] = max(-limit, min(limit, s['ox']))
                s['oz'] = max(-limit, min(limit, s['oz']))
                pbone.rotation_mode = 'XYZ'
                pbone.rotation_euler = (s['ox'], 0.0, s['oz'])
                pbone.keyframe_insert(data_path='rotation_euler', frame=frame)

    bpy.ops.object.mode_set(mode='OBJECT')

    if arm.animation_data and arm.animation_data.action:
        action = arm.animation_data.action
        action.name = 'SpringBoneHairAction'
        track = arm.animation_data.nla_tracks.new()
        track.name = 'SpringBoneHair'
        strip = track.strips.new('SpringBoneHair', 1, action)
        strip.frame_start = 1
        strip.frame_end = end_frame
        strip.blend_type = 'ADD'
        arm.animation_data.action = None

    print(f"  Spring bones: {len(chains)} chains, {end_frame}f in {time.time()-t:.1f}s")


# ============================================================================
# Frame selection (action frames = scene frames when strip is at frame 1)
# ============================================================================

def _sample_frames(start, end, count):
    """Pick count evenly-spaced frames from [start, end] inclusive."""
    if count == 1:
        return [round((start + end) / 2)]
    step = (end - start) / (count - 1)
    return [round(start + i * step) for i in range(count)]


def _select_anim_frames(anim, action_end, reversed=False):
    """Select frames for one animation. Returns (frames, expr_map)."""
    frames = []
    expr_map = {}

    if 'segments' in anim:
        for seg in anim['segments']:
            a_start = seg['action_frames'][0]
            a_end = seg['action_frames'][1]
            pick = seg.get('pick', 1)
            expression = seg.get('expression', None)

            if reversed:
                s_start = action_end - a_end + 1
                s_end = action_end - a_start + 1
            else:
                s_start = a_start
                s_end = a_end

            picked = _sample_frames(s_start, s_end, pick)
            for f in picked:
                frames.append(f)
                expr_map[f] = expression
    else:
        frames = _sample_frames(1, action_end, anim['frames'])
        expr_map = {f: None for f in frames}

    return frames, expr_map


# ============================================================================
# Expression helpers
# ============================================================================

def _set_expression(expression_name):
    """Set facial expression via shape keys."""
    face = _state['face_obj']
    if face is None or face.data.shape_keys is None:
        return
    sk = face.data.shape_keys.key_blocks
    for key in sk:
        if key.name.startswith('Fcl_ALL_') or key.name.startswith('Fcl_MTH_'):
            key.value = 0.0
    if expression_name is None:
        return
    expr_keys = {
        'surprised': ['Fcl_ALL_Surprised', 'Fcl_MTH_Surprised'],
        'angry': ['Fcl_ALL_Angry', 'Fcl_MTH_Angry'],
        'fun': ['Fcl_ALL_Fun', 'Fcl_MTH_Fun'],
        'sorrow': ['Fcl_ALL_Sorrow', 'Fcl_MTH_Sorrow'],
        'joy': ['Fcl_ALL_Joy', 'Fcl_MTH_Joy'],
    }
    for key_name in expr_keys.get(expression_name, []):
        if key_name in sk:
            sk[key_name].value = 1.0


# ============================================================================
# Per-animation render
# ============================================================================

def render_animation(anim_index):
    """
    Render one animation by muting others and shifting its strip to frame 1.
    The character stays on the same armature (imported once via setup_scene).
    Spring bones run fresh per animation. Action frames = scene frames.

    Call sequentially: render_animation(0), render_animation(1), ...
    Each call is self-contained (re-exec safe for MCP).
    """
    config = _state['config']
    if config is None:
        raise ValueError("No config loaded. Call load_config() first.")

    arm = _state['armature']
    if arm is None:
        raise ValueError("No armature. Call setup_scene() or init_from_scene() first.")

    anim = config['animations'][anim_index]
    reversed = anim.get('reversed', False)

    # Compute frame cursor from previous animations
    cursor = sum(a['frames'] for a in config['animations'][:anim_index])

    print(f"\n{'='*50}")
    print(f"Animation {anim_index}: {anim['name']}")
    print(f"  Sprite frames {cursor+1}-{cursor+anim['frames']}")
    print(f"{'='*50}")

    # Clean output dir on first animation
    out_dir = _state['out_dir']
    os.makedirs(out_dir, exist_ok=True)
    if anim_index == 0:
        for f in os.listdir(out_dir):
            if f.startswith('frame_') and f.endswith('.png'):
                os.remove(os.path.join(out_dir, f))

    # --- Mute all tracks except this one ---
    target_track = None
    for track in arm.animation_data.nla_tracks:
        if track.name == 'SpringBoneHair':
            continue
        if track.name == anim['name']:
            track.mute = False
            target_track = track
        else:
            track.mute = True

    if target_track is None:
        raise RuntimeError(f"NLA track '{anim['name']}' not found")

    # --- Remove old spring bones ---
    _remove_spring_bones()

    # --- Shift strip to frame 1 ---
    strip = target_track.strips[0]
    orig_start = strip.frame_start
    orig_end = strip.frame_end
    duration = orig_end - orig_start
    strip.frame_start = 1
    strip.frame_end = 1 + duration
    action_end = int(strip.frame_end)

    print(f"  Shifted {anim['name']}: {orig_start}-{orig_end} -> 1-{action_end}")

    # --- Set scene range ---
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = action_end

    # --- Camera ---
    _setup_camera(action_end, global_bounds=config.get('global_camera', False))

    # --- Spring bones (fresh) ---
    _run_spring_bones(action_end)

    # --- Select frames ---
    frames, expr_map = _select_anim_frames(anim, action_end, reversed=reversed)
    print(f"  Frames: {frames}")

    # --- Render ---
    scene = bpy.context.scene
    for i, frame in enumerate(frames):
        idx = cursor + i
        scene.frame_set(frame)
        expression = expr_map.get(frame)
        _set_expression(expression)

        fname = f"frame_{idx+1:02d}_{frame:03d}.png"
        scene.render.filepath = os.path.join(out_dir, fname)
        bpy.ops.render.render(write_still=True)

        expr_str = f" [{expression}]" if expression else ""
        print(f"    {fname}{expr_str}")

    # --- Restore strip position ---
    strip.frame_start = orig_start
    strip.frame_end = orig_end

    # --- Unmute all ---
    for track in arm.animation_data.nla_tracks:
        track.mute = False

    # --- Remove spring bones (will be wrong after restore) ---
    _remove_spring_bones()

    print(f"  Done ({anim['frames']} frames, strip restored to {orig_start}-{orig_end})")


# ============================================================================
# Assembly
# ============================================================================

def assemble_sheet(output_path=None):
    """Assemble 16 rendered frames into a 1024x1024 sprite sheet."""
    if output_path is None:
        output_path = _state['sheet_path']

    out_dir = _state['out_dir']
    frame_files = sorted([f for f in os.listdir(out_dir)
                         if f.startswith('frame_') and f.endswith('.png')])

    if len(frame_files) != 16:
        print(f"WARNING: Expected 16 frames, found {len(frame_files)}")

    print(f"Assembling {len(frame_files)} frames into sprite sheet...")

    images = []
    for fname in frame_files:
        img = bpy.data.images.load(os.path.join(out_dir, fname))
        images.append(img)

    sheet = bpy.data.images.new('sprite_sheet', 1024, 1024, alpha=True)
    pixels = [0.0] * (1024 * 1024 * 4)

    for idx, img in enumerate(images):
        row = idx // 4
        col = idx % 4
        x_start = col * 256
        y_start = 1024 - (row + 1) * 256

        frame_pixels = list(img.pixels)
        for py in range(256):
            for px in range(256):
                src = (py * 256 + px) * 4
                dst_x = x_start + px
                dst_y = y_start + py
                dst = (dst_y * 1024 + dst_x) * 4
                pixels[dst] = frame_pixels[src]
                pixels[dst + 1] = frame_pixels[src + 1]
                pixels[dst + 2] = frame_pixels[src + 2]
                pixels[dst + 3] = frame_pixels[src + 3]

    sheet.pixels = pixels
    sheet.filepath_raw = output_path
    sheet.file_format = 'PNG'
    sheet.save()

    for img in images:
        bpy.data.images.remove(img)
    bpy.data.images.remove(sheet)

    size = os.path.getsize(output_path)
    print(f"Sprite sheet saved: {output_path} ({size//1024}KB)")


def create_gif(output_path=None, delay=10):
    """Create an animated GIF from the 16 rendered frames."""
    if output_path is None:
        output_path = _state['gif_path']

    out_dir = _state['out_dir']
    frame_files = sorted([f for f in os.listdir(out_dir)
                         if f.startswith('frame_') and f.endswith('.png')])

    frames_data = []
    for fname in frame_files:
        img = bpy.data.images.load(os.path.join(out_dir, fname))
        w, h = img.size[0], img.size[1]
        pix = list(img.pixels)
        rgb = []
        for y in range(h - 1, -1, -1):
            for x in range(w):
                idx = (y * w + x) * 4
                rgb.append((int(pix[idx] * 255),
                           int(pix[idx + 1] * 255),
                           int(pix[idx + 2] * 255)))
        frames_data.append((w, h, rgb))
        bpy.data.images.remove(img)

    import random
    random.seed(42)
    all_colors = set()
    for w, h, rgb in frames_data:
        sample = random.sample(rgb, min(5000, len(rgb)))
        all_colors.update(sample)

    colors_list = list(all_colors)
    random.shuffle(colors_list)
    palette = colors_list[:255]
    palette.append((255, 255, 255))

    def closest_color(r, g, b):
        best = 0
        best_dist = float('inf')
        for i, (pr, pg, pb) in enumerate(palette):
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_dist:
                best_dist = d
                best = i
                if d == 0:
                    break
        return best

    with open(output_path, 'wb') as f:
        w, h = frames_data[0][0], frames_data[0][1]
        f.write(b'GIF89a')
        f.write(struct.pack('<HH', w, h))
        f.write(bytes([0xF7, 0x00, 0x00]))

        for r, g, b in palette:
            f.write(bytes([r, g, b]))

        f.write(bytes([0x21, 0xFF, 0x0B]))
        f.write(b'NETSCAPE2.0')
        f.write(bytes([0x03, 0x01, 0x00, 0x00, 0x00]))

        for fi, (fw, fh, rgb) in enumerate(frames_data):
            f.write(bytes([0x21, 0xF9, 0x04, 0x00]))
            f.write(struct.pack('<H', delay))
            f.write(bytes([0x00, 0x00]))

            f.write(bytes([0x2C]))
            f.write(struct.pack('<HHHH', 0, 0, fw, fh))
            f.write(bytes([0x00]))

            min_code_size = 8
            f.write(bytes([min_code_size]))
            clear_code = 1 << min_code_size
            eoi_code = clear_code + 1

            indices = [closest_color(r, g, b) for r, g, b in rgb]

            class BitWriter:
                def __init__(self):
                    self.buf = bytearray()
                    self.bits = 0
                    self.nbits = 0
                def write(self, value, nbits):
                    self.bits |= (value << self.nbits)
                    self.nbits += nbits
                    while self.nbits >= 8:
                        self.buf.append(self.bits & 0xFF)
                        self.bits >>= 8
                        self.nbits -= 8
                def flush(self):
                    if self.nbits > 0:
                        self.buf.append(self.bits & 0xFF)
                    return bytes(self.buf)

            bw = BitWriter()
            code_size = min_code_size + 1
            next_code = eoi_code + 1
            table = {}
            bw.write(clear_code, code_size)

            if indices:
                prefix = indices[0]
                for pixel in indices[1:]:
                    key = (prefix, pixel)
                    if key in table:
                        prefix = table[key]
                    else:
                        bw.write(prefix, code_size)
                        if next_code < 4096:
                            table[key] = next_code
                            next_code += 1
                            if next_code > (1 << code_size) and code_size < 12:
                                code_size += 1
                        else:
                            bw.write(clear_code, code_size)
                            table = {}
                            code_size = min_code_size + 1
                            next_code = eoi_code + 1
                        prefix = pixel
                bw.write(prefix, code_size)

            bw.write(eoi_code, code_size)
            compressed = bw.flush()

            pos = 0
            while pos < len(compressed):
                chunk = compressed[pos:pos + 255]
                f.write(bytes([len(chunk)]))
                f.write(chunk)
                pos += 255
            f.write(bytes([0x00]))

        f.write(bytes([0x3B]))

    size = os.path.getsize(output_path)
    print(f"GIF saved: {output_path} ({size // 1024}KB)")


# ============================================================================
# Save scene
# ============================================================================

def save_scene(filepath=None):
    """Save the Blender scene file."""
    if filepath is None:
        filepath = _state['scene_path']
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=filepath)
    print(f"Scene saved: {filepath}")


# ============================================================================
# Full pipeline (CLI)
# ============================================================================

def run_full_pipeline(config_path):
    """Run the complete pipeline from config to finished sprite sheet."""
    print("=" * 60)
    print("SPRITE SHEET RENDER PIPELINE (Per-Animation)")
    print("=" * 60)

    config = load_config(config_path)
    setup_scene(config)

    for i in range(len(config['animations'])):
        render_animation(i)

    assemble_sheet()
    create_gif()
    save_scene()

    # Update config with selected frames
    out_dir = _state['out_dir']
    frame_files = sorted([f for f in os.listdir(out_dir)
                         if f.startswith('frame_') and f.endswith('.png')])
    selected = []
    for fname in frame_files:
        parts = fname.replace('.png', '').split('_')
        selected.append(int(parts[2]))
    config['selected_frames'] = selected
    with open(_state['config_path'], 'w') as f:
        json.dump(config, f, indent=4)
    print(f"Config updated with selected_frames: {selected}")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"  Sprite sheet: {_state['sheet_path']}")
    print(f"  GIF: {_state['gif_path']}")
    print(f"  Scene: {_state['scene_path']}")
    print("=" * 60)


# ============================================================================
# CLI entry point
# ============================================================================

if __name__ == "__main__":
    import sys
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
        if args:
            run_full_pipeline(os.path.abspath(args[0]))
        else:
            print("Usage: blender --background --python render_sheet_indv.py -- config.json")
    else:
        print("render_sheet_indv.py loaded. Call functions manually via MCP.")
        print("  load_config(path) -> init_from_scene() -> render_animation(0) -> ...")
