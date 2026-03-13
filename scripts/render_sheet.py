"""
Sprite Sheet Render Pipeline
=============================
Automated pipeline to render a sprite sheet from a config JSON.

Usage via Blender CLI:
    blender --background --python scripts/render_sheet.py -- data/configs/sheet_XX.json

Usage via Blender MCP (step by step, fresh scene):
    exec(open(r"C:\dev\loracomp3\scripts\render_sheet.py").read())
    config = load_config(r"C:\dev\loracomp3\data\configs\sheet_06_roundhousekick_illegalknee.json")
    setup_scene(config)
    setup_lighting()
    setup_render_settings()
    setup_camera()          # Must be before spring bones
    run_spring_bones()      # VRoid characters only
    frames, expr_map = select_frames(config)
    render_batch(frames, expr_map, 0, 4)   # Render in batches of 4
    render_batch(frames, expr_map, 4, 8)
    render_batch(frames, expr_map, 8, 12)
    render_batch(frames, expr_map, 12, 16)
    assemble_sheet()
    create_gif()
    save_scene()

Usage via Blender MCP (from pre-configured .blend file):
    exec(open(r"C:\dev\loracomp3\scripts\render_sheet.py").read())
    render_from_scene(
        r"C:\dev\loracomp3\data\configs\sheet_08_fall_getup.json",
        r"C:\dev\loracomp3\data\scenes\sheet_08_fall_getup.blend",
    )

CRITICAL GOTCHAS:
- Camera rotation MUST be (pi/2, 0, -pi/2) for +X facing. (pi/2, 0, +pi/2) renders BLANK.
- Delete ALL empties after every FBX import (Freestyle crash).
- Blender 5.0 engine is 'BLENDER_EEVEE' not 'BLENDER_EEVEE_NEXT'.
- Render in batches of 4 frames max via MCP to avoid timeout.
- Mma Kick.fbx crashes Freestyle — avoid entirely.
"""

import bpy
import os
import math
import time
import json
import struct


# ============================================================================
# Global state (set by setup_scene)
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
    'scene_start': 1,
    'scene_end': 1,
    'selected_frames': [],
    'expression_map': {},
}

# Paths
BASE_DIR = r"C:\dev\loracomp3"
ANIMATIONS_DIR = os.path.join(BASE_DIR, "data", "animations")
CONFIGS_DIR = os.path.join(BASE_DIR, "data", "configs")
RENDERS_DIR = os.path.join(BASE_DIR, "data", "renders")
SCENES_DIR = os.path.join(BASE_DIR, "data", "scenes")

# Camera settings
CAM_DEPTH = -2.4          # Camera X position (negative, looking along +X)
CAM_PADDING = 1.15        # 15% padding around character bounding box
CAM_ROTATION = (math.pi / 2, 0, -math.pi / 2)  # CRITICAL: must be -pi/2 for +X

# Spring bone defaults
SPRING_STIFFNESS = 0.3
SPRING_DAMPING = 0.2
SPRING_REACTION = 2.0
SPRING_MAX_DEG = 45.0

# NLA gap between strips
NLA_GAP = 0


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
    name = config['name'].lower().replace(' ', '_').replace('+', '').replace('  ', '_')
    # Derive file names from config filename
    config_basename = os.path.splitext(os.path.basename(config_path))[0]
    sheet_slug = config_basename.replace('sheet_%02d_' % idx, '')

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
# Scene setup
# ============================================================================

