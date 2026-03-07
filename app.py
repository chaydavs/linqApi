import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from flask import Flask, request, jsonify

from config import LINQ_PHONE_NUMBER, PORT, TEMP_HOT, TEMP_WARM
from contacts import (
    create_contact,
    get_contact_by_id,
    get_user_contacts,
    find_contact_by_name,
    update_contact,
    first_name,
)
from brain import parse_brain_dump, draft_follow_up, generate_summary
from linq_client import (
    send_message,
    send_message_to_phone,
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
last_draft_shown = {}  # sender_phone -> contact_id


def _format_draft_preview(contact: dict, footer: str) -> str:
    """Build the draft preview message shown to the user."""
    msg = f"📝 Draft for {contact['name']} ({contact['company']}):\n\n"
    msg += f"\"{contact['draft']}\"\n\n"
    msg += footer
    return msg


def process_message(chat_id: str, sender: str, text: str, message_id: str, attachments: list = None):
    """Route incoming message to the right handler."""
    start_typing(chat_id)
    mark_read(chat_id)

    text_lower = text.strip().lower() if text else ""

    try:
        if text_lower in ("summary", "recap", "/summary"):
            handle_summary(chat_id, sender)

        elif text_lower in ("/update", "update", "morning"):
            handle_update(chat_id, sender)

        elif text_lower.startswith("draft for ") or text_lower.startswith("draft "):
            name = text.split("for ", 1)[-1] if "for " in text else text.split("draft ", 1)[-1]
            handle_draft_request(chat_id, sender, name.strip())

        elif text_lower == "send" or text_lower.startswith("send to "):
            handle_send(chat_id, sender, text)

        elif text_lower.startswith("edit "):
            handle_edit(chat_id, sender, text)

        elif text_lower in ("help", "/help"):
            handle_help(chat_id)

        elif text_lower in ("contacts", "list", "who"):
            handle_list(chat_id, sender)

        elif attachments and any(a.get("type", "").startswith("audio") for a in attachments):
            audio_attachment = next(a for a in attachments if a.get("type", "").startswith("audio"))
            audio_url = audio_attachment.get("url")
            if audio_url:
                transcribed = transcribe_voice_memo(audio_url)
                preview = f"{transcribed[:100]}..." if len(transcribed) > 100 else transcribed
                send_message(chat_id, f"🎤 Heard: \"{preview}\"")
                handle_brain_dump(chat_id, sender, transcribed, message_id)
            else:
                send_message(chat_id, "Couldn't process that voice memo - no audio URL found.")

        elif text and text.strip():
            handle_brain_dump(chat_id, sender, text, message_id)

        else:
            send_message(chat_id, "Send me a brain dump about someone you met, or say 'help' for commands.")

    except Exception:
        logger.exception("Error processing message from %s", sender)
    finally:
        stop_typing(chat_id)


def handle_brain_dump(chat_id: str, sender: str, text: str, message_id: str):
    """Parse a brain dump and store as contact."""
    try:
        parsed = parse_brain_dump(text)
        contact = create_contact(sender, parsed)

        lines = [f"✅ Logged: {contact['name']}"]
        if contact["company"]:
            lines[0] += f" — {contact['company']}"
        if contact["title"]:
            lines[0] += f", {contact['title']}"
        if contact["follow_up_date"] and contact["follow_up_action"]:
            lines.append(f"📋 Follow-up: {contact['follow_up_date']} — {contact['follow_up_action']}")
        if contact["personal_details"]:
            lines.append(f"💬 Noted: {', '.join(contact['personal_details'])}")
        if contact["temperature"] in (TEMP_HOT, TEMP_WARM) and contact["follow_up_action"]:
            lines.append(f"✍️ Say 'draft for {first_name(contact)}' when you're ready to review")

        send_message(chat_id, "\n".join(lines))
        send_reaction(message_id, "like")

    except Exception as e:
        logger.exception("Brain dump parse failed")
        send_message(chat_id, f"Couldn't parse that — try again? Error: {str(e)[:100]}")


def handle_summary(chat_id: str, sender: str):
    """Generate and send day summary."""
    user_list = get_user_contacts(sender)
    if not user_list:
        send_message(chat_id, "No contacts logged yet. Text me about someone you met!")
        return

    summary = generate_summary(user_list)
    send_message(chat_id, summary)


def handle_update(chat_id: str, sender: str):
    """Morning update — replies, pending follow-ups, today's actions."""
    user_list = get_user_contacts(sender)
    if not user_list:
        send_message(chat_id, "No contacts yet. Get out there today! 💪")
        return

    sent_contacts = []
    unsent_hot = []
    draft_ready = []
    for c in user_list:
        if c["sent"]:
            sent_contacts.append(c)
        elif c["temperature"] == TEMP_HOT:
            unsent_hot.append(c)
        if c["draft"] and not c["sent"]:
            draft_ready.append(c)

    lines = ["☀️ Here's your update:\n"]

    if sent_contacts:
        lines.append("📬 SENT:")
        for c in sent_contacts:
            if c["reply_received"]:
                status = f"replied: \"{c['reply_received']}\""
            else:
                status = "delivered"
            lines.append(f"  • {c['name']} ({c['company']}) — {status}")

    if unsent_hot:
        lines.append("\n🔴 NEEDS FOLLOW-UP TODAY:")
        for c in unsent_hot:
            draft_status = "draft ready ✓" if c["draft"] else "no draft yet"
            lines.append(f"  • {c['name']} ({c['company']}) — {c['follow_up_action']} [{draft_status}]")

    if draft_ready:
        lines.append(f"\n✍️ {len(draft_ready)} draft(s) ready to review and send")

    lines.append(f"\n🔢 Totals: {len(user_list)} contacts, {len(sent_contacts)} followed up")

    send_message(chat_id, "\n".join(lines))


def handle_draft_request(chat_id: str, sender: str, name_query: str):
    """Show draft follow-up for a contact."""
    contact = find_contact_by_name(sender, name_query)

    if not contact:
        send_message(chat_id, f"Couldn't find anyone named '{name_query}'. Try 'contacts' to see your list.")
        return

    if not contact["draft"]:
        draft = draft_follow_up(contact)
        update_contact(contact["id"], draft=draft)

    last_draft_shown[sender] = contact["id"]

    if contact.get("phone"):
        footer = "Reply SEND to send now\nReply LATER to hold\nOr tell me what to change"
    else:
        footer = "⚠️ No phone number on file — tell me their number and I'll send it"

    send_message(chat_id, _format_draft_preview(contact, footer))


def handle_send(chat_id: str, sender: str, text: str):
    """Send the last shown draft to the contact."""
    contact = None

    if text.lower().startswith("send to "):
        name = text[8:].strip()
        contact = find_contact_by_name(sender, name)
    elif sender in last_draft_shown:
        contact = get_contact_by_id(last_draft_shown[sender])

    if not contact:
        send_message(chat_id, "Send what? Review a draft first — say 'draft for [name]'")
        return

    if not contact.get("draft"):
        send_message(chat_id, f"No draft ready for {contact['name']}. Say 'draft for {first_name(contact)}' first.")
        return

    if not contact.get("phone"):
        send_message(chat_id, f"I don't have a phone number for {contact['name']}. Text me their number.")
        return

    result = send_message_to_phone(contact["phone"], contact["draft"])

    if "error" not in result:
        update_contact(contact["id"], sent=True, sent_at=datetime.now().isoformat())
        send_message(chat_id, f"✅ Sent to {contact['name']} ({contact['phone']})\n📱 Delivered via iMessage")
    else:
        send_message(chat_id, f"❌ Couldn't send: {result['error']}\nCheck the phone number and try again.")


def handle_edit(chat_id: str, sender: str, text: str):
    """Handle edit requests for drafts."""
    if sender not in last_draft_shown:
        send_message(chat_id, "Nothing to edit. Review a draft first — say 'draft for [name]'")
        return

    contact = get_contact_by_id(last_draft_shown[sender])
    if not contact:
        send_message(chat_id, "Contact not found. Try 'draft for [name]' again.")
        return

    edit_instruction = text[5:].strip()
    draft = draft_follow_up({**contact, "notes": contact["notes"] + f" | Edit request: {edit_instruction}"})
    updated = update_contact(contact["id"], draft=draft)

    send_message(chat_id, _format_draft_preview(updated or contact, "Reply SEND to send now, or edit again"))


def handle_help(chat_id: str):
    """Show available commands."""
    help_text = (
        "🤖 LinqUp — Conference Contact Agent\n\n"
        "Just text me about anyone you meet:\n"
        "\"Sarah Chen, Stripe, VP RevOps, wants case study, follow up Thursday\"\n\n"
        "Commands:\n"
        "• summary — see everyone you've met today\n"
        "• /update — morning briefing with replies and pending follow-ups\n"
        "• draft for [name] — review AI-generated follow-up\n"
        "• send — send the last draft\n"
        "• send to [name] — send draft to specific person\n"
        "• edit [changes] — modify the last shown draft\n"
        "• contacts — list all contacts\n"
        "• help — this message\n\n"
        "💡 Pro tip: Send voice memos for faster logging"
    )
    send_message(chat_id, help_text)


def handle_list(chat_id: str, sender: str):
    """List all contacts."""
    user_list = get_user_contacts(sender)
    if not user_list:
        send_message(chat_id, "No contacts yet. Text me about someone you met!")
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

    send_message(chat_id, "\n".join(lines))


# === FLASK WEBHOOK ENDPOINT ===

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming Linq webhook events."""
    event = request.json
    if not event or not isinstance(event, dict):
        return jsonify({"status": "bad request"}), 400

    event_type = event.get("type", "")

    if event_type == "message.received":
        data = event.get("data", {})
        chat_id = data.get("chatId", "")
        sender = data.get("sender", "")
        text = data.get("text", "")
        message_id = data.get("messageId", "")
        attachments = data.get("attachments", [])

        if not chat_id or not sender:
            return jsonify({"status": "missing fields"}), 400

        if sender == LINQ_PHONE_NUMBER:
            return jsonify({"status": "ignored"}), 200

        executor.submit(process_message, chat_id, sender, text, message_id, attachments)

    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
