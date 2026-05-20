# AI-GM V2 — Roadmap

> Tree of all tasks ordered by implementation sequence.
> **Legend:** `[x]` = done · `[-]` = partial/in-progress · `[ ]` = pending
> **Auto-updated** by Claude after each completed task/subtask.
> Spec details → `docs/V2_ARCHITECTURE/01_IMPLEMENTATION_PLAN.md`
> **2026-05-18 audit** corrected several boxes — see `docs/V2_ARCHITECTURE/AUDIT_2026_05_18.md` + `DECISIONS_2026_05_18.md`.

> **2026-05-19 sequencing note (Rest Sandbox):** R4 (Rozbij obóz) ships solo to close Stage 2B. Rest Sandbox is deliberately deferred to a new **Stage 2C+** block that lands AFTER `/rest` endpoints (X3/X4) — without those endpoints the harness has no full loop to exercise. Order: R4 → Stage 2B-Schema P2 (S14–S19) → Stage 2C (X1–X9) → Stage 2C+ (RSB1–RSB5) → Stage 2D.

---

## 🎯 EXECUTION QUEUE — strict order, check off top to bottom

> Phase-grouped reference is below this section. **Always work the topmost unchecked item.**
> Stage breaks are momentum/scope markers, not blocking.

### Stage 1 — Quick wins (close audit gaps fast, ~half day total)

- [x] **W1** Wound label text rendered under HP bar in character sheet (T24) — commit `66d40e0`
- [x] **W2** Wound label text rendered under HP bar in combat banner (T24) — commit `66d40e0`
- [x] **W3** Verified enemy HP shows both bar **and** number per [D3] (already correct in code at `app.js:2903`) — commit `66d40e0`
- [x] **W4** Condition rename migration: `fear_shaken`+`fear_frightened` → `frightened`, `terror` → `panicked`, added `break` to registry — commit `97fcba3` (lowercase per DB convention; spec uppercase = rhetorical)
- [x] **W5** TASK_28 deceased NPC `relationship` field — commit `10072e8`

### Stage 2 — XP Loop [D7 + D13 — locked priority]

> **Przeprojektowany 2026-05-18 po dyskusji z user'em.** Cztery podetapy w kolejności: zegar → bezpieczne miejsca → źródła XP → UI wydawania. Spec D12: poziomy są display-only (brak bannera level-up — paseksilent fill+reset).

#### Stage 2A — Zegar gry (fundament, niczego widocznego dla gracza bez tego)

- [x] **T1** `advance_clock(campaign_id, hours, reason)` — `clock_service.py`, audit log rolling 50, commit `1ee136d`
- [x] **T2** Travel między hex'ami / lokacjami → hook w `player_hex_travel`, commit `1ee136d`
- [ ] **T3** Krótki odpoczynek → `advance_clock(1)` (defer do Stage 2C, brak call site)
- [ ] **T4** Długi odpoczynek → `advance_clock(8)` (defer do Stage 2C, brak call site)
- [x] **T5** Nagłówek UI: "**Dzień 3, 14:00 Popołudnie**" + `GET /clock`, commit `1ee136d`

#### Stage 2B — Bezpieczne miejsca (safe_for_rest edytowalne dynamicznie)