def setup_scene(config=None):
    """
    Set up the Blender scene: import FBX files, arrange NLA strips.

    Args:
        config: Config dict (if None, uses previously loaded config)
    """
    if config is None:
        config = _state['config']
    if config is None:
        raise ValueError("No config loaded. Call load_config() first.")

    # Start fresh
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

        # CRITICAL: Delete ALL empties (prevents Freestyle crash)
        for obj in list(bpy.data.objects):
            if obj.type == 'EMPTY':
                bpy.data.objects.remove(obj, do_unlink=True)

        if ai == 0:
            # First import — keep armature and meshes
            armature = None
            for obj in bpy.data.objects:
                if obj.type == 'ARMATURE':
                    armature = obj
                    break
            if armature is None:
                raise RuntimeError("No armature found after FBX import")

            # Get the action from this import
            action = armature.animation_data.action
            action.name = anim['name']
            action_end = int(action.frame_range[1])

            # Fix slot identifier (Blender 5.0)
            for slot in action.slots:
                slot.identifier = "OB" + armature.name

            # Push to NLA
            track = armature.animation_data.nla_tracks.new()
            track.name = anim['name']
            strip = track.strips.new(anim['name'], current_frame, action)
            strip.frame_start = current_frame
            strip.frame_end = current_frame + action_end - 1
            strip.extrapolation = 'NOTHING'

            if anim.get('reversed', False):
                strip.use_reverse = True

            print(f"  NLA: {anim['name']} frames {strip.frame_start}-{strip.frame_end}")
            current_frame = int(strip.frame_end) + NLA_GAP + 1

            # Clear active action
            armature.animation_data.action = None

        else:
            # Subsequent imports — extract action, delete duplicates
            # Find the new armature (usually Armature.001)
            new_arm = None
            for obj in bpy.data.objects:
                if obj.type == 'ARMATURE' and obj != armature:
                    new_arm = obj
                    break

            if new_arm and new_arm.animation_data and new_arm.animation_data.action:
                action = new_arm.animation_data.action
                action.name = anim['name']
                action_end = int(action.frame_range[1])

                # Fix slot — point to original armature
                for slot in action.slots:
                    slot.identifier = "OB" + armature.name

                # Push to NLA on original armature
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
                current_frame = int(strip.frame_end) + NLA_GAP + 1

            # Delete ALL duplicate objects from second import
            for obj in list(bpy.data.objects):
                if obj.type == 'ARMATURE' and obj != armature:
                    bpy.data.objects.remove(obj, do_unlink=True)
            # Delete duplicate meshes (Body.001, Face.001, Hair.001, etc.)
            for obj in list(bpy.data.objects):
                if obj.type == 'MESH' and obj.name.endswith('.001'):
                    bpy.data.objects.remove(obj, do_unlink=True)

    # Clear any remaining active action
    if armature.animation_data:
        armature.animation_data.action = None

    # Set scene range
    scene_end = current_frame - NLA_GAP - 1
    scene.frame_start = 1
    scene.frame_end = scene_end

    # Store state
    _state['armature'] = armature
    _state['meshes'] = [c for c in armature.children if c.type == 'MESH']
    _state['scene_start'] = 1
    _state['scene_end'] = scene_end

    # Find Face mesh (for expressions)
    for obj in _state['meshes']:
        if obj.data.shape_keys:
            keys = [k.name for k in obj.data.shape_keys.key_blocks]
            if 'Fcl_ALL_Surprised' in keys:
                _state['face_obj'] = obj
                break

    # Print NLA summary
    print(f"\n--- NLA Summary ---")
    for track in armature.animation_data.nla_tracks:
        for strip in track.strips:
            print(f"  {track.name}: frames {strip.frame_start}-{strip.frame_end} "
                  f"(action {strip.action_frame_start}-{strip.action_frame_end})")
    print(f"Scene range: {scene.frame_start}-{scene.frame_end}")
    print(f"Face mesh: {_state['face_obj'].name if _state['face_obj'] else 'None'}")

    return armature


# ============================================================================
# Lighting
# ============================================================================

def setup_lighting():
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

    # Kill specular on all materials
    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs['Specular IOR Level'].default_value = 0.0
                node.inputs['Roughness'].default_value = 1.0

    print("Lighting: 3 suns, no shadows, specular killed")


# ============================================================================
# Render settings
# ============================================================================

