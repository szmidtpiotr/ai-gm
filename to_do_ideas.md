# To-Do & Ideas Backlog

Planned features and improvements, in rough priority order.
Items marked **[BLOCKED]** depend on another item being done first.

---

## HIGH PRIORITY

### 1. ~~Weapon `effect_json` — Structured Combat Effects~~ ✅ DONE (2026-05-14)

**Implemented:**
- DB: `effect_json TEXT DEFAULT NULL` on `game_config_weapons`
- Combat engine: `_apply_weapon_effects()` — `extra_damage` (doubled on crit), `on_hit_save` (enemy rolls stat vs DC; on fail: extra damage or apply condition from `game_config_conditions`)
- Condition duration countdown + legacy `skip_turn` + legacy `damage_per_turn` now evaluated each round
- AI Kreator: LLM generates valid `effect_json`; Effect Builder UI (visual cards, no raw JSON needed)
- Admin Panel: `effect_json` column + textarea in weapon Edit modal

**Remaining gap — condition `stat_mods`** (see item 1a below):
Conditions like `poisoned` ({stat_mods:{STR:-2}}) show up and deal periodic damage, but stat penalties are NOT yet applied to attack/save rolls. This requires checking conditions before every roll computation.

### 1a. Condition `stat_mods` applied to combat rolls

**What**: When an actor has a condition with `stat_mods` (e.g. poisoned → STR -2), those penalties should reduce their effective stat modifier during attacks and saving throws.

**Where to change:**
- `_combatant_stat_modifier()` in `combat_service.py` — currently reads raw stats; needs to sum up `stat_mods` from all active conditions
- Affects both enemy attacks (enemy combatant conditions) and player saves
- Conditions are already stored in `actor["conditions"]`; just need to fold their `stat_mods` into the modifier

**Complexity:** Medium. One helper function change + tests.

---

### 2. AI Kreator — Q&A / Guided Mode

**[BLOCKED by #1]** — Implement after `effect_json` so the LLM can ask about combat effects in a guided way.

**What**: Add a "Tryb prowadzony" (Guided Mode) toggle to the AI Kreator overlay. Instead of filling all fields at once, the LLM asks targeted questions one at a time:
- "Jaką rolę bojową ma ta broń? (szybka/balansowana/ciężka)"
- "Czy ma specjalny efekt przy trafieniu? (ogień/trucizna/oszołomienie/brak)"
- "Dla kogo jest przeznaczona?" (class picker)
- etc.

Each answer narrows the form, and the LLM pre-fills correlated fields automatically (e.g. "szybka" → d4, DEX, finesse=true).

**Implementation ideas:**
- New session flag `mode: "guided" | "quick"` in SmartEntryMessageReq
- Backend: guided mode skips bulk-fill, returns `next_question` object instead of full draft
- Frontend: guided mode renders the question prominently, quick answers as option chips

---

## MEDIUM PRIORITY

### 3. Bank pomysłów — Visual Rework

**What**: The right panel ("Szkic pomysłu") needs a proper visual design. Currently it's a raw field list. Should look like a proper idea card — formatted sections, collapsible JSON, visual category badge.

**Specific issues:**
- Object fields display as raw JSON pre — needs readable sub-sections
- The whole panel layout could use more breathing room
- "Ready to save" state needs a clearer visual affordance (not just a button appearing)

---

### 4. Bank pomysłów — Link Idea to Campaign

**What**: Allow admin to push an idea from the Ideas Bank directly into a specific campaign's GM plan, rather than just saving to the general bank.

**Flow:**
- Bank card gets a "Dodaj do kampanii" button
- Dropdown to pick active campaign
- Backend merges idea's structured data into `gm_plan_json` (as a new arc or scene hook)
- Or: Warsztat can pull from Bank ("Załaduj pomysł" dropdown in campaign Warsztat)

---

### 5. Campaign V2 Migration Tool

**What**: Admin button in Campaign Monitor to migrate a campaign from V1 schema to V2, or apply incremental patches when the game version updates — without losing any turns, narrative, or character progress.

**Logic:**
- Check `schema_version` and `game_version` on campaign
- If V1 → V2: recalculate HP/Mana with V2 formula, add V2 `sheet_json` fields with defaults (bonds, weaknesses, secret_predisposition), recalculate XP
- If V2 → V2.x: additive-only — new fields get defaults, existing data untouched
- Migration is **idempotent**: re-running it on an already-migrated campaign is a no-op
- Log each migration step to audit log

**Why important for production**: When we deploy game updates, existing player campaigns must not break or lose progress.

---

## LOW PRIORITY / NICE TO HAVE

### 6. Weapon Targeting & AOE in Combat UI

After `effect_json` (#1) is built: surface targeting type and AOE radius in the combat flow. Currently `targeting` (single/aoe/line) and `aoe_radius_m` exist in the DB but the combat engine treats all weapons as single-target.

### 7. AI Kreator — More Tables

Extend Smart Entry to support more tables beyond the current four:
- `game_config_conditions` (status effects)
- `game_config_skills` (new skill definitions)
- `game_config_archetypes` (character class archetypes)

Each needs its own SCHEMA_DESCRIPTOR entry and LLM constraints.

### 8. Ideas Bank — Campaign Seeder

When creating a new campaign, allow admin to pick 2-3 ideas from the Bank as "seeds" — the campaign creation wizard auto-builds initial `gm_plan_json` hooks from the selected ideas.

### 9. Warsztat — JSON diff viewer

In the Campaign Warsztat, instead of showing the LLM's proposed changes as plain text cards, show a proper side-by-side diff of the old and new `gm_plan_json` values with syntax highlighting.

### 10. Admin Panel v2 — Dark/Light theme toggle

Currently locked to dark theme. Add a toggle stored in `localStorage`.

---

## DONE (reference)

- Smart Entry v3 form-first redesign (2026-05-14)
- Warsztat moved inside campaign modal, no dropdown needed (2026-05-14)
- Bank pomysłów (renamed from Warsztaty) (2026-05-14)
- Kreator tab removed from Kampanie hub (2026-05-14)
- Campaign workshop JSON stripped from chat display (2026-05-14)
- Plan GM shows all arcs read-only with NPCs/locations/hooks (2026-05-14)
- Bank pomysłów `is_active` migration fix (2026-05-14)
- Chat bubbles text-selectable across all panels (2026-05-14)
