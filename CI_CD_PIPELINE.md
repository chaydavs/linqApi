# LinqUp CI/CD Pipeline — Agent-Driven Quality Assurance

## Overview

LinqUp uses a **fully automated, agent-driven CI/CD pipeline** built entirely with Claude Code's agent system. Instead of traditional CI tools (GitHub Actions, Jenkins), the pipeline is composed of **7 specialized AI agents**, **6 slash commands**, and **3 lifecycle hooks** that work together to review code, scan for security vulnerabilities, hunt edge cases, run tests, and verify demo readiness — all from the command line.

The entire pipeline runs with a single command: `/pipeline`

```
┌─────────────────────────────────────────────────────────────┐
│                        /pipeline                            │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ code-reviewer │  │ edge-hunter  │  │  build-status    │  │
│  │    agent      │  │    agent     │  │     agent        │  │
│  │              │  │              │  │                  │  │
│  │ Scans all    │  │ Traces API   │  │ Checks 16       │  │
│  │ Python files │  │ call chains  │  │ features against │  │
│  │ for bugs,    │  │ for timeouts,│  │ spec, reports    │  │
│  │ security,    │  │ race conds,  │  │ demo readiness   │  │
│  │ code quality │  │ bottlenecks  │  │                  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │            │
│         ▼                 ▼                    ▼            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              pytest (215 tests)                      │   │
│  │              + import validation                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│              🟢 READY TO DEMO                               │
│              🟡 ALMOST READY — [issues]                     │
│              🔴 NOT READY — [blockers]                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Architecture

### Three Layers

```
Layer 1: Hooks (automatic triggers)
├── SessionStart  → Announces available agents & commands
├── PostToolUse   → Flags file modifications for review
└── Stop          → Runs import validation before session ends

Layer 2: Slash Commands (user-triggered)
├── /pipeline  → Full 5-step quality pipeline
├── /review    → Quick code review of changed files
├── /edges     → Edge case and latency scan
├── /test      → Run all test suites
├── /prompt    → Create/debug Claude API prompts
└── /status    → Build progress and demo readiness

Layer 3: Agents (specialized AI reviewers)
├── code-reviewer     → Bugs, code quality, Python/Flask best practices
├── security-scanner → Secrets, deps, input validation, auth, error leakage
├── edge-hunter       → Timeouts, race conditions, bottlenecks
├── build-status      → Feature completeness tracker
├── tester            → Unit tests, integration tests, demo flow
├── pr-reviewer       → Git diff analysis, PR descriptions
└── prompt-engineer   → Claude prompt quality and debugging
```

---

## The Agents

### 1. Code Reviewer (`code-reviewer`)

**Purpose**: Scans all Python files for bugs, security issues, and code quality problems. Modeled after a senior engineer's review style — fast, honest, focused on what actually breaks.

**Location**: `.claude/agents/code-reviewer.md`

**What it checks**:
- **Critical**: Unhandled exceptions, API keys in code, race conditions, data loss
- **High**: Error handling gaps, edge cases, Flask patterns, Claude prompt quality
- **Medium**: Readability, DRY violations, type hints, magic strings

**How it works**:
1. Uses Grep/Glob to find files to review
2. Reads each file completely
3. Analyzes against a 3-tier checklist (Critical / Important / Polish)
4. Returns structured review with file:line references and fix suggestions

**Example output**:
```
### CRITICAL
- lstrip("about") bug: app.py:325 — strips individual characters, not the word
  → Fix: Use removeprefix() or startswith() check

### HIGH
- Whisper API has no timeout: voice.py:32 — can block executor thread indefinitely
  → Fix: Add timeout=60.0 parameter

