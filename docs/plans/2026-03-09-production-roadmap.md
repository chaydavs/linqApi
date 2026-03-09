# LinqUp — Production Architecture & Product Roadmap

**Date**: 2026-03-09
**Status**: Planning

## Where We Are (Demo)

```
iPhone iMessage → Linq Blue API → Flask webhook → Claude AI → Linq API → iMessage out
                                        ↓
                                  JSON file store
```

- Single Flask server, single Linq bot number
- In-memory + JSON file persistence
- Multi-rep works (data isolated by phone number)
- No auth, no database, no queue, no deployment pipeline

## Phase 1: Demo-Ready (Current)

**What works:**
- Brain dump parsing (Claude) with contact merging
- Intent classification (conversational routing)
- Draft generation personalized to rep profile
- Date tracking with overdue/today/upcoming
- Text-based tile follow-ups
- Contact CRUD with JSON persistence
- Rep onboarding + /setup

**What's stubbed:**
- Image tile sending (Linq media endpoint TBD)
- send_message_to_phone getting 400 (payload format needs debugging)
- No proactive reminders (passive only via /update)

---

## Phase 2: Production MVP

### Architecture

```
                    ┌─────────────────────────────────┐
                    │         TRANSPORT LAYER          │
                    │                                  │
  iMessage ──→ Linq Blue ──┐                          │
  SMS ──→ Twilio ──────────┤                          │
  WhatsApp ──→ WA Biz API ─┤  Webhook Router          │
  Slack ──→ Slack Events ──┤  (normalize to common    │
  Web App ──→ REST API ────┘   message format)        │
                    │                                  │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │          MESSAGE QUEUE            │
                    │    (Redis / SQS / Bull)           │
                    │    Decouples webhook from brain   │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │           BRAIN LAYER             │
                    │                                   │
                    │  Intent Classifier (Claude)       │
                    │  Brain Dump Parser (Claude)       │
                    │  Draft Generator (Claude)         │
                    │  Tile Content Generator (Claude)  │
                    │  Date Resolver                    │
                    │  Contact Merger                   │
                    │                                   │
                    │  * Same code as demo, just        │
                    │    extracted into workers          │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │         DATA LAYER                │
                    │                                   │
                    │  PostgreSQL                       │
                    │  ├── users (rep profiles)         │
                    │  ├── contacts                     │
                    │  ├── drafts                       │
                    │  ├── messages (audit log)         │
                    │  └── reminders                    │
                    │                                   │
                    │  Redis (cache + queue)            │
                    └──────────────────────────────────┘
```

### Key Changes from Demo → Production

| Component | Demo | Production |
|-----------|------|------------|
| Storage | JSON file | PostgreSQL |
| Queue | ThreadPoolExecutor | Redis + worker processes |
| Auth | None (phone = identity) | JWT + API keys |
| Transport | Linq only | Multi-channel adapter |
| Deployment | `python app.py` | Docker + Railway/Fly.io |
| Monitoring | print() statements | Sentry + structured logging |
| Rate limiting | None | Per-user + per-channel |
| Secrets | .env file | Vault / Railway secrets |

### Database Schema (PostgreSQL)

```sql
-- Rep/user accounts
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone VARCHAR(20) UNIQUE,
    email VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    role VARCHAR(255),
    product TEXT,
    channel VARCHAR(20) DEFAULT 'imessage',  -- imessage, sms, whatsapp, slack
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Contacts captured by reps
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    title VARCHAR(255),
    phone VARCHAR(20),
    email VARCHAR(255),
    notes TEXT,
    follow_up_date DATE,
    follow_up_action TEXT,
    temperature VARCHAR(10) DEFAULT 'warm',
    personal_details JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Drafts (versioned, not overwritten)
CREATE TABLE drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id UUID REFERENCES contacts(id),
    content TEXT NOT NULL,
    version INT DEFAULT 1,
    sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMPTZ,
    sent_via VARCHAR(20),
    reply_received TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Scheduled reminders
CREATE TABLE reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    contact_id UUID REFERENCES contacts(id),
    remind_at TIMESTAMPTZ NOT NULL,
    action TEXT NOT NULL,
    sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Transport Adapter Pattern

```python
# Each channel implements this interface
class TransportAdapter:
    def send_message(self, to: str, text: str) -> dict:
        """Send a text message to a recipient."""
        ...

    def send_image(self, to: str, image_url: str) -> dict:
        """Send an image to a recipient."""
        ...

    def parse_webhook(self, payload: dict) -> Message:
        """Normalize incoming webhook to common Message format."""
        ...

