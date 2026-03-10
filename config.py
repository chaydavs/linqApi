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

# Validate required env vars at startup
_REQUIRED = {"ANTHROPIC_API_KEY": ANTHROPIC_API_KEY, "LINQ_API_TOKEN": LINQ_API_TOKEN, "LINQ_PHONE_NUMBER": LINQ_PHONE_NUMBER}
_missing = [k for k, v in _REQUIRED.items() if not v]
if _missing:
    import sys
    print(f"[FATAL] Missing required env vars: {', '.join(_missing)}", flush=True)
    sys.exit(1)

TEMP_HOT = "hot"
TEMP_WARM = "warm"
TEMP_SAVED = "saved"
