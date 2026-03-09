# LinqUp — Conference Contact Agent

> Text your Linq number a brain dump after every conference conversation. The agent captures it, structures it, drafts a human-sounding follow-up, sends it as a real iMessage, and gives you status updates the next morning.

## The Problem

A salesperson meets 30-80 people at a conference. By Monday, they remember maybe 5 conversations clearly. Linq's badge scanner captures WHO you meet (name, email, company). LinqUp captures WHAT you talked about and executes the follow-up.

## How It Works

Everything lives in one iMessage thread with your Linq number:

1. **Capture** — Text a brain dump: `"Sarah Chen, Stripe, VP RevOps. Wants case study. Husband went to VT. Follow up Thursday."`
2. **Recall** — Text `summary` to see everyone you met, organized by priority
3. **Draft** — Text `draft for Sarah` to review an AI-generated personal follow-up
4. **Send** — Text `send` to deliver it as a real iMessage to Sarah's phone
5. **Visual** — Text `send Sarah something about scaling` to generate and send AI visual tiles
6. **Update** — Text `/update` the next morning for a status briefing

## Tech Stack

| Component | Technology |
|---|---|
| Server | Python 3.11 + Flask |
| AI Brain | Claude API (Sonnet) |
| Voice | OpenAI Whisper API |
| Messaging | Linq Blue v3 API |
| Visual Tiles | Playwright + Chromium |
| Tunnel | ngrok |

## Setup

### 1. Clone and install

```bash
git clone https://github.com/chaydavs/linqApi.git
cd linqApi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys:
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...        (optional, for voice memos)
# LINQ_API_TOKEN=...
# LINQ_PHONE_NUMBER=+1...
```

### 3. Start the server

```bash
python3 app.py
```

### 4. Expose with ngrok

```bash
ngrok http 3000
```

### 5. Configure webhook

Set your ngrok URL + `/webhook` as the webhook URL in the Linq sandbox dashboard.

## Commands

| Command | What it does |
|---|---|
| *(any text)* | Parse as brain dump, log contact |
| *(voice memo)* | Transcribe with Whisper, then parse as brain dump |
| `summary` | Day summary organized by priority |
| `/update` | Morning briefing — replies, pending, today's actions |
| `draft for [name]` | Review AI-generated follow-up |
| `send` | Send last shown draft |
| `send to [name]` | Send draft for specific person |
| `send [name] something` | Generate and send visual tile deck |
| `follow up with [name]` | Visual follow-up with context tiles |
| `edit [changes]` | Modify the last shown draft |
| `contacts` | List all logged contacts |
| `help` | Show command list |

## Visual Tiles

LinqUp can generate AI-powered visual micro-presentations sent as image tiles via iMessage. Each deck tells a story tailored to the contact.

### Deck Types

| Type | When used | Tiles |
|---|---|---|
| **Hook** | Lead has a pain point, needs re-engagement | 5 tiles |
| **ROI** | Pushed back on pricing, needs justification | 5 tiles |
| **Proof** | Wants social proof, case studies, validation | 4 tiles |
| **Personal** | Strong personal connection captured | 3 tiles |
| **Competitive** | Evaluating alternatives or using a competitor | 4 tiles |

### How it works

```
Contact context → Claude selects deck type → Claude generates tile content (JSON)
→ HTML rendering (900x1200px, DM Sans, dark gradients) → Playwright screenshots
→ PNG images sent via Linq iMessage API
```

You can hint the deck type: `send Sarah something about ROI` will force an ROI deck.

## Testing

```bash
python -m pytest tests/ -v
```

216 tests covering routing, tile rendering, engine logic, prompts, and image conversion.

### Simulate a webhook locally

```bash
curl -X POST http://localhost:3000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "type": "message.received",
    "data": {
      "chatId": "test-chat",
      "sender": "+1234567890",
      "text": "Sarah Chen, Stripe, VP RevOps, wants case study, husband went to VT, follow up Thursday",
      "messageId": "msg1"
    }
  }'
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────────────────┐
│   iPhone     │────▶│  Linq Blue   │────▶│  Flask Server (app.py)       │
│   iMessage   │◀────│  API         │◀────│                              │
└─────────────┘     └──────────────┘     │  brain.py    → Claude API    │
                                          │  contacts.py → Contact Store │
                                          │  linq_client → Linq API      │
                                          │  voice.py    → Whisper API   │
                                          │  tiles/      → Visual Engine │
                                          └──────────────────────────────┘
```

## File Structure

```
├── app.py              # Flask server, webhook, command routing
├── brain.py            # Claude API — parse, draft, summarize
├── contacts.py         # Thread-safe contact store
├── linq_client.py      # Linq API client
├── voice.py            # Whisper transcription
├── config.py           # Environment variables, constants
├── tiles/
│   ├── prompts.py      # Claude prompts, deck guidelines, constants
│   ├── renderer.py     # HTML template rendering (XSS-safe)
│   ├── image_converter.py  # Playwright HTML → PNG
│   └── engine.py       # Full pipeline orchestration
├── tests/              # pytest suite (216 tests)
├── requirements.txt    # Python dependencies
├── CLAUDE.md           # Development instructions
├── .env.example        # API key template
└── .gitignore
```
