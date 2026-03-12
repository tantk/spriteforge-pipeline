"""Screenshot the DefaultTaste HTML files as 'bad UI' training data.

Reads HTML files from defaulttaste/public/artifacts/gemini-flash/,
opens each in a headless browser, and saves a 1024x1024 screenshot
to data/bad_ui/.
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTML_DIR = PROJECT_ROOT / "defaulttaste" / "public" / "artifacts" / "gemini-flash"
OUTPUT_DIR = PROJECT_ROOT / "data" / "bad_ui"
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 1024
SCREENSHOT_SIZE = 1024
MAX_SCREENSHOTS = 50


async def run():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html_files = sorted(HTML_DIR.glob("*.html"))[:MAX_SCREENSHOTS]

    if not html_files:
        print(f"No HTML files found in {HTML_DIR}")
        sys.exit(1)

    print(f"Screenshotting {len(html_files)} HTML files...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            device_scale_factor=1,
        )

        for i, html_file in enumerate(html_files):
            page = await context.new_page()
            try:
                file_url = html_file.as_uri()
                await page.goto(file_url, wait_until="networkidle", timeout=15000)
                # Wait a bit for any CSS animations to settle
                await page.wait_for_timeout(500)

                output_path = OUTPUT_DIR / f"{html_file.stem}.png"
                await page.screenshot(
                    path=str(output_path),
                    clip={"x": 0, "y": 0, "width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                )
                print(f"  [{i+1}/{len(html_files)}] {html_file.stem} -> {output_path.name}")
            except Exception as e:
                print(f"  [{i+1}/{len(html_files)}] {html_file.stem} FAILED: {e}")
            finally:
                await page.close()

        await browser.close()

    saved = len(list(OUTPUT_DIR.glob("*.png")))
    print(f"\nDone. Saved {saved} screenshots to {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(run())
