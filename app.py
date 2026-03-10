import json
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from flask import Flask, request, jsonify, send_file

from config import LINQ_PHONE_NUMBER, PORT, TEMP_HOT, TEMP_WARM
import re
from datetime import date

from contacts import (
    clear_user_data,
    create_contact,
    find_and_merge_contact,
    get_contact_by_id,
    get_rep_profile,
    get_user_contacts,
    find_contact_by_name,
    set_rep_profile,
    update_contact,
    first_name,
)
from brain import (
    parse_brain_dump,
    draft_follow_up,
    generate_summary,
    classify_intent,
    parse_rep_profile,
    resolve_follow_up_date,
)
from linq_client import (
    send_reply,
    start_typing,
    stop_typing,
    mark_read,
    send_reaction,
)
from voice import transcribe_voice_memo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=10)

# Track which contact was last shown a draft for (simple state for "send" command)
_draft_lock = threading.Lock()
last_draft_shown = {}  # sender_phone -> contact_id


def _format_draft_preview(contact: dict, footer: str) -> str:
    """Build the draft preview message shown to the user."""
    msg = f"📝 Draft for {contact['name']} ({contact['company']}):\n\n"
    msg += f"\"{contact['draft']}\"\n\n"
    msg += footer
    return msg


def _fast_path_route(text_lower: str) -> str:
    """Try to match exact commands without a Claude call. Returns intent or empty string."""
    if text_lower in ("summary", "recap", "/summary"):
        return "summary"
    if text_lower in ("/update", "update", "morning"):
        return "update"
    if text_lower in ("help", "/help"):
        return "help"
    if text_lower in ("contacts", "list", "who"):
        return "contacts"
    if text_lower == "send" or text_lower.startswith("send to "):
        return "send"
    if text_lower.startswith("draft for ") or text_lower.startswith("draft "):
        return "draft_keyword"
    if text_lower.startswith("follow up with "):
        return "visual"
    if text_lower.startswith("edit "):
        return "edit"
    if text_lower.startswith("/setup"):
        return "setup"
    if text_lower in ("/restart", "restart", "/reset", "reset"):
        return "restart"
    if _is_visual_send(text_lower):
        return "visual_send"
    return ""


# Track which users are in onboarding flow
_onboarding_pending = set()  # sender phones awaiting profile response


