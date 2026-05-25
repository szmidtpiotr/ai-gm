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
- [x] **T3** Krótki odpoczynek → `advance_clock(1)` — zaimplementowane w Stage 2C: `rest_service.perform_short_rest()` (X4)
- [x] **T4** Długi odpoczynek → `advance_clock(8)` — zaimplementowane w Stage 2C: `rest_service.perform_long_rest()` (X3)
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
- [x] **S17** `resolve_starting_hex()` auto-pair: added `_find_canonical_location_for_name()` helper (label similarity ≥ 0.4, then subtype keyword fallback via `_SUBTYPE_KEYWORDS` dict). On match → `UPDATE world_hexes SET location_key`. On miss → `INSERT OR IGNORE game_locations key=start_{campaign_id}` (`safe_for_rest=1`, `canonical=0`, `created_by='gm_runtime'`) then stamp `location_key`. Also sets `game_sessions.current_location_id` when not already anchored so context injection works from turn 1.
- [x] **S18** "Promote to canonical" button in admin Review Queue: `PATCH /api/admin/world/locations/{key}/promote-canonical` in `world_review.py`; "☆ Kanon" / "⭐ Kanon" button added to pending-locations `extraActions` in `world.js` (disabled/greyed when already canonical). `table.js` patched to support `ex.style` on action buttons (v8→v9 cache-bust).
- [x] **S19** Telemetry endpoint `GET /api/admin/locations/stats` in `admin_location.py` — returns `{total, seed_count, admin_count, gm_runtime_count, canonical_count, gm_runtime_share}` keyed by `created_by` column value.

#### Stage 2D — Wpięcie 22 źródeł XP [D14] (najważniejsze dla różnorodności gry)

- [x] **XS1** `[BEAT_COMPLETE:beat_key]` → `campaign.beat_complete` 30 XP — `_process_beat_signals` now calls `grant_beat_complete` (was dead code)
- [x] **XS2** `[QUEST_COMPLETE:quest_key]` → `campaign.side_quest` 40 XP — narrative tag parser in `turn_pipeline`
- [x] **XS3** `[DUNGEON_CLEAR:dungeon_key]` → `campaign.dungeon_cleared` 75 XP — narrative tag parser
- [x] **XS4** `[CAMPAIGN_END:ending_id]` → `campaign.campaign_ending` 200 XP — narrative tag parser
- [x] **XS5** First macro-location visit → `exploration.location_new` 15 XP — `grant_first_location_visit` reads/writes `characters.visited_location_keys`
- [x] **XS6** First DIALOGUE with new npc_key → `exploration.npc_first_talk` 5 XP — `_process_npc_first_talk` in `turn_pipeline`
- [x] **XS7** `[DISCOVERY:lore_key]` → `exploration.secret` 10 XP — narrative tag parser
- [x] **XS8** `[DISCOVERY:secret_location]` → `exploration.hidden_room` 10 XP — narrative tag parser
- [x] **XS9** Skill success DC 12-15 → `skills.skill_dc_12` 3 XP — turns.py roll resolution hook
- [x] **XS10** Skill success DC 16-19 → `skills.skill_dc_16` 8 XP — same hook
- [x] **XS11** Skill success DC ≥ 20 → `skills.skill_dc_20` 15 XP — same hook
- [x] **XS12** `[XP_GRANT:reason:amount]` → `narrative.free_grant`, cap 50 XP/session — narrative tag parser
- [x] **XS13** Outnumbered victory (≥3 enemies) → `combat.outnumbered_victory` 20 XP — `combat_service.resolve_attack` victory hook
- [x] **XS14** Death save survived → `combat.death_save_survived` 15 XP — turns.py death-save outcome hook
- [x] **XS15** New session (≥30 min gap) → `session.start_bonus` 10 XP — `_process_session_start` in `turn_pipeline`

#### Stage 2C — UI wydawania PD + endpointy /rest (wieńczy pętlę)

- [x] **X1** XP bar — `.xp-bar-card` fill toward next 100-XP milestone; `#sheet-xp-bar-fill` + pending badge `#sheet-xp-pending`.
- [x] **X2** "Poz. N" label — `#sheet-level` computed as `floor(xp_lifetime_earned/100)+1`, max 10.
- [x] **X3** `POST /api/characters/{id}/rest?type=long` — `safe_for_rest` gate, full HP/mana, flush `pending_xp→xp_available`, reset `short_rests_used=0` + `death_saves_failed=0`, +8h clock, audit row in `character_xp_grants`.
- [x] **X4** `POST /api/characters/{id}/rest?type=short` — same gate, `short_rests_used < 2` (T23), 1d6+CON_mod HP regen capped at max, +1h clock.
- [x] **X5** Rest buttons — ☽ Krótki (N/2 charges) / ★ Długi / ⬆ Awansuj; disabled + note when not safe. In `#sheet-rest-actions`.
- [x] **X6** Awansuj panel — skill rank-up cards from `/characters/{id}/xp` costs, calls `POST spend-skill`.
- [x] **X7** Awansuj panel — stat point-up cards, calls `POST spend-stat`.
- [x] **X8** Awansuj panel — Scholar spell learn (75 XP) / R2 (50) / R3 (100); new endpoints `spend-spell-learn` + `spend-spell-upgrade`.
- [x] **X9** XP log — last 20 grants from `/xp/grant-log` inside Awansuj modal.

#### Stage 2C+ — Rest Sandbox (admin harness)

