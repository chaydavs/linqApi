"""Convert rendered HTML tiles to PNG images using Playwright."""

import logging
import os
import tempfile

from tiles.prompts import TILE_WIDTH, TILE_HEIGHT

logger = logging.getLogger(__name__)


def html_to_image(html: str) -> str:
    """Convert HTML string to a PNG image file.

    Returns the file path of the generated PNG.
    Caller is responsible for cleanup after sending.
    """
    # Write HTML to a temp file
    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(html)
        html_path = f.name

    img_path = html_path.replace(".html", ".png")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": TILE_WIDTH, "height": TILE_HEIGHT}
            )
            page.goto(f"file://{html_path}", timeout=10000)
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            page.screenshot(path=img_path, full_page=False, timeout=10000)
            browser.close()

        return img_path

    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        raise RuntimeError("Playwright not installed")
    finally:
        try:
            os.unlink(html_path)
        except OSError:
            pass


def render_deck_images(html_pages: list[str]) -> list[str]:
    """Render a list of HTML strings into PNG image paths.

    Reuses a single browser instance across all tiles for efficiency.
    """
    if not html_pages:
        return []

    from playwright.sync_api import sync_playwright

    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for html in html_pages:
                # Write HTML to temp file
                with tempfile.NamedTemporaryFile(
                    suffix=".html", delete=False, mode="w", encoding="utf-8"
                ) as f:
                    f.write(html)
                    html_path = f.name

                img_path = html_path.replace(".html", ".png")

                try:
                    page = browser.new_page(
                        viewport={"width": TILE_WIDTH, "height": TILE_HEIGHT}
                    )
                    page.goto(f"file://{html_path}", timeout=10000)
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                    page.screenshot(path=img_path, full_page=False, timeout=10000)
                    page.close()
                    paths.append(img_path)
                finally:
                    try:
                        os.unlink(html_path)
                    except OSError:
                        pass
        finally:
            browser.close()

    return paths


def cleanup_images(paths: list[str]):
    """Remove generated image files after sending."""
    for path in paths:
        try:
            os.unlink(path)
        except OSError:
            pass
