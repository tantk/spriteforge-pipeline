"""Extract pairs from SketchBench using pre-rasterized PNGs from Benchmark_Testset."""
import re
import shutil
from pathlib import Path
from collections import defaultdict

TESTSET = Path(r"C:\dev\loracomp3\data\sketch_datasets\sketchbench\Benchmark_Testset")
ROUGH_DIR = TESTSET / "rough" / "pixel"
GT_DIR = TESTSET / "gt" / "pixel"
OUT_DIR = Path(r"C:\dev\loracomp3\data\sketch_datasets\sketchbench\pairs")

(OUT_DIR / "rough").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "clean").mkdir(parents=True, exist_ok=True)

# Find all GT cleaned PNGs at 1000px resolution
gt_files = sorted(GT_DIR.glob("*_norm_cleaned_1000.png"))
print(f"Found {len(gt_files)} GT cleaned 1000px PNGs")

# Build mapping: sketch_id -> list of GT paths
sketch_to_gts = defaultdict(list)
for gt_path in gt_files:
    name = gt_path.stem.replace("_norm_cleaned_1000", "")
    match = re.match(r"(.+?_[A-Z]+_\d+)_(.*)", name)
    if not match:
        continue
    sketch_id = match.group(1)
    # Check rough exists (use 1000px version)
    rough_path = ROUGH_DIR / f"{sketch_id}_norm_rough_1000.png"
    if not rough_path.exists():
        # Try original resolution
        rough_path = ROUGH_DIR / f"{sketch_id}.png"
    if rough_path.exists():
        sketch_to_gts[sketch_id].append((gt_path, rough_path))

print(f"Found {len(sketch_to_gts)} unique sketches with rough+GT pairs")

# Pick one GT per sketch, extract up to 100
selected = []
for sketch_id in sorted(sketch_to_gts.keys()):
    if len(selected) >= 100:
        break
    gt_path, rough_path = sketch_to_gts[sketch_id][0]
    idx = f"{len(selected)+1:03d}"
    shutil.copy2(rough_path, OUT_DIR / "rough" / f"{idx}.png")
    shutil.copy2(gt_path, OUT_DIR / "clean" / f"{idx}.png")
    selected.append(sketch_id)

print(f"\nDone! {len(selected)} pairs extracted to {OUT_DIR}")
