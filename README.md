# AI-GM - RPG Game Project

AI-GM is a browser-based RPG where the backend LLM acts as Game Master.  
The project includes player gameplay UI, admin configuration UI, per-user LLM settings, and observability tooling.

## Quick Start

```bash
# Fresh Ubuntu host may need:
# sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/szmidtpiotr/ai-gm.git
cd ai-gm
chmod +x install.sh
./install.sh
```

Services:

- Frontend: `http://localhost:3001`
- Backend API: `http://localhost:8000/api`
- Swagger docs: `http://localhost:8000/docs`

Installer notes:

- `install.sh` now runs with interactive checkpoints before destructive/mid-configuration steps.
- For CI/automation use non-interactive mode: `./install.sh --yes`.
- At the end, installer prints and saves a full status summary to `install-summary.txt` (URLs, LLM mode, DB path, runtime container status).
- Dedicated PROD host recommended bootstrap: `GRAFANA_ADMIN_PASSWORD='...' ./install.sh --with-observability --no-ollama`
- `--no-ollama` is the recommended first boot mode when the final custom LLM URL / API key / model will be configured later from `Admin Panel -> Accounts`.

## Remote Workspace Operation

In the current team setup, `/home/piotrszmidt/remote_mount/ai-gm` is an NFS-mounted view of the repo hosted on `192.168.1.61`.

- Edit files in the mounted workspace as needed, but run Docker, tests, restarts, and rebuilds only on `piotrszmidt@192.168.1.61`.
- Do not use the local machine as the AI-GM dev runtime.
- Validate deployed dev changes via `https://aigm-dev.studio-colorbox.com/`.
- Restart or rebuild the relevant remote services after code changes when required.

## Environment Roles

- DEV host: `192.168.1.61`
  - development runtime only
  - branch flow centered on `develop`
- PROD host: `192.168.1.63`
  - production runtime only
  - deploy only from `main`
  - observability stack lives there together with PROD

Current recommended production flow:

1. Finish and validate work on DEV
2. Promote `develop` -> `main`
3. SSH to `192.168.1.63`
4. Run `./scripts/deploy_prod.sh`

`scripts/promote_and_deploy_prod.sh` is kept only as a legacy helper and should not be the default production path for the dedicated PROD host model.

## Current Stack

- Backend: FastAPI + SQLite
- Frontend: static HTML/CSS/JS served by Nginx
- LLM providers: Ollama and OpenAI-compatible endpoints
- Runtime config storage: SQLite (`/data/ai_gm.db`)

## Implemented Features

### Player Side

- Login gate before loading gameplay data.
- Campaign/character/turn flow with streaming and non-streaming responses.
- Player UI no longer edits provider / base URL / API key; those are managed from admin only.
- LLM panel collapsed by default, toggleable in UI.
- Mechanics metadata endpoint for skill/DC descriptions and roll hints.

### Admin Side

- Token-protected `/api/admin/*` API.
- Admin dev login endpoint for local development.
- Global LLM settings and saved presets in `Admin Panel -> Accounts`.
- Tabbed admin panel with inline CRUD:
  - stats
  - skills
  - dc tiers
  - weapons
  - enemies
  - conditions
  - accounts
  - user LLM settings
- Lock guard support (`locked_at` + `force=true`).
- Audit log on create/update/delete operations.
- Config export/import with dry-run and version checks.

### Config Tables (seeded)

- `game_config_stats`
- `game_config_skills`
- `game_config_dc`
- `game_config_weapons` (example row: `shortsword`)
- `game_config_enemies` (example row: `goblin`)
- `game_config_conditions` (example row: `poisoned`)

## Key API Groups

- Gameplay:
  - `/api/campaigns/*`
  - `/api/characters/*`
  - `/api/turns/*`
- Player auth:
  - `POST /api/auth/login`
- LLM settings:
  - `/api/users/{user_id}/llm-settings`
- Admin:
  - `/api/admin/*`
- Mechanics metadata:
  - `GET /api/mechanics/metadata`

## LLM Resolution

The backend resolves effective LLM config in one place:

- **Server default**: active admin preset / runtime override if present, otherwise `LLM_*` environment variables.
- **User custom**: `/api/users/{user_id}/llm-settings` with `mode="custom"` overrides the server default.
- **User default**: `/api/users/{user_id}/llm-settings` with `mode="default"` falls back to the resolved server default.

Relevant environment variables:

- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_API_KEY`
- `LLM_TEMPERATURE`
- `LLM_TOP_P`
- `LLM_TOP_K`
- `LLM_REPEAT_PENALTY`
- `LLM_MAX_TOKENS`

Notes:

- Global provider / API credentials are edited from `Admin Panel -> Accounts`, not from the player frontend.
- Saved global presets can be activated later and deleted once inactive.

- Player UI now saves only the player profile LLM mode/config and no longer overwrites the global server runtime on normal "Connect".
- Tests/CI should use the same `LLM_*` env path or explicit request override fixtures instead of assuming a separate LLM config mechanism.

## Figma Handoff Docs

Design-to-code handoff documents are tracked in:

- `docs/figma-handoff/README.md`
- `docs/figma-handoff/FIGMA_BRIEF.md`
- `docs/figma-handoff/COMPONENT_MAP.md`
- `docs/figma-handoff/UI_SPEC.md`

## Observability

Observability assets (Grafana/Loki/Promtail + MCP connector docs) are in:

- `observability/`

The Notion page `Debug Platform` is the operational source of truth; keep docs and repo synchronized.

## Development Notes

- Main branch is the source of truth for shipped features.
- Use feature branches for isolated work, then merge when smoke tests pass.
- Do not commit secrets (`.env`, `.secrets/`, credentials files).

## Database Backup & Restore

The SQLite database is stored at `./data/ai_gm.db` (bind-mounted into the backend
container at `/data/ai_gm.db`).

**Backup:**

```bash
./scripts/backup.sh
# Saves timestamped copy to ./backups/
```

**Automatic pre-import backups:**

- `POST /api/admin/config/import`
- `POST /api/admin/config/catalog-snapshot/import`

When `dry_run=false`, backend creates a DB snapshot in `./backups/imports/` before
replacing config/catalog rows. Retention keeps recent backups for 30 days, always
preserves at least the latest 3 older snapshots, and caps the import-backup pool at 10 files.

**Restore:**

```bash
./scripts/restore.sh ai_gm_20260420_143000.db
# Auto-backs up current DB before replacing
# Restart backend after: docker compose restart backend
```

**Manual one-liner:**

```bash
cp ./data/ai_gm.db ./backups/ai_gm_$(date +%Y%m%d_%H%M%S).db
```

### Migrating from a named Docker volume

If you have existing data in the named Docker volume (`ai_gm_data` or similar),
extract it before switching:

```bash
docker compose down
docker run --rm \
  -v <project>_ai_gm_data:/source \
  -v "$(pwd)/data":/dest \
  alpine cp /source/ai_gm.db /dest/ai_gm.db
docker compose up -d
```

Then verify: `ls -lh ./data/ai_gm.db`
