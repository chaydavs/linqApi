"""Unit tests for tiles/prompts.py constants and structure.

These tests verify the shape and completeness of the constant data that
drives the tile engine — no API calls required.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tiles.prompts import (
    DECK_SELECTOR_PROMPT,
    TILE_CONTENT_PROMPT,
    DECK_GUIDELINES,
    ACCENT_COLORS,
    DECK_GRADIENTS,
)

VALID_DECK_TYPES = ("hook", "roi", "proof", "personal", "competitive")


# ---------------------------------------------------------------------------
# Completeness checks — all 5 deck types must be represented
# ---------------------------------------------------------------------------

class TestDeckTypeCoverage:
    def test_deck_guidelines_has_all_types(self):
        for dt in VALID_DECK_TYPES:
            assert dt in DECK_GUIDELINES, f"DECK_GUIDELINES missing: {dt}"

    def test_accent_colors_has_all_types(self):
        for dt in VALID_DECK_TYPES:
            assert dt in ACCENT_COLORS, f"ACCENT_COLORS missing: {dt}"

    def test_deck_gradients_has_all_types(self):
        for dt in VALID_DECK_TYPES:
            assert dt in DECK_GRADIENTS, f"DECK_GRADIENTS missing: {dt}"

    def test_no_extra_types_in_accent_colors(self):
        for key in ACCENT_COLORS:
            assert key in VALID_DECK_TYPES, f"Unexpected key in ACCENT_COLORS: {key}"

    def test_no_extra_types_in_deck_guidelines(self):
        for key in DECK_GUIDELINES:
            assert key in VALID_DECK_TYPES, f"Unexpected key in DECK_GUIDELINES: {key}"


# ---------------------------------------------------------------------------
# Accent color format
# ---------------------------------------------------------------------------

class TestAccentColorFormat:
    @pytest.mark.parametrize("deck_type", VALID_DECK_TYPES)
    def test_accent_is_hex_string(self, deck_type):
        color = ACCENT_COLORS[deck_type]
        assert isinstance(color, str)
        assert color.startswith("#"), f"Accent for {deck_type} is not a hex color: {color}"

    @pytest.mark.parametrize("deck_type", VALID_DECK_TYPES)
    def test_accent_has_correct_length(self, deck_type):
        color = ACCENT_COLORS[deck_type]
        # Must be #RRGGBB (7 chars) or #RGB (4 chars)
        assert len(color) in (4, 7), f"Unexpected hex length for {deck_type}: {color}"

    def test_all_accent_colors_are_unique(self):
        colors = list(ACCENT_COLORS.values())
        assert len(colors) == len(set(colors)), "Duplicate accent colors found"


# ---------------------------------------------------------------------------
# Gradient lists
# ---------------------------------------------------------------------------

class TestDeckGradients:
    @pytest.mark.parametrize("deck_type", VALID_DECK_TYPES)
    def test_gradients_is_list(self, deck_type):
        assert isinstance(DECK_GRADIENTS[deck_type], list)

    @pytest.mark.parametrize("deck_type", VALID_DECK_TYPES)
    def test_gradients_not_empty(self, deck_type):
        assert len(DECK_GRADIENTS[deck_type]) > 0

    @pytest.mark.parametrize("deck_type", VALID_DECK_TYPES)
    def test_gradients_are_strings(self, deck_type):
        for g in DECK_GRADIENTS[deck_type]:
            assert isinstance(g, str)

    @pytest.mark.parametrize("deck_type", VALID_DECK_TYPES)
    def test_gradients_contain_linear_gradient(self, deck_type):
        for g in DECK_GRADIENTS[deck_type]:
            assert "linear-gradient" in g, f"Bad gradient in {deck_type}: {g}"

    def test_personal_deck_has_3_gradients(self):
        """Personal deck has 3 tiles, so 3 gradients."""
        assert len(DECK_GRADIENTS["personal"]) == 3

    def test_proof_deck_has_4_gradients(self):
        """Proof deck has 4 tiles, so 4 gradients."""
        assert len(DECK_GRADIENTS["proof"]) == 4

    def test_hook_deck_has_5_gradients(self):
        """Hook deck has 5 tiles, so 5 gradients."""
        assert len(DECK_GRADIENTS["hook"]) == 5

    def test_roi_deck_has_5_gradients(self):
        assert len(DECK_GRADIENTS["roi"]) == 5

    def test_competitive_deck_has_4_gradients(self):
        assert len(DECK_GRADIENTS["competitive"]) == 4


# ---------------------------------------------------------------------------
# Prompt template placeholders
# ---------------------------------------------------------------------------

class TestPromptTemplates:
    def test_deck_selector_prompt_has_context_placeholder(self):
        assert "{context}" in DECK_SELECTOR_PROMPT

    def test_deck_selector_prompt_lists_all_types(self):
        for dt in VALID_DECK_TYPES:
            assert dt in DECK_SELECTOR_PROMPT

    def test_deck_selector_prompt_instructs_single_word_response(self):
        assert "ONLY" in DECK_SELECTOR_PROMPT

    def test_tile_content_prompt_has_required_placeholders(self):
        required = ["{deck_type}", "{context}", "{hint_section}", "{deck_guidelines}", "{accent_hex}"]
        for placeholder in required:
            assert placeholder in TILE_CONTENT_PROMPT, f"Missing placeholder: {placeholder}"

    def test_tile_content_prompt_lists_tile_types(self):
        expected_types = ["cover", "stat", "list", "cta"]
        for t in expected_types:
            assert t in TILE_CONTENT_PROMPT

    def test_tile_content_prompt_instructs_json_only(self):
        assert "JSON" in TILE_CONTENT_PROMPT

    def test_deck_selector_prompt_can_be_formatted(self):
        """Verify no KeyError when formatting with all required keys."""
        formatted = DECK_SELECTOR_PROMPT.format(context='{"name": "Test"}')
        assert "Test" in formatted

    def test_tile_content_prompt_can_be_formatted(self):
        formatted = TILE_CONTENT_PROMPT.format(
            deck_type="hook",
            context='{"name": "Test"}',
            hint_section="",
            deck_guidelines=DECK_GUIDELINES["hook"],
            accent_hex="#A78BFA",
        )
        assert "hook" in formatted

    def test_deck_guidelines_are_non_empty_strings(self):
        for dt, guideline in DECK_GUIDELINES.items():
            assert isinstance(guideline, str)
            assert len(guideline) > 20, f"Guideline too short for {dt}"
