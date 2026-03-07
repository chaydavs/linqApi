import requests
from config import LINQ_API_TOKEN, LINQ_BASE_URL

HEADERS = {
    "Authorization": f"Bearer {LINQ_API_TOKEN}",
    "Content-Type": "application/json"
}


def send_message(chat_id: str, text: str, effect: str = None) -> dict:
    """Send an iMessage to a chat. Returns message data including ID."""
    url = f"{LINQ_BASE_URL}/chats/{chat_id}/messages"
    payload = {"text": text}
    if effect:
        payload["effect"] = effect
    resp = requests.post(url, json=payload, headers=HEADERS)
    return resp.json()


def send_message_to_phone(phone_number: str, text: str) -> dict:
    """Send an iMessage directly to a phone number (for follow-ups to contacts).

    NOTE: Check sandbox docs for exact endpoint. This may need adjustment
    based on the actual Linq Blue v3 API structure.
    """
    # Attempt 1: Direct message to phone
    url = f"{LINQ_BASE_URL}/messages"
    payload = {"to": phone_number, "text": text}
    resp = requests.post(url, json=payload, headers=HEADERS)

    if resp.status_code == 200:
        return resp.json()

    # Attempt 2: Create chat first, then send message
    chat_url = f"{LINQ_BASE_URL}/chats"
    chat_resp = requests.post(chat_url, json={"participants": [phone_number]}, headers=HEADERS)
    if chat_resp.status_code == 200:
        chat_data = chat_resp.json()
        chat_id = chat_data.get("id") or chat_data.get("chatId")
        if chat_id:
            return send_message(chat_id, text)

    return {"error": "Could not send - check API docs for correct endpoint"}


def start_typing(chat_id: str):
    """Show typing indicator."""
    url = f"{LINQ_BASE_URL}/chats/{chat_id}/typing"
    try:
        requests.post(url, headers=HEADERS)
    except requests.RequestException:
        pass


def stop_typing(chat_id: str):
    """Hide typing indicator."""
    url = f"{LINQ_BASE_URL}/chats/{chat_id}/typing"
    try:
        requests.delete(url, headers=HEADERS)
    except requests.RequestException:
        pass


def mark_read(chat_id: str):
    """Mark chat as read."""
    url = f"{LINQ_BASE_URL}/chats/{chat_id}/read"
    try:
        requests.post(url, headers=HEADERS)
    except requests.RequestException:
        pass


def send_reaction(message_id: str, reaction: str):
    """React to a message."""
    if not message_id:
        return
    url = f"{LINQ_BASE_URL}/messages/{message_id}/reactions"
    try:
        requests.post(url, json={"reaction": reaction}, headers=HEADERS)
    except requests.RequestException:
        pass
