import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
LINQ_API_TOKEN: str = os.getenv("LINQ_API_TOKEN", "")
LINQ_BASE_URL: str = os.getenv("LINQ_BASE_URL", "https://api.linqapp.com/api/partner/v3")
LINQ_PHONE_NUMBER: str = os.getenv("LINQ_PHONE_NUMBER", "")
PORT = int(os.getenv("PORT", 3000))

CLAUDE_MODEL = "claude-sonnet-4-20250514"

TEMP_HOT = "hot"
TEMP_WARM = "warm"
TEMP_SAVED = "saved"
