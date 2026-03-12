# Qwen-Image LoRA Competition Entry

**Track:** Track 1 "AI for Production" → "Design Efficiency Tools"
**Competition Deadline:** March 18, 2026
**Base Model:** Qwen/Qwen-Image-Edit-2509
**Training Platform:** ModelScope Civision

---

## Current Concept: 3D Animation → 2D Pixel Art Sprite Sheets

Train a LoRA that converts 3D rendered character animation frames into pixel art sprite sheets — useful for indie game developers who want to quickly generate sprite assets from 3D models.

### Training Data Format
- **Input:** 3D rendered sprite sheet (1024x1024, 4x4 grid of 256x256 frames)
- **Output:** Pixel art sprite sheet (same layout)
- **Target:** ~50 training pairs (5 characters x 10 sprite sheets each)

### Pipeline Overview

```
VRoid Studio → VRM → FBX (material fix) → Mixamo (auto-rig + animations)
    → Blender (import, NLA, camera, hair physics, render)
        → Assemble 16 frames into 1024x1024 sprite sheet + GIF
            → Pixel art conversion (TODO)
                → Training pairs
```

---

## Status

- [x] Character creation (VRoid Studio)
- [x] VRM → FBX conversion script (material fix for Mixamo)
- [x] Mixamo auto-rig + animation download (47 animations)
- [x] Blender render pipeline (camera, lighting, outline, background)
- [x] Spring bone hair physics
- [x] Blender addon v3.0 (`blender_sprite_pipeline_addon.py`)
- [x] **Sheet 01: Idle + Walk** — rendered
- [x] **Sheet 02: Run Forward + Run To Rolling** — rendered
- [x] **Sheet 03: Left Right Hook** — rendered
- [x] **Sheet 04: Hook + Right Hook** — rendered
- [x] **Sheet 05: Quad Punch** — rendered (segment-based frame selection)
- [x] **Sheet 06: Illegal Knee + Roundhouse Kick** — re-rendering (segment-based + expressions)
- [x] **Sheet 07: Kicking** — rendered
- [ ] Sheets 08-10 (Hit Reactions, Death/Recovery, Movement)
- [ ] Pixel art conversion pipeline
- [ ] Additional characters (target: 5 total, mix of VRoid + Mixamo)
- [ ] Package training pairs
- [ ] Train LoRA
- [ ] Evaluate & submit

---

## Agent Quick-Start: How to Create a Sprite Sheet

This section is a complete guide for an AI agent to create a new sprite sheet from scratch using Blender MCP. Follow these steps exactly.

### Prerequisites
- Blender 5.0 open with MCP addon connected
- Character FBX already imported (or import via steps below)

### Step 1: Choose Animations

Pick 1-3 animations from the 47 available Mixamo FBX files in `data/animations/`. Decide:
- How many frames each animation gets (total must = 16 for 4x4 grid)
- Whether any need reversed playback
- Whether animations have extreme movement (rolls, flips → needs root motion stripping)

### Step 2: Create Config JSON

Save to `data/configs/sheet_XX_name.json`. The config defines everything needed to reproduce the sheet.

```json
{
    "name": "Illegal Knee + Roundhouse Kick",
    "sheet_index": 6,
    "prompt": "A 4x4 sprite sheet of a character performing [describe all animations and their phases].",
    "animations": [
        {
            "name": "Illegal Knee",
            "fbx": "Illegal Knee.fbx",
            "frames": 8,
            "reversed": false,
            "description": "Illegal knee strike driving upward",
            "segments": [
                {"action_frames": [1, 12], "pick": 2, "description": "Wind-up / stance"},
                {"action_frames": [13, 18], "pick": 2, "description": "Knee driving upward", "expression": "surprised"},
                {"action_frames": [19, 20], "pick": 1, "description": "Peak impact", "expression": "surprised"},
                {"action_frames": [21, 25], "pick": 2, "description": "Follow-through"},
                {"action_frames": [26, 31], "pick": 1, "description": "Recovery"}
            ]
        }
    ],
    "total_frames": 16,
    "grid": "4x4",
    "resolution": "1024x1024",
    "frame_size": "256x256"
}
```

