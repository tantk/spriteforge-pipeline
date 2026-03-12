"""Blender script: Test render a Mixamo animation FBX.

Imports the FBX, fixes materials, sets up camera + lighting, renders a frame.

Usage:
  blender --background --python test_render_animation.py -- input.fbx output.png [frame]
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

    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            print(f"  Mesh: {obj.name} ({len(obj.data.vertices)} verts, {len(obj.data.materials)} mats)")
        elif obj.type == 'ARMATURE':
            print(f"  Armature: {obj.name} ({len(obj.data.bones)} bones)")

def debug_and_fix_materials():
    """Check material state after FBX import and fix if needed."""
    print("\n--- Material Debug ---")
    for mat in bpy.data.materials:
        if not mat.node_tree:
            print(f"  {mat.name}: NO NODE TREE")
            continue

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Find key nodes
        tex_nodes = [n for n in nodes if n.type == 'TEX_IMAGE']
        principled = [n for n in nodes if n.type == 'BSDF_PRINCIPLED']
        emission = [n for n in nodes if n.type == 'EMISSION']
        output = [n for n in nodes if n.type == 'OUTPUT_MATERIAL']

        has_tex = len(tex_nodes) > 0
        has_image = has_tex and tex_nodes[0].image is not None
        tex_img_name = tex_nodes[0].image.name if has_image else "none"

        print(f"  {mat.name}: tex={len(tex_nodes)} principled={len(principled)} emission={len(emission)} output={len(output)}")
        if has_tex:
            print(f"    Texture image: {tex_img_name}")
            # Check what texture is connected to
            for link in links:
                if link.from_node in tex_nodes:
                    print(f"    {link.from_node.name}.{link.from_socket.name} -> {link.to_node.name}.{link.to_socket.name}")

        # Fix: ensure texture -> Principled BSDF -> Output
        if has_image and principled:
            p = principled[0]
            t = tex_nodes[0]
            base_color = p.inputs.get('Base Color')
            if base_color and not base_color.links:
                print(f"    FIXING: connecting texture to Principled BSDF")
                links.new(t.outputs['Color'], p.inputs['Base Color'])
                links.new(t.outputs['Alpha'], p.inputs['Alpha'])
        elif has_image and not principled:
            # No Principled BSDF - create one
            print(f"    FIXING: creating Principled BSDF")
            t = tex_nodes[0]
            p = nodes.new('ShaderNodeBsdfPrincipled')
            links.new(t.outputs['Color'], p.inputs['Base Color'])
            links.new(t.outputs['Alpha'], p.inputs['Alpha'])
            if output:
                # Remove old surface link
                for link in list(links):
                    if link.to_node == output[0] and link.to_socket.name == 'Surface':
                        links.remove(link)
                links.new(p.outputs['BSDF'], output[0].inputs['Surface'])

    print("--- End Material Debug ---\n")

def setup_camera_and_light():
    """Set up camera facing the character and a simple light."""
    min_co = [float('inf')] * 3
    max_co = [float('-inf')] * 3
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            for v in obj.data.vertices:
                world_co = obj.matrix_world @ v.co
                for i in range(3):
                    min_co[i] = min(min_co[i], world_co[i])
                    max_co[i] = max(max_co[i], world_co[i])

    center_x = (min_co[0] + max_co[0]) / 2
    center_y = (min_co[1] + max_co[1]) / 2
    center_z = (min_co[2] + max_co[2]) / 2
    height = max_co[2] - min_co[2]

    print(f"Character bounds: height={height:.2f}, center=({center_x:.2f}, {center_y:.2f}, {center_z:.2f})")

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

    # Flat lighting for pixel art sprites
    # Key light: front-top sun, no shadow
    sun1 = bpy.data.lights.new("Sun_Key", 'SUN')
    sun1.energy = 4.0
    sun1.use_shadow = False
    sun1_obj = bpy.data.objects.new("Sun_Key", sun1)
    bpy.context.scene.collection.objects.link(sun1_obj)
    sun1_obj.rotation_euler = (math.radians(30), 0, math.radians(-20))

    # Fill light: opposite side, no shadow
    sun2 = bpy.data.lights.new("Sun_Fill", 'SUN')
    sun2.energy = 2.5
    sun2.use_shadow = False
    sun2_obj = bpy.data.objects.new("Sun_Fill", sun2)
    bpy.context.scene.collection.objects.link(sun2_obj)
    sun2_obj.rotation_euler = (math.radians(40), 0, math.radians(160))

    # Rim light: from behind, no shadow
    sun3 = bpy.data.lights.new("Sun_Rim", 'SUN')
    sun3.energy = 1.5
    sun3.use_shadow = False
    sun3_obj = bpy.data.objects.new("Sun_Rim", sun3)
    bpy.context.scene.collection.objects.link(sun3_obj)
    sun3_obj.rotation_euler = (math.radians(60), 0, math.radians(180))

    # Make all materials less shiny (reduce specular for flat look)
    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs['Specular IOR Level'].default_value = 0.0
                node.inputs['Roughness'].default_value = 1.0

def setup_render(output_path):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.film_transparent = False  # Solid background for debugging
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'

    # Standard color management (no filmic tone curve darkening whites)
    scene.view_settings.view_transform = 'Standard'

    # Freestyle outline
    scene.render.use_freestyle = True
    view_layer = scene.view_layers[0]
    view_layer.use_freestyle = True
    # Configure line set
    if view_layer.freestyle_settings.linesets:
        lineset = view_layer.freestyle_settings.linesets[0]
    else:
        lineset = view_layer.freestyle_settings.linesets.new("OutlineSet")
    lineset.select_silhouette = False
    lineset.select_border = False
    lineset.select_contour = False
    lineset.select_crease = False
    lineset.select_edge_mark = False
    lineset.select_external_contour = True  # Only the outermost silhouette
    lineset.select_material_boundary = False
    lineset.select_suggestive_contour = False
    lineset.select_ridge_valley = False
    # Line style: black, 2px wide
    style = lineset.linestyle
    style.color = (0, 0, 0)
    style.thickness = 1.0

    # Set world background to gray so we can see the character
    world = bpy.data.worlds.get('World')
    if not world:
        world = bpy.data.worlds.new('World')
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
        bg.inputs['Strength'].default_value = 1.0

def render_frame(frame_num):
    bpy.context.scene.frame_set(frame_num)
    bpy.ops.render.render(write_still=True)
    print(f"Rendered frame {frame_num}")

def main():
    argv = sys.argv
    try:
        idx = argv.index("--")
        args = argv[idx + 1:]
    except ValueError:
        print("Usage: blender --background --python test_render_animation.py -- input.fbx output.png [frame]")
        sys.exit(1)

    fbx_path = os.path.abspath(args[0])
    output_path = os.path.abspath(args[1])
    frame = int(args[2]) if len(args) > 2 else 1

    print(f"\n=== Test Render ===")
    print(f"Input:  {fbx_path}")
    print(f"Output: {output_path}")
    print(f"Frame:  {frame}")

    clear_scene()
    import_fbx(fbx_path)
    debug_and_fix_materials()
    setup_camera_and_light()
    setup_render(output_path)
    render_frame(frame)

    scene = bpy.context.scene
    print(f"\nAnimation range: {scene.frame_start} to {scene.frame_end}")
    print(f"=== Done! ===")

if __name__ == "__main__":
    main()
