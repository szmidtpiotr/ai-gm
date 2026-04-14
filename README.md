# 🎲 AI Game Master

A locally-run AI-powered RPG Game Master. You type your actions — the AI narrates the world, runs the rules, and plays all NPCs. Built with FastAPI, SQLite, Ollama (local LLM), and a browser-based frontend.

---

## 🧠 What Is This?

AI GM is a text-based fantasy RPG where a local LLM (via Ollama) acts as the Game Master. It narrates scenes, resolves actions with dice rolls, manages your character sheet, and tracks the full campaign history — all running on your own machine, no external API required.

---

## 🚀 Quick Start

### 1. Clone & run

```bash
git clone https://github.com/szmidtpiotr/AI-GM.git
cd AI-GM
docker compose up -d --build
```

| Service | URL |
|---|---|
| Game UI | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| API | http://localhost:8000/api |
| Ollama | http://localhost:11434 |

### 2. Pull an LLM model

Models must be pulled into the Ollama container (not the host):

```bash
docker compose exec ollama ollama pull gemma3:4b
docker compose exec ollama ollama list
```

Recommended models: `gemma3:4b`, `llama3`, `mistral`

### 3. Quick API test

```bash
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/campaigns | jq
```

---

## 🏗️ Architecture

| Service | Role | Port |
|---|---|---|
| `frontend` | Static UI served by Nginx | 3000 |
| `backend` | FastAPI REST API | 8000 |
| `ollama` | Local LLM runner (NVIDIA GPU support) | 11434 |
| `ai_gm_data` | Persistent Docker volume for SQLite DB | — |

Data is stored in `/data/ai_gm.db` (SQLite) inside the `ai_gm_data` Docker volume — campaigns and history survive container restarts.

---

## 📡 API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/models` | List available Ollama models |
| GET | `/api/campaigns` | List all campaigns |
| POST | `/api/campaigns` | Create new campaign |
| GET | `/api/campaigns/{id}` | Get campaign details |
| DELETE | `/api/campaigns/{id}` | Delete campaign |
| GET | `/api/campaigns/{id}/characters` | List characters in campaign |
| POST | `/api/campaigns/{id}/characters` | Create character |
| GET | `/api/campaigns/{id}/turns` | Get full turn history |
| POST | `/api/campaigns/{id}/turns` | Submit player action (triggers GM response) |
| POST | `/api/commands/execute` | Execute a game command |

Full interactive docs at `http://localhost:8000/docs`.

---

## 🎮 Game Rules (Phase 5.5 — Locked)

### Stats
7 core stats: **STR, DEX, CON, INT, WIS, CHA, LCK**
Modifier formula: `floor((value - 10) / 2)`

### Archetypes
- **Warrior** — STR/CON focus, melee combat skills
- **Mage** — INT/WIS focus, arcana and spells

### Dice System
`d20 + stat modifier + skill rank + proficiency bonus ≥ DC`

| Difficulty | DC |
|---|---|
| Easy | 8 |
| Medium | 12 |
| Hard | 16 |
| Extreme | 20 |
| Legendary | 24+ |

- **Nat 20** → auto-success + double damage
- **Nat 1** → auto-fail + narrative complication
- **Advantage** → roll 2d20, take higher
- **Disadvantage** → roll 2d20, take lower

### Skills (10 total)
`athletics`, `stealth`, `awareness`, `survival`, `lore`, `investigation`, `arcana`, `medicine`, `persuasion`, `intimidation`

Skill ranks: 0–5 (Untrained → Master). Proficiency bonus applies at rank ≥ 3.

### Saves
`fortitude_save` (CON), `reflex_save` (DEX), `willpower_save` (WIS), `arcane_save` (INT)

---

## 🛠️ Developer Setup

### Dev mode (live reload)

Create `docker-compose.override.yml`:

```yaml
services:
  backend:
    volumes:
      - ./backend:/app
      - ai_gm_data:/data
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      WATCHFILES_FORCE_POLLING: "true"
```

Then run:

```bash
docker compose up -d --build
docker compose logs -f backend
```

Code changes in `./backend` are reflected immediately without rebuild.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama address used by backend |
| `OLLAMA_TIMEOUT` | `60` | LLM request timeout (seconds) |
| `DEFAULT_CAMPAIGN_LANGUAGE` | `pl` | Default campaign language |
| `GAME_LANG` | `pl-PL` | Game language setting |
| `DATABASE_URL` | `sqlite:////data/ai_gm.db` | SQLite path |

To use an external Ollama host instead of the container:

```env
OLLAMA_BASE_URL=http://your-host:11434
```

### Branch workflow

- Develop on feature branches
- Merge to `main` when confirmed working
- Pull `main` on production desktop: `git pull && docker compose up -d --build`

---

## 📦 Tech Stack

- **Python 3.12** + FastAPI + Pydantic
- **SQLite** — campaigns, characters, turns, game state
- **Ollama** — local LLM runner (Gemma, Llama, Mistral, etc.)
- **Docker Compose** — orchestration
- **Nginx** — static frontend server

---

## 🗺️ Roadmap

| Phase | Name | Status |
|---|---|---|
| 1 | Core game loop | ✅ Done |
| 2 | Player object + World system | ✅ Done |
| 3 | AI GM prompt engineering | ✅ Done |
| 3.1 | Character creation + opening scene | ✅ Done |
| 3.2 | Roll system + action resolution | 🔄 In Progress |
| 4 | Save / Load system | ✅ Done |
| 5 | Web UI + Core backend (FastAPI + SQLite) | 🔄 In Progress |
| 5.5 | Game Design rules session | ✅ Done (locked) |
| 6 | Character creation & sheet UI | 🔴 Next |
| 7 | Dice roll full fix (wired to sheet) | 🔴 Planned |
| 8 | Admin backend UI | 💡 Future |
| 9 | Persistent memory across sessions | 💡 Future |
| 10 | Polish, sound, map, modding | 💡 Future |

### Active Dev Improvements
- ⚡ Streaming LLM responses (SSE, typewriter effect)
- 📋 Export / copy session as text (debugging)
- 🕹️ Command autocomplete + help overlay
- 📊 LLM I/O logger (compare model quality)
- 🧭 Campaign summary / history window

---

## 📝 Notes

- Turn numbers (`turn_number`) are counted per campaign, independent of SQLite row IDs
- Pydantic warning on `model_id` / `model_` namespace — cosmetic only, does not affect function
- API path `/campaigns/campaigns/{id}/turns` was a temporary router prefix bug — main path `/api/campaigns/{id}/turns` is correct