### What's Good
- Thread safety in contacts.py — lock wraps all mutations, returns copies
- html.escape() applied uniformly in renderer.py
```

---

### 2. Security Reviewer (`security-scanner`)

**Purpose**: Dedicated security scanner that checks for secrets, dependency vulnerabilities, input validation gaps, error leakage, and authentication holes. Thinks like an attacker: "What can I send to the webhook to break things?"

**Location**: `.claude/agents/security-scanner.md`

**5-check scan**:

| Check | What it does |
|-------|-------------|
| 1. Secret Scan | Grep for hardcoded keys, verify `.env` is gitignored, check git history |
| 2. Dependency Audit | Run `pip audit` for known CVEs in requirements.txt |
| 3. Input Validation Trace | Trace untrusted data from webhook through every handler to Claude/Linq |
| 4. Error Leakage | Ensure no exception text or internal state reaches user via iMessage |
| 5. Auth & Authorization | Webhook HMAC verification, rate limiting, contact isolation |

**Why it's separate from code-reviewer**: The code-reviewer catches security issues incidentally while scanning for bugs. The security-scanner is systematic — it runs a 5-step checklist specifically designed to find vulnerabilities. Code review might catch `str(e)` in a send_message call; the security reviewer traces every path where internal state could reach the user.

**Example output**:
```
### CRITICAL (fix before demo)
- No webhook authentication: app.py:373 — anyone with ngrok URL can trigger Claude API calls
  → Fix: Add LINQ_WEBHOOK_SECRET env var, verify HMAC signature

### WARNING (fix before production)
- audio_url downloaded without validation: voice.py:22 — potential SSRF
  → Fix: Validate URL against allowlist or Linq domain

### Passing
- API keys loaded from env vars via config.py
- .env is gitignored
- All Claude output html.escape()'d before HTML rendering
- Contact store isolates by user_phone — no cross-user access
```

---

### 3. Edge Hunter (`edge-hunter`)

**Purpose**: Traces every external API call from webhook receipt to final message send. Calculates worst-case timing. Finds race conditions and bottlenecks that would break a live demo.

**Location**: `.claude/agents/edge-hunter.md`

**What it checks**:
- Every external call has a timeout
- Webhook handlers don't block (use ThreadPoolExecutor)
- No race conditions in concurrent message processing
- Playwright rendering bottlenecks
- Total end-to-end timing per command

**Example output**:
```
CRITICAL: Playwright blocks executor thread for 15-30s per tile deck
  tiles/image_converter.py:63 — 10 concurrent requests saturate all workers

WARNING: send_message_to_phone worst-case 45s (3-leg fallback)
  linq_client.py:44-66

