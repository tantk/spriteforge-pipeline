"""Debug: Print all bone names from VRM armature."""
import bpy
import sys
import shutil
import os

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

vrm_path = sys.argv[sys.argv.index("--") + 1]
try:
    bpy.ops.import_scene.gltf(filepath=vrm_path)
except:
    glb_path = vrm_path.rsplit('.', 1)[0] + '_temp.glb'
    shutil.copy2(vrm_path, glb_path)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    os.remove(glb_path)

for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        print(f"\nArmature: {obj.name} ({len(obj.data.bones)} bones)")
        for bone in obj.data.bones:
            parent = bone.parent.name if bone.parent else "ROOT"
            print(f"  {bone.name}  (parent: {parent})")