> **Position:** ships AFTER Stage 2C delivers `/rest` endpoints (X3, X4) and BEFORE Stage 2D begins. Mirrors Combat Sandbox (issue #21) — gives admins an isolated rig to exercise the full rest loop without playing through a campaign.
> **Why here, not earlier:** without working `/rest` endpoints the harness has nothing to exercise — would just toggle camp setup. After Stage 2C, the sandbox can validate the complete loop: build_camp → short rest → long rest → HP/mana regen → encounter rolls → XP spend.

- [x] **RSB1** `backend/app/routers/rest_sandbox.py` at `/api/admin/rest-sandbox/*`. Clone prefix `[RSB] `, sheet tag `__rest_sandbox_clone__=true`. Dedicated test hex at (99,99). Registered in `main.py`.
- [x] **RSB2** Endpoints: `GET /heroes`, `POST /setup`, `GET /character/{id}`, `POST /set-hex-safe`, `POST /build-camp` (proxies `world_service.build_camp`), `POST /short-rest` (proxies `perform_short_rest`), `POST /long-rest` (proxies `perform_long_rest`), `POST /roll-encounter` (random check vs hex encounter_chance), `POST /reset-hero`, `POST /end`.
- [x] **RSB3** `frontend/admin_panel_v2/sections/rest_sandbox.js` — 💤 Rest Sandbox nav entry. 3-column: hero picker + sheet card | rest controls (🏕/🔒/🔓/☽/★/🎲/↺) | event log. Module registered in `index.html`.
- [x] **RSB4** 📋 Kopiuj raport — clipboard markdown with hero state (HP/mana/XP/conditions) + full log.
- [x] **RSB5** Implementation-record issue #48 + future Playwright tracker issue #49.

### Stage 3 — New surprise condition [D11]

- [x] **Z1** Seed row in `game_config_conditions` — `key='zaskoczony'`, `label='Zaskoczony'`, `effect_json` carries `grants_attacker_bonus:{atk_bonus:2,first_hit_doubled:true}`, `auto_remove='on_damage'`. Schema columns: `key/label/effect_json/description/is_active/stackable/auto_remove` (no separate label_pl/applies_to/default_duration columns).
- [x] **Z2** `combat_service._apply_attack_bonuses(attacker, target)` — reads target conditions, returns `{atk_bonus, first_hit_doubled, consumed_keys}`. Wired into `resolve_attack`: +2 to attack total before dodge check; damage `×2` on `first_hit_doubled`, `×2` on nat20 crit, `×4` combined.
- [x] **Z3** `_clear_consumed_conditions(target, [...])` — invoked after damage is applied, strips `zaskoczony` from `enemy.conditions` in-place.
- [x] **Z4** `[APPLY_CONDITION:condition_key:enemy_ref]` tag — parsed in both `create_turn` and `create_turn_stream` (`APPLY_CONDITION_RE`), routed to new `apply_condition_to_combatant(campaign_id, enemy_ref, condition_key)` helper (matches by enemy_key or name, idempotent). Tag stripped from narrative server-side AND in frontend `stripInternalTags`. System prompt addendum tells LLM when to emit (DC 8 alone / DC 16 group).
- [x] **Z5** Frontend ⚡ badge — initiative chip (top-left absolute) + combatant row (inline after name). Pulse animation `zaskoczony-pulse` 1.4s. Tooltip: "Zaskoczony — atak +2, pierwsze trafienie podwaja obrażenia". Cache-bust `stage3-zaskoczony-2026-05-20`.
- [x] **Z6** Verified via Python smoke test — helpers return correct bonuses, multiplier math (`×1/×2/×2/×4`) holds, `apply_condition_to_combatant` works by-key, by-name, is idempotent.

### Stage 4 — Character sheet polish [issue #24, remaining ~9 items]

- [x] **S1** Location badge 📍 in sheet header — `current_location_label` added to `GET /api/characters/{id}` payload (resolved via `game_sessions.current_location_id → game_locations.label`); rendered as `.sheet-location-badge` chip next to character name in `populateCharacterSheet`. Auto-refreshes whenever the sheet repopulates (after each turn). Cache-bust `stage4-s1-location-badge-2026-05-21`.
- [x] **S2** Skill rank dots (●●●○○, 5 max) replacing numeric rank — implemented as part of the merged Stats+Skills tab. Each skill row renders `ceiling` pips via `.stat-skill-row__dot`/`--filled`; gold glow on filled pips. Cache-bust `stage4-s1s2s3-merged-2026-05-21`.
- [x] **S3** Proficiency `+2` badge at rank ≥ 3 — green pill `.stat-skill-row__prof` rendered inline next to dots when rank reaches 3+; tooltip "Premia biegłości". Also factored into the per-skill roll bonus (`mod + rank + 2`) shown on the right of each row.
- [x] **S2+S3 bonus — Stats/Skills tab merge** — collapsed the two tabs into one (Skills tab + button removed). New `renderStatSkillList()` groups every trained skill under its parent stat. Each stat block: 3-letter code, value, modifier pill, **0–20 progress bar with base fill (gold) + reserved right strip for future item bonuses (green)**, then nested skill rows showing dots, prof pill, and the precomputed roll bonus. Stats with no trained skills show "brak wytrenowanych". Wizard's pre-existing `.skill-row` namespace preserved by renaming new classes to `.stat-skill-row__*`.
- [x] **S4** Stat tooltip on tap — `.stat-skill-group__code` carries `title=` with full Polish name + role hint (e.g. STR → "Siła — walka wręcz, dźwiganie, fizyczna moc. Modyfikator wchodzi do ataków bronią białą i Atletyki."). `tabindex="0"` makes it tap-focusable so iOS Safari renders the tooltip on tap.
- [x] **S5** Condition tooltip — new `GET /api/mechanics/conditions` public endpoint serves label + description. Frontend `_ensureConditionMeta()` caches it (5-min TTL); chip rendering injects the description into `title=` and `tabindex="0"` for keyboard/tap access.
- [x] **S6** Auto-expand Conditions — section flashes a 0.55s outline (`conditions-flash` keyframes) when any condition is active. `.sheet-conditions--expanded` class added/removed by `renderConditionsBlock`.
- [x] **S7** Quest item drop blocker — `_renderLoreRow` now suppresses the ✕ drop button when `item.item_type === 'quest'` OR `item.is_quest === true`. Narrative items keep the button.
- [x] **S8** Real-time HP red flash + number tick — `flashHpOnDamage(hp)` compares against `_lastVitals.hp`; on decrease pulses `.stat-card--damaged` (red box-shadow flash) on the HP card and `.stat-card__value--ticked` (scale 1→1.18→1, red→accent) on the number.
- [x] **S9** Gold pulse on change — `pulseGoldOnChange()` adds `.inv-gold--pulsing` (scale 1.04 + yellow drop-shadow) for 700ms whenever `gold_gp` differs from prior render.
- [x] **S10** XP bar fill animation on gain — `pulseXpOnGain(xpAvail)` triggers `.xp-bar-card--gained` (lime box-shadow halo) + `.xp-bar__fill--filling` (shimmer sweep across the fill) when `xp_available` increased.
- [x] **S11** Condition fade-in/out — `_lastConditionKeys` diffed each render. New keys get `condition-chip--entering` (orange→red ease-in scale-up), removed keys get `condition-chip--leaving` (220ms shrink + fade) before the DOM removes them.
- [x] **S12** Mobile bottom tab bar — `#mobile-bottom-bar` (Gra/Postać/Ekwipunek) fixed to viewport bottom, CSS-gated `@media (max-width: 768px)`. iOS safe-area inset honored. Clicks route via `handleMobileBarClick` → `toggleCharacterSheet` + `_switchSheetTab('stats'|'inventory')`. Adds `padding-bottom` to body + sheet panel so the bar doesn't cover content.

### Stage 5 — 8-slot anatomical equipment [D1]

- [x] **E1** `game_config_items.armor_coverage` column (enum enforced in code: `head`/`torso`/`limb_arm`/`limb_leg`/`full`; default `torso`)
- [x] **E2** `loot_service._SLOT_VALUES` expanded to 8 slots; legacy `armor` slot removed across the stack
- [x] **E3** ADMIN_SEEDS backfill — labels matched against helm/gauntlet/greave/full-plate patterns; legacy `slot='armor'` migrated to `slot='torso'`
- [x] **E4** `equip_item()` is coverage-aware: `full` armor anchors at torso and locks 4 limbs in one transaction; slot validation rejects mismatched targets (head→leg → ValueError)
- [x] **E5** Frontend anatomical diagram — heraldic medieval cartouches around a golden warrior silhouette; 8 slots arranged via `grid-template-areas`
- [x] **E6** Click-to-filter — tapping an empty slot filters the backpack to equippable items; `Filtr: <slot>` pill above the pack
- [x] **E7** Slot wound tint — `arm_wound`/`leg_wound`/`head_wound`/etc. read from `sheet.conditions`; affected slot gets a red gradient + 🩸 drop + `wound-pulse` animation
- [x] **E8** (follow-up) `weapon_slot` enum on `game_config_weapons` (`main_hand`/`two_handed`/`off_hand_only`/`either`); two-handed weapons lock both hands; shield-class items reject `main_hand`. Smart Entry + admin v2 weapons table + modal expose the field. Auto-equip helper picks the right slot.
- [x] **E9** (follow-up) Bare-hand combat — seeded `unarmed` weapon (1d3 STR melee, weapon_slot=either) and rewired `default_weapon_row()` to use it instead of the alphabetical-first catalog row.
- [x] **E10** (follow-up) Identity sheet display — read both V2 (`bonds[].description`, `weaknesses[].description`) and V1 (`bond`, `flaw`) keys so heroes created in either format show identity data under "Historia/Wygląd" tab.

### Stage 6 — T42 Persistent Hero endpoints [D4]

- [x] **H1** `GET /api/heroes?user_id=X` — enriched hero roster with `campaigns_completed` (count from history), `total_xp_lifetime` (sheet.xp_lifetime_earned), `hero_status` (idle/in_campaign/in_dungeon), `last_activity_at`. Filters `[SBX] %` / `[RSB] %` names + `__sandbox_clone__` sheet flag. Legacy `GET /characters?user_id=X` preserved for compat.
- [x] **H2** `GET /api/characters/{id}/history` — history rows joined with `campaigns.title`, ordered by `completed_at DESC`. Returns `{history: [{id, campaign_id, campaign_title, outcome, xp_earned, gold_at_end, turns_count, chapter_summary, completed_at}]}`.
- [x] **H2 write hook** — `DELETE /api/campaigns/{id}` now INSERTs a `character_campaign_history` row with `outcome='abandoned'` for each hero before unlinking. Idempotent gate prevents double-write.
- [x] **H3** Heroes screen UI — new `.hero-card` layout: name + status chip (idle=green / in_campaign=gold / in_dungeon=red), archetype·level·HP·last-seen line, current-campaign line, trophy row (⚔ completed count · 🏆 lifetime XP · 📜 Historia · ⬆ Awansuj when idle+XP). Cards sort in_campaign > in_dungeon > idle, newest within each group.
- [x] **H4** Hero history modal — `openHeroHistoryModal()` fades a centered card in over a backdrop; each row carries outcome icon (🏆/💀/🚪), Polish outcome label, XP earned, turn count, relative date (`_relativeTimePL`); empty state distinguishes "first campaign in progress" vs "no campaigns".
- [x] **H5** Between-campaigns XP spending — idle hero card with `sheet.xp_available > 0` exposes a `⬆ Awansuj (N PD)` button that opens the existing X6/X7/X8 Awansuj panel without entering a campaign.

### Stage 7 — Combat UI polish (T34 cleanup)

- [x] **C1** Condition badges on combatant rows — `_renderConditionBadges()` produces one `.init-chip__cond-badge` per active condition, pulled from `combatant.conditions[]`. 10 keys mapped (zaskoczony/poisoned/bleeding/burning/frightened/panicked/stunned/blinded/cursed/break) with per-condition pulse animations + tooltips from `/api/mechanics/conditions`. Surprise ⚡ from Z5 unified into this system.
- [x] **C2** "Tura wroga…" overlay — `_showEnemyTurnOverlay()` lazy-mounts inside the combat banner and fades in via `.combat-status-overlay--visible`. Card has pulsing red box-shadow, sequenced 3-dot ellipsis, optional "Działa: <enemy name>". Triggered eagerly on enemy-turn POST and re-validated by every `renderCombatUI()` poll. Auto-hidden on combat end. `backdrop-filter: blur(2px)` on desktop.

### Stage 8 — Debug System [D5]

- [x] **D1** `/debug` slash commands in `commands_service._execute_debug_command`: `dump-state` (default), `set-hp N` (clamped to [0, max_hp]), `set-state STATE` (writes `session_flags.state` per WSM convention, auto-seeds `pending_skill_test` for SKILL_TEST_PENDING, supports full WSM enum incl. FEAR/DEATH_SAVE), `reset-cooldowns` (zeroes short_rests_used + death_saves_failed + wipes character_dungeon_runs). Composer integration: `/debug` listed in SLASH_COMMANDS, bare `/debug` prints inline usage hint, autocomplete via `DEBUG_CMD_TREE` mirrors `/admin` pattern (suggests subcommands AND state-value options after `set-state `).
- [x] **D2** `POST /api/debug/command` in `routers/debug.py` — admin-only via `_user_is_admin(user_id)` helper, routes through `execute_command_logic`, restricted to `/debug` prefix. 403 for non-admin, 400 for non-debug commands.
- [x] **D3** `[🐛]` floating button anchored **top-right (top: 100px)** — clear of composer/send button. Visibility gated by BOTH `currentUser.is_admin` AND `debugMode` (Settings → "🐛 Pokaż debug pod wiadomościami GM" toggle). Drawer is 420 px right-edge slide-out, mobile full-width.
- [x] **D4** Six tabs in drawer (🌍 State / 🎯 Intent / ⚙ Mechanic / 🤖 LLM / 📜 Narrator / ⏱ Timing) plus refresh + copy-to-clipboard + close actions. Body is a `<pre>` JSON dump.
- [x] **D5** `GET /api/debug/last-turn?character_id=X&user_id=Y` — snapshot endpoint (chose this over inline-debug-in-turn-response). Returns game_state (sheet + session_flags), `last_intent` (route + user_text + parsed JSON envelope), `mechanic_result` (live combat_state or last combat_turns row), `llm_prompts` (raw narrator envelope until journaling lands), `narrator_output`, `performance_timing` (placeholder until timing journaling lands), `last_turn_meta`. Drawer fetches from here on open and after each `/debug ...` command.
- [x] **D6** Admin v2 `sections/debug.js` — 5 cards (Player State / GM Decisions / Validation Flags / Feature Flags / Reset Test Env). Each card has input fields + Pobierz/Refresh button + `<pre>` output. Reset is gated by `confirm()`. Feature Flags auto-loads on first mount.

### Stage 9 — Phase 10 finishing [split into 3 sub-phases]

Stage 9 covers 7 items across 3 task areas (TASK_36 summaries, TASK_37 palette, TASK_38 death/victory). Shipped in 3 cohesive sub-phases — each lands independently with its own implementation-record comment on issue #62 and keeps a working main between pushes.

#### Sub-phase 9-A — Death/Victory UI (frontend-heavy, cohesive UX payoff)
**Why grouped:** all three items render the post-campaign experience. Frontend-heavy with small backend (expose epitaph + ending in campaign payload). The death screen DOM already exists in `index.html` with embers/vignette/skull animation — just needs the epitaph wired and post-end options added. Victory screen is the warm-gold mirror of death.

- [x] **P5** TASK_38 — epitaph wired into death screen. New backend `GET /api/campaigns/{id}/end-summary` returns `outcome: 'death' | 'victory'` + epitaph (from `campaigns.epitaph` populated by `solo_death_service.generate_epitaph_llm()`). Frontend `showDeathScreen` fetches it on mount and renders into `#death-epitaph-text` with the 1.6 s opacity + letter-spacing collapse animation (`.death-epitaph--lit` class triggered via `requestAnimationFrame`).
- [x] **P6** TASK_38 — victory screen shipped. New `#victory-screen` overlay: rotating sun-rays (60 s loop), warm-gold rising embers (`vember-rise` 6 s), laurel-wreath SVG with bloom + glow pulse, character name + class + level + lifetime XP, ending title + summary from `gm_plan_json.endings[ending_id]`. Shows on `campaigns.status === 'completed'`. Auto-trigger via `[CAMPAIGN_END:ending_id]` tag is out-of-scope for 9-A — for now exposed as `window.showVictoryScreen()` for manual testing; will auto-fire when sub-phase 9-B wires status-change detection.
- [x] **P7** TASK_38 — post-end options panel. Three `data-end-action` buttons (`new-adventure` / `new-world` / `new-hero`) shared between death + victory screens. `handleEndAction()` routes: new-hero → `loadHeroes()` + `showScreen('heroes')`; new-world → keep hero, `loadCampaigns()` + `showScreen('campaigns')`; new-adventure → same hero, `showScreen('newCampaign')` with toast hint. Wskrześ button hidden by default (still in DOM as `#resurrect-btn[hidden]` — admin-only toggle in a future task).

#### Sub-phase 9-B — Dual summaries + continuity injection (backend + LLM plumbing)
**Why grouped:** P2 depends on P1 having usable summaries. Schema migration + service plumbing + turn-pipeline prompt prefix all touch overlapping files (`history_summary_service.py`, `context_injector.py`, `campaign_ai_summaries` schema).

- [x] **P1** TASK_36: dual summaries — **infrastructure already in place** (`campaign_ai_summaries.audience` column + `persist_summary(audience=...)` + per-audience `fetch_latest_saved_summary`). Added new `GET /api/campaigns/{id}/summaries?user_id=Y` returning `{player, gm, gm_visible}` in one round-trip with admin-only gm portion. Existing `/history/summary?audience=gm` endpoint now requires `user_id` matching an admin (403 otherwise). Player audience stays open.
- [x] **P2** TASK_36: continuity injection — `ContextInjector._build_continuity_block(campaign_id, session_flags)` checks last turn timestamp; when gap ≥ 30 min (matches XS15 SESSION_GAP_MINUTES) AND `session_flags.continuity_injected_at_turn != last_turn_number`, fetches the latest `player_summary` and prepends a "=== TWOJA PRZYGODA DOTYCHCZAS ===" block to the narrator prompt with a directive to weave it into the first paragraph without quoting. Marks session_flags so it fires once per gap. Never reads `gm_summary` (player-only narrative bridge).

#### Sub-phase 9-C — Cooldown + command palette (small isolated polish)
**Why grouped:** both small, both can ship anytime, no dependency on A or B. Cooldown is a one-line gate, palette reuses existing autocomplete data structures.

- [x] **P3** TASK_36: Historia cooldown — `/mem` rate-limited to **20 narrative turns** per campaign. Counter in `session_flags.historia_last_turn` (number of narrative turns at last successful /mem). Gate in `post_memory_ask`: if `narrative_n - last < 20`, returns `HTTP 429` with `detail={error: 'historia_cooldown', message, turns_remaining, ...}`. Frontend `handleMemCommand` catches the structured detail and renders it as a system bubble (`🕯 Pamięć potrzebuje czasu. Spróbuj za N tur.`) instead of a toast. Admin users bypass both the gate AND the post-success stamp. `apiRequest` upgraded to attach the full error body as `err.body` so structured 429 detail survives the throw.
- [x] **P4** TASK_37: command palette modal — `#command-palette` opens on `⌘` button in composer OR `Ctrl+/` (`Cmd+/` on Mac) keybinding while on the game screen. Search input filters by command name or description (case-insensitive substring + prefix match). Arrow keys navigate; Enter inserts the command stub into the chat input with cursor positioned for args; Esc / backdrop click / re-press Ctrl+/ closes. Sources: `SLASH_COMMANDS` (filtered by `adminOnly`) + `DEBUG_CMD_TREE` (admin-only, includes `preview-death` / `preview-victory`). Empty-state "Brak pasujących komend." Mobile: full-width card, single-column item rows.

### Stage 10 — Auth security baseline [D6 · split into 3 sub-phases — see #63]

**2026-05-21 audit:** current state is "trust the client" — `user_id` is a query param, "token" is the literal string `user:<id>`. Plain-text passwords exist alongside bcrypt. Migrating to JWT means rewriting auth on ~40 endpoints, so the work is split to keep main shippable between steps.

#### Sub-phase 10-A — Hardening of what exists (additive, ships independently)
- [x] **A1** Plain-text + sha256 password rows transparently re-hashed to bcrypt ($2b$12$) on next successful login. Existing bcrypt rows untouched. `_verify_user_password` now returns `(ok, kind)` so the login handler knows when to re-hash. `demo` user already migrated as a smoke test.
- [x] **A4** Brute-force lockout — `users.failed_login_count` + `users.lockout_until` columns added (idempotent ALTER). 10 consecutive fails → 15 min lock, `HTTP 423 Locked` with structured detail `{error, message, minutes_remaining, lockout_until}`. Successful login clears both columns. Lockout window self-expires on time check (no background job needed).
- [x] **A5** `users.role` enum column (`player`/`gm`/`admin`) added with `DEFAULT 'player'`. Backfill UPDATEs sync from `is_admin` (1→'admin', 0→'player') on every startup, idempotent. Login response now carries `role` alongside the legacy `is_admin`. Both columns coexist; downstream code can switch to `role` on its own timeline.

#### Sub-phase 10-B — JWT issuance (parallel to existing query-param auth)
- [x] **A2** JWT bearer tokens. `backend/app/services/jwt_service.py` issues HS256 tokens (7-day access, 30-day refresh) using `JWT_SECRET` env (dev fallback derived from hostname + DB path). Refresh tokens carry a `jti` for future revocation. `backend/app/core/jwt_auth.py` exposes `current_user_optional` + `require_current_user` FastAPI dependencies. Login now emits `{access_token, refresh_token, token_type, expires_in}` alongside the legacy `user_id`/`is_admin`/`role`. New endpoints: `POST /auth/refresh` (exchanges refresh for new access, re-fetches current role from DB), `GET /auth/me` (validates current token + returns identity).
- [x] **A2 frontend** — Frontend stores `aigm_access_token` + `aigm_refresh_token` in localStorage on login. `apiRequest` attaches `Authorization: Bearer <token>` on every request when present. Auto-refresh on 401: single-flight `_tryRefreshAccessToken` exchanges refresh for new access and retries the failed request transparently. Logout clears both keys. Existing `?user_id=` query-param fallback untouched — 10-B is purely additive.

#### Sub-phase 10-C — Migrate enforcement (THE breaking change, on branch `stage10c-jwt-enforcement`)
- [x] **A3** All 18 authenticated endpoints now resolve `user_id` via `resolve_authed_user_id(authorization, user_id_query)`. Trust order: (1) JWT signature → payload.sub; (2) legacy `?user_id=` query (logs deprecation warning); (3) 401 if neither. When both present, must agree or 400. Endpoints sweep covers `auth.py`, `campaign_history.py`, `campaign_helpme.py`, `campaign_memory.py`, `campaigns.py`, `characters.py`, `debug.py`. Frontend `apiRequest` already attaches the Bearer header (10-B); two stray raw `fetch()` calls (xp + xp/grant-log) migrated to `apiRequest` so they get the header automatically.
- [x] **A6** Admin-only endpoints use `require_admin_role(authorization, user_id_query)` — verifies JWT `role='admin'` OR `is_admin=1` claim; falls back to DB lookup when only query param present. Applied to `/debug/last-turn`, `/debug/command`, and the `/summaries` gm-audience gate. 403 for non-admins, 400 for mismatched JWT+query.
- [x] **A7** Multi-device verification — JWT is stateless by design; two independent sessions sign their own tokens and the server validates each independently. Manual two-tab login confirmed both work concurrently with separate access tokens (acceptance check, no code change required).
- [x] **A8** Onboarding 2-step: cinematic welcome (step 1) + theme picker (step 2, 4 themes: Mrok/Bursztyn/Sepia/Jasność, live CSS var overrides, saved to localStorage). `users.onboarded_at` flag set on completion. CSS `[data-theme=*]` overrides applied on page load. — commit `d79fa05` (cinematic) + `A8-theme-picker-2026-05-24`

### Stage 11 — Hero Resurrection system [see #64]

The Stage 9-A death screen ships with a `Wskrześ bohatera` button that today is rendered `hidden` and has no backend — so dying is permanent. This stage wires the real resurrection flow with **per-user admin-configurable cost** (XP claw-back / gold % / recent-gain gold / random equipped-item loss / free for admins). Slotted ahead of Hero Journal because death-screen polish without a working button feels broken, and the migration pattern (extra `users` columns) is hot in head from Stage 10-A.

Design decisions resolved with owner in #64: XP revert cascades to skill/spell purchases, gold-recent-days uses `min(recent_gains, current_gold × cap%)`, item loss is deterministic (no save), resurrect resets death_saves_failed + short_rests_used + dungeon cooldowns.

- [x] **R1** Migration — `users.resurrection_enabled BOOLEAN DEFAULT 0`, `resurrection_cost_mode TEXT DEFAULT 'admin_free'`, `resurrection_cost_value INTEGER DEFAULT 25`, `resurrection_cost_cap_percent INTEGER DEFAULT 50`, `resurrection_uses_remaining INTEGER DEFAULT NULL`. New table `character_gold_log (character_id, delta, source, created_at, game_clock_day)`. Verify `character_xp_log` schema is journal-complete (`reverted_at` column needed).
- [x] **R2** Backend service `app/services/resurrection_service.py` — 5 cost-mode handlers (`xp_revert`, `gold_percent`, `gold_recent_days`, `item_loss`, `admin_free`) + `cost_preview(character_id, user_id)` returning what *would* be lost without applying.
- [x] **R3** Player endpoint `POST /api/characters/{id}/resurrect` — requires JWT (player owns hero), reads user config, applies cost, restores HP to `max_hp // 2`, clears `status='dead'` → `'active'`, resets death-state flags, decrements `resurrection_uses_remaining` if not null. Returns `{cost_paid, hero_summary}`.
- [x] **R4** Admin endpoints — `POST /api/admin/characters/{id}/resurrect` with `force: bool` (bypass cost + uses-remaining when true), `GET /api/admin/users/{id}/resurrection-config`, `PATCH /api/admin/users/{id}/resurrection-config`. All gated by `require_admin_role`.
- [x] **R5** Helper additions — `xp_service.revert_last_xp_with_purchases(character_id, amount)` (also undoes skill ranks / spells bought after threshold), `inventory_service.random_functional_item(character_id)` (pool = equipped + has effect_json or non-zero DR, excludes quest-marked).
- [x] **R6** Gold journaling — every mutation to `sheet_json.gold` writes a row to `character_gold_log`. Audit: `inventory_service`, `shop` purchase/sell, `loot_service.grant_loot_to_character`, XP-grant-to-gold paths. Tag each with `source` (`loot`, `shop_sell`, `shop_buy`, `quest_reward`, …).
- [x] **R7** Admin Panel v2 — `sections/players.js` gets a "Wskrzeszenie" card per user: master toggle, mode dropdown, value input, cap-percent input (conditional on mode), uses-remaining input. Live preview line ("Tryb: gold_recent_days → ostatnie 7 dni, max 50% obecnego złota").
- [x] **R8** Frontend death screen wiring — `index.html:868` un-hides `#resurrect-btn` when `currentUser.resurrection_enabled` AND `(resurrection_uses_remaining > 0 OR null)`. `app.js:5952` `handleResurrect()` calls `GET /resurrect-preview` → renders confirmation modal with the actual cost line ("Stracisz: 245 PD, 12 GP, ranga Atletyka 3→2") → POST `/resurrect` on confirm → on success play a brief revival animation + reload campaign state.
- [x] **R9** Admin force-resurrect button in `sections/players.js` — visible when viewing a dead-character user; "Wskrzesz bez kosztu" button POSTs admin endpoint with `force=true`. Confirmation modal.
- [x] **R10** Backend tests `test_resurrection.py` — 5 mode handlers, force-bypass path, uses-remaining decrement, full state reset (death_saves_failed + short_rests_used + dungeon cooldowns), gold journal integrity after partial revert.

### Stage 11-C — Auth UX: Registration + Onboarding + Profile + Invite System [→ doc 19, #67–#72]

> Design doc: `docs/V2_ARCHITECTURE/19_AUTH_UX_REGISTRATION_PROFILE.md`
> Full design session complete 2026-05-22. All screens decided. See doc for DB schema + screen specs.

#### Backend foundation [#67]
- [x] **C1** DB migration — `user_invites`, `email_verification_tokens`, `password_reset_tokens`, `user_friendships` tables; `users.invited_by_user_id`, `email_verified_at`, `onboarded_at`, `invite_weekly_limit` columns; `app_config` keys: `smtp_*`, `registration_open`
- [x] **C2** Email service — `app/services/email_service.py`: `send_email(to, subject, html)` via SMTP using `app_config` settings; `send_invite_email()`, `send_verification_email()`, `send_password_reset_email()` helpers

#### Invite + registration [#68]
- [x] **C3** Invite CRUD — `POST /api/invites` (create, admin or player, respects weekly quota), `GET /api/invites/{code}` (validate + return inviter info), admin endpoints: list all invites, revoke, boost user quota
- [x] **C4** Registration — `POST /api/auth/register` (validates invite code/token, creates user, marks invite used, sends verification email, returns JWT)
- [x] **C5** `GET /api/auth/registration-status` (public) — returns `{open: bool}` for login screen conditional link

#### Email verification + password reset [#69]
- [x] **C6** Email verification — `POST /api/auth/verify-email` (validates token, sets `email_verified_at`); `POST /api/auth/resend-verification` (rate-limited 1/2min); login endpoint returns `{error: "email_unverified"}` when unverified on 2nd+ login
- [x] **C7** Password reset — `POST /api/auth/forgot-password` (always 200, sends email if account exists); `POST /api/auth/reset-password` (validates token, updates password, auto-returns JWT, marks token used)

#### Frontend auth screens [#70]
- [x] **C8** Login screen additions — "Nie pamiętasz hasła? → Reset" and "Masz zaproszenie? → Zarejestruj się" footer links; email-unverified gate screen on login
- [x] **C9** Registration screen — invite card (inviter avatar + name + personal message), email pre-filled+locked, username + password fields, countdown timer, bare `/register` screen for code entry
- [x] **C10** Forgot password screens — enter email screen + set new password screen (2h token, auto-login on save)

#### Frontend onboarding + profile [#71]
- [x] **C11** Onboarding flow — 2-step: (1) CSS cinematic with inviter message card + atmospheric art + title, auto-advance 6s; (2) theme picker → "Zaczynam przygodę"; gated on `onboarded_at IS NULL` from login response
- [x] **C12** Profile page — Chronicle stats, Friends section (add/search players, foundation for multiplayer), Invites (sent quota + "Wyślij zaproszenie" button), Security (change password / delete account); entry via Settings drawer "Konto" link
- [x] **C13** Send invite modal — email form + copyable link (both in one modal); accessible from profile page + "📨 Zaproś znajomego" chip on heroes screen

#### Admin features [#72]
- [x] **C14** Admin SMTP config — System panel → Email section: `smtp_host/port/username/password/from_name/from_address/use_tls` form + "Wyślij testowy email" button
- [x] **C15** Admin invite tree — Players → "Drzewo zaproszeń" tab: interactive D3.js collapsible tree, activity colour coding (green/yellow/grey), click-node flyout, "Eksportuj CSV" button

### Stage 11-D — Slash Commands hardening (done)
- [x] **SD1** Per-command `admin_enabled` + `player_enabled` toggles in admin panel
- [x] **SD2** Per-command `alias` field — admin can rename `/search` → `/szukaj`; players forced to use alias, admin keeps canonical fallback
- [x] **SD3** Backend `/api/mechanics/slash-commands` returns alias as `command` + new `canonical` field
- [x] **SD4** Client-side alias expansion in `handleSlashCommand` (preserves original text in user bubble)
- [x] **SD5** New `/quest` command (default alias `/zadania`) reading from `character_quests` table
- [x] **SD6** Streaming endpoint `[CMD_JSON]` properly rendered as system bubble (was falling through to "raw narrative token")
- [x] **SD7** Archetype gate — non-Scholar `arcana`/`spell_attack`/`arcane_save` checks blocked server-side + filtered from GM's skill list prompt
- [x] **SD8** Polish-label support for `/roll` autocomplete and backend command parser (label↔key resolver)

### Stage 11-E — Content library expansion (done — seeded on DEV)
- [x] **CL1** Seed 30 weapons (swords, axes, blunt, polearm, ranged, spell focus) with Polish labels + descriptions
- [x] **CL2** Seed 30 armors (light/medium/heavy + shields + helmets + boots + gloves + cloaks) with `ac_bonus` + `armor_coverage`
- [x] **CL3** Seed 60+ misc items (tools, containers, quest/lore items, magical passive items, instruments, mundane gear)
- [x] **CL4** Seed 30 consumables (healing/mana potions, buff potions, single-use scrolls, food, throwables/poisons)
- [x] Script: `scripts/seed_extra_content.py` (idempotent — re-runnable on PROD when ready)

### Stage 12 — Hero Journal [T45]

- [x] **J1** Journal UI in heroes screen — chapter list (one per completed campaign). Modal "Kronika przygód" with Cinzel chapter headings (Rozdział I/II/III…), outcome badge (Zwycięstwo/Śmierć/Porzucono), stats row, and chapter_summary body (placeholder "Podsumowanie wkrótce…" when not yet generated). `_toRoman()` helper. Cache-bust `j1-journal-2026-05-24`.
- [x] **J2** Chapter summary LLM generator — 2 paragraphs, first-person, on campaign close. Async daemon thread via `chapter_summary_service.py`. Hooks: death path (turns.py ×2), victory path (xp_sources.py `grant_campaign_end`), abandonment path (campaigns.py DELETE handler). Idempotent `ensure_history_row()` + `schedule_chapter_summary()`. `campaigns.status` set to `'completed'` on victory for the first time.
- [x] **J3** Running summary for active campaign (auto-update every 10 turns). Backend: `summary_auto_ensure_every_n_narrative_turns` lowered 20→10 via `_ensure_j3_summary_interval()` migration; `DEFAULT_SUMMARY_AUTO_ENSURE_EVERY_N_NARRATIVE_TURNS=10`. Frontend: `_journalBadgeTurns` counter init from existing turn count mod 10; increments per `sendTurn`; at 10 shows pulsing gold badge dot on journal button; clears on open.
- [x] **J4** Cross-campaign `/mem` (search across all hero's campaigns). `_fetch_cross_campaign_corpus()` in `memory_qa_service.py` joins `character_campaign_history` → `campaign_ai_summaries` for ALL campaigns, each labeled `=== Title (Outcome) ===`. `answer_from_summaries()` accepts `character_id`; endpoint passes it. Prompt updated to cite campaign names in answers. Source field: `cross_campaign` vs `single_campaign`.
- [x] **J5** XP timeline visualization (horizontal bar with level markers). Pure frontend: `renderXpTimeline(sheet)` in `populateCharacterSheet`. 8px track, gradient fill to `xp_lifetime_earned/1000`, 9 dividers, pulsing accent cursor at fill edge, 10 centered level labels (current highlighted), meta row with PD-to-next. No new API calls.
- [x] **J6** Cross-campaign minimap — combined visited hex overlay. New endpoint `GET /characters/{id}/hex-map` (UNION of `campaign_hex_data.discovered=1` across all character campaigns + active). `_renderHexMinimap()` renders flat-top SVG (S=12) with `TYPE_COLORS`, gold stroke. `_appendJournalMinimap()` appends "Odwiedzone miejsca" section at bottom of hero journal modal.

### Stage 12-B — Księga Wiedzy: Quick Tips

Short, glossary-style entries that explain a single mechanic in 1–3 sentences. Surfaced inside the Księga Wiedzy panel as a dedicated "Wskazówki" tab and triggered contextually when the player encounters a new mechanic for the first time (e.g. first time hit by a critical → auto-open "Krytyczna porażka (Nat 1)" tip).

- [x] **KW1** Reused existing `knowledge_book` table (already existed); added `icon TEXT DEFAULT ''` and `related_command TEXT DEFAULT ''` columns via `_ensure_knowledge_book_v2()` migration. 23 Polish seed entries added across 5 categories (total 31 tips).
- [x] **KW2** Admin CRUD extended — `admin.py` PATCH `allowed` set + POST INSERT include `icon` + `related_command` fields; existing admin panel Księga Wiedzy section already provided the UI.
- [x] **KW3** Player UI — new "Wskazówki" tab (tab button + `#tab-knowledge` div in `index.html`); `renderKnowledgeTab()` groups tips by category (Walka / Magia / Eksploracja / Mechaniki / Postać); `GET /api/knowledge-tips` endpoint in `backend/app/api/knowledge.py`. Cache-bust `kw-tips-2026-05-24`.
- [x] **KW4** Contextual trigger hook — `parseGmFull` extracts `[TIP:key]` tags (stripped from display); `_handleTriggeredTips(keys)` surfaces unseen tips using `aigm_seen_tips` localStorage set; seen keys persisted so each tip fires only once per player.
- [x] **KW5** Seeded 30 Quick Tips across 5 categories: 7 Walka · 4 Magia · 5 Eksploracja · 3 Mechaniki (DC/statystyki/biegłość) · 4 Postać + original 7 legacy tips = 31 total.
- [x] **KW6** "📖 Pokaż wskazówki" chip appended to `/help` system bubble after `appendMessage`; click opens character sheet (if closed) and switches to knowledge tab via `_switchSheetTab('knowledge')` + `renderKnowledgeTab()`. CSS: `.help-wskazowki-chip` gold pill with hover state.
- [x] **KW7** `[TIP:key]` guidance added to `system_prompt.txt` under new section `## TAG [TIP:klucz]`. Documents all 23 valid keys by category, rules (1 tag/turn, end of response, first encounter only), and example output. Frontend `parseGmFull` already strips tags + `_handleTriggeredTips` surfaces unseen tips (wired in KW4).

### Stage 12-C — Hex World Expansion [2026-05-24]

Extends the hex travel system from a static map into a living, auto-expanding world.

- [x] **HW1** Neighbor outline fix — `get_campaign_world_map()` always adds all 6 neighbors of `current_hex` to the outline set, split into `outline` (real DB hex) vs `unexplored` (no DB row, very faint dotted); both are click-to-travel — commit `77b9a7c`
- [x] **HW2** Full-screen travel cinematic — terrain-specific gradient, floating emoji, destination name, atmosphere flavor, cycling tips (all 31 tips, round-robin via `aigm_travel_tip_idx`), 15 s progress bar, tap-to-dismiss with 400 ms grace, auto-dismiss — commits `77b9a7c` + `eaf98be` + `14bea34`
- [x] **HW3** GM arrival narration — after cinematic closes, auto-sends "Przybyłem do: [miejsce]." trigger; system_prompt.txt `## PRZYBYCIE DO NOWEGO MIEJSCA` section instructs GM to give 2-3 sentence location intro — commit `7aa52c7`
- [x] **HW4** Dynamic world expansion — travel to an `unexplored` (phantom) hex auto-generates a new `world_hexes` row using `_auto_generate_hex(q, r, conn)` with spawn-weight sampling; `ok: false` guard in `_wmExecuteTravel` prevents stuck-at-origin — commit `06d75e4`
- [x] **HW5** `spawn_weight` column on `hex_type_config` — migration + initial weights (plains 30 → dungeon/castle 1); `_auto_generate_hex` uses `random.choices(types, weights)` for terrain frequency — commit `06d75e4`
- [x] **HW6** Admin "🌿 Typy Terenu" subtab in Mapa Świata — inline editable table (spawn_weight, travel_hours, ENC%), probability bars, ✏️ full modal with color picker, emoji icon picker (7 groups: Roślinność / Krajobraz / Drzewa / Woda / Miejsca / Symbole / Stworzenia), "Nowy typ" create flow — today, issue #86
- [x] **HW7** `[HEX CONTEXT]` LLM injection — `_inject_hex_terrain_context()` in `game_engine.py` appends terrain_type, Polish label, atmosphere, and narration directive to every system prompt turn; GM now knows the biome and can narrate accordingly — today, issue #86

### Stage 13 — Admin polish

- [x] **AP1** TASK_32: inline "Edytuj i Zatwierdź" modal in World Review Queue — commit `c7d708d`, issue [#104](https://github.com/szmidtpiotr/ai-gm/issues/104). Adds GET/PATCH for pending NPCs/enemies + modal that pre-fills full row, diff-only PATCH, then approves in one flow
- [x] **AP1.v2** Multi-role NPC checkboxes + loot preview/edit in enemy modal + backfill script — commit `b06e4f9`, issue [#108](https://github.com/szmidtpiotr/ai-gm/issues/108). Role checkboxes now in both pending modal AND main NPC tab; pending-enemy modal shows editable loot preview before approve; `scripts/backfill_enemy_loot.py` ran on DEV (26 tables populated)
- [x] **AP2** TASK_32: batch select + bulk approve in Pending review — commit `13054b0`, issue [#105](https://github.com/szmidtpiotr/ai-gm/issues/105). Per-tab toolbar (NPC + Wrogowie) with select-all, count, bulk approve/reject via parallel POSTs. Locations/Weapons deferred (use renderTable)
- [x] **AP3** TASK_33SA: conversational refinement — AI keeps draft state, applies incremental edits — commit `87542ce`, issue [#109](https://github.com/szmidtpiotr/ai-gm/issues/109). Two-mode system prompt (TWORZENIE vs UZUPEŁNIANIA); LLM returns only changed fields in refinement mode; mode badge + placeholder adapt; `changed_fields` in response; `_flashChangedFields()` highlights updated rows (AP4 foundation)
- [x] **AP4** TASK_33SA: form fields highlight changed-in-last-response — commit `1b636ac`, issue [#112](https://github.com/szmidtpiotr/ai-gm/issues/112). Persistent accent dot (●) on field label via `se-field-changed--marked`; cleared on next AI response or manual edit
- [x] **AP5** TASK_33SA: delta line in chat — commit `1b636ac`, issue [#112](https://github.com/szmidtpiotr/ai-gm/issues/112). Backend computes `"Zmieniłem: field: old → new"` string; frontend appends as bordered italic sub-line inside the chat bubble (refinement mode only)

### Stage 14 — Phase 11 Observability

- [x] **O1** TASK_47: `game_events` table + `event_logger` service — commit `cc51537`
- [x] **O2** TASK_48: `llm_call_log` table + admin viewer — commit `cc51537`
- [x] **O3** TASK_49: admin analytics panel (dashboard/events/LLM tabs) — commit `cc51537`
- [x] **O4** TASK_50: MCP server with 9 tools for AI-queryable game data — commit `098e11f`. Streamable HTTP at `https://aigm-dev.studio-colorbox.com/mcp` (NPM proxy). Docs: `docs/MCP_SERVER.md`
- [x] **O4b** MCP admin integration — analytics MCP tab (live status ping, copy URL, Perplexity guide, tool list), topbar status pill polling every 60 s — commit `a0aef22`, issue [#103](https://github.com/szmidtpiotr/ai-gm/issues/103)
- [x] **O4c** MCP write tools (11-14) — `initialize_player_session`, `submit_player_turn`, `change_player_zone`, `flee_from_combat`; HTTP API via demo account; `httpx` dep; `DB_PATH` fix + `depends_on` in dev compose — commit `3d51c44`

### Stage 15 — Phase 12 AI Test Agent — **TEMPORARILY CANCELLED** (2026-05-25)

Browser-driven test agent (T1-T10) deprioritised in favour of the **MCP server** (Stage 14 O4 / O4b / O4c), which gives an external LLM direct read+write access to the live game and lets Perplexity / Claude / any MCP client drive end-to-end scenarios without Playwright selectors. Revisit if MCP-based regression coverage proves insufficient.

- [~] **T1** Update `ai_test_agent/` selectors for hero-first flow — *cancelled*
- [~] **T2** Baseline regression scenario (login → hero → campaign → first turn) — *cancelled*
- [~] **T3** Dungeon regression (enter → 3 rooms → boss → exit → loot verify) — *cancelled*
- [~] **T4** Adversarial: inventory exploit (item duplication via GM) — *cancelled*
- [~] **T5** Adversarial: economy cheat — *cancelled*
- [~] **T6** Adversarial: prompt injection — *cancelled*
- [~] **T7** LLM consistency (10× same scenario) — *cancelled*
- [~] **T8** Admin Test Runner UI updates — *cancelled*
- [~] **T9** CI integration on DEV deploy — *cancelled*
- [~] **T10** Combat Sandbox autotest harness ([#22]) — YAML scenarios via `/api/admin/sandbox/run-scenario` — *cancelled*

### Stage 16 — Known issues / bugs backlog

Bugs discovered during gameplay that don't fit a numbered stage. Pick into the queue when prioritised.

- [x] **K1** GM hallucinates weapons / items the player doesn't own — **FIXED** (issue #87, commit e4dc9b0): `_inject_character_inventory_context()` prepends `[PLAYER INVENTORY]` to system prompt every turn; ZASADA guardrail added to system_prompt.txt; verified mobile 2026-05-24.
- [x] **K2** GM requests unnecessary skill rolls (e.g. Kowalstwo when entering a village square just because a blacksmith is in the scene). Observed during Stage 2B R4 follow-up, 2026-05-19. **FIXED via prompt-only path** — commit `5835952` strengthened the roll_cue rules in `system_prompt.txt`: line 38 explicitly bans roll_cue after reading/examining; line 42 adds `KRYTYCZNA ZASADA: roll_cue WYŁĄCZNIE gdy gracz TERAZ bezpośrednio podejmuje ryzykowną akcję`; lines 49-60 list always-roll examples as player-verb statements ("Przekradam", "Otwieram", "Kujam"…). The optional backend filter was not built — prompt-half held in subsequent gameplay (no new sightings as of 2026-05-25). Reopen if observed again.

### Stage 17 — Future feature backlog (deferred, multi-step)

Larger feature requests that need their own design pass when they reach the queue.

- [x] **F3 — Accelerometer shake-to-roll dice on mobile ([#66]).** Full implementation including secondary scope — commits `5a17448` (base), `283ac57` (directional + haptic), `a44b819` (tilt-aim + manual fallback), `306b26c` (reticle removed per player feedback), issue [#113](https://github.com/szmidtpiotr/ai-gm/issues/113). `_initShakeToRoll` (18 m/s² threshold) + `_initTiltAim` (DeviceOrientation ±30° → vector, silent — no visual aid) + `start_throw_with_vector` in `dice.js`; `navigator.vibrate(60)` haptic on detection; "🎲 Rzuć ręcznie" pill as always-available fallback; iOS motion+orientation permissions bundled in one tap (`localStorage.aigm_motion_permission` / `aigm_orientation_permission`).
- [ ] **F1 — Player account management screen.** Standalone "Twoje konto" view accessible from the main menu / settings. Scope: change password (verify old + new + confirm), change display name, account deletion (soft-delete with grace period), session/device list, **add friend** flow (search by username/email, friend-request pattern, accept/decline). Backend: extend `users` table with `display_name_color`?, add `user_friendships` table with `(user_a, user_b, status)`, new endpoints `/api/me/*`. Frontend: dedicated screen below `heroes`, gold-accent profile card, friend list with status chips. Out of scope: email verification, 2FA (push to Stage 10 Auth security).
- [ ] **F2 — Multiplayer in-character / out-of-character chat between players.** Once campaigns become multi-character, players need a sidechannel to coordinate without GM involvement. Scope: `/say` (in-character, visible to all players in the same campaign, NOT to the GM context — does NOT feed the narrator), `/whisper @player` (private), `/ooc` (out-of-character, all players see, NOT GM context). Backend: `campaign_player_messages` table with `(campaign_id, sender_user_id, recipient_user_id_or_null, channel, body, created_at)`, polling or websocket. Frontend: small "playerzy" channel pane parallel to the chat scroll, color-coded per channel. Open question: how / whether to surface to GM at all (probably NEVER — that's the whole point of "without GM involved").

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
  - [x] **Rename condition keys** — migration `main.py:188-201` collapsed `fear_shaken`/`fear_frightened` → `frightened`, `terror` → `panicked`, seeded `break` row. Keys are lowercase (not UPPERCASE as [D2] suggested) — functional rename complete, casing left as-is to avoid migration churn.
- [x] **T17 Critical Hits** — threshold + hit location table + lasting effects
- [x] **T18 Death Saves** — escalating DC 10/13/16/19, pure d20
- [x] **T19 Flee Mechanic** — opposed DEX, loot abandoned, zone change
- [x] **🆕 `zaskoczony` (Surprised) condition** _(added 2026-05-18 per [D11])_ — fully shipped Stage 3 Z1-Z5
  - [x] DB row in `game_config_conditions` (`zaskoczony` / `Zaskoczony` / `auto_remove=on_damage`)
  - [x] Backend: +2 ATK + first hit ×2 damage + Nat 20 ×4 — `combat_service.py:1666`
  - [x] Auto-clear on damage taken — `combat_service.py:1821`
  - [x] Frontend: ⚡ pulsing badge on combatant row — `app.js:4396` + `styles.css:5425-5447`
  - [x] Triggered by player Stealth success via GM tag `[APPLY_CONDITION:zaskoczony:enemy_key]` — `system_prompt.txt:138-149`

---

## Phase 06 — Economy

- [x] **T20 Inventory & Equipment** — 8-slot anatomical model shipped per [D1]
  - [x] 3-slot functional system (main_hand · off_hand · armor) shipped (legacy)
  - [x] Click-to-equip, combat restrictions, auto-pick (shield→off_hand, dual-wield→off_hand)
  - [x] **8 slots live**: head · torso · l_arm · r_arm · l_leg · r_leg · main_hand · off_hand — `loot_service.py:32` coverage→slot map, `app.js:5909-6080` slot defs + occupation tracking
  - [x] `game_config_items.armor_coverage` column with `head`/`torso`/`limb_arm`/`limb_leg`/`full` enum — `loot_service.py:39 _VALID_ARMOR_COVERAGE`
  - [x] No new gloves/boots types — limb_arm/limb_leg auto-pick left/right (`app.js:5953-5954`)
  - [x] Anatomical slot diagram in character sheet — body areas `larm`/`rarm`/`lleg`/`rleg` rendered in sheet
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

- [x] **T47 Game Event Logging** — `game_events` table, event_logger service — commit `cc51537`
- [x] **T48 LLM Call Log** — `llm_call_log` table, admin viewer — commit `cc51537`
- [x] **T49 Admin Analytics Panel** — dashboard/dice/combat/economy/events/LLM/MCP tabs — commit `cc51537`, MCP tab `a0aef22`
- [x] **T50 MCP Server** — 9 tools, Streamable HTTP, public via `https://aigm-dev.studio-colorbox.com/mcp` — commit `098e11f`

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

Updated 2026-05-24 (after Stage 12-B + 12-C):

```
Phase 01  Foundation        ████████████  5/5    100%
Phase 02  Character         █████████░░░  3.5/4   88%   (T42 partial)
Phase 03  World             ████████████  3/3    100%
Phase 04  Gameplay Loop     ████████████  4/4    100%
Phase 05  Combat            ███████████░  5.5/7   79%   (T16 rename + zaskoczony pending)
Phase 06  Economy           ████████░░░░  6.5/10  65%   (T20/T24/T25V2/T26X partial)
Phase 07  Narrator          ███████████░  3.5/4   88%   (T28 deceased context)
Phase 08  Admin             ██████████░░  4.5/5   90%   (+sandbox bonus, T32/T33SA partial)
Phase 09  Frontend          ██████████░░  4/5     80%   (T44 partial; hex world + T35 done)
Phase 10  Polish            ████████████  5/5    100%   (T36-T39 + T45 all complete)
Phase 11  Observability     ░░░░░░░░░░░░  0/4      0%
Phase 12  AI Test Agent     ░░░░░░░░░░░░  0/10     0%

Bonus stages (not in original plan):
  Stage 11-C  Auth UX (registration / onboarding / invites)  7/7   100%
  Stage 11-D  Slash commands hardening                        8/8   100%
  Stage 11-E  Content library (weapons/armor/items/cons)      5/5   100%
  Stage 12-B  Księga Wiedzy quick tips                        7/7   100%
  Stage 12-C  Hex world expansion + GM biome context          7/7   100%

Overall (original plan):  ~~~~~~~~~~~~~~~~  42/64  66%
Overall (incl. bonus):    ~~~~~~~~~~~~~~~~  ~80 tasks complete
```
