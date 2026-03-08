---
description: Run the full LinqUp quality pipeline — code review, edge cases, tests, build status
---

Run these checks IN ORDER, reporting results for each:

## Step 1: Code Review
Use the code-reviewer agent to scan all Python files (app.py, brain.py, contacts.py, linq_client.py, voice.py, and any files in tiles/). Focus on critical and important issues only.

## Step 2: Edge Case Scan
Use the edge-hunter agent to trace every external API call and check for:
- Missing timeouts
- Webhook handler blocking (not using background threads)
- Race conditions with concurrent messages
- Image rendering bottlenecks (if tiles/ exists)
- Total timing from trigger to message sent

## Step 3: Tests
Run the pytest suite:
```bash
python -m pytest tests/ -v --tb=short
```

Also run the import check:
```bash
python3 -c "import app" 2>&1 && echo "✅ All imports resolve" || echo "❌ Import error"
```

## Step 4: Build Status
Use the build-status agent to check which LinqUp features are implemented and working.

## Step 5: Summary
Give me a single verdict:
- 🟢 READY TO DEMO — all critical checks pass
- 🟡 ALMOST READY — minor issues, list them
- 🔴 NOT READY — critical blockers, list them and tell me which one to fix first
