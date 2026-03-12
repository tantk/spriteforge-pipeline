"""Build snowboard training pairs: person/board input → action shot output.

Single-image edit mode:
  edit_image: person with snowboard (standing, posing, portrait with gear)
  image: action shot (jumping, carving, powder)
  prompt: instruction to generate action shot

Curation steps:
1. Merge person + board categories (remove duplicates)
2. Filter out bad images (landscapes, skis, no snowboard content)
3. Randomly pair inputs with action shot outputs
4. Package for Civision upload
"""

import json
import random
import shutil
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "snowboard"
OUTPUT_DIR = PROJECT_ROOT / "data" / "snowboard_pairs"

# Photo IDs to reject (manually identified: landscapes, skis, boots, sleds, no snowboard)
REJECT_IDS = {
    # Board category rejects
    "paRm0lsr3YI",   # ski resort landscape, no snowboard
    "E6zize3pZZU",   # sleds, not snowboards
    "KmNVe41xTEs",   # skis with poles
    "944653",         # winter boot, not snowboard
    "24349783",       # ski bindings close-up
    "weFx9RflIfU",   # ski boots on skis
    # Person category rejects
    "4hCDHihJoWA",   # skier with poles doing flip (not snowboarder)
    "880497",         # landscape, person barely visible at edge
    "0-rnYCJzOEM",   # skier
    "1740098",        # skier on slope
    "Freq5fHt5GI",   # could be skier
    "nb0aP7p1-k",    # ambiguous
    # Action category rejects (non-action or skiing)
    "6141670",        # person walking with board, not action
}

# Photo IDs that are action shots misplaced in other categories
ACTION_OVERRIDE = {
    "nQz49efZEFs",    # powder explosion - action shot
    "QzUsG1EieqE",    # cliff jump - action shot
    "83icOWazZZ4",    # snowboarders carving downhill - action
    "9-dHYri9BOE",    # B&W powder carving - action
}

PROMPTS = [
    "Generate an extreme snowboarding action shot. Show a dynamic jump with snow spray against a mountain backdrop.",
    "Create a dramatic snowboarding trick photo. Capture mid-air rotation with powder explosion and blue sky.",
    "Transform this into a high-energy snowboarding moment. Show carving through deep powder with spray.",
    "Generate a professional snowboard photography shot. Dynamic action with dramatic lighting and mountain scenery.",
    "Create an epic snowboarding jump shot. Capture the peak of a trick with snow particles and mountain backdrop.",
    "Transform this into a stunning backcountry snowboarding photo. Deep powder turn with spray against pristine mountains.",
    "Generate a competition-style snowboard trick shot. Halfpipe or park jump with clean grab and style.",
    "Create an adrenaline-filled snowboarding action photo. High-speed carving with powder cloud and dramatic angle.",
]


def get_photo_id(filename: str) -> str:
    parts = filename.rsplit(".", 1)[0].split("_", 1)
    return parts[1] if len(parts) >= 2 else parts[0]


def collect_category(cat_dir: Path, reject_ids: set, override_ids: set) -> list[Path]:
    """Collect valid images from a category, filtering rejects and overrides."""
    valid = []
    for f in sorted(cat_dir.glob("*.jpg")):
        pid = get_photo_id(f.name)
        if pid in reject_ids:
            continue
        if pid in override_ids:
            continue
        valid.append(f)
    return valid


def run():
    # Collect action shots (output/target)
    action_dir = RAW_DIR / "action"
    action_files = collect_category(action_dir, REJECT_IDS, set())
    # Also add action overrides from other categories
    for cat in ["person", "board"]:
        cat_dir = RAW_DIR / cat
        for f in cat_dir.glob("*.jpg"):
            pid = get_photo_id(f.name)
            if pid in ACTION_OVERRIDE:
                action_files.append(f)

    # Collect input images (person + board merged, deduplicated)
    seen_ids = set()
    input_files = []

    for cat in ["person", "board"]:
        cat_dir = RAW_DIR / cat
        for f in sorted(cat_dir.glob("*.jpg")):
            pid = get_photo_id(f.name)
            if pid in REJECT_IDS or pid in ACTION_OVERRIDE:
                continue
            if pid in seen_ids:
                continue
            # Also skip if this ID is in the action category (don't use as input)
            action_ids = {get_photo_id(a.name) for a in action_files}
            if pid in action_ids:
                continue
            seen_ids.add(pid)
            input_files.append(f)

    print(f"Action shots (targets): {len(action_files)}")
    print(f"Input images (person/board): {len(input_files)}")

    # Number of pairs = min of both
    n_pairs = min(len(action_files), len(input_files))
    print(f"Creating {n_pairs} training pairs...")

    # Shuffle for random pairing
    random.seed(42)
    random.shuffle(action_files)
    random.shuffle(input_files)

    # Create output dirs
    (OUTPUT_DIR / "input").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "output").mkdir(parents=True, exist_ok=True)

    metadata = []
    for i in range(n_pairs):
        idx = f"{i+1:03d}"
        input_src = input_files[i]
        action_src = action_files[i]
        prompt = PROMPTS[i % len(PROMPTS)]

        input_dest = OUTPUT_DIR / "input" / f"{idx}.jpg"
        output_dest = OUTPUT_DIR / "output" / f"{idx}.jpg"

        shutil.copy2(input_src, input_dest)
        shutil.copy2(action_src, output_dest)

        metadata.append({
            "image": f"output/{idx}.jpg",
            "prompt": prompt,
            "edit_image": [f"input/{idx}.jpg"],
        })

    # Write metadata
    meta_path = OUTPUT_DIR / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    print(f"\nDone! Created {n_pairs} pairs:")
    print(f"  Inputs:   {OUTPUT_DIR / 'input'}/")
    print(f"  Outputs:  {OUTPUT_DIR / 'output'}/")
    print(f"  Metadata: {meta_path}")

    # Also package as Civision ZIP (single image edit mode)
    import zipfile
    zip_path = OUTPUT_DIR / "civision_snowboard.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, entry in enumerate(metadata):
            idx = i + 1
            input_path = OUTPUT_DIR / entry["edit_image"][0]
            output_path = OUTPUT_DIR / entry["image"]
            prompt = entry["prompt"]

            zf.write(input_path, f"{idx}_start.jpg")
            zf.write(output_path, f"{idx}_end.jpg")
            zf.writestr(f"{idx}.txt", prompt)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"\n  Civision ZIP: {zip_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    run()
