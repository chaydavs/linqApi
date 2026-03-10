# LinqUp

**AI-powered follow-up agent for sales reps, built on Linq's iMessage API.**

LinqUp turns messy conference brain dumps into structured contacts, personalized follow-up drafts, and visual tile presentations — all from a single iMessage thread.

---

## The Problem

A salesperson meets 50+ people at a conference. By Monday, they remember maybe 5 conversations clearly. The rest? Business cards in a pocket, never followed up.

CRMs don't help — nobody opens Salesforce at 11pm after a conference dinner.

**LinqUp lives where reps already are: iMessage.** Text about someone you met, get an AI-drafted follow-up in seconds.

---

## How It Works

```
Rep texts brain dump → Claude parses contact info → Stores with date tracking
                                                   → Generates personalized draft
                                                   → Creates visual tile deck
                                                   → All previewed in iMessage
```

### Demo Flow

| Step | You text | LinqUp responds |
|------|----------|----------------|
| 1 | `Hey` | Onboarding — asks for your name, company, product |
| 2 | `Chay Davuluri, LinqUp, AI sales platform` | Profile saved, ready to go |
| 3 | `Sarah Chen, Stripe, VP RevOps, wants case study, follow up Thursday, she's training for a marathon` | Parses name, company, title, action, date, personal detail |
| 4 | `update` | Pipeline grouped by urgency: overdue / today / upcoming |
| 5 | `draft for Sarah` | AI-generated personalized follow-up referencing the marathon |
| 6 | `send` | Finalizes draft, ready to copy and send |
| 7 | `follow up with Sarah` | Generates visual tile presentation in-chat |
| 8 | `/restart` | Clears everything, fresh start |

---

## Features

### Contact Capture
- **Natural language parsing** — text however you want, Claude extracts structured data
- **Voice memo support** — send a voice note, Whisper transcribes, then parses
- **Contact merging** — re-mention someone and new info merges in, no duplicates
- **Date tracking** — "follow up Thursday" becomes an actual date with overdue alerts

### AI Drafts
- **Personalized to the rep** — uses your name, company, and product context
- **References personal details** — marathon training, school connections, shared interests
- **Editable** — say "edit make it shorter" or "edit add the case study link"
- **Preview mode** — drafts shown to you first, you decide when to send

### Visual Tile Decks
- **5 deck types**: hook, ROI, proof, personal, competitive
- **12 tile types**: cover, stat, list, comparison, math, timeline, quote, metrics, and more
- **AI-selected** — Claude picks the best deck type based on the contact's context
- **Hintable** — "follow up with Sarah, include something about scaling" steers the content

### Pipeline Management
- **Morning update** — grouped by overdue (red), today (yellow), upcoming (green)
- **Sent tracking** — see which contacts have been followed up
- **Draft status** — see who has a draft ready vs. who needs one

### Rep Onboarding
- **One-message setup** — text your name, company, and what you sell
- **Profile persists** — survives server restarts via JSON file storage
- **Personalized output** — drafts reference your identity, not generic templates

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Server | Python 3.11 + Flask | Webhook handler, command routing |
| AI | Claude API (Sonnet) | Parse brain dumps, classify intent, draft follow-ups, generate tiles |
| Voice | OpenAI Whisper | Transcribe voice memos to text |
| Messaging | Linq Blue v3 API | Receive/send iMessages via webhook |
| Visual Tiles | Playwright + Chromium | HTML-to-PNG tile rendering (image pipeline) |
| Persistence | JSON file store | Thread-safe, atomic writes, survives restarts |

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/chaydavs/linqApi.git
cd linqApi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # for visual tile image rendering
```

### 2. Configure environment

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...            # optional — only needed for voice memos
LINQ_API_TOKEN=your-linq-token
LINQ_PHONE_NUMBER=+1XXXXXXXXXX
```

The server validates these at startup and will exit with a clear error if any are missing.

### 3. Start the server

```bash
python3 app.py
```

### 4. Expose with ngrok

```bash
ngrok http 3000
```

### 5. Configure webhook

