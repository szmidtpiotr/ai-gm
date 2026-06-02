---
name: ai-gm-tdd
description: >-
  Test-driven development for the AI-GM backend (pytest, red-green-refactor, in-memory
  SQLite fixtures, LLM mocks). Use when adding or fixing backend logic, writing unit tests,
  or when the user asks for TDD, test coverage, or "tests first".
---

# AI-GM — test-driven development (backend)

Human-readable setup: [`docs/GETTING_STARTED.md`](../../../docs/GETTING_STARTED.md). UX E2E: `./scripts/test_e2e.sh`.

## Run tests (no SSH)

| Command | Environment |
|---------|-------------|
| `./scripts/test_local.sh [args]` | Local venv in `backend/.venv` — **use this by default** |
| `./scripts/test_dev.sh [args]` | Docker container `ai-gm-dev-backend-1` (local compose or friend's server) |
| `./scripts/verify_testing_setup.sh` | Smoke-check scripts + 76 tests in venv + container |

Path args: `tests/foo.py` or `backend/tests/foo.py` (both work; rewritten for cwd).

**Inside Docker**, tests are at `tests/` (WORKDIR `/app`), **not** `backend/tests/`.

```bash
./scripts/test_local.sh tests/test_gm_plan_schema.py -v
./scripts/test_dev.sh tests/test_economy_service.py -q
```

Do **not** `pytest backend/tests/...` from repo root without `cd backend` — `ModuleNotFoundError: No module named 'app'`.

## When to use vs other skills

| Goal | Tool |
|------|------|
| Unit tests, TDD, bug repro in pytest | **This skill** |
| Deploy dev stack | `ai-gm-dev-deploy` |
| Play 3–6 live turns on deployed DEV | `game-test` |

Mock LLM/HTTP — never call Ollama in unit tests.

## Red → green → refactor

1. Failing test in `backend/tests/test_<area>.py`
2. Minimal change in `backend/app/`
3. `./scripts/test_local.sh tests/test_<area>.py -v`
4. Refactor; keep green

## Conventions

- In-memory SQLite fixtures (`test_economy_service.py`)
- Legacy `unittest.TestCase` in older phase-8 files — match the file you edit
- `@patch` for external I/O
- Locked mechanics: fix code, not DC/dice assertions, without human approval

## Reliable smoke subset (verified in Docker + local venv)

```bash
./scripts/test_local.sh \
  tests/test_gm_plan_schema.py \
  tests/test_economy_service.py \
  tests/test_game_engine_death.py \
  tests/test_dice_resolve_test_name.py -q
```

Full `tests/` in Docker may hit DB-migration/integration failures; TDD on one file at a time.

## Human docs

[`docs/TESTING.md`](../../../docs/TESTING.md)
