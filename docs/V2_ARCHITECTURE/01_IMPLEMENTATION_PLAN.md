# AI-GM V2 — Implementation Plan

> **Rule:** One task at a time. Test after each task. Discuss before moving to next.
> No task starts until the previous one passes its test checklist.
> All decisions recorded in session docs 00–05.

---

## Phase Overview

| Phase | Name | Tasks | What it delivers |
|-------|------|-------|-----------------|
| 01 | Foundation | 5 | DB schema + state definitions, Intent Parser, World State Machine, Context Injector |
| 02 | Character | 4 | HP/Mana formulas, character wizard, campaign plan generation, **persistent hero** |
| 03 | World | 3 | Location system, NPC system, data tables pattern |
| 04 | Gameplay Loop | 4 | Turn pipeline, skill tests, campaign plan v2, opening scene |
| 05 | Combat | 7 | State machine, **range zones + combat map**, enemy AI, Fear/Terror, crit hits, death saves, flee |
| 06 | Economy | 8 | Inventory, shop, loot, healing, wound labels, **XP (WFRP style)**, **Scholar spells**, **dungeon runs** |
| 07 | Narrator | 4 | Narrator engine, combat narration, NPC dialogue, scene narration |
| 08 | Admin | 5 | Ideas Workshop, Smart Entry agent, campaign workshop, world review queue, **Visual World Builder** |
| 09 | Frontend | 5 | Hybrid input UI, combat UI, character sheet UI, **Player World Map**, **Debug System** |
| 10 | Polish | 5 | **Hero Journal**, memory/history, command palette, campaign end/death, auth |
| 11 | Observability | 5 | Game event logging, LLM call log, **admin analytics panel**, **MCP server** |

**Total tasks: 55**

> Phase 11 adds: `game_events` + `llm_call_log` tables, event_logger service, admin analytics section (dashboard/events/LLM tabs), and MCP server with 9 tools for AI-queryable game data.
> Full design in `08_OBSERVABILITY_AND_MCP.md`

---

## Full Task List

### Phase 01 — Foundation
> Must be first. Every other phase depends on it.

| Task | File | Status | Notes |
|------|------|--------|-------|
| 01 | TASK_01_DB_SCHEMA | ✅ | All tables + game_state_definitions seed, location_connections, map columns |
| 02 | TASK_02_INTENT_PARSER | ✅ | Player text → ACTION tag |
| 03 | TASK_03_WORLD_STATE_MACHINE | ✅ | Validates actions, transitions states, reads state_definitions from DB |
| 04 | TASK_04_CONTEXT_INJECTOR | ✅ | Builds narrator prompt from DB content + mechanical result |

### Phase 02 — Character
> Depends on Phase 01.

| Task | File | Status | Notes |
|------|------|--------|-------|
| 05 | TASK_05_HP_MANA_FORMULAS | ✅ | HP = base + CON_mod × level. Mana = 8 + INT_mod × level (Scholar) |
| 06 | TASK_06_CHARACTER_WIZARD | ✅ | 4-step wizard, GM identity generation, secret predisposition |
| 07 | TASK_07_CAMPAIGN_PLAN_GENERATION | ✅ | LLM generates from character + Ideas Bank |
| 42 | TASK_42_PERSISTENT_HERO | ❌ | Hero lives across campaigns, rest state, adventure selection |

### Phase 03 — World
> Depends on Phase 01.

| Task | File | Status | Notes |
|------|------|--------|-------|
| 08 | TASK_08_LOCATION_SYSTEM | ✅ | Badge, safe_for_rest, location_connections validation |
| 09 | TASK_09_NPC_SYSTEM | ✅ | Personality DB, keyword triggers, dialogue hooks |
| 10 | TASK_10_DATA_TABLES_SOURCE_OF_TRUTH | ✅ | Lookup-before-create, pending_review, review queue |

### Phase 04 — Gameplay Loop
> Depends on Phase 01, 02, 03.

| Task | File | Status | Notes |
|------|------|--------|-------|
| 11 | TASK_11_TURN_PIPELINE | ✅ | Full 9-step pipeline in turn_pipeline.py |
| 12 | TASK_12_SKILL_TESTS | 🔶 | Non-combat rolls, counter-skill matrix, roll popup |
| 13 | TASK_13_CAMPAIGN_PLAN_V2 | ✅ | Runtime schema, deviation detection, all GM tags |
| 04B | TASK_04B_OPENING_SCENE | ✅ | First GM turn after character finalization |

### Phase 05 — Combat
> Depends on Phase 01, 04.

