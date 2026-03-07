# LinqUp — Conference Contact Agent

## Project Overview
Flask webhook server that receives iMessages via Linq Blue API, parses brain dumps with Claude, manages contacts, drafts personalized follow-ups, generates visual tile decks, and sends them as real iMessages.

## Architecture
```
iPhone iMessage → Linq Blue API → webhook POST → Flask → Claude/Whisper → Linq API → iMessage out
                                                       → Tiles Engine → Playwright → PNG → iMessage out
```

## File Structure
- `app.py` — Flask server, webhook handler, message routing, all command handlers
- `brain.py` — Claude API integration (parse brain dumps, draft follow-ups, generate summaries)
- `contacts.py` — Thread-safe contact store with CRUD operations (returns copies, not references)
- `linq_client.py` — Linq Blue v3 API client (send messages, typing indicators, reactions)
- `voice.py` — Whisper transcription for voice memos
- `config.py` — Environment variables and constants
- `tiles/` — Visual tile deck engine
  - `prompts.py` — Claude prompts, deck guidelines, accent colors, gradients, tile dimensions
  - `renderer.py` — HTML template rendering (900x1200px self-contained pages, HTML-escaped)
  - `image_converter.py` — Playwright HTML-to-PNG conversion
  - `engine.py` — Full pipeline: context → deck type → content → render → send
- `tests/` — pytest test suite (216 tests)

## Running
```bash
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # needed for visual tiles
python3 app.py
# In another terminal: ngrok http 3000
# Set webhook URL in Linq dashboard to: https://<ngrok-url>/webhook
```

## Testing
```bash
python -m pytest tests/ -v
```

## Key Conventions

### Constants
- Model name: use `CLAUDE_MODEL` from `config.py`, never hardcode
- Temperature values: use `TEMP_HOT`, `TEMP_WARM`, `TEMP_SAVED` from `config.py`
- Tile dimensions: use `TILE_WIDTH`, `TILE_HEIGHT` from `tiles/prompts.py` — single source of truth

### Thread Safety
- All contact store mutations go through `contacts.py` functions (`create_contact`, `update_contact`)
- Contact accessors return **shallow copies** (`dict(contact)`), not live store references
- Never mutate contact dicts directly in `app.py` — use `update_contact(contact_id, field=value)`
- Webhook processing uses `ThreadPoolExecutor(max_workers=10)`, not bare threads
- `last_draft_shown` dict is protected by `_draft_lock` in `app.py`

### API Calls
- Claude: use `_call_claude(system, content, max_tokens)` helper in `brain.py`
- Anthropic client is lazy-initialized via `_get_client()` (doesn't crash without API key at import)
- Linq fire-and-forget: use `_linq_request(method, path, json)` helper in `linq_client.py`
- Linq client uses `requests.Session` for connection reuse — don't create raw `requests.get/post`

### Contact Access
- Use `get_contact_by_id()` not `contacts_store.get()` — encapsulates the store
- Use `first_name(contact)` not `contact["name"].split()[0]` — handles edge cases
- Use `find_contact_by_name()` for fuzzy lookup by name

### Error Handling
- All handlers log exceptions via `logger.exception()`
- Linq helper functions log warnings on failure, don't raise
- Both OpenAI and Anthropic clients are lazy-initialized (don't crash without API key at import)

### Visual Tiles
- 5 deck types: hook, roi, proof, personal, competitive
- 12 tile types: cover, stat, list, gain, comparison, metrics, quote, math, timeline, personal, bridge, cta
- Tile content generated via `_call_claude()` in `brain.py` — same pattern as other Claude calls
- All Claude-generated content is `html.escape()`d before HTML injection (XSS prevention)
- Accent colors validated against hex pattern via `_safe_accent()` (CSS injection prevention)
- HTML rendered at 900x1200px with DM Sans font, dark gradients, single accent color per deck
- Playwright converts HTML to PNG screenshots for iMessage sending
- JSON parse has single retry on `JSONDecodeError` (matches `parse_brain_dump` pattern)
- Add new tile types in `renderer.py:_tile_inner_html()`, new deck types in `prompts.py`
- After adding Playwright: `playwright install chromium`

### Immutability
- Contact store returns copies, never live references
- `update_contact()` creates new dict (`{**contact, **updates}`), doesn't mutate in place
- `generate_tile_content()` returns new tile dicts with accent, doesn't mutate parsed JSON
- `create_contact()` copies `personal_details` list to avoid shared mutable default

### Git Workflow
- Work on `test1` branch, push after every change
- Commit format: `type: description` (feat, fix, refactor, docs, chore)

## Common Mistakes to Avoid
1. **Don't hardcode model names** — always use `CLAUDE_MODEL` constant
2. **Don't mutate contacts directly** — use `update_contact()` from contacts.py
3. **Don't use bare `threading.Thread`** — use the `executor` ThreadPoolExecutor
4. **Don't silently swallow errors** — always log with `logger.warning()` or `logger.exception()`
5. **Don't eagerly generate drafts** — generate lazily when user requests with "draft for"
6. **Don't create new `requests` calls in linq_client** — use `session` and `_linq_request()`
7. **Don't send full contact objects to Claude** — trim to only needed fields (see `SUMMARY_FIELDS`)
8. **Don't import `contacts` dict directly** — use accessor functions from contacts.py
9. **Don't forget webhook validation** — always check for required fields before processing
10. **Don't use raw temperature strings** — use `TEMP_HOT`, `TEMP_WARM`, `TEMP_SAVED`
11. **Don't inject Claude output into HTML unescaped** — always use `html.escape()` in renderer.py
12. **Don't return live dict references from contacts.py** — always return `dict(contact)` copies
13. **Don't define TILE_WIDTH/HEIGHT locally** — import from `tiles/prompts.py`
14. **Don't eagerly initialize API clients** — use lazy `_get_client()` / `_get_openai_client()` pattern
15. **Don't access `last_draft_shown` without `_draft_lock`** — it's shared across executor threads