**Config rules:**
- Each animation has `segments` with `action_frames` [start, end], `pick` (number of frames to select from this segment), and `description`
- Optional `"expression": "surprised"` on segments where the character should show emotion (impact frames, shouting, etc.)
- `action_frames` are frame numbers from the FBX file (check via Blender import)
- Sum of all `pick` values across all animations must = 16
- The `prompt` field is a natural language description for LoRA training
- Segment descriptions should describe the character's **visible pose and body position**

### Step 3: Blender Scene Setup via MCP

Execute each step as a separate `execute_blender_code` call:

#### 3a. Open/create scene and import first animation FBX
```python
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
# Import first animation FBX (brings character mesh + armature + animation)
bpy.ops.import_scene.fbx(filepath=r"C:\dev\loracomp3\data\animations\AnimName.fbx")
# CRITICAL: Delete ALL empties immediately (prevents Freestyle crash)
for obj in list(bpy.data.objects):
    if obj.type == 'EMPTY':
        bpy.data.objects.remove(obj, do_unlink=True)
```

#### 3b. Import additional animation FBXs
```python
# Import second animation
bpy.ops.import_scene.fbx(filepath=r"C:\dev\loracomp3\data\animations\AnimName2.fbx")
# CRITICAL: Delete ALL duplicate objects from second import
# (keeps only first armature, first set of meshes)
# Delete duplicate armature, meshes, AND empties
for obj in list(bpy.data.objects):
    if obj.type == 'EMPTY':
        bpy.data.objects.remove(obj, do_unlink=True)
# Delete the second armature (usually named "Armature.001")
dup_arm = bpy.data.objects.get('Armature.001')
if dup_arm:
    bpy.data.objects.remove(dup_arm, do_unlink=True)
# Delete duplicate meshes (Body.001, Face.001, Hair.001)
for name in ['Body.001', 'Face.001', 'Hair.001']:
    obj = bpy.data.objects.get(name)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)
```

#### 3c. Set up NLA strips
```python
arm = bpy.data.objects['Armature']
# Each imported animation becomes an action
# Push actions to NLA tracks with gaps between them
# Example: anim1 at frames 1-54, anim2 at frames 58-108 (4-frame gap)
# Set strip.extrapolation = 'NOTHING' on all strips (prevents T-pose bleed)
```

#### 3d. Fix VRM materials (if character came from VRoid)
```python
# VRM materials need: Output Surface link swap only
# Don't rebuild — that breaks Mixamo skeleton mapping
for mat in bpy.data.materials:
    if not mat.node_tree: continue
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.inputs['Specular IOR Level'].default_value = 0.0
            node.inputs['Roughness'].default_value = 1.0
```

### Step 4: Camera Setup (CRITICAL — read carefully)

**Always use orthographic dynamic camera.** Never use Copy Location constraint or perspective camera.

```python
import bpy, math

cam_data = bpy.data.cameras.new("Camera")
cam_data.type = 'ORTHO'
cam_obj = bpy.data.objects.new("Camera", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# CRITICAL: Camera rotation must be (pi/2, 0, -pi/2) to look along +X
# (pi/2, 0, +pi/2) looks along -X and renders BLANK FRAMES)
cam_obj.rotation_euler = (math.pi/2, 0, -math.pi/2)
```

**Dynamic camera algorithm (direct bounding box method):**
```python
arm = bpy.data.objects['Armature']
meshes = [c for c in arm.children if c.type == 'MESH']
DEPTH = -2.4    # Camera X position (negative, looking along +X towards character at X≈0)
PADDING = 1.15  # 15% padding around character

for f in range(scene_start, scene_end + 1):
    scene.frame_set(f)
    depsgraph = bpy.context.evaluated_depsgraph_get()

    min_y, max_y = float('inf'), float('-inf')
    min_z, max_z = float('inf'), float('-inf')

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
    ortho_scale = max(max_y - min_y, max_z - min_z) * PADDING

    cam_obj.location = (DEPTH, center_y, center_z)
    cam_obj.data.ortho_scale = ortho_scale
    cam_obj.keyframe_insert(data_path='location', frame=f)
    cam_obj.data.keyframe_insert(data_path='ortho_scale', frame=f)
```

