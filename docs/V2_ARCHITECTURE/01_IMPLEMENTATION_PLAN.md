# AI-GM V2 — Implementation Plan

> **Rule:** One task at a time. Test after each task. Discuss before moving to next.
> No task starts until the previous one passes its test checklist.
> All decisions recorded in session docs 00–05 + dated decision logs.
>
> **2026-05-18 audit pass** — full spec-vs-code audit (`AUDIT_2026_05_18.md`) corrected many ✅/❌ markers in this file; resolutions captured in `DECISIONS_2026_05_18.md`. The status markers below are now honest as of that date. **Next priority: XP loop ([D7]).**

---

## Current state snapshot (2026-05-18)

After today's audit pass:

**Fully done ✅ (per spec, no gaps):**
T01 T02 T03 T04 · T05 T06 T07 · T10 · T11 T13 · T14 T15 T17 T18 T19 · T21 T22 T23 T26 (spells) T41 · T26N T27 T29 · T30 T31 T40 · T33 (UI) T34 T43 · T46

**Partially done ⚠️ (functional but with spec gaps — see DECISIONS_2026_05_18.md):**
T08 T09 (review queue details) · T04B T12 (frontend popup) · T16 (condition rename pending) · T20 (3-slot → 8-slot pending) · T24 (no frontend label) · T25V2 T26X (no player UI for spending/log) · T28 (deceased context) · T32 T33SA · T35 (see #24) · T44 (player UI missing) · T36 T37 T38 T39 · T42

**Not started ❌:**
T45 Hero Journal

**Next priority:** XP loop ([D7]) — earning works, spending UI completely missing, no long-rest endpoint. Player progression is mechanically frozen.

**New work agreed today (not yet shipped):**
- D11 — new condition `zaskoczony` (Surprised) for stealth-ambush combat bonuses
- D2 — rename combat conditions to spec terminology (`FRIGHTENED`, `PANICKED`, `BREAK`)
- D1 — 8-slot anatomical equipment model (replaces current 3-slot)
- D6 — auth security baseline (JWT + bcrypt + lockout + roles + onboarding modal)

Implementation order locked in `DECISIONS_2026_05_18.md` § "Implementation order proposed".

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
| 42 | TASK_42_PERSISTENT_HERO | ⚠️ | Schema done (`hero_status`, `visited_location_keys`, `character_campaign_history`). Endpoints + UI **missing**: `GET /api/heroes`, `GET /characters/{id}/history`, `POST /characters/{id}/rest`, between-campaigns REST UI. See [AUDIT_2026_05_18 → D4]. |

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
| 12 | TASK_12_SKILL_TESTS | ✅ | Non-combat rolls, counter-skill matrix, roll popup |
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
| 20 | TASK_20_INVENTORY_EQUIPMENT | ⚠️ | 3 functional slots shipped (`main_hand`/`off_hand`/`armor`); **8-slot anatomical model agreed** (6 armor body parts + 2 weapon — see [DECISIONS D1]) not yet built. |
| 21 | TASK_21_SHOP_SYSTEM | ✅ | Narrative-embedded entry, buy/sell, merchant NPCs |
| 22 | TASK_22_LOOT_SYSTEM | ✅ | Location-tied, expiry rules, partial claim |
| 23 | TASK_23_HEALING_SYSTEM | ⚠️ | Items + Mend Wounds + counters ✅. **Endpointy `POST /rest?type=long|short` ❌** — wymóg dla XP loop per [D14]. Implementacja w Stage 2C (X3, X4). |
| 24 | TASK_24_WOUND_LABELS | ⚠️ | Backend `get_wound_label()` + narrator injection done. **Frontend wound-label text below player HP bar not rendered**. |
| 25V2 | TASK_25_XP_PROGRESSION_V2 | ⚠️ | Earning side ✅ (`grant_character_xp` fires on **combat.kill_*** only — 5/6 categories dead seed). Spending side ❌ (no UI). No `/rest` endpoint, no clock advance, no XP→spendable flip. **Stage 2 (4 sub-stages: 2A clock → 2B safe-rest → 2D 22 XP sources → 2C UI) per [D7+D13]. NEXT PRIORITY.** |
| 26 | TASK_26_SCHOLAR_SPELLS | ✅ | Spell list, Arcane Points, upgrade tiers, miscast scaling, rank-by-usage |
| 26X | TASK_26_XP_CONFIG_AND_LOG | ⚠️ | 22 sources seeded ✅, admin endpoints ✅. **Only 1/22 fires in code** (`combat.kill_*`). Player "Historia PD" view ❌. Wiring planned in Stage 2D (XS1–XS15). |
| 42 | TASK_42_CHARACTER_FIRST_FLOW | ✅ | Hero-first model complete — hero→campaign selection, cascade unlink on delete, session restore |
| 41 | TASK_41_DUNGEON_RUNS | ✅ | Backend + full player UI: picker modal, room types, riddle bank, square tile map, death handling, F5 restore |

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
| 31 | TASK_31_CAMPAIGN_WORKSHOP | ✅ | Campaign workshop tab inside campaign detail modal |
| 32 | TASK_32_WORLD_REVIEW_QUEUE | ✅ | Approve/reject pending world entries — Lokacje/NPC/Przeciwnicy |
| 33SA | TASK_33_SMART_ENTRY_AGENT | ⚠️ | Form-first approach built; Q&A questionnaire mode missing |
| 40 | TASK_40_WORLD_BUILDER | ✅ | Hex grid SVG, axial coords, A* travel, encounter rolls, terrain types, world builder admin tab |

### Phase 09 — Frontend
> Depends on Phase 04, 05, 06.

| Task | File | Status | Notes |
|------|------|--------|-------|
| 33 | TASK_33_HYBRID_INPUT_UI | ✅ | Context buttons + free text, suggested_actions[] API, structured bypass |
| 34 | TASK_34_COMBAT_UI | ✅ | Spell picker, initiative panel (#18), zone system (#19), crit flash (#23) — all sub-tasks complete |
| 35 | TASK_35_CHARACTER_SHEET_UI | ⚠️ | Basics shipped (header, HP/mana bars, gold, stats grid, skills, 3-slot equipment, inventory, conditions, identity, spells tab). **Spec gaps remain** — see #24: location badge, wound label, XP progress bar, level-up banner, XP spending UI, long rest, skill rank dots, mobile bottom tabs, real-time animations. |
| 43 | TASK_43_PLAYER_WORLD_MAP | ✅ | Fog-of-war world map, click-to-travel, swipe-close |
| 44 | TASK_44_DEBUG_SYSTEM | ⚠️ | Admin-only backend exists (`routers/debug.py`: `/player_state`, `/gm_decisions`, `/validation_flags`). **Missing:** player-facing debug drawer, `/debug` slash commands, admin panel "🐛 Debug" section. Per [DECISIONS D5] both player+admin sides to ship. |
| 46 | TASK_46_NARRATIVE_ITEMS | ✅ | LLM-invented items grant to inventory with `item_type='narrative'`; inv_xor constraint patched (commits c4b2d12 + 232722f) |

### Phase 10 — Polish
> Depends on everything.

| Task | File | Status | Notes |
|------|------|--------|-------|
| 36 | TASK_36_MEMORY_HISTORY | ⚠️ | `/mem` semantic search ✅, `/helpme` ✅, `campaign_history` summary generator ✅. **Missing:** dual summaries (player vs gm), session-start GM continuity injection wiring, Historia cooldown enforcement. |
| 37 | TASK_37_COMMAND_PALETTE | ⚠️ | `/help` lists commands in system bubble ✅. **Missing:** full modal with search, click-to-insert, per-command admin toggle. |
| 38 | TASK_38_CAMPAIGN_END_DEATH | ⚠️ | Death screen overlay ✅, epitaph LLM (`solo_death_service.generate_epitaph_llm`) ✅. **Missing:** epitaph wiring into UI, victory screen ending content, post-end "Nowa Przygoda/Nowy Świat" options. |
| 39 | TASK_39_AUTH_ONBOARDING | ⚠️ | Basic login + admin token works. **Missing per [DECISIONS D6]:** JWT migration, bcrypt verification, brute-force lockout, role-based access (player/gm/admin), onboarding overlay. Ship as one bundle. |
| 45 | TASK_45_HERO_JOURNAL | ❌ | Cross-campaign chronicle, chapter summaries, /mem cross-campaign, XP timeline, cross-campaign minimap. Schema for `character_campaign_history` exists from T42 — UI work starts here. |

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

---

## Out-of-Plan Work Completed

Work completed as of 2026-05-14 that was not in the original V2 plan:

### Task 42 — Character-First Flow (2026-05-14, design decision)

**Problem:** Current flow is Campaign → Character (character is created inside a campaign). This makes dungeon runs impossible to test — a hero can't enter a dungeon without first creating a campaign.

**Decision:** Invert to Character → (Campaign | Dungeon | Free Roam).

**New flow:**
1. Player lands on a **hero selection screen** — list of existing heroes or "Create new hero"
2. Character wizard runs standalone (no campaign yet) — produces a persistent `character` record
3. After hero is ready: "What's next?" screen — pick Campaign / Dungeon Run / (future: Free Roam)
4. Campaign creation links an existing hero (not creates one inline)
5. Dungeon run links an existing hero directly — no campaign needed

**DB impact:**
- `campaigns.character_id` already exists — no FK change needed
- Character creation endpoint separates from campaign creation endpoint
- A character with no active campaign is valid — "idle hero"
- `characters` table gains `status` field: `idle | in_campaign | in_dungeon`

**Frontend impact:**
- Player UI: new hero selection / creation screen before campaign/dungeon entry
- Admin UI: Campaign creation form gets "pick existing character" dropdown instead of inline wizard
- Campaign monitor: hero shown as persistent entity, not campaign-scoped

**Backend impact:**
- `POST /api/characters` — create standalone character (no campaign_id required)
- `POST /api/campaigns` — accepts `character_id`, no longer creates character inline
- `GET /api/characters/{id}` — hero profile with all campaigns + dungeon runs listed

---

### Hex Map Design Decision (2026-05-14)

**Decision:** World map uses hex grid (Honeycomb.js + SVG), replacing the planned node-edge graph (Cytoscape.js).

**1 hex = 1 hour of travel** — travel time is computed from hex path + terrain modifiers, not stored manually in `location_connections`.

**Terrain system:** Each hex cell has a terrain type (`plains`, `forest`, `mountain`, `water`, `swamp`, `road`, `city`, `dungeon`, `ruins`, `castle`). Terrain determines: travel time modifier (0.5×–2×), encounter chance (5%–40%), and visual icon/colour.

**New DB table:** `map_terrain (q, r, terrain)` — the terrain canvas, painted by admin independently of location placement.

**`location_connections.travel_hours`** becomes a derived/cache field (computed from hex pathfinding), not manually set.

**Per-hex encounter rolls:** Each hex traversed during travel rolls for a random encounter using `game_config_encounters.zone` matching the terrain type.

**Full spec:** `05_WORLD_BUILDER_AND_PERSISTENCE.md` section 1.

---

### Spell Rank Progression + Knowledge Book (2026-05-14)

**Spell rank progression by usage:**
- `character_spells.use_count` column tracks successful casts per spell per character
- `record_spell_use(character_id, spell_key, conn)` in `spell_service.py`: increments counter, auto-ranks up when threshold reached, resets counter to 0 on rank-up
- Thresholds: R1→R2 = 5 successful casts (all tiers). R2→R3 = 5 + (tier × 2). Example: Tier 1 spell needs 7 uses for R3; Tier 5 needs 15.
- Hook in `combat_service.resolve_attack()` after successful spell hit: fires for all `_is_spell and hit` outcomes
- Frontend receives `out["spell_rank_up"] = {spell_key, new_rank}` when a rank-up occurs (used for narration/notification)

**Knowledge Book:**
- `knowledge_book` table: `tip_key`, `category` (general/magic/combat/mechanics/exploration/economy), `title`, `body`, `sort_order`, `is_active`
- Admin CRUD: `GET/POST/PATCH/DELETE /api/admin/knowledge-book`
- Admin UI: **Księga Wiedzy** sidebar section (`sections/knowledge.js`) — full table, inline edit, add/edit modal
- 5 seed tips: spell_rank_progression, mana_system, nat20_nat1, conditions_stat_mods, dc_scale
- **Convention going forward:** whenever a new mechanic is designed/implemented, add a player-facing tip to `knowledge_book` seed in `migrations_admin.py`

### Campaign Version Sync / Migration Script — Design Decision (2026-05-14)

**Decision:** Build an admin-triggered campaign migration tool (not automatic, not silent).

**Context:** When game mechanics change (HP formula, new sheet fields, schema version bump) existing live campaigns must be brought forward without losing turns, narrative, or character progress. The "Campaign V2 Migration Tool" (to_do_ideas.md item #5) covers this need.

**Agreed design:**
- Triggered from admin Campaign Monitor — a "Migruj kampanię" button per campaign
- Reads `schema_version` (and optionally `game_version`) from the campaign row
- Migration is **idempotent** — re-running on an already-migrated campaign is a no-op
- V1 → V2 path: recalculate HP/Mana with V2 formula, add missing `sheet_json` fields (bonds, weaknesses, secret_predisposition) with neutral defaults, recalculate XP from turn history
- V2 → V2.x path: additive only — new fields get defaults, existing data untouched
- Each migration step is logged to a per-campaign audit log (stored in `migrations_log` JSON field or a separate table)
- Backend: a `campaign_migrator.py` service, triggered via `POST /api/admin/campaigns/{id}/migrate`
- Frontend: button in Campaign Monitor → shows a modal with a preview of what will change → confirm → progress log displayed

**Not in scope for this migration tool:**
- Automatic migration on deploy (too risky — do it admin-side deliberately)
- Bulk migration of all campaigns at once (do one at a time to catch issues)
- Rollback (the pre-migrate auto-backup via `./scripts/backup.sh` is the rollback path)

**Priority:** Medium — implement before next production schema change. Tracked in to_do_ideas.md item #5.

---

### Condition `stat_mods` applied to combat rolls (2026-05-14)

- `_combatant_stat_modifier()` in `combat_service.py` now folds `stat_mods` from all active conditions into the computed modifier
- Applies to: player attack rolls, player saves, enemy attack rolls, enemy periodic saves
- Multiple conditions stack additively; works for both sheet-based (player) and combatant-dict-based (enemy) actors
- 18 unit tests in `backend/tests/test_phase9b_t29_condition_stat_mods.py` cover baseline, single penalty, stacking, multi-stat, and conditions-without-stat-mods
- See `11_CONDITIONS_SYSTEM.md` for the updated execution model table

### Scholar Spells — Task 26 full implementation (2026-05-15)

- `backend/app/services/spell_service.py` — new service: spell lookup, mana deduction, miscast (level-scaled), Nat20 secondary effects, learn/upgrade spells, `grant_starting_spells()`
- DB: `game_config_spells` table with 9 seeded spells (magic_bolt, mend_wounds, arcane_shield, sleep, burning_arc, drain_life, chain_lightning, stone_skin, fireball) — tier 1–5, mana costs, rank 2/3 JSON upgrades
- DB: `character_spells` join table (character_id, spell_key, rank, use_count)
- `combat_service.py`: mana check + deduct before spell attack; miscast on Nat1 (stun L1-2, 1d4 self-dmg L3-4, 1d6+stun L5-7, 1d8+stun+secondary L8+); Nat20 secondary effects (d6: double/stun/zone-change/burning)
- Character creation: Scholar starts with magic_bolt + mend_wounds R1, `arcane_points=1` in sheet JSON
- Admin endpoints: GET /admin/spells, GET/POST /admin/characters/{id}/spells (learn, upgrade)

### Dungeon Runs — Task 41 full implementation (2026-05-15)

- DB: `game_dungeons` table (key, label, location_key, rooms, enemy_pool, boss_enemy, loot_tier, atmosphere, cooldown_hours, min_level) + 3 seeds: goblin_warren, rat_tunnels, crypt_of_bones
- DB: `character_dungeon_runs` table — UNIQUE per (character_id, location_key), tracks run_count + cooldown_until
- `dungeon_service.py`: `scale_enemy_stats()` level multiplier ×0.75→×2.0 (boss one tier higher, damage die stepped at ≥1.5×), `generate_dungeon_instance()` builds rooms[] with scaled stats, `enter_dungeon()` (cooldown check → generate → persist in session_flags.dungeon_run), `advance_room()` (mark cleared → next room or complete), `get_active_dungeon_run()`, `get_current_room()`
- `dungeons.py` endpoints: POST /dungeons/{key}/enter (423 on cooldown), POST /dungeons/advance-room (complete+record on last room), GET /campaigns/{id}/dungeon-run
- Admin panel: Świat → Lochy tab — list, create, edit, delete via /api/admin/dungeons

### Spells admin CRUD + content tab (2026-05-14)

- Backend: `GET /admin/spells` returns all spells (active + inactive); `POST`, `PATCH`, `DELETE` added for full spell management
- Frontend: **Zaklęcia** subtab in Content section — full table with tier/mana/type/dice columns, inline edit, add/edit modal, delete
- Weapons tab filters out `weapon_type = 'spell'` rows (already migrated to `game_config_spells` in Task 26)
- Smart Entry wired to `game_config_spells` when the Zaklęcia tab is active

### Weapon effect_json (2026-05-14)
- `effect_json TEXT DEFAULT NULL` column added to `game_config_weapons` via migration
- `_apply_weapon_effects()` method in `combat_service.py`: handles `extra_damage` (doubled on crit) and `on_hit_save` (save or take extra damage / apply condition)
- Conditions applied via weapon effect look up `game_config_conditions` for full condition data
- Legacy condition evaluation working: `skip_turn`, `damage_per_turn`, duration countdown
- Effect Builder UI in AI Kreator (Smart Entry): visual card-based editor — no raw JSON required from admin
- LLM generates valid `effect_json` from a plain-language description
- Admin Panel: `effect_json` column visible in weapon table + textarea in weapon Edit modal

### Admin Panel v2 (`frontend/admin_panel_v2/`)
- Full replacement of the old admin panel; served at `/admin2/`
- Sections: dashboard, mechanics, content (weapons/items/consumables/loot), world, narrator, players, campaigns, analytics, workshops (Bank pomysłów), voice, system
- Smart Entry v3 integrated as AI Kreator across all content sections
- Campaign detail modal: 4 tabs — Przegląd, Plan GM, Tury, Warsztat
- Plan GM tab: all arcs shown read-only, hooks rendered as lists (NPCs / Lokacje / Przedmioty)
- Świat section: builder tab placeholder + Oczekujące (pending review) sub-tab

### Session 2026-05-15 — Loot System, Admin Map, Bug Fixes

**Loot System Rework:**
- `game_config_loot_entries` rebuilt with `consumable_key` column + 3-way XOR constraint (item_key | consumable_key | weapon_key = exactly 1)
- Fixed `_finalize_phase_8h_loot_entries` that was stripping consumable_key on every restart
- New `source_type`/`source_key` API for loot entry create (frontend-driven)
- `delete_loot_entry_by_id` endpoint (`DELETE /api/admin/loot-tables/{key}/entries/by-id/{id}`)
- Admin frontend: inline editing (click weight/min/max to edit in place), source type badges

**Enemy Loot Auto-Creation:**
- `create_enemy()` in admin_config.py auto-creates `loot_{key}` table and assigns it
- `approve_entity()` in world_service.py creates loot table when pending enemy is approved
- `_backfill_enemy_loot_tables()` migration: 53 existing enemies got loot tables on restart
- Enemy edit modal (world.js + content.js): "Tabela łupów" dropdown + "Szansa na łup %" field

**Bug Fixes:**
- Campaign deletion cascade: `DELETE FROM characters` → `UPDATE SET campaign_id=NULL, status='idle'` — hero no longer deleted with its campaign
- Hero data refreshed in frontend after campaign deletion (stale campaign_id was blocking re-assignment)
- `handleNewCampaignWithHero`: always reassigns hero regardless of stale campaign_id
- `selectCampaign`: hero in wrong campaign now gets properly re-assigned instead of falling back to wizard
- Input stuck disabled: Escape key + visibilitychange recovery handler; `_skillTestPending` flag prevents premature re-enable

**Admin Campaign Monitor:**
- Delete (🗑) button on each campaign card
- New "🗺 Mapa" tab: SVG hex grid of all world hexes with campaign overlay, click-to-edit campaign-specific fields (discovered, encounter_cleared, campaign_label, campaign_notes)
- Backend: `GET /api/admin/campaigns/{id}/hex-map`, `PATCH /api/admin/campaigns/{id}/hex-map/{q}/{r}`

### Dungeon Runs — Full Design (2026-05-15)

Task 41 backend is complete. Player UI not yet built. Full design agreed:

**Flow:**
- Entry: "Loch" card on campaign selection screen (currently "Wkrótce") → Dungeon Picker modal
- Mid-campaign access: `/loch` slash command or header icon; saves `session_flags.dungeon_previous_campaign_id`, restores on exit
- Session model: Option B — disposable campaign (`mode: "dungeon"`) created on entry, deleted/ended on completion
- Hero returns to previous campaign automatically after dungeon ends

**Death:**
- Soft fail: run ends, cooldown starts, hero exits with HP = campaign state (HP they had when entering)
- Admin switch: `dungeon_death_hp_mode` in game_config: `"campaign_state"` (default) | `"one_hp"` (punishing mode)
- Future: tie to dungeon difficulty level

**Loot — Three tiers:**
- Combat rooms: `enemy.loot_table_key` (existing) + `room_loot_chance` (float) for ambient post-combat find
- Chest rooms: `chest_loot_table_key` on `game_dungeons`
- Boss room: `boss_loot_table_key` on `game_dungeons` — guaranteed drop, should include dungeon-exclusive items

**Dungeon-exclusive items:**
- `source_exclusive` TEXT column on `game_config_items` AND `game_config_weapons`
- `NULL` = everywhere, `'dungeon'` = dungeon drops only, `'boss'` = boss drops only
- Shops and regular world loot auto-filter `source_exclusive IS NOT NULL`

**Room types (configurable via `room_types_json` on dungeon):**
| Type | Frequency | Mechanic |
|------|-----------|---------|
| `combat` | ~50% | Standard fight |
| `chest` | ~15% | Auto-loot from chest_loot_table, advance immediately |
| `trap` | ~15% | Skill check (DEX/WIS), fail = damage/debuff, can still advance |
| `riddle` | ~10% | Riddle from DB bank, deterministic answer check |
| `rest` | ~5% | HP recovery, atmospheric narration |
| `boss` | Last room always | Combat, drops from boss_loot_table |

**Riddle system — Riddle Bank:**
- `game_config_riddles` table: `key`, `text`, `answer`, `answer_alts` (JSON), `hints` (JSON array), `difficulty` (1–3), `theme`, `is_active`
- Answer checking: normalize (lowercase, strip diacritics) → Levenshtein fuzzy match ~80% threshold — NO LLM for answer judging
- `dungeon_riddle_source` per dungeon: `"database"` (safe/default) | `"llm"` (experimental) | `"mixed"`
- `dungeon_riddle_max_hints` global + per-dungeon override
- LLM only narrates atmosphere, does NOT generate or judge riddles in database mode
- Admin: Riddle Bank CRUD (World section or System section), 10–15 Polish dark-fantasy seeds

**XP/Items carry-over:** Yes — `character_inventory` and `sheet_json` are `character_id`-scoped, not campaign-scoped. Dungeon loot automatically appears in main campaign.

**Schema additions needed:**
- `game_dungeons`: + `chest_loot_table_key`, `boss_loot_table_key`, `room_loot_chance`, `room_types_json`, `riddle_source`, `riddle_max_hints`
- `game_config_riddles`: new table
- `game_config_items` + `game_config_weapons`: + `source_exclusive TEXT`
- `game_config` key: `dungeon_death_hp_mode`

### GM Narrative Formatting (2026-05-15)

Distinguish narrative types inside GM chat bubbles:
- **Dialog** (`„..."` Polish quotes, `—` em-dash lines): italic + warm amber color `#d4a565`, left border accent on em-dash paragraphs
- **Description**: unchanged default styling
- **Inline mixing**: single paragraph can have both — quoted spans get italic/amber, surrounding text stays default
- Implemented in `formatGmNarrative()` replacing `formatMessageContent()` for GM bubbles only
- No new fonts — italic + color is sufficient for the dark fantasy context

### Dungeon V2 — Final State (2026-05-16)

**What was built (complete):**

#### Backend
- `game_dungeons` extended: `chest_loot_table_key`, `boss_loot_table_key`, `room_loot_chance`, `room_types_json`, `riddle_source`, `riddle_max_hints`
- `game_config_riddles` table: `key`, `text`, `answer`, `answer_alts` (JSON), `hints` (JSON), `difficulty` (1–3), `theme`, `is_active`
- 12 Polish dark-fantasy riddles seeded (difficulties 1–3, themes: general/dungeon/magic/nature/death)
- `source_exclusive` on `game_config_items` + `game_config_weapons`: NULL=everywhere, `'dungeon'`=dungeon only, `'boss'`=boss only
- `game_config_meta` keys: `dungeon_death_hp_mode` (campaign_state|one_hp), `dungeon_riddle_max_hints` (default 2)
- `dungeon_service.py`: room type generation (combat/chest/trap/riddle/rest/boss), riddle pick from DB, deterministic fuzzy answer check (Levenshtein 80%), chest/boss loot rolling, death handling
- New API endpoints: `POST /dungeons/resolve-room` (riddle/trap/chest/rest), `POST /dungeons/death`, `POST /dungeons/exit`
- Admin API: `GET/POST/PATCH/DELETE /api/admin/riddles`

#### Player Frontend (`frontend/front/`)
- **"Loch" card** on campaign selection (amber styled, active)
- **Dungeon Picker modal**: lists all dungeons with cooldown badges and atmosphere preview
- **Dungeon HUD**: fixed bar below game header showing dungeon name + room progress pips (icons per type) + advance/map/exit buttons. Hidden on all non-game screens.
- **Dungeon Map** (`#dungeon-map-overlay`): slide-up square tile grid, revealed room by room, auto-opens on first advance
- **Riddle panel** (`#dungeon-riddle-panel`): text input + submit + hint button
- **Dungeon Complete overlay**: boss loot list + cooldown timer + exit
- F5 restore: detects `mode='dungeon'` on campaign, restores `_activeDungeonRun` + HUD
- Disposable campaign model: dungeon creates tmp campaign (`mode='dungeon'`), deleted on exit

#### Admin Panel (`frontend/admin_panel_v2/`)
- **Świat → Lochy tab**: dungeon editor now includes chest/boss loot table keys, room_loot_chance, riddle_source, riddle_max_hints
- **Świat → Zagadki tab** (NEW): full CRUD for `game_config_riddles` — list/add/edit/delete riddles with multi-line answer_alts and hints editors
- Loot tables: 3 dungeon chest tables created (`chest_goblin_warren`, `chest_rat_tunnels`, `chest_crypt_of_bones`)

#### Riddle System Design
- Riddle bank (`game_config_riddles`) is the default mode — answers checked deterministically
- `riddle_source` per dungeon: `"database"` (safe, default), `"llm"` (experimental), `"mixed"`
- Answer normalization: lowercase + strip diacritics → exact match OR Levenshtein ≤ 20% edit distance
- `riddle_max_hints` (global default: 2, per-dungeon override): LLM reveals hints from `hints[]` array in order
- On hints exhausted: automatic fail penalty (1d4 damage) but player can still advance
- LLM only narrates the room atmosphere — does NOT generate or judge riddle answers in database mode

#### 34 Dungeon/Boss-Exclusive Items Created
- 4 boss weapons (on-hit conditions), 2 dungeon weapons
- 11 boss items (armor, misc, consumables — boss quality)
- 17 dungeon items (consumables, armor, misc)
- All items use only supported effects: `heal_hp`, `restore_mana`, `remove_condition`, `apply_condition`, `narrative_only`
- `stat_buff`, `death_ward`, `passive`, `aoe` effects are NOT supported by the engine and were converted

### Session 2026-05-16 — Dungeon Polish, Skill Tests, Data Cleanup

**Dungeon runs — final polish:**
- Dungeon HUD hidden on all non-game screens (wizard, heroes, campaigns); restored on return to game
- Pre-LLM skill test keyword scan: player text checked against `trigger_keywords` BEFORE the LLM is called — no longer depends on LLM generating a `[SKILL_TEST:]` tag
- Fixed trigger_keywords split: was comma-split, keywords are space-separated — now supports both
- `_roll_dice_value` extended to handle `NdN+bonus` format (e.g. `"2d6+2"`) — was breaking healing potions
- Rogue archetype added to character creation wizard: 🏹 card with `+2 ZRĘ · +1 SZCZ · HP: 8`, shortbow + dagger starter kit
- Lockpicking skill added: `Otwieranie Zamków` (DEX), trigger keywords for locks/doors/chests

**Admin panel — dungeon editor:**
- Riddle Bank CRUD: `Świat → 🔮 Zagadki` — full add/edit/delete with multi-line answer_alts and hints
- Backend: `GET/POST/PATCH/DELETE /api/admin/riddles`
- Dungeon modal updated with V2 fields: chest/boss loot table keys, room_loot_chance, riddle_source, riddle_max_hints
- Dungeon AI generator: floating 🤖 FAB in bottom-right corner → slide-up chat panel; generates dungeon from plain Polish description; AI pre-fills form or saves directly
- Backend: `game_dungeons` added as `AssistantResourceLiteral` resource type

**Game data cleanup:**
- Stats: all 6 translated to Polish (Siła, Zręczność, Kondycja, Inteligencja, Mądrość, Charyzma)
- Skills: all 16 translated to Polish + trigger_keywords filled for all
- Conditions: 7 existing + 6 new (Spowolniony, Osłabiony, Ogarnięty Paniką, Sparaliżowany, Uciszony, Niewidzialny); `auto_remove` turn counts filled; `poisoned` → Polish
- DC: all 5 descriptions filled
- Spells: all 9 have Rank 2 + Rank 3 JSON
- Items: `effect_json` filled for all healing potions, mana potions, bandages, antidotes, consumables
- Archetypes: JSON fixed (was malformed), `hp_base` + `starter_gold_gp` editable
- Dungeon/boss items: 34 exclusive items created (4 boss weapons, 2 dungeon weapons, 11 boss items, 17 dungeon items), all using only supported effects
- `source_exclusive` column added to items + weapons (NULL/dungeon/boss)

**Admin UI fixes:**
- Items table: added `Opis`, `Efekt`, `Źródło` columns; modal includes `effect_json` + `source_exclusive`
- Weapons table: `Szkoła Magii` column hidden (spells moved to separate tab)
- Loot table sidebar: scrollable (fixed `height: 100%` + `overflow: hidden` on panel)
- Loot entries: scrollable (max-height: 340px) + search filter with count
- Archetypes: `hp_base`, `starter_gold_gp`, `starter_items_json` now visible and editable

### Session 2026-05-17/18 — T34 Combat UI completed, Combat Sandbox, bug audit

**T34 Combat UI — all sub-tasks shipped:**
- **Initiative panel** (issue #18, commit `6d9ba8a`): horizontal chip track above combat banner; player + enemies in initiative order; active chip gold-glow + downward caret; "acted this round" dims to 0.45 opacity; round-end sweep animation resets state; downed combatants greyscale + diagonal slash; mobile horizontal scroll.
- **Zone system** (issue #19, commits `b8bbf11` backend + `d57953f` frontend): two-zone model per `04_MAGIC_RANGE_MAP.md §4`. Combatants get `zone: 'engaged' | 'ranged'` on combat start (scholar→ranged, warrior→engaged, enemies via keyword heuristic). Player melee gating: out-of-range targets return `{blocked, block_reason: 'out_of_range'}` without consuming the turn. Enemy AI: melee enemy in wrong zone charges (consumes turn, no attack). New `POST /api/campaigns/{id}/combat/zone-change` endpoint. Frontend splits combat banner into DYSTANS/ZWARCIE columns + composer Zbliż się/Cofnij się button + initiative-chip zone glyph.
- **Crit flash** (issue #23, commit `74c350a`): theatrical full-viewport overlay on Nat 20 / Nat 1 from both attacks and skill tests. Crit = inverse vignette with four gold beams + "CIOS KRYTYCZNY" in Cinzel. Fumble = blood-red vignette closing in + "FATALNE PUDŁO" with cracked text shadow + 180 ms viewport shake. CSS-only motion, `pointer-events: none`, honors `prefers-reduced-motion`.

**Combat Sandbox** (issue #21, commits `6fa73bf` → `f91e45f` → many follow-ups):
- New admin panel section at `/admin2/` → ⚔ Sandbox. Reuses production combat engine — anything verified there matches real gameplay.
- Backend router `backend/app/routers/sandbox.py` at `/api/admin/sandbox/*`: `/heroes`, `/enemies`, `/setup`, `/start-combat`, `/reset-hero`, `/end-combat`, `/advance-turn`, `/character/{id}`.
- **Hero isolation**: every `/setup` creates a disposable clone of the chosen hero (`name='[SBX] <orig>'`, `sheet_json.__sandbox_clone__=true`). Inventory + spells cloned via `character_inventory` and `character_spells` copy. Original hero never touched even on sandbox death. Prior clones purged on each setup (FK cascade drops their data). `/heroes` filters clones from the picker.
- **Layout**: 3-column responsive — Setup + Character Sheet card / Live combat state + actions / Log + 📋 Kopiuj raport. Sheet card shows HP+mana bars, 7-stat grid, conditions, inventory grouped by type with Załóż/Zdejmij/Użyj buttons (shield routes to `off_hand`, second weapon auto-routes to dual-wield), spells chip row, ✨ Czar picker for Scholar.
- **Combat events feed**: mirrors player UI roll cards (d20 + modifier vs AC, hit/miss, damage, weapon used) — filtered to the active combat's `combat_id` so prior fights don't leak.
- **Auto-enemy-turn**: 750 ms after every player action; manual ⏭ Tura wroga retained as override.
- **Copy report**: structured markdown bundle (hero + inventory + spells + combat state + events + log) for pasting into bug reports.
- **Companion issue #22** filed for Playwright autotest harness scaling this to scripted scenarios.

**Bug fixes & audits:**
- Issue #20 (phantom skill tests) — narrowed at first (excluded `key='attack'` from pre-LLM keyword scan), then broadened on Geralt regression. New `_COMBAT_CLASS_SKILLS` sentinel covers `attack / ranged_attack / two_handed / melee_attack / spell_attack / initiative`. RAW_MIGRATIONS trimmed `kowalstwo` trigger_keywords (removed weapon nouns `metal ostrze zbroja miecz jakość`) and cleared `initiative` entirely. Full skill-by-skill audit posted on issue.
- Issue #15 (F5 roll persistence) — new `GET /api/campaigns/{id}/combat/turns/history` endpoint returns every `combat_turns` row for the campaign across all combats (not just active). Skill-test persistence extended with full `[Rzut: skill — d20 ±mod = total — Outcome]` format so hydration reconstructs the rich roll card. Frontend interleaves campaign turns + combat history by `created_at`.
- Issue #10 (Scholar offensive spells) — `create_standalone_character` (modern hero-first flow) now calls `grant_starting_spells(char_id, conn)` for `archetype='scholar'`. Was previously only on the legacy campaign-scoped path; affected scholars backfilled.
- Issue #16 (loot table search) — new search input + client-side filter on the loot-tables sidebar.
- Combat banner buttons mobile fix: `.combat-composer` padding-bottom adds `env(safe-area-inset-bottom)` and `@media (max-width: 480px)` compresses padding/font/icons so all three buttons fit on phones.

**Documentation:**
- T34 line in this file flipped to ✅ with sub-task issue links.
- T46 line flipped to ✅ — narrative items shipped commit `c4b2d12`.
- T33 line flipped to ✅ for structured action bypass.

**Workflow rule codified in CLAUDE.md** — every implementation now requires a GitHub issue with structured sections (Task / What was implemented / Files changed / Backend / Numbers Policy / Acceptance / Out of scope) and `needs-testing` label until visually verified.

---

### T47a — Turn Cancel: Client-Side Abort ❌

**Status:** Planned  
**Priority:** Medium — pure UX polish, no backend dependency

**Problem:** Once the player hits Send, they are locked out until the LLM finishes — even if they immediately realize they want to rephrase or add context. On mobile there is no ESC key to fall back on.

**What it delivers:**
- A **✕ Cofnij** pill button appears in the composer area the moment a turn is submitted, stays visible until the GM response arrives
- Pressing ESC (desktop) or tapping ✕ Cofnij (mobile) aborts the pending `fetch()` via `AbortController`
- The player's original message text is restored to the input field
- The "typing…" / loading state is cleared and the player bubble removed from chat
- A brief toast "Wiadomość cofnięta — możesz poprawić" confirms the cancel
- If the LLM already finished streaming before the user cancels, the cancel is ignored (response is shown normally)

**Scope:**
- Only the client-side fetch is aborted — the backend LLM call continues running until it finishes, then the response is discarded (server never knows a cancel happened)
- This is acceptable because: turns are not persisted until the full response is written to `campaign_turns`, so a cancelled turn leaves no DB trace
- Token/time waste on the server for the abandoned call is the accepted tradeoff

**Files to change:** `frontend/front/js/app.js`, `frontend/front/css/styles.css`, `frontend/front/index.html`

---

### T47b — Turn Cancel: Server-Side Kill ❌

**Status:** Planned — implement after T47a, only if token waste becomes a real problem  
**Priority:** Low

**Problem:** After T47a, cancelled turns still burn LLM tokens on the server because `AbortController` only severs the HTTP connection — the FastAPI streaming generator keeps running.

**What it would deliver:**
- `POST /api/campaigns/{id}/turns/cancel` endpoint that:
  1. Checks a per-campaign "cancel requested" flag in `session_flags`
  2. The streaming generator in `turns.py` polls `request.is_disconnected()` (already available in Starlette) or checks the flag every N tokens and raises `asyncio.CancelledError` to break out early
  3. Returns 200 immediately; the generator notices on its next yield and exits
- No partial turn is persisted (the INSERT happens only on normal completion)

**Complexity assessment:**
- **Medium-hard.** Not technically difficult, but requires careful async coordination:
  1. The turn endpoint is a synchronous FastAPI route run in a thread pool — `request.is_disconnected()` requires `await` so the streaming generator would need to be converted to `async def` or the cancel flag approach used instead
  2. The cancel-flag approach (write `session_flags.cancel_requested=true` → generator reads it) is simpler but adds a DB read per streaming chunk
  3. Ollama, OpenAI, and Azure each have different httpx streaming contexts — the cancellation must be tested on all three drivers independently
  4. A race condition exists: if the cancel arrives after the LLM finishes but before the INSERT, the turn should still be discarded — requires a post-stream cancel check
  5. The `/cancel` endpoint itself needs auth (player can only cancel their own active turn)
- **Estimate:** ~4–6 hours including testing on all three LLM drivers

**Files to change:** `backend/app/api/turns.py` (all three streaming paths), `backend/app/services/llm_service.py` (yield-loop break), new `POST /cancel` route, `frontend/front/js/app.js` (fire cancel request before aborting fetch)
