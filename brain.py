import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

_client: Optional[anthropic.Anthropic] = None


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
- If you know the sender's name, sign naturally (e.g. "- Chay" or just use first person)
- If you know the sender's company/product, reference it naturally where relevant

You will receive the contact's structured data and the sender's profile. Write ONLY the message text. Nothing else."""


PROFILE_PARSE_PROMPT = """Parse this person's self-introduction into a profile. Return ONLY valid JSON:
{
    "name": "Full Name",
    "company": "Company or organization",
    "role": "Job title or role",
    "product": "What they sell or work on"
}

Rules:
- If info isn't mentioned, use empty string
- Be generous with inference: "I'm Chay from LinqUp, we do sales APIs" → product = "sales APIs"
- Return ONLY the JSON. No explanation."""


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
    block = response.content[0]
    text = block.text if hasattr(block, "text") else str(block)
    return text.strip()


INTENT_SYSTEM_PROMPT = """You are a message intent classifier for a conference sales assistant bot.
A sales rep texts this bot to log contacts, get drafts, manage follow-ups, AND get sales advice.

You are a FULL sales sidekick — you help with everything a rep needs at a conference:
dinner spots to impress leads, talking points for meetings, industry insights, travel tips, conversation starters, meeting prep, etc.

Classify the user's message into ONE intent. Return ONLY valid JSON:
{
    "intent": "one of the intents below",
    "name": "person name if referenced (e.g. 'give me adaarsh' → 'adaarsh', 'draft for Sarah' → 'Sarah')",
    "hint": "any additional context or instruction from the user",
    "reply": "ONLY for greeting/conversational/question — a helpful, friendly response"
}

Intents:
- greeting: "hi", "hey", "what's up", "good morning". Reply warmly, mention they can text about people they meet.
- brain_dump: Contains info about a PERSON — name + details (company, role, notes, what was discussed). This is the CORE use case.
- draft: Wants to see/review a follow-up draft. "draft for X", "show me X", "yeah give me X", "what about X", just a person's name.
- send: Wants to send a message. "send", "send it", "send to X", "yeah send it"
- summary: "summary", "recap"
- update: "update", "morning", "/update"
- help: "help", "commands", "what can you do"
- contacts: "contacts", "list", "who do I have"
- visual: Wants visual tiles. "send X something", "follow up with X"
- edit: Modify a draft. "edit: make it shorter", "change the tone", "make it more casual"
- question: Asking ANYTHING — about a contact, about sales strategy, dinner spots, meeting prep, industry questions, travel, conversation tips. BE GENUINELY HELPFUL. Answer the actual question with useful, specific info. You are a knowledgeable sales advisor.
- phone_number: Message is just a phone number.
- conversational: Casual chat, thanks. "cool", "thanks", "ok nice", "got it", "awesome"

CRITICAL rules:
- If someone mentions a person's name WITH details about them (company, role, what they discussed, interests), it's brain_dump
- If someone just says a name or asks for something about a name, it's draft (they want to see that contact)
- "Yeah give me X" / "show me X" / "what about X" → draft, with name = X
- Short casual messages (hi, thanks, cool, ok) are NEVER brain_dump
- A message needs SUBSTANTIAL contact info to be a brain_dump — just a name alone is NOT enough
- For QUESTION intent: actually answer the question! Suggest specific restaurants, give real meeting prep advice, share industry talking points. Be the rep's smartest friend. Keep it concise (2-4 sentences) since it's iMessage.
- Return ONLY the JSON object. No markdown. No explanation."""


def classify_intent(text: str, contact_names: Optional[list[str]] = None) -> dict[str, str]:
    """Classify user message intent using Claude."""
    _fallback: dict[str, str] = {"intent": "brain_dump", "name": "", "hint": "", "reply": ""}
    try:
        context = ""
        if contact_names:
            context = f"\n\nExisting contacts the user has logged: {', '.join(contact_names)}"

        raw = _call_claude(
            INTENT_SYSTEM_PROMPT,
            f"Classify this message:{context}\n\n\"{text}\"",
            max_tokens=400,
        )
        cleaned = _clean_json_response(raw)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Intent classification JSON parse failed, defaulting to brain_dump")
        return _fallback
    except Exception:
        logger.exception("Intent classification failed (API error), defaulting to brain_dump")
        return _fallback


def parse_brain_dump(raw_text: str) -> dict[str, Any]:
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
        try:
            return json.loads(retry_text)
        except json.JSONDecodeError:
            logger.error("Brain dump parse failed twice: %s", retry_text[:200])
            raise ValueError("Could not parse contact info — please try rephrasing")


def draft_follow_up(contact: dict[str, Any], rep_profile: Optional[dict[str, str]] = None) -> str:
    """Generate a personalized follow-up message."""
    personal = ", ".join(contact.get("personal_details", [])) or "none captured"

    rep_section = ""
    if rep_profile and rep_profile.get("name"):
        rep_section = (
            f"\n\nSender (the salesperson writing this message):\n"
            f"Name: {rep_profile['name']}\n"
            f"Company: {rep_profile.get('company', '')}\n"
            f"Role: {rep_profile.get('role', '')}\n"
            f"Product/Service: {rep_profile.get('product', '')}"
        )

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
            f"{rep_section}"
        ),
        max_tokens=300
    )


def parse_rep_profile(text: str) -> dict[str, str]:
    """Parse a rep's self-introduction into a profile."""
    raw = _call_claude(PROFILE_PARSE_PROMPT, text, max_tokens=150)
    cleaned = _clean_json_response(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Profile parse failed")
        return {"name": text.strip(), "company": "", "role": "", "product": ""}


def resolve_follow_up_date(raw_date: str) -> str:
    """Convert natural language date to ISO format.

    'Thursday' → '2026-03-12', 'next week' → next Monday, 'tomorrow' → tomorrow.
    Returns empty string if can't parse.
    """
    if not raw_date:
        return ""

    raw = raw_date.strip().lower()
    today = datetime.now().date()

    # Already ISO format
    try:
        datetime.strptime(raw, "%Y-%m-%d")
        return raw
    except ValueError:
        pass

    # Day names
    day_names = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
        "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
    }
    for name, day_num in day_names.items():
        if raw.startswith(name):
            days_ahead = day_num - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).isoformat()

    if raw == "tomorrow":
        return (today + timedelta(days=1)).isoformat()

    if raw == "today":
        return today.isoformat()

    if "next week" in raw:
        days_to_monday = 7 - today.weekday()
        return (today + timedelta(days=days_to_monday)).isoformat()

    # "in X days"
    if raw.startswith("in ") and "day" in raw:
        try:
            num = int("".join(c for c in raw if c.isdigit()))
            return (today + timedelta(days=num)).isoformat()
        except ValueError:
            pass

    logger.info("Could not resolve date: '%s', keeping raw", raw_date)
    return ""


def generate_summary(contacts_list: list[dict[str, Any]]) -> str:
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
