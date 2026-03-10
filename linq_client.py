import json
import logging
from typing import Any, Optional
import requests
from config import LINQ_API_TOKEN, LINQ_BASE_URL, LINQ_PHONE_NUMBER

logger = logging.getLogger(__name__)

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {LINQ_API_TOKEN}",
    "Content-Type": "application/json"
})


def _linq_request(method: str, path: str, json_body: Optional[dict[str, Any]] = None) -> None:
    """Fire-and-forget request to Linq API. Logs failures instead of raising."""
    url = f"{LINQ_BASE_URL}{path}"
    try:
        session.request(method, url, json=json_body, timeout=5)
    except requests.RequestException as e:
        logger.warning("Linq API %s %s failed: %s", method, path, e)


def send_message_to_phone(
    phone_number: str, text: str, effect: Optional[str] = None
) -> dict[str, Any]:
    """Send a new iMessage to a phone number (outbound to contact).

    Uses POST /chats with from/to/message.parts format.
    """
    url = f"{LINQ_BASE_URL}/chats"
    parts: list[dict[str, str]] = [{"type": "text", "value": text}]
    message_obj: dict[str, Any] = {"parts": parts}
    payload: dict[str, Any] = {
        "from": LINQ_PHONE_NUMBER,
        "to": [phone_number],
        "message": message_obj,
    }
    if effect:
        message_obj["effect"] = effect

    try:
        print(f"[SEND_MSG] POST {url}", flush=True)
        print(f"[SEND_MSG] payload: {json.dumps(payload)[:500]}", flush=True)
        resp = session.post(url, json=payload, timeout=15)
        print(f"[SEND_MSG] status={resp.status_code} body={resp.text[:300]}", flush=True)
        resp.raise_for_status()
        data = resp.json()
        chat = data.get("chat", {})
        message = chat.get("message", {})
        return {
            "success": True,
            "chat_id": chat.get("id", ""),
            "message_id": message.get("id", ""),
            "service": chat.get("service", ""),
        }
    except (requests.RequestException, ValueError) as e:
        logger.error("send_message_to_phone failed for %s: %s", phone_number, e)
        print(f"[SEND_MSG] ERROR: {e}", flush=True)
        return {"success": False, "error": str(e)}


def send_reply(
    chat_id: str, text: str, effect: Optional[str] = None
) -> dict[str, Any]:
    """Reply in an existing chat (responding to the rep).

    Uses POST /chats/{chat_id}/messages with parts format.
    """
    url = f"{LINQ_BASE_URL}/chats/{chat_id}/messages"
    message_obj: dict[str, Any] = {
        "parts": [{"type": "text", "value": text}],
    }
    if effect:
        message_obj["effect"] = effect
    payload: dict[str, Any] = {"message": message_obj}

    try:
        print(f"[SEND_REPLY] POST {url}", flush=True)
        print(f"[SEND_REPLY] payload: {payload}", flush=True)
        resp = session.post(url, json=payload, timeout=15)
        print(f"[SEND_REPLY] status={resp.status_code} body={resp.text[:300]}", flush=True)
        resp.raise_for_status()
        data = resp.json()
        return {
            "success": True,
            "message_id": data.get("id", data.get("messageId", "")),
        }
    except (requests.RequestException, ValueError) as e:
        logger.error("send_reply failed for chat %s: %s", chat_id, e)
        print(f"[SEND_REPLY] ERROR: {e}", flush=True)
        return {"success": False, "error": str(e)}


def send_image_reply(chat_id: str, image_url: str) -> dict[str, Any]:
    """Send an image attachment in an existing chat.

    Uses Linq v3 parts format with type "attachment" pointing to a public URL.
    The image must be publicly accessible (e.g., via ngrok).
    """
    url = f"{LINQ_BASE_URL}/chats/{chat_id}/messages"
    payload: dict[str, Any] = {
        "message": {
            "parts": [{"type": "media", "value": image_url}],
        }
    }

    try:
        print(f"[SEND_IMAGE] POST {url}", flush=True)
        print(f"[SEND_IMAGE] image_url: {image_url}", flush=True)
        resp = session.post(url, json=payload, timeout=15)
        print(f"[SEND_IMAGE] status={resp.status_code} body={resp.text[:300]}", flush=True)
        resp.raise_for_status()
        data = resp.json()
        return {
            "success": True,
            "message_id": data.get("id", data.get("messageId", "")),
        }
    except (requests.RequestException, ValueError) as e:
        logger.error("send_image_reply failed for chat %s: %s", chat_id, e)
        print(f"[SEND_IMAGE] ERROR: {e}", flush=True)
        return {"success": False, "error": str(e)}


def start_typing(chat_id: str) -> None:
    """Show typing indicator."""
    _linq_request("POST", f"/chats/{chat_id}/typing")


def stop_typing(chat_id: str) -> None:
    """Hide typing indicator."""
    _linq_request("DELETE", f"/chats/{chat_id}/typing")


def mark_read(chat_id: str) -> None:
    """Mark chat as read."""
    _linq_request("POST", f"/chats/{chat_id}/read")


def send_reaction(message_id: str, reaction: str) -> None:
    """React to a message."""
    if not message_id:
        return
    _linq_request("POST", f"/messages/{message_id}/reactions", {"reaction": reaction})
