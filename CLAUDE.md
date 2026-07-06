# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Remote-Only Execution (CRITICAL)

This workspace is an **NFS mount** of `192.168.1.61:/home/piotrszmidt`. The local machine is an editor client only.

- **Never** run `docker compose`, `docker build`, `pytest`, dev servers, or rebuilds locally for this project.
- All runtime commands run via SSH on `claude@192.168.1.61` (DEV) or `192.168.1.62` (PROD).
- Repo path on DEV server: `/home/piotrszmidt/ai-gm`.
- Verify dev changes at `https://aigm-dev.studio-colorbox.com/`.
- Default to the DEV stack (`ai-gm-dev-*` containers); never touch PROD containers (`ai-gm-backend-1`, `ai-gm-frontend-1`) without explicit user request.

## Environment Roles & Branch Flow

- **DEV host** `192.168.1.61` — runs `docker-compose.dev.yml` (containers `ai-gm-dev-backend-1`, `ai-gm-dev-frontend-1`, `ai-gm-dev-test-agent-1`). Branch: `develop`. Ports: frontend `:3002`, backend `:8100`, test-agent `:4000`, voice `:8302`.
- **PROD host** `192.168.1.62` (hostname `prog-ai-gm`) — runs `docker-compose.yml` (containers `ai-gm-backend-1`, `ai-gm-frontend-1`). Branch: `main`. Ports: frontend `:3001`, backend `:8000`, voice `:8300`. Observability stack lives here. (`.63` is dead — do not use.)
- Promotion: finish on DEV → merge `develop` → `main` → push `main` triggers GH Actions `deploy-production.yml` on the self-hosted runner (`.62`), which runs `./scripts/deploy_prod.sh` automatically. Use `./scripts/deploy_dev.sh` on `.61` for DEV.

## Common Commands (run on the relevant remote host)

```bash
# DEV restart/rebuild (on .61)
# IMPORTANT: backend code is baked into the image — docker compose restart alone does NOT
# pick up Python changes. Always use --build for backend code changes.
docker compose -f docker-compose.dev.yml up -d --build backend   # rebuild backend only (faster)
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans  # rebuild everything
./scripts/deploy_dev.sh   # pulls develop, rebuilds, healthchecks :8100

# PROD deploy (on .62) — normally auto-runs via GH Actions on push to main
./scripts/deploy_prod.sh  # pulls main, rebuilds, healthchecks :8000

# Backend tests — NOTE: inside the container tests live at /app/tests/, NOT backend/tests/
# Fast TDD iteration (docker cp avoids rebuild; use --build only in FAZA 4 deploy)
docker cp backend/tests/test_foo.py ai-gm-dev-backend-1:/app/tests/test_foo.py
docker cp backend/app/services/my_service.py ai-gm-dev-backend-1:/app/app/services/my_service.py
docker exec ai-gm-dev-backend-1 pytest tests/test_foo.py -v        # run single test file
docker exec ai-gm-dev-backend-1 pytest tests/ -k "pattern" -q      # run by keyword

# DO NOT run the full suite (pytest tests/) — ~8-9 min, many pre-existing failures.
# Piotr runs the full suite manually per phase. Target only the relevant file(s).

# DB backup/restore (data/ is bind-mounted to /data inside container)
./scripts/backup.sh                                  # → ./backups/ai_gm_<ts>.db
./scripts/restore.sh ai_gm_20260420_143000.db        # auto-backs up current first

# Logs
docker compose -f docker-compose.dev.yml logs backend --tail=50
```

### Test environment variables

`env.test` at repo root is auto-loaded by `app/bootstrap_env.py` on startup. Key vars:

| Var | Effect |
|---|---|
| `AI_TEST_MODE=1` | Enables seeded test user / campaign; seeds `ai_test_player` |
| `AI_TEST_STUB_LLM=1` | Disables live LLM calls — returns deterministic stub responses |

For E2E (Playwright) tests: `./scripts/test_e2e.sh` — starts isolated `docker-compose.e2e.yml` (ports 18100/13002), seeds test data, runs preflight checks, then Playwright suite under `ai_test_agent/playwright/ux/`.

Playwright specs in `ai_test_agent/playwright/` are **bind-mounted** (`:rw`) into the test-agent container — new spec files are live immediately without a rebuild, and auto-appear in `/admin/#tools → 🎭 Playwright`.

## Architecture