def process_message(chat_id: str, sender: str, text: str, message_id: str, attachments: Optional[list[dict[str, str]]] = None):
    """Route incoming message to the right handler using intent classification."""
    print(f"[PROCESS] chat_id={chat_id} sender={sender} text={text!r} msg_id={message_id}", flush=True)
    start_typing(chat_id)
    mark_read(chat_id)

    text_lower = text.strip().lower() if text else ""

    try:
        # Check if user is in onboarding flow (awaiting profile response)
        if sender in _onboarding_pending and text and text.strip():
            _onboarding_pending.discard(sender)
            handle_setup(chat_id, sender, text)
            return

        # First-time user onboarding
        profile = get_rep_profile(sender)
        if not profile and text_lower not in ("help", "/help"):
            _onboarding_pending.add(sender)
            send_reply(
                chat_id,
                "Hey! I'm LinqUp — your follow-up sidekick. 👋\n\n"
                "Quick intro — what's your name, company, and what do you sell?\n\n"
                "Example: \"Chay Davuluri, LinqUp, sales API platform\""
            )
            return

        # Handle voice memos first (attachment-based, no intent needed)
        if attachments and any(a.get("type", "").startswith("audio") for a in attachments):
            audio_attachment = next(a for a in attachments if a.get("type", "").startswith("audio"))
            audio_url = audio_attachment.get("url")
            if audio_url:
                transcribed = transcribe_voice_memo(audio_url)
                preview = f"{transcribed[:100]}..." if len(transcribed) > 100 else transcribed
                send_reply(chat_id, f"🎤 Heard: \"{preview}\"")
                handle_brain_dump(chat_id, sender, transcribed, message_id)
            else:
                send_reply(chat_id, "Couldn't grab that voice memo — try again?")
            return

        # Handle bare phone numbers
        if _is_phone_number(text_lower):
            handle_phone_number(chat_id, sender, text.strip())
            return

        if not text or not text.strip():
            rep_name = profile.get("name", "").split()[0] if profile else ""
            greeting = f"Hey{' ' + rep_name if rep_name else ''}!"
            send_reply(chat_id, f"{greeting} Text me about someone you met, or say 'update' to check your pipeline.")
            return

        # Fast path: exact keyword matches (no Claude call needed)
        fast = _fast_path_route(text_lower)
        if fast == "summary":
            handle_summary(chat_id, sender)
            return
        if fast == "update":
            handle_update(chat_id, sender)
            return
        if fast == "help":
            handle_help(chat_id)
            return
        if fast == "contacts":
            handle_list(chat_id, sender)
            return
        if fast == "send":
            handle_send(chat_id, sender, text)
            return
        if fast == "draft_keyword":
            name = text.split("for ", 1)[-1] if "for " in text else text.split("draft ", 1)[-1]
            handle_draft_request(chat_id, sender, name.strip())
            return
        if fast == "visual":
            name, hint = _parse_follow_up_command(text)
            handle_visual_follow_up(chat_id, sender, name, hint)
            return
        if fast == "visual_send":
            name, hint = _parse_visual_command(text)
            handle_visual_follow_up(chat_id, sender, name, hint)
            return
        if fast == "edit":
            handle_edit(chat_id, sender, text)
            return
        if fast == "setup":
            setup_text = text[6:].strip() if len(text) > 6 else ""
            if setup_text:
                handle_setup(chat_id, sender, setup_text)
            else:
                send_reply(chat_id, "Tell me about yourself! Example: \"Chay Davuluri, LinqUp, sales API platform\"")
                _onboarding_pending.add(sender)
            return
        if fast == "restart":
            handle_restart(chat_id, sender)
            return

        # No fast match — use Claude to classify intent
        user_contacts = get_user_contacts(sender)
        contact_names = [c["name"] for c in user_contacts]
        intent_result = classify_intent(text, contact_names)
        intent = intent_result.get("intent") or "brain_dump"
        name = (intent_result.get("name") or "").strip()
        reply_text = intent_result.get("reply") or ""

        print(f"[INTENT] {intent} name={name!r} reply={reply_text!r}", flush=True)

        if intent == "greeting" or intent == "conversational":
            send_reply(chat_id, reply_text or "Hey! Text me about someone you met and I'll help you follow up. 👋")

        elif intent == "draft":
            if name:
                handle_draft_request(chat_id, sender, name)
            else:
                send_reply(chat_id, "Who do you want a draft for? Try 'draft for [name]'")

        elif intent == "send":
            handle_send(chat_id, sender, text)

        elif intent == "summary":
            handle_summary(chat_id, sender)

        elif intent == "update":
            handle_update(chat_id, sender)

        elif intent == "help":
            handle_help(chat_id)

        elif intent == "contacts":
            handle_list(chat_id, sender)

        elif intent == "visual" or intent == "follow_up":
            if name:
                hint = intent_result.get("hint", "")
                handle_visual_follow_up(chat_id, sender, name, hint)
            else:
                send_reply(chat_id, "Who should I follow up with? Try 'follow up with [name]'")

        elif intent == "edit":
            handle_edit(chat_id, sender, text)

        elif intent == "question":
            if reply_text:
                send_reply(chat_id, reply_text)
            else:
                send_reply(chat_id, "I'm not sure — try 'contacts' to see your list or 'help' for commands.")

        elif intent == "phone_number":
            handle_phone_number(chat_id, sender, text.strip())

        else:
            # Default: brain_dump — this message contains contact info
            handle_brain_dump(chat_id, sender, text, message_id)

    except Exception:
        logger.exception("Error processing message from %s", sender)
    finally:
        stop_typing(chat_id)


