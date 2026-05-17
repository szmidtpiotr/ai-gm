# AI-GM V2 — Roadmap

> Tree of all tasks ordered by implementation sequence.  
> **Legend:** `[x]` = done · `[-]` = partial/in-progress · `[ ]` = pending  
> **Auto-updated** by Claude after each completed task/subtask.  
> Spec details → `docs/V2_ARCHITECTURE/01_IMPLEMENTATION_PLAN.md`

---

## Phase 01 — Foundation
- [x] **T01 DB Schema** — all tables, state definitions, location_connections
- [x] **T02 Intent Parser** — player text → ACTION tag
- [x] **T03 World State Machine** — validate actions, transition states
- [x] **T04 Context Injector** — narrator prompt from DB + mechanical result
- [x] **T04B Opening Scene** — first GM turn after character finalization

---

## Phase 02 — Character
- [x] **T05 HP/Mana Formulas** — HP = base + CON_mod × level · Mana = 8 + INT_mod × level
- [x] **T06 Character Wizard**
  - [x] 4-step wizard (name/archetype → stats → skills → identity)
  - [x] Warrior · Scholar archetypes
  - [x] Łotrzyk (Rogue) archetype — DEX+2 · LCK+1 · HP 8 · shortbow starter
  - [x] LCK (Szczęście) as 7th stat in wizard + sheet
  - [x] Stat tooltips on `?` hover — instant custom tooltip (no native delay)
  - [x] Skill descriptions with Polish labels and hints in wizard
  - [x] Rogue accepted by backend (was silently converting to warrior)
- [x] **T07 Campaign Plan Generation** — LLM generates from character + Ideas Bank
- [x] **T42 Persistent Hero / Character-First Flow**
  - [x] Hero exists independently of campaigns (status: idle/in_campaign)
  - [x] Campaign deletion frees hero (SET NULL, not DELETE)
  - [x] Hero refreshed in frontend after campaign deletion
  - [x] Wizard always clears stale `currentCampaignId` when creating new hero
  - [x] `assign-campaign` frees previous hero before assigning new one
  - [x] Session flags cleared when new hero assigned to campaign

---

## Phase 03 — World
- [x] **T08 Location System** — badge, safe_for_rest, connections
- [x] **T09 NPC System** — personality DB, keyword triggers, dialogue hooks
- [x] **T10 Data Tables** — lookup-before-create, pending_review queue

---

## Phase 04 — Gameplay Loop
- [x] **T11 Turn Pipeline** — 9-step pipeline in turn_pipeline.py
- [x] **T12 Skill Tests**
  - [x] Non-combat rolls, roll popup with d20 animation
  - [x] Pre-LLM keyword scan — triggers test before LLM call
  - [x] Word-boundary matching + min 5-char keywords (fixes "się" matching everything)
  - [x] Skill test result saved to campaign_turns (survives F5)
  - [x] Roll result shown in chat after confirmation
- [x] **T13 Campaign Plan V2** — runtime schema, deviation detection, GM tags
- [x] **T04B Opening Scene** _(listed above)_

---

## Phase 05 — Combat
- [x] **T14 Combat State Machine** — initiative, round flow, range zones, enemy auto-turn
- [x] **T15 Enemy AI Rules** — behavior profiles in DB, rule-based decisions
- [x] **T16 Fear/Terror** — WIS save, FRIGHTENED/PANICKED/BREAK conditions
- [x] **T17 Critical Hits** — threshold + hit location table + lasting effects
- [x] **T18 Death Saves** — escalating DC 10/13/16/19, CON modifier
- [x] **T19 Flee Mechanic** — opposed DEX, loot abandoned, zone change

---

## Phase 06 — Economy
- [x] **T20 Inventory & Equipment** — slots, click-to-equip, combat restrictions
- [x] **T21 Shop System** — narrative-embedded entry, buy/sell, merchant NPCs
- [x] **T22 Loot System**
  - [x] 3-way XOR entries (item_key · consumable_key · weapon_key)
  - [x] Admin inline editing (click weight/qty to edit)
  - [x] Type badges (Przedmiot · Materiał · Broń)
  - [x] Delete by ID endpoint
  - [x] Enemy loot tables auto-created on create/approve
  - [x] 55 enemy loot tables backfilled
  - [x] Dungeon chest + boss loot tables
