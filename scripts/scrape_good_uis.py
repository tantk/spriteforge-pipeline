"""Scrape good UI screenshots from rocket.new template previews.

Uses Playwright to visit template pages, extract the preview iframe URL,
navigate to it directly, and screenshot the rendered template.
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "good_ui_clean"
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 1024

TEMPLATES = [
    # Portfolio & Agency
    "pixel-brutalist-designer-landing-page-template",
    "backstage-viral-creatoragency-landing-page-template",
    "inbox-highconverting-emailmarketing-landing-page-template",
    "keyframe-immersive-animator-landing-page-template",
    "reel-electric-motionportfolio-landing-page-template",
    "byline-compelling-freelancewriter-landing-page-template",
    "sizzle-scrollstopping-beverage-landing-page-template",
    "weave-iridescent-textile-landing-page-template",
    "byline-powerful-sportspr-landing-page-template",
    "reel-cinematic-sports-landing-page-template",
    "scaffold-precision-wordpress-landing-page-template",
    # Technology
    "fourohfour-iridescent-saas-landing-page-template",
    "cultivate-precision-agriculture-landing-page-template",
    "volt-powerful-electrical-landing-page-template",
    "uptime-brutalist-itservices-landing-page-template",
    "streak-powerful-whitelabel-landing-page-template",
    "nexus-commanding-franchise-landing-page-template",
    "recover-powerful-homeservices-landing-page-template",
    "drip-powerful-dentalmarketing-landing-page-template",
    "ledger-powerful-tobaccocrm-landing-page-template",
    "triage-powerful-manufacturing-landing-page-template",
    "ledger-powerful-realestatepos-landing-page-template",
    "encode-authoritative-dnastorage-landing-page-template",
    # Food & Beverage
    "tawa-authentic-southindian-landing-page-template",
    "plara-artisan-thaidining-landing-page-template",
    "nourish-wholesome-macrobiotic-landing-page-template-1",
    "savor-vibrant-mealdelivery-landing-page-template",
    "thali-vibrant-restaurant-landing-page-template",
    "forage-artisan-paleo-landing-page-template",
    "pulse-wholesome-mealkit-landing-page-template",
    "asado-sizzling-parrilla-landing-page-template",
    "shuck-artisan-oysterbar-landing-page-template",
    "mercado-artisan-grocery-landing-page-template",
    "plancha-sizzling-foodtruck-landing-page-template",
    # Health & Medical
    "clarity-sharp-optometrist-landing-page-template",
    "digest-gastroenterology-landing-page-template",
    "pulse-trust-cardiology-landing-page-template",
    "harmony-dental-billing-landing-page-template",
    "breathe-trusted-pediatricallergy-landing-page-template",
    "thrive-menopause-clinic-landing-page-template",
    "rounds-authoritative-research-landing-page-template",
    # Professional Services
    "vows-trusted-officiant-landing-page-template",
    "aisle-transformative-weddingtech-landing-page-template",
    "surveill-authoritative-investigation-landing-page-template",
    "welder-highconverting-booking-landing-page-template",
    "torch-authoritative-welding-landing-page-template",
]

BASE_URL = "https://www.rocket.new/templates/"


async def screenshot_template(browser, slug: str, index: int, total: int) -> bool:
    """Visit a template page, find the iframe preview URL, then screenshot it directly."""
    url = BASE_URL + slug
    output_path = OUTPUT_DIR / f"{slug}.png"

    if output_path.exists():
        print(f"  [{index}/{total}] {slug} already exists, skipping")
        return True

    page = None
    try:
        # Step 1: Visit template page and extract iframe src
        page = await browser.new_page()
        print(f"  [{index}/{total}] Loading {slug}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)

        iframe_el = await page.query_selector("iframe")
        if not iframe_el:
            print(f"    No iframe found, skipping")
            return False

        iframe_src = await iframe_el.get_attribute("src")
        if not iframe_src:
            print(f"    Iframe has no src, skipping")
            return False

        print(f"    Found preview URL: {iframe_src[:80]}...")
        await page.close()
        page = None

        # Step 2: Visit the iframe URL directly and screenshot it
        page = await browser.new_page()
        await page.set_viewport_size({"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})
        await page.goto(iframe_src, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Dismiss cookie banners and hide rocket.new watermark
        await page.evaluate("""() => {
            // Remove common cookie banner selectors
            const cookieSelectors = [
                '[class*="cookie"]', '[class*="Cookie"]',
                '[class*="consent"]', '[class*="Consent"]',
                '[class*="banner"]', '[id*="cookie"]',
                '[id*="consent"]', '[class*="gdpr"]',
                '[class*="notice"]',
            ];
            for (const sel of cookieSelectors) {
                document.querySelectorAll(sel).forEach(el => el.remove());
            }

            // Remove rocket.new badge/watermark (usually bottom-right fixed element)
            const allEls = document.querySelectorAll('a, div, span, img');
            for (const el of allEls) {
                const text = (el.textContent || '').toLowerCase();
                const href = (el.getAttribute('href') || '').toLowerCase();
                if (text.includes('rocket.new') || text.includes('rocket new') ||
                    href.includes('rocket.new') || href.includes('builtwithrocket')) {
                    el.remove();
                }
            }

            // Remove any fixed/sticky elements at the bottom (common for badges & banners)
            document.querySelectorAll('*').forEach(el => {
                const style = window.getComputedStyle(el);
                if ((style.position === 'fixed' || style.position === 'sticky') &&
                    el.getBoundingClientRect().bottom > window.innerHeight - 80) {
                    el.remove();
                }
            });
        }""")
        await page.wait_for_timeout(500)

        await page.screenshot(
            path=str(output_path),
            clip={"x": 0, "y": 0, "width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        )
        print(f"    -> {output_path.name}")
        return True
    except Exception as e:
        print(f"    FAILED: {e}")
        return False
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def run():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: pip install playwright && playwright install chromium")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Scraping {len(TEMPLATES)} templates from rocket.new...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            device_scale_factor=1,
        )

        success = 0
        for i, slug in enumerate(TEMPLATES):
            ok = await screenshot_template(context, slug, i + 1, len(TEMPLATES))
            if ok:
                success += 1
            await asyncio.sleep(2)

        await browser.close()

    print(f"\nDone. Saved {success}/{len(TEMPLATES)} screenshots to {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(run())