def setup_render_settings():
    """Configure EEVEE render, white background, Freestyle outline."""
    scene = bpy.context.scene

    # Engine
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'

    # Color management — Standard for pure white
    scene.view_settings.view_transform = 'Standard'

    # White background
    world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
        bg.inputs['Strength'].default_value = 1.0

    # Freestyle outline (1px black, external contour only)
    scene.render.use_freestyle = True
    vl = scene.view_layers[0]
    vl.use_freestyle = True
    vl.freestyle_settings.sphere_radius = 0  # CRITICAL: prevents crash

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

    print("Render settings: EEVEE 256x256, Standard, white BG, Freestyle 1px")


# ============================================================================
# Camera (ORTHO, direct bounding box method)
# ============================================================================

def setup_camera(global_bounds=False):
    """
    Create orthographic camera and bake per-frame keyframes using direct
    bounding box method.

    Args:
        global_bounds: If True, use a single bounding box across all frames
                       for consistent character size. Best for animations with
                       large pose changes (e.g., standing to lying down).
                       If False (default), bake per-frame for tighter framing.

    CRITICAL: Rotation must be (pi/2, 0, -pi/2). Using +pi/2 renders BLANK.
    """
    scene = bpy.context.scene
    arm = _state['armature']
    meshes = _state['meshes']

    if not meshes:
        raise RuntimeError("No meshes found. Run setup_scene() first.")

    # Create camera
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = 'ORTHO'
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # CRITICAL rotation
    cam_obj.rotation_euler = CAM_ROTATION

    t = time.time()

    if global_bounds:
        # Hybrid: per-frame Y centering + fixed Z + fixed scale
        # Ground stays in same place, character tracks horizontally only
        # NOTE: ortho_scale uses max per-frame Y span (character width),
        # NOT global Y range (travel distance), since camera tracks Y.
        g_min_z = float('inf')
        g_max_z = float('-inf')
        max_frame_y_span = 0
        frame_y_centers = {}

        for f in range(_state['scene_start'], _state['scene_end'] + 1):
            scene.frame_set(f)
            depsgraph = bpy.context.evaluated_depsgraph_get()

            min_y = float('inf')
            max_y = float('-inf')
            min_z = float('inf')
            max_z = float('-inf')

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
            max_frame_y_span = max(max_frame_y_span, max_y - min_y)
            g_min_z = min(g_min_z, min_z)
            g_max_z = max(g_max_z, max_z)

        center_z = (g_min_z + g_max_z) / 2
        span_z = g_max_z - g_min_z
        ortho_scale = max(max_frame_y_span, span_z) * CAM_PADDING
        cam_obj.data.ortho_scale = ortho_scale

        # Bake per-frame Y position, fixed Z
        for f, cy in frame_y_centers.items():
            cam_obj.location = (CAM_DEPTH, cy, center_z)
            cam_obj.keyframe_insert(data_path='location', frame=f)

        elapsed = time.time() - t
        print(f"Camera: ORTHO global (fixed Z + per-frame Y), {_state['scene_end']} frames in {elapsed:.1f}s")
        print(f"  ortho_scale={ortho_scale:.3f}, center_z={center_z:.3f}")
    else:
        # Bake per-frame keyframes
        for f in range(_state['scene_start'], _state['scene_end'] + 1):
            scene.frame_set(f)
            depsgraph = bpy.context.evaluated_depsgraph_get()

            min_y = float('inf')
            max_y = float('-inf')
            min_z = float('inf')
            max_z = float('-inf')

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

        elapsed = time.time() - t
        print(f"Camera: ORTHO per-frame, {_state['scene_end']} frames baked in {elapsed:.1f}s")

    print(f"  Depth={CAM_DEPTH}, Padding={CAM_PADDING}")


# ============================================================================
# Spring bone hair physics
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