_PHONE_RE = re.compile(r"^\+?\d[\d\s\-().]{6,15}$")


def _is_phone_number(text: str) -> bool:
    """Check if the message is just a phone number."""
    return bool(_PHONE_RE.match(text.strip()))


def handle_phone_number(chat_id: str, sender: str, phone: str):
    """Attach a phone number to the last discussed contact."""
    # Normalize: strip spaces, dashes, parens
    clean_phone = re.sub(r"[\s\-().]+", "", phone)

    with _draft_lock:
        contact_id = last_draft_shown.get(sender)

    if contact_id:
        contact = get_contact_by_id(contact_id)
        if contact:
            updated = update_contact(contact_id, phone=clean_phone)
            if updated:
                send_reply(chat_id, f"📱 Got it — saved {clean_phone} for {updated['name']}")
                return

    # No recent draft context — check if any contact is missing a phone
    user_list = get_user_contacts(sender)
    no_phone = [c for c in reversed(user_list) if not c.get("phone")]
    if no_phone:
        contact = no_phone[0]
        updated = update_contact(contact["id"], phone=clean_phone)
        if updated:
            send_reply(chat_id, f"📱 Got it — saved {clean_phone} for {updated['name']}")
            return

    send_reply(chat_id, f"Got the number {clean_phone}, but I'm not sure who it's for. Try: 'Sarah Chen, phone {clean_phone}'")


def handle_setup(chat_id: str, sender: str, text: str):
    """Parse and store rep profile."""
    try:
        parsed = parse_rep_profile(text)
        profile = set_rep_profile(sender, parsed)
        rep_name = profile.get("name", "").split()[0] or "there"
        company = profile.get("company", "")
        product = profile.get("product", "")

        msg = f"Nice to meet you, {rep_name}!"
        if company:
            msg += f" {company}"
            if product:
                msg += f" — {product}"
            msg += " sounds great."
        msg += "\n\nI'm ready! Text me about anyone you meet and I'll handle the rest. 🚀"

        send_reply(chat_id, msg)
    except Exception:
        logger.exception("Profile setup failed")
        _onboarding_pending.add(sender)
        send_reply(chat_id, "Hmm, I couldn't catch that. Try: \"Your Name, Company, what you sell\"")


def handle_restart(chat_id: str, sender: str):
    """Clear all data for this user and restart from onboarding."""
    count = clear_user_data(sender)
    _onboarding_pending.discard(sender)
    with _draft_lock:
        last_draft_shown.pop(sender, None)

    _onboarding_pending.add(sender)
    send_reply(
        chat_id,
        f"🔄 Reset! Cleared {count} contact{'s' if count != 1 else ''} and your profile.\n\n"
        "Hey! I'm LinqUp — your follow-up sidekick. 👋\n\n"
        "Quick intro — what's your name, company, and what do you sell?\n\n"
        "Example: \"Chay Davuluri, LinqUp, sales API platform\""
    )