**Camera coordinate system:**
- Camera looks along **+X** (world)
- Screen horizontal = **world Y**
- Screen vertical = **world Z**
- `cam.location = (DEPTH, center_y, center_z)` where DEPTH is negative

**Why direct method (not iterative)?** The old iterative approach (world_to_camera_view, 8 iterations) was unreliable — accumulated errors and complex convergence. The direct method computes the exact bounding box in world space and sets camera position/scale in one pass. No iteration needed.

### Step 5: Lighting Setup
```python
import math
for name, energy, rot in [
    ("Key", 4.0, (30, 0, -20)),
    ("Fill", 2.5, (40, 0, 160)),
    ("Rim", 1.5, (60, 0, 180)),
]:
    light = bpy.data.lights.new(f"Sun_{name}", 'SUN')
    light.energy = energy
    light.use_shadow = False
    obj = bpy.data.objects.new(f"Sun_{name}", light)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_euler = tuple(math.radians(a) for a in rot)
```

### Step 6: Render Settings
```python
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'  # NOT BLENDER_EEVEE_NEXT in Blender 5.0
scene.render.resolution_x = 256
scene.render.resolution_y = 256
scene.render.film_transparent = False
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.view_settings.view_transform = 'Standard'  # NOT Filmic

# White background
world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
bg.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
bg.inputs['Strength'].default_value = 1.0

# Freestyle outline (1px black, external contour only)
scene.render.use_freestyle = True
vl = scene.view_layers[0]
vl.use_freestyle = True
vl.freestyle_settings.sphere_radius = 0  # CRITICAL: prevents crash
ls = vl.freestyle_settings.linesets[0]
ls.select_silhouette = False
ls.select_border = False
ls.select_contour = False
ls.select_crease = False
ls.select_edge_mark = False
ls.select_external_contour = True
ls.select_material_boundary = False
ls.linestyle.color = (0, 0, 0)
ls.linestyle.thickness = 1.0
```

### Step 7: Spring Bone Hair Physics (VRoid characters only)

Run **AFTER** camera setup. Hair physics depends on camera position for frustum clamping.

```python
# Find hair chains: bones starting with J_Sec_Hair1_*
# Simulate spring dynamics: stiffness=0.3, damping=0.2, reaction=2.0, max_deg=45.0
# See scripts/test_spring_bones.py for full implementation
# Key: for NLA-based animations, pass end_frame explicitly (don't rely on action.frame_range)
# Push result to NLA track with blend_type='ADD':
track = arm.animation_data.nla_tracks.new()
track.name = 'SpringBoneHair'
strip = track.strips.new('SpringBoneHair', 1, action)
strip.blend_type = 'ADD'
arm.animation_data.action = None  # Clear active action so NLA takes over
```

### Step 8: Select Frames from Segments

```python
def sample_frames(start, end, count):
    """Pick count evenly-spaced frames from [start, end] inclusive."""
    if count == 1:
        return [round((start + end) / 2)]
    step = (end - start) / (count - 1)
    return [round(start + i * step) for i in range(count)]

# For each animation's segments, convert action frames to scene frames:
offset = strip.frame_start - strip.action_frame_start
for seg in animation['segments']:
    scene_start = seg['action_frames'][0] + offset
    scene_end = seg['action_frames'][1] + offset
    frames = sample_frames(scene_start, scene_end, seg['pick'])
```

### Step 9: Render Frames (via MCP)

**CRITICAL: Render in batches of 4 frames** to avoid MCP timeout.