def run_spring_bones(stiffness=SPRING_STIFFNESS, damping=SPRING_DAMPING,
                     reaction=SPRING_REACTION, max_deg=SPRING_MAX_DEG):
    """
    Run spring bone hair physics simulation and push to NLA.
    VRoid characters only (skips if no J_Sec_Hair* bones found).

    Must run AFTER setup_camera() — frustum clamp depends on camera position.
    """
    arm = _state['armature']
    end_frame = _state['scene_end']

    chains = _find_hair_chains(arm)
    if not chains:
        print("Spring bones: No hair chains found (Mixamo character?). Skipping.")
        return

    print(f"Spring bones: {len(chains)} hair chains, {end_frame} frames")

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')

    # Record head rotations
    head_quats = []
    for frame in range(1, end_frame + 1):
        bpy.context.scene.frame_set(frame)
        head_pbone = arm.pose.bones.get('J_Bip_C_Head')
        if head_pbone is None:
            print("  Warning: J_Bip_C_Head not found. Skipping spring bones.")
            bpy.ops.object.mode_set(mode='OBJECT')
            return
        world_mat = arm.matrix_world @ head_pbone.matrix
        head_quats.append(world_mat.to_quaternion())

    # Init state
    state = {}
    for chain in chains:
        for bone_name in chain:
            state[bone_name] = {'ox': 0.0, 'oz': 0.0, 'vx': 0.0, 'vz': 0.0}

    max_rad = math.radians(max_deg)
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

                fx = -delta_euler.x * reaction * cf
                fz = -delta_euler.z * reaction * cf
                fx += -s['ox'] * stiffness
                fz += -s['oz'] * stiffness

                s['vx'] = s['vx'] * (1.0 - damping) + fx
                s['vz'] = s['vz'] * (1.0 - damping) + fz
                s['ox'] += s['vx']
                s['oz'] += s['vz']

                limit = max_rad * cf
                s['ox'] = max(-limit, min(limit, s['ox']))
                s['oz'] = max(-limit, min(limit, s['oz']))

                pbone.rotation_mode = 'XYZ'
                pbone.rotation_euler = (s['ox'], 0.0, s['oz'])
                pbone.keyframe_insert(data_path='rotation_euler', frame=frame)

    bpy.ops.object.mode_set(mode='OBJECT')
    sim_time = time.time() - t
    print(f"  Simulation: {end_frame} frames in {sim_time:.1f}s")

    # Push to NLA
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
        print(f"  Pushed to NLA: SpringBoneHair (ADD blend)")


# ============================================================================
# Frame selection
# ============================================================================

def _sample_frames(start, end, count):
    """Pick count evenly-spaced frames from [start, end] inclusive."""
    if count == 1:
        return [round((start + end) / 2)]
    step = (end - start) / (count - 1)
    return [round(start + i * step) for i in range(count)]


def select_frames(config=None):
    """
    Compute selected frames and expression map from config segments.

    Returns:
        (frames, expression_map) where frames is a list of 16 scene frame numbers
        and expression_map is {frame: 'expression_name' or None}
    """
    if config is None:
        config = _state['config']

    arm = _state['armature']
    nla_tracks = arm.animation_data.nla_tracks

    all_frames = []
    expr_map = {}

    for anim in config['animations']:
        # Find the NLA track/strip for this animation
        track = nla_tracks.get(anim['name'])
        if track is None:
            raise RuntimeError(f"NLA track '{anim['name']}' not found")
        strip = track.strips[0]
        offset = strip.frame_start - strip.action_frame_start

        if 'segments' in anim:
            # Segment-based selection
            for seg in anim['segments']:
                action_start = seg['action_frames'][0]
                action_end = seg['action_frames'][1]
                scene_start = action_start + offset
                scene_end = action_end + offset
                pick = seg.get('pick', 1)
                expression = seg.get('expression', None)

                frames = _sample_frames(int(scene_start), int(scene_end), pick)
                for f in frames:
                    all_frames.append(f)
                    expr_map[f] = expression
        else:
            # Even spread across full action range
            scene_start = int(strip.frame_start)
            scene_end = int(strip.frame_end)
            frames = _sample_frames(scene_start, scene_end, anim['frames'])
            for f in frames:
                all_frames.append(f)
                expr_map[f] = None

    if len(all_frames) != 16:
        print(f"WARNING: Expected 16 frames, got {len(all_frames)}")

    _state['selected_frames'] = all_frames
    _state['expression_map'] = expr_map

    print(f"\n--- Frame Selection ({len(all_frames)} frames) ---")
    for i, f in enumerate(all_frames):
        expr = expr_map.get(f)
        expr_str = f" [{expr}]" if expr else ""
        print(f"  Frame {i+1:2d}: scene={f}{expr_str}")

    return all_frames, expr_map


