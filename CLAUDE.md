# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Remote-Only Execution (CRITICAL)

This workspace is an **NFS mount** of `192.168.1.61:/home/piotrszmidt`. The local machine is an editor client only.

- **Never** run `docker compose`, `docker build`, `pytest`, dev servers, or rebuilds locally for this project.
- All runtime commands run via SSH on `piotrszmidt@192.168.1.61` (DEV) or `192.168.1.63` (PROD).
- Repo path on DEV server: `/home/piotrszmidt/ai-gm`.
- Verify dev changes at `https://aigm-dev.studio-colorbox.com/`.
- Default to the DEV stack (`ai-gm-dev-*` containers); never touch PROD containers (`ai-gm-backend-1`, `ai-gm-frontend-1`) without explicit user request.

## Environment Roles & Branch Flow

- **DEV host** `192.168.1.61` — runs `docker-compose.dev.yml` (containers `ai-gm-dev-backend-1`, `ai-gm-dev-frontend-1`, `ai-gm-dev-test-agent-1`). Branch: `develop`. Ports: frontend `:3002`, backend `:8100`, test-agent `:4000`, voice `:8302`.
- **PROD host** `192.168.1.63` — runs `docker-compose.yml`. Branch: `main`. Ports: frontend `:3001`, backend `:8000`, voice `:8300`. Observability stack lives here.
- Promotion: finish on DEV → merge `develop` → `main` → SSH to `.63` → run `./scripts/deploy_prod.sh`. Use `./scripts/deploy_dev.sh` on `.61` for DEV. `scripts/promote_and_deploy_prod.sh` is legacy.

## Common Commands (run on the relevant remote host)

```bash
# DEV restart/rebuild (on .61)
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans
./scripts/deploy_dev.sh   # pulls develop, rebuilds, healthchecks :8100

# PROD deploy (on .63)
./scripts/deploy_prod.sh  # pulls main, rebuilds, healthchecks :8000

# Backend tests — run inside the dev backend container
docker exec ai-gm-dev-backend-1 pytest backend/tests/test_phase8_combat.py
docker exec ai-gm-dev-backend-1 python3 backend/tests/run_dice_full_wiring_checks.py
# Or pytest from repo root (uses pytest.ini, testpaths=backend/tests tests)
docker exec ai-gm-dev-backend-1 pytest -k <pattern>

# DB backup/restore (data/ is bind-mounted to /data inside container)
./scripts/backup.sh                                  # → ./backups/ai_gm_<ts>.db
./scripts/restore.sh ai_gm_20260420_143000.db        # auto-backs up current first

# Logs
docker compose -f docker-compose.dev.yml logs backend --tail=50
```

## Architecture

**Stack:** FastAPI + SQLite backend, static HTML/CSS/JS frontend served by Nginx, optional Piper-based voice service, optional Grafana/Loki observability. LLM providers: Ollama and OpenAI-compatible endpoints. Game narration is **Polish**; code/docs are English.

### Backend (`backend/app/`)

- Entry point: `app/main.py` — wires FastAPI, runs `init_db()` + `run_raw_migrations()` + `run_app_sql_migrations()` + `run_admin_migrations()` + `hydrate_runtime_from_stored_preset()` in lifespan. Includes routers from `app.api.*` (gameplay) and `app.routers.*` (admin/locations/settings/debug). When `AI_TEST_MODE=1`, mounts `debug_router` and `test_runner_router`.
- Two router namespaces — both live: `app/api/` (gameplay surface: `auth`, `campaigns`, `characters`, `turns`, `combat`, `inventory`, `npcs`, `shop`, `mechanics`, `commands`, `campaign_*`, `client_logs`) and `app/routers/` (admin/system: `admin`, `admin_cheat`, `admin_location`, `bg_images`, `debug`, `locations`, `session_location`, `settings`, `test_runner`).
- Services (`app/services/`) hold all business logic — game engine, dice, combat, LLM, summaries, GM plan, locations, inventory, shop, XP, weapon rules, effect-JSON migrations. Routers are thin and call services.
- Migrations: `app/migrations_admin.py` (admin tables) + inline `RAW_MIGRATIONS` list in `main.py` + `app/db/migrations/*.sql` files. SQLite path inside container is `/data/ai_gm.db` (DEV uses `/data/ai_gm_dev.db` per compose env, but routers using raw `sqlite3` hardcode `/data/ai_gm.db` — keep paths consistent).
- System prompt loaded via `app/system_prompt_loader.py` from `backend/prompts/system_prompt.txt` — this is the **mechanics contract** (locked).
- Logging: `app/core/logging.py` (structlog JSON), Prometheus instrumentation via `prometheus_fastapi_instrumentator`, request IDs propagated to logs and `X-Request-Id` response header.