- [x] **R1** LLM tag `[SET_SAFE_FOR_REST:location_key:on|off]` — GM dynamicznie oznacza miejsca (np. po misji "oczyszczono karczmę" → bezpieczna) — commit `7ee98a1`
- [x] **R2** Dziedziczenie: hex jest safe ⇔ ma lokację z `safe_for_rest=1`. Implementacja: helper `_hex_is_safe_for_rest(q, r)` używany przez endpointy /rest — commit `7ee98a1`
- [x] **R3** Admin UI: edytuj `safe_for_rest` z karty lokacji (już istnieje?) **i** z edytora hexa na mapie kampanii — commit `c40b21d` (+ wired Lokacje subtab `c277ea8`, grouped view `69fad5c`)
- [x] **R4** Akcja gracza "**Rozbij obóz**" [D15] — tworzy tymczasową sub-lokację `temp_camp` z `safe_for_rest=1`, +1h zegara, +20% encounter chance podczas odpoczynku
  - [x] **R4a** Migration: `game_locations` ADD COLUMN `temporary INTEGER NOT NULL DEFAULT 0` (marks short-lived sub-locations like camps; cleaned up on MOVEMENT away from hex)
  - [x] **R4b** `world_service.build_camp(campaign_id)` — resolves current hex, finds parent macro (or "wilderness" placeholder), inserts `temp_camp_{campaign_id}_{ts}` with `safe_for_rest=1`, `temporary=1`, `created_by='gm_runtime'`, `canonical=0`, `source_campaign_id={campaign_id}`; sets `world_hexes.location_key` to new key
  - [x] **R4c** Endpoint: `POST /api/campaigns/{id}/build-camp` — calls service, advances clock +1h via `advance_clock`, sets `session_flags.camp_encounter_boost = 0.20` (consumed by next /rest call), returns `{location, current_clock, encounter_boost}`. Gates: not in combat, current hex not already `safe_for_rest=1`
  - [x] **R4d** Player UI: "🔥 Rozbij obóz" button in suggested actions, surfaced by `suggested_actions._build_narrative_actions` only when current hex `safe_for_rest=0` AND not in combat. Click → `handleBuildCamp()` calls dedicated endpoint, prints system line + patches local action list (REST enabled, BUILD_CAMP removed)
  - [x] **R4e** Auto-cleanup: `hex_travel_service.resolve_chain_travel` calls `world_service.deactivate_temporary_location_on_hex` on the *from* hex before updating session flags; soft-deletes `temporary=1` rows + clears hex.location_key
  - [x] **R4f** Smoke tests: build-camp on wilderness hex → 200 + safe + +1h clock; second build-camp on same hex → 409; deactivate helper soft-deletes the row and clears hex.location_key (manual call verified)

#### Stage 2B-Schema — Locations source-of-truth (provenance + reuse)

> **Cel:** osiągnąć stosunek ~60-70% wykorzystywanych lokacji z DB (seedy / Kreator AI / admin manual) vs ~30-40% mintowanych runtime przez GM.
> Dziś GM tworzy lokacje bez śladu pochodzenia — nie da się odsiać junku ani filtrować pod biom/typ.
> Spec → `PHASE_03_WORLD/TASK_08_LOCATION_SYSTEM.md` (Provenance & Reuse) + `TASK_10_DATA_TABLES_SOURCE_OF_TRUTH.md` (Candidate Injection).

##### Phase 1 — Schema migration + admin surfacing (ship before R4) ✅

- [x] **S1** Migration: `game_locations` ALTER ADD COLUMN `created_by TEXT NOT NULL DEFAULT 'admin_manual'` (enum: `seed`/`admin_manual`/`admin_kreator`/`gm_runtime`/`import`)
- [x] **S2** Migration: ADD COLUMN `location_subtype TEXT DEFAULT NULL` (tavern/village/town/castle/ruin/cave/forest_clearing/road/watchtower/…)
- [x] **S3** Migration: ADD COLUMN `biome TEXT DEFAULT NULL` (forest/mountain/swamp/plains/coast/desert/urban/…) — matches `world_hexes.hex_type`
- [x] **S4** Migration: ADD COLUMN `tier INTEGER NOT NULL DEFAULT 1` (1–5, level gating)
- [x] **S5** Migration: ADD COLUMN `canonical INTEGER NOT NULL DEFAULT 0` (admin-promoted "preferred reuse" flag)
- [x] **S6** Migration: ADD COLUMN `usage_count INTEGER NOT NULL DEFAULT 0` (incremented on visit — Phase 2)
- [x] **S7** Migration: ADD COLUMN `source_campaign_id INTEGER NULL REFERENCES campaigns(id)` (which campaign minted gm_runtime records)
- [x] **S8** Backfill: `UPDATE game_locations SET created_by = CASE WHEN ai_generated=1 THEN 'gm_runtime' ELSE 'admin_manual' END, canonical = CASE WHEN review_status='permanent' AND ai_generated=0 THEN 1 ELSE 0 END`
- [x] **S9** `_get_or_create_location` (`world_service.py`): set `created_by='gm_runtime'`, `canonical=0`, `source_campaign_id=campaign_id`
- [x] **S10** Admin POST/PATCH/PUT (`locations.py`): accept + persist new fields; default `created_by='admin_manual'`, `canonical=1`
- [x] **S11** Smart Entry schema endpoint: expose new fields with proper enums/dropdowns; on save → `created_by='admin_kreator'`, `canonical=1`
- [x] **S12** Admin UI table (Lokacje): add columns `created_by` (color-coded badge), `subtype`, `biome`, ⭐ `canonical` (one-click toggle), `usage_count` (sortable)
- [x] **S13** Admin UI modal: add subtype + biome + tier dropdowns, canonical checkbox

