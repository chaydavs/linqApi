import threading
from datetime import datetime
from typing import Optional
import uuid

_lock = threading.Lock()

# Main contact store - keyed by unique ID
contacts = {}

# Map user phone numbers to their contact lists
user_contacts = {}  # phone -> [contact_id, ...]


def create_contact(user_phone: str, parsed_data: dict) -> dict:
    """Create a new contact from parsed output."""
    contact_id = str(uuid.uuid4())[:8]

    contact = {
        "id": contact_id,
        "owner": user_phone,
        "name": parsed_data.get("name", "Unknown"),
        "company": parsed_data.get("company", ""),
        "title": parsed_data.get("title", ""),
        "phone": parsed_data.get("phone", ""),
        "email": parsed_data.get("email", ""),
        "notes": parsed_data.get("notes", ""),
        "follow_up_date": parsed_data.get("follow_up_date", ""),
        "follow_up_action": parsed_data.get("follow_up_action", ""),
        "temperature": parsed_data.get("temperature", "warm"),
        "personal_details": parsed_data.get("personal_details", []),
        "created_at": datetime.now().isoformat(),
        "draft": None,
        "sent": False,
        "sent_at": None,
        "reply_received": None,
    }

    with _lock:
        contacts[contact_id] = contact
        if user_phone not in user_contacts:
            user_contacts[user_phone] = []
        user_contacts[user_phone].append(contact_id)

    return contact


def get_user_contacts(user_phone: str) -> list:
    """Get all contacts for a user."""
    with _lock:
        ids = user_contacts.get(user_phone, [])
        return [c for cid in ids if (c := contacts.get(cid)) is not None]


def get_contact_by_id(contact_id: str) -> Optional[dict]:
    """Get a contact by its ID."""
    with _lock:
        return contacts.get(contact_id)


def update_contact(contact_id: str, **updates) -> Optional[dict]:
    """Update fields on a contact. Returns updated contact or None."""
    with _lock:
        contact = contacts.get(contact_id)
        if not contact:
            return None
        contact.update(updates)
        return contact


def find_contact_by_name(user_phone: str, name_query: str) -> Optional[dict]:
    """Fuzzy find a contact by name."""
    user_list = get_user_contacts(user_phone)
    name_lower = name_query.lower()
    for c in user_list:
        if name_lower in c["name"].lower():
            return c
    return None


def first_name(contact: dict) -> str:
    """Extract first name from contact, with fallback."""
    parts = contact.get("name", "").split()
    return parts[0] if parts else "them"
