"""Blender script: Convert VRM to Mixamo-ready FBX.

VRM files are GLB files internally, so we import as GLB.
Removes armature (Mixamo needs clean mesh to auto-rig).
Rewires MToon materials to Principled BSDF so textures export with color.

Usage:
  blender --background --python vrm_to_mixamo_fbx.py -- input.vrm output.fbx
"""
import bpy
import sys
import os
import shutil

def clear_scene():
    """Remove all objects from the scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)

def import_vrm_as_glb(vrm_path):
    """Import VRM file by treating it as GLB."""
    try:
        bpy.ops.import_scene.gltf(filepath=vrm_path)
        print(f"Imported {vrm_path} as glTF/GLB")
        return True
    except Exception as e:
        print(f"Direct import failed: {e}")

    # If that fails, copy as .glb and try again
    glb_path = vrm_path.rsplit('.', 1)[0] + '_temp.glb'
    shutil.copy2(vrm_path, glb_path)
    try:
        bpy.ops.import_scene.gltf(filepath=glb_path)
        print(f"Imported {glb_path} as GLB copy")
        return True
    except Exception as e:
        print(f"GLB import also failed: {e}")
        return False
    finally:
        if os.path.exists(glb_path):
            os.remove(glb_path)

def print_scene_info():
    """Print what's in the scene after import."""
    armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    others = [obj for obj in bpy.data.objects if obj.type not in ('ARMATURE', 'MESH')]
    print(f"Scene: {len(armatures)} armature(s), {len(meshes)} mesh(es), {len(others)} other(s)")
    for arm in armatures:
        print(f"  Armature: {arm.name} ({len(arm.data.bones)} bones)")
    for mesh in meshes:
        print(f"  Mesh: {mesh.name} ({len(mesh.data.vertices)} verts)")

def rename_bones_for_mixamo():
    """Rename VRM bones to Mixamo naming convention."""
    VRM_TO_MIXAMO = {
        "J_Bip_C_Hips": "Hips",
        "J_Bip_C_Spine": "Spine",
        "J_Bip_C_Chest": "Spine1",
        "J_Bip_C_UpperChest": "Spine2",
        "J_Bip_C_Neck": "Neck",
        "J_Bip_C_Head": "Head",
        "J_Bip_L_Shoulder": "LeftShoulder",
        "J_Bip_L_UpperArm": "LeftArm",
        "J_Bip_L_LowerArm": "LeftForeArm",
        "J_Bip_L_Hand": "LeftHand",
        "J_Bip_L_Thumb1": "LeftHandThumb1",
        "J_Bip_L_Thumb2": "LeftHandThumb2",
        "J_Bip_L_Thumb3": "LeftHandThumb3",
        "J_Bip_L_Index1": "LeftHandIndex1",
        "J_Bip_L_Index2": "LeftHandIndex2",
        "J_Bip_L_Index3": "LeftHandIndex3",
        "J_Bip_L_Middle1": "LeftHandMiddle1",
        "J_Bip_L_Middle2": "LeftHandMiddle2",
        "J_Bip_L_Middle3": "LeftHandMiddle3",
        "J_Bip_L_Ring1": "LeftHandRing1",
        "J_Bip_L_Ring2": "LeftHandRing2",
        "J_Bip_L_Ring3": "LeftHandRing3",
        "J_Bip_L_Little1": "LeftHandPinky1",
        "J_Bip_L_Little2": "LeftHandPinky2",
        "J_Bip_L_Little3": "LeftHandPinky3",
        "J_Bip_R_Shoulder": "RightShoulder",
        "J_Bip_R_UpperArm": "RightArm",
        "J_Bip_R_LowerArm": "RightForeArm",
        "J_Bip_R_Hand": "RightHand",
        "J_Bip_R_Thumb1": "RightHandThumb1",
        "J_Bip_R_Thumb2": "RightHandThumb2",
        "J_Bip_R_Thumb3": "RightHandThumb3",
        "J_Bip_R_Index1": "RightHandIndex1",
        "J_Bip_R_Index2": "RightHandIndex2",
        "J_Bip_R_Index3": "RightHandIndex3",
        "J_Bip_R_Middle1": "RightHandMiddle1",
        "J_Bip_R_Middle2": "RightHandMiddle2",
        "J_Bip_R_Middle3": "RightHandMiddle3",
        "J_Bip_R_Ring1": "RightHandRing1",
        "J_Bip_R_Ring2": "RightHandRing2",
        "J_Bip_R_Ring3": "RightHandRing3",
        "J_Bip_R_Little1": "RightHandPinky1",
        "J_Bip_R_Little2": "RightHandPinky2",
        "J_Bip_R_Little3": "RightHandPinky3",
        "J_Bip_L_UpperLeg": "LeftUpLeg",
        "J_Bip_L_LowerLeg": "LeftLeg",
        "J_Bip_L_Foot": "LeftFoot",
        "J_Bip_L_ToeBase": "LeftToeBase",
        "J_Bip_R_UpperLeg": "RightUpLeg",
        "J_Bip_R_LowerLeg": "RightLeg",
        "J_Bip_R_Foot": "RightFoot",
        "J_Bip_R_ToeBase": "RightToeBase",
    }

    for obj in bpy.data.objects:
        if obj.type != 'ARMATURE':
            continue
        renamed = 0
        for bone in obj.data.bones:
            if bone.name in VRM_TO_MIXAMO:
                new_name = VRM_TO_MIXAMO[bone.name]
                bone.name = new_name
                renamed += 1
        print(f"Renamed {renamed} bones to Mixamo convention")

        # Also remove non-essential bones (hair, skirt, bust physics)
        # These confuse Mixamo's skeleton mapper
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        remove_prefixes = ('J_Sec_', 'J_Adj_')
        removed = 0
        for ebone in list(obj.data.edit_bones):
            if any(ebone.name.startswith(p) for p in remove_prefixes):
                obj.data.edit_bones.remove(ebone)
                removed += 1
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"Removed {removed} non-essential bones (hair/physics/adjust)")

