"""Build Qwen-Image-Edit training metadata from bad/good UI pairs.

Expects:
  data/bad_ui/   - bad UI screenshots (*.png)
  data/good_ui/  - good UI screenshots (*.png) with MATCHING filenames

Outputs:
  data/pairs/metadata.json  - training metadata for DiffSynth-Studio
  data/pairs/bad/            - copies of bad UI images
  data/pairs/good/           - copies of good UI images

The metadata format matches Qwen-Image-Edit multi-image training:
  {
      "image": "good/001.png",          # target (output)
      "prompt": "...",                   # editing instruction
      "edit_image": ["bad/001.png"]      # source (input)
  }
"""

import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BAD_DIR = PROJECT_ROOT / "data" / "bad_ui"
GOOD_DIR = PROJECT_ROOT / "data" / "good_ui"
PAIRS_DIR = PROJECT_ROOT / "data" / "pairs"

PROMPTS = [
    "Redesign this website with a modern, polished UI. Improve the typography, color palette, spacing, and visual hierarchy while keeping the same page structure and layout.",
    "Transform this generic website into a professional, visually appealing design. Use better fonts, refined colors, proper whitespace, and clean visual elements. Keep the same layout structure.",
    "Upgrade this basic website design to a high-quality, modern interface. Improve the color scheme, typography, spacing, and overall visual polish while preserving the original layout.",
    "Make this website look professionally designed. Apply better typography, a cohesive color palette, improved spacing, and visual refinement. Maintain the same content structure.",
    "Enhance this plain website with modern design principles. Improve the visual hierarchy, color harmony, font choices, and whitespace usage. Keep the same page layout.",
]


def run():
    BAD_DIR.mkdir(parents=True, exist_ok=True)
    GOOD_DIR.mkdir(parents=True, exist_ok=True)
    (PAIRS_DIR / "bad").mkdir(parents=True, exist_ok=True)
    (PAIRS_DIR / "good").mkdir(parents=True, exist_ok=True)

    bad_files = {f.stem: f for f in sorted(BAD_DIR.glob("*.png"))}
    good_files = {f.stem: f for f in sorted(GOOD_DIR.glob("*.png"))}

    # Find matching pairs
    matched = sorted(set(bad_files.keys()) & set(good_files.keys()))

    if not matched:
        print(f"No matching pairs found.")
        print(f"  Bad UI screenshots:  {len(bad_files)} in {BAD_DIR}")
        print(f"  Good UI screenshots: {len(good_files)} in {GOOD_DIR}")
        print(f"\nTo create pairs, add good UI screenshots to {GOOD_DIR}")
        print(f"with the SAME filenames as the bad ones.")
        print(f"\nAvailable bad UI files:")
        for name in sorted(bad_files.keys())[:10]:
            print(f"  {name}.png")
        if len(bad_files) > 10:
            print(f"  ... and {len(bad_files) - 10} more")
        return

    metadata = []
    for i, name in enumerate(matched):
        # Copy files to pairs directory with sequential naming
        idx = f"{i+1:03d}"
        bad_dest = PAIRS_DIR / "bad" / f"{idx}.png"
        good_dest = PAIRS_DIR / "good" / f"{idx}.png"

        shutil.copy2(bad_files[name], bad_dest)
        shutil.copy2(good_files[name], good_dest)

        prompt = PROMPTS[i % len(PROMPTS)]

        metadata.append({
            "image": f"good/{idx}.png",
            "prompt": prompt,
            "edit_image": [f"bad/{idx}.png"],
        })

    # Write metadata
    meta_path = PAIRS_DIR / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    print(f"Built {len(metadata)} training pairs")
    print(f"  Metadata: {meta_path}")
    print(f"  Bad UIs:  {PAIRS_DIR / 'bad'}")
    print(f"  Good UIs: {PAIRS_DIR / 'good'}")


if __name__ == "__main__":
    run()
