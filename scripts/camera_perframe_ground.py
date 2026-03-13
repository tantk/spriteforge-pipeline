"""
Per-Frame Ground Camera for Sprite Sheet Rendering
====================================================
Variant of hybrid camera where BOTH axes track per-frame:
  - Horizontal: per-frame mesh center (same as hybrid)
  - Vertical: per-frame ground anchoring (character's lowest point always
    near frame bottom)

Used for animations with extreme vertical movement (rolling, tumbling)
where a fixed ground level causes the character to float or clip.

ortho_scale is still locked from a reference frame for consistent sizing.

Usage via Blender MCP:
    import sys, types
    with open(r"C:\\dev\\loracomp3\\scripts\\camera_perframe_ground.py") as f:
        mod = types.ModuleType("camera_perframe_ground")
        exec(f.read(), mod.__dict__)
        sys.modules['camera_perframe_ground'] = mod

    camera_perframe_ground.setup_camera_perframe_ground(rs._state, reference_frame=1)
"""

import bpy
import math
import time


# Camera settings (same as render_sheet.py / camera_hybrid.py)
CAM_DEPTH = -2.4
CAM_PADDING = 1.15
CAM_BASE_ROTATION = (math.pi / 2, 0)
DEFAULT_CAM_Z = -math.pi / 2
GROUND_MARGIN = 0.03


def _get_screen_bounds_at_frame(scene, meshes, frame, cam_z_rot):
    """Get screen-space bounds of deformed meshes at a specific frame."""
    scene.frame_set(frame)
    depsgraph = bpy.context.evaluated_depsgraph_get()

    cos_t = math.cos(cam_z_rot)
    sin_t = math.sin(cam_z_rot)

    h_min = float('inf')
    h_max = float('-inf')
    z_min = float('inf')
    z_max = float('-inf')

    for mesh_obj in meshes:
        eval_obj = mesh_obj.evaluated_get(depsgraph)
        mesh_data = eval_obj.to_mesh()
        for v in mesh_data.vertices:
            world_co = eval_obj.matrix_world @ v.co
            h = world_co.x * cos_t + world_co.y * sin_t
            h_min = min(h_min, h)
            h_max = max(h_max, h)
            z_min = min(z_min, world_co.z)
            z_max = max(z_max, world_co.z)
        eval_obj.to_mesh_clear()

    return h_min, h_max, z_min, z_max


def _cam_world_position(h_center, cam_z, cam_z_rot, depth=CAM_DEPTH):
    """Compute camera world XYZ from screen-space horizontal center."""
    cos_t = math.cos(cam_z_rot)
    sin_t = math.sin(cam_z_rot)

    cam_x = depth * (-sin_t) + h_center * cos_t
    cam_y = depth * cos_t + h_center * sin_t

    return (cam_x, cam_y, cam_z)


def setup_camera_perframe_ground(state, reference_frame=None, padding=CAM_PADDING,
                                  ground_margin=GROUND_MARGIN, ortho_scale_override=None):
    """
    Per-frame ground camera: both axes track per-frame.

    Horizontal: per-frame mesh center in screen space.
    Vertical: per-frame ground anchoring — character's lowest point always
    at ground_margin from the frame bottom.

    ortho_scale locked from reference frame (or overridden).

    Args:
        state: The _state dict from render_sheet.py
        reference_frame: Frame for scale reference. If None, first frame.
        padding: Padding multiplier for ortho_scale (default 1.15)
        ground_margin: Fraction of frame below ground line (default 0.03)
        ortho_scale_override: Force a specific ortho_scale

    Returns:
        cam_obj: The created camera object
    """
    scene = bpy.context.scene
    meshes = state['meshes']

    if not meshes:
        raise RuntimeError("No meshes found in state.")

    if reference_frame is None:
        reference_frame = state['scene_start']

    cam_z_rot = DEFAULT_CAM_Z

    # Remove existing camera
    for obj in list(bpy.data.objects):
        if obj.type == 'CAMERA':
            bpy.data.objects.remove(obj, do_unlink=True)
    for cam in list(bpy.data.cameras):
        bpy.data.cameras.remove(cam)

    # Create camera
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = 'ORTHO'
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    t = time.time()

    # === Phase 1: Reference scale ===
    h_min, h_max, z_min, z_max = _get_screen_bounds_at_frame(
        scene, meshes, reference_frame, cam_z_rot
    )
    ref_scale = max(h_max - h_min, z_max - z_min) * padding

    print(f"Phase 1: Reference frame {reference_frame}")
    print(f"  span_h={h_max - h_min:.3f}, span_z={z_max - z_min:.3f}, ref_scale={ref_scale:.3f}")

    # === Phase 2: Per-frame bounds ===
    max_h_span = 0
    frame_data = {}

    for f in range(state['scene_start'], state['scene_end'] + 1):
        f_h_min, f_h_max, f_z_min, f_z_max = _get_screen_bounds_at_frame(
            scene, meshes, f, cam_z_rot
        )
        h_center = (f_h_min + f_h_max) / 2
        h_span = f_h_max - f_h_min
        frame_data[f] = (h_center, f_z_min)
        max_h_span = max(max_h_span, h_span)

    phase2_time = time.time() - t
    print(f"Phase 2: {len(frame_data)} frames scanned in {phase2_time:.1f}s")
    print(f"  Max horizontal span: {max_h_span:.3f}")

    # === Phase 3: Final scale ===
    if ortho_scale_override is not None:
        final_scale = ortho_scale_override
        print(f"Phase 3: Using forced ortho_scale={final_scale:.3f}")
    else:
        max_h_padded = max_h_span * padding
        if max_h_padded > ref_scale:
            print(f"Phase 3: Bumping scale {ref_scale:.3f} -> {max_h_padded:.3f}")
            final_scale = max_h_padded
        else:
            final_scale = ref_scale
            print(f"Phase 3: Using ref_scale={final_scale:.3f}")

    cam_data.ortho_scale = final_scale

    # === Bake: per-frame ground tracking ===
    for f, (hc, f_z_min) in frame_data.items():
        f_cam_z = f_z_min + final_scale * (0.5 - ground_margin)
        pos = _cam_world_position(hc, f_cam_z, cam_z_rot)
        cam_obj.location = pos
        cam_obj.rotation_euler = (CAM_BASE_ROTATION[0], CAM_BASE_ROTATION[1], cam_z_rot)
        cam_obj.keyframe_insert(data_path='location', frame=f)

    total_time = time.time() - t
    print(f"\nCamera PERFRAME_GROUND done: ortho_scale={final_scale:.3f}, {total_time:.1f}s")

    return cam_obj
