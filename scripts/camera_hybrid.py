"""
Hybrid Camera Setup for Sprite Sheet Rendering
================================================
Reference pose scale + ground-anchored Z + per-frame horizontal centering.
Supports per-range camera Z rotation for animations where the character
faces different directions (e.g., fall + getup with facing correction).

Algorithm:
  Phase 1: Compute ortho_scale and ground level from a reference frame.
           Ground level = bottom of character's feet (min_z at reference frame).
           ortho_scale = character height * padding.
  Phase 2: Per-frame camera positioning:
           - Camera Z (screen vertical): FIXED ground-anchored.
           - Camera horizontal: Per-frame mesh center in screen space.
           - Camera rotation: Per-frame Z rotation from rotation ranges.
  Phase 3: Safety — if any frame's horizontal span exceeds ortho_scale, bump.

Usage via Blender MCP:
    import sys, types
    with open(r"C:\\dev\\loracomp3\\scripts\\camera_hybrid.py") as f:
        mod = types.ModuleType("camera_hybrid")
        exec(f.read(), mod.__dict__)
        sys.modules['camera_hybrid'] = mod

    camera_hybrid.setup_camera_hybrid(rs._state, reference_frame=1)

    # With rotation ranges (e.g., character faces different direction in frames 1-7):
    camera_hybrid.setup_camera_hybrid(rs._state, reference_frame=1,
        camera_rotations=[
            {"frames": [1, 7], "z_degrees": 170},
            {"frames": [8, 253], "z_degrees": -90},
        ])
"""

import bpy
import math
import time


# Camera settings (same as render_sheet.py)
CAM_DEPTH = -2.4
CAM_PADDING = 1.15
CAM_BASE_ROTATION = (math.pi / 2, 0)  # X, Y fixed; Z varies per range

# Default camera Z rotation (standard: looking along +X)
DEFAULT_CAM_Z = -math.pi / 2

# Fraction of ortho_scale reserved as margin below the ground line.
GROUND_MARGIN = 0.03


def _get_cam_z_rotation(rotations, frame):
    """Get camera Z rotation (radians) for a given frame."""
    if not rotations:
        return DEFAULT_CAM_Z
    for entry in rotations:
        f_start, f_end = entry['frames']
        if f_start <= frame <= f_end:
            return math.radians(entry['z_degrees'])
    return DEFAULT_CAM_Z



def _get_screen_bounds_at_frame(scene, meshes, frame, cam_z_rot):
    """Get screen-space bounds of deformed meshes at a specific frame.

    Projects mesh vertices onto the camera's coordinate system:
      - Horizontal (h): projection onto camera right axis = (cos(θ), sin(θ), 0)
      - Vertical: world Z (camera up is always +Z)

    Returns: h_min, h_max, z_min, z_max
    """
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
            # Project onto camera right axis
            h = world_co.x * cos_t + world_co.y * sin_t
            h_min = min(h_min, h)
            h_max = max(h_max, h)
            z_min = min(z_min, world_co.z)
            z_max = max(z_max, world_co.z)
        eval_obj.to_mesh_clear()

    return h_min, h_max, z_min, z_max


def _cam_world_position(h_center, cam_z, cam_z_rot, depth=CAM_DEPTH):
    """Compute camera world XYZ from screen-space horizontal center.

    Camera look direction: (-sin(θ), cos(θ), 0)
    Camera right direction: (cos(θ), sin(θ), 0)

    Position = depth * look + h_center * right + (0, 0, cam_z)
    """
    cos_t = math.cos(cam_z_rot)
    sin_t = math.sin(cam_z_rot)

    cam_x = depth * (-sin_t) + h_center * cos_t
    cam_y = depth * cos_t + h_center * sin_t

    return (cam_x, cam_y, cam_z)