##### Phase 2 — Reuse engine + auto-pair starting hex (ship after Stage 2B closes)

- [x] **S14** Context injector: extended `build_available_content_index(conn, location_key, character_id=None)` with a "Nearby known places of this type" section — biome+subtype filter capped by `max(1, hero_level // 2)`, ordered `canonical DESC, usage_count DESC, label ASC LIMIT 5`. Graceful fallback to biome-only when biome+subtype yields nothing (unique subtypes like the only city). Wired into `ContextInjector` via `_build_content_index_block` (block was dead code before — `mechanic_result["available_content_index"]` was set but never injected). Tag annotations: `[canonical]`, `[visits=N]`, `(T<tier>)`.
- [x] **S15** Prompt addendum in `system_prompt.txt` → new section `### REUŻYWANIE ZNANYCH LOKACJI (priorytet nad action: create)`: explains the `Nearby known places` section, defines hard rule (check list before emitting `action: create`), spells out when `create` is allowed (empty list OR fabularnie distinct), notes `[canonical]` and `visits=N` semantics, declares duplicates a narrative error.
- [x] **S16** `usage_count`: increment on every `game_sessions.current_location_id` change. Three write paths patched: `turns.py` (GM location_intent), `turn_pipeline.py` (`_update_character_location` / WSM MOVEMENT), `session_location.py` (admin override, only on actual change).
- [ ] **S17** `resolve_starting_hex()` auto-pair: if a canonical location matches `starting_location_name` (label similarity ≥ 0.4 **or** subtype match), set `world_hexes.location_key`; otherwise create a minimal `start_{campaign_id}` location with `safe_for_rest=1`, `canonical=0`, `created_by='gm_runtime'`
- [ ] **S18** "Promote to canonical" button in admin Review Queue → flips `canonical=1` (independent of `review_status`)
- [ ] **S19** Telemetry endpoint `/api/admin/locations/stats` returning `{seed_count, admin_count, gm_runtime_count, canonical_count, gm_runtime_share}` for dashboard widget

#### Stage 2D — Wpięcie 22 źródeł XP [D14] (najważniejsze dla różnorodności gry)

- [ ] **XS1** `[BEAT_COMPLETE:beat_key]` tag → grant XP z `campaign.beat_complete` (30 XP)
- [ ] **XS2** `[QUEST_COMPLETE:quest_key]` → `campaign.side_quest` (40 XP)
- [ ] **XS3** `[DUNGEON_CLEAR:dungeon_key]` → `campaign.dungeon_cleared` (75 XP)
- [ ] **XS4** `[CAMPAIGN_END:ending_id]` → `campaign.campaign_ending` (200 XP)
- [ ] **XS5** Pierwsza wizyta w macro-lokacji → `exploration.location_new` (15 XP). Tracking via `characters.visited_location_keys`
- [ ] **XS6** Pierwsza rozmowa z NPC (DIALOGUE z nowym npc_key) → `exploration.npc_first_talk` (5 XP)
- [ ] **XS7** `[DISCOVERY:lore_key]` → `exploration.secret` (10 XP)
- [ ] **XS8** `[DISCOVERY:secret_location]` → `exploration.hidden_room` (10 XP)
- [ ] **XS9** Sukces w teście DC ∈ [12-15] → `skills.skill_dc_12` (3 XP)
- [ ] **XS10** Sukces w teście DC ∈ [16-19] → `skills.skill_dc_16` (8 XP)
- [ ] **XS11** Sukces w teście DC ≥ 20 → `skills.skill_dc_20` (15 XP)
- [ ] **XS12** LLM tag `[XP_GRANT:reason:amount]` → `narrative.*` (cap 50 XP per session)
- [ ] **XS13** `outnumbered_victory` — wygrana walka z 3+ wrogami → 20 XP (combat extra, łatwy add-on)
- [ ] **XS14** `death_save_survived` — przeżycie rzutu na śmierć → 15 XP (combat extra)
- [ ] **XS15** Session start trigger (po hydration F5 → +0, ale rozpoczęcie nowej sesji w >30 min gap → bonus)

#### Stage 2C — UI wydawania PD + endpointy /rest (wieńczy pętlę)

