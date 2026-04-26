# AI-GM - RPG Game Project

AI-GM is a browser-based RPG where the backend LLM acts as Game Master.  
The project includes player gameplay UI, admin configuration UI, per-user LLM settings, and observability tooling.

## Quick Start

```bash
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

## Current Stack

- Backend: FastAPI + SQLite
- Frontend: static HTML/CSS/JS served by Nginx
- LLM providers: Ollama and OpenAI-compatible endpoints
- Runtime config storage: SQLite (`/data/ai_gm.db`)

## Implemented Features

### Player Side
- Login gate before loading gameplay data.
- Campaign/character/turn flow with streaming and non-streaming responses.
- Per-user LLM settings (`provider`, `base_url`, `model`, optional `api_key`).
- LLM panel collapsed by default, toggleable in UI.
- Mechanics metadata endpoint for skill/DC descriptions and roll hints.

### Admin Side
- Token-protected `/api/admin/*` API.
- Admin dev login endpoint for local development.
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
