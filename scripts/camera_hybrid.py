"""
Hybrid Camera Setup for Sprite Sheet Rendering
================================================
Reference pose scale + ground-anchored Z + per-frame horizontal centering.

Algorithm:
  Phase 1: Compute ortho_scale and ground level from a reference frame.
           Ground level = bottom of character's feet (min_z at reference frame).
           ortho_scale = character height * padding.
  Phase 2: Per-frame camera positioning:
           - Camera Z: FIXED. Ground level anchored near frame bottom.
             Character always "stands on" the ground at the same screen position.
           - Camera Y: Per-frame mesh center (horizontal centering only).
             Distributes left/right white space evenly — no horizontal clipping.
  Phase 3: Safety — if any frame's horizontal span exceeds ortho_scale, bump.
           Vertical overflow above the frame top is allowed (rare, only jumps).

Usage via Blender MCP:
    import sys, types
    with open(r"C:\\dev\\loracomp3\\scripts\\camera_hybrid.py") as f:
        mod = types.ModuleType("camera_hybrid")
        exec(f.read(), mod.__dict__)
        sys.modules['camera_hybrid'] = mod

    camera_hybrid.setup_camera_hybrid(rs._state, reference_frame=1)
"""

import bpy
import math
import time


# Camera settings (same as render_sheet.py)
CAM_DEPTH = -2.4
CAM_PADDING = 1.15
CAM_ROTATION = (math.pi / 2, 0, -math.pi / 2)

# Fraction of ortho_scale reserved as margin below the ground line.
# 0.03 = 3% of the frame height below the feet.
GROUND_MARGIN = 0.03


def _get_mesh_bounds_at_frame(scene, meshes, frame):
    """Get world-space Y/Z bounding box of deformed meshes at a specific frame."""
    scene.frame_set(frame)
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

    return min_y, max_y, min_z, max_z


def setup_camera_hybrid(state, reference_frame=None, padding=CAM_PADDING,
                        ground_margin=GROUND_MARGIN, ortho_scale_override=None):
    """
    Hybrid camera: ground-anchored + horizontally centered.

    Camera Z is FIXED so the ground level (feet at reference frame) always
    appears at the same screen position near the bottom of the frame.
    Camera Y tracks the per-frame mesh center for horizontal centering.
    ortho_scale is locked from the reference frame for consistent character size.

    Args:
        state: The _state dict from render_sheet.py
        reference_frame: Frame for scale + ground reference. If None, first frame.
        padding: Padding multiplier for ortho_scale (default 1.15)
        ground_margin: Fraction of frame below ground line (default 0.03 = 3%)

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
    cam_obj.rotation_euler = CAM_ROTATION

    t = time.time()

    # === Phase 1: Reference scale + ground level ===
    min_y, max_y, min_z, max_z = _get_mesh_bounds_at_frame(
        scene, meshes, reference_frame
    )
    ref_span_y = max_y - min_y
    ref_span_z = max_z - min_z
    ground_z = min_z  # Bottom of feet = ground level

    # ortho_scale based on standing height (Z span dominates for standing chars)
    ref_scale = max(ref_span_y, ref_span_z) * padding

    # Camera Z: anchor ground near bottom of frame
    # Frame bottom = cam_z - ortho_scale/2
    # We want: frame bottom = ground_z - ground_margin * ortho_scale
    # So: cam_z - ortho_scale/2 = ground_z - ground_margin * ortho_scale
    # => cam_z = ground_z + ortho_scale * (0.5 - ground_margin)
    cam_z = ground_z + ref_scale * (0.5 - ground_margin)

    print(f"Phase 1: Reference frame {reference_frame}")
    print(f"  span_y={ref_span_y:.3f}, span_z={ref_span_z:.3f}")
    print(f"  ground_z={ground_z:.4f}, ortho_scale={ref_scale:.3f}")
    print(f"  cam_z={cam_z:.3f} (ground at {ground_margin*100:.0f}% from bottom)")

    # === Phase 2: Per-frame horizontal centering ===
    max_y_span = 0
    max_y_span_frame = reference_frame
    frame_center_ys = {}

    for f in range(state['scene_start'], state['scene_end'] + 1):
        f_min_y, f_max_y, f_min_z, f_max_z = _get_mesh_bounds_at_frame(
            scene, meshes, f
        )
        center_y = (f_min_y + f_max_y) / 2
        y_span = f_max_y - f_min_y

        frame_center_ys[f] = center_y

        if y_span > max_y_span:
            max_y_span = y_span
            max_y_span_frame = f

    phase2_time = time.time() - t
    print(f"Phase 2: Horizontal centering computed ({state['scene_end']} frames in {phase2_time:.1f}s)")
    print(f"  Max Y span: {max_y_span:.3f} at frame {max_y_span_frame}")

    # === Phase 3: Determine final scale ===
    if ortho_scale_override is not None:
        # User-forced scale — skip safety bump
        final_scale = ortho_scale_override
        cam_z = ground_z + final_scale * (0.5 - ground_margin)
        print(f"Phase 3: Using forced ortho_scale={final_scale:.3f} (override)")
        print(f"  Max Y span*pad={max_y_span * padding:.3f}, "
              f"margin={(1 - max_y_span / final_scale) * 50:.1f}% per side")
    else:
        # Safety — check horizontal span, bump scale if needed.
        # Vertical overflow above frame top is acceptable.
        max_y_span_padded = max_y_span * padding
        if max_y_span_padded > ref_scale:
            print(f"Phase 3: Horizontal span exceeds reference scale at frame {max_y_span_frame}")
            print(f"  Bumping scale: {ref_scale:.3f} -> {max_y_span_padded:.3f} "
                  f"(+{(max_y_span_padded/ref_scale - 1)*100:.1f}%)")
            final_scale = max_y_span_padded
            cam_z = ground_z + final_scale * (0.5 - ground_margin)
        else:
            print(f"Phase 3: All frames fit horizontally (max_y_span*pad={max_y_span_padded:.3f} "
                  f"<= ref_scale={ref_scale:.3f})")
            final_scale = ref_scale

    cam_data.ortho_scale = final_scale

    # === Bake camera keyframes ===
    # Z is FIXED (ground-anchored), only Y varies per frame
    for f, cy in frame_center_ys.items():
        cam_obj.location = (CAM_DEPTH, cy, cam_z)
        cam_obj.keyframe_insert(data_path='location', frame=f)

    total_time = time.time() - t
    print(f"\nCamera HYBRID done: ortho_scale={final_scale:.3f}, cam_z={cam_z:.3f}, {total_time:.1f}s")
    print(f"  View range Z: [{ground_z - ground_margin * final_scale:.3f}, "
          f"{ground_z + final_scale * (1 - ground_margin):.3f}]")

    return cam_obj