# ============================================================================
# Expression helpers
# ============================================================================

def _set_expression(expression_name):
    """Set facial expression on the Face mesh via shape keys."""
    face = _state['face_obj']
    if face is None or face.data.shape_keys is None:
        return

    sk = face.data.shape_keys.key_blocks

    # Reset all expression keys
    for key in sk:
        if key.name.startswith('Fcl_ALL_') or key.name.startswith('Fcl_MTH_'):
            key.value = 0.0

    if expression_name is None:
        return

    # Map expression names to shape keys
    expr_keys = {
        'surprised': ['Fcl_ALL_Surprised', 'Fcl_MTH_Surprised'],
        'angry': ['Fcl_ALL_Angry', 'Fcl_MTH_Angry'],
        'fun': ['Fcl_ALL_Fun', 'Fcl_MTH_Fun'],
        'sorrow': ['Fcl_ALL_Sorrow', 'Fcl_MTH_Sorrow'],
        'joy': ['Fcl_ALL_Joy', 'Fcl_MTH_Joy'],
    }

    keys_to_set = expr_keys.get(expression_name, [])
    for key_name in keys_to_set:
        if key_name in sk:
            sk[key_name].value = 1.0


# ============================================================================
# Rendering
# ============================================================================

def render_batch(frames=None, expr_map=None, start=0, end=4):
    """
    Render a batch of frames. Call multiple times with different start/end
    to avoid MCP timeout (max 4 frames per batch recommended).

    Args:
        frames: List of all 16 scene frame numbers (default: _state['selected_frames'])
        expr_map: Dict of frame -> expression name (default: _state['expression_map'])
        start: Index into frames list (inclusive)
        end: Index into frames list (exclusive)
    """
    if frames is None:
        frames = _state['selected_frames']
    if expr_map is None:
        expr_map = _state['expression_map']

    out_dir = _state['out_dir']
    os.makedirs(out_dir, exist_ok=True)

    # Clean old frames on first batch
    if start == 0:
        for f in os.listdir(out_dir):
            if f.startswith('frame_') and f.endswith('.png'):
                os.remove(os.path.join(out_dir, f))

    scene = bpy.context.scene
    batch_frames = frames[start:end]

    for i, frame in enumerate(batch_frames):
        idx = start + i
        scene.frame_set(frame)

        # Set expression
        expression = expr_map.get(frame)
        _set_expression(expression)

        fname = f"frame_{idx+1:02d}_{frame:03d}.png"
        scene.render.filepath = os.path.join(out_dir, fname)
        bpy.ops.render.render(write_still=True)

        expr_str = f" [{expression}]" if expression else ""
        print(f"  Rendered {fname}{expr_str}")

    print(f"Batch {start//4 + 1} done (frames {start+1}-{end})")


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

    # Load frame images
    images = []
    for fname in frame_files:
        img = bpy.data.images.load(os.path.join(out_dir, fname))
        images.append(img)

    # Create 1024x1024 sheet
    sheet = bpy.data.images.new('sprite_sheet', 1024, 1024, alpha=True)
    pixels = [0.0] * (1024 * 1024 * 4)

    for idx, img in enumerate(images):
        row = idx // 4
        col = idx % 4
        x_start = col * 256
        y_start = 1024 - (row + 1) * 256  # Blender origin is bottom-left

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

    # Cleanup
    for img in images:
        bpy.data.images.remove(img)
    bpy.data.images.remove(sheet)

    size = os.path.getsize(output_path)
    print(f"Sprite sheet saved: {output_path} ({size//1024}KB)")


