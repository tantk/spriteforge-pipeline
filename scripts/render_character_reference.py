"""
Render 1024x1024 character reference images (idle frame 1) for all characters.
Uses the same camera/lighting as sprite sheets but at 1024x1024 resolution.
"""
import bpy
import os
import sys
import types
import time

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

BASE_DIR = r"C:\dev\loracomp3"

# Load render pipeline
_ns = {"__name__": "render_sheet"}
exec(open(os.path.join(BASE_DIR, "scripts", "render_sheet.py")).read(), _ns)

with open(os.path.join(BASE_DIR, "scripts", "camera_hybrid.py")) as f:
    cam_hybrid = types.ModuleType("camera_hybrid")
    exec(f.read(), cam_hybrid.__dict__)

CHAR_DIR = os.path.join(BASE_DIR, "data", "characters", "AvatarSample_B")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "renders_final")

# Characters to render
CHARACTERS = [
    "original_character.vrm",
    "army_man.vrm",
    "blackdress_girl.vrm",
    "blackshirt_man.vrm",
    "bluedress_girl.vrm",
    "greenhair_girl.vrm",
    "pinkhair_boy.vrm",
    "darkskin_girl.vrm",
    "pinkskirt_girl.vrm",
]

# Filter by --char if provided
if "--char" in argv:
    char_filter = argv[argv.index("--char") + 1]
    CHARACTERS = [c for c in CHARACTERS if c == char_filter]

for char_vrm in CHARACTERS:
    char_name = os.path.splitext(char_vrm)[0]
    out_path = os.path.join(OUTPUT_DIR, char_name, "character_reference.png")
    
    if os.path.exists(out_path):
        print(f"SKIP (exists): {char_name}")
        continue

    print(f"\n=== Rendering reference for {char_name} ===")
    t0 = time.time()

    # Clean scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for b in list(bpy.data.meshes): bpy.data.meshes.remove(b)
    for b in list(bpy.data.armatures): bpy.data.armatures.remove(b)
    for b in list(bpy.data.actions): bpy.data.actions.remove(b)
    for b in list(bpy.data.cameras): bpy.data.cameras.remove(b)
    for b in list(bpy.data.lights): bpy.data.lights.remove(b)
    for b in list(bpy.data.materials): bpy.data.materials.remove(b)

    # Import VRM
    vrm_path = os.path.join(CHAR_DIR, char_vrm)
    bpy.ops.import_scene.vrm(filepath=vrm_path)
    for obj in list(bpy.data.objects):
        if obj.type == 'EMPTY':
            bpy.data.objects.remove(obj, do_unlink=True)

    armature = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    meshes = [c for c in armature.children if c.type == 'MESH']

    # Import Idle FBX for the pose
    animations_dir = os.path.join(BASE_DIR, "data", "characters", char_name, "animations")
    if os.path.isdir(animations_dir):
        idle_fbx = os.path.join(animations_dir, "Idle.fbx")
    else:
        idle_fbx = os.path.join(BASE_DIR, "data", "animations", "Idle.fbx")

    bpy.ops.import_scene.fbx(filepath=idle_fbx)
    for obj in list(bpy.data.objects):
        if obj.type == 'EMPTY':
            bpy.data.objects.remove(obj, do_unlink=True)

    # Find FBX armature and assign action
    fbx_arm = [o for o in bpy.data.objects if o.type == 'ARMATURE' and o != armature][0]
    action = fbx_arm.animation_data.action
    for slot in action.slots:
        slot.identifier = "OB" + armature.name
    if armature.animation_data is None:
        armature.animation_data_create()
    armature.animation_data.action = action

    # Delete FBX armature and its meshes (prevents overlap)
    for child in list(fbx_arm.children):
        bpy.data.objects.remove(child, do_unlink=True)
    bpy.data.objects.remove(fbx_arm, do_unlink=True)
    # Also delete any duplicate meshes (.001 suffix)
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and '.001' in obj.name:
            bpy.data.objects.remove(obj, do_unlink=True)

    # Set to frame 1
    bpy.context.scene.frame_set(1)

    # Setup lighting
    _ns['setup_lighting']()

    # Setup render settings at 1024x1024
    _ns['setup_render_settings']()
    bpy.context.scene.render.resolution_x = 1024
    bpy.context.scene.render.resolution_y = 1024

    # Setup camera
    _state = _ns['_state']
    _state['armature'] = armature
    _state['meshes'] = meshes
    cam_hybrid.setup_camera_hybrid(_state, reference_frame=1)

    # Render
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

    # Delete FBX armature
    bpy.data.objects.remove(fbx_arm, do_unlink=True)

    elapsed = time.time() - t0
    print(f"  Saved: {out_path} ({elapsed:.0f}s)")

print("\nDone!")
import bpy
bpy.ops.wm.quit_blender()
