"""Split Pepper&Carrot pages into square panel crops and resize to 1024x1024.

Each tall comic page (~2400x3500) gets split into overlapping square crops
from top to bottom, then both color and grayscale versions are resized to 1024x1024.
"""
from pathlib import Path
from PIL import Image

COLOR_DIR = Path(r"C:\dev\loracomp3\data\peppercarrot\color")
GRAY_DIR = Path(r"C:\dev\loracomp3\data\peppercarrot\grayscale")
OUT_DIR = Path(r"C:\dev\loracomp3\data\peppercarrot\pairs_1024")

(OUT_DIR / "color").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "grayscale").mkdir(parents=True, exist_ok=True)

TARGET = 1024
pair_idx = 0

color_files = sorted(COLOR_DIR.glob("*.jpg"))
print(f"Processing {len(color_files)} pages...")

for color_path in color_files:
    gray_path = GRAY_DIR / color_path.name
    if not gray_path.exists():
        continue

    color_img = Image.open(color_path)
    gray_img = Image.open(gray_path)
    w, h = color_img.size

    # Calculate square crop size = width (since pages are portrait, width < height)
    crop_size = w

    # Slide from top to bottom with some overlap
    stride = int(crop_size * 0.85)  # 15% overlap between crops
    y = 0
    while y + crop_size <= h:
        # Crop square region
        box = (0, y, crop_size, y + crop_size)
        color_crop = color_img.crop(box).resize((TARGET, TARGET), Image.LANCZOS)
        gray_crop = gray_img.crop(box).resize((TARGET, TARGET), Image.LANCZOS)

        pair_idx += 1
        idx = f"{pair_idx:04d}"
        color_crop.save(OUT_DIR / "color" / f"{idx}.jpg", quality=95)
        gray_crop.save(OUT_DIR / "grayscale" / f"{idx}.jpg", quality=95)

        y += stride

    # Also grab the bottom crop if we didn't exactly reach it
    if y - stride + crop_size < h and h - crop_size > 0:
        box = (0, h - crop_size, crop_size, h)
        color_crop = color_img.crop(box).resize((TARGET, TARGET), Image.LANCZOS)
        gray_crop = gray_img.crop(box).resize((TARGET, TARGET), Image.LANCZOS)

        pair_idx += 1
        idx = f"{pair_idx:04d}"
        color_crop.save(OUT_DIR / "color" / f"{idx}.jpg", quality=95)
        gray_crop.save(OUT_DIR / "grayscale" / f"{idx}.jpg", quality=95)

    if pair_idx % 50 == 0:
        print(f"  {pair_idx} crops so far...")

print(f"\nDone! {pair_idx} pairs at 1024x1024")
print(f"  Color: {OUT_DIR / 'color'}")
print(f"  Grayscale: {OUT_DIR / 'grayscale'}")