- [ ] **X1** Pasek PD w karcie postaci — "47/100 do milestone 100" (czysto wizualny, bez bannera per [D12])
- [ ] **X2** Etykieta "Poz. N" w nagłówku (computed `floor(xp_total/100)`, max 10) — bez fanfar
- [ ] **X3** `POST /api/characters/{id}/rest?type=long` — waliduje `safe_for_rest`, +8h zegara, full HP/mana, **flip pending XP → spendable**, reset death save counter
- [ ] **X4** `POST /api/characters/{id}/rest?type=short` — +1h, regen 1d6+CON HP, max 2 między długimi (T23 spec)
- [ ] **X5** UI: dwa przyciski w karcie (krótki / długi odpoczynek) z confirmation, gated na safe_for_rest
- [ ] **X6** Panel "Awansuj" — skill rank-up cards (cost `max(30, 30 × rank)`, calls `spend_skill_rank_up`)
- [ ] **X7** Panel "Awansuj" — stat point-up cards (cost `max(30, 50 × modifier)`, calls `spend_stat_point_up`)
- [ ] **X8** Panel "Awansuj" — spell learn (75 XP) / upgrade (R2=50, R3=100) cards dla Scholar
- [ ] **X9** "Historia PD" view — paginated `character_xp_grants` log, grouped by category, w karcie postaci

#### Stage 2C+ — Rest Sandbox (admin harness)