def handle_brain_dump(chat_id: str, sender: str, text: str, message_id: str):
    """Parse a brain dump and store/merge as contact."""
    try:
        parsed = parse_brain_dump(text)

        # Resolve follow-up date to actual ISO date
        raw_date = parsed.get("follow_up_date", "")
        if raw_date:
            actual_date = resolve_follow_up_date(raw_date)
            if actual_date:
                parsed["follow_up_date_actual"] = actual_date

        contact, is_new = find_and_merge_contact(sender, parsed)
        fname = first_name(contact)

        # Conversational confirmation
        if is_new:
            header = f"Got {contact['name']}!"
            if contact["company"]:
                header += f" {contact['company']}"
                if contact["title"]:
                    header += f", {contact['title']}"
                header += "."
        else:
            header = f"Updated {contact['name']} — added the new info."

        lines = [header]

        if contact["follow_up_date"] and contact["follow_up_action"]:
            date_display = contact["follow_up_date"]
            lines.append(f"📋 {contact['follow_up_action']} — {date_display}")

        if contact["personal_details"]:
            details = ", ".join(contact["personal_details"][:3])
            lines.append(f"💬 {details}")

        if contact["temperature"] in (TEMP_HOT, TEMP_WARM) and contact["follow_up_action"]:
            lines.append(f"\nSay 'draft for {fname}' when you're ready ✍️")

        send_reply(chat_id, "\n".join(lines))
        send_reaction(message_id, "like")

    except Exception as e:
        logger.exception("Brain dump parse failed")
        send_reply(
            chat_id,
            "Hmm, I couldn't quite get that. Try something like:\n"
            "\"Sarah Chen, Stripe, VP RevOps, wants case study, follow up Thursday\""
        )


def handle_summary(chat_id: str, sender: str):
    """Generate and send day summary."""
    user_list = get_user_contacts(sender)
    if not user_list:
        send_reply(chat_id, "No contacts logged yet. Text me about someone you met!")
        return

    summary = generate_summary(user_list)
    send_reply(chat_id, summary)


def _date_status(contact: dict) -> tuple[str, str]:
    """Return (group, display) for a contact's follow-up date.

    Groups: 'overdue', 'today', 'upcoming', 'none'.
    """
    actual = contact.get("follow_up_date_actual", "")
    if not actual:
        return "none", ""

    try:
        follow_date = date.fromisoformat(actual)
    except ValueError:
        return "none", contact.get("follow_up_date", "")

    today = date.today()
    delta = (follow_date - today).days

    if delta < 0:
        return "overdue", f"{abs(delta)} day{'s' if abs(delta) != 1 else ''} overdue"
    if delta == 0:
        return "today", "today"
    if delta == 1:
        return "upcoming", "tomorrow"
    return "upcoming", f"in {delta} days"


def handle_update(chat_id: str, sender: str):
    """Morning update — date-aware, grouped by urgency."""
    user_list = get_user_contacts(sender)
    if not user_list:
        send_reply(chat_id, "No contacts yet! Text me about someone you meet and I'll track everything. 🎯")
        return

    profile = get_rep_profile(sender)
    rep_name = profile.get("name", "").split()[0] if profile else ""

    overdue = []
    due_today = []
    upcoming = []
    sent_contacts = []
    other = []

    for c in user_list:
        if c["sent"]:
            sent_contacts.append(c)
            continue

        group, display = _date_status(c)
        if group == "overdue":
            overdue.append((c, display))
        elif group == "today":
            due_today.append((c, display))
        elif group == "upcoming":
            upcoming.append((c, display))
        else:
            other.append(c)

    greeting = f"Hey {rep_name}! " if rep_name else ""
    lines = [f"{greeting}Here's your pipeline:\n"]

    if overdue:
        lines.append("🔴 OVERDUE")
        for c, display in overdue:
            draft_tag = " ✓ draft ready" if c["draft"] else ""
            action = c["follow_up_action"] or "follow up"
            lines.append(f"  • {c['name']} ({c['company']}) — {action} — {display}{draft_tag}")
            lines.append(f"    → 'draft for {first_name(c)}'")

    if due_today:
        lines.append("\n🟡 DUE TODAY")
        for c, display in due_today:
            draft_tag = " ✓ draft ready" if c["draft"] else ""
            action = c["follow_up_action"] or "follow up"
            lines.append(f"  • {c['name']} ({c['company']}) — {action}{draft_tag}")
            lines.append(f"    → 'draft for {first_name(c)}'")

    if upcoming:
        lines.append("\n🟢 COMING UP")
        for c, display in upcoming:
            action = c["follow_up_action"] or "follow up"
            lines.append(f"  • {c['name']} ({c['company']}) — {action} ({display})")

    if sent_contacts:
        lines.append("\n📬 SENT")
        for c in sent_contacts:
            if c["reply_received"]:
                status = f"replied: \"{c['reply_received']}\""
            else:
                status = "delivered"
            lines.append(f"  • {c['name']} ({c['company']}) — {status}")

    if other:
        lines.append("\n📋 NO DATE SET")
        for c in other:
            draft_tag = " ✓ draft ready" if c["draft"] else ""
            lines.append(f"  • {c['name']} ({c['company']}){draft_tag}")

    # Summary line
    total = len(user_list)
    followed = len(sent_contacts)
    drafts = sum(1 for c in user_list if c["draft"] and not c["sent"])
    lines.append(f"\n━━━━━━━━━━━━━━━━━━\n{total} contacts | {followed} sent | {drafts} drafts ready")

    send_reply(chat_id, "\n".join(lines))


