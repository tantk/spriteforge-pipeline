bl_info = {
    "name": "Sprite Pipeline",
    "author": "loracomp3",
    "version": (3, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool",
    "description": "Sprite sheet pipeline: camera tracking, animation import, render settings",
    "category": "Interface",
}

import bpy
import os

PIPELINE_CAM = {
    'location': (-2.4063, -0.3171, 0.6149),
    'rotation': (1.6393, -0.0000027, -1.4561),
    'lens': 50.0,
    'sensor_width': 36.0,
    'sensor_fit': 'AUTO',
}


def setup_camera_tracking(cam, armature):
    """Add Copy Location constraint so camera follows character XY movement."""
    # Remove existing copy location constraints
    for c in list(cam.constraints):
        if c.type == 'COPY_LOCATION':
            cam.constraints.remove(c)

    constraint = cam.constraints.new('COPY_LOCATION')
    constraint.name = "Track Character"
    constraint.target = armature
    constraint.use_x = True
    constraint.use_y = True
    constraint.use_z = False   # Keep camera height fixed, character bobs naturally
    constraint.use_offset = True  # Add character movement to camera's own position


class PIPELINE_OT_reset_camera(bpy.types.Operator):
    bl_idname = "pipeline.reset_camera"
    bl_label = "Pipeline Camera"
    bl_description = "Reset camera to pipeline angle with character tracking"

    def execute(self, context):
        cam = context.scene.camera
        if not cam:
            self.report({'ERROR'}, "No active camera")
            return {'CANCELLED'}

        cam.location = PIPELINE_CAM['location']
        cam.rotation_euler = PIPELINE_CAM['rotation']
        cam.data.type = 'PERSP'
        cam.data.lens = PIPELINE_CAM['lens']
        cam.data.sensor_width = PIPELINE_CAM['sensor_width']
        cam.data.sensor_height = 24.0
        cam.data.sensor_fit = PIPELINE_CAM['sensor_fit']

        context.scene.render.resolution_x = 256
        context.scene.render.resolution_y = 256

        # Set up camera tracking if armature exists
        arm = None
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                arm = obj
                break
        if arm:
            setup_camera_tracking(cam, arm)

        # Snap viewport to camera
        area = context.area
        if area and area.type == 'VIEW_3D':
            area.spaces[0].region_3d.view_perspective = 'CAMERA'
        else:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.region_3d.view_perspective = 'CAMERA'
                            break
                    break

        self.report({'INFO'}, "Camera reset with character tracking")
        return {'FINISHED'}


class PIPELINE_OT_import_animation(bpy.types.Operator):
    bl_idname = "pipeline.import_animation"
    bl_label = "Import Animation"
    bl_description = "Import Mixamo FBX and add to NLA. Camera tracks character automatically"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.fbx', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        # Find existing main armature
        main_arm = None
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE' and not obj.name.endswith('.001'):
                main_arm = obj
                break

        # Import the FBX (no root motion stripping — camera tracks instead)
        bpy.ops.import_scene.fbx(filepath=self.filepath)

        # Find the newly imported armature
        new_arm = None
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE' and obj.animation_data and obj.animation_data.action:
                if main_arm is None or obj.name != main_arm.name:
                    new_arm = obj
                    break

        if not new_arm or not new_arm.animation_data or not new_arm.animation_data.action:
            self.report({'ERROR'}, "No animation found in imported FBX")
            return {'CANCELLED'}

        # Get animation name from filename
        anim_name = os.path.splitext(os.path.basename(self.filepath))[0]
        action = new_arm.animation_data.action
        action.name = anim_name

        if main_arm is None:
            # First import — this becomes our main armature
            main_arm = new_arm
            main_arm.animation_data.action = None
            track = main_arm.animation_data.nla_tracks.new()
            track.name = anim_name
            nla_strip = track.strips.new(anim_name, 1, action)
            nla_strip.extrapolation = 'NOTHING'

            # Set up camera tracking
            cam = context.scene.camera
            if cam:
                setup_camera_tracking(cam, main_arm)

            self.report({'INFO'}, f"Imported '{anim_name}' (frames 1-{int(action.frame_range[1])})")
        else:
            # Fix slot identifier to match main armature
            for slot in action.slots:
                slot.identifier = "OB" + main_arm.name

            # Find where to place the new strip
            max_end = 0
            for track in main_arm.animation_data.nla_tracks:
                for s in track.strips:
                    if s.frame_end > max_end:
                        max_end = s.frame_end
            start_frame = int(max_end) + 4

            # Add to main armature NLA
            track = main_arm.animation_data.nla_tracks.new()
            track.name = anim_name
            nla_strip = track.strips.new(anim_name, start_frame, action)
            nla_strip.extrapolation = 'NOTHING'

            # Delete duplicate character
            objects_to_delete = [new_arm] + list(new_arm.children)
            bpy.ops.object.select_all(action='DESELECT')
            for obj in objects_to_delete:
                obj.select_set(True)
            bpy.ops.object.delete()

            # Update scene end frame
            new_end = int(nla_strip.frame_end)
            if new_end > context.scene.frame_end:
                context.scene.frame_end = new_end

            self.report({'INFO'}, f"Imported '{anim_name}' (frames {start_frame}-{int(nla_strip.frame_end)})")

        return {'FINISHED'}


class PIPELINE_OT_custom_camera(bpy.types.Operator):
    bl_idname = "pipeline.custom_camera"
    bl_label = "Custom Camera"
    bl_description = "Set up ortho camera with per-frame bounding box tracking"

    def execute(self, context):
        import math
        import time

        scene = context.scene
        cam = scene.camera
        if not cam:
            self.report({'ERROR'}, "No active camera")
            return {'CANCELLED'}

        arm = None
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                arm = obj
                break
        if not arm:
            self.report({'ERROR'}, "No armature found")
            return {'CANCELLED'}

        meshes = [c for c in arm.children if c.type == 'MESH']
        if not meshes:
            self.report({'ERROR'}, "No meshes found under armature")
            return {'CANCELLED'}

        # Remove any constraints
        for c in list(cam.constraints):
            cam.constraints.remove(c)

        # Clear existing keyframes
        if cam.animation_data:
            cam.animation_data_clear()
        if cam.data.animation_data:
            cam.data.animation_data_clear()

        # Set ortho camera facing +X
        cam.data.type = 'ORTHO'
        cam.rotation_euler = (math.pi / 2, 0, -math.pi / 2)

        CAM_DEPTH = -2.4
        CAM_PADDING = 1.15

        # Bake per-frame keyframes from bounding box
        t = time.time()
        for f in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(f)
            depsgraph = context.evaluated_depsgraph_get()

            min_y = float('inf')
            max_y = float('-inf')
            min_z = float('inf')
            max_z = float('-inf')

            for mesh_obj in meshes:
                eval_obj = mesh_obj.evaluated_get(depsgraph)
                mesh_data = eval_obj.to_mesh()
                for v in mesh_data.vertices:
                    world_co = eval_obj.matrix_world @ v.co
                    min_y = min(min_y, world_co.y)
                    max_y = max(max_y, world_co.y)
                    min_z = min(min_z, world_co.z)
                    max_z = max(max_z, world_co.z)
                eval_obj.to_mesh_clear()

            center_y = (min_y + max_y) / 2
            center_z = (min_z + max_z) / 2
            ortho_scale = max(max_y - min_y, max_z - min_z) * CAM_PADDING

            cam.location = (CAM_DEPTH, center_y, center_z)
            cam.data.ortho_scale = ortho_scale

            cam.keyframe_insert(data_path='location', frame=f)
            cam.data.keyframe_insert(data_path='ortho_scale', frame=f)

        elapsed = time.time() - t

        # Snap viewport to camera
        area = context.area
        if area and area.type == 'VIEW_3D':
            area.spaces[0].region_3d.view_perspective = 'CAMERA'
        else:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.region_3d.view_perspective = 'CAMERA'
                            break
                    break

        self.report({'INFO'}, f"Ortho camera: {scene.frame_end - scene.frame_start + 1} frames baked in {elapsed:.1f}s")
        return {'FINISHED'}


class PIPELINE_PT_panel(bpy.types.Panel):
    bl_label = "Sprite Pipeline"
    bl_idname = "PIPELINE_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        layout.operator("pipeline.reset_camera", icon='CAMERA_DATA')
        layout.operator("pipeline.import_animation", icon='IMPORT')
        layout.separator()
        layout.operator("pipeline.custom_camera", icon='VIEW_CAMERA')


classes = [
    PIPELINE_OT_reset_camera,
    PIPELINE_OT_import_animation,
    PIPELINE_OT_custom_camera,
    PIPELINE_PT_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
