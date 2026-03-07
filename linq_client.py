import logging
import requests
from config import LINQ_API_TOKEN, LINQ_BASE_URL

logger = logging.getLogger(__name__)

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {LINQ_API_TOKEN}",
    "Content-Type": "application/json"
})


def _linq_request(method: str, path: str, json_body: dict = None) -> None:
    """Fire-and-forget request to Linq API. Logs failures instead of raising."""
    url = f"{LINQ_BASE_URL}{path}"
    try:
        session.request(method, url, json=json_body)
    except requests.RequestException as e:
        logger.warning("Linq API %s %s failed: %s", method, path, e)


def send_message(chat_id: str, text: str, effect: str = None) -> dict:
    """Send an iMessage to a chat. Returns message data including ID."""
    url = f"{LINQ_BASE_URL}/chats/{chat_id}/messages"
    payload = {"text": text}
    if effect:
        payload["effect"] = effect
    try:
        resp = session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.error("send_message failed for chat %s: %s", chat_id, e)
        return {"error": str(e)}


def send_message_to_phone(phone_number: str, text: str) -> dict:
    """Send an iMessage directly to a phone number (for follow-ups to contacts).

    NOTE: Check sandbox docs for exact endpoint. This may need adjustment
    based on the actual Linq Blue v3 API structure.
    """
    # Attempt 1: Direct message to phone
    url = f"{LINQ_BASE_URL}/messages"
    payload = {"to": phone_number, "text": text}
    resp = session.post(url, json=payload)

    if resp.status_code in (200, 201):
        return resp.json()

    # Attempt 2: Create chat first, then send message
    chat_url = f"{LINQ_BASE_URL}/chats"
    chat_resp = session.post(chat_url, json={"participants": [phone_number]})
    if chat_resp.status_code in (200, 201):
        chat_data = chat_resp.json()
        chat_id = chat_data.get("id") or chat_data.get("chatId")
        if chat_id:
            return send_message(chat_id, text)

    return {"error": "Could not send - check API docs for correct endpoint"}


def start_typing(chat_id: str):
    """Show typing indicator."""
    _linq_request("POST", f"/chats/{chat_id}/typing")


def stop_typing(chat_id: str):
    """Hide typing indicator."""
    _linq_request("DELETE", f"/chats/{chat_id}/typing")


def mark_read(chat_id: str):
    """Mark chat as read."""
    _linq_request("POST", f"/chats/{chat_id}/read")


def send_reaction(message_id: str, reaction: str):
    """React to a message."""
    if not message_id:
        return
    _linq_request("POST", f"/messages/{message_id}/reactions", {"reaction": reaction})