def handle_draft_request(chat_id: str, sender: str, name_query: str):
    """Show draft follow-up for a contact."""
    contact = find_contact_by_name(sender, name_query)

    if not contact:
        send_reply(chat_id, f"Can't find '{name_query}' — try 'contacts' to see who you've logged.")
        return

    if not contact["draft"]:
        profile = get_rep_profile(sender)
        draft = draft_follow_up(contact, rep_profile=profile)
        contact = update_contact(contact["id"], draft=draft) or contact

    with _draft_lock:
        last_draft_shown[sender] = contact["id"]

    if contact.get("phone"):
        footer = "Reply SEND to send now\nReply LATER to hold\nOr tell me what to change"
    else:
        footer = "⚠️ No phone number on file — tell me their number and I'll send it"

    send_reply(chat_id, _format_draft_preview(contact, footer))


def handle_send(chat_id: str, sender: str, text: str):
    """Finalize and present the draft — ready for the rep to copy and send."""
    contact = None

    if text.lower().startswith("send to "):
        name = text[8:].strip()
        contact = find_contact_by_name(sender, name)
    else:
        with _draft_lock:
            contact_id = last_draft_shown.get(sender)
        if contact_id:
            contact = get_contact_by_id(contact_id)

    if not contact:
        send_reply(chat_id, "Send what? Review a draft first — say 'draft for [name]'")
        return

    if not contact.get("draft"):
        send_reply(chat_id, f"No draft ready for {contact['name']}. Say 'draft for {first_name(contact)}' first.")
        return

    # Mark as finalized and present the ready-to-send message
    update_contact(contact["id"], sent=True, sent_at=datetime.now().isoformat())

    phone_line = f"\n📱 Send to: {contact['phone']}" if contact.get("phone") else ""

    send_reply(
        chat_id,
        f"✅ Finalized for {contact['name']} ({contact['company']}){phone_line}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{contact['draft']}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Copy and send when ready! Say 'draft for [name]' to regenerate."
    )


def handle_edit(chat_id: str, sender: str, text: str):
    """Handle edit requests for drafts."""
    with _draft_lock:
        contact_id = last_draft_shown.get(sender)
    if not contact_id:
        send_reply(chat_id, "Nothing to edit. Review a draft first — say 'draft for [name]'")
        return

    contact = get_contact_by_id(contact_id)
    if not contact:
        send_reply(chat_id, "Contact not found. Try 'draft for [name]' again.")
        return

    edit_instruction = text[5:].strip()
    profile = get_rep_profile(sender)
    draft = draft_follow_up({**contact, "notes": contact["notes"] + f" | Edit request: {edit_instruction}"}, rep_profile=profile)
    updated = update_contact(contact["id"], draft=draft)

    send_reply(chat_id, _format_draft_preview(updated or contact, "Reply SEND to send now, or edit again"))


