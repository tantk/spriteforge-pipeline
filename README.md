# SpriteForge Pipeline

**Automated fighting game sprite sheet rendering from 3D characters.**

Takes VRoid characters + Mixamo animations → produces consistent 4×4 sprite sheets (16 frames at 256×256, assembled into 1024×1024 sheets).

---

## What It Does

- Retargets Mixamo animations onto any VRoid character
- Renders 16-frame sprite sheets with consistent camera, lighting, and Freestyle outline
- Spring bone hair physics simulation
- GPU-accelerated EEVEE rendering (~2 min per sheet)
- Supports 16 fighting animations out of the box

---

## Requirements

- [Blender 5.0](https://www.blender.org/download/)
- [VRoid Studio](https://vroid.com/en/studio) (for creating characters)
- [Mixamo](https://www.mixamo.com/) account (for animations)
- Python 3.10+
- Windows (for `start /min` GPU rendering)

---

## Quick Start

### 1. Create Characters

Create characters in VRoid Studio, export as `.vrm`. Place in `data/characters/AvatarSample_B/`.

### 2. Get Animations

Upload your character to Mixamo, download animations as FBX ("With Skin"). Place in `data/animations/`.

### 3. Retarget Animations

Retarget Mixamo animations onto each VRM character:

```bash
# Single character
blender --background --python scripts/retarget_export.py -- --char my_character.vrm

# Single animation
blender --background --python scripts/retarget_export.py -- --char my_character.vrm --anim "Idle.fbx"

# All characters
blender --background --python scripts/retarget_export.py
```

Output: `data/characters/{char_name}/animations/*.fbx`

### 4. Render Sprite Sheets

```bash
# Single character, GPU rendering (minimized window)
start /min /wait "" "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --python scripts/batch_render_characters.py -- --char my_character.vrm

# Single sheet only
start /min /wait "" "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --python scripts/batch_render_characters.py -- --char my_character.vrm --sheet 1

# CPU fallback (slower, ~2.5x)
blender --background --python scripts/batch_render_characters.py -- --char my_character.vrm
```

Output: `data/renders_final/{char_name}/sheet_*.png` and `.gif`

**Important:** Do NOT use `--background` for rendering — EEVEE needs GPU context. Use `start /min` for minimized window with full GPU access.

### 5. Render Character References

Renders a 1024×1024 idle frame per character:

```bash
start /min /wait "" "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --python scripts/render_character_reference.py
```

Output: `data/renders_final/{char_name}/character_reference.png`

---

## Animations

16 configs in `data/configs/`:

| Sheet | Animation | Notes |
|-------|-----------|-------|
| 01 | Idle + Walk | 3 animations combined |
| 02 | Run + Roll | Per-frame ground tracking camera |
| 03 | Left Right Hook | |
| 04 | Hook + Right Hook | |
| 05 | Quad Punch | |
| 06 | Knee + Roundhouse Kick | |
| 07 | Spinning Kick | |
| 08 | Fall + Get Up | Special export mode (`export_mode: root_motion`) |
| 09 | Armada | Capoeira spinning kick |
| 10 | Hit + Block | Uses `render_sheet_indv.py` for hair reset |
| 11 | Left Right Kick | Mirrored animation |
| 12 | Knees to Uppercut | |
| 13 | Punch Elbow Combo | |
| 14 | Northern Soul Spin A | 360° character rotation |
| 15 | Northern Soul Spin B | Alternate angle coverage |
| 16 | Northern Soul Spin C | Remaining angles |

---

## Scripts

| Script | Purpose |
|--------|---------|
| `retarget_export.py` | Retarget Mixamo animations onto VRM characters via visual bake |
| `batch_render_characters.py` | Batch render all sheets for all characters |
| `render_sheet.py` | Core render pipeline (scene setup, NLA, camera, spring bones) |
| `render_sheet_indv.py` | Variant for sheets with hair reset animations |
| `render_character_reference.py` | 1024×1024 character idle frame |
| `camera_hybrid.py` | Ground-anchored + horizontal centering camera |
| `camera_perframe_ground.py` | Per-frame ground tracking camera |
| `package_training_pairs.py` | Package sprite sheets into training pairs |

---

## How It Works

### Retargeting

The pipeline uses Blender's Retarget addon to transfer Mixamo animations onto VRM characters with different body proportions. The process: import VRM + FBX → constraint-based binding → visual bake → FBX export with rest pose fix.

**Critical:** Do not zero the FBX armature transform or modify root motion fcurves. The visual bake captures everything correctly. See `retarget_pipeline.md` for details.

### Camera System

Two camera modes:
- **Hybrid camera** — fixed ground-anchored vertical position, per-frame horizontal tracking. Used for most animations.
- **Per-frame ground camera** — tracks the character's lowest point every frame. Used for rolling/tumbling animations.

Both use orthographic projection for consistent sprite framing.

### Rendering

- Engine: EEVEE (GPU rasterizer)
- Resolution: 256×256 per frame, assembled into 1024×1024 sheets
- Freestyle outline: 1px black, external contour only
- White background, Standard color management
- Spring bone hair physics simulated after camera setup

---

## Adding New Animations

1. Download the animation from Mixamo as FBX
2. Create a config JSON in `data/configs/`:

```json
{
    "name": "My Animation",
    "sheet_index": 17,
    "prompt": "Description of the animation",
    "camera": "hybrid",
    "camera_reference_frame": 1,
    "animations": [
        {
            "name": "My Animation",
            "fbx": "My Animation.fbx",
            "frames": 16,
            "reversed": false,
            "description": "What the animation shows",
            "segments": [
                {"action_frames": [1, 10], "pick": 8, "description": "First half"},
                {"action_frames": [11, 20], "pick": 8, "description": "Second half"}
            ]
        }
    ],
    "total_frames": 16,
    "grid": "4x4",
    "resolution": "1024x1024",
    "frame_size": "256x256"
}
```

3. Add the FBX filename to `ALL_ANIMS` in `retarget_export.py`
4. Run retarget + render

---

## License

Pipeline code is provided as-is. VRoid characters and Mixamo animations are subject to their respective licenses.