def create_gif(output_path=None, delay=10):
    """
    Create an animated GIF from the 16 rendered frames.

    Args:
        output_path: GIF file path (default: derived from config)
        delay: Frame delay in 1/100 seconds (default: 10 = 100ms)
    """
    if output_path is None:
        output_path = _state['gif_path']

    out_dir = _state['out_dir']
    frame_files = sorted([f for f in os.listdir(out_dir)
                         if f.startswith('frame_') and f.endswith('.png')])

    # Load frames
    frames_data = []
    for fname in frame_files:
        img = bpy.data.images.load(os.path.join(out_dir, fname))
        w, h = img.size[0], img.size[1]
        pix = list(img.pixels)

        # Convert to RGB bytes (flip vertically for GIF top-to-bottom)
        rgb = []
        for y in range(h - 1, -1, -1):
            for x in range(w):
                idx = (y * w + x) * 4
                rgb.append((int(pix[idx] * 255),
                           int(pix[idx + 1] * 255),
                           int(pix[idx + 2] * 255)))
        frames_data.append((w, h, rgb))
        bpy.data.images.remove(img)

    # Build palette from sampled colors
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

    # Write GIF
    with open(output_path, 'wb') as f:
        w, h = frames_data[0][0], frames_data[0][1]

        # Header
        f.write(b'GIF89a')
        f.write(struct.pack('<HH', w, h))
        f.write(bytes([0xF7, 0x00, 0x00]))

        # Global Color Table
        for r, g, b in palette:
            f.write(bytes([r, g, b]))

        # Netscape loop extension
        f.write(bytes([0x21, 0xFF, 0x0B]))
        f.write(b'NETSCAPE2.0')
        f.write(bytes([0x03, 0x01, 0x00, 0x00, 0x00]))

        for fi, (fw, fh, rgb) in enumerate(frames_data):
            # Graphic Control Extension
            f.write(bytes([0x21, 0xF9, 0x04, 0x00]))
            f.write(struct.pack('<H', delay))
            f.write(bytes([0x00, 0x00]))

            # Image Descriptor
            f.write(bytes([0x2C]))
            f.write(struct.pack('<HHHH', 0, 0, fw, fh))
            f.write(bytes([0x00]))

            # LZW
            min_code_size = 8
            f.write(bytes([min_code_size]))

            clear_code = 1 << min_code_size
            eoi_code = clear_code + 1

            # Quantize
            indices = [closest_color(r, g, b) for r, g, b in rgb]

            # LZW encode
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
# Render from pre-configured scene
# ============================================================================

def render_from_scene(config_path, blend_path=None):
    """
    Render sprite sheet from a pre-configured .blend file.

    Loads the .blend (preserving baked animation edits, armature orientation,
    etc.), optionally sets up hybrid camera, then renders.

    The .blend path can be passed as an argument or set in the config JSON
    as "scene": "filename.blend" (resolved relative to data/scenes/).

    Camera mode is read from config "camera" field:
      - "hybrid": Ground-anchored + horizontal centering (camera_hybrid.py).
                  Supports "camera_reference_frame" and "camera_ortho_scale".
      - absent/null: Uses whatever camera is already in the .blend file.

    Usage:
        exec(open(r"C:\\dev\\loracomp3\\scripts\\render_sheet.py").read())
        render_from_scene(r"C:\\dev\\loracomp3\\data\\configs\\sheet_08_fall_getup.json")
    """
    config = load_config(config_path)

    # Resolve .blend path
    if blend_path is None and config.get('scene'):
        blend_path = os.path.join(SCENES_DIR, config['scene'])

    if blend_path:
        load_scene(blend_path)

    # Camera setup from config
    camera_mode = config.get('camera')
    if camera_mode == 'hybrid':
        _setup_hybrid_camera(config)

    setup_render_settings()
    frames, expr_map = select_frames(config)

    for batch_start in range(0, len(frames), 4):
        batch_end = min(batch_start + 4, len(frames))
        render_batch(frames, expr_map, batch_start, batch_end)

    assemble_sheet()
    create_gif()

    config['selected_frames'] = frames
    with open(_state['config_path'], 'w') as f:
        json.dump(config, f, indent=4)
    print(f"Config updated with selected_frames")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE (from scene)")
    print(f"  Sprite sheet: {_state['sheet_path']}")
    print(f"  GIF: {_state['gif_path']}")
    print("=" * 60)