**Stack:** FastAPI + SQLite backend, static HTML/CSS/JS frontend served by Nginx, optional Piper-based voice service, optional Grafana/Loki observability. LLM providers: Ollama and OpenAI-compatible endpoints. Game narration is **Polish**; code/docs are English.

### Backend (`backend/app/`)

- Entry point: `app/main.py` — wires FastAPI, runs `init_db()` + `run_raw_migrations()` + `run_app_sql_migrations()` + `run_admin_migrations()` + `hydrate_runtime_from_stored_preset()` in lifespan.
- Two router namespaces:
  - `app/api/` — gameplay surface: `auth`, `campaigns`, `characters`, `turns`, `combat`, `inventory`, `npcs`, `shop`, `mechanics`, `commands`, `campaign_*`, `client_logs`, `multiplayer`, `party_chat`
  - `app/routers/` — admin/system: `admin`, `admin_cheat`, `admin_location`, `bg_images`, `debug`, `locations`, `session_location`, `settings`, `test_runner`, `smart_entry`, `ideas_workshop`, `workshops`
- Services (`app/services/`) hold all business logic — game engine, dice, combat, LLM, summaries, GM plan, locations, inventory, shop, XP, weapon rules, effect-JSON migrations.
- **Turn pipeline submodules** (`app/services/turn/`): the main turn handler delegates to five submodules — `commands.py` (special slash commands), `gambling.py` (dice mini-game), `gate.py` (pre-turn validation gates), `intent.py` (player intent classification), `skill_router.py` (skill check routing). These feed into `turns.py` in `app/api/`.
- Migrations: `app/migrations_admin.py` (admin tables) + inline `RAW_MIGRATIONS` in `main.py` + `app/db/migrations/*.sql`. SQLite path inside container: `/data/ai_gm.db`.
- System prompt loaded from `backend/prompts/system_prompt.txt` — **mechanics contract, locked**.
- Logging: `app/core/logging.py` (structlog JSON), Prometheus instrumentation, request IDs in `X-Request-Id` response header.
- `app/systems/` — multi-game-system stubs: `fantasy.py` is active; `cyberpunk.py` and `neuroshima.py` are non-functional stubs for a future system-switcher. Do not build on these stubs without explicit direction.

### LLM Resolution (single source of truth)

Effective LLM config resolved in `app/services/llm_service.py`:
1. **Server default:** active admin preset / runtime override → fallback to `LLM_*` env vars.
2. **User custom:** `/api/users/{user_id}/llm-settings` with `mode="custom"` overrides server default.
3. **User default:** same endpoint with `mode="default"` falls through to server default.

Global provider/credentials edited from `Admin Panel → Accounts`. Player UI "Connect" persists profile config only — must not overwrite global runtime.

### Frontend — Two UIs

**Player UI** (`frontend/front/index.html` + `frontend/front/js/`): Login gate → gameplay. Standard RPG turn flow.

**Modular Admin Shell** (`frontend/admin/`) — active admin interface at `/admin/`:
- Entry: `index.html` — loads sidebar nav, mounts section ES modules dynamically
- Login: native overlay (`doLogin`/`doLogout`) using `POST /api/admin/dev-login`; token stored in localStorage
- Shared utilities: `shared/api.js` (adminFetch + APIError), `shared/toast.js`, `shared/modal.js`

**Modular Admin sections** (each exports `async init(panel)`):

| Section key | File | Description |
|---|---|---|
| `overview` | `sections/overview.js` | Overview stats |
| `players` | `sections/players.js` | User accounts, LLM settings |
| `campaigns` | `sections/campaigns.js` | Campaign monitor + Warsztat tab |
| `content` | `sections/content.js` | Weapons, armor, items, consumables, loot tables + 🤖 Kreator AI |
| `world` | `sections/world.js` | Locations, NPCs, enemies, rules, pending review, world builder |
| `map` | `sections/map.js` | Mapa świata (hex grid) |
| `mechanics` | `sections/mechanics.js` | Stats, skills, DC, conditions |
| `dungeons` | `sections/dungeons.js` | Dungeon seeds + runs |
| `forge` | `sections/forge.js` | Kuźnia — asset forge / batch content builder |
| `invites` | `sections/invites.js` | Invite codes |
| `bugreports` | `sections/bugreports.js` | Bug report inbox |
| `push` | `sections/push.js` | Push notifications |
| `tools` | `sections/tools.js` | Test Runner (Playwright), DB tools |
| `system` | `sections/system.js` | LLM presets, config export/import |

**Legacy Admin (`frontend/admin_panel_v2/`)** — still operational at `/admin2/`; has sandbox, analytics, narrator, voice sections not yet ported to modular admin. Do not add new features here.

