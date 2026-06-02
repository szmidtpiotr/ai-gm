# Testing & TDD — AI-GM

## Two ways to run tests (no SSH)

| Script | When |
|--------|------|
| `./scripts/test_local.sh` | **Default for contributors** — Python venv in `backend/.venv`, your machine |
| `./scripts/test_dev.sh` | Same tests inside Docker (`ai-gm-dev-backend-1` or local compose) |

Both accept paths as `tests/foo.py` **or** `backend/tests/foo.py` (rewritten automatically).

Verify the setup end-to-end:

```bash
./scripts/verify_testing_setup.sh
```

## Local workflow (recommended)

```bash
cd /path/to/ai-gm
./scripts/verify_testing_setup.sh    # once, after clone
./scripts/test_local.sh tests/test_gm_plan_schema.py -v
```

TDD loop:

1. Add/change test under `backend/tests/`.
2. `./scripts/test_local.sh tests/test_your_file.py -v`
3. Implement under `backend/app/`.
4. Re-run until green.

**Important:** run pytest from the `backend/` package root (the scripts do this for you).  
Do **not** run `pytest backend/tests/...` from the repo root without `PYTHONPATH` — imports like `from app.services...` will fail.

## Docker workflow (matches the game server container)

The backend image copies only `backend/` → `/app`. Tests inside the container are **`/app/tests/`**, not `backend/tests/`.

```bash
docker compose -f docker-compose.dev.yml up -d --build backend
./scripts/test_dev.sh tests/test_economy_service.py -v
```

Or build and run without compose:

```bash
docker build -t ai-gm-backend-test backend/
docker run --rm ai-gm-backend-test python3 -m pytest tests/test_gm_plan_schema.py -q
```

## Layout

| Path on disk | Path in container | Notes |
|--------------|-------------------|--------|
| `backend/tests/` | `tests/` | Primary suite (~900+ tests) |
| `tests/` (repo root) | *not in image* | Extra tests; use `test_local.sh` from repo with root `pytest.ini` if needed |
| `backend/pytest.ini` | used in container | `testpaths = tests` |
| `pytest.ini` (repo root) | editor / full repo | `testpaths = backend/tests tests` |

## Writing tests

In-memory SQLite + mocks (no live LLM):

```python
import sqlite3
import pytest
from app.services.my_service import my_function

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("CREATE TABLE characters (id INTEGER PRIMARY KEY);")
    yield conn
    conn.close()
```

Locked mechanics: fix code to match `backend/prompts/system_prompt.txt`, not tests, unless the team agrees to change the rules.

## Known limitations (verified 2026-06-02)

- **NFS / read-only mount:** some tests error with `OSError: [Errno 30] Read-only file system` when the repo is on sshfs/NFS. Use a normal local disk or Docker.
- **Full suite in Docker:** ~730 passed, many failures/errors on tests that expect a migrated `ai_gm.db` or HTTP integration DB — use targeted files for TDD.
- **`tests/test_phase8_smart_entry.py`:** collection error (`_infer_table` import) — test drift vs router; fix separately.
- **Friend's remote DEV host** (`192.168.1.61`): optional; same `test_dev.sh` when their container is running — not required for your local TDD.

## Agent skills

- `.cursor/skills/ai-gm-tdd/SKILL.md` — TDD conventions
- `.claude/skills/game-test/` — live playtest on DEV (not unit tests)
