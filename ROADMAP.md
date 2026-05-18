# AI-GM V2 — Roadmap

> Tree of all tasks ordered by implementation sequence.
> **Legend:** `[x]` = done · `[-]` = partial/in-progress · `[ ]` = pending
> **Auto-updated** by Claude after each completed task/subtask.
> Spec details → `docs/V2_ARCHITECTURE/01_IMPLEMENTATION_PLAN.md`
> **2026-05-18 audit** corrected several boxes — see `docs/V2_ARCHITECTURE/AUDIT_2026_05_18.md` + `DECISIONS_2026_05_18.md`.

---

## 📍 Next priority (per [DECISIONS D7])

**XP loop** — earning works, spending UI completely missing. Player progression is mechanically frozen.

Minimum viable order:
1. XP progress bar + level display in character sheet
2. `POST /api/characters/{id}/rest` long-rest endpoint (flips pending XP → spendable)
3. Skill rank-up UI (cards, cost shown, click → spend → confirm)
4. Stat point-up UI (same UX)
5. Level-up notification banner per spec
6. Player "Historia PD" XP log view

After XP loop, queue continues in `DECISIONS_2026_05_18.md` § "Implementation order".

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
  - [x] Warrior · Scholar · Rogue (Łotrzyk) archetypes
  - [x] LCK (Szczęście) as 7th stat
  - [x] Stat/skill tooltips
- [x] **T07 Campaign Plan Generation** — LLM generates from character + Ideas Bank
- [-] **T42 Persistent Hero / Character-First Flow**
  - [x] Hero exists independently of campaigns (status: idle/in_campaign)
  - [x] Campaign deletion frees hero (SET NULL, not DELETE)
  - [x] `hero_status`, `visited_location_keys` columns
  - [x] `character_campaign_history` table
  - [x] Session flags cleared when new hero assigned
  - [ ] `GET /api/heroes` endpoint (list heroes across users)
  - [ ] `GET /api/characters/{id}/history` endpoint
  - [ ] `POST /api/characters/{id}/rest` endpoint (long rest)
  - [ ] Between-campaigns REST state UI (XP spending, hero journal access)
  - [ ] Fallen Hero → NPC promotion admin flow

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
  - [x] Word-boundary matching + min 5-char keywords
  - [x] Skill test result saved to campaign_turns (survives F5)
  - [x] Combat-class skills (`attack`/`ranged_attack`/`two_handed`/`initiative`) excluded from keyword scan
  - [x] `kowalstwo` trigger_keywords trimmed of weapon nouns
- [x] **T13 Campaign Plan V2** — runtime schema, deviation detection, GM tags
- [x] **T04B Opening Scene** _(listed above)_

---

## Phase 05 — Combat

- [x] **T14 Combat State Machine** — initiative, round flow, range zones, enemy auto-turn
- [x] **T15 Enemy AI Rules** — behavior profiles in DB, rule-based decisions
- [-] **T16 Fear/Terror** — WIS save, escalating conditions
  - [x] Trigger logic + DC ladder + Nat 1 escalation
  - [x] FEAR_IMMUNE tracking per entity type
  - [x] BREAK forced-flee logic
  - [ ] **Rename condition keys** `fear_shaken` → `FRIGHTENED`, `terror` → `PANICKED`, `break` → `BREAK` per [D2] (idempotent migration on startup)
- [x] **T17 Critical Hits** — threshold + hit location table + lasting effects
- [x] **T18 Death Saves** — escalating DC 10/13/16/19, pure d20
- [x] **T19 Flee Mechanic** — opposed DEX, loot abandoned, zone change
- [ ] **🆕 `zaskoczony` (Surprised) condition** _(added 2026-05-18 per [D11])_
  - [ ] DB row in `game_config_conditions` with Polish label
  - [ ] Backend: +2 ATK + first hit ×2 damage hooks in `combat_service`
  - [ ] Auto-clear on damage taken OR round expiry
  - [ ] Frontend: ⚡ badge on initiative chip + combatant row
  - [ ] Triggered by player Stealth success (Easy DC 8 alone / Hard DC 16 group)

---

## Phase 06 — Economy

- [-] **T20 Inventory & Equipment** — _3-slot shipped, 8-slot anatomical model agreed per [D1]_
  - [x] 3-slot functional system (main_hand · off_hand · armor) shipped
  - [x] Click-to-equip, combat restrictions, auto-pick (shield→off_hand, dual-wield→off_hand)
  - [ ] **Migrate to 8 slots**: head · torso · l_arm · r_arm · l_leg · r_leg · main_hand · off_hand
  - [ ] `game_config_items.armor_coverage` column (`head`/`torso`/`limb_arm`/`limb_leg`/`full`)
  - [ ] No new gloves/boots types — boots = leg armor, gloves = arm armor
  - [ ] Anatomical slot diagram in character sheet (replaces 3-card triptych)