### MCP Server (`mcp_server/server.py`)

Custom MCP server (~86K) that exposes game state and actions as Claude tools. Runs alongside the backend and is used by Claude Code itself during development sessions. Provides tools for querying game events, rolling dice, submitting player turns, checking system health, and accessing campaign context. Not part of the player-facing product — it's a development/integration interface.

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

Campaign cards: delete (🗑) button on each card. Status filter (Aktywne/Zakończone/Wszystkie).

Campaign modal has 5 tabs:
1. **Przegląd** — character stats, HP bar, conditions, last turn snippets
2. **Plan GM** — all arcs (not just active), full scene goals, hooks (NPCs/locations/items), roadmap — **read-only, does not affect player**. "Następna scena" button in the actions bar advances the GM plan scene pointer (affects AI narration of next turn).
3. **Tury** — last 10 turns
4. **🗺 Mapa** — SVG hex grid of all world hexes with campaign overlay. Click any hex to edit: `discovered` (fog of war), `encounter_cleared`, `campaign_label`, `campaign_notes`. PATCH: `GET /api/admin/campaigns/{id}/hex-map`, `PATCH /api/admin/campaigns/{id}/hex-map/{q}/{r}`
5. **🔧 Warsztat** — Campaign workshop: chat with LLM about the campaign, propose changes to `gm_plan_json`. Right panel shows "PROPONOWANE ZMIANY" cards with ✓ Zatwierdź buttons — each approval writes that field patch to DB. Raw JSON stripped from chat display.

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
- Admin: Świat → Lochy tab in modular admin (`/admin/#dungeons`)

### Loot System

- `game_config_loot_tables` — loot table definitions (key, label, gold_min, gold_max)
- `game_config_loot_entries` — entries with 3-way XOR: exactly one of `item_key`, `consumable_key`, `weapon_key` must be set; `weight` (1–100 = % drop chance), `qty_min`/`qty_max`
- Every enemy has an auto-created `loot_{enemy_key}` table (on create or on approve-pending)
- Enemy has `loot_table_key` (FK) + `drop_chance` (float 0–1) columns
- Admin endpoints: `POST/DELETE /api/admin/loot-tables`, `POST /api/admin/loot-tables/{key}/entries` (upsert via `source_type`/`source_key`), `DELETE /api/admin/loot-tables/{key}/entries/by-id/{id}`
- Frontend: Zawartość → Tabele łupów — inline edit (click weight/min/max), type badges (item/consumable/weapon), delete by ID
- `loot_service.py`: `get_loot_table()`, `roll_loot()`, `grant_loot_to_character()`, `roll_gold_drop()`

### Hero-First Model (Character First Flow)

- Heroes (`characters` table) are independent entities with `status` (`idle`/`active`) and optional `campaign_id`
- Deleting a campaign sets `characters.campaign_id = NULL, status = 'idle'` — hero is freed, NOT deleted
- `handleNewCampaignWithHero()` always reassigns the hero (no stale campaign_id check)
- `selectCampaign()` auto-assigns the current hero to any campaign it's not already in

### Combat Sandbox (admin testing harness)

Admin-only feature at `/admin2/` → ⚔ Sandbox. Reuses the production combat engine — anything verified there matches real gameplay behavior. Use it to test combat mechanics without playing through narrative.

- Router: `backend/app/routers/sandbox.py` at `/api/admin/sandbox/*`
  - `GET /heroes`, `GET /enemies`, `GET /character/{id}`
  - `POST /setup` — creates a disposable clone of the chosen hero (name `[SBX] <orig>`, sheet tagged `__sandbox_clone__=true`). Inventory + spells cloned via `character_inventory` / `character_spells` copy. **Original hero never touched**, even if the clone dies in sandbox combat. Prior clones purged on each setup.
  - `POST /start-combat`, `POST /reset-hero`, `POST /end-combat`, `POST /advance-turn`
- Frontend section: `frontend/admin_panel_v2/sections/sandbox.js`
  - 3-column layout: Setup + Character Sheet card / Live combat state + actions / Log + Kopiuj raport
  - Auto-processes enemy turns (750 ms delay); manual override button retained
  - Combat events feed mirrors player UI roll cards, filtered to active combat_id only
  - 📋 Kopiuj raport — bundles hero + inventory + spells + combat state + events + log into clipboard markdown for bug reports
