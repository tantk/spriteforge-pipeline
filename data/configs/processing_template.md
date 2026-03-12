# Sprite Sheet Processing Template

Reusable pipeline for generating sprite sheets from Mixamo animations.
All steps are the same for every sheet — only the config JSON changes.

## Prerequisites
- Blender 5.0 with MCP server running
- Character FBX + animation FBX files from Mixamo (downloaded "With Skin")
- Config JSON in `data/configs/sheet_XX_name.json`
- Render settings in `data/configs/render_settings.json`

## Inputs
- **Config JSON**: defines animations, frame counts, segments, prompt
- **render_settings.json**: camera, lighting, materials, freestyle, dynamic camera params

## Steps

### Step 1: Scene Setup
```
1. Clear scene
2. Import first animation FBX (brings full character mesh + armature)
3. Rename action, fix slot identifier ("OB" + armature.name), push to NLA
4. For each additional animation FBX:
   a. Import FBX
   b. Rename action, fix slot identifier
   c. Push to NLA (start = previous strip end + 4 frame gap)
   d. Set strip.extrapolation = 'NOTHING'
   e. If reversed: strip.use_reverse = True
   f. Delete duplicate armature + meshes from import
5. Clear active action on armature
6. Set scene frame range (1 to last strip end)
```

### Step 2: Camera + Lighting + Render Settings
```
Apply from render_settings.json:
- Camera: PERSP 50mm, sensor 36x24mm, base location (-2.4063, -0.3171, 0.6149),
  rotation (1.6393, -0.0000027, -1.4561)
- Lighting: 3 suns, no shadows
  Key:  energy=4.0, rotation=(30deg, 0, -20deg)
  Fill: energy=2.5, rotation=(40deg, 0, 160deg)
  Rim:  energy=1.5, rotation=(60deg, 0, 180deg)
- Render: EEVEE 256x256, Standard color management, white BG, film_transparent=False
- Freestyle: external_contour only, black, 1px
- Materials: All Principled BSDF → Specular IOR Level=0, Roughness=1
- World: white background, strength=1.0
```

### Step 3: Spring Bone Hair Physics (first pass)
```
VRoid characters only (skip for Mixamo built-in characters).
- Detect J_Sec_Hair1_* bone chains
- Params: stiffness=0.3, damping=0.2, reaction=2.0, max_deg=25
- Simulate spring dynamics reacting to head movement
- Bake keyframes → push to SpringBoneHair NLA track
```

### Step 4: Root Motion Stripping (conditional)
```
ONLY for extreme movement animations (rolls, flips, falls, death).
Skip for idle, walk, punch, kick, block, standing combos.

If needed:
1. Remove Copy Location constraint from camera (if any)
2. For each frame, compute Hips bone world XY position
3. Bake inverse offset into armature location:
   armature.location.xy = -(hips_xy - reference_xy)
4. Keep Z natural (vertical bob preserved)
5. Push offset keyframes to RootMotionStrip NLA track
```

### Step 5: Dynamic Camera (mesh-vertex based, iterative)
```
ALWAYS run this step. Prevents "teleport" between animations.

1. Remove any Copy Location constraint from camera
2. Reset camera to base position
3. For each frame in range:
   a. Reset camera to base position
   b. Evaluate deformed Body mesh vertices (every 4th for speed)
   c. Find min/max screen X and Y via world_to_camera_view()
   d. Compute shift:
      - Y: bottom-anchor lowest vertex at 10% from bottom (TARGET_BOTTOM=0.10)
      - X: center character horizontally (center_x=0.50)
      - If top would exceed 90%, center vertically instead
   e. Convert screen-space shift to world-space camera offset:
      offset = cam_local_axis * shift * (sensor_size / focal_length) * distance
   f. Move camera, re-measure, repeat (up to 8 iterations, tolerance < 0.008)
   g. Bake camera location keyframe (LINEAR interpolation)
```

### Step 6: Spring Bone Hair Physics (re-run)
```
Must re-run AFTER dynamic camera — frustum clamp depends on camera position.
Same params as Step 3. Remove old SpringBoneHair track first.
```

### Step 7: Frame Selection
```python
def sample_frames(start, end, count):
    if count == 1: return [round((start + end) / 2)]
    step = (end - start) / (count - 1)
    return [round(start + i * step) for i in range(count)]

# For each animation in config:
#   If segments defined:
#     offset = strip.frame_start - strip.action_frame_start
#     For each segment: sample_frames(action_start + offset, action_end + offset, segment_count)
#   Else:
#     sample_frames(strip.frame_start, strip.frame_end, animation.frames)
#
# Avoid NLA overlap frames (where two strips share the same frame number)
# Total must = 16
```

### Step 8: Render + Assemble
```
1. Set render settings (EEVEE, 256x256, PNG)
2. Hide debug markers (LowestPointMarker, HipsMarker) if present
3. For each of 16 selected frames:
   - scene.frame_set(frame)
   - Render to data/renders/sheet_XX/frame_NN_FFF.png
4. Assemble 4x4 grid → 1024x1024 sprite sheet PNG
5. Generate GIF (150ms per frame, loop=0)
```

### Step 9: Save Scene + Outputs
```
- Save Blender scene: data/scenes/sheet_XX_name.blend
- Sprite sheet: data/renders/sheet_XX_name.png
- GIF: data/renders/sheet_XX_name.gif
- Individual frames: data/renders/sheet_XX/
- Update manifest.json with sheet info, selected frames, status
```

## What Changes Per Sheet
| What | Where |
|------|-------|
| Animation selection + frame counts | Config JSON |
| Segment definitions + descriptions | Config JSON |
| Prompt for LoRA training | Config JSON |
| Root motion stripping (yes/no) | Step 4 — only for extreme movement |

Everything else is identical.

## Verified On
- Sheet 01: Idle + Walk (3 animations, segments)
- Sheet 02: Run Forward + Run To Rolling (2 animations, 7 segments, root motion strip)
- Sheet 03: Left Right Hook (2 animations, even spread, no segments)
