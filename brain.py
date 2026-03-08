import json
import logging
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client

PARSE_SYSTEM_PROMPT = """You are a contact parsing assistant. Users will send you raw,
unstructured text (or transcribed voice memos) about people they just met at a conference.

Extract and return ONLY valid JSON with these fields:
{
    "name": "Full Name",
    "company": "Company Name",
    "title": "Job Title (if mentioned)",
    "phone": "Phone number (if mentioned, any format)",
    "email": "Email (if mentioned)",
    "notes": "Key business context - what they care about, pain points, what was discussed",
    "follow_up_date": "When to follow up (if mentioned) - keep as natural language like 'Thursday' or 'next week'",
    "follow_up_action": "What to send or do - 'send case study', 'schedule demo', etc.",
    "temperature": "hot (clear buying intent or scheduled follow-up), warm (interested but no commitment), saved (casual contact, no action needed)",
    "personal_details": ["Array of personal facts - school connections, hobbies, family mentions, anything that makes follow-up feel human"]
}

Rules:
- If information isn't mentioned, use empty string or empty array
- Infer title/role from context clues if not explicitly stated
- "Follow up Thursday" means follow_up_date = "Thursday"
- Keep notes concise but preserve all business-relevant context
- Personal details are GOLD - these make follow-ups feel real
- Return ONLY the JSON object. No markdown. No explanation. No code fences."""


DRAFT_SYSTEM_PROMPT = """You are a follow-up message writer. You write short, casual,
human-sounding iMessages that a salesperson would send after meeting someone at a conference.

Rules:
- Sound like a REAL PERSON texting, not a corporation
- Keep it under 3-4 sentences max
- Reference something personal from the conversation (school connection, shared interest, joke you shared)
- Reference the specific business context or what you promised to send
- Include a clear but soft call to action
- No "I hope this message finds you well" - nobody texts like that
- No formal sign-offs - it's iMessage, not email
- Match the energy: if the meeting was casual, keep it casual. If it was business-focused, be direct.

You will receive the contact's structured data. Write ONLY the message text. Nothing else."""


SUMMARY_SYSTEM_PROMPT = """You are a conference day summarizer. Given a list of contacts
with their details, produce a clean, scannable summary organized by priority.

Format:
🔴 HOT - contacts with scheduled follow-ups or clear buying intent
🟡 WARM - interested contacts worth following up
🟢 SAVED - casual contacts, no immediate action

For each contact show: Name, Company - Title - key note - follow-up status
At the bottom: draft status and totals.

Keep it tight. This gets read on a phone screen."""

SUMMARY_FIELDS = ("name", "company", "title", "notes", "temperature",
                   "follow_up_date", "follow_up_action", "personal_details",
                   "draft", "sent")


def _clean_json_response(text: str) -> str:
    """Strip markdown code fences from Claude's response."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _call_claude(system: str, user_content: str, max_tokens: int = 500) -> str:
    """Make a Claude API call and return the text response."""
    response = _get_client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
        timeout=30.0,
    )
    return response.content[0].text.strip()


def parse_brain_dump(raw_text: str) -> dict:
    """Parse unstructured brain dump into structured contact."""
    text = _clean_json_response(_call_claude(PARSE_SYSTEM_PROMPT, raw_text))

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("First parse attempt failed, retrying")
        retry_text = _clean_json_response(
            _call_claude(
                PARSE_SYSTEM_PROMPT,
                f"Parse this into the JSON format. Return ONLY valid JSON, no backticks:\n\n{raw_text}"
            )
        )
        return json.loads(retry_text)


def draft_follow_up(contact: dict) -> str:
    """Generate a personalized follow-up message."""
    personal = ", ".join(contact.get("personal_details", [])) or "none captured"

    return _call_claude(
        DRAFT_SYSTEM_PROMPT,
        (
            f"Write a follow-up iMessage for this contact:\n\n"
            f"Name: {contact['name']}\n"
            f"Company: {contact['company']}\n"
            f"Title: {contact['title']}\n"
            f"What we discussed: {contact['notes']}\n"
            f"What I promised: {contact['follow_up_action']}\n"
            f"Personal details: {personal}\n"
            f"Temperature: {contact['temperature']}"
        ),
        max_tokens=300
    )


def generate_summary(contacts_list: list) -> str:
    """Generate end-of-day summary."""
    trimmed = [
        {k: c.get(k, "") for k in SUMMARY_FIELDS}
        for c in contacts_list
    ]
    return _call_claude(
        SUMMARY_SYSTEM_PROMPT,
        f"Here are today's contacts:\n\n{json.dumps(trimmed)}",
        max_tokens=800
    )