### LLM Resolution (single source of truth)

Effective LLM config resolved in `app/services/llm_service.py`:
1. **Server default:** active admin preset / runtime override → fallback to `LLM_*` env vars (`LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TEMPERATURE`, `LLM_TOP_P`, `LLM_TOP_K`, `LLM_REPEAT_PENALTY`, `LLM_MAX_TOKENS`).
2. **User custom:** `/api/users/{user_id}/llm-settings` with `mode="custom"` overrides server default.
3. **User default:** same endpoint with `mode="default"` falls through to server default.

Global provider/credentials are edited from `Admin Panel → Accounts`, never the player frontend. Player UI's "Connect" only persists its profile mode/config — it must not overwrite the global runtime.

### Frontend (`frontend/`)

Static files served by Nginx (`frontend/nginx.conf` proxies `/api/*` to backend). Two UIs:
- Player: `frontend/index.html` + `frontend/js/{api,app,ui,events,state,actions,combat_*,inventory,shop,...}.js`. Login gate before gameplay.
- Admin: `frontend/admin.html` + `frontend/admin_panel/{index.html, sections/, shared/}` — token-protected, tabbed CRUD over `/api/admin/*` (stats, skills, dc, weapons, enemies, conditions, accounts, user LLM, locations, etc.). Lock guard via `locked_at` + `force=true`. Audit logs on writes. Config export/import with `dry_run` and version checks; `dry_run=false` snapshots DB to `./backups/imports/`.

### Test Agent (`ai_test_agent/`, DEV only)

Playwright + Express service on port 4000 used by the admin Test Runner. The dev backend `depends_on` test-agent healthcheck. `BASE_URL=http://frontend:80`, planner uses Ollama via `LLM_API_URL`. Scenarios under `ai_test_agent/scenarios/` are bind-mounted into both containers.

## Locked Game Mechanics (do not modify without explicit approval)

- **Stats (7):** STR, DEX, CON, INT, WIS, CHA, LCK
- **Roll formula:** `d20 + stat_modifier + skill_rank + proficiency_bonus ≥ DC`. Proficiency bonus +2 when `skill_rank ≥ 3`. Nat 20 = auto-success + double damage; Nat 1 = auto-fail + complication.
- **DC scale:** Easy 8 / Medium 12 / Hard 16 / Extreme 20 / Legendary 24+
- **HP:** archetype base + `CON_mod × level`. **Mana (Mage only):** `8 + INT_mod × level`.
- Source of truth: `backend/prompts/system_prompt.txt`. Database schema changes require a migration (in `migrations_admin.py` or `app/db/migrations/*.sql`), never direct DB edits. Fix code, not test assertions.

## Database

- SQLite file: `data/ai_gm.db` on host (bind-mounted to `/data/ai_gm.db` in backend container). DEV compose maps `./data-dev` instead.
- Pre-import auto-backups on `POST /api/admin/config/import` and `POST /api/admin/config/catalog-snapshot/import` (when `dry_run=false`) → `./backups/imports/`. Retention: 30 days, ≥3 older snapshots, capped at 10.

## Conventions

- Commit messages: include phase number when relevant, e.g. `phase-9b: ...`. Polish or English both fine in messages (existing log mixes).
- New endpoint: route in `backend/app/api/<module>.py` or `backend/app/routers/<module>.py` → register in `app/main.py` → add test in `backend/tests/test_<module>.py`.
- DB change: write migration → test on DB copy → update SQLModel models if needed → add schema-verifying test.
- Frontend change: edit HTML/CSS/JS under `frontend/` → verify in browser at `https://aigm-dev.studio-colorbox.com/` (DEV) → check console.

## Reference Files

- Backend entry: `backend/app/main.py`
- LLM service: `backend/app/services/llm_service.py`
- Combat: `backend/app/services/combat_service.py`
- Dice: `backend/app/services/dice.py`
- Game engine: `backend/app/services/game_engine.py`
- System prompt: `backend/prompts/system_prompt.txt`
- Admin migrations: `backend/app/migrations_admin.py`
- Frontend entry: `frontend/index.html`, admin: `frontend/admin.html` + `frontend/admin_panel/`
- Compose: `docker-compose.yml` (PROD), `docker-compose.dev.yml` (DEV)
