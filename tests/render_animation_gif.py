"""Blender script: Render animation frames at interval, then create GIF.

Usage:
  blender --background --python render_animation_gif.py -- input.fbx output_dir [frame_step]
"""
import bpy
import sys
import os
import math

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)

def import_fbx(fbx_path):
    bpy.ops.import_scene.fbx(filepath=fbx_path)
    print(f"Imported {fbx_path}")

def setup_camera_and_light():
    min_co = [float('inf')] * 3
    max_co = [float('-inf')] * 3
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            for v in obj.data.vertices:
                world_co = obj.matrix_world @ v.co
                for i in range(3):
                    min_co[i] = min(min_co[i], world_co[i])
                    max_co[i] = max(max_co[i], world_co[i])

    # Camera: exact values from user's Blender setup
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

    # Flat lighting, all shadows OFF
    sun1 = bpy.data.lights.new("Sun_Key", 'SUN')
    sun1.energy = 4.0
    sun1.use_shadow = False
    sun1_obj = bpy.data.objects.new("Sun_Key", sun1)
    bpy.context.scene.collection.objects.link(sun1_obj)
    sun1_obj.rotation_euler = (math.radians(30), 0, math.radians(-20))

    sun2 = bpy.data.lights.new("Sun_Fill", 'SUN')
    sun2.energy = 2.5
    sun2.use_shadow = False
    sun2_obj = bpy.data.objects.new("Sun_Fill", sun2)
    bpy.context.scene.collection.objects.link(sun2_obj)
    sun2_obj.rotation_euler = (math.radians(40), 0, math.radians(160))

    sun3 = bpy.data.lights.new("Sun_Rim", 'SUN')
    sun3.energy = 1.5
    sun3.use_shadow = False
    sun3_obj = bpy.data.objects.new("Sun_Rim", sun3)
    bpy.context.scene.collection.objects.link(sun3_obj)
    sun3_obj.rotation_euler = (math.radians(60), 0, math.radians(180))

    # Flat materials
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

    # Standard color management
    scene.view_settings.view_transform = 'Standard'

    # White background
    world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
        bg.inputs['Strength'].default_value = 1.0

    # Freestyle outline
    scene.render.use_freestyle = True
    view_layer = scene.view_layers[0]
    view_layer.use_freestyle = True
    if view_layer.freestyle_settings.linesets:
        lineset = view_layer.freestyle_settings.linesets[0]
    else:
        lineset = view_layer.freestyle_settings.linesets.new("OutlineSet")
    lineset.select_silhouette = False
    lineset.select_border = False
    lineset.select_contour = False
    lineset.select_crease = False
    lineset.select_edge_mark = False
    lineset.select_external_contour = True
    lineset.select_material_boundary = False
    lineset.select_suggestive_contour = False
    lineset.select_ridge_valley = False
    style = lineset.linestyle
    style.color = (0, 0, 0)
    style.thickness = 1.0

def main():
    argv = sys.argv
    idx = argv.index("--")
    args = argv[idx + 1:]

    fbx_path = os.path.abspath(args[0])
    out_dir = os.path.abspath(args[1])
    frame_step = int(args[2]) if len(args) > 2 else 10

    os.makedirs(out_dir, exist_ok=True)

    clear_scene()
    import_fbx(fbx_path)
    setup_camera_and_light()
    setup_render()

    scene = bpy.context.scene
    # Use actual armature action keyframe range, not scene default (250)
    start = scene.frame_start
    end = scene.frame_end
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj.animation_data and obj.animation_data.action:
            action = obj.animation_data.action
            end = int(action.frame_range[1])
            print(f"Armature action '{action.name}' range: {int(action.frame_range[0])} to {end}")
            break
    print(f"Animation: frame {start} to {end}, step {frame_step}")

    frames_rendered = []
    frame = start
    while frame <= end:
        scene.frame_set(frame)
        filepath = os.path.join(out_dir, f"frame_{frame:04d}.png")
        scene.render.filepath = filepath
        bpy.ops.render.render(write_still=True)
        frames_rendered.append(filepath)
        print(f"  Rendered frame {frame}")
        frame += frame_step

    print(f"\nRendered {len(frames_rendered)} frames to {out_dir}")

if __name__ == "__main__":
    main()