| Task | File | Status | Notes |
|------|------|--------|-------|
| 14 | TASK_14_COMBAT_STATE_MACHINE | ✅ | Initiative, round flow, **range zones**, enemy auto-turn |
| 15 | TASK_15_ENEMY_AI_RULES | ✅ | Behavior profiles in DB, rule-based enemy decisions |
| 16 | TASK_16_FEAR_TERROR | ✅ | WIS save, FRIGHTENED/PANICKED/BREAK conditions |
| 17 | TASK_17_CRITICAL_HITS | ✅ | Threshold + hit location table + lasting effects |
| 18 | TASK_18_DEATH_SAVES | ✅ | Escalating DC 10/13/16/19, CON modifier, counter reset |
| 19 | TASK_19_FLEE_MECHANIC | ✅ | Opposed DEX, loot abandoned, zone change |

### Phase 06 — Economy
> Depends on Phase 03 (locations for loot), Phase 05 (combat for loot/healing).

| Task | File | Status | Notes |
|------|------|--------|-------|
| 20 | TASK_20_INVENTORY_EQUIPMENT | ✅ | Slots, click-to-equip, combat restrictions |
| 21 | TASK_21_SHOP_SYSTEM | ✅ | Narrative-embedded entry, buy/sell, merchant NPCs |
| 22 | TASK_22_LOOT_SYSTEM | ✅ | Location-tied, expiry rules, partial claim |
| 23 | TASK_23_HEALING_SYSTEM | ✅ | Items, rest, Scholar Mend Wounds |
| 24 | TASK_24_WOUND_LABELS | ✅ | HP% thresholds, narrator injection, HP bar colour |
| 25V2 | TASK_25_XP_PROGRESSION_V2 | ✅ | WFRP style: everything purchased with XP, magic tied to INT |
| 26 | TASK_26_SCHOLAR_SPELLS | ❌ | Spell list, Arcane Points, upgrade tiers, miscast scaling |
| 41 | TASK_41_DUNGEON_RUNS | ❌ | Standalone farmable dungeons, cooldown, scaling |

### Phase 07 — Narrator
> Depends on Phase 04, 05.

| Task | File | Status | Notes |
|------|------|--------|-------|
| 26N | TASK_26_NARRATOR_ENGINE | ✅ | System prompt, constraints, post-processing, fallbacks |
| 27 | TASK_27_COMBAT_NARRATION | ✅ | Per-action narration, parallellised, fallback templates |
| 28 | TASK_28_NPC_DIALOGUE | ✅ | In-character, keyword triggers, session memory |
| 29 | TASK_29_SCENE_NARRATION | ✅ | Exploration, movement, rest, skill test outcomes |

### Phase 08 — Admin
> Depends on Phase 03, 04.

| Task | File | Status | Notes |
|------|------|--------|-------|
| 30 | TASK_30_IDEAS_WORKSHOP | ✅ | AI agent co-authoring for Ideas Bank |
| 31 | TASK_31_CAMPAIGN_WORKSHOP | ❌ | Admin views/edits live campaigns |
| 32 | TASK_32_WORLD_REVIEW_QUEUE | ❌ | Approve/reject pending world entries |
| 33SA | TASK_33_SMART_ENTRY_AGENT | ❌ | Universal AI-assisted form creation for any table |
| 40 | TASK_40_WORLD_BUILDER | ❌ | **DETAILED** — Cytoscape.js visual map editor, NPC/enemy assignment, connections |

### Phase 09 — Frontend
> Depends on Phase 04, 05, 06.

| Task | File | Status | Notes |
|------|------|--------|-------|
| 33 | TASK_33_HYBRID_INPUT_UI | ❌ | Context buttons + free text, suggested_actions[] API |
| 34 | TASK_34_COMBAT_UI | ❌ | Initiative panel, zone display, crit flash, roll popups |
| 35 | TASK_35_CHARACTER_SHEET_UI | ❌ | Stats, skills, spells, equipment slots, conditions |
| 43 | TASK_43_PLAYER_WORLD_MAP | ❌ | Fog-of-war world map, click-to-travel |
| 44 | TASK_44_DEBUG_SYSTEM | ❌ | Admin debug drawer, /debug commands, DB key display |

### Phase 10 — Polish
> Depends on everything.

