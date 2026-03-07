# LinqUp — Conference Contact Agent

## Project Overview
Flask webhook server that receives iMessages via Linq Blue API, parses brain dumps with Claude, manages contacts, drafts personalized follow-ups, and sends them as real iMessages.

## Architecture
```
iPhone iMessage → Linq Blue API → webhook POST → Flask → Claude/Whisper → Linq API → iMessage out
```

## File Structure
- `app.py` — Flask server, webhook handler, message routing, all command handlers
- `brain.py` — Claude API integration (parse brain dumps, draft follow-ups, generate summaries)
- `contacts.py` — Thread-safe contact store with CRUD operations
- `linq_client.py` — Linq Blue v3 API client (send messages, typing indicators, reactions)
- `voice.py` — Whisper transcription for voice memos
- `config.py` — Environment variables and constants
- `tiles/` — Visual tile deck engine
  - `prompts.py` — Claude prompts, deck guidelines, accent colors, gradients
  - `renderer.py` — HTML template rendering (900x1200px self-contained pages)
  - `image_converter.py` — Playwright HTML-to-PNG conversion
  - `engine.py` — Full pipeline: context → deck type → content → render → send

## Running
```bash
source venv/bin/activate
python3 app.py
# In another terminal: ngrok http 3000
# Set webhook URL in Linq dashboard to: https://<ngrok-url>/webhook
```

## Key Conventions

### Constants
- Model name: use `CLAUDE_MODEL` from `config.py`, never hardcode
- Temperature values: use `TEMP_HOT`, `TEMP_WARM`, `TEMP_SAVED` from `config.py`

### Thread Safety
- All contact store mutations go through `contacts.py` functions (`create_contact`, `update_contact`)
- Never mutate contact dicts directly in `app.py` — use `update_contact(contact_id, field=value)`
- Webhook processing uses `ThreadPoolExecutor(max_workers=10)`, not bare threads

### API Calls
- Claude: use `_call_claude(system, content, max_tokens)` helper in `brain.py`
- Linq fire-and-forget: use `_linq_request(method, path, json)` helper in `linq_client.py`
- Linq client uses `requests.Session` for connection reuse — don't create raw `requests.get/post`

### Contact Access
- Use `get_contact_by_id()` not `contacts_store.get()` — encapsulates the store
- Use `first_name(contact)` not `contact["name"].split()[0]` — handles edge cases
- Use `find_contact_by_name()` for fuzzy lookup by name

### Error Handling
- All handlers log exceptions via `logger.exception()`
- Linq helper functions log warnings on failure, don't raise
- OpenAI client is lazy-initialized (doesn't crash without API key at import)

### Visual Tiles
- 5 deck types: hook, roi, proof, personal, competitive
- Tile content generated via `_call_claude()` in `brain.py` — same pattern as other Claude calls
- HTML rendered at 900x1200px with DM Sans font, dark gradients, single accent color per deck
- Playwright converts HTML to PNG screenshots for iMessage sending
- Add new tile types in `renderer.py:_tile_inner_html()`, new deck types in `prompts.py`
- After adding Playwright: `playwright install chromium`

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