- [x] **T21 Shop System** — narrative-embedded entry, buy/sell, merchant NPCs
- [x] **T22 Loot System**
  - [x] 3-way XOR entries, admin inline editing, type badges
  - [x] Enemy loot tables auto-created on create/approve (55 backfilled)
  - [x] Dungeon chest + boss loot tables
  - [x] Loot table sidebar search ([#16])
- [x] **T23 Healing System** — items, rest, Scholar Mend Wounds
- [-] **T24 Wound Labels** — backend done, frontend rendering missing
  - [x] `get_wound_label()` helper with 5 thresholds + colors
  - [x] Narrator injection (`wound_label` in turn response)
  - [ ] Render wound-label text below player HP bar in character sheet
  - [ ] Render wound-label text below player HP bar in combat banner
- [-] **T25V2 XP Progression V2** — _**earning works · spending UI missing — NEXT PRIORITY [D7]**_
  - [x] `grant_character_xp` fires on enemy defeat
  - [x] XP awards table seeded (22 sources, 6 categories)
  - [x] Backend endpoints: `spend_skill_rank_up`, `spend_stat_point_up`
  - [x] Admin "mg" manual grant
  - [ ] Player XP progress bar (current / next-level)
  - [ ] Level display in header (`floor(xp_total / 100)`)
  - [ ] `POST /api/characters/{id}/rest` long-rest endpoint
  - [ ] Player "Awansuj" panel — skill cards, stat cards, spell cards
  - [ ] Level-up notification banner
- [-] **T26X XP Config + Log** — admin done, player Historia PD missing
  - [x] `game_config_xp_awards` editable by admin
  - [x] `character_xp_grants` audit log
  - [x] Admin `/xp-report` aggregated by category
  - [ ] Player-facing "Historia PD" view in character sheet
- [x] **T26 Scholar Spells**
  - [x] 9 spells (tiers 1–5), mana system, miscast scaling
  - [x] Rank 2 + Rank 3 JSON for all spells
  - [x] Spell tab in character sheet (Scholar only)
  - [x] Spell picker in combat (Zaklęcie button)
  - [x] Standalone hero flow grants starting spells (`magic_bolt` + `mend_wounds`)
- [x] **T41 Dungeon Runs**
  - [x] Backend: room types, riddle bank, loot tiers, `source_exclusive`
  - [x] Player UI: picker modal, HUD, square tile map, riddle panel, complete overlay
  - [x] F5 restore + HUD scope rules + admin editor + AI Kreator
- [x] **T46 Narrative Items**
  - [x] `character_inventory.label` column + frontend lore section
  - [x] Narrative weapon detection + pending review flow
  - [x] Admin review: Zatwierdź (global) · Zachowaj (campaign) · Odrzuć

---

## Phase 07 — Narrator

- [x] **T26N Narrator Engine** — system prompt, constraints, post-processing
- [x] **T27 Combat Narration** — per-action, parallelised, fallback templates
- [-] **T28 NPC Dialogue** — in-character, keyword triggers, session memory
  - [x] Core dialogue request schema + LLM prompt
  - [x] `must_reveal_info` enforcement + reluctance markers
  - [ ] Deceased NPC `relationship` field (ally/enemy/neutral) in dataclass — referenced in code but not defined
- [x] **T29 Scene Narration** — exploration, movement, rest, skill outcomes

---

## Phase 08 — Admin

- [x] **T30 Ideas Workshop** — AI agent co-authoring for Ideas Bank
- [x] **T31 Campaign Workshop** — chat tab inside campaign modal
- [-] **T32 World Review Queue** — approve/reject working, polish missing
  - [x] Approve · Discard per row
  - [x] Pending counts badge
  - [ ] Inline "Edytuj i Zatwierdź" modal
  - [ ] Batch select / bulk approve
- [-] **T33SA Smart Entry Agent** — form-first shipped per [D8]
  - [x] Form-first one-shot fill via chat
  - [x] Tables supported: weapons, items, consumables, enemies, spells
  - [x] Effect Builder UI for `effect_json`
  - [ ] Conversational refinement: AI keeps draft state, applies incremental edits, shows delta line ("Zmieniłem: damage 1d6 → 1d10")
  - [ ] Form fields highlight which ones changed in last AI response
- [x] **T40 World Builder (Hex Grid)**
  - [x] SVG hex grid, axial coords, A* travel, terrain types
  - [x] Admin campaign map tab + click-to-edit campaign overlay
- [x] **🆕 Combat Sandbox** _(2026-05-17/18, [#21])_
  - [x] Hero clone isolation (`[SBX]` prefix), inventory + spells cloned
  - [x] Character sheet card, auto-enemy-turn, events feed mirroring player UI
  - [x] HP bars, copy-report-to-clipboard, per-fight state reset
  - [ ] Companion: Playwright autotest harness ([#22])

### Extra Admin work (not in original plan)

- [x] Admin data cleanup, loot table admin, enemy modal, archetype admin
- [x] Items + weapons + campaign monitor + dungeon admin polish
- [x] Combat Sandbox admin section ([#21])

---

## Phase 09 — Frontend (Player UI)

- [x] **T33 Hybrid Input UI** — context buttons, suggested_actions[] from backend
  - [x] Backend `suggested_actions.py` + dataclass
  - [x] Frontend `renderSuggestedActions` + disabled-state styling
  - [x] Structured-action bypass (`input_type: "structured"`)
  - [x] Combat composer integration ([#17] series)
- [x] **T34 Combat UI**
  - [x] Spell picker (Scholar — floating overlay, mana check)
  - [x] Initiative panel ([#18], commit `6d9ba8a`)
  - [x] Zone system (engaged/ranged) — display, gating, AI charging, zone-change ([#19], `b8bbf11` + `d57953f`)
  - [x] Crit flash overlay (Nat 20 / Nat 1) ([#23], `74c350a`)
  - [ ] Enemy HP: show bar **AND** number per [D3] _(currently shows both — verify rendered correctly)_
  - [ ] Fear/condition badge icons on combatant rows (⚠ Przerażony, ☠ Zatruty, ⚡ Zaskoczony)
  - [ ] Wound label text below player HP bar in combat panel
- [-] **T35 Character Sheet UI** — _basics shipped, ~9 spec items missing per [#24]_
  - [x] HP bar · Mana bar (Scholar) · Level · gold · LCK
  - [x] Stat modifiers (color-coded), conditions chip row, Arcane Points
  - [x] Skills tab, Inventory tab (3-slot), Spells tab (Scholar), Identity tab
  - [ ] Location badge 📍 in header
  - [ ] Wound label text under HP bar (color-coded per HP%)
  - [ ] XP progress bar + level-up banner _(part of XP loop)_
  - [ ] Skill rank dots (●●●○○) + proficiency badge at rank 3+
  - [ ] Stat tooltip on tap (full name + description)
  - [ ] Condition tooltip with mechanical effect
  - [ ] Auto-expand Conditions section when active
  - [ ] Quest item drop blocker (hide Porzuć button)
  - [ ] Mobile bottom tab bar (Gra | Postać | Ekwipunek)
  - [ ] Real-time animations (HP flash, gold pulse, XP fill, condition fade)
  - [ ] **8-slot equipment diagram** per [D1] _(replaces current 3-card triptych)_
- [x] **T43 Player World Map** — fog-of-war hex grid, click-to-travel, swipe-close
- [-] **T44 Debug System** — _admin backend exists, full spec'd UI missing per [D5]_
  - [x] Admin endpoints (`routers/debug.py`): `/player_state`, `/gm_decisions`, `/validation_flags`, `/settings/feature_flags`, `/reset_test_env`
  - [ ] Player-facing debug drawer (right panel, 420px)
  - [ ] Section tabs (game_state, last_intent, mechanic_result, llm_prompts, narrator_output)
  - [ ] Slash commands: `/debug set-hp`, `/debug set-state`, `/debug reset-cooldowns`
  - [ ] `debug_mode=True` in turn response payload for inline introspection
  - [ ] Admin Panel "🐛 Debug" section that surfaces the existing endpoints in UI

### Extra Frontend work

- [x] GM narrative formatting, skill test roll popup, fast custom tooltip
- [x] F5 session restore (localStorage), input stuck recovery
- [x] F5 roll-bubble rehydration ([#15], full d20+mod+total+outcome reconstruction)
- [x] Combat composer mobile-friendly (safe-area-inset-bottom, narrow-viewport scaling)

---

## Phase 10 — Polish

- [-] **T36 Memory/History**
  - [x] `/mem` semantic search over campaign turns
  - [x] `/helpme` hint command
  - [x] Campaign history summary generator
  - [ ] Dual summaries (player_summary vs gm_summary)
  - [ ] GM continuity injection at session start (30+ min gap)
  - [ ] Historia cooldown enforcement (20 turns)
- [-] **T37 Command Palette**
  - [x] `/help` lists commands in chat system bubble
  - [x] Admin-only commands hidden from non-admin players
  - [ ] Full modal with search field + click-to-insert
  - [ ] Per-command admin toggle (enabled_for_players setting)
- [-] **T38 Campaign End/Death**
  - [x] Death screen overlay
  - [x] Epitaph LLM generator (`solo_death_service.generate_epitaph_llm`)
  - [ ] Epitaph wiring into death screen UI
  - [ ] Victory screen with ending title/summary content
  - [ ] Post-end "Nowa Przygoda / Nowy Świat" options
- [-] **T39 Auth/Onboarding** — _ship as full security baseline per [D6]_
  - [x] Basic login + admin token
  - [ ] **JWT bearer tokens** (HS256, 7-day expiry, refresh endpoint)
  - [ ] **bcrypt password hashing** (cost 12) — verify, migrate if not
  - [ ] **Brute-force lockout** (10 fails → 15 min lock)
  - [ ] **Role-based access** (`player` / `gm` / `admin`)
  - [ ] **Multi-device sessions** (natural via JWT)
  - [ ] **Onboarding overlay** (first-login modal: welcome + theme picker + accept rules)
- [ ] **T45 Hero Journal** — cross-campaign chronicle, chapter summaries, /mem cross-campaign

---

## Phase 11 — Observability

- [ ] **T47 Game Event Logging** — `game_events` table, event_logger service
- [ ] **T48 LLM Call Log** — `llm_call_log` table, admin viewer
- [ ] **T49 Admin Analytics Panel** — dashboard/events/LLM tabs
- [ ] **T50 MCP Server** — 9 tools for AI-queryable game data

---

## Phase 12 — AI Test Agent _(after all phases complete)_

> Rework the existing `ai_test_agent/` (Playwright + Express + LLM orchestrator) to run automated adversarial and regression tests against the full game.

- [ ] **T51 Update agent for current UI** — rewrite selectors for hero-first flow
- [ ] **T52 Regression: baseline flow** — login → hero → campaign → first turn → verify
- [ ] **T53 Regression: dungeon run** — enter → 3 rooms → boss → exit → loot
- [ ] **T54 Adversarial: inventory exploit** — duplicate items via GM dialogue
- [ ] **T55 Adversarial: economy cheat** — illegitimate gold/XP attempts
- [ ] **T56 Adversarial: prompt injection** — malicious player text
- [ ] **T57 LLM consistency test** — 10× same scenario, drift comparison
- [ ] **T58 Admin panel: Test Runner UI** — trigger scenarios, show results
- [ ] **T59 CI integration** — baseline regression after each deploy
- [ ] **T60 Combat Sandbox autotest harness** ([#22]) — YAML scenarios via `/api/admin/sandbox/run-scenario`

---

## Progress Summary

After 2026-05-18 audit corrections:

```
Phase 01  Foundation        ████████████  5/5    100%
Phase 02  Character         █████████░░░  3.5/4   88%   (T42 partial)
Phase 03  World             ████████████  3/3    100%
Phase 04  Gameplay Loop     ████████████  4/4    100%
Phase 05  Combat            ███████████░  5.5/7   79%   (T16 rename + zaskoczony pending)
Phase 06  Economy           ████████░░░░  6.5/10  65%   (T20/T24/T25V2/T26X partial)
Phase 07  Narrator          ███████████░  3.5/4   88%   (T28 deceased context)
Phase 08  Admin             ██████████░░  4.5/5   90%   (+sandbox bonus, T32/T33SA partial)
Phase 09  Frontend          █████████░░░  3.5/5   70%   (T35 partial, T44 partial)
Phase 10  Polish            ███░░░░░░░░░  1.5/5   30%   (T36-T39 partial, T45 not started)
Phase 11  Observability     ░░░░░░░░░░░░  0/4      0%
Phase 12  AI Test Agent     ░░░░░░░░░░░░  0/10     0%

Overall:  ~~~~~~~~~~~~~~~~  40.5/64  63%
```

_The numbers dropped slightly vs the pre-audit estimate (67% → 63%) because partial completions are now scored at 0.5 instead of 1.0. The work itself didn't regress — we just have honest accounting._
