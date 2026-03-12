"""Debug: Check texture details from VRM."""
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

for img in bpy.data.images:
    print(f"Image: {img.name}")
    print(f"  Size: {img.size[0]}x{img.size[1]}")
    print(f"  Channels: {img.channels}")
    print(f"  Color space: {img.colorspace_settings.name}")
    print(f"  File format: {img.file_format}")
    print(f"  Packed: {img.packed_file is not None}")
    print(f"  Filepath: {img.filepath}")
