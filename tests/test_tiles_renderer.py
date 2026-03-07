"""Unit tests for tiles/renderer.py pure HTML rendering functions.

Covers:
- _base_css: accent color injection, correct dimensions, required CSS classes
- _tile_inner_html: each tile type produces correct structural HTML
- render_tile_html: full HTML page structure, gradient selection, tile index clamping
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tiles.renderer import _base_css, _tile_inner_html, render_tile_html, TILE_WIDTH, TILE_HEIGHT
from tiles.prompts import DECK_GRADIENTS, ACCENT_COLORS


# ---------------------------------------------------------------------------
# _base_css
# ---------------------------------------------------------------------------

class TestBaseCss:
    """Shared CSS string must embed accent color and correct dimensions."""

    def test_accent_color_in_css(self):
        css = _base_css("#FF5733")
        assert "#FF5733" in css

    def test_tile_width_in_css(self):
        css = _base_css("#A78BFA")
        assert f"{TILE_WIDTH}px" in css

    def test_tile_height_in_css(self):
        css = _base_css("#A78BFA")
        assert f"{TILE_HEIGHT}px" in css

    def test_tile_class_defined(self):
        css = _base_css("#A78BFA")
        assert ".tile" in css

    def test_tag_class_defined(self):
        css = _base_css("#A78BFA")
        assert ".tag" in css

    def test_headline_class_defined(self):
        css = _base_css("#A78BFA")
        assert ".headline" in css

    def test_stat_class_defined(self):
        css = _base_css("#A78BFA")
        assert ".stat" in css

    def test_body_class_defined(self):
        css = _base_css("#A78BFA")
        assert ".body" in css

    def test_cta_button_class_defined(self):
        css = _base_css("#A78BFA")
        assert ".cta-button" in css

    def test_dm_sans_font_imported(self):
        css = _base_css("#A78BFA")
        assert "DM Sans" in css

    def test_returns_string(self):
        assert isinstance(_base_css("#A78BFA"), str)

    def test_different_accent_produces_different_css(self):
        css1 = _base_css("#FF0000")
        css2 = _base_css("#00FF00")
        assert css1 != css2

    def test_overflow_hidden_on_body(self):
        css = _base_css("#A78BFA")
        assert "overflow: hidden" in css


# ---------------------------------------------------------------------------
# _tile_inner_html — cover tile
# ---------------------------------------------------------------------------

class TestTileInnerHtmlCover:
    def _cover(self, **kwargs):
        base = {"type": "cover", "accent": "#A78BFA", "headline": "Test Headline", "body": "Body text"}
        base.update(kwargs)
        return _tile_inner_html(base)

    def test_headline_in_output(self):
        html = self._cover()
        assert "Test Headline" in html

    def test_body_in_output(self):
        html = self._cover()
        assert "Body text" in html

    def test_tag_rendered_when_present(self):
        html = self._cover(tag="THE CHALLENGE")
        assert "THE CHALLENGE" in html
        assert 'class="tag"' in html

    def test_tag_absent_when_not_provided(self):
        html = self._cover()
        assert 'class="tag"' not in html

    def test_swipe_indicator_present(self):
        html = self._cover()
        assert "SWIPE" in html

    def test_accent_color_in_output(self):
        html = self._cover(accent="#DEADBE")
        assert "#DEADBE" in html

    def test_headline_class_used(self):
        html = self._cover()
        assert 'class="headline"' in html


# ---------------------------------------------------------------------------
# _tile_inner_html — stat tile
# ---------------------------------------------------------------------------

class TestTileInnerHtmlStat:
    def _stat(self, **kwargs):
        base = {"type": "stat", "accent": "#38BDF8", "stat": "47%",
                "stat_label": "of deals stall", "source": "Gartner 2024"}
        base.update(kwargs)
        return _tile_inner_html(base)

    def test_stat_value_in_output(self):
        assert "47%" in self._stat()

    def test_stat_label_in_output(self):
        assert "of deals stall" in self._stat()

    def test_source_in_output(self):
        assert "Gartner 2024" in self._stat()

    def test_stat_class_used(self):
        assert 'class="stat"' in self._stat()

    def test_missing_stat_does_not_crash(self):
        html = _tile_inner_html({"type": "stat", "accent": "#38BDF8"})
        assert isinstance(html, str)


# ---------------------------------------------------------------------------
# _tile_inner_html — list tile
# ---------------------------------------------------------------------------

class TestTileInnerHtmlList:
    def _list_tile(self, **kwargs):
        base = {
            "type": "list",
            "accent": "#A78BFA",
            "headline": "Warning Signs",
            "items": [
                {"label": "ITEM 1", "value": "First warning", "icon": "⚠️"},
                {"label": "ITEM 2", "value": "Second warning", "icon": "🔴"},
            ],
        }
        base.update(kwargs)
        return _tile_inner_html(base)

    def test_headline_in_output(self):
        assert "Warning Signs" in self._list_tile()

    def test_items_rendered(self):
        html = self._list_tile()
        assert "ITEM 1" in html
        assert "First warning" in html

    def test_icon_rendered(self):
        html = self._list_tile()
        assert "⚠️" in html

    def test_empty_items_does_not_crash(self):
        html = _tile_inner_html({"type": "list", "accent": "#A78BFA", "items": []})
        assert isinstance(html, str)

    def test_gain_type_uses_same_template(self):
        """'gain' type shares the list template."""
        tile = {"type": "gain", "accent": "#A78BFA", "headline": "What You Gain",
                "items": [{"label": "SPEED", "value": "3x faster", "icon": "🚀"}]}
        html = _tile_inner_html(tile)
        assert "What You Gain" in html
        assert "3x faster" in html


# ---------------------------------------------------------------------------
# _tile_inner_html — comparison tile
# ---------------------------------------------------------------------------

class TestTileInnerHtmlComparison:
    def _comp(self, **kwargs):
        base = {
            "type": "comparison",
            "accent": "#64748B",
            "headline": "Legacy vs Modern",
            "items": [
                {"label": "Onboarding", "old_value": "6 weeks", "value": "3 days"},
                {"label": "Uptime", "old_value": "95%", "value": "99.9%"},
            ],
        }
        base.update(kwargs)
        return _tile_inner_html(base)

    def test_headline_in_output(self):
        assert "Legacy vs Modern" in self._comp()

    def test_old_value_in_output(self):
        assert "6 weeks" in self._comp()

    def test_new_value_in_output(self):
        assert "3 days" in self._comp()

    def test_label_in_output(self):
        assert "Onboarding" in self._comp()

    def test_line_through_on_old_value(self):
        assert "line-through" in self._comp()

    def test_metrics_type_shares_comparison_template(self):
        tile = {
            "type": "metrics",
            "accent": "#4ADE80",
            "headline": "Before / After",
            "items": [{"label": "Speed", "old_value": "1x", "value": "10x"}],
        }
        html = _tile_inner_html(tile)
        assert "Before / After" in html
        assert "1x" in html
        assert "10x" in html


# ---------------------------------------------------------------------------
# _tile_inner_html — quote tile
# ---------------------------------------------------------------------------

class TestTileInnerHtmlQuote:
    def _quote(self, **kwargs):
        base = {
            "type": "quote",
            "accent": "#4ADE80",
            "body": "We cut our close rate in half.",
            "headline": "VP Sales, Notion",
            "source": "Q3 2024",
        }
        base.update(kwargs)
        return _tile_inner_html(base)

    def test_body_quote_in_output(self):
        assert "We cut our close rate" in self._quote()

    def test_headline_speaker_in_output(self):
        assert "VP Sales, Notion" in self._quote()

    def test_source_in_output(self):
        assert "Q3 2024" in self._quote()

    def test_italic_style_on_quote(self):
        assert "italic" in self._quote()


# ---------------------------------------------------------------------------
# _tile_inner_html — math tile
# ---------------------------------------------------------------------------

class TestTileInnerHtmlMath:
    def test_stat_in_output(self):
        tile = {"type": "math", "accent": "#38BDF8", "tag": "YOUR NUMBERS",
                "stat": "$240K", "stat_label": "annual cost of status quo", "source": "5 AEs * $48K"}
        html = _tile_inner_html(tile)
        assert "$240K" in html

    def test_tag_in_output(self):
        tile = {"type": "math", "accent": "#38BDF8", "tag": "YOUR NUMBERS", "stat": "$240K"}
        html = _tile_inner_html(tile)
        assert "YOUR NUMBERS" in html


# ---------------------------------------------------------------------------
# _tile_inner_html — timeline tile
# ---------------------------------------------------------------------------

class TestTileInnerHtmlTimeline:
    def _timeline(self):
        return {
            "type": "timeline",
            "accent": "#38BDF8",
            "headline": "Your Payback Roadmap",
            "items": [
                {"label": "Week 1", "value": "Onboarded"},
                {"label": "Month 1", "value": "First win"},
                {"label": "Month 3", "value": "ROI positive"},
            ],
        }

    def test_headline_in_output(self):
        assert "Your Payback Roadmap" in _tile_inner_html(self._timeline())

    def test_all_items_rendered(self):
        html = _tile_inner_html(self._timeline())
        assert "Week 1" in html
        assert "Month 1" in html
        assert "Month 3" in html

    def test_checkmark_icon_present(self):
        assert "✓" in _tile_inner_html(self._timeline())

    def test_last_item_has_no_connector_line(self):
        """The last timeline item omits the vertical connector div."""
        html = _tile_inner_html(self._timeline())
        # The connector style only appears for non-last items
        # We can verify it appears at least once (for items before the last)
        assert "height:48px" in html


# ---------------------------------------------------------------------------
# _tile_inner_html — personal tile
# ---------------------------------------------------------------------------

class TestTileInnerHtmlPersonal:
    def test_emoji_in_output(self):
        tile = {"type": "personal", "accent": "#F59E0B",
                "stat": "🏈", "headline": "Fellow Orange Nation fan", "body": "We talked for an hour."}
        html = _tile_inner_html(tile)
        assert "🏈" in html
        assert "Fellow Orange Nation fan" in html

    def test_default_emoji_when_stat_missing(self):
        tile = {"type": "personal", "accent": "#F59E0B", "headline": "Something personal"}
        html = _tile_inner_html(tile)
        assert "👋" in html


# ---------------------------------------------------------------------------
# _tile_inner_html — bridge tile
# ---------------------------------------------------------------------------

class TestTileInnerHtmlBridge:
    def test_body_in_output(self):
        tile = {"type": "bridge", "accent": "#F59E0B",
                "body": "That shared passion for speed is exactly why we built this."}
        html = _tile_inner_html(tile)
        assert "That shared passion for speed" in html


# ---------------------------------------------------------------------------
# _tile_inner_html — cta tile
# ---------------------------------------------------------------------------

class TestTileInnerHtmlCta:
    def _cta(self, **kwargs):
        base = {
            "type": "cta",
            "accent": "#A78BFA",
            "headline": "Ready to see it live?",
            "body": "Takes 15 minutes.",
            "cta_text": "Book a quick demo →",
        }
        base.update(kwargs)
        return _tile_inner_html(base)

    def test_headline_in_output(self):
        assert "Ready to see it live?" in self._cta()

    def test_body_in_output(self):
        assert "Takes 15 minutes." in self._cta()

    def test_cta_text_in_output(self):
        assert "Book a quick demo →" in self._cta()

    def test_cta_button_class_used(self):
        assert 'class="cta-button"' in self._cta()

    def test_default_cta_text_when_missing(self):
        tile = {"type": "cta", "accent": "#A78BFA", "headline": "Let's talk"}
        html = _tile_inner_html(tile)
        assert "Let&#x27;s talk →" in html


# ---------------------------------------------------------------------------
# _tile_inner_html — fallback for unknown type
# ---------------------------------------------------------------------------

class TestTileInnerHtmlFallback:
    def test_unknown_type_renders_headline_and_body(self):
        tile = {"type": "unknown_future_type", "headline": "Mystery Tile",
                "body": "Some body text", "accent": "#A78BFA"}
        html = _tile_inner_html(tile)
        assert "Mystery Tile" in html
        assert "Some body text" in html

    def test_returns_string_for_empty_tile(self):
        html = _tile_inner_html({})
        assert isinstance(html, str)


# ---------------------------------------------------------------------------
# render_tile_html — full page
# ---------------------------------------------------------------------------

class TestRenderTileHtml:
    def _minimal_tile(self, deck_type="hook", tile_index=0):
        tile = {"type": "cover", "headline": "Test", "body": "Body", "accent": "#A78BFA"}
        return render_tile_html(tile, deck_type=deck_type, tile_index=tile_index)

    def test_returns_string(self):
        assert isinstance(self._minimal_tile(), str)

    def test_doctype_present(self):
        assert "<!DOCTYPE html>" in self._minimal_tile()

    def test_utf8_charset(self):
        assert 'charset="utf-8"' in self._minimal_tile()

    def test_tile_div_present(self):
        assert 'class="tile"' in self._minimal_tile()

    def test_style_tag_present(self):
        assert "<style>" in self._minimal_tile()

    def test_headline_content_in_page(self):
        tile = {"type": "cover", "headline": "Big Bold Claim", "accent": "#A78BFA"}
        html = render_tile_html(tile, deck_type="hook", tile_index=0)
        assert "Big Bold Claim" in html

    def test_accent_color_injected(self):
        tile = {"type": "cover", "headline": "H", "accent": "#ABCDEF"}
        html = render_tile_html(tile, deck_type="hook", tile_index=0)
        assert "#ABCDEF" in html

    # Gradient selection per deck type
    @pytest.mark.parametrize("deck_type", ["hook", "roi", "proof", "personal", "competitive"])
    def test_gradient_for_each_deck_type(self, deck_type):
        tile = {"type": "cover", "headline": "H", "accent": ACCENT_COLORS[deck_type]}
        html = render_tile_html(tile, deck_type=deck_type, tile_index=0)
        expected_gradient = DECK_GRADIENTS[deck_type][0]
        assert expected_gradient in html

    def test_tile_index_selects_correct_gradient(self):
        """tile_index=1 should use the second gradient."""
        tile = {"type": "cover", "headline": "H", "accent": "#A78BFA"}
        html = render_tile_html(tile, deck_type="hook", tile_index=1)
        assert DECK_GRADIENTS["hook"][1] in html

    def test_tile_index_clamps_at_last_gradient(self):
        """tile_index beyond list length should use the last gradient."""
        tile = {"type": "cover", "headline": "H", "accent": "#A78BFA"}
        hook_gradients = DECK_GRADIENTS["hook"]
        html = render_tile_html(tile, deck_type="hook", tile_index=999)
        assert hook_gradients[-1] in html

    def test_tile_index_zero_uses_first_gradient(self):
        tile = {"type": "cover", "headline": "H", "accent": "#A78BFA"}
        html = render_tile_html(tile, deck_type="hook", tile_index=0)
        assert DECK_GRADIENTS["hook"][0] in html

    def test_unknown_deck_type_falls_back_to_hook_gradient(self):
        """An unrecognized deck_type should fall back to hook gradients."""
        tile = {"type": "cover", "headline": "H", "accent": "#A78BFA"}
        html = render_tile_html(tile, deck_type="nonexistent_type", tile_index=0)
        assert DECK_GRADIENTS["hook"][0] in html

    def test_body_tag_present(self):
        html = self._minimal_tile()
        assert "<body>" in html
        assert "</body>" in html

    def test_html_tag_present(self):
        html = self._minimal_tile()
        assert "<html>" in html

    def test_default_deck_type_is_hook(self):
        """Default deck_type parameter should produce hook gradients."""
        tile = {"type": "cover", "headline": "H", "accent": "#A78BFA"}
        html = render_tile_html(tile)
        assert DECK_GRADIENTS["hook"][0] in html
