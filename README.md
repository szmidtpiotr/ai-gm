# 🎲 AI Game Master

A locally-run AI-powered RPG Game Master. You type your actions — the AI narrates the world, runs the rules, and plays all NPCs. Built with FastAPI, SQLite, Ollama (local LLM), and a browser-based frontend.

---

## 🧠 What Is This?

AI GM is a text-based fantasy RPG where a local LLM (via Ollama) acts as the Game Master. It narrates scenes, resolves actions with dice rolls, manages your character sheet, and tracks the full campaign history — all running on your own machine, no external API required.

---

## 🚀 Quick Start

### 1. Clone & run

```bash
git clone https://github.com/szmidtpiotr/ai-gm.git
cd ai-gm
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

Recommended models: `gemma3:4b`, `llama3.1:8b`, `mistral`

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

### Roll Cue Format (machine-readable, frozen)
The GM emits exactly one of these strings as the last line of a response when a roll is needed:
```
Roll Stealth d20
Roll Initiative d20
Roll Attack d20
Roll Dex Save d20
Roll Str Save d20
Roll Con Save d20
Roll Int Save d20
Roll Wis Save d20
Roll Cha Save d20
```
No punctuation, no markdown, no extra words. Parser depends on this exact format.

### Commands
| Command | Description |
|---|---|
| `/sheet` | Returns full character JSON |
| `/roll` | Rolls d20 + modifier for last GM-requested roll |
| `/help` | Lists available commands |

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

```
✅ Phase 1   — Core game loop (input → AI → output)
✅ Phase 2   — Player object + World/scene system
✅ Phase 3   — AI GM prompt engineering
✅ Phase 3.1 — Character creation + opening scene
🔄 Phase 3.2 — Roll system + action resolution       ← YOU ARE HERE
🔴 Phase 4   — Save / Load system (formalise endpoints)
🔴 Phase 5   — Combat system v1 (enemy stats, HP, turn-based)
🔴 Phase 6   — NPC system + dialogue
🔴 Phase 7   — Main quest skeleton (Act 1)
💡 Phase 8   — Web UI (browser-based interface)
💡 Phase 9   — Persistent memory across sessions
💡 Phase 10  — Polish, sound, map, modding
```

### 🔧 Active Dev — Planned Improvements

| Feature | Status | Notes |
|---|---|---|
| ⚡ Streaming LLM responses (SSE typewriter) | Planned | Ollama supports `stream=True`; frontend via SSE |
| 📋 Export / copy session as text | Planned | Debug tool — saves turn history to `.txt` |
| 🕹️ `/help` command overlay | Planned | Lists all commands with descriptions |
| 🗂️ Campaign summary / history window | Planned | Scrollable session log panel |
| 📊 LLM I/O logger | Planned | Logs model name, prompt, response, duration to `.jsonl` |
| 🔬 LLM parameter tweaking | Planned | `temperature`, `top_p`, `top_k` via config or CLI flags |
| 🧹 Clear chat on new campaign | Planned | Wipe history when new campaign starts |
| 🖥️ Prod/dev environment (Ubuntu Desktop) | Planned | systemd service for prod, override for dev |

---

## 📝 Notes

- Turn numbers (`turn_number`) are counted per campaign, independent of SQLite row IDs
- Pydantic warning on `model_id` / `model_` namespace — cosmetic only, does not affect function
- API path `/campaigns/campaigns/{id}/turns` was a temporary router prefix bug — main path `/api/campaigns/{id}/turns` is correct
- GM input classifier: dialogue → no roll, normal action → no roll, risky action → roll cue as last line
- Roll cue format is frozen — model upgrades must be re-tested against the parser
