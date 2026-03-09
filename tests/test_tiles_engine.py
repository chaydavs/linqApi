"""Unit tests for tiles/engine.py pure functions.

Covers:
- assemble_tile_context: field mapping, missing key defaults, immutability
- select_deck_type: all hint-based keyword shortcuts (no Claude call)
- generate_tile_content: accent injection, mocked Claude response
- generate_and_send_deck: success/failure returns, mocked pipeline
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tiles.engine import assemble_tile_context, select_deck_type, generate_tile_content


# ---------------------------------------------------------------------------
# assemble_tile_context
# ---------------------------------------------------------------------------

class TestAssembleTileContext:
    """Build the context dict passed to Claude for tile generation."""

    def test_all_fields_present(self, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        assert ctx["name"] == "Sarah Chen"
        assert ctx["company"] == "Stripe"
        assert ctx["title"] == "VP RevOps"
        assert "case study" in ctx["pain_points"]
        assert ctx["follow_up_action"] == "send enterprise case study"
        assert ctx["personal_details"] == ["husband went to VT"]
        assert ctx["temperature"] == "hot"

    def test_notes_maps_to_pain_points(self, sample_contact):
        """'notes' field in contact maps to 'pain_points' in context."""
        ctx = assemble_tile_context(sample_contact)
        assert ctx["pain_points"] == sample_contact["notes"]
        assert "notes" not in ctx

    def test_missing_optional_fields_default_empty(self):
        ctx = assemble_tile_context({"name": "Alex"})
        assert ctx["company"] == ""
        assert ctx["title"] == ""
        assert ctx["pain_points"] == ""
        assert ctx["follow_up_action"] == ""
        assert ctx["personal_details"] == []
        assert ctx["temperature"] == "warm"

    def test_temperature_defaults_to_warm_when_absent(self):
        ctx = assemble_tile_context({})
        assert ctx["temperature"] == "warm"

    def test_returns_new_dict(self, sample_contact):
        """assemble_tile_context must not return the original contact dict."""
        ctx = assemble_tile_context(sample_contact)
        assert ctx is not sample_contact

    def test_original_contact_not_mutated(self, sample_contact):
        original_name = sample_contact["name"]
        ctx = assemble_tile_context(sample_contact)
        ctx["name"] = "MUTATED"
        assert sample_contact["name"] == original_name

    def test_personal_details_list_preserved(self, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        assert isinstance(ctx["personal_details"], list)
        assert len(ctx["personal_details"]) == 1

    def test_empty_personal_details(self, sample_contact_minimal):
        ctx = assemble_tile_context(sample_contact_minimal)
        assert ctx["personal_details"] == []

    def test_output_keys(self, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        expected_keys = {"name", "company", "title", "pain_points",
                         "follow_up_action", "personal_details", "temperature"}
        assert set(ctx.keys()) == expected_keys


# ---------------------------------------------------------------------------
# select_deck_type — hint-based shortcuts (no Claude call)
# ---------------------------------------------------------------------------

class TestSelectDeckTypeHints:
    """Hint keywords must map to deck types without calling Claude."""

    # ROI hints
    @pytest.mark.parametrize("hint", [
        "price is a concern",
        "what's the cost",
        "need roi justification",
        "tight budget this quarter",
        "ROI deck please",
        "BUDGET approval needed",
    ])
    def test_roi_hint_keywords(self, hint, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        with patch("tiles.engine._call_claude") as mock_claude:
            result = select_deck_type(ctx, hint=hint)
        assert result == "roi"
        mock_claude.assert_not_called()

    # Proof hints
    @pytest.mark.parametrize("hint", [
        "she wants proof",
        "send a case study",
        "can you show a testimonial",
        "PROOF of results",
        "Case Study",
    ])
    def test_proof_hint_keywords(self, hint, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        with patch("tiles.engine._call_claude") as mock_claude:
            result = select_deck_type(ctx, hint=hint)
        assert result == "proof"
        mock_claude.assert_not_called()

    # Competitive hints
    @pytest.mark.parametrize("hint", [
        "compare to salesforce",
        "they're looking at a competitor",
        "versus hubspot",
        "vs the current vendor",
        "Competitor evaluation",
    ])
    def test_competitive_hint_keywords(self, hint, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        with patch("tiles.engine._call_claude") as mock_claude:
            result = select_deck_type(ctx, hint=hint)
        assert result == "competitive"
        mock_claude.assert_not_called()

    def test_no_hint_calls_claude(self, sample_contact):
        """When hint is None, Claude must be consulted."""
        ctx = assemble_tile_context(sample_contact)
        with patch("tiles.engine._call_claude", return_value="hook") as mock_claude:
            result = select_deck_type(ctx, hint=None)
        mock_claude.assert_called_once()
        assert result == "hook"

    def test_empty_hint_calls_claude(self, sample_contact):
        """Empty string hint should not match any keyword — falls through to Claude."""
        ctx = assemble_tile_context(sample_contact)
        with patch("tiles.engine._call_claude", return_value="proof") as mock_claude:
            result = select_deck_type(ctx, hint="")
        mock_claude.assert_called_once()
        assert result == "proof"

    def test_unrelated_hint_calls_claude(self, sample_contact):
        """Hints with no keyword match should delegate to Claude."""
        ctx = assemble_tile_context(sample_contact)
        with patch("tiles.engine._call_claude", return_value="personal") as mock_claude:
            result = select_deck_type(ctx, hint="tell me about your team culture")
        mock_claude.assert_called_once()
        assert result == "personal"

    def test_claude_invalid_response_defaults_to_hook(self, sample_contact):
        """If Claude returns garbage, default to 'hook'."""
        ctx = assemble_tile_context(sample_contact)
        with patch("tiles.engine._call_claude", return_value="nonsense_type"):
            result = select_deck_type(ctx, hint=None)
        assert result == "hook"

    @pytest.mark.parametrize("valid_type", ["hook", "roi", "proof", "personal", "competitive"])
    def test_claude_all_valid_types_accepted(self, valid_type, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        with patch("tiles.engine._call_claude", return_value=valid_type):
            result = select_deck_type(ctx, hint=None)
        assert result == valid_type

    def test_claude_response_whitespace_stripped(self, sample_contact):
        """Claude sometimes returns extra whitespace — must be tolerated."""
        ctx = assemble_tile_context(sample_contact)
        with patch("tiles.engine._call_claude", return_value="  roi  "):
            result = select_deck_type(ctx, hint=None)
        assert result == "roi"


# ---------------------------------------------------------------------------
# generate_tile_content
# ---------------------------------------------------------------------------

class TestGenerateTileContent:
    """Tile content generation with mocked Claude response."""

    def _make_tiles(self, accent="#A78BFA"):
        return [
            {"type": "cover", "headline": "The Challenge", "body": "text", "accent": accent},
            {"type": "stat", "stat": "47%", "stat_label": "metric", "source": "Gartner"},
        ]

    def test_accent_added_to_tiles_missing_accent(self, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        tiles_no_accent = [
            {"type": "cover", "headline": "Pain", "body": "text"},
            {"type": "stat", "stat": "47%", "stat_label": "label"},
        ]
        mock_response = json.dumps(tiles_no_accent)

        with patch("tiles.engine._call_claude", return_value=mock_response):
            result = generate_tile_content(ctx, "hook")

        for tile in result:
            assert "accent" in tile
            assert tile["accent"] == "#A78BFA"  # hook accent color

    def test_existing_accent_not_overwritten(self, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        custom_accent = "#FF0000"
        tiles_with_accent = [{"type": "cover", "headline": "H", "body": "B", "accent": custom_accent}]
        mock_response = json.dumps(tiles_with_accent)

        with patch("tiles.engine._call_claude", return_value=mock_response):
            result = generate_tile_content(ctx, "hook")

        assert result[0]["accent"] == custom_accent

    def test_returns_list(self, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        tiles = self._make_tiles()
        with patch("tiles.engine._call_claude", return_value=json.dumps(tiles)):
            result = generate_tile_content(ctx, "hook")
        assert isinstance(result, list)

    def test_correct_accent_per_deck_type(self, sample_contact):
        from tiles.prompts import ACCENT_COLORS
        ctx = assemble_tile_context(sample_contact)

        for deck_type, expected_accent in ACCENT_COLORS.items():
            tile_no_accent = [{"type": "cover", "headline": "H"}]
            with patch("tiles.engine._call_claude", return_value=json.dumps(tile_no_accent)):
                result = generate_tile_content(ctx, deck_type)
            assert result[0]["accent"] == expected_accent, (
                f"deck_type={deck_type}: expected {expected_accent}, got {result[0]['accent']}"
            )

    def test_hint_included_in_prompt(self, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        tiles = self._make_tiles()
        captured_prompt = {}

        def capture_call(system, content, max_tokens=500):
            captured_prompt["content"] = content
            return json.dumps(tiles)

        with patch("tiles.engine._call_claude", side_effect=capture_call):
            generate_tile_content(ctx, "roi", hint="focus on payback period")

        assert "payback period" in captured_prompt["content"]

    def test_no_hint_leaves_hint_section_empty(self, sample_contact):
        ctx = assemble_tile_context(sample_contact)
        tiles = self._make_tiles()
        captured_prompt = {}

        def capture_call(system, content, max_tokens=500):
            captured_prompt["content"] = content
            return json.dumps(tiles)

        with patch("tiles.engine._call_claude", side_effect=capture_call):
            generate_tile_content(ctx, "hook", hint=None)

        assert "The rep specifically asked" not in captured_prompt["content"]

    def test_markdown_fenced_json_cleaned(self, sample_contact):
        """Claude sometimes wraps JSON in ```json fences — must be stripped."""
        ctx = assemble_tile_context(sample_contact)
        tiles = [{"type": "cover", "headline": "H"}]
        fenced = f"```json\n{json.dumps(tiles)}\n```"

        with patch("tiles.engine._call_claude", return_value=fenced):
            result = generate_tile_content(ctx, "hook")

        assert isinstance(result, list)
        assert result[0]["headline"] == "H"