class LinqAdapter(TransportAdapter): ...
class TwilioAdapter(TransportAdapter): ...
class SlackAdapter(TransportAdapter): ...
class WhatsAppAdapter(TransportAdapter): ...
```

The brain layer never touches transport directly — it receives a `Message` and returns a `Response`. The adapter handles delivery.

---

## Phase 3: Growth Features

### 3a. Proactive Reminders
- APScheduler or Celery Beat checks `reminders` table every minute
- Sends morning briefing at rep's preferred time
- Nudges for overdue follow-ups: "Hey Chay, Sarah's case study is 2 days overdue"
- Rep sets schedule: "/remind me at 8am" or "/remind me every morning"

### 3b. CRM Integration
- One-click export to Salesforce, HubSpot, Pipedrive
- Bidirectional sync: if a contact replies in CRM, LinqUp knows
- OAuth flow for each CRM
- Field mapping: LinqUp contact fields → CRM custom fields

### 3c. Team Dashboard (Web App)
- Manager view: all reps' pipelines in one dashboard
- Analytics: contacts captured per event, follow-up rates, response rates
- Leaderboard: who's following up fastest
- Built with Next.js + the same PostgreSQL backend

### 3d. Smart Tile Images
- When Linq confirms media endpoint, re-enable Playwright pipeline
- Or: host tile images on S3/Cloudflare, send as URLs
- Or: generate tiles as PDF attachments

### 3e. Reply Tracking
- When a contact replies to a sent message, match it back to the contact
- Surface in /update: "Sarah replied: 'Sounds great, let's chat Tuesday'"
- Auto-suggest next action: "Want me to schedule that call?"

---

## Product Roadmap

### Q2 2026 — Demo to Beta
| Week | Milestone |
|------|-----------|
| 1-2 | Fix send_message_to_phone, image tiles, polish demo |
| 3-4 | PostgreSQL migration, Docker deployment |
| 5-6 | Twilio SMS adapter (second channel) |
| 7-8 | Web signup flow, JWT auth, beta launch (10 reps) |

### Q3 2026 — Beta to Launch
| Month | Milestone |
|-------|-----------|
| Jul | Proactive reminders, reply tracking |
| Aug | CRM integration (Salesforce + HubSpot) |
| Sep | Team dashboard (web), analytics |

### Q4 2026 — Scale
| Month | Milestone |
|-------|-----------|
| Oct | WhatsApp + Slack channels |
| Nov | Enterprise features: SSO, admin controls, audit log |
| Dec | Self-serve signup, pricing tiers, public launch |

---

## Pricing Model (Conceptual)

| Tier | Price | What |
|------|-------|------|
| Free | $0/mo | 10 contacts, 5 drafts/day, iMessage only |
| Pro | $29/mo | Unlimited contacts, all channels, CRM export |
| Team | $19/rep/mo | Manager dashboard, analytics, shared contacts |
| Enterprise | Custom | SSO, API access, dedicated support, SLA |

Revenue levers:
- Per-rep seat pricing (SaaS standard)
- Claude API costs are ~$0.03-0.10 per interaction (very low marginal cost)
- CRM integrations as upsell
- Volume discounts for large teams

---

## Technical Decisions — Why Each Choice

| Decision | Why |
|----------|-----|
| PostgreSQL over MongoDB | Relational data (users → contacts → drafts), strong consistency, JSONB for flexible fields |
| Redis queue over Celery | Simpler ops, built-in pub/sub for real-time, fast enough for our scale |
| Transport adapter pattern | Add channels without touching brain logic, each adapter is ~100 lines |
| Claude for intent + parsing | No training data needed, handles messy human text, works day one |
| JSON file for demo | Zero setup, good enough for demo, easy to migrate (just INSERT rows) |
| Flask → FastAPI for prod | Async support for concurrent Claude calls, built-in OpenAPI docs |

---

## Migration Path: Demo → Production

The code is already structured for this migration:

1. **contacts.py** → becomes SQLAlchemy models + repository pattern
2. **brain.py** → unchanged (pure Claude logic, no storage dependency)
3. **app.py** → split into routes.py (endpoints) + handlers.py (business logic)
4. **linq_client.py** → becomes one of several transport adapters
5. **tiles/** → unchanged (content generation is transport-agnostic)

The brain is the product. Everything else is plumbing.
