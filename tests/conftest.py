"""Shared pytest fixtures and configuration for LinqUp tests."""

import pytest
import sys
import os

# Ensure the project root is on sys.path so imports resolve correctly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def sample_contact():
    """Minimal contact dict matching the schema used throughout the app."""
    return {
        "id": "contact-abc-123",
        "name": "Sarah Chen",
        "company": "Stripe",
        "title": "VP RevOps",
        "phone": "+15550001111",
        "email": "sarah@stripe.com",
        "notes": "Current tool too slow for growth; wants enterprise case study",
        "follow_up_date": "Thursday",
        "follow_up_action": "send enterprise case study",
        "temperature": "hot",
        "personal_details": ["husband went to VT"],
        "draft": None,
        "sent": False,
        "reply_received": None,
        "sent_at": None,
    }


@pytest.fixture
def sample_contact_no_phone():
    """Contact without a phone number."""
    return {
        "id": "contact-def-456",
        "name": "Mike Torres",
        "company": "Datadog",
        "title": "Engineering Lead",
        "phone": "",
        "email": "",
        "notes": "Wants pricing deck",
        "follow_up_date": "tomorrow",
        "follow_up_action": "send pricing",
        "temperature": "warm",
        "personal_details": [],
        "draft": "Hey Mike...",
        "sent": False,
        "reply_received": None,
        "sent_at": None,
    }


@pytest.fixture
def sample_contact_minimal():
    """Contact with only required fields — tests graceful handling of missing keys."""
    return {
        "id": "contact-xyz-789",
        "name": "James Wu",
        "company": "",
        "title": "",
        "phone": "",
        "email": "",
        "notes": "",
        "follow_up_date": "",
        "follow_up_action": "",
        "temperature": "saved",
        "personal_details": [],
        "draft": None,
        "sent": False,
        "reply_received": None,
        "sent_at": None,
    }