Set your ngrok URL + `/webhook` as the webhook URL in the [Linq sandbox dashboard](https://dashboard.linqapp.com).

---

## Commands

| Command | What it does |
|---------|-------------|
| *(any text with contact info)* | Parse as brain dump, store/merge contact |
| *(voice memo)* | Transcribe with Whisper, then parse |
| `update` | Pipeline view — overdue, today, upcoming, sent |
| `contacts` | List all saved contacts with status |
| `summary` | AI-generated day recap by priority |
| `draft for [name]` | Generate personalized follow-up message |
| `send` | Finalize last draft (ready to copy & send) |
| `send to [name]` | Finalize draft for a specific contact |
| `follow up with [name]` | Generate visual tile presentation |
| `edit [changes]` | Revise the last draft |
| `/setup` | Update your rep profile |
| `/restart` | Clear all data and start fresh |
| `help` | Show command reference |

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────────────────────────────┐
│   iPhone     │────>│  Linq Blue   │────>│  Flask Server                      │
│   iMessage   │<────│  v3 API      │<────│                                    │
└─────────────┘     └──────────────┘     │  app.py        → Routing + Handlers│
                                          │  brain.py      → Claude AI Engine  │
                                          │  contacts.py   → Contact Store     │
                                          │  linq_client.py→ Linq API Client   │
                                          │  voice.py      → Whisper API       │
                                          │  tiles/         → Visual Tile Engine│
                                          └────────────────────────────────────┘
```

### Message Flow

```
Webhook POST → event_type filter → direction filter → ThreadPoolExecutor
    → Fast-path keyword match (no AI call) OR Claude intent classification
    → Route to handler (brain_dump, draft, update, visual, etc.)
    → Reply via Linq API
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Two-tier routing (fast path + Claude) | Common commands skip the AI call entirely — lower latency |
| JSON file persistence | Zero-setup for demo, atomic writes, easy migration to PostgreSQL |
| Lazy API client init | Server starts without API keys at import time — fails on first use |
| Contact copies (immutable) | Thread-safe access from 10 concurrent executor threads |
| Preview mode (no outbound send) | Drafts and tiles shown to rep in-chat — they forward when ready |

---

## File Structure

```
linqApi/
├── app.py                 # Flask server, webhook, intent routing, all command handlers
├── brain.py               # Claude API — intent classification, parsing, drafting, dates
├── contacts.py            # Thread-safe contact store with JSON persistence
├── linq_client.py         # Linq Blue v3 API client (reply, typing, reactions)
├── voice.py               # OpenAI Whisper voice memo transcription
├── config.py              # Environment variables, constants, startup validation
├── tiles/
│   ├── prompts.py         # Deck guidelines, accent colors, tile dimensions
│   ├── renderer.py        # HTML template rendering (XSS-safe, html.escape)
│   ├── text_renderer.py   # Text-based tile formatting for iMessage
│   ├── image_converter.py # Playwright HTML-to-PNG conversion
│   └── engine.py          # Tile pipeline orchestration
├── tests/                 # 215 pytest tests
│   ├── test_app_routing.py
│   ├── test_tiles_engine.py
│   ├── test_tiles_renderer.py
│   ├── test_tiles_prompts.py
│   └── test_image_converter.py
├── tile_preview/          # Sample tile output images
├── docs/plans/            # Architecture and design documents
├── requirements.txt
└── .gitignore
```

---

## Testing

```bash
python -m pytest tests/ -v
```

215 tests covering:
- Intent routing and command parsing
- Tile rendering (all 12 tile types)
- Tile engine (context assembly, deck selection, content generation)
- Prompt templates and deck configuration
- Image converter cleanup and error handling

### Simulate a webhook locally

```bash
curl -X POST http://localhost:3000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "api_version": "v3",
    "event_type": "message.received",
    "data": {
      "direction": "inbound",
      "chat": {"id": "test-chat-id"},
      "sender_handle": {"handle": "+1234567890"},
      "parts": [{"type": "text", "value": "Sarah Chen, Stripe, VP RevOps, wants case study, follow up Thursday"}],
      "id": "msg-001"
    }
  }'
```

---

## Production Roadmap

See [docs/plans/2026-03-09-production-roadmap.md](docs/plans/2026-03-09-production-roadmap.md) for:
- PostgreSQL migration plan
- Multi-channel transport adapter pattern (SMS, WhatsApp, Slack)
- Proactive reminders and CRM integration
- Team dashboard and analytics
- Pricing model