- [x] **T23 Healing System** — items, rest, Scholar Mend Wounds
- [x] **T24 Wound Labels** — HP% thresholds, narrator injection, HP bar color
- [x] **T25 XP Progression V2** — WFRP style, everything purchased with XP
- [x] **T26 Scholar Spells**
  - [x] 9 spells (tiers 1–5), mana system, miscast scaling
  - [x] Rank 2 + Rank 3 JSON for all spells
  - [x] Arcane Points tracking
  - [x] Spell tab in character sheet (Scholar only)
  - [x] Spell picker in combat (Scholar — "Zaklęcie" button)
  - [x] `spell_key` flows through resolve-attack to combat service
- [x] **T41 Dungeon Runs**
  - [x] Backend: room types (combat/chest/trap/riddle/rest/boss)
  - [x] Riddle bank (12 Polish riddles, deterministic answer checking)
  - [x] Loot tiers (enemy · chest · boss)
  - [x] `source_exclusive` on items/weapons (NULL · dungeon · boss)
  - [x] Death handling + session isolation
  - [x] Player UI: dungeon picker modal
  - [x] Player UI: dungeon HUD (room progress pips, icons per type)
  - [x] Player UI: square tile map (Betrayal at House on the Hill style)
    - [x] Tiles hidden until entered
    - [x] Auto-opens on first advance (teaches the mechanic)
    - [x] 🗺 button in HUD to reopen anytime
  - [x] Player UI: riddle input panel with hints
  - [x] Player UI: dungeon complete overlay with boss loot
  - [x] F5 restore (detects mode='dungeon', restores HUD)
  - [x] HUD aligned to game column width (not full browser)
  - [x] HUD hidden on non-game screens (wizard, hero/campaign select)
  - [x] Admin: dungeon editor updated (chest/boss loot, riddle settings)
  - [x] Admin: Riddle Bank CRUD (Świat → Zagadki tab)
  - [x] Admin: AI Kreator dla Lochu (floating 🤖 FAB)
  - [x] 34 dungeon/boss-exclusive items created
- [x] **T46 Narrative Items**
  - [x] `character_inventory.label` column (free-form items)
  - [x] Narrative items (notes, amulets) → inventory rows, visible in lore section
  - [x] Drop button (✕) for narrative items with description tooltip
  - [x] `game_config_weapons.campaign_id` + `review_status` columns
  - [x] Narrative weapons detected by label keywords → pending DB weapon, equippable immediately
  - [x] Admin review: Zatwierdź (global) · Zachowaj (campaign-scoped) · Odrzuć
  - [x] Pending weapons in Oczekujące → ⚔ Broń section with edit modal
  - [x] Migrate old `sheet_json.narrative_items` to inventory rows on startup
  - [x] System prompt reinforced: always `Grant Item` on ANY physical pickup
  - [x] Spec: `docs/V2_ARCHITECTURE/TASK_NARRATIVE_ITEMS.md`

---

## Phase 07 — Narrator
- [x] **T26N Narrator Engine** — system prompt, constraints, post-processing
- [x] **T27 Combat Narration** — per-action, parallelised, fallback templates
- [x] **T28 NPC Dialogue** — in-character, keyword triggers, session memory
- [x] **T29 Scene Narration** — exploration, movement, rest, skill outcomes

---

## Phase 08 — Admin
- [x] **T30 Ideas Workshop** — AI agent co-authoring for Ideas Bank
- [x] **T31 Campaign Workshop** — chat tab inside campaign modal
- [x] **T32 World Review Queue** — approve/reject Lokacje · NPC · Przeciwnicy
- [-] **T33SA Smart Entry Agent** — form-first built; Q&A guided mode missing
- [x] **T40 World Builder (Hex Grid)**
  - [x] SVG hex grid, axial coords, A* travel
  - [x] Terrain types, encounter rolls, atmosphere
  - [x] World builder admin tab
  - [x] Admin campaign map tab (Mapa in campaign modal)
  - [x] Click hex to edit campaign overlay fields (discovered, label, notes)

### Extra Admin work (not in original plan)
- [x] **Admin data cleanup** — Polish labels for all stats/skills/conditions/DC
- [x] **Loot table admin** — inline editing, scrollable sidebar with search
- [x] **Enemy modal** — loot table + drop chance fields (world.js + content.js)
- [x] **Archetype admin** — hp_base + starter_gold editable, starter_items visible
- [x] **Items table** — effect_json · source_exclusive columns shown + editable
- [x] **Weapons table** — magic_school column hidden
- [x] **Campaign monitor** — delete button on cards, Mapa tab with hex editor
- [x] **Dungeon admin** — AI Kreator (floating FAB), riddle bank, full V2 fields

---

## Phase 09 — Frontend (Player UI)
- [ ] **T33 Hybrid Input UI** — context buttons, suggested_actions[] from backend
- [-] **T34 Combat UI**
  - [x] Spell picker (Scholar — floating overlay, mana check)
  - [ ] Initiative panel showing turn order
  - [ ] Zone display (engaged/ranged/distant)
  - [ ] Crit flash animation
