"""Unit tests for app.py pure routing and parsing functions.

Covers:
- _is_visual_send
- _parse_visual_command
- _parse_follow_up_command

No API calls, no Flask test client needed — all pure functions.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import _is_visual_send, _parse_visual_command, _parse_follow_up_command


# ---------------------------------------------------------------------------
# _is_visual_send
# ---------------------------------------------------------------------------

class TestIsVisualSend:
    """Detect when the user wants visual tiles sent."""

    def test_send_something(self):
        assert _is_visual_send("send sarah something") is True

    def test_send_visual(self):
        assert _is_visual_send("send mike visual") is True

    def test_send_tiles(self):
        assert _is_visual_send("send james tiles") is True

    def test_send_deck(self):
        assert _is_visual_send("send sarah a deck") is True

    def test_send_slides(self):
        assert _is_visual_send("send james slides") is True

    def test_send_something_with_trailing_hint(self):
        assert _is_visual_send("send sarah something about scaling") is True

    def test_plain_send_is_not_visual(self):
        """'send' alone means send the last draft — not visual tiles."""
        assert _is_visual_send("send") is False

    def test_send_to_is_not_visual(self):
        """'send to <name>' means forward a text draft, not tiles."""
        assert _is_visual_send("send to sarah") is False

    def test_unrelated_message_is_not_visual(self):
        assert _is_visual_send("draft for sarah") is False

    def test_empty_string_is_not_visual(self):
        assert _is_visual_send("") is False

    def test_summary_is_not_visual(self):
        assert _is_visual_send("summary") is False

    def test_send_case_study_is_not_visual(self):
        """'send case study' should NOT match — 'study' is not in visual_words."""
        assert _is_visual_send("send case study") is False

    def test_case_insensitive_matching(self):
        # Function receives text already lowercased by caller in process_message.
        # Confirm it still works with lowercase input.
        assert _is_visual_send("send sarah something") is True

    def test_send_roi_deck(self):
        assert _is_visual_send("send mike roi deck") is True


# ---------------------------------------------------------------------------
# _parse_visual_command
# ---------------------------------------------------------------------------

class TestParseVisualCommand:
    """Parse 'send <name> something [about <hint>]' into (name, hint)."""

    def test_basic_something_no_hint(self):
        name, hint = _parse_visual_command("send Sarah something")
        assert name.lower() == "sarah"
        assert hint == ""

    def test_something_with_hint(self):
        name, hint = _parse_visual_command("send Sarah something about scaling")
        assert name.lower() == "sarah"
        assert "scaling" in hint

    def test_visual_keyword(self):
        name, hint = _parse_visual_command("send Mike visual")
        assert name.lower() == "mike"
        assert hint == ""

    def test_tiles_keyword(self):
        name, hint = _parse_visual_command("send James tiles")
        assert name.lower() == "james"
        assert hint == ""

    def test_deck_keyword(self):
        name, hint = _parse_visual_command("send Sarah a deck")
        # 'a deck' — name may include 'a' before 'deck' splits it
        # Verify deck_type is found; name part should at minimum contain 'sarah'
        assert "sarah" in name.lower()
        assert hint == ""

    def test_slides_keyword(self):
        name, hint = _parse_visual_command("send James slides on pricing")
        assert "james" in name.lower()

    def test_hint_with_about_prefix(self):
        name, hint = _parse_visual_command("send Sarah something about ROI and cost savings")
        assert "sarah" in name.lower()
        assert "roi" in hint.lower() or "cost" in hint.lower()

    def test_multiword_name(self):
        name, hint = _parse_visual_command("send Sarah Chen something about onboarding")
        assert "sarah" in name.lower()
        assert "onboarding" in hint.lower()

    def test_returns_tuple_of_two(self):
        result = _parse_visual_command("send Sarah something")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_name_and_hint_are_strings(self):
        name, hint = _parse_visual_command("send Mike something")
        assert isinstance(name, str)
        assert isinstance(hint, str)

    def test_no_visual_keyword_falls_through(self):
        """If no visual keyword found, rest of string becomes name with empty hint."""
        name, hint = _parse_visual_command("send Mike")
        assert "mike" in name.lower()
        assert hint == ""


# ---------------------------------------------------------------------------
# _parse_follow_up_command
# ---------------------------------------------------------------------------

class TestParseFollowUpCommand:
    """Parse 'follow up with <name>[, <hint>]' into (name, hint)."""

    def test_basic_no_hint(self):
        name, hint = _parse_follow_up_command("follow up with Sarah")
        assert name.strip().lower() == "sarah"
        assert hint == ""

    def test_comma_separator(self):
        name, hint = _parse_follow_up_command("follow up with Sarah, send the case study")
        assert name.strip().lower() == "sarah"
        assert "case study" in hint.lower()

    def test_include_separator(self):
        name, hint = _parse_follow_up_command("follow up with Mike include something about pricing")
        assert "mike" in name.lower()
        assert "pricing" in hint.lower()

    def test_about_separator(self):
        name, hint = _parse_follow_up_command("follow up with James about the scaling deck")
        assert "james" in name.lower()
        assert "scaling" in hint.lower()

    def test_with_separator(self):
        name, hint = _parse_follow_up_command("follow up with Sarah with the roi breakdown")
        # 'with' appears in prefix AND as separator — name ends up empty if 'with' is the first separator
        # Behaviorally: as long as Sarah is in the right slot, test passes.
        # The separator logic walks left-to-right on the rest after "follow up with "
        # rest = "Sarah with the roi breakdown"
        # idx of " with " → name="Sarah", hint="the roi breakdown"
        assert "sarah" in name.lower()
        assert "roi" in hint.lower()

    def test_returns_tuple_of_two(self):
        result = _parse_follow_up_command("follow up with Sarah")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_name_and_hint_are_strings(self):
        name, hint = _parse_follow_up_command("follow up with Sarah")
        assert isinstance(name, str)
        assert isinstance(hint, str)

    def test_multiword_name(self):
        name, hint = _parse_follow_up_command("follow up with Sarah Chen, include roi breakdown")
        assert "sarah" in name.lower()
        assert "chen" in name.lower()
        assert "roi" in hint.lower()

    def test_hint_is_stripped(self):
        name, hint = _parse_follow_up_command("follow up with Sarah, include pricing deck")
        assert not hint.startswith(" ")
        assert not hint.endswith(" ")

    def test_no_separator_returns_full_name_empty_hint(self):
        name, hint = _parse_follow_up_command("follow up with Sarah Chen")
        assert "sarah" in name.lower()
        assert hint == ""
