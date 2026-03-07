"""Unit tests for tiles/image_converter.py.

Covers:
- cleanup_images: removes temp files, silently ignores missing files
- html_to_image: raises RuntimeError when Playwright not installed
- render_deck_images: calls html_to_image once per HTML page
"""

import sys
import os
import tempfile
import pytest
from unittest.mock import patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tiles.image_converter import cleanup_images, html_to_image, render_deck_images


# ---------------------------------------------------------------------------
# cleanup_images
# ---------------------------------------------------------------------------

class TestCleanupImages:
    """File removal — must handle both existing and missing paths safely."""

    def test_removes_existing_files(self, tmp_path):
        file1 = tmp_path / "tile_0.png"
        file2 = tmp_path / "tile_1.png"
        file1.write_bytes(b"fake png data")
        file2.write_bytes(b"fake png data")

        cleanup_images([str(file1), str(file2)])

        assert not file1.exists()
        assert not file2.exists()

    def test_silently_ignores_missing_file(self, tmp_path):
        missing = str(tmp_path / "nonexistent.png")
        # Must not raise
        cleanup_images([missing])

    def test_empty_list_does_nothing(self):
        cleanup_images([])  # Should not raise

    def test_partial_list_still_removes_existing(self, tmp_path):
        existing = tmp_path / "real.png"
        existing.write_bytes(b"data")
        missing = str(tmp_path / "ghost.png")

        cleanup_images([str(existing), missing])

        assert not existing.exists()

    def test_real_tempfile_removed(self):
        """End-to-end: create a real tempfile, clean it up, verify gone."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
            f.write(b"\x89PNG\r\n")

        assert os.path.exists(path)
        cleanup_images([path])
        assert not os.path.exists(path)

    def test_returns_none(self, tmp_path):
        f = tmp_path / "tile.png"
        f.write_bytes(b"data")
        result = cleanup_images([str(f)])
        assert result is None

    def test_directory_path_handled_gracefully(self, tmp_path):
        """Passing a directory path instead of a file should not crash."""
        cleanup_images([str(tmp_path)])


# ---------------------------------------------------------------------------
# html_to_image — Playwright not installed
# ---------------------------------------------------------------------------

class TestHtmlToImageNoPlaywright:
    """When Playwright is not installed, html_to_image must raise RuntimeError."""

    def test_raises_runtime_error_when_playwright_missing(self):
        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            # Force ImportError path by hiding the module
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "playwright.sync_api":
                    raise ImportError("No module named 'playwright'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(RuntimeError, match="Playwright not installed"):
                    html_to_image("<html><body>test</body></html>")

    def test_html_tempfile_cleaned_up_even_on_failure(self):
        """Even when Playwright is missing the HTML temp file must be removed."""
        import builtins
        original_import = builtins.__import__
        html_paths_created = []

        original_named_temp = tempfile.NamedTemporaryFile

        def tracking_tempfile(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            if kwargs.get("suffix") == ".html" or (args and args[0] == ".html"):
                html_paths_created.append(f.name)
            return f

        def mock_import(name, *args, **kwargs):
            if name == "playwright.sync_api":
                raise ImportError("No module named 'playwright'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(RuntimeError):
                html_to_image("<html><body>test</body></html>")

        # All HTML temp files created during the call should be gone
        for p in html_paths_created:
            assert not os.path.exists(p), f"Temp file not cleaned up: {p}"


# ---------------------------------------------------------------------------
# render_deck_images
# ---------------------------------------------------------------------------

class TestRenderDeckImages:
    """render_deck_images should call html_to_image once per HTML page."""

    def test_calls_html_to_image_for_each_page(self):
        html_pages = ["<html>1</html>", "<html>2</html>", "<html>3</html>"]
        fake_paths = ["/tmp/tile_0.png", "/tmp/tile_1.png", "/tmp/tile_2.png"]

        with patch("tiles.image_converter.html_to_image", side_effect=fake_paths) as mock_convert:
            result = render_deck_images(html_pages)

        assert mock_convert.call_count == 3
        mock_convert.assert_has_calls([call(p) for p in html_pages])

    def test_returns_list_of_paths(self):
        fake_paths = ["/tmp/tile_0.png", "/tmp/tile_1.png"]
        with patch("tiles.image_converter.html_to_image", side_effect=fake_paths):
            result = render_deck_images(["<html>1</html>", "<html>2</html>"])
        assert result == fake_paths

    def test_empty_input_returns_empty_list(self):
        with patch("tiles.image_converter.html_to_image") as mock_convert:
            result = render_deck_images([])
        assert result == []
        mock_convert.assert_not_called()

    def test_single_page(self):
        with patch("tiles.image_converter.html_to_image", return_value="/tmp/tile.png"):
            result = render_deck_images(["<html>test</html>"])
        assert result == ["/tmp/tile.png"]

    def test_preserves_order(self):
        ordered_paths = [f"/tmp/tile_{i}.png" for i in range(5)]
        html_pages = [f"<html>{i}</html>" for i in range(5)]
        with patch("tiles.image_converter.html_to_image", side_effect=ordered_paths):
            result = render_deck_images(html_pages)
        assert result == ordered_paths
