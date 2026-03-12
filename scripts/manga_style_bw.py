"""Convert color Pepper&Carrot pages to manga-style B&W with screentones.

Real manga uses:
- Pure black ink lines (no gray)
- Screentone dot patterns for shading (not smooth gradients)
- High contrast
"""
from pathlib import Path
from PIL import Image, ImageFilter
import numpy as np

COLOR_DIR = Path(r"C:\dev\loracomp3\data\peppercarrot\pairs_1024\color")
OUT_DIR = Path(r"C:\dev\loracomp3\data\peppercarrot\pairs_1024\manga_bw")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def apply_screentone(gray_array, dot_spacing=6):
    """Convert grayscale values to screentone dot pattern."""
    h, w = gray_array.shape
    result = np.ones((h, w), dtype=np.uint8) * 255  # white background

    for y in range(0, h, dot_spacing):
        for x in range(0, h, dot_spacing):
            # Sample the average gray value in this cell
            cell = gray_array[y:y+dot_spacing, x:x+dot_spacing]
            if cell.size == 0:
                continue
            avg = cell.mean()

            # Darker areas = bigger dots
            # avg 0 = black (full dot), avg 255 = white (no dot)
            darkness = 1.0 - (avg / 255.0)
            radius = int(darkness * dot_spacing * 0.5)

            if radius > 0:
                cy, cx = y + dot_spacing // 2, x + dot_spacing // 2
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        if dy*dy + dx*dx <= radius*radius:
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w:
                                result[ny, nx] = 0
    return result


def color_to_manga(img):
    """Convert a color image to manga-style B&W."""
    gray = np.array(img.convert("L"))

    # 1. Extract strong edges for line art (pure black lines)
    img_pil = img.convert("L")
    edges = img_pil.filter(ImageFilter.FIND_EDGES)
    edges_arr = np.array(edges)
    # Threshold edges to pure black/white
    line_mask = edges_arr > 30  # edge pixels

    # 2. Apply screentone to the grayscale for shading
    screentone = apply_screentone(gray, dot_spacing=5)

    # 3. Combine: line art on top of screentone
    result = screentone.copy()
    result[line_mask] = 0  # Black lines

    # 4. Boost contrast - make darks darker, lights lighter
    result = np.clip(result, 0, 255).astype(np.uint8)

    return Image.fromarray(result)


# Process first few as test
files = sorted(COLOR_DIR.glob("*.jpg"))
print(f"Processing {len(files)} images...")

for i, f in enumerate(files):
    img = Image.open(f)
    manga = color_to_manga(img)
    manga.save(OUT_DIR / f.name, quality=95)
    if (i + 1) % 50 == 0:
        print(f"  {i+1}/{len(files)}")

print(f"\nDone! {len(files)} manga-style B&W images in {OUT_DIR}")
