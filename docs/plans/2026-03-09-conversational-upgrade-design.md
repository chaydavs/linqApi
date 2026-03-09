# Conversational LinqUp Upgrade — Design Doc

**Date**: 2026-03-09
**Status**: Approved
**Branch**: test1

## Problem

LinqUp works but feels robotic. "Logged:", rigid command parsing, no personalization, image tiles can't send, dates are strings not actionable. The USP — natural language understanding — isn't reflected in the UX.

## Goals

1. Bot feels like a warm, organized friend — not a command-line tool
2. Rep profile personalizes every interaction (drafts reference rep's name/company)
3. Dates are real and actionable (overdue/today/upcoming in /update)
4. Tiles deliver as text sequences (no image dependency)
5. All responses are mobile-optimized (scannable, bullet-pointed)

---

## 1. Rep Profile & Onboarding

### Store
```python
# contacts.py
rep_profiles = {}  # phone -> {"name", "company", "role", "product"}
```

Thread-safe with existing `_lock`. Returns copies like contact store.

### Onboarding Flow
1. First message from unknown rep → bot asks: "Hey! I'm LinqUp — your follow-up sidekick. Quick — what's your name, company, and what do you sell?"
2. Rep responds naturally: "Chay Davuluri, LinqUp, API platform for sales"
3. Claude parses → stores profile
4. Bot confirms: "Nice to meet you, Chay! I'm ready. Text me about anyone you meet and I'll handle the rest."

### /setup Command
- `process_message` detects `/setup` or intent classifier routes "update my profile" etc.
- Parses the text after `/setup` with Claude into profile fields
- Confirms: "Updated! You're Chay Davuluri at LinqUp."

### Profile Injection
- `draft_follow_up()` gets rep profile as context → drafts say "Hey Sarah, it's Chay from LinqUp" not generic
- `generate_summary()` uses rep name in header
- Tile content references rep's company/product naturally

### Files Changed
- `contacts.py` — add `rep_profiles` store, `get_rep_profile()`, `set_rep_profile()`
- `brain.py` — add `PROFILE_PARSE_PROMPT`, update `DRAFT_SYSTEM_PROMPT` to accept rep context
- `app.py` — add onboarding check in `process_message`, add `/setup` handler

---

## 2. Conversational Tone

### Response Rewrites

| Scenario | Current | New |
|----------|---------|-----|
| Brain dump logged | "Logged: Sarah Chen — Stripe, VP RevOps" | "Got Sarah! Stripe, VP RevOps. Case study follow-up on Thursday — I'll remind you." |
| Brain dump updated | "Updated: Sarah Chen" | "Updated Sarah's info — added the phone number." |
| No contacts | "No contacts logged yet." | "No contacts yet! Text me about someone you met — even a quick voice memo works." |
| Help | Wall of text with bullet list | Shorter, warmer, with "just text naturally" emphasis |
| Error | "Couldn't parse that — Error: ..." | "Hmm, I couldn't quite get that. Try something like: 'Met Sarah at Stripe, wants a demo'" |
| Greeting | N/A (was logging "Hi") | "Hey Chay! Ready when you are. Text me about someone you met or say 'update' to check your pipeline." |

### Implementation
- Rewrite confirmation messages in `handle_brain_dump()`
- Rewrite `handle_help()` — shorter, emphasize natural language
- Rewrite `handle_update()` — better formatting (see section 5)
- Intent classifier already handles greetings/conversational — just improve reply quality

### Files Changed
- `app.py` — rewrite response strings in handlers
- `brain.py` — update `INTENT_SYSTEM_PROMPT` reply examples for warmer tone

---

## 3. Smart Date Tracking

### Date Parsing
Add to `parse_brain_dump` output: Claude already extracts `follow_up_date` as a string ("Thursday"). Add a post-processing step:

```python
# brain.py
def resolve_follow_up_date(raw_date: str) -> str:
    """Convert 'Thursday', 'next week', 'in 3 days' to ISO date string."""
```

Uses `datetime` + simple rules:
- Day names → next occurrence of that day
- "next week" → next Monday
- "tomorrow" → tomorrow
- "in X days" → today + X
- Already a date → parse as-is
- Can't parse → keep raw string, log warning

### Contact Store Changes
```python
contact = {
    ...
    "follow_up_date": "Thursday",           # raw string (preserved)
    "follow_up_date_actual": "2026-03-12",  # resolved ISO date
    ...
}
```

### /update Grouping
```
🔴 OVERDUE (1):
  Sarah Chen — Stripe — send case study (2 days ago)
  → Reply 'draft for Sarah' to write follow-up

🟡 TODAY (1):
  David Chen — reconnect with Elliot
  → Reply 'draft for David'

🟢 UPCOMING (1):
  Mike Lee — Acme — schedule demo (in 3 days)

📊 Pipeline: 3 contacts, 1 followed up, 2 drafts ready
```

### Files Changed
- `brain.py` — add `resolve_follow_up_date()`
- `contacts.py` — add `follow_up_date_actual` field to contact schema
- `app.py` — rewrite `handle_update()` with date-aware grouping

---

## 4. Text-Only Tiles

### Current Problem
Tile pipeline generates HTML → Playwright PNG → `_send_image_to_phone()` (stubbed). Images never send.

### Solution
Replace image rendering with text-message sequences. Claude generates the same structured content, but instead of HTML we format as iMessages.

### Text Tile Format
Each tile becomes a separate message sent in sequence:

```
📊 THE CHALLENGE
━━━━━━━━━━━━━━━━━━
67% of RevOps teams spend more time on manual data entry than actual selling.

Is that what your team is dealing with?
```

```
📈 THE SHIFT
━━━━━━━━━━━━━━━━━━
Companies using automated follow-up see:
  • 3.2x faster response times
  • 47% higher conversion rates
  • 60% less manual CRM work

Source: Forrester 2025 Sales Tech Report
```

```
💬 LET'S TALK
━━━━━━━━━━━━━━━━━━
Sarah — want me to show you how this works for a team your size? Happy to do a quick 15-min walkthrough this week.
```

### Implementation
- New function `format_tiles_as_text(tiles: list, contact: dict) -> list[str]`
- Each tile dict → formatted text string based on tile type
- `handle_visual_follow_up()` sends intro → text tiles → outro via `send_message_to_phone()`
- Remove Playwright dependency from the send path (keep for future image support)

### Files Changed
- `tiles/engine.py` — add `generate_and_send_text_deck()`, keep `generate_and_send_deck()` for future
- `tiles/text_renderer.py` — NEW file, `format_tiles_as_text()` with per-type formatters
- `app.py` — `handle_visual_follow_up()` calls text deck instead of image deck

---

## 5. Better Update/Summary Format

### /update — Redesigned
```
Good morning, Chay! Here's your pipeline:

🔴 OVERDUE
  • Sarah Chen (Stripe) — send case study — 2 days ago
    → 'draft for Sarah'

🟡 DUE TODAY
  • David Chen — reconnect with Elliot
    → 'draft for David'

🟢 COMING UP
  • Mike Lee (Acme) — demo next Tuesday

📬 SENT (1)
  • Amy Park (Google) — delivered, no reply yet

━━━━━━━━━━━━━━━━━━
3 contacts | 1 followed up | 2 drafts ready
```

### summary — Redesigned
Keep Claude-generated but update the system prompt to output in this scannable format with emoji grouping and short lines.

### Files Changed
- `app.py` — rewrite `handle_update()` completely
- `brain.py` — update `SUMMARY_SYSTEM_PROMPT` for mobile-friendly format

---

## Implementation Order

| Phase | What | Files | Risk |
|-------|------|-------|------|
| 1 | Rep profile store + onboarding | contacts.py, app.py, brain.py | Low |
| 2 | Conversational tone rewrites | app.py, brain.py | Low |
| 3 | Smart date tracking | brain.py, contacts.py, app.py | Medium (date parsing edge cases) |
| 4 | Better /update format | app.py | Low |
| 5 | Text-only tiles | tiles/text_renderer.py, tiles/engine.py, app.py | Medium |

Each phase is independently testable and deployable.

---

## Future Roadmap (not in this sprint)

- **Proactive morning push** — APScheduler sends /update automatically at rep's preferred time
- **Image tiles** — When Linq media endpoint is confirmed, re-enable Playwright pipeline
- **CRM export** — Dump contacts to CSV or sync to Salesforce/HubSpot
- **Multi-rep support** — Multiple reps sharing a bot number with isolated data
- **Reply tracking** — When a contact replies, surface it in /update
