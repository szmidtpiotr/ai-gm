# Getting started — develop & test AI-GM locally

This guide is for **contributors working on their own machine** (laptop, normal git clone). You do **not** need SSH access to the project’s remote DEV server (`192.168.1.61`) to write code or run tests.

If you only edit files over NFS/sshfs from that server, prefer running tests **inside Docker on your machine** (see [Troubleshooting](#troubleshooting)) — some pytest files cannot write on read-only mounts.

---

## What you need installed

| Tool | Used for |
|------|----------|
| **Git** | Clone the repo |
| **Docker Desktop** (or Docker Engine + Compose) | E2E stack, optional dev backend, container pytest |
| **Python 3.12+** | Local pytest via `./scripts/test_local.sh` (script creates `backend/.venv`) |
| **Node.js 18+** | Playwright UX tests (`ai_test_agent/`) |

Optional: a browser to open `http://127.0.0.1:13002` while debugging E2E.

---

## First-time setup (about 10 minutes)

```bash
git clone https://github.com/szmidtpiotr/ai-gm.git
cd ai-gm

# 1) Check scripts + a small pytest smoke (local venv + Docker image)
./scripts/verify_testing_setup.sh

# 2) Playwright (first time only)
cd ai_test_agent
npm ci
npx playwright install chromium
cd ..

# 3) Full UX path (Docker E2E stack + browser tests, stub GM — no real LLM)
./scripts/test_e2e.sh
```

If step 3 ends with **`3 passed`**, your machine is ready.

Test login used by E2E (seeded automatically):

| Field | Value |
|-------|--------|
| Username | `ai_test_player` |
| Password | `demo` |
| Hero | `TestPlayer` |
| Campaign | `AI Test Campaign` |

---

## Commands you will use every day

Run these from the **repo root** (`ai-gm/`).

| Goal | Command |
|------|---------|
| “Is my tooling OK?” | `./scripts/verify_testing_setup.sh` |
| **TDD** — one test file | `./scripts/test_local.sh tests/test_whatever.py -v` |
| **TDD** — match name | `./scripts/test_local.sh tests/ -k "pattern" -v` |
| Same tests in Docker | `./scripts/test_dev.sh tests/test_whatever.py -v` |
| **UX** — login → game → GM reply | `./scripts/test_e2e.sh` |
| API only (before browser) | `BACKEND_URL=http://127.0.0.1:18100 ./scripts/e2e_preflight.sh` |

Paths work as `tests/foo.py` **or** `backend/tests/foo.py` — scripts rewrite paths for the container.

**Do not** run `pytest backend/tests/...` from the repo root without setup — imports will fail. Always use the scripts above.

---

## Recommended workflow (TDD + UX)

1. **Pick a task** (issue, bug, small feature).
2. **Write or extend a pytest** under `backend/tests/`.
3. **Red → green:**
   ```bash
   ./scripts/test_local.sh tests/test_your_feature.py -v
   ```
4. Implement in `backend/app/`.
5. If you touched **player UI** (`frontend/front/`), run UX tests:
   ```bash
   ./scripts/test_e2e.sh
   ```
6. Commit with a clear message; open a PR when ready.

Deeper reference: **[`docs/TESTING.md`](TESTING.md)** (test pyramid, Docker layout, known suite limits).

---

## How UX tests work (Playwright)

`./scripts/test_e2e.sh` does the following:

1. Starts an **isolated** stack (`docker-compose.e2e.yml`) on ports **18100** (API) and **13002** (UI), **unless** something is already listening on DEV ports **8100** / **3002**.
2. Seeds test user, hero, and campaign.
3. Runs **`scripts/e2e_preflight.sh`** — HTTP checks that must pass before the browser runs:
   - `GET /api/campaigns` (includes “AI Test Campaign”)
   - `GET /api/heroes?user_id=1` (includes “TestPlayer”)
   - `GET /api/campaigns/1/characters` (includes “TestPlayer”)
   - `GET /api/ui/texts`
4. Runs specs in `ai_test_agent/playwright/ux/`:
   - login + heroes hub
   - send a chat line → GM bubble ( **stub LLM**, deterministic text)
   - open character sheet on mobile layout

Stub LLM is enabled with `AI_TEST_STUB_LLM=1` — no Ollama required for E2E.

### Run one UX spec

```bash
cd ai_test_agent
BASE_URL=http://127.0.0.1:13002 \
BACKEND_URL=http://127.0.0.1:18100 \
AI_TEST_CONFIG_PATH=/absolute/path/to/ai-gm/data-dev/ai_test_config.json \
npx playwright test playwright/ux/02_game_turn.spec.js \
  --config=playwright/playwright.config.js
```

### See the browser (debug)

```bash
HEADED=1 ./scripts/test_e2e.sh
```

### After a failed E2E run

```bash
# HTML report
cd ai_test_agent && npx playwright show-report

# Trace for last failure
npx playwright show-trace playwright-results/<folder>/trace.zip
```

---

## Optional: run the full dev stack locally

For manual clicking in the browser (not required for tests):

```bash
cp env.test.example env.test    # enables AI_TEST_MODE + stub LLM on dev backend
docker compose -f docker-compose.dev.yml up -d --build
# UI: http://127.0.0.1:3002   API: http://127.0.0.1:8100
```

Then `./scripts/test_e2e.sh` will **reuse** that DEV stack instead of starting the isolated E2E compose.

`env.test` is gitignored — never commit secrets. See `env.test.example` for variables.

---

## If you change the database or player APIs

The isolated E2E database is created once per Docker volume from:

- `backend/sql/schema.sql`
- `backend/sql/002_turn_engine.sql`
- `backend/sql/004_campaign_turns.sql`
- `backend/sql/e2e_bootstrap.sql`

If you add a column/table that the **player UI** needs:

1. Add it to **`backend/sql/e2e_bootstrap.sql`** (or a new SQL file wired in `backend/scripts/e2e_entrypoint.sh`).
2. Add a check to **`scripts/e2e_preflight.sh`** if there is a simple GET that should prove it works.
3. Recreate the E2E volume and re-run:
   ```bash
   docker compose -f docker-compose.e2e.yml down -v
   ./scripts/test_e2e.sh
   ```

---

## Troubleshooting

### `verify_testing_setup.sh` fails on “local pytest”

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..
./scripts/verify_testing_setup.sh
```

### `Read-only file system` during pytest

The repo is on **NFS/sshfs**. Clone or copy to a local disk, or use Docker only:

```bash
./scripts/test_dev.sh tests/test_gm_plan_schema.py -v
```

### `e2e_preflight` fails with HTTP 500 on `/api/campaigns` or `/api/campaigns/1/characters`

E2E DB schema is incomplete. See [If you change the database](#if-you-change-the-database-or-player-apis) and run `down -v` to reset the volume.

### Playwright: `reset_test_env failed`

Backend must have `AI_TEST_MODE=1`. For the isolated stack this is set in `docker-compose.e2e.yml`. For dev compose, use `env.test` from `env.test.example`.

### Playwright: cannot find `ai_test_config.json`

After first successful seed:

```bash
mkdir -p data-dev
docker compose -f docker-compose.e2e.yml exec -T backend cat /data/ai_test_config.json > data-dev/ai_test_config.json
export AI_TEST_CONFIG_PATH="$(pwd)/data-dev/ai_test_config.json"
```

`test_e2e.sh` sets this path by default.

### Full pytest suite is not all green

Expected today: use **targeted** files for TDD. The full suite expects a fully migrated production-like DB. See [`docs/TESTING.md`](TESTING.md#known-limitations-verified-2026-06-02).

---

## Game rules you must not change casually

Mechanics are locked in `backend/prompts/system_prompt.txt` (stats, DC scale, roll formula).  
**Fix code to match tests and the prompt** — do not weaken tests to make broken mechanics pass without team agreement.

---

## Cursor / Claude helpers (optional)

| File | Purpose |
|------|---------|
| `.cursor/skills/ai-gm-tdd/SKILL.md` | TDD conventions for agents |
| `.claude/skills/game-test/SKILL.md` | Live playtest on a deployed DEV server (not unit tests) |
| `docs/TESTING.md` | Full testing reference |

---

## Remote DEV server (owners only)

The repo maintainers also deploy to `192.168.1.61` (DEV) and `192.168.1.63` (PROD). That flow is in the root **`README.md`** and **`CLAUDE.md`**. Contributors on a normal clone can ignore SSH unless asked to verify on https://aigm-dev.studio-colorbox.com/

---

## Quick checklist before you push

- [ ] `./scripts/test_local.sh tests/<files you touched>.py -v` — green
- [ ] If UI changed: `./scripts/test_e2e.sh` — **3 passed**
- [ ] No secrets in the commit (`.env`, `env.test`, API keys)
