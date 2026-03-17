"""
Package files needed for FBX export on Ubuntu server.

Usage:
    python scripts/package_for_ubuntu.py
    python scripts/package_for_ubuntu.py --chars blackshirt_man bluedress_girl greenhair_girl pinkhair_boy
"""

import os
import sys
import zipfile
import glob
import argparse

BASE_DIR = r"C:\dev\loracomp3"

parser = argparse.ArgumentParser()
parser.add_argument("--chars", nargs="+", default=[
    "blackshirt_man", "bluedress_girl", "greenhair_girl", "pinkhair_boy"
])
args = parser.parse_args()

out_zip = os.path.join(BASE_DIR, "ubuntu_export_package.zip")

files_to_pack = []

# retarget_export.py
files_to_pack.append("scripts/retarget_export.py")

# All source animations
for f in glob.glob(os.path.join(BASE_DIR, "data", "animations", "*.fbx")):
    files_to_pack.append(os.path.relpath(f, BASE_DIR))

# All configs (needed for export_mode detection)
for f in glob.glob(os.path.join(BASE_DIR, "data", "configs", "sheet_*.json")):
    files_to_pack.append(os.path.relpath(f, BASE_DIR))

# VRM characters
for char in args.chars:
    vrm = os.path.join("data", "characters", "AvatarSample_B", f"{char}.vrm")
    if os.path.exists(os.path.join(BASE_DIR, vrm)):
        files_to_pack.append(vrm)
    else:
        print(f"WARNING: {vrm} not found, skipping")

# Instructions
files_to_pack.append("scripts/ubuntu_export_instructions.md")

print(f"Packing {len(files_to_pack)} files...")
total_size = 0
with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    for rel_path in files_to_pack:
        full_path = os.path.join(BASE_DIR, rel_path)
        zf.write(full_path, rel_path)
        size = os.path.getsize(full_path)
        total_size += size

print(f"\nPackaged: {out_zip}")
print(f"Total: {len(files_to_pack)} files, {total_size / 1024 / 1024:.1f} MB uncompressed")
print(f"Zip size: {os.path.getsize(out_zip) / 1024 / 1024:.1f} MB")
print(f"\nCharacters included: {', '.join(args.chars)}")