- [x] **T35 Character Sheet UI**
  - [x] Stats tab: HP bar · Mana bar (Scholar) · Level · XP · LCK
  - [x] Stat modifiers (+2 green / -1 red / +0 grey)
  - [x] Conditions section (active conditions with chip badges)
  - [x] Arcane Points (Scholar)
  - [x] Skills tab (trained skills with rank/ceiling, tap for description)
  - [x] Inventory tab (equipment slots, backpack, lore items, gold)
  - [x] Spells tab (Scholar only — spell cards with mana cost, rank pips)
  - [x] Identity/lore tab (backstory, appearance, personality, bonds)
- [x] **T43 Player World Map** — fog-of-war hex grid, click-to-travel, swipe-close
- [ ] **T44 Debug System** — admin debug drawer, /debug commands, DB key display

### Extra Frontend work
- [x] **GM narrative formatting** — dialog italic amber · em-dash speech border
- [x] **Skill test roll popup** — centered, light yellow parchment background
- [x] **Fast custom tooltip** — instant `data-tooltip` (replaces 750ms native delay)
- [x] **F5 session restore** — localStorage (hero_id + campaign_id), works cross-refresh
- [x] **Input stuck fix** — Escape + visibilitychange recovery, `_skillTestPending` flag

---

## Phase 10 — Polish
- [ ] **T36 Memory/History** — /mem command (superseded by Hero Journal below)
- [ ] **T37 Command Palette** — /help modal, admin command toggles
- [ ] **T38 Campaign End/Death** — victory screen, death screen, post-death options
- [ ] **T39 Auth/Onboarding** — auth flow, first-time UX
- [ ] **T45 Hero Journal** — cross-campaign chronicle, chapter summaries, /mem

---

## Phase 11 — Observability
- [ ] **T47 Game Event Logging** — `game_events` table, event_logger service
- [ ] **T48 LLM Call Log** — `llm_call_log` table, admin viewer
- [ ] **T49 Admin Analytics Panel** — dashboard/events/LLM tabs
- [ ] **T50 MCP Server** — 9 tools for AI-queryable game data

---

## Phase 12 — AI Test Agent _(after all phases complete)_

> Rework the existing `ai_test_agent/` (Playwright + Express + LLM orchestrator) to run automated adversarial and regression tests against the full game.
> The agent uses an LLM to play the game autonomously — reading UI snapshots, deciding what to type/click, Playwright executes it.

- [ ] **T51 Update agent for current UI** — rewrite selectors for hero-first flow (no legacy `#campaign-select`)
- [ ] **T52 Regression scenario: baseline flow** — login → create hero → start campaign → complete first turn → verify GM responds
- [ ] **T53 Regression scenario: dungeon run** — enter dungeon → clear 3 rooms → boss → exit → verify loot in inventory
- [ ] **T54 Adversarial: inventory exploit** — LLM tries to duplicate items via GM dialogue → verify economy integrity
- [ ] **T55 Adversarial: economy cheat** — LLM tries to get gold/XP illegitimately → verify system resists
- [ ] **T56 Adversarial: prompt injection** — LLM sends malicious player text → verify GM doesn't break system prompt
- [ ] **T57 LLM consistency test** — run `honest_player_flow` scenario 10× → compare XP, location, quest outcomes for drift
- [ ] **T58 Admin panel: Test Runner UI** — update the test runner section in admin to trigger scenarios and show results
- [ ] **T59 CI integration** — run baseline regression automatically after each deploy on DEV

---

## Progress Summary

```
Phase 01  Foundation        ████████████  5/5   100%
Phase 02  Character         ████████████  4/4   100%  (incl. T42)
Phase 03  World             ████████████  3/3   100%
Phase 04  Gameplay Loop     ████████████  4/4   100%
Phase 05  Combat            ████████████  6/6   100%
Phase 06  Economy           ████████░░░░  8/9    89%  (T46 pending)
Phase 07  Narrator          ████████████  4/4   100%
Phase 08  Admin             ████████████  5/5   100%  (+extras)
Phase 09  Frontend          ████████░░░░  3/5    60%  (T33, T34 partial, T44 pending)
Phase 10  Polish            ░░░░░░░░░░░░  0/5     0%
Phase 11  Observability     ░░░░░░░░░░░░  0/4     0%
Phase 12  AI Test Agent     ░░░░░░░░░░░░  0/9     0%  (after all phases)

Overall:  ~~~~~~~~~~~~~~~~  42/63   67%
```
