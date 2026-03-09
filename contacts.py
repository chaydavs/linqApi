import json
import os
import threading
from datetime import datetime
from typing import Optional
import uuid

_lock = threading.Lock()

# Persistence file path
_DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "store.json")

# Main contact store - keyed by unique ID
contacts = {}

# Map user phone numbers to their contact lists
user_contacts = {}  # phone -> [contact_id, ...]

# Rep profiles — keyed by phone number
rep_profiles = {}  # phone -> {"name", "company", "role", "product"}


def _save() -> None:
    """Persist all stores to disk. Must be called inside _lock."""
    data = {
        "contacts": contacts,
        "user_contacts": user_contacts,
        "rep_profiles": rep_profiles,
    }
    os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
    tmp = _DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, _DATA_FILE)


def _load() -> None:
    """Load stores from disk on startup."""
    global contacts, user_contacts, rep_profiles
    if not os.path.exists(_DATA_FILE):
        return
    try:
        with open(_DATA_FILE) as f:
            data = json.load(f)
        contacts = data.get("contacts", {})
        user_contacts = data.get("user_contacts", {})
        rep_profiles = data.get("rep_profiles", {})
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] Could not load data file: {e}", flush=True)


# Load on import
_load()


def get_rep_profile(user_phone: str) -> Optional[dict]:
    """Get rep profile, or None if not onboarded."""
    with _lock:
        profile = rep_profiles.get(user_phone)
        return dict(profile) if profile else None


def set_rep_profile(user_phone: str, profile_data: dict) -> dict:
    """Create or update rep profile. Returns the stored profile."""
    profile = {
        "phone": user_phone,
        "name": profile_data.get("name", ""),
        "company": profile_data.get("company", ""),
        "role": profile_data.get("role", ""),
        "product": profile_data.get("product", ""),
    }
    with _lock:
        rep_profiles[user_phone] = profile
        _save()
    return dict(profile)


def create_contact(user_phone: str, parsed_data: dict) -> dict:
    """Create a new contact from Claude's parsed output."""
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
        "follow_up_date_actual": parsed_data.get("follow_up_date_actual", ""),
        "follow_up_action": parsed_data.get("follow_up_action", ""),
        "temperature": parsed_data.get("temperature", "warm"),
        "personal_details": list(parsed_data.get("personal_details", [])),
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
        _save()

    return dict(contact)


def get_user_contacts(user_phone: str) -> list:
    """Get all contacts for a user."""
    with _lock:
        ids = user_contacts.get(user_phone, [])
        return [dict(c) for cid in ids if (c := contacts.get(cid)) is not None]


def get_contact_by_id(contact_id: str) -> Optional[dict]:
    """Get a contact by its ID."""
    with _lock:
        contact = contacts.get(contact_id)
        return dict(contact) if contact else None


def update_contact(contact_id: str, **updates) -> Optional[dict]:
    """Update fields on a contact. Returns updated contact or None."""
    with _lock:
        contact = contacts.get(contact_id)
        if not contact:
            return None
        contacts[contact_id] = {**contact, **updates}
        _save()
        return dict(contacts[contact_id])


def find_contact_by_name(user_phone: str, name_query: str) -> Optional[dict]:
    """Fuzzy find a contact by name. Returns the most recent match."""
    user_list = get_user_contacts(user_phone)
    name_lower = name_query.lower()
    # Iterate in reverse so we find the most recently added match
    for c in reversed(user_list):
        if name_lower in c["name"].lower():
            return c
    return None


def find_and_merge_contact(user_phone: str, parsed_data: dict) -> tuple[dict, bool]:
    """Find existing contact by name and merge, or create new.

    Returns (contact, is_new). Merges non-empty fields from parsed_data
    into the existing contact, preserving data that's already there.
    """
    name = parsed_data.get("name", "").strip()
    if not name:
        # No name — can't merge, just create
        return create_contact(user_phone, parsed_data), True

    existing = find_contact_by_name(user_phone, name)

    if not existing:
        return create_contact(user_phone, parsed_data), True

    # Check if it's a close enough name match (not just substring)
    existing_name_lower = existing["name"].lower()
    new_name_lower = name.lower()
    is_close_match = (
        existing_name_lower == new_name_lower
        or existing_name_lower.startswith(new_name_lower)
        or new_name_lower.startswith(existing_name_lower)
    )

    if not is_close_match:
        return create_contact(user_phone, parsed_data), True

    # Merge: update only fields that are non-empty in parsed_data
    mergeable_fields = (
        "company", "title", "phone", "email", "notes",
        "follow_up_date", "follow_up_action", "temperature",
    )
    updates = {}
    for field in mergeable_fields:
        new_val = parsed_data.get(field, "")
        old_val = existing.get(field, "")
        if new_val and (not old_val or new_val != old_val):
            updates[field] = new_val

    # Merge personal_details — combine unique items
    new_details = parsed_data.get("personal_details", [])
    if new_details:
        old_details = existing.get("personal_details", [])
        old_set = {d.lower() for d in old_details}
        merged = list(old_details) + [d for d in new_details if d.lower() not in old_set]
        updates["personal_details"] = merged

    # Merge notes — append if new info
    new_notes = parsed_data.get("notes", "")
    old_notes = existing.get("notes", "")
    if new_notes and old_notes and new_notes != old_notes:
        updates["notes"] = f"{old_notes}; {new_notes}"

    if updates:
        updated = update_contact(existing["id"], **updates)
        return updated or existing, False

    return existing, False


def first_name(contact: dict) -> str:
    """Extract first name from contact, with fallback."""
    parts = contact.get("name", "").split()
    return parts[0] if parts else "them"
