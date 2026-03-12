"""Collect snowboarding images from Unsplash API.

Supplements the Pexels collection with Unsplash photos.
Free tier: 50 requests/hour.

Get API key at: https://unsplash.com/developers
Set UNSPLASH_ACCESS_KEY in .env
"""

import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "snowboard"

SEARCHES = {
    "action": [
        "snowboarding jump",
        "snowboard trick",
        "snowboarding powder",
        "extreme snowboarding",
    ],
    "person": [
        "snowboarder portrait",
        "snowboarder",
        "winter sport athlete",
    ],
    "board": [
        "snowboard equipment",
        "snowboard",
    ],
}


def search_unsplash(query: str, access_key: str, per_page: int = 30, page: int = 1) -> list[dict]:
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": query,
        "per_page": per_page,
        "page": page,
        "orientation": "landscape",
    }
    headers = {"Authorization": f"Client-ID {access_key}"}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("results", [])


def download_image(url: str, output_path: Path) -> bool:
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


def run():
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        print("ERROR: UNSPLASH_ACCESS_KEY not set.")
        print("Get a free key at: https://unsplash.com/developers")
        print("Then add to .env: UNSPLASH_ACCESS_KEY=your_key_here")
        return

    for category, queries in SEARCHES.items():
        out_dir = DATA_DIR / category
        out_dir.mkdir(parents=True, exist_ok=True)

        existing = set()
        for f in out_dir.glob("*.jpg"):
            parts = f.stem.split("_")
            if len(parts) >= 2:
                existing.add(parts[-1])

        count = len(list(out_dir.glob("*.jpg")))
        print(f"\n=== {category} ({count} existing) ===")

        for query in queries:
            print(f"  Searching: '{query}'...")
            try:
                results = search_unsplash(query, access_key, per_page=20)
            except Exception as e:
                print(f"    Error: {e}")
                continue

            for photo in results:
                pid = photo["id"]
                if pid in existing:
                    continue
                existing.add(pid)

                # Use "regular" size (1080px width)
                img_url = photo["urls"]["regular"]
                count += 1
                filename = f"{count:03d}_{pid}.jpg"
                ok = download_image(img_url, out_dir / filename)
                if ok:
                    print(f"    [{count}] {filename}")

                time.sleep(0.3)

            time.sleep(2)  # Stay under rate limit

        print(f"  Total {category}: {len(list(out_dir.glob('*.jpg')))} images")


if __name__ == "__main__":
    run()
