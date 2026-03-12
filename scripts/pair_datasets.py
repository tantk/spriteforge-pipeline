"""Pair bad UI screenshots with good UI screenshots and build training metadata.

Since both sets are landing pages of various types, we randomly pair them.
The LoRA will learn the general transformation: generic/ugly → polished/professional.

Outputs:
  data/pairs/bad/001.png ...
  data/pairs/good/001.png ...
  data/pairs/metadata.json  (Qwen-Image-Edit format)
"""

import json
import random
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BAD_DIR = PROJECT_ROOT / "data" / "bad_ui"
GOOD_DIR = PROJECT_ROOT / "data" / "good_ui_clean"
PAIRS_DIR = PROJECT_ROOT / "data" / "pairs"

PROMPTS = [
    "Redesign this website with a modern, polished UI. Improve the typography, color palette, spacing, and visual hierarchy while keeping the same page structure.",
    "Transform this generic website into a professional, visually appealing design. Use better fonts, refined colors, proper whitespace, and clean visual elements.",
    "Upgrade this basic website design to a high-quality, modern interface. Improve the color scheme, typography, spacing, and overall visual polish.",
    "Make this website look professionally designed. Apply better typography, a cohesive color palette, improved spacing, and visual refinement.",
    "Enhance this plain website with modern design principles. Improve the visual hierarchy, color harmony, font choices, and whitespace usage.",
    "Give this website a complete visual overhaul. Modernize the typography, apply a sophisticated color palette, and improve the layout aesthetics.",
    "Redesign this outdated website interface with contemporary design standards. Focus on clean typography, balanced colors, and refined spacing.",
    "Transform this amateur-looking website into a polished, professional landing page with elegant typography and a harmonious color scheme.",
    "Elevate this basic website to a premium design. Improve font selections, color coordination, visual balance, and overall aesthetic quality.",
    "Reimagine this website with world-class design. Apply refined typography, a curated color palette, and intentional whitespace for a polished result.",
]

NUM_PAIRS = 45  # limited by good UI count


def run():
    bad_files = sorted(BAD_DIR.glob("*.png"))
    good_files = sorted(GOOD_DIR.glob("*.png"))

    print(f"Bad UIs:  {len(bad_files)}")
    print(f"Good UIs: {len(good_files)}")

    n = min(NUM_PAIRS, len(bad_files), len(good_files))
    print(f"Creating {n} pairs...")

    # Shuffle both lists independently for random pairing
    random.seed(42)
    bad_sample = random.sample(bad_files, n)
    good_sample = random.sample(good_files, n)

    # Create output dirs
    (PAIRS_DIR / "bad").mkdir(parents=True, exist_ok=True)
    (PAIRS_DIR / "good").mkdir(parents=True, exist_ok=True)

    metadata = []
    for i, (bad_f, good_f) in enumerate(zip(bad_sample, good_sample)):
        idx = f"{i+1:03d}"

        bad_dest = PAIRS_DIR / "bad" / f"{idx}.png"
        good_dest = PAIRS_DIR / "good" / f"{idx}.png"

        shutil.copy2(bad_f, bad_dest)
        shutil.copy2(good_f, good_dest)

        prompt = PROMPTS[i % len(PROMPTS)]

        metadata.append({
            "image": f"good/{idx}.png",
            "prompt": prompt,
            "edit_image": [f"bad/{idx}.png"],
        })

    meta_path = PAIRS_DIR / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    print(f"\nDone! Created {n} pairs:")
    print(f"  {PAIRS_DIR / 'bad'}/")
    print(f"  {PAIRS_DIR / 'good'}/")
    print(f"  {meta_path}")
    print(f"\nReady for Qwen-Image-Edit LoRA training.")


if __name__ == "__main__":
    run()
