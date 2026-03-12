"""Test: Render with hair cloth physics and time it."""
import bpy
import sys
import os
import math
import time

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

def add_hair_physics():
    """Add cloth simulation to the Hair mesh."""
    hair_obj = None
    collision_targets = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and 'Hair' in obj.name:
            hair_obj = obj
        elif obj.type == 'MESH':
            collision_targets.append(obj)
    if not hair_obj:
        print("No Hair mesh found")
        return

    # Add Collision modifier to ALL non-hair meshes so hair can't clip through
    for body_obj in collision_targets:
        print(f"Adding collision to {body_obj.name}")
        bpy.context.view_layer.objects.active = body_obj
        col_mod = body_obj.modifiers.new("Collision", 'COLLISION')
        col_mod.settings.thickness_outer = 0.002
        col_mod.settings.thickness_inner = 0.001

    print(f"Adding cloth physics to {hair_obj.name}")
    bpy.context.view_layer.objects.active = hair_obj

    # Add cloth modifier
    cloth_mod = hair_obj.modifiers.new("Cloth", 'CLOTH')
    cloth = cloth_mod.settings

    # Very stiff hair: minimal movement, just subtle sway at tips
    cloth.mass = 0.02
    cloth.tension_stiffness = 80.0
    cloth.compression_stiffness = 80.0
    cloth.bending_stiffness = 40.0
    cloth.tension_damping = 50.0
    cloth.compression_damping = 50.0
    cloth.bending_damping = 25.0

    # Pin group: vertices near the head stay attached
    # We'll create a vertex group based on Z position (top vertices are pinned)
    vg = hair_obj.vertex_groups.new(name="Pin")
    # Find the top of the hair mesh to set pin zone
    max_z = max((hair_obj.matrix_world @ v.co).z for v in hair_obj.data.vertices)
    min_z = min((hair_obj.matrix_world @ v.co).z for v in hair_obj.data.vertices)
    hair_height = max_z - min_z
    # Pin the top 50% of the hair — only the very tips can move
    pin_threshold = max_z - hair_height * 0.50
    fade_zone = hair_height * 0.25

    print(f"  Hair Z range: {min_z:.2f} to {max_z:.2f}, pin above {pin_threshold:.2f}")

    for v in hair_obj.data.vertices:
        world_co = hair_obj.matrix_world @ v.co
        if world_co.z > pin_threshold:
            vg.add([v.index], 1.0, 'REPLACE')
        elif world_co.z > pin_threshold - fade_zone:
            weight = (world_co.z - (pin_threshold - fade_zone)) / fade_zone
            vg.add([v.index], weight, 'REPLACE')

    cloth.vertex_group_mass = "Pin"

    # Collision settings
    cloth_mod.collision_settings.use_self_collision = False
    cloth_mod.collision_settings.use_collision = True
    cloth_mod.collision_settings.distance_min = 0.003

    # Get frame range
    end_frame = 54
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj.animation_data and obj.animation_data.action:
            end_frame = int(obj.animation_data.action.frame_range[1])
            break

    # Bake physics
    print(f"Baking cloth physics for frames 1 to {end_frame}...")
    t = time.time()
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = end_frame

    # Need to step through frames to bake
    for frame in range(1, end_frame + 1):
        bpy.context.scene.frame_set(frame)
    bake_time = time.time() - t
    print(f"Physics bake took {bake_time:.1f}s")
    return bake_time

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

    # Time WITHOUT physics
    t_start = time.time()
    end_frame = 54
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj.animation_data and obj.animation_data.action:
            end_frame = int(obj.animation_data.action.frame_range[1])
            break

    frames = list(range(1, end_frame + 1, 5))
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        bpy.context.scene.render.filepath = os.path.join(out_dir, f"no_physics_{frame:04d}.png")
        bpy.ops.render.render(write_still=True)
    no_phys_time = time.time() - t_start
    print(f"\nWithout physics: {len(frames)} frames in {no_phys_time:.1f}s ({no_phys_time/len(frames):.1f}s/frame)")

    # Time WITH physics
    t_start = time.time()
    bake_time = add_hair_physics()
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        bpy.context.scene.render.filepath = os.path.join(out_dir, f"physics_{frame:04d}.png")
        bpy.ops.render.render(write_still=True)
    phys_time = time.time() - t_start
    print(f"With physics: {len(frames)} frames in {phys_time:.1f}s ({phys_time/len(frames):.1f}s/frame)")
    print(f"\nOverhead: {phys_time - no_phys_time:.1f}s extra ({(phys_time/no_phys_time - 1)*100:.0f}% slower)")

if __name__ == "__main__":
    main()
