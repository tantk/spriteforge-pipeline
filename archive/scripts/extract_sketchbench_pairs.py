"""Extract 100 pairs from SketchBench: rough sketch -> clean line art (GT)."""
import os
import re
import shutil
import cairosvg
from pathlib import Path

BENCH_DIR = Path(r"C:\dev\loracomp3\data\sketch_datasets\sketchbench\extracted\Benchmark_Dataset")
ROUGH_DIR = BENCH_DIR / "Rough" / "PNG"
GT_DIR = BENCH_DIR / "GT"
OUT_DIR = Path(r"C:\dev\loracomp3\data\sketch_datasets\sketchbench\pairs")

(OUT_DIR / "rough").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "clean").mkdir(parents=True, exist_ok=True)

# Find all GT "full" SVGs (the complete cleaned version)
gt_files = sorted(GT_DIR.glob("*_norm_full.svg"))
print(f"Found {len(gt_files)} GT full SVGs")

# Build mapping: sketch_id -> list of GT SVGs
pairs = []
for gt_svg in gt_files:
    # e.g. Art_freeform_AG_02_Branislav Mirkovic_norm_full.svg
    # sketch_id = Art_freeform_AG_02
    name = gt_svg.stem.replace("_norm_full", "")
    # Remove artist name: everything after the ID pattern (XX_NN)
    match = re.match(r"(.+?_[A-Z]+_\d+)_(.*)", name)
    if not match:
        continue
    sketch_id = match.group(1)
    artist = match.group(2)

    rough_path = ROUGH_DIR / f"{sketch_id}.png"
    if rough_path.exists():
        pairs.append((sketch_id, artist, rough_path, gt_svg))

print(f"Found {len(pairs)} valid rough+GT pairs")

# Take first 100 (pick one artist per sketch for consistency)
seen_ids = set()
selected = []
for sketch_id, artist, rough_path, gt_svg in pairs:
    if sketch_id in seen_ids:
        continue
    seen_ids.add(sketch_id)
    selected.append((sketch_id, artist, rough_path, gt_svg))
    if len(selected) >= 100:
        break

print(f"Selected {len(selected)} unique pairs")

for i, (sketch_id, artist, rough_path, gt_svg) in enumerate(selected):
    idx = f"{i+1:03d}"
    # Copy rough
    shutil.copy2(rough_path, OUT_DIR / "rough" / f"{idx}.png")
    # Convert GT SVG -> PNG
    try:
        cairosvg.svg2png(
            url=str(gt_svg),
            write_to=str(OUT_DIR / "clean" / f"{idx}.png"),
            output_width=1024,
            output_height=1024,
        )
    except Exception as e:
        print(f"  Failed to convert {gt_svg.name}: {e}")
        continue

    if (i + 1) % 20 == 0:
        print(f"  Processed {i+1}/{len(selected)}")

print(f"\nDone! Pairs saved to {OUT_DIR}")
print(f"  Rough: {OUT_DIR / 'rough'}/")
print(f"  Clean: {OUT_DIR / 'clean'}/")
