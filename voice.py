import requests
import tempfile
import os
from openai import OpenAI
from config import OPENAI_API_KEY

_openai_client = None


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def transcribe_voice_memo(audio_url: str) -> str:
    """Download voice memo from Linq webhook data and transcribe with Whisper."""
    audio_response = requests.get(audio_url)
    audio_response.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
        f.write(audio_response.content)
        temp_path = f.name

    try:
        with open(temp_path, "rb") as audio_file:
            transcript = _get_openai_client().audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return transcript.text
    finally:
        os.unlink(temp_path)