def handle_help(chat_id: str):
    """Show available commands."""
    help_text = (
        "LinqUp — AI Follow-Up Agent\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Text me about anyone you meet — I'll parse, store, and draft follow-ups.\n\n"
        "CAPTURE\n"
        "  Just text naturally or send a voice memo\n"
        "  \"Sarah Chen, Stripe, VP RevOps, wants case study, follow up Thursday\"\n\n"
        "COMMANDS\n"
        "  update — your pipeline: overdue, today, upcoming\n"
        "  contacts — list all saved contacts\n"
        "  summary — AI-generated day recap\n"
        "  draft for [name] — generate follow-up message\n"
        "  send — finalize last draft (ready to copy & send)\n"
        "  send to [name] — finalize draft for specific contact\n"
        "  follow up with [name] — generate visual tile presentation\n"
        "  edit [changes] — revise last draft\n"
        "  /setup — update your profile\n"
        "  /restart — clear everything and start fresh\n"
        "  help — this reference"
    )
    send_reply(chat_id, help_text)


def handle_list(chat_id: str, sender: str):
    """List all contacts."""
    user_list = get_user_contacts(sender)
    if not user_list:
        send_reply(chat_id, "No contacts yet. Text me about someone you met!")
        return

    lines = [f"📇 Your contacts ({len(user_list)}):\n"]
    for c in user_list:
        if c["sent"]:
            status = "✅ sent"
        elif c["draft"]:
            status = "✍️ draft ready"
        else:
            status = "📋 logged"
        lines.append(f"• {c['name']} — {c['company']} [{status}]")

    send_reply(chat_id, "\n".join(lines))


def _is_visual_send(text_lower: str) -> bool:
    """Detect if the user wants visual tiles sent."""
    if not text_lower.startswith("send "):
        return False
    visual_words = ("something", "visual", "tiles", "deck", "slides")
    return any(w in text_lower for w in visual_words)


def _parse_visual_command(text: str) -> tuple[str, str]:
    """Parse 'send Sarah something about scaling' into (name, hint)."""
    # Remove "send " prefix
    rest = text[5:].strip()

    # Try to split on visual keywords to find where name ends
    for keyword in ("something", "visual", "tiles", "deck", "slides"):
        if keyword in rest.lower():
            idx = rest.lower().index(keyword)
            name = rest[:idx].strip().rstrip(",").strip()
            hint_raw = rest[idx + len(keyword):]
            hint = hint_raw.strip()
            for prefix in ("about ", "on "):
                if hint.lower().startswith(prefix):
                    hint = hint[len(prefix):]
                    break
            hint = hint.strip() if hint else ""
            return name, hint

    return rest, ""


def _parse_follow_up_command(text: str) -> tuple[str, str]:
    """Parse 'follow up with Sarah, include something about scaling'."""
    rest = text[len("follow up with "):].strip()

    for separator in (",", " include ", " with ", " about "):
        if separator in rest.lower():
            idx = rest.lower().index(separator)
            name = rest[:idx].strip()
            hint = rest[idx + len(separator):].strip()
            return name, hint

    return rest, ""


