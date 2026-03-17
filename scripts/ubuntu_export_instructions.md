# FBX Export on Ubuntu Server

## Prerequisites

- Blender 5.0 installed (`sudo snap install blender --classic` or download from blender.org)
- No GPU needed — export is CPU-only

## Files to Copy

Copy these from Windows to the Ubuntu server (preserving directory structure):

```
loracomp3/
├── scripts/
│   └── retarget_export.py
├── data/
│   ├── animations/          ← all 24 source Mixamo FBXs (~650MB)
│   ├── configs/             ← all sheet_*.json (for export_mode detection)
│   └── characters/
│       └── AvatarSample_B/  ← VRM files for characters you want to export
│           ├── blackshirt_man.vrm
│           ├── bluedress_girl.vrm
│           ├── greenhair_girl.vrm
│           └── pinkhair_boy.vrm
```

Use the packaging script to create a zip:
```cmd
python scripts/package_for_ubuntu.py
```
This creates `ubuntu_export_package.zip` in the project root.

## On Ubuntu

```bash
# Unzip
unzip ubuntu_export_package.zip -d ~/loracomp3
cd ~/loracomp3

# Edit BASE_DIR in retarget_export.py to match Ubuntu path
sed -i 's|C:\\dev\\loracomp3|/home/YOUR_USER/loracomp3|g' scripts/retarget_export.py

# Export one character at a time
blender --background --python scripts/retarget_export.py -- --char blackshirt_man.vrm
blender --background --python scripts/retarget_export.py -- --char bluedress_girl.vrm
blender --background --python scripts/retarget_export.py -- --char greenhair_girl.vrm
blender --background --python scripts/retarget_export.py -- --char pinkhair_boy.vrm

# Or all at once (sequential)
blender --background --python scripts/retarget_export.py
```

Each character takes ~9 minutes. 4 characters = ~36 minutes.

## Copy Results Back

The exported FBXs are in `data/characters/{char_name}/animations/`. Copy them back to Windows:

```bash
# On Ubuntu, zip the results
cd ~/loracomp3
zip -r exported_fbxs.zip data/characters/*/animations/

# Copy to Windows via scp, rsync, or manual transfer
```

On Windows, extract into `C:\dev\loracomp3\` (merge with existing).

## Notes

- The Retarget addon is auto-installed on first run (`bpy.ops.extensions.package_install`)
- 22 animations use SIMPLE mode, 2 use ROOT_MOTION mode (auto-detected from configs)
- Each animation is independent — if one fails, others continue
- Existing FBXs are skipped (delete to re-export)