| Task | File | Status | Notes |
|------|------|--------|-------|
| 36 | TASK_36_MEMORY_HISTORY | ❌ | /mem command, AI summary (superseded by Hero Journal) |
| 37 | TASK_37_COMMAND_PALETTE | ❌ | /help modal, admin command toggles |
| 38 | TASK_38_CAMPAIGN_END_DEATH | ❌ | Victory screen, death screen, post-death options |
| 39 | TASK_39_AUTH_ONBOARDING | ❌ | Auth flow, first-time UX |
| 45 | TASK_45_HERO_JOURNAL | ❌ | Cross-campaign chronicle, chapter summaries, /mem cross-campaign |

---

## Implementation Order (Dependencies)

```
PHASE 01 (Foundation) — everything depends on this
  Task 01 → Task 02 → Task 03 → Task 04

PHASE 02 (Character)
  Depends on: Phase 01
  Task 05 → Task 06 → Task 07 → Task 42

PHASE 03 (World)
  Depends on: Phase 01
  Task 08 → Task 09 → Task 10
  [Can run parallel with Phase 02]

PHASE 04 (Gameplay)
  Depends on: Phase 01, 02, 03
  Task 11 → Task 12 → Task 13 → Task 04B

PHASE 05 (Combat)
  Depends on: Phase 01, 04
  Task 14 → Task 15 → Task 16 → Task 17 → Task 18 → Task 19

PHASE 06 (Economy)
  Depends on: Phase 03 (loot needs locations), Phase 05 (healing in combat)
  Tasks 20-26 → Task 41 (dungeon runs last — needs combat + loot)

PHASE 07 (Narrator)
  Depends on: Phase 04, 05
  Tasks 26N-29 [can run parallel with Phase 06]

PHASE 08 (Admin)
  Depends on: Phase 03, 04
  Task 30 → Task 31 → Task 32 → Task 33SA → Task 40 (World Builder last — needs all tables ready)

PHASE 09 (Frontend)
  Depends on: Phase 04, 05, 06
  Tasks 33-35 → Task 43 (Player Map after World Builder) → Task 44 (Debug anytime)

PHASE 10 (Polish)
  Depends on: everything
  Tasks 36-39 → Task 45 (Hero Journal last — needs persistent hero + campaign history)
```

---

## Open Decisions

**ALL BLOCKING DECISIONS RESOLVED.** See `10_ALL_OPEN_DECISIONS_RESOLVED.md` for the full canonical list.

Quick reference:

| Decision | Answer |
|----------|--------|
| Death save roll | Pure d20, escalating DC 10/13/16/19 |
| Death save counter reset | No reset mid-combat |
| Crit threshold | 5 over AC (Nat 20 always crits) |
| Fear DC | Admin-configurable per enemy (seeds: Troll=12, Vampire=16, Demon=18) |
| HP base | Warrior=10, Scholar=6 (in archetypes.hp_base) |
| XP spending | Long rest only |
| Companions | Dynamic / story-driven (campaign plan decides) |
| Post-death options | All 3: restart / accept death / retire |
| Dungeon cooldown | Admin-configurable per dungeon seed |
| Registration | Admin-only default + toggleable self-registration |
| **Hero architecture** | **Heroes primary. Campaigns attached TO heroes. Player creates multiple heroes. One active adventure per hero at a time.** |

## Previously Listed as Open (now resolved)
| Critical hit threshold (over AC by N) | Phase 05, Task 17 | Proposed: 5 over AC |
| Max companions (1 or 2) | Phase 05 | User considering |
| XP spending timing | Phase 06 | Long rest only vs anytime |
| Dungeon cooldown hours | Phase 06 | Proposed: 72h (3 in-world days) |
| Campaign end options | Phase 10 | Restart vs Accept death vs Retire |
| Self-registration | Phase 10 | Admin-only creation for now |

---

## Architecture Decisions Log

