"""Visual Tiles Engine — orchestrates context → deck → render → send."""

import json
import logging
from typing import Optional

from brain import _call_claude, _clean_json_response
from contacts import first_name as get_first_name
from tiles.prompts import (
    ACCENT_COLORS,
    DECK_GUIDELINES,
    DECK_SELECTOR_PROMPT,
    TILE_CONTENT_PROMPT,
)
from tiles.renderer import render_tile_html
from tiles.image_converter import render_deck_images, cleanup_images

logger = logging.getLogger(__name__)


def assemble_tile_context(contact: dict) -> dict:
    """Build the context object Claude needs to generate tile content."""
    return {
        "name": contact.get("name", ""),
        "company": contact.get("company", ""),
        "title": contact.get("title", ""),
        "pain_points": contact.get("notes", ""),
        "follow_up_action": contact.get("follow_up_action", ""),
        "personal_details": contact.get("personal_details", []),
        "temperature": contact.get("temperature", "warm"),
    }


def select_deck_type(context: dict, hint: Optional[str] = None) -> str:
    """Use Claude to pick the best deck type for this contact."""
    if hint:
        hint_lower = hint.lower()
        if any(w in hint_lower for w in ("price", "cost", "roi", "budget")):
            return "roi"
        if any(w in hint_lower for w in ("proof", "case study", "testimonial")):
            return "proof"
        if any(w in hint_lower for w in ("compare", "competitor", "versus", "vs")):
            return "competitive"

    prompt = DECK_SELECTOR_PROMPT.format(context=json.dumps(context))
    result = _call_claude("You are a sales strategist.", prompt, max_tokens=10).strip().lower()

    valid_types = ("hook", "roi", "proof", "personal", "competitive")
    if result in valid_types:
        return result

    logger.warning("Claude returned invalid deck type '%s', defaulting to hook", result)
    return "hook"


def generate_tile_content(context: dict, deck_type: str, hint: Optional[str] = None) -> list[dict]:
    """Use Claude to generate structured content for each tile."""
    accent = ACCENT_COLORS.get(deck_type, "#A78BFA")
    guidelines = DECK_GUIDELINES.get(deck_type, DECK_GUIDELINES["hook"])

    hint_section = f"The rep specifically asked to include: {hint}" if hint else ""

    prompt = TILE_CONTENT_PROMPT.format(
        deck_type=deck_type,
        context=json.dumps(context),
        hint_section=hint_section,
        deck_guidelines=guidelines,
        accent_hex=accent,
    )

    raw = _call_claude(
        "You are a sales deck content strategist. Return only valid JSON arrays.",
        prompt,
        max_tokens=1500,
    )

    cleaned = _clean_json_response(raw)
    try:
        tiles = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Tile JSON parse failed, retrying once")
        raw = _call_claude(
            "You are a sales deck content strategist. Return only valid JSON arrays.",
            prompt,
            max_tokens=1500,
        )
        tiles = json.loads(_clean_json_response(raw))

    # Ensure every tile has the accent color (immutable — new list of new dicts)
    return [
        {**tile, "accent": tile.get("accent", accent)} for tile in tiles
    ]


def generate_and_send_deck(contact: dict, hint: Optional[str] = None) -> dict:
    """Full pipeline: context → deck type → content → render → send.

    Returns dict with success status and metadata.
    """
    from linq_client import send_message_to_phone

    phone = contact.get("phone")
    if not phone:
        return {"success": False, "error": "No phone number for contact"}

    try:
        # Step 1: Assemble context
        context = assemble_tile_context(contact)
        logger.info("Tile context assembled for %s", contact.get("name"))

        # Step 2: Select deck type
        deck_type = select_deck_type(context, hint)
        logger.info("Selected deck type: %s for %s", deck_type, contact.get("name"))

        # Step 3: Generate tile content
        tiles = generate_tile_content(context, deck_type, hint)
        logger.info("Generated %d tiles for %s", len(tiles), contact.get("name"))

        # Step 4: Render HTML → images
        html_pages = [
            render_tile_html(tile, deck_type=deck_type, tile_index=i)
            for i, tile in enumerate(tiles)
        ]
        image_paths = render_deck_images(html_pages)
        logger.info("Rendered %d tile images", len(image_paths))

        # Step 5: Send via Linq
        intro = f"Hey {get_first_name(contact)} — thought you'd find this interesting 👇"
        send_message_to_phone(phone, intro)

        # Send each tile image
        for img_path in image_paths:
            _send_image_to_phone(phone, img_path)

        # Follow-up text
        outro = contact.get("draft") or "Let me know what you think!"
        send_message_to_phone(phone, outro)

        # Cleanup temp files
        cleanup_images(image_paths)

        return {
            "success": True,
            "deck_type": deck_type,
            "num_tiles": len(tiles),
        }

    except Exception as e:
        logger.exception("Tile deck generation failed for %s", contact.get("name"))
        return {"success": False, "error": str(e)[:200]}


def _send_image_to_phone(phone: str, image_path: str):
    """Send an image file to a phone number via Linq API.

    NOTE: The exact Linq API endpoint for image/media sending needs
    to be confirmed against their sandbox docs. This is a best-guess
    implementation that may need adjustment.
    """
    import base64
    from linq_client import _linq_request

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    _linq_request("POST", "/messages", {
        "to": phone,
        "attachments": [{
            "type": "image/png",
            "data": image_data,
        }],
    })


def generate_preview_deck(contact: dict, hint: Optional[str] = None) -> dict:
    """Generate tile content without rendering/sending — for preview."""
    context = assemble_tile_context(contact)
    deck_type = select_deck_type(context, hint)
    tiles = generate_tile_content(context, deck_type, hint)
    return {"deck_type": deck_type, "tiles": tiles}
