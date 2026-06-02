# AI-GM — Dark Fantasy RPG with AI Game Master

A browser-based single-player RPG where a Large Language Model acts as the Game Master. Players create heroes, embark on campaigns, engage in tactical combat, explore a hex world map, and run standalone dungeons — all narrated in real-time by the AI.

> **Language:** Game narration in **Polish**. Code and docs in English.

---

## Features

### Player Experience
- **Hero-first flow** — create a hero independently, then pick campaigns or dungeons
- **3 archetypes**: Wojownik (Warrior), Uczony (Scholar/Mage), Łotrzyk (Rogue)
- **7 stats**: STR, DEX, CON, INT, WIS, CHA, LCK with archetype bonuses and modifiers
- **Skill system** — 16 skills with trigger keywords; pre-LLM scan fires before the LLM call
- **Turn-based narrative** — GM narrates every action, move, conversation, and event in Polish
- **Character sheet** — stats with modifiers, mana bar, conditions, XP, spells (Scholar), inventory

### Combat
- **Tactical combat engine** — initiative, range zones (engaged/ranged/distant), enemy AI behavior profiles
- **Dice roll popup** — animated d20 with parchment background; results saved to campaign history
- **Scholar spell picker** — select from learned spells mid-combat, mana-checked overlay
- **13 conditions** — stat penalties, auto-remove turn counters (Krwawiący, Zatruty, Ogłuszony…)
- **Critical hits** — nat 20 = double damage; nat 1 = complications
- **Death saves** — escalating DC per failure; flee mechanic with loot abandon

### World
- **Hex world map** — fog-of-war, click-to-travel, terrain types, encounter rolls, A* pathfinding
- **Location system** — GM creates locations narratively; pending admin review queue
- **NPC system** — personality profiles, keyword dialogue triggers

### Dungeon Runs (standalone farmable content)
- **Room types**: combat · chest · trap · riddle · rest · boss
- **Riddle bank** — 12 Polish dark-fantasy riddles, Levenshtein fuzzy answer checking
- **Square tile map** (Betrayal at House on the Hill style) — rooms revealed on entry
- **3-tier loot**: enemy drops · chest table · guaranteed boss drop
- **Dungeon-exclusive items** — `source_exclusive` flag (dungeon/boss only)
- **Cooldown system** — per-character, per-dungeon, admin-configurable hours

### Economy & Inventory
- **Inventory** — equipment slots (main_hand/off_hand/armor), backpack, quest/lore items, gold
- **Loot system** — 3-way item type (item/consumable/weapon), per-enemy loot tables with weights
- **Shop system** — narrative-embedded merchant encounters
- **XP progression** — WFRP-style: spend XP to upgrade stats and skills
- **Scholar spells** — 9 spells (tiers 1–5), mana, arcane points, rank 2/3 upgrades, miscast on nat 1

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + SQLite |
| Frontend (Player) | Static HTML/CSS/JS served by Nginx |
| Frontend (Admin) | Modular JS sections at `/admin2/` |
| LLM | Ollama (local) or any OpenAI-compatible endpoint |
| Runtime config | SQLite (`/data/ai_gm.db`) |
| Voice (optional) | Piper TTS |
| Observability (opt) | Grafana + Loki + Prometheus |

---

## Architecture

```
Player Browser
  └─ /front/         Player UI (login → hero → campaigns/dungeons → gameplay)
  └─ /admin2/        Admin Panel v2 (modular JS sections)

Backend (FastAPI)
  ├─ /api/           Player-facing endpoints
  │    ├─ campaigns, characters, turns, combat, inventory, dungeons
  │    ├─ world-map, skill-tests, mechanics, shop, npcs
  │    └─ characters/{id}/spells, dungeons/{key}/enter, resolve-room
  ├─ /api/admin/     Admin endpoints (token-protected)
  │    ├─ weapons, items, enemies, conditions, skills, dc, archetypes
  │    ├─ loot-tables, dungeons, riddles, campaigns/hex-map
  │    └─ llm-presets, config export/import, assistant/draft
  └─ Services
       ├─ combat_service.py         — turn resolution, spell attacks, conditions
       ├─ dungeon_service.py        — room gen, riddles, loot tiers, death handling
       ├─ loot_service.py           — inventory, item effects, dice roller
       ├─ spell_service.py          — mana, miscast, arcane points, rank upgrades
       ├─ world_service.py          — locations, NPCs, enemies (pending review pipeline)
       ├─ hex_travel_service.py     — A* pathfinding, fog-of-war, encounter clearing
       └─ turns.py                  — 9-step turn pipeline, skill test interception
```