```python
import bpy, os

scene = bpy.context.scene
out_dir = r"C:\dev\loracomp3\data\renders\sheet_XX"
os.makedirs(out_dir, exist_ok=True)

# Get Face mesh for expressions
face = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj.data.shape_keys:
        if 'Fcl_ALL_Surprised' in [k.name for k in obj.data.shape_keys.key_blocks]:
            face = obj
            break
sk = face.data.shape_keys.key_blocks

# For each frame (batch of 4):
for i, frame in enumerate(selected_frames[0:4]):
    scene.frame_set(frame)

    # Set expression based on segment config
    if frame_needs_expression(frame, 'surprised'):
        sk['Fcl_ALL_Surprised'].value = 1.0
        sk['Fcl_MTH_Surprised'].value = 1.0  # Open mouth / shouting
    else:
        sk['Fcl_ALL_Surprised'].value = 0.0
        sk['Fcl_MTH_Surprised'].value = 0.0

    fname = f"frame_{i+1:02d}_{frame:03d}.png"
    scene.render.filepath = os.path.join(out_dir, fname)
    bpy.ops.render.render(write_still=True)
```

**Expression shape keys (VRoid characters):**
- `Fcl_ALL_Surprised` — eyebrows + eyes + mouth surprised composite
- `Fcl_MTH_Surprised` — mouth open (adds extra mouth opening for "shouting" look)
- `Fcl_ALL_Angry`, `Fcl_ALL_Fun`, `Fcl_ALL_Sorrow` — other emotions
- Set value to 1.0 for full expression, 0.0 for neutral
- Expressions are set programmatically per frame before rendering (NOT keyframed)

### Step 10: Assemble Sprite Sheet + GIF

```python
# Using Blender's image API (no PIL needed):
images = [bpy.data.images.load(path) for path in frame_paths]
sheet = bpy.data.images.new('sprite_sheet', 1024, 1024, alpha=True)
pixels = [0.0] * (1024 * 1024 * 4)

for idx, img in enumerate(images):
    row, col = idx // 4, idx % 4
    x_start = col * 256
    y_start = 1024 - (row + 1) * 256  # Blender origin is bottom-left
    frame_pixels = list(img.pixels)
    for py in range(256):
        for px in range(256):
            src = (py * 256 + px) * 4
            dst = ((y_start + py) * 1024 + (x_start + px)) * 4
            pixels[dst:dst+4] = frame_pixels[src:src+4]

sheet.pixels = pixels
sheet.filepath_raw = output_path
sheet.file_format = 'PNG'
sheet.save()
```

For GIF: use the LZW encoder (see render code in previous sessions) or PIL if available.

### Step 11: Save Scene + Update Manifest

```python
bpy.ops.wm.save_as_mainfile(filepath=r"C:\dev\loracomp3\data\scenes\sheet_XX_name.blend")
```

Update `data/manifest.json` with the new sheet entry (see existing entries for format).

---

## Critical Gotchas (MUST READ)

### Camera Rotation
- **CORRECT:** `cam.rotation_euler = (math.pi/2, 0, -math.pi/2)` → looks along +X
- **WRONG:** `cam.rotation_euler = (math.pi/2, 0, +math.pi/2)` → looks along -X, renders BLANK

### Freestyle Crashes
- **Delete ALL empties** after every FBX import. `J_Sec_*_end` empties cause `SphericalGrid::assignCells` null pointer crash in Freestyle.
- Set `freestyle_settings.sphere_radius = 0`
- **Mma Kick.fbx crashes Freestyle** even with empties deleted — avoid this animation entirely

### Blender 5.0 API
- Render engine is `'BLENDER_EEVEE'` (not `'BLENDER_EEVEE_NEXT'`)
- Action fcurves: `action.layers[].strips[].channelbags[].fcurves` (not `action.fcurves`)
- For simpler approach, use `keyframe_insert()` on objects directly

### Duplicate Objects on Second FBX Import
- Second FBX import creates `Armature.001`, `Body.001`, `Face.001`, `Hair.001` + empties
- Delete ALL duplicates after import, keep only the original objects

### Animation Orientation
- Some Mixamo animations (e.g., Roundhouse Kick) have different base Z rotation (~-87°) vs standard (~-45°)
- Fix: offset all Z rotation keyframes + rotate XY location keyframes by the same angle in the action's fcurves
- See sheet 06 scene for reference implementation

