"""Collect snowboarding training data from Pexels API.

Downloads three categories of images:
  1. Snowboarder portraits/standing shots (input 1)
  2. Snowboard product/equipment shots (input 2)
  3. Snowboarding action shots (target output)

Requires a free Pexels API key: https://www.pexels.com/api/
Set PEXELS_API_KEY in .env or pass as argument.
"""

import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "snowboard"

CATEGORIES = {
    "action": {
        "dir": DATA_DIR / "action",
        "queries": [
            "snowboarding action jump",
            "snowboarder trick air",
            "snowboarding powder spray",
            "snowboard halfpipe",
            "extreme snowboarding mountain",
            "snowboarder backflip",
        ],
        "per_query": 15,
    },
    "person": {
        "dir": DATA_DIR / "person",
        "queries": [
            "snowboarder portrait",
            "snowboarder standing snow",
            "person snowboard gear",
            "skier snowboarder face",
            "winter sport athlete portrait",
        ],
        "per_query": 15,
    },
    "board": {
        "dir": DATA_DIR / "board",
        "queries": [
            "snowboard equipment",
            "snowboard close up",
            "snowboard bindings",
            "colorful snowboard",
            "snowboard standing snow",
        ],
        "per_query": 15,
    },
}

HEADERS = {}


def search_pexels(query: str, per_page: int = 15, page: int = 1) -> list[dict]:
    """Search Pexels for photos."""
    url = "https://api.pexels.com/v1/search"
    params = {
        "query": query,
        "per_page": per_page,
        "page": page,
        "orientation": "landscape",
        "size": "large",
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("photos", [])


def download_image(url: str, output_path: Path) -> bool:
    """Download an image to disk."""
    if output_path.exists():
        return True
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
        return True
    except Exception as e:
        print(f"    FAILED: {e}")
        return False


def collect_category(name: str, config: dict) -> int:
    """Collect images for one category."""
    out_dir = config["dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    existing = len(list(out_dir.glob("*.jpg")))
    print(f"\n{'='*50}")
    print(f"Category: {name} ({existing} existing)")
    print(f"{'='*50}")

    count = existing
    seen_ids = set()

    # Track existing IDs to avoid duplicates
    for f in out_dir.glob("*.jpg"):
        parts = f.stem.split("_")
        if len(parts) >= 2:
            seen_ids.add(parts[-1])

    for query in config["queries"]:
        print(f"\n  Searching: '{query}'...")
        try:
            photos = search_pexels(query, per_page=config["per_query"])
        except Exception as e:
            print(f"    Search failed: {e}")
            continue

        for photo in photos:
            photo_id = str(photo["id"])
            if photo_id in seen_ids:
                continue
            seen_ids.add(photo_id)

            # Use the "large" size (940px width) - good balance of quality/size
            img_url = photo["src"]["large"]
            count += 1
            filename = f"{count:03d}_{photo_id}.jpg"
            output_path = out_dir / filename

            ok = download_image(img_url, output_path)
            if ok:
                print(f"    [{count}] {filename}")

            time.sleep(0.2)  # Rate limiting

        time.sleep(1)  # Between queries

    final_count = len(list(out_dir.glob("*.jpg")))
    print(f"\n  Total {name}: {final_count} images")
    return final_count


def run():
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        print("ERROR: PEXELS_API_KEY not set.")
        print("Get a free key at: https://www.pexels.com/api/")
        print("Then add to .env: PEXELS_API_KEY=your_key_here")
        return

    HEADERS["Authorization"] = api_key
    print(f"Output directory: {DATA_DIR}")

    totals = {}
    for name, config in CATEGORIES.items():
        totals[name] = collect_category(name, config)

    print(f"\n{'='*50}")
    print("Summary:")
    for name, count in totals.items():
        print(f"  {name}: {count} images")
    print(f"  Total: {sum(totals.values())} images")


if __name__ == "__main__":
    run()
