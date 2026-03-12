"""Test: Spring bone physics for VRM hair bones.

Animates secondary hair bones (J_Sec_Hair*) using spring dynamics.
When the head moves, hair bones lag behind with spring-damped inertia.

Usage:
  blender --background --python test_spring_bones.py -- input.fbx output_dir
"""
import bpy
import sys
import os
import math
import time
import mathutils


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)


def import_fbx(fbx_path):
    bpy.ops.import_scene.fbx(filepath=fbx_path)


def setup_camera_and_light():
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = 'PERSP'
    cam_data.lens = 50.0
    cam_data.sensor_width = 36.0
    cam_data.sensor_height = 24.0
    cam_data.sensor_fit = 'AUTO'
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    cam_obj.location = (-2.4063, -0.3171, 0.6149)
    cam_obj.rotation_euler = (1.6393, -0.0000027, -1.4561)

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


def setup_render():
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
    ls.linestyle.color = (0, 0, 0)
    ls.linestyle.thickness = 1.0


def find_hair_chains(arm_obj):
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


def simulate_spring_bones(arm_obj, stiffness=0.8, damping=0.6, reaction=0.15, max_deg=5.0):
    """
    Spring bone simulation for hair chains.

    When the head rotates, hair bones resist the motion (inertia) then spring back.

    Args:
        stiffness: Return-to-rest force (0-1). Higher = stiffer hair.
        damping: Velocity decay (0-1). Higher = less bouncy.
        reaction: How much hair reacts to head movement. Lower = subtler.
        max_deg: Maximum rotation offset in degrees per bone.
    """
    chains = find_hair_chains(arm_obj)
    print(f"Spring bones: {len(chains)} hair chains")
    for chain in chains:
        print(f"  {chain[0]} ({len(chain)} bones)")

    # Get frame range from armature action
    end_frame = 54
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj.animation_data and obj.animation_data.action:
            end_frame = int(obj.animation_data.action.frame_range[1])
            break

    # Enter pose mode
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')

    # First pass: record head bone world rotation at each frame
    head_quats = []
    for frame in range(1, end_frame + 1):
        bpy.context.scene.frame_set(frame)
        head_pbone = arm_obj.pose.bones['J_Bip_C_Head']
        world_mat = arm_obj.matrix_world @ head_pbone.matrix
        head_quats.append(world_mat.to_quaternion())

    # Initialize spring state for each bone
    state = {}
    for chain in chains:
        for bone_name in chain:
            state[bone_name] = {
                'ox': 0.0, 'oz': 0.0,  # Rotation offset (radians)
                'vx': 0.0, 'vz': 0.0,  # Angular velocity
            }

    max_rad = math.radians(max_deg)

    # Second pass: simulate springs and keyframe
    t = time.time()
    prev_quat = head_quats[0]

    for fi in range(len(head_quats)):
        frame = fi + 1
        bpy.context.scene.frame_set(frame)

        # Head angular velocity (euler delta)
        cur_quat = head_quats[fi]
        delta = prev_quat.inverted() @ cur_quat
        delta_euler = delta.to_euler()
        prev_quat = cur_quat

        for chain in chains:
            for ci, bone_name in enumerate(chain):
                pbone = arm_obj.pose.bones[bone_name]
                s = state[bone_name]

                # Chain factor: tips move more than roots
                cf = (ci + 1) / len(chain)

                # Inertia force: oppose head rotation (hair lags behind)
                fx = -delta_euler.x * reaction * cf
                fz = -delta_euler.z * reaction * cf

                # Spring force: return to rest (offset → 0)
                fx += -s['ox'] * stiffness
                fz += -s['oz'] * stiffness

                # Update velocity with damping
                s['vx'] = s['vx'] * (1.0 - damping) + fx
                s['vz'] = s['vz'] * (1.0 - damping) + fz

                # Update offset
                s['ox'] += s['vx']
                s['oz'] += s['vz']

                # Clamp to max angle (scaled by chain factor)
                limit = max_rad * cf
                s['ox'] = max(-limit, min(limit, s['ox']))
                s['oz'] = max(-limit, min(limit, s['oz']))

                # Apply rotation in bone-local space
                # X = tilt forward/back, Z = tilt left/right
                pbone.rotation_mode = 'XYZ'
                pbone.rotation_euler = (s['ox'], 0.0, s['oz'])
                pbone.keyframe_insert(data_path='rotation_euler', frame=frame)

    bpy.ops.object.mode_set(mode='OBJECT')
    sim_time = time.time() - t
    print(f"Spring bone simulation: {end_frame} frames in {sim_time:.1f}s")
    return sim_time


def main():
    argv = sys.argv
    idx = argv.index("--")
    args = argv[idx + 1:]
    fbx_path = os.path.abspath(args[0])
    out_dir = os.path.abspath(args[1])
    os.makedirs(out_dir, exist_ok=True)

    clear_scene()
    import_fbx(fbx_path)
    setup_camera_and_light()
    setup_render()

    # Find armature
    arm_obj = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            arm_obj = obj
            break

    # Get frame range
    end_frame = 54
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj.animation_data and obj.animation_data.action:
            end_frame = int(obj.animation_data.action.frame_range[1])
            break

    frames = list(range(1, end_frame + 1, 5))

    # Render WITHOUT spring bones
    t_start = time.time()
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        bpy.context.scene.render.filepath = os.path.join(out_dir, f"no_spring_{frame:04d}.png")
        bpy.ops.render.render(write_still=True)
    no_spring_time = time.time() - t_start
    print(f"\nWithout spring bones: {len(frames)} frames in {no_spring_time:.1f}s")

    # Add spring bone physics
    sim_time = simulate_spring_bones(
        arm_obj,
        stiffness=0.3,   # Loose — slow return to rest
        damping=0.2,      # Low damping — more bouncy/oscillation
        reaction=2.0,     # Strong reaction to head movement
        max_deg=45.0,     # Max 45 degrees rotation at tips
    )

    # Render WITH spring bones
    t_start = time.time()
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        bpy.context.scene.render.filepath = os.path.join(out_dir, f"spring_{frame:04d}.png")
        bpy.ops.render.render(write_still=True)
    spring_time = time.time() - t_start
    print(f"With spring bones: {len(frames)} frames in {spring_time:.1f}s")
    print(f"Spring sim overhead: {sim_time:.1f}s")
    print(f"Render overhead: {spring_time - no_spring_time:.1f}s")


if __name__ == "__main__":
    main()
