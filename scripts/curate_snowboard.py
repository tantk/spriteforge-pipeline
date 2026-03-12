"""Curate snowboard images: deduplicate, filter, and organize.

Steps:
1. Deduplicate across categories (same photo ID kept in best category)
2. Remove too-small files (< 30KB likely low quality/broken)
3. Copy curated images to data/snowboard_curated/
4. Generate a review HTML for manual spot-checking
"""

import shutil
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "snowboard"
CURATED_DIR = PROJECT_ROOT / "data" / "snowboard_curated"
MIN_FILE_SIZE_KB = 30
MIN_WIDTH = 800
MIN_HEIGHT = 500

# Priority: which category gets the photo if it appears in multiple
CATEGORY_PRIORITY = {"action": 1, "person": 2, "board": 3}


def get_photo_id(filename: str) -> str:
    """Extract photo ID from filename like '001_31934896.jpg'."""
    parts = filename.rsplit(".", 1)[0].split("_", 1)
    return parts[1] if len(parts) >= 2 else parts[0]


def run():
    # Step 1: Inventory all files and their categories
    all_files = {}  # photo_id -> [(category, path), ...]
    for cat in ["action", "person", "board"]:
        cat_dir = RAW_DIR / cat
        if not cat_dir.exists():
            continue
        for f in cat_dir.glob("*.jpg"):
            pid = get_photo_id(f.name)
            if pid not in all_files:
                all_files[pid] = []
            all_files[pid].append((cat, f))

    print(f"Total unique photo IDs: {len(all_files)}")

    # Step 2: Assign each photo to ONE category (highest priority)
    assignments = {"action": [], "person": [], "board": []}
    for pid, entries in all_files.items():
        # Pick the category with highest priority (lowest number)
        best = min(entries, key=lambda x: CATEGORY_PRIORITY[x[0]])
        cat, path = best
        assignments[cat].append((pid, path))

    for cat, items in assignments.items():
        print(f"  {cat}: {len(items)} (after dedup)")

    # Step 3: Filter by file size and dimensions
    curated = {"action": [], "person": [], "board": []}
    rejected = {"too_small_file": 0, "too_small_dims": 0, "error": 0}

    for cat, items in assignments.items():
        for pid, path in items:
            # File size check
            size_kb = path.stat().st_size / 1024
            if size_kb < MIN_FILE_SIZE_KB:
                rejected["too_small_file"] += 1
                continue

            # Dimension check
            try:
                img = Image.open(path)
                w, h = img.size
                if w < MIN_WIDTH or h < MIN_HEIGHT:
                    rejected["too_small_dims"] += 1
                    continue
                curated[cat].append((pid, path, w, h, size_kb))
            except Exception:
                rejected["error"] += 1
                continue

    print(f"\nAfter filtering:")
    for cat, items in curated.items():
        print(f"  {cat}: {len(items)}")
    print(f"  Rejected: {rejected}")

    # Step 4: Copy to curated directory
    for cat in curated:
        out_dir = CURATED_DIR / cat
        out_dir.mkdir(parents=True, exist_ok=True)

    for cat, items in curated.items():
        # Sort by file size descending (larger = likely higher quality)
        items.sort(key=lambda x: x[4], reverse=True)
        for i, (pid, path, w, h, size_kb) in enumerate(items):
            idx = f"{i+1:03d}"
            dest = CURATED_DIR / cat / f"{idx}_{pid}.jpg"
            shutil.copy2(path, dest)

    # Step 5: Generate review HTML
    html_path = CURATED_DIR / "review.html"
    html = ['<!DOCTYPE html><html><head><meta charset="utf-8">']
    html.append('<style>')
    html.append('body { font-family: sans-serif; background: #111; color: #eee; }')
    html.append('.category { margin: 20px 0; }')
    html.append('.category h2 { color: #4af; }')
    html.append('.grid { display: flex; flex-wrap: wrap; gap: 8px; }')
    html.append('.card { width: 200px; text-align: center; }')
    html.append('.card img { width: 200px; height: 133px; object-fit: cover; border-radius: 4px; }')
    html.append('.card .label { font-size: 11px; color: #888; margin-top: 2px; }')
    html.append('</style></head><body>')
    html.append('<h1>Snowboard Data Review</h1>')

    for cat, items in curated.items():
        html.append(f'<div class="category"><h2>{cat} ({len(items)} images)</h2>')
        html.append('<div class="grid">')
        for i, (pid, path, w, h, size_kb) in enumerate(items):
            idx = f"{i+1:03d}"
            fname = f"{idx}_{pid}.jpg"
            html.append(f'<div class="card">')
            html.append(f'<img src="{cat}/{fname}" loading="lazy">')
            html.append(f'<div class="label">{fname}<br>{w}x{h} {size_kb:.0f}KB</div>')
            html.append(f'</div>')
        html.append('</div></div>')

    html.append('</body></html>')
    html_path.write_text('\n'.join(html), encoding='utf-8')
    print(f"\nReview page: {html_path}")
    print("Open in browser to visually inspect all images.")

    # Summary
    total = sum(len(v) for v in curated.values())
    print(f"\nTotal curated: {total} images")


if __name__ == "__main__":
    run()
