# Sheet 03: Left Right Hook — Processing Steps

## Config
`data/configs/sheet_03_leftrighthook.json`

## Animations
| Animation | FBX | Frames | Description |
|-----------|-----|--------|-------------|
| Hook (1) | Hook (1).fbx | 8 | Left hook with left foot stepping forward |
| Hook Punch | Hook Punch.fbx | 8 | Stationary right hook punch |

## NLA Layout
```
Hook (1):     frames 1-49   (49 action frames)
Hook Punch:   frames 49-101 (53 action frames)
SpringBoneHair: frames 1-101
```

## Processing Steps

### 1. Scene Setup
```python
# Clear scene, import Hook (1).fbx (brings full character)
# Rename action → "Hook (1)", fix slot, push to NLA
# Import Hook Punch.fbx → rename action, fix slot, push to NLA
# Delete duplicate armature from second import
# Set strip.extrapolation = 'NOTHING' on both strips
```

### 2. Camera + Lighting + Render Settings
```python
# Camera: PERSP 50mm, base location (-2.4063, -0.3171, 0.6149)
# 3 sun lights: Key(4.0), Fill(2.5), Rim(1.5), no shadows
# EEVEE 256x256, Standard color management, white BG
# Freestyle: external_contour only, black, 1px
# Materials: Specular IOR Level=0, Roughness=1
```
Applied from `data/configs/render_settings.json`.

### 3. Spring Bone Hair Physics (first pass)
```python
# stiffness=0.3, damping=0.2, reaction=2.0, max_deg=25
# 12 hair chains detected, baked into SpringBoneHair NLA track
```

### 4. Dynamic Camera (mesh-vertex based, iterative)

**Why not Copy Location constraint?**
Different Mixamo animations position the character's visible body differently even when the armature origin doesn't move. The Copy Location constraint tracks the armature origin, causing a visible "teleport" when switching between animations. The dynamic camera tracks actual mesh bounds for consistent framing.

```python
# Remove any Copy Location constraint from camera
# Camera rotation stays FIXED, only position pans
# Per frame (1-101):
#   1. Reset camera to base position
#   2. Evaluate deformed Body mesh vertices (every 4th vertex)
#   3. Find screen bounds via world_to_camera_view()
#   4. Bottom-anchor lowest vertex at 10% from bottom edge
#   5. Center character horizontally
#   6. Convert screen-space shift to world-space camera offset
#   7. Iterate up to 8 times until converged (<0.008 tolerance)
#   8. Bake camera location keyframe (LINEAR interpolation)
# Result: 101 frames in ~8s
```

### 5. Spring Bone Hair Physics (re-run after camera)
Spring bones re-run after dynamic camera because hair physics depend on camera position for frustum clamping.

### 6. Frame Selection
```python
# Hook (1): 8 frames evenly from 1-48 → [1, 8, 14, 21, 28, 35, 41, 48]
# Hook Punch: 8 frames evenly from 50-101 → [50, 57, 65, 72, 79, 86, 94, 101]
# Avoid frame 49 (NLA strip overlap)
# Total: 16 frames
```

### 7. Render + Assemble
```python
# Render 16 frames at 256x256 with EEVEE
# Assemble into 4x4 grid → 1024x1024 sprite sheet
# Generate GIF (150ms per frame, loop)
```

## Output
- **Sprite sheet:** `data/renders/sheet_03_leftrighthook.png`
- **GIF:** `data/renders/sheet_03_leftrighthook.gif`
- **Individual frames:** `data/renders/sheet_03/`
- **Scene:** `data/scenes/sheet_03_leftrighthook.blend`

## Selected Frames
```
[1, 8, 14, 21, 28, 35, 41, 48, 50, 57, 65, 72, 79, 86, 94, 101]
 |--- Hook (1), left hook ---|  |--- Hook Punch, right hook ---|
```

## Key Decisions
- **Dynamic camera over Copy Location**: Prevents teleport between animations
- **8+8 frame split**: Both animations get equal representation
- **No root motion stripping needed**: Character stays mostly upright for both punches
- **Frame 49 avoided**: NLA overlap point between the two strips