def _setup_hybrid_camera(config):
    """Set up hybrid camera from config settings."""
    import importlib.util
    hybrid_path = os.path.join(BASE_DIR, "scripts", "camera_hybrid.py")
    spec = importlib.util.spec_from_file_location("camera_hybrid", hybrid_path)
    camera_hybrid = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(camera_hybrid)

    ref_frame = config.get('camera_reference_frame')
    ortho_override = config.get('camera_ortho_scale')

    camera_hybrid.setup_camera_hybrid(
        _state,
        reference_frame=ref_frame,
        ortho_scale_override=ortho_override,
    )


def load_scene(blend_path):
    """
    Open a saved .blend file and populate _state from the existing scene.
    """
    bpy.ops.wm.open_mainfile(filepath=blend_path)

    scene = bpy.context.scene
    armature = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            armature = obj
            break

    if armature is None:
        raise RuntimeError(f"No armature found in {blend_path}")

    _state['armature'] = armature
    all_meshes = [c for c in armature.children if c.type == 'MESH']
    # Filter out tracker/helper meshes (e.g., HipTracker, FootTracker)
    _state['meshes'] = [m for m in all_meshes if 'Tracker' not in m.name]
    _state['scene_start'] = scene.frame_start
    _state['scene_end'] = scene.frame_end

    # Hide tracker meshes from render
    trackers = [m for m in all_meshes if 'Tracker' in m.name]
    for t in trackers:
        t.hide_render = True
        t.hide_viewport = True

    # Find Face mesh (for expressions)
    _state['face_obj'] = None
    for obj in _state['meshes']:
        if obj.data.shape_keys:
            keys = [k.name for k in obj.data.shape_keys.key_blocks]
            if 'Fcl_ALL_Surprised' in keys:
                _state['face_obj'] = obj
                break

    print(f"Loaded scene: {blend_path}")
    print(f"  Armature: {armature.name}")
    print(f"  Meshes: {[m.name for m in _state['meshes']]}")
    if trackers:
        print(f"  Hidden trackers: {[t.name for t in trackers]}")
    print(f"  Scene range: {scene.frame_start}-{scene.frame_end}")
    print(f"  Face mesh: {_state['face_obj'].name if _state['face_obj'] else 'None'}")


# ============================================================================
# Full pipeline (for CLI usage)
# ============================================================================

def run_full_pipeline(config_path):
    """Run the complete pipeline from config to finished sprite sheet."""
    print("=" * 60)
    print("SPRITE SHEET RENDER PIPELINE")
    print("=" * 60)

    config = load_config(config_path)
    setup_scene(config)
    setup_lighting()
    setup_render_settings()
    setup_camera(global_bounds=config.get('global_camera', False))
    run_spring_bones()
    frames, expr_map = select_frames(config)

    # Render in batches of 4
    for batch_start in range(0, len(frames), 4):
        batch_end = min(batch_start + 4, len(frames))
        render_batch(frames, expr_map, batch_start, batch_end)

    assemble_sheet()
    create_gif()
    save_scene()

    # Update config with selected frames
    config['selected_frames'] = frames
    with open(_state['config_path'], 'w') as f:
        json.dump(config, f, indent=4)
    print(f"Config updated with selected_frames")

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
            print("Usage: blender --background --python render_sheet.py -- config.json")
    else:
        print("render_sheet.py loaded. Call functions manually via MCP.")
        print("  load_config(path) -> setup_scene() -> setup_lighting() -> ...")
