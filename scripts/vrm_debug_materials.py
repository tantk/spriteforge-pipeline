"""Debug: Print material node info from imported VRM."""
import bpy
import sys
import os
import shutil

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Import
vrm_path = sys.argv[sys.argv.index("--") + 1]
try:
    bpy.ops.import_scene.gltf(filepath=vrm_path)
except:
    glb_path = vrm_path.rsplit('.', 1)[0] + '_temp.glb'
    shutil.copy2(vrm_path, glb_path)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    os.remove(glb_path)

# Dump material info
for mat in bpy.data.materials:
    print(f"\n=== Material: {mat.name} ===")
    if not mat.use_nodes or not mat.node_tree:
        print("  No node tree")
        continue
    for node in mat.node_tree.nodes:
        print(f"  Node: {node.name} (type={node.type}, bl_idname={node.bl_idname})")
        if node.type == 'TEX_IMAGE' and node.image:
            print(f"    Image: {node.image.name} ({node.image.size[0]}x{node.image.size[1]})")
        if node.type == 'BSDF_PRINCIPLED':
            base_color = node.inputs.get('Base Color')
            if base_color:
                print(f"    Base Color: {base_color.default_value[:]}")
                if base_color.links:
                    print(f"    Base Color linked from: {base_color.links[0].from_node.name}")
                else:
                    print(f"    Base Color: NOT LINKED")
        # Print all outputs with links
        for output in node.outputs:
            for link in output.links:
                print(f"    {node.name}.{output.name} -> {link.to_node.name}.{link.to_socket.name}")