def remove_armature_keep_mesh():
    """Remove armature but keep mesh frozen in T-pose."""
    bpy.ops.object.select_all(action='DESELECT')

    armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']

    print(f"Stripping {len(armatures)} armature(s), keeping {len(meshes)} mesh(es)")

    # Remove shape keys first (they block modifier_apply)
    for mesh_obj in meshes:
        if mesh_obj.data.shape_keys:
            print(f"  Removing shape keys from {mesh_obj.name} ({len(mesh_obj.data.shape_keys.key_blocks)} keys)")
            # Use data API to clear shape keys (avoids operator context issues)
            mesh_obj.shape_key_clear()

    # Apply armature modifiers on meshes (freezes T-pose shape)
    for mesh_obj in meshes:
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)
        for mod in list(mesh_obj.modifiers):
            if mod.type == 'ARMATURE':
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    print(f"  Applied armature modifier on {mesh_obj.name}")
                except Exception as e:
                    print(f"  Could not apply modifier on {mesh_obj.name}: {e}, removing")
                    mesh_obj.modifiers.remove(mod)
        mesh_obj.select_set(False)

    # Clear parent relationships (meshes are parented to armature)
    for mesh_obj in meshes:
        mesh_obj.select_set(True)
    if meshes:
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.select_all(action='DESELECT')

    # Delete armatures
    for arm in armatures:
        arm.select_set(True)
    bpy.ops.object.delete()

    # Delete empties, lights, cameras
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.data.objects:
        if obj.type in ('EMPTY', 'LIGHT', 'CAMERA'):
            obj.select_set(True)
    bpy.ops.object.delete()

    # Also remove all vertex groups (bone weights) from meshes
    remaining = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    for mesh_obj in remaining:
        mesh_obj.vertex_groups.clear()

    print(f"  Remaining: {len(remaining)} clean mesh(es), no armature, no vertex groups")

def fix_materials_for_fbx():
    """Minimal fix: add Principled BSDF connected to texture, swap output.

    Keeps all existing nodes intact — just adds a new Principled BSDF
    and redirects the Material Output to use it.
    """
    fixed = 0
    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.node_tree:
            continue

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Find the image texture node
        tex_node = None
        for node in nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                tex_node = node
                break
        if not tex_node:
            continue

        # Find Material Output
        output_node = None
        for node in nodes:
            if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
                output_node = node
                break
        if not output_node:
            for node in nodes:
                if node.type == 'OUTPUT_MATERIAL':
                    output_node = node
                    break
        if not output_node:
            continue

        # Add Principled BSDF (don't remove anything)
        principled = nodes.new('ShaderNodeBsdfPrincipled')
        principled.location = (300, 300)

        # Connect texture -> Principled BSDF
        links.new(tex_node.outputs['Color'], principled.inputs['Base Color'])
        links.new(tex_node.outputs['Alpha'], principled.inputs['Alpha'])

        # Remove ONLY the existing Surface link on output, replace with Principled
        for link in list(links):
            if link.to_node == output_node and link.to_socket.name == 'Surface':
                links.remove(link)
        links.new(principled.outputs['BSDF'], output_node.inputs['Surface'])

        fixed += 1
        print(f"  Fixed material: {mat.name}")

    print(f"Rewired {fixed} materials to Principled BSDF")

def export_fbx(output_path):
    """Export as FBX with embedded textures for Mixamo."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.fbx(
        filepath=output_path,
        use_selection=True,
        apply_scale_options='FBX_SCALE_ALL',
        path_mode='COPY',
        embed_textures=True,
        mesh_smooth_type='FACE',
        add_leaf_bones=False,
        axis_forward='-Z',
        axis_up='Y',
    )
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Exported FBX to {output_path} ({size_mb:.1f} MB)")

def main():
    argv = sys.argv
    try:
        idx = argv.index("--")
        args = argv[idx + 1:]
    except ValueError:
        print("Usage: blender --background --python vrm_to_mixamo_fbx.py -- input.vrm output.fbx")
        sys.exit(1)

    if len(args) < 2:
        print("Usage: blender --background --python vrm_to_mixamo_fbx.py -- input.vrm output.fbx")
        sys.exit(1)

    vrm_path = os.path.abspath(args[0])
    fbx_path = os.path.abspath(args[1])

    print(f"\n=== VRM to Mixamo FBX Converter ===")
    print(f"Input:  {vrm_path}")
    print(f"Output: {fbx_path}")

    clear_scene()

    if not import_vrm_as_glb(vrm_path):
        print("ERROR: Could not import VRM file")
        sys.exit(1)

    print_scene_info()

    # Fix materials: add Principled BSDF for color (minimal, keeps everything else)
    fix_materials_for_fbx()

    # Export clean mesh with embedded textures
    export_fbx(fbx_path)

    print("\n=== Done! Upload the FBX to Mixamo for auto-rigging ===")

if __name__ == "__main__":
    main()