def handle_visual_follow_up(chat_id: str, sender: str, name_query: str, hint: Optional[str] = None):
    """Generate tile deck as PNG images and send them in-chat for the rep to preview."""
    from tiles.engine import generate_image_tile_preview
    from tiles.image_converter import cleanup_images
    import shutil

    contact = find_contact_by_name(sender, name_query)
    if not contact:
        send_reply(chat_id, f"Can't find '{name_query}' — try 'contacts' to see who you've logged.")
        return

    send_reply(chat_id, f"Building a deck for {first_name(contact)}... ✨")

    image_paths = []
    served_paths = []
    try:
        result = generate_image_tile_preview(contact, hint=hint)
        deck_type = result.get("deck_type", "")
        image_paths = result.get("image_paths", [])

        if not image_paths:
            send_reply(chat_id, "Couldn't generate tile images — try again?")
            return

        # Copy images to the serving directory and build public URLs
        public_urls = []
        for i, src_path in enumerate(image_paths):
            filename = f"{sender.replace('+', '')}_{contact['id']}_{i}.png"
            dest_path = _os.path.join(_TILE_IMAGE_DIR, filename)
            shutil.copy2(src_path, dest_path)
            served_paths.append(dest_path)

            # Build public URL — use request context if available, else localhost
            try:
                base = _get_public_base_url()
            except RuntimeError:
                base = f"http://localhost:{PORT}"
            public_urls.append(f"{base}/tile-images/{filename}")

        # Send each tile image via Linq as an attachment
        from linq_client import send_image_reply
        for url in public_urls:
            send_image_reply(chat_id, url)

        # Closing summary
        num = len(image_paths)
        phone_info = f" to {contact['phone']}" if contact.get("phone") else ""
        send_reply(
            chat_id,
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📋 {num} {deck_type} slides for {contact['name']}\n"
            f"Forward these{phone_info} when ready!"
        )
    except Exception:
        logger.exception("Tile image generation failed for %s", contact.get("name"))
        send_reply(chat_id, "Something went wrong generating tiles — try again?")
    finally:
        cleanup_images(image_paths)


# === TILE IMAGE SERVING ===

# Store generated tile images temporarily for serving via Flask
import os as _os

_TILE_IMAGE_DIR = _os.path.join(_os.path.dirname(__file__), "data", "tile_images")
_os.makedirs(_TILE_IMAGE_DIR, exist_ok=True)


@app.route("/tile-images/<filename>", methods=["GET"])
def serve_tile_image(filename: str):
    """Serve a generated tile image PNG."""
    filepath = _os.path.join(_TILE_IMAGE_DIR, filename)
    if not _os.path.isfile(filepath):
        return jsonify({"error": "not found"}), 404
    return send_file(filepath, mimetype="image/png")


def _get_public_base_url() -> str:
    """Get the public base URL (ngrok or localhost) for serving tile images."""
    # Check X-Forwarded-Host from ngrok, or fall back to request.host_url
    forwarded = request.headers.get("X-Forwarded-Host", "")
    if forwarded:
        proto = request.headers.get("X-Forwarded-Proto", "https")
        return f"{proto}://{forwarded}"
    return request.host_url.rstrip("/")


# === FLASK WEBHOOK ENDPOINT ===

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming Linq v3 webhook events."""
    payload = request.json
    print("=" * 60, file=sys.stderr)
    print("WEBHOOK HIT", file=sys.stderr)
    print(json.dumps(payload, indent=2) if payload else "NO PAYLOAD", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    sys.stderr.flush()

    if not payload or not isinstance(payload, dict):
        return jsonify({"status": "bad request"}), 400

    event_type = payload.get("event_type", "")

    # Only process inbound messages — ignore typing, sent, delivered, read events
    if event_type != "message.received":
        return jsonify({"status": "ignored", "event_type": event_type}), 200

    data = payload.get("data", {})

    # Skip non-inbound messages (outbound = messages we sent)
    if data.get("direction") != "inbound":
        return jsonify({"status": "ignored", "reason": "not inbound"}), 200

    # Extract fields from actual Linq v3 payload structure
    chat = data.get("chat", {})
    chat_id = chat.get("id", "")
    sender_handle = data.get("sender_handle", {})
    sender = sender_handle.get("handle", "")
    message_id = data.get("id", "")

    # Extract text from parts array
    parts = data.get("parts", [])
    text = ""
    attachments = []
    for part in parts:
        part_type = part.get("type", "")
        if part_type == "text":
            text = part.get("value", "")
        elif part_type.startswith("audio"):
            attachments.append({"type": part_type, "url": part.get("value", "")})

    if not chat_id or not sender:
        return jsonify({"status": "missing fields"}), 400

    # Ignore messages from our own bot number
    if sender == LINQ_PHONE_NUMBER:
        return jsonify({"status": "ignored"}), 200

    executor.submit(process_message, chat_id, sender, text, message_id, attachments)

    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
