# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Remote-Only Execution (CRITICAL)

This workspace is an **NFS mount** of `192.168.1.61:/home/piotrszmidt`. The local machine is an editor client only.

- **Never** run `docker compose`, `docker build`, `pytest`, dev servers, or rebuilds locally for this project.
- All runtime commands run via SSH on `claude@192.168.1.61` (DEV) or `192.168.1.63` (PROD).
- Repo path on DEV server: `/home/piotrszmidt/ai-gm`.
- Verify dev changes at `https://aigm-dev.studio-colorbox.com/`.
- Default to the DEV stack (`ai-gm-dev-*` containers); never touch PROD containers (`ai-gm-backend-1`, `ai-gm-frontend-1`) without explicit user request.

## Environment Roles & Branch Flow

- **DEV host** `192.168.1.61` — runs `docker-compose.dev.yml` (containers `ai-gm-dev-backend-1`, `ai-gm-dev-frontend-1`, `ai-gm-dev-test-agent-1`). Branch: `develop`. Ports: frontend `:3002`, backend `:8100`, test-agent `:4000`, voice `:8302`.
- **PROD host** `192.168.1.63` — runs `docker-compose.yml`. Branch: `main`. Ports: frontend `:3001`, backend `:8000`, voice `:8300`. Observability stack lives here.
- Promotion: finish on DEV → merge `develop` → `main` → SSH to `.63` → run `./scripts/deploy_prod.sh`. Use `./scripts/deploy_dev.sh` on `.61` for DEV.

## Common Commands (run on the relevant remote host)

