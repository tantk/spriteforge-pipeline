"""Split concatenated anime sketch-colorization pairs into separate sketch/color images."""
from pathlib import Path
from PIL import Image

RAW_DIR = Path(r"C:\dev\loracomp3\data\sketch_datasets\anime_sketch\raw")
OUT_DIR = Path(r"C:\dev\loracomp3\data\sketch_datasets\anime_sketch\pairs")

(OUT_DIR / "sketch").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "color").mkdir(parents=True, exist_ok=True)

files = sorted(RAW_DIR.glob("*.png"))[:100]
print(f"Processing {len(files)} files...")

for i, f in enumerate(files):
    img = Image.open(f)
    w, h = img.size
    mid = w // 2
    # Left half = color, Right half = sketch
    color = img.crop((0, 0, mid, h))
    sketch = img.crop((mid, 0, w, h))

    idx = f"{i+1:03d}"
    color.save(OUT_DIR / "color" / f"{idx}.png")
    sketch.save(OUT_DIR / "sketch" / f"{idx}.png")

print(f"Done! {len(files)} pairs split:")
print(f"  Sketch: {OUT_DIR / 'sketch'}/")
print(f"  Color: {OUT_DIR / 'color'}/")