### Spring Bones
- `test_spring_bones.py` defaults to 54 frames — for NLA animations, pass `end_frame` explicitly
- Run AFTER camera setup (frustum clamp depends on camera position)
- Push to NLA with `blend_type='ADD'`

### VRM Material Fix
- Only swap Output Surface link (full rebuild breaks Mixamo skeleton mapping)

### Color Management
- Must use `Standard` view transform (not Filmic) for pure white background

### MCP Timeout
- Render in batches of 4 frames per MCP call to avoid timeout
- Complex Blender operations should be broken into smaller code blocks

---

## Animation Transition Problem (Solved)

When combining multiple Mixamo animations in one sheet, the character can "teleport" at transitions because:
1. Each animation has its own internal body positioning
2. Root/Hips bones read (0,0,0) locally, but accumulated pose chain produces different world positions
3. Cannot fix by offsetting bone fcurves — the shift comes from the entire pose
4. Copy Location constraint tracks armature origin which doesn't move

**Fix:** Dynamic camera measures actual mesh bounds per frame → consistent framing. Each frame is independently framed, so transitions between animations are seamless.

---

## Root Motion Stripping (for extreme movement only)

For animations where the character travels far (rolls, flips, falls):
1. Remove any camera constraints
2. Per frame: compute Hips bone world XY position
3. Bake inverse offset into armature location: `armature.location.xy = -(hips_xy - reference_xy)`
4. Keep Z natural (vertical bob preserved)
5. Then run dynamic camera on top

| Animation Type | Root Motion Strip? |
|---|---|
| Idle, walk, punch, kick, block | No |
| Run + roll, flips, falls, death | Yes |
| Standing combos | No |
| Hit reactions | Check — if drifts far, strip |

---

## Completed Sprite Sheets

### Sheet 01: Idle + Walk
- **Animations:** Idle (8f) + Walking (4f) + Walking Back (4f reversed)
- **Pipeline:** Simple
- **Config:** `data/configs/sheet_01_idle_walk.json`
- **Scene:** `data/scenes/sheet_01_idle_walk.blend`
- **Output:** `data/renders/sheet_01_idle_walk.png`, `.gif`

### Sheet 02: Run Forward + Run To Rolling
- **Animations:** Run Forward (4f) + Run To Rolling (12f, 7 segments)
- **Pipeline:** Complex (root motion strip + dynamic camera)
- **Config:** `data/configs/sheet_02_run_roll.json`
- **Scene:** `data/scenes/sheet_02_run_roll.blend`
- **Output:** `data/renders/sheet_02_run_roll.png`, `.gif`
- **Note:** Hair physics needs re-run after camera changes

### Sheet 03: Left Right Hook
- **Animations:** Hook (1) (8f) + Hook Punch (8f)
- **Config:** `data/configs/sheet_03_leftrighthook.json`
- **Scene:** `data/scenes/sheet_03_leftrighthook.blend`
- **Output:** `data/renders/sheet_03_leftrighthook.png`, `.gif`

### Sheet 04: Hook + Right Hook
- **Animations:** Hook (8f) + Right Hook (8f)
- **Config:** `data/configs/sheet_04_hookrighthook.json`
- **Scene:** `data/scenes/sheet_04_hookrighthook.blend`
- **Output:** `data/renders/sheet_04_hookrighthook.png`, `.gif`

### Sheet 05: Quad Punch
- **Animations:** Quad Punch (16f, segment-based selection)
- **Config:** `data/configs/sheet_05_quadpunch.json`
- **Scene:** `data/scenes/sheet_05_quadpunch.blend`
- **Output:** `data/renders/sheet_05_quadpunch.png`, `.gif`

### Sheet 06: Illegal Knee + Roundhouse Kick
- **Animations:** Illegal Knee (8f) + Roundhouse Kick (8f)
- **Pipeline:** Complex (animation orientation fix + segment-based + expressions)
- **Config:** `data/configs/sheet_06_roundhousekick_illegalknee.json`
- **Scene:** `data/scenes/sheet_06_roundhousekick_illegalknee.blend`
- **Output:** `data/renders/sheet_06_roundhousekick_illegalknee.png`, `.gif`
- **Notes:** Roundhouse Kick required +42 deg Z rotation offset. Surprised expression on impact frames.