> **Position:** ships AFTER Stage 2C delivers `/rest` endpoints (X3, X4) and BEFORE Stage 2D begins. Mirrors Combat Sandbox (issue #21) — gives admins an isolated rig to exercise the full rest loop without playing through a campaign.
> **Why here, not earlier:** without working `/rest` endpoints the harness has nothing to exercise — would just toggle camp setup. After Stage 2C, the sandbox can validate the complete loop: build_camp → short rest → long rest → HP/mana regen → encounter rolls → XP spend.

- [ ] **RSB1** Router `backend/app/routers/rest_sandbox.py` at `/api/admin/rest-sandbox/*` — mirrors `sandbox.py` structure (heroes list, setup clone, end). Clone tagged `__rest_sandbox_clone__=true` to keep it filtered from pickers.
- [ ] **RSB2** Endpoints exercise R4 + X3 + X4: `POST /setup` (hero clone + place on test hex), `POST /set-hex-safe-for-rest` (toggle hex safety), `POST /build-camp` (proxy to R4 endpoint), `POST /short-rest` (proxy to X4), `POST /long-rest` (proxy to X3), `POST /roll-encounter` (force encounter roll given current boost), `POST /reset-hero` (HP/mana/XP back to baseline)
- [ ] **RSB3** Frontend section `frontend/admin_panel_v2/sections/rest_sandbox.js` mounted as 💤 Rest Sandbox in admin sidebar (next to ⚔ Combat Sandbox). 3-column layout: hero state (HP/mana/XP/conditions) | rest controls (toggle safe / build camp / short / long / encounter) | event log.
- [ ] **RSB4** 📋 Kopiuj raport button bundles hero state + log + final HP/mana into clipboard markdown for issue reports.
- [ ] **RSB5** Implementation-record issue + companion future-Playwright tracker (mirrors #21/#22 pattern).

### Stage 3 — New surprise condition [D11]

- [ ] **Z1** Seed row in `game_config_conditions`: `key='zaskoczony'`, label_pl `'Zaskoczony'`, applies_to `'enemy'`, default_duration 1
- [ ] **Z2** Backend: `combat_service._apply_attack_bonuses(attacker, target)` reads `zaskoczony` → returns `{atk_bonus: 2, first_hit_doubled: true}`
- [ ] **Z3** Backend: clear `zaskoczony` immediately after target takes any damage
- [ ] **Z4** Backend: emit `[APPLY_CONDITION:zaskoczony:<enemy_key>]` tag from stealth-success path (DC 8 alone / DC 16 group)
- [ ] **Z5** Frontend: ⚡ badge on initiative chip + combatant row with tooltip
- [ ] **Z6** Tests: Nat 20 player attack vs `zaskoczony` enemy → ×4 damage (×2 crit × ×2 surprise); regular hit → ×2

### Stage 4 — Character sheet polish [issue #24, remaining ~9 items]

- [ ] **S1** Location badge 📍 in sheet header (updates on every MOVEMENT action)
- [ ] **S2** Skill rank dots (●●●○○, 5 max) replacing numeric rank
- [ ] **S3** Proficiency `+2` badge at rank ≥ 3
- [ ] **S4** Stat tooltip on tap (full name + Polish description)
- [ ] **S5** Condition tooltip with mechanical effect text
- [ ] **S6** Auto-expand Conditions section when any active condition present
- [ ] **S7** Quest item drop blocker — hide `[Porzuć]` button for `item_type='quest'`
- [ ] **S8** Real-time HP red flash + number tick on damage
- [ ] **S9** Real-time gold coin pulse animation on change
- [ ] **S10** Real-time XP bar fill animation when XP gained
- [ ] **S11** New condition fade-in (orange highlight) + condition removed fade-out
- [ ] **S12** Mobile bottom tab bar below 768px: Gra | Postać | Ekwipunek

### Stage 5 — 8-slot anatomical equipment [D1]

- [ ] **E1** `game_config_items.armor_coverage` column with check constraint (`head`/`torso`/`limb_arm`/`limb_leg`/`full`)
- [ ] **E2** Backend `loot_service._SLOT_VALUES` expanded to 8: `{head, torso, l_arm, r_arm, l_leg, r_leg, main_hand, off_hand}`
- [ ] **E3** Data migration: existing armor rows infer coverage from label (heavy → `full`, default → `torso`); equipped slot becomes `torso`
- [ ] **E4** `equip_item()` resolves armor by `armor_coverage` (e.g. `full` occupies torso + l_arm + r_arm + l_leg + r_leg simultaneously)
- [ ] **E5** Frontend: anatomical 8-slot diagram in character sheet (replaces current 3-card triptych)
- [ ] **E6** Frontend: click slot → filter inventory to equippable items for that slot
- [ ] **E7** Frontend: slot wound tint (red highlight if wound condition affects that body part — e.g. `arm_wound` tints both arms)

### Stage 6 — T42 Persistent Hero endpoints [D4]

- [ ] **H1** `GET /api/heroes` — list all active heroes (filter sandbox clones), include `campaigns_completed`, `total_xp`, `hero_status`
- [ ] **H2** `GET /api/characters/{id}/history` — full `character_campaign_history` records ordered by `completed_at` DESC
- [ ] **H3** Heroes screen UI: cards showing each hero's status (idle/in_campaign/in_dungeon) + last activity
- [ ] **H4** Hero history view — past campaigns with outcome (victory/death/abandoned), XP earned, level at close
- [ ] **H5** Between-campaigns REST state — idle hero can spend XP, see history, before picking next adventure (overlaps with T45, this is the lite version)

### Stage 7 — Combat UI polish (T34 cleanup)

- [ ] **C1** Condition badges on combatant rows (⚠ FRIGHTENED, ☠ poisoned, 🩸 bleeding, ⚡ zaskoczony, etc.)
- [ ] **C2** "Tura wroga..." text overlay during enemy auto-turn (not just disabled buttons)

### Stage 8 — Debug System [D5]

- [ ] **D1** Player `/debug` slash commands: `set-hp <n>`, `set-state <state>`, `reset-cooldowns`, `dump-state`
- [ ] **D2** `POST /api/debug/command` endpoint (admin-only)
- [ ] **D3** Player debug drawer (420px right panel, toggle via `[🐛]` button, admin-only)
- [ ] **D4** Section tabs in drawer: game_state, last_intent, mechanic_result, llm_prompts, narrator_output, performance_timing
- [ ] **D5** `debug_mode=True` in turn response payload (when admin user is in session)
- [ ] **D6** Admin Panel v2 "🐛 Debug" section — surfaces existing `routers/debug.py` endpoints in UI

### Stage 9 — Phase 10 finishing

- [ ] **P1** TASK_36: dual summaries (`player_summary` vs `gm_summary`) generation
- [ ] **P2** TASK_36: GM continuity injection at session start (>30 min gap detection + summary prepend)
- [ ] **P3** TASK_36: Historia cooldown — `historia` command available once per 20 turns
- [ ] **P4** TASK_37: full command palette modal with search field + click-to-insert + per-command admin toggle
- [ ] **P5** TASK_38: wire epitaph into death screen (currently generator exists, UI doesn't show it)
- [ ] **P6** TASK_38: victory screen with ending title + summary from campaign plan
- [ ] **P7** TASK_38: post-end options panel — Nowa Przygoda (same world) / Nowy Świat / Nowy Bohater

### Stage 10 — Auth security baseline [D6]

- [ ] **A1** Audit current password hashing — verify bcrypt; if not, migrate users on next login
- [ ] **A2** JWT bearer tokens (HS256, 7-day expiry); refresh endpoint
- [ ] **A3** Migrate auth middleware from current cookie/bearer to JWT
- [ ] **A4** Brute-force lockout — 10 fails → 15 min lock, counter resets on success
- [ ] **A5** Roles column on `users` table (`player`/`gm`/`admin`); existing admins keep their flag
- [ ] **A6** Role-based endpoint guards (admin-only routes verify `role='admin'`)
- [ ] **A7** Multi-device sessions — verify JWT works on phone + desktop simultaneously
- [ ] **A8** Onboarding overlay — first-login modal: welcome text, theme picker, accept rules, [Zaczynam przygodę], `users.onboarded_at` flag

### Stage 11 — Hero Journal [T45]

- [ ] **J1** Journal UI in heroes screen — chapter list (one per completed campaign)
- [ ] **J2** Chapter summary LLM generator — 2 paragraphs, first-person, on campaign close
- [ ] **J3** Running summary for active campaign (auto-update every 10 turns)
- [ ] **J4** Cross-campaign `/mem` (search across all hero's campaigns)
- [ ] **J5** XP timeline visualization (horizontal bar with level markers)
- [ ] **J6** Cross-campaign minimap — combined visited hex overlay

### Stage 12 — Admin polish

- [ ] **AP1** TASK_32: inline "Edytuj i Zatwierdź" modal in World Review Queue
- [ ] **AP2** TASK_32: batch select + bulk approve in Pending review
- [ ] **AP3** TASK_33SA: conversational refinement — AI keeps draft state, applies incremental edits
- [ ] **AP4** TASK_33SA: form fields highlight changed-in-last-response
- [ ] **AP5** TASK_33SA: delta line in chat (`Zmieniłem: damage 1d6 → 1d10`)

### Stage 13 — Phase 11 Observability

- [ ] **O1** TASK_47: `game_events` table + `event_logger` service
- [ ] **O2** TASK_48: `llm_call_log` table + admin viewer
- [ ] **O3** TASK_49: admin analytics panel (dashboard/events/LLM tabs)
- [ ] **O4** TASK_50: MCP server with 9 tools for AI-queryable game data

### Stage 14 — Phase 12 AI Test Agent

- [ ] **T1** Update `ai_test_agent/` selectors for hero-first flow
- [ ] **T2** Baseline regression scenario (login → hero → campaign → first turn)
- [ ] **T3** Dungeon regression (enter → 3 rooms → boss → exit → loot verify)
- [ ] **T4** Adversarial: inventory exploit (item duplication via GM)
- [ ] **T5** Adversarial: economy cheat
- [ ] **T6** Adversarial: prompt injection
- [ ] **T7** LLM consistency (10× same scenario)
- [ ] **T8** Admin Test Runner UI updates
- [ ] **T9** CI integration on DEV deploy
- [ ] **T10** Combat Sandbox autotest harness ([#22]) — YAML scenarios via `/api/admin/sandbox/run-scenario`

### Stage 15 — Known issues / bugs backlog

Bugs discovered during gameplay that don't fit a numbered stage. Pick into the queue when prioritised.

- [ ] **K1** GM hallucinates weapons / items the player doesn't own (observed during Stage 2B R4 verification, 2026-05-19). LLM narrates "wyciągasz miecz" or grants ad-hoc weapons in combat without inventory lookup. Fix direction: enforce inventory grounding — pre-turn inventory snapshot prepended to context, plus prompt guardrail "Nigdy nie zakładaj że gracz posiada przedmiot, który nie jest w [INVENTORY]". May need a `weapon_grounding_check` post-pass that scans narrative for weapon mentions vs. inventory and downgrades hallucinated weapons to "improvisedfists" damage.
- [ ] **K2** GM requests unnecessary skill rolls (e.g. Kowalstwo when entering a village square just because a blacksmith is in the scene). Observed during Stage 2B R4 follow-up, 2026-05-19. Fix direction: tighten roll-cue prompt rules so rolls require a *player attempt* on the skill, not mere proximity to a themed NPC; add a roll-cue filter that drops cues whose `reason` doesn't reference a player verb.

---

## How to use this queue

1. **Pick the topmost unchecked item.** That's the next task.
2. **Ship it, mark `[x]`, file an issue per the workflow rule (`needs-testing` label).**
3. **Don't skip ahead** — earlier items either unblock later ones or close audit gaps that polish work would otherwise hide.
4. If priorities shift, **edit the queue order first**, don't work out of order silently.

Each stage is a momentum marker, not a gate. You can pause between any two items.

---

## Reference: by phase (legacy view)

The original phase-grouped view follows below for context. Cross-reference task IDs (e.g. `W4` = condition rename, lives in Phase 05; `X4` = `/rest` endpoint, lives in Phase 06).

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
