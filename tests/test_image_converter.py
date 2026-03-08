"""Unit tests for tiles/image_converter.py.

Covers:
- cleanup_images: removes temp files, silently ignores missing files
- html_to_image: raises RuntimeError when Playwright not installed
- render_deck_images: renders each HTML page with a single shared browser
"""

import sys
import os
import tempfile
import pytest
from unittest.mock import patch, call, MagicMock

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
# render_deck_images — single browser, multiple pages
# ---------------------------------------------------------------------------

class TestRenderDeckImages:
    """render_deck_images reuses a single browser for all tiles."""

    def test_empty_input_returns_empty_list(self):
        result = render_deck_images([])
        assert result == []

    def _mock_playwright(self):
        """Create a mock Playwright context manager chain."""
        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_sync_pw = MagicMock()
        mock_sync_pw.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_sync_pw.return_value.__exit__ = MagicMock(return_value=False)

        mock_module = MagicMock()
        mock_module.sync_playwright = mock_sync_pw
        return mock_module, mock_pw, mock_browser, mock_page

    def test_renders_correct_number_of_images(self):
        """Each HTML page produces one PNG path."""
        html_pages = ["<html>1</html>", "<html>2</html>", "<html>3</html>"]
        mock_module, mock_pw, mock_browser, mock_page = self._mock_playwright()

        with patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": mock_module}):
            result = render_deck_images(html_pages)

        assert len(result) == 3
        assert all(p.endswith(".png") for p in result)
        mock_pw.chromium.launch.assert_called_once()
        assert mock_browser.new_page.call_count == 3
        mock_browser.close.assert_called_once()
        cleanup_images(result)

    def test_single_page(self):
        mock_module, mock_pw, mock_browser, mock_page = self._mock_playwright()

        with patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": mock_module}):
            result = render_deck_images(["<html>test</html>"])

        assert len(result) == 1
        cleanup_images(result)

    def test_html_tempfiles_cleaned_up(self):
        """HTML temp files are removed even though PNG paths remain."""
        mock_module, mock_pw, mock_browser, mock_page = self._mock_playwright()

        with patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": mock_module}):
            result = render_deck_images(["<html>1</html>", "<html>2</html>"])

        for png_path in result:
            html_path = png_path.replace(".png", ".html")
            assert not os.path.exists(html_path)
        cleanup_images(result)