### Sheet 07: Kicking
- **Animations:** Kicking (16f)
- **Config:** `data/configs/sheet_07_kicking.json`
- **Scene:** `data/scenes/sheet_07_kicking.blend`
- **Output:** `data/renders/sheet_07_kicking.png`, `.gif`

---

## Planned Sheets

| Sheet | Theme | Candidates |
|-------|-------|-----------|
| 08 | Hit Reactions | Head Hit, Hit To Body, Stomach Hit, Reaction |
| 09 | Death/Recovery | Dying, Falling Back Death, Defeated, Getting Up |
| 10 | Movement | Jump, Long Step Forward, Sprinting Forward Roll |

---

## Project Structure

```
loracomp3/
├── PROJECT.md                              # This file
├── QwenImageLoRA_Competition.md            # Competition rules
├── blender_sprite_pipeline_addon.py        # Blender addon (v3.0)
├── .env                                    # ModelScope token
│
├── scripts/
│   ├── vrm_to_mixamo_fbx.py               # VRM → FBX converter
│   ├── test_spring_bones.py                # Spring bone hair physics
│   ├── test_render_animation.py            # Single frame render
│   ├── render_animation_gif.py             # Render animation → GIF
│   ├── check_animation_range.py            # Debug FBX keyframe ranges
│   └── test_angles.py                      # Debug camera angles
│
├── data/
│   ├── manifest.json                       # Master manifest (all sheets, characters, status)
│   ├── animations/                         # 45 Mixamo FBX files
│   ├── characters/                         # Character source files
│   │   └── AvatarSample_B/
│   │       ├── model.vroid
│   │       ├── AvatarSample_B.vrm
│   │       └── AvatarSample_B.fbx
│   ├── configs/                            # Sprite sheet configs (JSON per sheet)
│   ├── scenes/                             # Blender scene files (.blend per sheet)
│   └── renders/                            # Output (sprite sheets, GIFs, frame subdirs)
│
└── archive/                                # Old test files, deprecated experiments
```

---

## Character Pipeline (Upstream)

### Step 1: VRoid → FBX
- Create character in VRoid Studio, export as VRM
- **Script:** `scripts/vrm_to_mixamo_fbx.py` — minimal material fix (only swap Output Surface link)

### Step 2: Mixamo
- Upload FBX → auto-rigs to character proportions
- Download animations with "With Skin" option (47 animations available)

---

## Animations (47 Mixamo FBX files)

**Idle/Movement:** Idle, Mma Idle, Walking, Walking (1), Running, Treadmill Running, Run Forward, Fast Run, Long Step Forward, Jump

**Attacks:** Hook Punch, Hook, Hook (1), Lead Jab, Lead Jab (1), Right Hook, Uppercut, Boxing, Boxing (1), Quad Punch, Punch To Elbow Combo, Knee Jabs To Uppercut, Kicking, Mma Kick, Mma Kick (1), Roundhouse Kick, Illegal Knee, Leg Sweep, Armada, Martelo 2, Bencao

**Defense/Reaction:** Block, Body Block, Reaction, Head Hit, Medium Hit To Head, Hit To Body, Stomach Hit

**Death/Recovery:** Defeated, Dying, Dying (1), Falling Back Death, Getting Up

**Special:** Run To Rolling, Sprinting Forward Roll

---

## NLA Tips (Blender 5.0 Slotted Actions)

- Fix slot identifier: `slot.identifier = "OB" + armature.name`
- Prevent bleed: `strip.extrapolation = 'NOTHING'`
- Reverse playback: `strip.use_reverse = True`
- Action → scene frame: `scene_frame = action_frame + strip.frame_start - strip.action_frame_start`

---

## Previous Concept: UI Redesign (Abandoned)

Originally planned bad UI → good UI transformation. 42 training pairs uploaded to ModelScope (tantk7/ui-redesign-training-data). Pivoted to 3D→pixel art sprite sheets.