| Decision | Rationale | Doc |
|----------|-----------|-----|
| System controls world, LLM narrates | Prevent hallucinations, ensure consistency | 00_OVERVIEW |
| Hybrid input (buttons + free text) | Immersion + reliability | 04_MAGIC_RANGE_MAP |
| Enemy AI: rule-based behavior profiles | Deterministic, consistent, admin-configurable | TASK_15 |
| Campaign: LLM generates from character + Ideas Bank | Personalised every time, improves with content | TASK_07 |
| Tone: WFRP world, D&D clean stats | Best of both: dark + accessible | 00_OVERVIEW |
| WFRP elements: Fear/Terror, crit locations, grim | Selected features, not the full WFRP complexity | TASK_16, TASK_17 |
| Magic tied to INT, not level | Stats meaningful, no artificial gates | TASK_25V2 |
| XP-based WFRP-style advancement | Player agency in growth, no level locks | TASK_25V2 |
| Hero persists across campaigns | Narrative continuity, investment in character | TASK_42 |
| Visual world builder (Cytoscape.js) | Admin needs to see spatial relationships | TASK_40 |
| Global persistent world map | World has continuity across all campaigns | TASK_40, TASK_43 |
| Miscast scales by level | Level 1 Scholar too fragile for HP damage | 04_MAGIC_RANGE_MAP |
| Ranged weapons archetype-neutral | DEX determines accuracy, not archetype | 04_MAGIC_RANGE_MAP |
| Dungeon runs with cooldown | Allows farming without trivialising it | TASK_41 |
| Debug system admin-only | Testing needs vs player experience separation | TASK_44 |
| DB-driven state definitions | New states without code changes | 03_STATE_INTEGRITY |
| Smart Entry AI agent for forms | Admin thinks in stories, not schemas | 03_STATE_INTEGRITY |
| NPC companions auto-resolve turns | Player controls hero only, companions AI-driven | 05_WORLD_BUILDER |
| **Hero-centric model** | Heroes primary, campaigns assigned to heroes, multiple heroes per player | TASK_42, 10_DECISIONS |
| Death saves: pure d20, escalating DC | Escalation IS the "gets harder" mechanic — no CON modifier needed | TASK_18, 10_DECISIONS |
| XP spending at long rest only | Natural session rhythm, prevents mid-combat stat gaming | TASK_25V2, 10_DECISIONS |
| Companions: dynamic (story-driven) | Campaign plan decides — flexible, avoids hard cap | 10_DECISIONS |
| Conditions lifecycle | Rounds-based duration, end-of-round ticking, admin stacking toggle | 11_CONDITIONS_SYSTEM |
| Smart Entry Agent: visual questionnaire | Visual option cards + DB query/propose capability | TASK_33_SMART_ENTRY |
| DB cleanup: join tables replace JSON arrays | location_enemy_assignments, location_npc_assignments | 09_DB_CLEANUP |

---

## Key Reference Documents

| Doc | Contents |
|-----|---------|
| `00_OVERVIEW.md` | System architecture, component model, hero-centric model |
| `01_IMPLEMENTATION_PLAN.md` | This file |
| `02_DATA_FLOW_EXAMPLE.md` | Full traced example: campaign creation → first turn |
| `03_STATE_INTEGRITY_AND_SMART_ENTRY.md` | DB-driven states, Smart Entry pattern |
| `04_MAGIC_RANGE_MAP.md` | Magic system, range zones, Scholar spells |
| `05_WORLD_BUILDER_AND_PERSISTENCE.md` | Hero persistence, dungeon runs, XP |
| `06_COMBAT_SIMULATION.md` | Full combat traces (Warrior, Scholar, multi-enemy, fear) |
| `07_FRONTEND_CHANGES_AUDIT.md` | What frontend needs vs what exists in frontend/front/ |
| `08_OBSERVABILITY_AND_MCP.md` | Game events logging, admin analytics, MCP server |
| `09_DB_CLEANUP_DECISIONS.md` | All 22 schema audit decisions |
| `10_ALL_OPEN_DECISIONS_RESOLVED.md` | **ALL blocking decisions — canonical reference** |
| `11_CONDITIONS_SYSTEM.md` | Full conditions lifecycle spec |

---

## Key Reference Documents

| Doc | Contents |
|-----|---------|
| `00_OVERVIEW.md` | System architecture diagram, component model, LLM roles |
| `01_IMPLEMENTATION_PLAN.md` | This file — task list and order |
| `02_DATA_FLOW_EXAMPLE.md` | Complete data flow trace: campaign creation → first turn |
| `03_STATE_INTEGRITY_AND_SMART_ENTRY.md` | State system (DB-driven), Smart Entry pattern |
| `04_MAGIC_RANGE_MAP.md` | Magic system, range zones, maps, Scholar spells |
| `05_WORLD_BUILDER_AND_PERSISTENCE.md` | Hero persistence, dungeon runs, XP rework, debug |

---

## Testing Protocol

**After each task:**
1. Run automated tests: `docker exec ai-gm-dev-backend-1 pytest -k <task_keyword>`
2. Manual test at: `https://aigm-dev.studio-colorbox.com/`
3. Review task's test checklist — all items must pass
4. Discussion: does this feel right before moving on?

**Phase gates:**
- All tasks in phase complete ✅
- Integration test: full user flow for this phase works end-to-end
- No regressions in previous phases

**Deploy after each phase:** push to develop branch, test on DEV server.
