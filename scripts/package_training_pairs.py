"""
Package 100 training pairs for ModelScope Civision upload (multi-image format).

Format per pair:
  {N}_start_1.png  — character reference image (target character)
  {N}_start_2.png  — template sprite sheet (from a DIFFERENT character)
  {N}_end.png      — output sprite sheet (target character)
  {N}.txt          — prompt

Template rotation: each pair uses a different character's sprite sheet as
template, cycling through all available characters (never using the same
character as both target and template).

Output: data/civision_upload.zip
"""

import os
import json
import glob
import zipfile

BASE_DIR = r"C:\dev\loracomp3"
RENDERS_DIR = os.path.join(BASE_DIR, "data", "renders_final")
CONFIG_DIR = os.path.join(BASE_DIR, "data", "configs")
OUT_ZIP = os.path.join(BASE_DIR, "data", "civision_upload.zip")

# Load all configs for prompts
configs = {}
config_basenames = {}
for cfg_path in sorted(glob.glob(os.path.join(CONFIG_DIR, "sheet_*.json"))):
    with open(cfg_path) as f:
        cfg = json.load(f)
    configs[cfg["sheet_index"]] = cfg
    config_basenames[cfg["sheet_index"]] = os.path.splitext(os.path.basename(cfg_path))[0]

# Main characters (sheets 1-14)
main_characters = [
    "original_character",
    "army_man",
    "blackdress_girl",
    "blackshirt_man",
    "bluedress_girl",
    "greenhair_girl",
    "pinkhair_boy",
]

# Build 100 pairs
import random
random.seed(42)  # reproducible randomness

pairs = []

# 7 characters × 14 sheets = 98 pairs
for ci, char in enumerate(main_characters):
    for sheet_idx in range(1, 15):
        cfg = configs[sheet_idx]
        basename = config_basenames[sheet_idx]

        ref_path = os.path.join(RENDERS_DIR, char, "character_reference.png")
        sheet_path = os.path.join(RENDERS_DIR, char, f"{basename}.png")

        # Pick random template character (never the same as target)
        others = [c for c in main_characters if c != char]
        template_char = random.choice(others)
        template_path = os.path.join(RENDERS_DIR, template_char, f"{basename}.png")

        prompt = "Replace the character in the sprite sheet with the character from the reference image"

        pairs.append({
            "ref": ref_path,
            "template": template_path,
            "output": sheet_path,
            "prompt": prompt,
            "char": char,
            "template_char": template_char,
            "sheet": sheet_idx,
        })

# darkskin_girl × sheet 15
cfg15 = configs[15]
basename15 = config_basenames[15]
# Use a main character's sheet 15 as template
template_char_15 = "army_man"
pairs.append({
    "ref": os.path.join(RENDERS_DIR, "darkskin_girl", "character_reference.png"),
    "template": os.path.join(RENDERS_DIR, template_char_15, f"{basename15}.png"),
    "output": os.path.join(RENDERS_DIR, "darkskin_girl", f"{basename15}.png"),
    "prompt": "Replace the character in the sprite sheet with the character from the reference image",
    "char": "darkskin_girl",
    "template_char": template_char_15,
    "sheet": 15,
})

# pinkskirt_girl × sheet 16
cfg16 = configs[16]
basename16 = config_basenames[16]
template_char_16 = "blackdress_girl"
pairs.append({
    "ref": os.path.join(RENDERS_DIR, "pinkskirt_girl", "character_reference.png"),
    "template": os.path.join(RENDERS_DIR, template_char_16, f"{basename16}.png"),
    "output": os.path.join(RENDERS_DIR, "pinkskirt_girl", f"{basename16}.png"),
    "prompt": "Replace the character in the sprite sheet with the character from the reference image",
    "char": "pinkskirt_girl",
    "template_char": template_char_16,
    "sheet": 16,
})

print(f"Total pairs: {len(pairs)}")

# Verify all files exist
missing = 0
for p in pairs:
    for key in ["ref", "template", "output"]:
        if not os.path.exists(p[key]):
            print(f"MISSING: {p[key]}")
            missing += 1

if missing > 0:
    print(f"\n{missing} files missing! Fix before packaging.")
else:
    print("All files present. Packaging...")

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_STORED) as zf:
        for i, p in enumerate(pairs, 1):
            zf.write(p["ref"], f"{i}_start_1.png")
            zf.write(p["template"], f"{i}_start_2.png")
            zf.write(p["output"], f"{i}_end.png")
            zf.writestr(f"{i}.txt", p["prompt"])

    size_mb = os.path.getsize(OUT_ZIP) / 1024 / 1024
    print(f"\nSaved: {OUT_ZIP}")
    print(f"Size: {size_mb:.1f} MB")
    print(f"Pairs: {len(pairs)}")

    # Print summary with template rotation
    print("\n=== Pair Summary ===")
    for i, p in enumerate(pairs, 1):
        print(f"  {i:3d}: {p['char']} sheet {p['sheet']:02d} (template: {p['template_char']})")

    # Verify template diversity
    template_counts = {}
    for p in pairs:
        tc = p["template_char"]
        template_counts[tc] = template_counts.get(tc, 0) + 1
    print("\n=== Template Distribution ===")
    for tc, count in sorted(template_counts.items()):
        print(f"  {tc}: used {count} times as template")
