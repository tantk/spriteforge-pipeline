"""Download Pepper&Carrot hi-res comic pages and create grayscale versions."""
import json
import os
from pathlib import Path
from urllib.request import urlretrieve
from PIL import Image

OUT_DIR = Path(r"C:\dev\loracomp3\data\peppercarrot")
COLOR_DIR = OUT_DIR / "color"
GRAY_DIR = OUT_DIR / "grayscale"
COLOR_DIR.mkdir(parents=True, exist_ok=True)
GRAY_DIR.mkdir(parents=True, exist_ok=True)

# Episode list (39 episodes, each has varying number of pages)
EPISODES = [
    ("ep01_Potion-of-Flight", 4),
    ("ep02_Rainbow-potions", 4),
    ("ep03_The-secret-ingredients", 5),
    ("ep04_Stroke-of-genius", 4),
    ("ep05_Special-holiday-episode", 3),
    ("ep06_The-Potion-Contest", 5),
    ("ep07_The-Wish", 5),
    ("ep08_Pepper-s-Birthday-Party", 5),
    ("ep09_The-Remedy", 5),
    ("ep10_Summer-Special", 3),
    ("ep11_The-Witches-of-Chaosah", 5),
    ("ep12_Autumn-Clearout", 4),
    ("ep13_The-Pyjama-Party", 4),
    ("ep14_The-Dragon-s-Tooth", 5),
    ("ep15_The-Crystal-Ball", 5),
    ("ep16_The-Sage-of-the-Mountain", 5),
    ("ep17_A-Fresh-Start", 5),
    ("ep18_The-Encounter", 5),
    ("ep19_Pollution", 5),
    ("ep20_The-Picnic", 5),
    ("ep21_The-Magic-Contest", 6),
    ("ep22_The-Voting-System", 5),
    ("ep23_Take-a-Chance", 5),
    ("ep24_The-Unity-Tree", 6),
    ("ep25_There-are-no-Shortcuts", 5),
    ("ep26_Books-Are-Great", 5),
    ("ep27_Coriander-s-Invention", 5),
    ("ep28_The-Festivities", 5),
    ("ep29_Destroyer-of-Worlds", 5),
    ("ep30_Need-a-Hug", 4),
    ("ep31_The-Fight", 5),
    ("ep32_The-Battlefield", 5),
    ("ep33_Spell-of-War", 5),
    ("ep34_The-Knighting-of-Shichimi", 5),
    ("ep35_The-Reflection", 5),
    ("ep36_The-Surprise-Attack", 5),
    ("ep37_The-Tears-of-the-Phoenix", 5),
    ("ep38_The-Healer", 5),
    ("ep39_The-Tavern", 5),
]

BASE_URL = "https://www.peppercarrot.com/0_sources"

pair_count = 0
for ep_name, max_pages in EPISODES:
    ep_num = ep_name.split("_")[0].replace("ep", "")
    for page in range(1, max_pages + 1):
        page_str = f"{page:02d}"
        filename = f"en_Pepper-and-Carrot_by-David-Revoy_E{ep_num}P{page_str}.jpg"
        url = f"{BASE_URL}/{ep_name}/hi-res/{filename}"

        color_path = COLOR_DIR / f"E{ep_num}P{page_str}.jpg"
        gray_path = GRAY_DIR / f"E{ep_num}P{page_str}.jpg"

        if color_path.exists() and gray_path.exists():
            pair_count += 1
            continue

        try:
            if not color_path.exists():
                urlretrieve(url, color_path)

            # Create grayscale version
            img = Image.open(color_path)
            gray = img.convert("L").convert("RGB")  # Grayscale but keep as RGB
            gray.save(gray_path, quality=95)

            pair_count += 1
            if pair_count % 10 == 0:
                print(f"  Downloaded {pair_count} pairs...")
        except Exception as e:
            print(f"  Failed: {url} -> {e}")
            # Try with fewer pages
            if color_path.exists():
                color_path.unlink()
            break  # Move to next episode

print(f"\nDone! {pair_count} color/grayscale pairs")
print(f"  Color: {COLOR_DIR}")
print(f"  Grayscale: {GRAY_DIR}")