---

## Development

### Environment

| Role | Host | Branch | Ports |
|---|---|---|---|
| **DEV** | `192.168.1.61` | `main` | frontend `:3002`, backend `:8100` |
| **PROD** | `192.168.1.63` | `main` | frontend `:3001`, backend `:8000` |

> All commits go directly to **`main`**. No separate develop branch.

### Run on DEV

```bash
ssh claude@192.168.1.61
cd /home/piotrszmidt/ai-gm

# Rebuild and start
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans
# or
./scripts/deploy_dev.sh
```

### Deploy to PROD

```bash
ssh claude@192.168.1.63
cd ~/ai-gm
./scripts/deploy_prod.sh
```

### Database

```bash
./scripts/backup.sh                              # → ./backups/ai_gm_<timestamp>.db
./scripts/restore.sh ai_gm_20260517_143000.db   # auto-backs up current first

docker compose -f docker-compose.dev.yml logs backend --tail=50
```

### Tests (TDD)

```bash
./scripts/verify_testing_setup.sh          # smoke-check tooling
./scripts/test_local.sh                    # local venv (recommended)
./scripts/test_local.sh tests/test_gm_plan_schema.py -v
./scripts/test_dev.sh                      # inside Docker backend container
```

See **[`docs/TESTING.md`](docs/TESTING.md)** — paths, container layout (`tests/` not `backend/tests/` in Docker), known suite limitations.

---

## LLM Configuration

Resolution order (first match wins):

1. **Admin preset** — active preset in `Admin Panel → System`
2. **User custom** — `/api/users/{id}/llm-settings` with `mode="custom"`
3. **Environment vars** — `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`

Configure from `Admin Panel → System → LLM` or via `docker-compose.dev.yml` env vars.

---

## Admin Panel (`/admin2/`)

| Section | Description |
|---|---|
| **Mechaniki** | Stats, skills, DC tiers, conditions, archetypes |
| **Zawartość** | Weapons, armor, items, consumables, loot tables + AI Kreator |
| **Świat** | Locations, NPCs, enemies, dungeons, riddle bank, pending review |
| **Narracja** | System prompt tuning |
| **Gracze** | User accounts, per-user LLM settings |
| **Kampanie** | Campaign monitor, GM plan workshop, hex map editor per campaign |
| **System** | LLM presets, config export/import |

---

## Game Reference

### Archetypes

| Key | Name | HP | Bonus |
|---|---|---|---|
| `warrior` | Wojownik | 12 + CON | +2 STR, +1 CON |
| `scholar` | Uczony | 6 + CON | +2 INT, +1 WIS · Mana: 8 + INT_mod |
| `rogue` | Łotrzyk | 8 + CON | +2 DEX, +1 LCK |

### Difficulty Classes

| Label | DC |
|---|---|
| Łatwe | 9 |
| Średnie | 12 |
| Trudne | 16 |
| Ekstremalne | 20 |
| Legendarne | 24+ |

### Core Roll Formula

```
d20 + stat_modifier + skill_rank + proficiency_bonus ≥ DC
```
- Proficiency bonus: +2 when `skill_rank ≥ 3`
- Nat 20: auto-success + double damage
- Nat 1: auto-fail + complication

---

## Roadmap

See [`ROADMAP.md`](./ROADMAP.md) for the full task tree with completion checkboxes.

**Current: ~78% complete** (42 of 54 planned tasks done).

Key remaining tasks:
- **T46** — Narrative Items (LLM-invented items tracked in inventory, weapon review pipeline)
- **T33** — Hybrid Input UI (suggested actions from backend)
- **T34** — Combat UI polish (initiative panel, zone display)
- **T38** — Campaign End/Death screens
- **T45** — Hero Journal (cross-campaign chronicle)

---

## Security

- Do not commit `.env`, secrets, or credentials
- Admin token is separate from player auth
- LLM API keys stored server-side, never returned via API
- Player UI cannot modify global LLM runtime — admin-only
