"""Check where actual animation data exists in an FBX."""
import bpy
import sys
import os

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

fbx_path = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
bpy.ops.import_scene.fbx(filepath=fbx_path)

print(f"\nScene frame range: {bpy.context.scene.frame_start} to {bpy.context.scene.frame_end}")

# Check all actions for actual keyframe range
for action in bpy.data.actions:
    print(f"\nAction: {action.name}")
    print(f"  Frame range: {action.frame_range[0]:.0f} to {action.frame_range[1]:.0f}")
    print(f"  FCurves: {len(action.fcurves)}")

    # Find actual min/max keyframe across all fcurves
    min_frame = float('inf')
    max_frame = float('-inf')
    for fc in action.fcurves:
        for kp in fc.keyframe_points:
            min_frame = min(min_frame, kp.co[0])
            max_frame = max(max_frame, kp.co[0])
    if min_frame != float('inf'):
        print(f"  Actual keyframes: {min_frame:.0f} to {max_frame:.0f}")