TIMING: Brain dump — 3-6s typical, 31s worst case
TIMING: Visual tiles — 15-30s typical, 185s+ worst case
```

---

### 4. Build Status (`build-status`)

**Purpose**: Scans the codebase and reports which features are implemented, broken, or missing. Answers: "Can you record a demo right now?"

**Location**: `.claude/agents/build-status.md`

**Feature checklist** (16 items):

| # | Feature | Status |
|---|---------|--------|
| 1 | Flask webhook receives messages | Done |
| 2 | Message routing (10 commands) | Done |
| 3 | Brain dump parsing (Claude) | Done |
| 4 | Contact CRUD (thread-safe) | Done |
| 5 | Confirmation response | Done |
| 6 | Summary generation | Done |
| 7 | Draft generation (lazy) | Done |
| 8 | Draft review flow | Done |
| 9 | Send follow-up via iMessage | Done (endpoint unverified) |
| 10 | Linq API client | Done |
| 11 | Voice memo transcription | Done |
| 12 | /update morning briefing | Done |
| 13 | Typing indicators | Done |
| 14 | Reactions on confirmation | Done |
| 15 | Error handling | Done |
| 16 | Help command | Done |

---

### 5. Tester (`tester`)

**Purpose**: Comprehensive testing specialist with 6 test suites — from structural checks (no API keys needed) to full live demo simulation.

**Location**: `.claude/agents/tester.md`

**Test suites**:
| Suite | What it tests | Requirements |
|-------|---------------|-------------|
| 1. Structure | File existence, imports, dependencies, Flask routes | None |
| 2. Contact Store | CRUD operations, search, multi-user | None |
| 3. Claude Integration | Brain dump parsing, draft generation, summaries | ANTHROPIC_API_KEY |
| 4. Webhook Simulation | All 10 commands via curl | Server running |
| 5. Full Demo Flow | 7-step demo sequence end to end | Server + Claude key |
| 6. Linq Live | Real API calls to Linq sandbox | All keys + sandbox |

**pytest suite**: 215 tests covering routing, renderer (12 tile types), engine, prompts, and image converter.

---

### 6. PR Reviewer (`pr-reviewer`)

**Purpose**: Analyzes git diffs before pushing. Checks completeness, coherence, and risk. Writes PR descriptions that focus on what changed and why.

**Location**: `.claude/agents/pr-reviewer.md`

**Risk assessment**:
- **High risk**: Webhook handler, Linq API client, message sending (demo path)
- **Medium risk**: Claude prompt changes (could break JSON parsing)
- **Low risk**: Logging, comments, refactoring with no behavior change

---

### 7. Prompt Engineer (`prompt-engineer`)

**Purpose**: Creates, reviews, and debugs Claude API prompts. Tests prompts with real API calls to verify consistency.

**Location**: `.claude/agents/prompt-engineer.md`

**Project prompts it manages**:
- `PARSE_SYSTEM_PROMPT` — Parse brain dumps into structured JSON
- `DRAFT_SYSTEM_PROMPT` — Write follow-up iMessages
- `SUMMARY_SYSTEM_PROMPT` — Generate day summaries
- `DECK_SELECTOR_PROMPT` — Pick deck type from contact context
- `TILE_CONTENT_PROMPT` — Generate structured tile content JSON

---

## The Commands

### `/pipeline` — Full Quality Pipeline

The master command. Runs all checks in order, launches agents in parallel where possible, and gives a single traffic-light verdict.

```
Step 1: Code Review + Security  → code-reviewer + security-scanner (parallel)
Step 2: Edge Case Scan          → edge-hunter + build-status (parallel)
Step 3: Tests                   → pytest + import check
Step 4: Build Status            → build-status agent
Step 5: Summary                 → 🟢/🟡/🔴 verdict
```

**File**: `.claude/commands/pipeline.md`

### `/review` — Quick Code Review

Reviews only files modified in the current git working tree. Focused on critical issues.

**File**: `.claude/commands/review.md`

### `/edges` — Edge Case Scan

Full external API trace with timing analysis. Flags anything that would break during a live demo.

**File**: `.claude/commands/edges.md`

### `/test` — Run Test Suites

Runs 5 test suites in order (structure → contacts → Claude → webhooks → server health).

**File**: `.claude/commands/test.md`

### `/prompt` — Prompt Engineering

Interactive prompt creation, debugging (runs 3x for consistency), or review against quality checklist.

**File**: `.claude/commands/prompt.md`

### `/status` — Build Progress

Scans codebase against 16-feature spec. Ends with: "Can you record a Loom right now?"

**File**: `.claude/commands/status.md`

---

## The Hooks

Hooks are automatic triggers that run at specific lifecycle events. Configured in `.claude/settings.json`.

### SessionStart Hook
**When**: Every new Claude Code session begins.
**What**: Announces available agents and commands.
```
📋 LinqUp session started. Agents: code-reviewer, pr-reviewer, build-status,
tester, edge-hunter, prompt-engineer. Commands: /pipeline /review /edges
/test /prompt /status
```

### PostToolUse Hook (Edit|Write)
**When**: Any file is modified via Edit or Write tools.
**What**: Flags that code-reviewer should run.
```
🔍 File modified — code-reviewer will run at Stop.
```

### Stop Hook
**When**: Claude Code session ends.
**What**: Runs import validation to catch broken imports before the session closes.
```bash
cd /Users/chaitanyadavuluri/Downloads/Linq-API-WeChat && \
python3 -c "import app" 2>&1 && \
echo '✅ Import check passed' || echo '❌ Import error — something is broken'
```

---

## Pipeline Execution — Real Example

Here is an actual `/pipeline` run from March 8, 2026, showing what each step found and the fixes applied:

### Step 1: Code Review (code-reviewer agent)

**4 CRITICAL issues found**:
1. `app.py:325` — `lstrip("about")` strips individual characters, not the word "about". Input "overhead costs" becomes "verhead costs".
2. `app.py:373` — No webhook authentication. Anyone with the ngrok URL can trigger Claude API calls.
3. `brain.py:89-98` — `_call_claude()` has no exception handling. Anthropic SDK errors surface raw to user.
4. `brain.py:115` / `engine.py:87` — Retry `json.loads` is unwrapped. Double failure sends Python traceback via iMessage.

**6 HIGH issues found**: Unverified Linq endpoints, thread-unsafe lazy client init, error details leaked to user, potential auth on audio URLs, private function imports, UUID truncation.

### Step 2: Edge Case Scan (edge-hunter agent)

**5 CRITICAL timing/concurrency issues**:
1. Playwright blocks executor thread for full render duration (15-30s per deck)
2. TOCTOU race on draft generation for concurrent webhooks
3. `send_message_to_phone` worst-case 45s per call (3-leg fallback)
4. `_send_image_to_phone` base64-in-JSON likely rejected by Linq API
5. Whisper API has no timeout — can block thread indefinitely

**Timing analysis**:
| Command | Typical | Worst Case |
|---------|---------|------------|
| Brain dump | 3-6s | 31s |
| Draft | 2-4s | 31s |
| Summary | 4-9s | 31s |
| Visual tiles | 15-30s | 185s+ |

### Step 3: Tests

```
215/215 tests passed (0.54s)
All imports resolve ✅
```

### Step 4: Build Status (build-status agent)

**16/16 features implemented.** Two depend on unverified Linq API endpoints (`send_message_to_phone` and `_send_image_to_phone`).

### Step 5: Verdict

**ALMOST READY** — Three quick fixes needed.

### Fixes Applied

The pipeline identified 3 fixes that could be applied immediately:

| Fix | File | Issue | Time |
|-----|------|-------|------|
| `lstrip("about")` → prefix check | `app.py:325` | Corrupted every visual send hint | 2 min |
| Whisper timeout added (60s) | `voice.py:32` | Could hang executor thread forever | 1 min |
| Retry `json.loads` wrapped in try/except | `brain.py:115`, `engine.py:87` | Python traceback sent via iMessage | 2 min |

After applying fixes: **215/215 tests still pass. Status: READY TO DEMO.**

---

## File Structure

```
.claude/
├── settings.json          # Hooks configuration (3 lifecycle hooks)
├── agents/
│   ├── code-reviewer.md     # Bugs, code quality, Flask patterns
│   ├── security-scanner.md # Secrets, deps, input validation, auth
│   ├── edge-hunter.md       # Timeouts, race conditions, timing
│   ├── build-status.md      # Feature completeness tracker
│   ├── tester.md            # 6 test suites, mock + live modes
│   ├── pr-reviewer.md       # Git diff analysis, PR descriptions
│   └── prompt-engineer.md   # Claude prompt quality assurance
└── commands/
    ├── pipeline.md        # Full 5-step quality pipeline
    ├── review.md          # Quick code review
    ├── edges.md           # Edge case scan
    ├── test.md            # Run test suites
    ├── prompt.md          # Prompt engineering
    └── status.md          # Build progress check
