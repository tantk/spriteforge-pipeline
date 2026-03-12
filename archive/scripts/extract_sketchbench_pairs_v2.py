"""Extract pairs from SketchBench with fallback artists on SVG conversion failure."""
import re
import shutil
import cairosvg
from pathlib import Path
from collections import defaultdict

BENCH_DIR = Path(r"C:\dev\loracomp3\data\sketch_datasets\sketchbench\extracted\Benchmark_Dataset")
ROUGH_DIR = BENCH_DIR / "Rough" / "PNG"
GT_DIR = BENCH_DIR / "GT"
OUT_DIR = Path(r"C:\dev\loracomp3\data\sketch_datasets\sketchbench\pairs")

(OUT_DIR / "rough").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "clean").mkdir(parents=True, exist_ok=True)

# Build mapping: sketch_id -> list of (artist, gt_svg)
gt_files = sorted(GT_DIR.glob("*_norm_full.svg"))
sketch_to_gts = defaultdict(list)

for gt_svg in gt_files:
    name = gt_svg.stem.replace("_norm_full", "")
    match = re.match(r"(.+?_[A-Z]+_\d+)_(.*)", name)
    if not match:
        continue
    sketch_id = match.group(1)
    artist = match.group(2)
    rough_path = ROUGH_DIR / f"{sketch_id}.png"
    if rough_path.exists():
        sketch_to_gts[sketch_id].append((artist, gt_svg))

print(f"Found {len(sketch_to_gts)} unique sketches with GTs")

# For each sketch, try artists until one SVG converts successfully
successful = []
for sketch_id in sorted(sketch_to_gts.keys()):
    if len(successful) >= 100:
        break
    rough_path = ROUGH_DIR / f"{sketch_id}.png"
    converted = False
    for artist, gt_svg in sketch_to_gts[sketch_id]:
        try:
            idx = f"{len(successful)+1:03d}"
            out_path = OUT_DIR / "clean" / f"{idx}.png"
            cairosvg.svg2png(url=str(gt_svg), write_to=str(out_path), output_width=1024, output_height=1024)
            shutil.copy2(rough_path, OUT_DIR / "rough" / f"{idx}.png")
            successful.append((sketch_id, artist))
            converted = True
            break
        except Exception:
            continue
    if not converted:
        print(f"  SKIP {sketch_id} - all artists failed")

print(f"\nDone! {len(successful)} pairs extracted to {OUT_DIR}")
