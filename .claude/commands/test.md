---
description: Run LinqUp test suites
---

Use the tester agent. Run these test suites in order:

## Suite 1: Unit Tests (always run)
```bash
python -m pytest tests/ -v --tb=short
```

## Suite 2: Import Check (always run)
```bash
python3 -c "import app" 2>&1 && echo "✅ All imports resolve" || echo "❌ Import error"
```

## Suite 3: Contact Store (always run)
```bash
python3 -c "
from contacts import create_contact, get_user_contacts, find_contact_by_name, update_contact
c = create_contact('+1111', {'name':'Test User','company':'TestCo','title':'CTO','phone':'+1222','email':'','notes':'test notes','follow_up_date':'Thursday','follow_up_action':'send deck','temperature':'hot','personal_details':['likes coffee']})
assert c['name'] == 'Test User'
assert c['temperature'] == 'hot'
u = update_contact(c['id'], draft='Hey Test!')
assert u['draft'] == 'Hey Test!'
found = find_contact_by_name('+1111', 'Test')
assert found is not None
print('✅ Contact store: create, update, find all work')
"
```

## Suite 4: Claude Integration (only if ANTHROPIC_API_KEY is set)
Test brain dump parsing and draft generation with real Claude API calls.

## Suite 5: Server Health (only if server is running)
```bash
curl -s http://localhost:3000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ Server healthy' if d.get('status')=='healthy' else '❌ Server unhealthy')" 2>/dev/null || echo "⏭️ Server not running — skipping"
```

Report results per suite with pass/fail counts.
