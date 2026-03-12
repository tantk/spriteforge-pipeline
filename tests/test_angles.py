"""Render multiple camera angles for comparison."""
import bpy
import sys
import os
import math

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def import_fbx(fbx_path):
    bpy.ops.import_scene.fbx(filepath=fbx_path)

def setup_render():
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.3, 0.3, 0.3, 1.0)
    # Sun light
    light_data = bpy.data.lights.new("Sun", 'SUN')
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new("Sun", light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.rotation_euler = (math.radians(45), 0, math.radians(30))

def render_with_angle(angle_h, angle_v, output_path, label):
    # Remove old camera
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA' or obj.name == 'CamTarget':
            bpy.data.objects.remove(obj, do_unlink=True)

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 1.75
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    char_center_z = 0.7
    cam_distance = 5.0
    ah = math.radians(angle_h)
    av = math.radians(angle_v)
    cam_obj.location = (
        -cam_distance * math.sin(ah),
        -cam_distance * math.cos(ah),
        char_center_z + cam_distance * math.sin(av),
    )

    track = cam_obj.constraints.new(type='TRACK_TO')
    target = bpy.data.objects.new("CamTarget", None)
    target.location = (0, 0, char_center_z)
    bpy.context.scene.collection.objects.link(target)
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'

    bpy.context.scene.frame_set(15)
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    print(f"  {label}: H={angle_h}, V={angle_v} -> {output_path}")

fbx_path = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
out_dir = os.path.abspath(sys.argv[sys.argv.index("--") + 2])

clear_scene()
import_fbx(fbx_path)
setup_render()

angles = [
    (20, 8, "A_front_slight"),     # Nearly front, slight left
    (35, 12, "B_34_classic"),      # Classic 3/4
    (45, 15, "C_45_degree"),       # 45 degree
    (30, 5, "D_30_low"),           # 30 degrees, low elevation
    (40, 20, "E_40_high"),         # 40 degrees, higher up
    (25, 10, "F_25_subtle"),       # Subtle angle
]

for ah, av, label in angles:
    render_with_angle(ah, av, os.path.join(out_dir, f"{label}.png"), label)

print("\nDone! Check the output folder.")