def setup_camera_hybrid(state, reference_frame=None, padding=CAM_PADDING,
                        ground_margin=GROUND_MARGIN, ortho_scale_override=None,
                        camera_rotations=None):
    """
    Hybrid camera: ground-anchored + horizontally centered.

    Camera Z is FIXED so the ground level (feet at reference frame) always
    appears at the same screen position near the bottom of the frame.
    Camera horizontal position tracks the per-frame mesh center.
    ortho_scale is locked from the reference frame for consistent character size.

    Supports per-range camera Z rotation via camera_rotations:
        [{"frames": [1, 7], "z_degrees": 170},
         {"frames": [8, 253], "z_degrees": -90}]
    If None, uses fixed -90° (standard +X facing) for all frames.

    Args:
        state: The _state dict from render_sheet.py
        reference_frame: Frame for scale + ground reference. If None, first frame.
        padding: Padding multiplier for ortho_scale (default 1.15)
        ground_margin: Fraction of frame below ground line (default 0.03 = 3%)
        ortho_scale_override: Force a specific ortho_scale (skip safety bump)
        camera_rotations: List of {"frames": [start, end], "z_degrees": angle}

    Returns:
        cam_obj: The created camera object
    """
    scene = bpy.context.scene
    arm = state['armature']
    meshes = state['meshes']

    if not meshes:
        raise RuntimeError("No meshes found in state.")

    if reference_frame is None:
        reference_frame = state['scene_start']

    has_rotations = bool(camera_rotations)

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

    # === Phase 1: Reference scale + ground level ===
    ref_z_rot = _get_cam_z_rotation(camera_rotations, reference_frame)
    h_min, h_max, z_min, z_max = _get_screen_bounds_at_frame(
        scene, meshes, reference_frame, ref_z_rot
    )
    ref_span_h = h_max - h_min
    ref_span_z = z_max - z_min
    ground_z = z_min  # Bottom of feet = ground level

    # ortho_scale based on standing height (Z span dominates for standing chars)
    ref_scale = max(ref_span_h, ref_span_z) * padding

    # Camera Z (world): anchor ground near bottom of frame
    cam_z = ground_z + ref_scale * (0.5 - ground_margin)

    print(f"Phase 1: Reference frame {reference_frame} (cam_z_rot={math.degrees(ref_z_rot):.0f}°)")
    print(f"  span_h={ref_span_h:.3f}, span_z={ref_span_z:.3f}")
    print(f"  ground_z={ground_z:.4f}, ortho_scale={ref_scale:.3f}")
    print(f"  cam_z={cam_z:.3f} (ground at {ground_margin*100:.0f}% from bottom)")

    # === Phase 2: Per-frame screen-space centering ===
    max_h_span = 0
    max_h_span_frame = reference_frame
    frame_data = {}  # frame -> (h_center, f_z_min, f_z_max, cam_z_rot)

    for f in range(state['scene_start'], state['scene_end'] + 1):
        f_z_rot = _get_cam_z_rotation(camera_rotations, f)
        f_h_min, f_h_max, f_z_min, f_z_max = _get_screen_bounds_at_frame(
            scene, meshes, f, f_z_rot
        )
        h_center = (f_h_min + f_h_max) / 2
        h_span = f_h_max - f_h_min

        frame_data[f] = (h_center, f_z_min, f_z_max, f_z_rot)

        if h_span > max_h_span:
            max_h_span = h_span
            max_h_span_frame = f

    phase2_time = time.time() - t
    print(f"Phase 2: Screen-space centering computed ({state['scene_end']} frames in {phase2_time:.1f}s)")
    print(f"  Max horizontal span: {max_h_span:.3f} at frame {max_h_span_frame}")

    # === Phase 3: Determine final scale ===
    if ortho_scale_override is not None:
        final_scale = ortho_scale_override
        cam_z = ground_z + final_scale * (0.5 - ground_margin)
        print(f"Phase 3: Using forced ortho_scale={final_scale:.3f} (override)")
        print(f"  Max h_span*pad={max_h_span * padding:.3f}, "
              f"margin={(1 - max_h_span / final_scale) * 50:.1f}% per side")
    else:
        max_h_span_padded = max_h_span * padding
        if max_h_span_padded > ref_scale:
            print(f"Phase 3: Horizontal span exceeds reference scale at frame {max_h_span_frame}")
            print(f"  Bumping scale: {ref_scale:.3f} -> {max_h_span_padded:.3f} "
                  f"(+{(max_h_span_padded/ref_scale - 1)*100:.1f}%)")
            final_scale = max_h_span_padded
            cam_z = ground_z + final_scale * (0.5 - ground_margin)
        else:
            print(f"Phase 3: All frames fit horizontally (max_h_span*pad={max_h_span_padded:.3f} "
                  f"<= ref_scale={ref_scale:.3f})")
            final_scale = ref_scale

    cam_data.ortho_scale = final_scale

    # === Bake camera keyframes ===
    # Ground-anchored: cam_z fixed from reference ground level.
    # If character goes below ground, track downward to avoid clipping.
    for f, (hc, f_z_min, f_z_max, z_rot) in frame_data.items():
        effective_ground = min(f_z_min, ground_z)
        f_cam_z = effective_ground + final_scale * (0.5 - ground_margin)
        pos = _cam_world_position(hc, f_cam_z, z_rot)
        cam_obj.location = pos
        cam_obj.rotation_euler = (CAM_BASE_ROTATION[0], CAM_BASE_ROTATION[1], z_rot)
        cam_obj.keyframe_insert(data_path='location', frame=f)
        if has_rotations:
            cam_obj.keyframe_insert(data_path='rotation_euler', frame=f)

    # Set rotation keyframe interpolation to CONSTANT (step) to avoid
    # smooth transitions between rotation ranges
    if has_rotations and cam_obj.animation_data and cam_obj.animation_data.action:
        act = cam_obj.animation_data.action
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        if fc.data_path == 'rotation_euler':
                            for kp in fc.keyframe_points:
                                kp.interpolation = 'CONSTANT'

    total_time = time.time() - t
    rot_info = f", {len(camera_rotations)} rotation ranges" if has_rotations else ""
    print(f"\nCamera HYBRID done: ortho_scale={final_scale:.3f}, cam_z={cam_z:.3f}, "
          f"{total_time:.1f}s{rot_info}")
    print(f"  View range Z (standing): [{ground_z - ground_margin * final_scale:.3f}, "
          f"{ground_z + final_scale * (1 - ground_margin):.3f}]")

    return cam_obj