```bash
# DEV restart/rebuild (on .61)
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans
./scripts/deploy_dev.sh   # pulls develop, rebuilds, healthchecks :8100

# PROD deploy (on .63)
./scripts/deploy_prod.sh  # pulls main, rebuilds, healthchecks :8000

# Backend tests — run inside the dev backend container
docker exec ai-gm-dev-backend-1 pytest backend/tests/test_phase8_combat.py
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

- Entry point: `app/main.py` — wires FastAPI, runs `init_db()` + `run_raw_migrations()` + `run_app_sql_migrations()` + `run_admin_migrations()` + `hydrate_runtime_from_stored_preset()` in lifespan.
- Two router namespaces:
  - `app/api/` — gameplay surface: `auth`, `campaigns`, `characters`, `turns`, `combat`, `inventory`, `npcs`, `shop`, `mechanics`, `commands`, `campaign_*`, `client_logs`
  - `app/routers/` — admin/system: `admin`, `admin_cheat`, `admin_location`, `bg_images`, `debug`, `locations`, `session_location`, `settings`, `test_runner`, `smart_entry`, `ideas_workshop`, `workshops`
- Services (`app/services/`) hold all business logic — game engine, dice, combat, LLM, summaries, GM plan, locations, inventory, shop, XP, weapon rules, effect-JSON migrations.
- Migrations: `app/migrations_admin.py` (admin tables) + inline `RAW_MIGRATIONS` in `main.py` + `app/db/migrations/*.sql`. SQLite path inside container: `/data/ai_gm.db`.
- System prompt loaded from `backend/prompts/system_prompt.txt` — **mechanics contract, locked**.
- Logging: `app/core/logging.py` (structlog JSON), Prometheus instrumentation, request IDs in `X-Request-Id` response header.

### LLM Resolution (single source of truth)

Effective LLM config resolved in `app/services/llm_service.py`:
1. **Server default:** active admin preset / runtime override → fallback to `LLM_*` env vars.
2. **User custom:** `/api/users/{user_id}/llm-settings` with `mode="custom"` overrides server default.
3. **User default:** same endpoint with `mode="default"` falls through to server default.

Global provider/credentials edited from `Admin Panel → Accounts`. Player UI "Connect" persists profile config only — must not overwrite global runtime.

### Frontend — Two UIs

**Player UI** (`frontend/index.html` + `frontend/js/`): Login gate → gameplay. Standard RPG turn flow.

**Admin UI v2** (`frontend/admin_panel_v2/`) — the active admin interface at `/admin2/`:
- Entry: `index.html` — loads sidebar nav, mounts section modules dynamically
- Layout: `layout.css` — all shared styles
- Shared utilities: `shared/api.js` (adminFetch + APIError), `shared/toast.js`, `shared/modal.js`, `shared/table.js`, `shared/smart_entry.js`

**Admin Panel v2 sections** (each exports `async init(panel)`):

| Section key | File | Description |
|---|---|---|
| `dashboard` | `sections/dashboard.js` | Overview stats |
| `mechanics` | `sections/mechanics.js` | Stats, skills, DC, conditions |
| `content` | `sections/content.js` | Weapons, armor, items, consumables, loot tables + 🤖 Kreator AI |
| `world` | `sections/world.js` | Locations, NPCs, enemies, rules, pending review, world builder |
| `narrator` | `sections/narrator.js` | Narracja / system prompt tuning |
| `players` | `sections/players.js` | User accounts, LLM settings |
| `campaigns` | `sections/campaigns_hub.js` → `campaigns.js` | Campaign monitor + Warsztat tab |
| `analytics` | `sections/analytics.js` | Stats/usage charts |
| `workshops` | `sections/workshops.js` | Bank pomysłów (Ideas Bank) |
| `voice` | `sections/voice.js` | Piper TTS settings |
| `system` | `sections/system.js` | LLM presets, config export/import |

**Old Admin UI v1** (`frontend/admin_panel/`) — still accessible at `/admin/`. Being superseded by v2.

### Smart Entry (AI Kreator) — `shared/smart_entry.js` v4

Form-first AI record creator. Opens as overlay on any content tab.

- **Left pane**: chat — admin describes what they want; LLM fills form in one shot (JSON format)
- **Right pane**: real DB form — all fields rendered from `/api/admin/smart-entry/schema?table=X`
  - Dropdown at top: load existing record for editing (UPDATE mode) or "Nowy rekord" (INSERT)
  - Required fields marked `*`, label turns green when filled
  - "Zapisz rekord" enabled only when all required fields valid
- Supported tables: `game_config_weapons`, `game_config_items`, `game_config_consumables`, `game_config_enemies`
- After save: dispatches `CustomEvent("smart-entry-saved")` → content.js auto-refreshes the table
- Backend endpoints: `GET /schema`, `GET /list`, `GET /record`, `POST /message`, `POST /save`
- LLM prompt enforces JSON `{"reply":"...", "draft":{...}}` with schema-constrained valid enum values only; always generates `description` and `note` fields

**Note**: `note` (special abilities) is currently **informational text only** — displayed to GM but not parsed by the combat engine. Structured `effect_json` support is planned (see `to_do_ideas.md`).

### Campaign Monitor & Warsztat — `sections/campaigns.js`

Campaign modal has 4 tabs:
1. **Przegląd** — character stats, HP bar, conditions, last turn snippets
2. **Plan GM** — all arcs (not just active), full scene goals, hooks (NPCs/locations/items), roadmap — **read-only, does not affect player**. "Następna scena" button in the actions bar advances the GM plan scene pointer (affects AI narration of next turn).
3. **Tury** — last 10 turns
4. **🔧 Warsztat** — Campaign workshop: chat with LLM about the campaign, propose changes to `gm_plan_json`. Right panel shows "PROPONOWANE ZMIANY" cards with ✓ Zatwierdź buttons — each approval writes that field patch to DB. Raw JSON stripped from chat display.

### Bank pomysłów (Ideas Bank) — `sections/workshops.js`

Formerly "Warsztaty". Two-pane layout:
- **Left**: Warsztat Pomysłów chat — LLM asks clarifying questions, then generates a structured idea sketch (JSON). Save button appears when LLM signals `ready_to_save`. Saves to `campaign_ideas` table.
- **Bottom**: Bank Pomysłów grid — filterable by category and rating. Each card shows title + premise snippet, rating selector, delete button.

### Test Agent (`ai_test_agent/`, DEV only)

Playwright + Express on port 4000 used by admin Test Runner. `BASE_URL=http://frontend:80`.

### Scholar Magic System

Scholar archetype has `current_mana` / `max_mana` tracked in sheet JSON. Mana deducted on every `spell_attack` combat action.

- `game_config_spells` — 9 spells (tiers 1–5): magic_bolt, mend_wounds, arcane_shield, sleep, burning_arc, drain_life, chain_lightning, stone_skin, fireball
- `character_spells` — spells known per character + rank (1/2/3). Scholar starts with magic_bolt + mend_wounds R1
- `arcane_points` in `sheet_json` — earn 1/level, spend: 1pt = learn new spell, 1pt = R2, 2pt = R3
- Miscast (Nat 1): stun only (L1-2), 1d4 self-dmg (L3-4), 1d6+stun (L5-7), 1d8+stun+secondary (L8+)
- Nat 20 secondary (d6): double dmg / +stun / zone-change / burning condition

### Dungeon Runs

Standalone farmable dungeons separate from campaign story content.

- `game_dungeons` — dungeon seeds (enemy_pool, boss_enemy, rooms, loot_tier, cooldown_hours, atmosphere)
- `character_dungeon_runs` — per-character cooldown tracking (UNIQUE per character+dungeon)
- Entry: `POST /api/dungeons/{key}/enter` — checks cooldown (423 if blocked), generates scaled instance, stores in `session_flags.dungeon_run`
- Advance: `POST /api/dungeons/advance-room` — marks room cleared, moves to next, records completion on last room
- Enemy scaling: ×0.75–×2.0 by hero level; boss always one tier above regular enemies
- Admin: Świat → Lochy tab in admin panel v2

## Locked Game Mechanics (do not modify without explicit approval)

- **Stats (7):** STR, DEX, CON, INT, WIS, CHA, LCK
- **Roll formula:** `d20 + stat_modifier + skill_rank + proficiency_bonus ≥ DC`. Proficiency bonus +2 when `skill_rank ≥ 3`. Nat 20 = auto-success + double damage; Nat 1 = auto-fail + complication.
- **DC scale:** Easy 8 / Medium 12 / Hard 16 / Extreme 20 / Legendary 24+
- **HP:** archetype base + `CON_mod × level`. **Mana (Mage only):** `8 + INT_mod × level`.
- Source of truth: `backend/prompts/system_prompt.txt`. DB schema changes require a migration, never direct DB edits. Fix code, not test assertions.

## Database

- SQLite file: `data/ai_gm.db` on host (bind-mounted to `/data/ai_gm.db` in backend container). DEV compose maps `./data-dev` instead.
- Pre-import auto-backups on config import → `./backups/imports/`. Retention: 30 days, ≥3 older, capped at 10.
- Key tables: `game_config_weapons`, `game_config_items`, `game_config_consumables`, `game_config_enemies`, `game_config_skills`, `game_config_stats`, `campaign_ideas`, `campaign_turns`, `campaigns`, `characters`, `users`.

## Conventions

- Commit messages: include phase number when relevant. Polish or English fine.
- New endpoint: route in `backend/app/api/<module>.py` or `backend/app/routers/<module>.py` → register in `app/main.py`.
- DB change: write migration in `migrations_admin.py` → test on DB copy → update models if needed.
- Frontend change: edit under `frontend/` → verify in browser at `https://aigm-dev.studio-colorbox.com/` → check console.
- JS version strings in imports (`?v=N`) must be bumped when a shared module changes to bust browser cache.

## Reference Files

- Backend entry: `backend/app/main.py`
- LLM service: `backend/app/services/llm_service.py`
- Combat: `backend/app/services/combat_service.py`
- Scholar spell system: `backend/app/services/spell_service.py`
- Dungeon runs: `backend/app/services/dungeon_service.py`
- Smart Entry router: `backend/app/routers/smart_entry.py`
- Ideas Workshop router: `backend/app/routers/ideas_workshop.py`
- Admin migrations: `backend/app/migrations_admin.py`
- Admin Panel v2 entry: `frontend/admin_panel_v2/index.html`
- Smart Entry overlay: `frontend/admin_panel_v2/shared/smart_entry.js`
- Content section (weapons/items): `frontend/admin_panel_v2/sections/content.js`
- Campaign monitor: `frontend/admin_panel_v2/sections/campaigns.js`
- Ideas Bank: `frontend/admin_panel_v2/sections/workshops.js`
- All styles: `frontend/admin_panel_v2/layout.css`
- Player UI: `frontend/front/index.html`, `frontend/front/js/app.js`, `frontend/front/css/styles.css`
- Compose: `docker-compose.yml` (PROD), `docker-compose.dev.yml` (DEV)
- Planned work: `to_do_ideas.md`