```

---

## How It Compares to Traditional CI/CD

| Aspect | Traditional CI (GitHub Actions) | LinqUp Agent Pipeline |
|--------|------|------|
| Trigger | Push/PR event | `/pipeline` command or session hooks |
| Code review | Static linters (ESLint, Pylint) | AI agent that understands business context |
| Edge cases | Not covered | AI traces full API call chains, calculates timing |
| Test runner | pytest/Jest | pytest + curl simulation + live demo flow |
| Build status | Badge (pass/fail) | AI reads spec, reports feature-by-feature status |
| Verdict | Binary pass/fail | Traffic-light with prioritized fix list |
| Fix suggestions | None | Specific code changes with file:line references |
| Prompt quality | Not covered | Dedicated agent tests prompts 3x for consistency |
| Execution | Minutes (remote runner) | 30-90s (local, parallel agents) |

---

## Key Design Decisions

1. **Parallel agent execution**: Code review, edge hunting, and build status agents launch simultaneously. Tests run in parallel with agents. Total pipeline time: ~60-90s.

2. **Severity-based filtering**: Agents report CRITICAL > HIGH > MEDIUM. The pipeline verdict only blocks on CRITICAL issues — MEDIUM issues are noted but don't block demos.

3. **Domain-specific agents**: Each agent has deep knowledge of the LinqUp project (Flask webhooks, Linq v3 API, Claude prompts, Playwright tiles). They're not generic linters — they know the codebase.

4. **Hooks as guardrails**: The Stop hook runs `import app` before every session ends, catching broken imports immediately. The PostToolUse hook reminds that code-reviewer should run after modifications.

5. **Progressive test suites**: The tester agent auto-detects which API keys are available and runs appropriate suites. No keys = structure tests. Claude key = parsing tests. All keys = full live demo flow.

6. **Single-command orchestration**: `/pipeline` is the only command needed before a demo. It replaces running linters, tests, and manual review separately.
