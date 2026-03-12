"""Package the training pairs into a zip file ready for upload to ModelScope.

Creates a single zip file containing:
  bad/001.png ... bad/042.png
  good/001.png ... good/042.png
  metadata.json
"""

import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAIRS_DIR = PROJECT_ROOT / "data" / "pairs"
OUTPUT_ZIP = PROJECT_ROOT / "data" / "ui_redesign_training_data.zip"


def run():
    bad_files = sorted((PAIRS_DIR / "bad").glob("*.png"))
    good_files = sorted((PAIRS_DIR / "good").glob("*.png"))
    meta_file = PAIRS_DIR / "metadata.json"

    if not meta_file.exists():
        print("ERROR: metadata.json not found. Run pair_datasets.py first.")
        return

    print(f"Packaging {len(bad_files)} bad + {len(good_files)} good images...")

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in bad_files:
            zf.write(f, f"bad/{f.name}")
        for f in good_files:
            zf.write(f, f"good/{f.name}")
        zf.write(meta_file, "metadata.json")

    size_mb = OUTPUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"\nDone: {OUTPUT_ZIP}")
    print(f"Size: {size_mb:.1f} MB")
    print(f"Contents: {len(bad_files)} bad + {len(good_files)} good + metadata.json")


if __name__ == "__main__":
    run()
