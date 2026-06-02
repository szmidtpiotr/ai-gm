---
name: ai-gm-tdd
description: >-
  Test-driven development for the AI-GM backend. Use for pytest, red-green-refactor,
  writing unit tests, or when the user asks for TDD. Run ./scripts/test_local.sh locally
  or ./scripts/test_dev.sh in Docker — no SSH required.
---

# AI-GM TDD

Full instructions: `.cursor/skills/ai-gm-tdd/SKILL.md`

```bash
./scripts/verify_testing_setup.sh
./scripts/test_local.sh tests/test_gm_plan_schema.py -v
```

Inside Docker use `tests/…` paths (not `backend/tests/…`).