- Heroes are filtered out of the picker via `name NOT LIKE '[SBX] %' AND sheet_json.__sandbox_clone__ != 1` so admins never accidentally pick a clone as the source.
- Implementation record: issue #21. Companion #22 tracks future Playwright autotest integration.

### Combat Zones (T34 — engaged/ranged)

Per `docs/V2_ARCHITECTURE/04_MAGIC_RANGE_MAP.md §4`. Each combatant has `zone: 'engaged' | 'ranged'` in the `combatants` JSON.

- **Defaults at combat start**: Warrior → engaged, Scholar → ranged. Enemy zone via keyword heuristic in `combat_service._default_zone_for_enemy()` (archer/mage/shaman/łucznik/kusznik/etc. → ranged; default → engaged).
- **Player melee gating**: if attacker has a melee weapon and target is in a different zone, `resolve_attack` returns `{blocked: true, block_reason: 'out_of_range'}` **without consuming the turn**. Player must close (use the Zbliż się button) or switch to a ranged option.
- **Enemy AI charging**: melee enemy in wrong zone uses its turn to close (zone-change to player's zone), no attack that round. Tracked via `combat_turns.event_type='zone_change'`.
- **Zone change action**: `POST /api/campaigns/{id}/combat/zone-change` calls `change_player_zone(campaign_id)` which toggles the player's zone and advances the turn.
- Frontend combat banner splits into DYSTANS / ZWARCIE columns. Composer gets a Zbliż się / Cofnij się button. Initiative chips show 🏹 (ranged) or ⚔ (engaged) glyph.

## Locked Game Mechanics (do not modify without explicit approval)

- **Stats (7):** STR, DEX, CON, INT, WIS, CHA, LCK
- **Roll formula:** `d20 + stat_modifier + skill_rank + proficiency_bonus ≥ DC`. Proficiency bonus +2 when `skill_rank ≥ 3`. Nat 20 = auto-success + double damage; Nat 1 = auto-fail + complication.
- **DC scale:** Easy 8 / Medium 12 / Hard 16 / Extreme 20 / Legendary 24+
- **Combat defense (#826, 2026-06-19 — redesigned with explicit approval):** ONE defensive test per hit (no double jeopardy). Armor (`ac_base`/AC) = **damage reduction**, not a to-hit threshold (`armor = max(0, ac_base − 10)`, min 1 dmg/hit, Nat 20 ignores armor). Margin → damage: `+1 dmg` per full 5 pts of attack over defender's defense (Nat 20 ×2 separate). Symmetric player↔enemy. Helpers: `apply_defense_model`/`compute_enemy_attack_hit` in `combat_service.py`. **All values are STARTING values, Sandbox-tunable** (`MARGIN_DAMAGE_STEP`, `MARGIN_DAMAGE_BONUS`, `ARMOR_REDUCTION_OFFSET`). See `game_mechanics.md` CZĘŚĆ AB. Supersedes #753, covers #744.
- **HP:** archetype base + `CON_mod × level`. **Mana (Mage only):** `8 + INT_mod × level`.
- Source of truth: `backend/prompts/system_prompt.txt`. DB schema changes require a migration, never direct DB edits. Fix code, not test assertions.

## Database

- SQLite file: `data/ai_gm.db` on host (bind-mounted to `/data/ai_gm.db` in backend container). DEV compose maps `./data-dev` instead.
- Pre-import auto-backups on config import → `./backups/imports/`. Retention: 30 days, ≥3 older, capped at 10.
- Key tables: `game_config_weapons`, `game_config_items`, `game_config_consumables`, `game_config_enemies`, `game_config_skills`, `game_config_stats`, `campaign_ideas`, `campaign_turns`, `campaigns`, `characters`, `users`.

### World map ownership (`world_hexes`, map_level=0) — PIOTR-OWNED, do not edit without approval

- **Canonical source of truth = `docs/world/world_map_seed.json`** (git-committed; a commit = Piotr's approval). The DB table `world_hexes` (overworld, `map_level=0`) is a *derived cache* seeded from this file.
- **Do NOT wipe, reset, migrate or edit `world_hexes` (map_level=0)** as part of unrelated work. It is the Kresy world map and is owned by Piotr. If a task seems to require touching it, ask first.
- **Restore after an accidental wipe:** `python3 scripts/seed_world_map.py` (on `.61`) — idempotent, seeds only if empty; `--force` overwrites from the seed file. Also runs automatically at the end of `scripts/deploy_dev.sh`.
- **Persist Piotr's in-game edits (admin→Mapa):** `python3 scripts/snapshot_world_map.py` (on `.61`) dumps current `world_hexes` → `world_map_seed.json`, then **commit the file**. Only a committed snapshot is permanent and survives DB wipes.
- Base map generator (design artifact, separate from the seed): `scripts/generate_kresy_map.py` → `docs/world/kresy_map.json`. See map import / future-krainy work in issue #933.

## Conventions

- Commit messages: include phase number when relevant. Polish or English fine.
- New endpoint: route in `backend/app/api/<module>.py` or `backend/app/routers/<module>.py` → register in `app/main.py`.
- DB change: write migration in `migrations_admin.py` → test on DB copy → update models if needed.
- Frontend change: edit under `frontend/` → verify in browser at `https://aigm-dev.studio-colorbox.com/` → check console.
- JS version strings in imports (`?v=N`) must be bumped when a shared module changes to bust browser cache.
- **Player-UI ledger:** any change under `frontend/front/` (new/changed screen, modal, gameplay component, or system) → add or update the matching `F-NN` entry in `frontend_design.md` (Section 7, Feature Ledger), per the convention in Section 9. Keeps the redesign target 1:1 with the live player UI.
- **Księga Zasad ledger (living document):** any change that alters **player-facing rules/mechanics** (new/changed skill, spell, condition, combat rule, stat/DC change) → update the living Rules Book `frontend/front/rules/index.html` (served at `/rules/`) in the **same PR**. Checklist: chapter prose + example · test/entry card · gloss tooltip on new terms + "Pełny opis →" link · TOC entry + anchor `id` · illustration via Juggernaut-XL on `.170` if a scene/skill/spell. The Księga **describes, never defines** — source of truth stays `backend/prompts/system_prompt.txt`, `game_mechanics.md`, engine code, `game_config_*`. Skip when the change does not touch player rules. Per issue #868.

### Implementation record issues (mandatory)

Every time a new feature or task is implemented, file a GitHub issue documenting it. **Template reference: https://github.com/szmidtpiotr/ai-gm/issues/18** — match that structure exactly.

Required sections:
1. **Title**: `[TASK] <task code if any> — <short description>`
2. **Labels**: `enhancement` + `needs-testing` (verification flag — keep open until tested)
3. **Body**:
   - `## Task` — task name + companion feature-request link if one exists + implementation commit SHA
   - `## What was implemented` — concrete behavior, visual states table where relevant, motion timings, client-side state tracking
   - `## Files changed` — list every modified path with one-line rationale
   - `## Backend` — explicitly state "No changes" if frontend-only, else summarize endpoints / migrations
   - `## Numbers Policy` — each timing/threshold labeled as starting value with test plan (per game-design framework)
   - `## Acceptance` — checkbox list of verification steps to run in the browser
   - `## Out of scope` — sibling tasks deferred for separate issues
4. **Close only after** visual verification on DEV; the `needs-testing` label flags pending verification.

This applies to every implementation, no matter how small.

## Reference Files

- Backend entry: `backend/app/main.py`
- LLM service: `backend/app/services/llm_service.py`
- Combat: `backend/app/services/combat_service.py`
- Multiplayer combat: `backend/app/services/multiplayer_round_service.py`
- Scholar spell system: `backend/app/services/spell_service.py`
- Dungeon runs: `backend/app/services/dungeon_service.py`
- Turn submodules: `backend/app/services/turn/` (commands, gambling, gate, intent, skill_router)
- Smart Entry router: `backend/app/routers/smart_entry.py`
- Adventure Forge (campaign templates): `backend/app/routers/adventure_forge.py`
- Hex world map: `backend/app/routers/hex_world.py`
- Voice proxy (Piper TTS): `backend/app/routers/voice_proxy.py`
- Admin migrations: `backend/app/migrations_admin.py`
- MCP server (game tools for Claude): `mcp_server/server.py`
- Modular Admin entry: `frontend/admin/index.html`
- Content section (weapons/items): `frontend/admin/sections/content.js`
- Campaign monitor: `frontend/admin/sections/campaigns.js`
- Forge (asset builder): `frontend/admin/sections/forge.js`
- All admin styles: `frontend/admin/layout.css`
- Player UI: `frontend/front/index.html`, `frontend/front/js/app.js`, `frontend/front/css/styles.css`
- Compose: `docker-compose.yml` (PROD), `docker-compose.dev.yml` (DEV)
- Planned work: `to_do_ideas.md`
- Game mechanics reference (stats, combat, skills, DC, archetypes): `game_mechanics.md`
- System architecture map: `architecture-map.md`
