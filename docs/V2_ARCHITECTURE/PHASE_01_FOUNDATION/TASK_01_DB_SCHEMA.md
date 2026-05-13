# TASK 01 — V2 Database Schema

**Phase:** 01 — Foundation  
**Depends on:** nothing (first migration)  
**Blocks:** TASK_02 (Intent Parser), TASK_03 (World State Machine), TASK_04 (Context Injector)  
**File target:** `backend/app/migrations_admin.py` (append to `run_admin_migrations()`)

---

## Overview

V2 introduces a hard separation between mechanical resolution and LLM narration. This requires the DB to track structured state that was previously inferred or embedded in free-text fields. This task provisions all new tables and columns needed before any V2 service code is written. All changes are additive — no existing columns are removed or renamed.

---

## Design Context

In V1, the LLM turn pipeline wrote outcomes directly into session narrative text with no structured record of what mechanically happened. This made it impossible to:

- Audit why a combat ended a certain way
- Resume a session mid-condition (e.g., "character is feared")
- Power enemy behavior rules
- Build a replayable campaign Ideas Bank
- Determine whether a location was safe to rest in

Every new table and column below exists to answer one of those questions from code, not from asking the LLM.

---

## Migration Placement

All SQL in this task goes into `backend/app/migrations_admin.py` inside the `run_admin_migrations()` function. Each block is wrapped in its own `try/except` so a previously-applied partial migration does not break a fresh deployment. Use `IF NOT EXISTS` for CREATE TABLE and catch `OperationalError: duplicate column name` on ALTER TABLE statements.

Relevant function signature in the existing file:

```python
def run_admin_migrations(conn: sqlite3.Connection) -> None:
    """Apply incremental admin schema migrations. Safe to re-run."""
```

Each migration block must be logged at INFO level with a short label, e.g. `"v2-action-log-table"`.

---

## New Tables

### 1. `action_log`

Records every player ACTION tag that was processed by the World State Machine, the mechanical result produced by the resolver, and the final narrative text returned to the player. This is the authoritative audit trail for a session.

```sql
CREATE TABLE IF NOT EXISTS action_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id     INTEGER NOT NULL,
    character_id    INTEGER NOT NULL,
    turn_number     INTEGER NOT NULL,
    action_type     TEXT    NOT NULL,         -- e.g. ATTACK, FLEE, DIALOGUE
    action_params   TEXT    NOT NULL DEFAULT '{}',  -- JSON: {"target": "goblin_1", "weapon": "sword"}
    mechanic_result TEXT    NOT NULL DEFAULT '{}',  -- JSON: see schema below
    narrative_text  TEXT    NOT NULL DEFAULT '',    -- final Polish narrative shown to player
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_action_log_campaign
    ON action_log (campaign_id, turn_number);

CREATE INDEX IF NOT EXISTS idx_action_log_character
    ON action_log (character_id, created_at);
```

**`mechanic_result` JSON schema (examples):**

For ATTACK:
```json
{
  "roll": 17,
  "modifier": 3,
  "total": 20,
  "dc": 14,
  "success": true,
  "damage": 8,
  "crit": false,
  "target_hp_before": 22,
  "target_hp_after": 14,
  "target_alive": true
}
```

For SKILL_ATTEMPT:
```json
{
  "skill_key": "persuasion",
  "roll": 5,
  "modifier": 2,
  "total": 7,
  "dc": 12,
  "success": false,
  "consequence": "npc_hostile"
}
```

For MOVEMENT:
```json
{
  "from_location": "loc_tavern",
  "to_location": "loc_alley",
  "blocked": false
}
```

**Why this table matters:** the Context Injector (TASK_04) reads the most recent `mechanic_result` row to build the MECHANICAL RESULT BLOCK for the narrator. Without this table, that block must be reconstructed from session state, which is fragile.

---

### 2. `character_conditions`

Tracks active conditions on a character. Conditions are game-engine-managed — they are set, updated, and expired by resolvers, never by the LLM.

```sql
CREATE TABLE IF NOT EXISTS character_conditions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id    INTEGER NOT NULL,
    condition_type  TEXT    NOT NULL,  -- see vocabulary below
    severity        INTEGER NOT NULL DEFAULT 1,  -- 1=mild, 2=moderate, 3=severe
    expires_at      TEXT    NULL,       -- ISO8601 datetime OR NULL (permanent until cleared)
    source          TEXT    NOT NULL DEFAULT '',  -- e.g. "goblin_fear_aura", "crit_hit_leg"
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_char_conditions_active
    ON character_conditions (character_id, expires_at);
```

**Condition type vocabulary:**

| condition_type | Description | Mechanical effect |
|---|---|---|
| `fear_shaken` | Minor fear — 1st tier | -1 to all rolls |
| `fear_frightened` | Moderate fear — 2nd tier | -2 to all rolls, must pass WIS DC 12 to attack |
| `terror` | Maximum fear — 3rd tier | Cannot act offensively; must flee or hide |
| `prone` | Knocked down | -2 AC, movement costs double, melee attacks -1 |
| `wound_light` | Minor bleeding | -1 to STR/DEX checks |
| `wound_heavy` | Serious wound | -2 to STR/DEX checks, CON save end of each turn or lose 1 HP |
| `wound_critical` | Life-threatening | -4 to all rolls, DEX save DC 14 each turn or fall prone |
| `blinded` | Cannot see | Attacks at disadvantage (roll twice, take lower) |
| `stunned` | Loss of action | Skip next turn |
| `poisoned` | Toxin active | -2 to all rolls, 1d4 damage at start of each turn |
| `exhausted` | Rest overdue | -1 all rolls per level of exhaustion (stacks) |

**Severity field:** For tiered conditions (fear states), severity maps to tier (1/2/3). For wound conditions, severity maps to the wound label. For binary conditions (stunned, blinded), severity is always 1.

**Expiry logic:** `expires_at = NULL` means the condition persists until explicitly cleared by game logic (e.g., `FLEE` success clears `terror`). Turn-based expiry is tracked by comparing `expires_at` against a turn-count field, not a real clock — use `expires_at` as an integer turn number stored as text when turn-based, ISO8601 when time-based (rest timer). A migration note must document which conditions use which convention.

---

### 3. `enemy_behavior_profiles`

Rule-based AI behavior for each enemy type. The World State Machine uses this table to decide what an enemy does each combat turn without asking the LLM.

```sql
CREATE TABLE IF NOT EXISTS enemy_behavior_profiles (
    enemy_key               TEXT    PRIMARY KEY,  -- FK to game_config_enemies.key
    default_action          TEXT    NOT NULL DEFAULT 'attack',
        -- values: attack | defend | flee | use_special | taunt
    hp_threshold_flee       INTEGER NOT NULL DEFAULT 0,
        -- enemy flees when HP <= this % of max (0 = never flees)
    special_ability_key     TEXT    NULL,
        -- references a key in game_config skills/abilities table
    special_ability_cooldown_turns INTEGER NOT NULL DEFAULT 3,
    dialogue_on_aggro       TEXT    NOT NULL DEFAULT '',
        -- short Polish string displayed when enemy enters combat (system, not LLM)
    dialogue_on_death       TEXT    NOT NULL DEFAULT '',
        -- short Polish string displayed on enemy death
    fear_aura               INTEGER NOT NULL DEFAULT 0,  -- 0=false, 1=true
    fear_dc                 INTEGER NOT NULL DEFAULT 0,
        -- DC for WIS save when fear_aura=1; 0 means no aura check
    FOREIGN KEY (enemy_key) REFERENCES game_config_enemies(key)
);
```

**Default action values:**

- `attack` — target the character with lowest HP
- `defend` — use defensive stance (AC +2 this turn, no attack)
- `flee` — attempt to disengage (triggers FLEE_ATTEMPT in WSM)
- `use_special` — activate `special_ability_key` if cooldown allows, else fall back to `attack`
- `taunt` — emit `dialogue_on_aggro` and force character to make WIS DC 10 save or be compelled to attack this enemy next turn

**`hp_threshold_flee` usage example:** a bandit with `hp_threshold_flee = 25` will attempt to flee when reduced to 25% or below max HP. The flee attempt goes through the WSM FLEE resolver, which rolls DEX vs enemy DEX — it is not automatic.

**`fear_aura` resolution:** at the start of combat (and each time an enemy with `fear_aura=1` becomes visible), each character in the scene must make a WIS save against `fear_dc`. Failure applies `fear_shaken` condition (severity 1). A second failure in the same combat escalates to `fear_frightened` (severity 2). A natural 1 on either save escalates directly to `terror` (severity 3).

---

### 4. `combat_loot`

Loot generated after a combat encounter. Stored in DB so it persists if the player delays pickup, and so partial/abandoned loot can be reasoned about later.

```sql
CREATE TABLE IF NOT EXISTS combat_loot (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id         INTEGER NOT NULL,
    character_id        INTEGER NOT NULL,
    combat_location_id  TEXT    NOT NULL,  -- location key where combat occurred
    loot_items          TEXT    NOT NULL DEFAULT '[]',
        -- JSON array: [{"item_key": "sword_iron", "quantity": 1, "condition": "used"}, ...]
    status              TEXT    NOT NULL DEFAULT 'available',
        -- available | partial | claimed | abandoned | expired
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id)
);

CREATE INDEX IF NOT EXISTS idx_combat_loot_campaign
    ON combat_loot (campaign_id, status);
```

**Status transitions:**

```
available → partial   (player picked up some items)
available → claimed   (player picked up all items)
available → abandoned (player explicitly left the scene)
available → expired   (GM rule: loot expires after N sessions without pickup)
partial   → claimed
partial   → abandoned
partial   → expired
```

**`loot_items` JSON schema:**
```json
[
  {"item_key": "sword_iron",   "quantity": 1, "condition": "used"},
  {"item_key": "gold_coin",    "quantity": 12, "condition": "pristine"},
  {"item_key": "potion_minor", "quantity": 1, "condition": "pristine"}
]
```

`condition` is one of: `pristine`, `used`, `damaged`, `broken`. Damaged/broken items may have reduced sell value (handled in shop service).

---

### 5. `campaign_ideas`

The Ideas Bank. A structured library of narrative seeds, scene modules, NPC concepts, locations, encounter templates, and plot twists that the game engine can pull from when building campaign content. Unlike free-form notes, every entry has a `structured_data` JSON field that the engine can parse directly.

```sql
CREATE TABLE IF NOT EXISTS campaign_ideas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT    NOT NULL,
        -- seed | scene_module | npc_concept | location | encounter | plot_twist
    title           TEXT    NOT NULL,
    description     TEXT    NOT NULL DEFAULT '',
    structured_data TEXT    NOT NULL DEFAULT '{}',
        -- game-engine-readable JSON; schema varies by category (see below)
    tags            TEXT    NOT NULL DEFAULT '[]',
        -- JSON array of strings e.g. ["dark", "undead", "forest"]
    quality_rating  INTEGER NOT NULL DEFAULT 0,
        -- 0-5 stars; 0 = unreviewed
    times_used      INTEGER NOT NULL DEFAULT 0,
    created_by      TEXT    NOT NULL DEFAULT 'system',
        -- "system" | "admin" | "llm_generated_reviewed"
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    review_status   TEXT    NOT NULL DEFAULT 'draft'
        -- draft | approved | rejected | archived
);

CREATE INDEX IF NOT EXISTS idx_campaign_ideas_category
    ON campaign_ideas (category, review_status, quality_rating);

CREATE INDEX IF NOT EXISTS idx_campaign_ideas_tags
    ON campaign_ideas (tags);  -- partial scan; full-text search handled in Python
```

**`structured_data` schema by category:**

`encounter`:
```json
{
  "enemy_keys": ["goblin_scout", "goblin_shaman"],
  "enemy_count_range": [3, 6],
  "location_tag_requires": ["forest", "wilderness"],
  "difficulty": "medium",
  "special_trigger": "ambush",
  "loot_table_key": "goblin_standard"
}
```

`scene_module`:
```json
{
  "scene_type": "investigation",
  "required_npc_keys": ["innkeeper_old_boris"],
  "optional_npc_keys": ["merchant_traveling"],
  "clues": [
    {"clue_id": "bloodstain_floor", "description": "Plama krwi na podłodze", "reveals": "murder_happened_here"}
  ],
  "resolution_conditions": {"find_clues": 2, "talk_to_npc": 1}
}
```

`npc_concept`:
```json
{
  "archetype": "corrupt_guard",
  "faction": "town_guard",
  "attitude_default": "hostile",
  "bribable": true,
  "secret": "works_for_thieves_guild",
  "keyword_triggers": ["bribe", "thieves", "captain"]
}
```

`location`:
```json
{
  "terrain_type": "dungeon",
  "atmosphere_tags": ["dark", "damp", "ancient"],
  "safe_for_rest": false,
  "connection_slots": 3,
  "hazard_type": "trap",
  "loot_table_key": "dungeon_generic"
}
```

---

## Altered Columns (ALTER TABLE)

These are additive — no existing data is affected.

### `game_locations`

```sql
ALTER TABLE game_locations
    ADD COLUMN safe_for_rest INTEGER NOT NULL DEFAULT 0;
    -- 0 = dangerous (no rest), 1 = safe for short rest, 2 = safe for long rest

ALTER TABLE game_locations
    ADD COLUMN review_status TEXT NOT NULL DEFAULT 'permanent';
    -- permanent | draft | archived
```

**`safe_for_rest` usage:** the World State Machine's REST validator reads this column. If `safe_for_rest = 0`, the action is blocked with a system message. No LLM involved in that decision.

**`review_status` on locations:** `permanent` = canonical world content, never auto-expires. `draft` = added during a session by LLM narration, pending admin review. `archived` = removed from active world but kept for history.

---

### `npc_definitions`

```sql
ALTER TABLE npc_definitions
    ADD COLUMN review_status TEXT NOT NULL DEFAULT 'permanent';

ALTER TABLE npc_definitions
    ADD COLUMN keyword_triggers TEXT NOT NULL DEFAULT '[]';
    -- JSON array: [{"keyword": "guild", "must_reveal_info": "The guild meets at the docks.", "is_secret": false}, ...]

ALTER TABLE npc_definitions
    ADD COLUMN personality_prompt TEXT NOT NULL DEFAULT '';
    -- Short fragment injected into narrator prompt:
    -- e.g. "Speaks in short sentences. Always suspicious. Never smiles."
```

**`keyword_triggers` JSON schema:**
```json
[
  {
    "keyword": "guild",
    "must_reveal_info": "Gilda spotyka się w każdą środę przy doках.",
    "is_secret": false
  },
  {
    "keyword": "murder",
    "must_reveal_info": "Widział mężczyznę w płaszczu tej nocy.",
    "is_secret": true
  }
]
```

`is_secret = true` means the trigger fires only if the character has a `PERSUASION` or `INTIMIDATION` roll that passed a DC set on the NPC (handled in DIALOGUE resolver). `is_secret = false` means the info is revealed freely when the topic is raised.

**`personality_prompt` examples:**
- `"Mówi skrótowo. Zawsze podejrzliwy. Nigdy się nie uśmiecha."`
- `"Entuzjastyczny kupiec. Używa wielu komplementów. Zawsze proponuje zniżkę na końcu."`
- `"Tajemnicza wiedźma. Mówi w zagadkach. Unika bezpośrednich odpowiedzi."`

---

### `game_config_enemies`

```sql
-- V2 new columns
ALTER TABLE game_config_enemies ADD COLUMN review_status TEXT NOT NULL DEFAULT 'permanent';
ALTER TABLE game_config_enemies ADD COLUMN behavior_profile_key TEXT NULL;
ALTER TABLE game_config_enemies ADD COLUMN hit_location_table TEXT NOT NULL DEFAULT 'standard';
    -- standard | humanoid_armored | beast | undead | construct
ALTER TABLE game_config_enemies ADD COLUMN fear_aura INTEGER NOT NULL DEFAULT 0;
ALTER TABLE game_config_enemies ADD COLUMN fear_dc INTEGER NOT NULL DEFAULT 12;
ALTER TABLE game_config_enemies ADD COLUMN skills_json TEXT NOT NULL DEFAULT '{}';
    -- e.g. {"perception": 2, "stealth": 1, "athletics": 3}
    -- Used by Mechanic Resolver for opposed skill tests:
    -- player Stealth vs enemy skills_json.perception rank
```

**`hit_location_table` values:** `standard` = head/torso/limbs. `undead` = different crit effects (severed limb doesn't stop it). `construct` = immune to fear and bleeding. `beast` = different body parts.

**`skills_json`:** Allows custom enemies to have real skill ranks matching the player skill system. When a player attempts an opposed skill test against this enemy, the resolver checks this JSON first. If the skill is not present, falls back to a tier-based default (weak=0, standard=1, elite=2, boss=3).

**`dex_modifier`:** Already exists in DB — add to admin panel as editable field. Critical for V2 initiative and flee mechanic.

---

## V1 Cleanup Migrations (run before V2 additions)

These fix inconsistencies in the existing schema before new V2 columns are added.

### `game_config_items` — cleanup

```sql
-- Add ac_bonus as direct column (simpler than reading effect_json)
ALTER TABLE game_config_items ADD COLUMN ac_bonus INTEGER NOT NULL DEFAULT 0;

-- Migrate existing armor AC values out of effect_json into ac_bonus
UPDATE game_config_items
SET ac_bonus = CAST(json_extract(effect_json, '$.stat_mods.AC') AS INTEGER)
WHERE item_type = 'armor'
  AND json_extract(effect_json, '$.stat_mods.AC') IS NOT NULL;

-- Drop old weight column (superseded by weight_kg)
-- NOTE: SQLite doesn't support DROP COLUMN in older versions.
-- If SQLite >= 3.35: ALTER TABLE game_config_items DROP COLUMN weight;
-- Otherwise: recreate the table without the column during a future cleanup migration.

-- Drop proficiency_classes (was removed, verify it's gone)
-- ALTER TABLE game_config_items DROP COLUMN proficiency_classes; (if still present)
```

### `game_config_loot_entries` — cleanup

```sql
-- Drop currency_code — V2 uses unified gold, not per-entry currency
-- ALTER TABLE game_config_loot_entries DROP COLUMN currency_code; (if SQLite >= 3.35)
```

### `game_config_archetypes` — add hp_base

```sql
ALTER TABLE game_config_archetypes ADD COLUMN hp_base INTEGER NOT NULL DEFAULT 10;

-- Seed correct values:
UPDATE game_config_archetypes SET hp_base = 10 WHERE key = 'warrior';
UPDATE game_config_archetypes SET hp_base = 6  WHERE key = 'scholar';
UPDATE game_config_archetypes SET hp_base = 8  WHERE key = 'ranger'; -- future
```

### `game_config_consumables` — add review flags

```sql
ALTER TABLE game_config_consumables ADD COLUMN ai_generated INTEGER NOT NULL DEFAULT 0;
ALTER TABLE game_config_consumables ADD COLUMN approved INTEGER NOT NULL DEFAULT 1;
```

### `game_locations` — V2 additions + cleanup

```sql
-- World Builder positioning
ALTER TABLE game_locations ADD COLUMN map_x REAL DEFAULT NULL;
ALTER TABLE game_locations ADD COLUMN map_y REAL DEFAULT NULL;
ALTER TABLE game_locations ADD COLUMN map_icon TEXT NOT NULL DEFAULT 'town'
    CHECK(map_icon IN ('town','dungeon','forest','ruin','castle','cave','road','camp','port'));
ALTER TABLE game_locations ADD COLUMN visible_before_visit INTEGER NOT NULL DEFAULT 0;
ALTER TABLE game_locations ADD COLUMN safe_for_rest INTEGER NOT NULL DEFAULT 0;
ALTER TABLE game_locations ADD COLUMN review_status TEXT NOT NULL DEFAULT 'permanent'
    CHECK(review_status IN ('permanent','pending_review','discarded'));
ALTER TABLE game_locations ADD COLUMN parent_key TEXT DEFAULT NULL;
    -- String key equivalent of parent_id. Both maintained for compatibility.
    -- New V2 code uses parent_key; parent_id kept for FK integrity.

-- Seed parent_key from parent_id (one-time data migration)
UPDATE game_locations AS l
SET parent_key = (SELECT key FROM game_locations p WHERE p.id = l.parent_id)
WHERE parent_id IS NOT NULL;

-- NOTE: enemy_keys and npc_keys JSON columns are REPLACED by join tables
-- (location_enemy_assignments, location_npc_assignments — see below).
-- The JSON columns are kept during migration for backwards compat, then dropped
-- after join table data is verified.
```

### `npcs` — V2 additions

```sql
ALTER TABLE npcs ADD COLUMN personality_prompt TEXT DEFAULT NULL;
    -- Short string injected into LLM narrator to keep NPC in character.
    -- E.g. "Gruff innkeeper. Short sentences. Deeply suspicious of strangers."

ALTER TABLE npcs ADD COLUMN keyword_triggers TEXT NOT NULL DEFAULT '[]';
    -- JSON array: [{keyword: "murders", must_reveal_info: "Found body near mill", is_secret: false}]
    -- When player dialogue includes a keyword, must_reveal_info is injected as constraint.

ALTER TABLE npcs ADD COLUMN review_status TEXT NOT NULL DEFAULT 'permanent'
    CHECK(review_status IN ('permanent','pending_review','discarded'));
```

### Location Join Tables (replace JSON arrays on game_locations)

```sql
CREATE TABLE IF NOT EXISTS location_npc_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    location_key    TEXT NOT NULL,
    npc_key         TEXT NOT NULL,
    assignment_type TEXT NOT NULL DEFAULT 'resident'
        CHECK(assignment_type IN ('resident','visitor','quest_only','patrol')),
    notes           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(location_key, npc_key)
);

CREATE TABLE IF NOT EXISTS location_enemy_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    location_key    TEXT NOT NULL,
    enemy_key       TEXT NOT NULL,
    spawn_chance    REAL NOT NULL DEFAULT 1.0,
    max_count       INTEGER NOT NULL DEFAULT 3,
    notes           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(location_key, enemy_key)
);

-- Migrate existing JSON data into join tables (one-time)
-- Run after tables created:
--   Python script reads game_locations.enemy_keys JSON → inserts into location_enemy_assignments
--   Python script reads game_locations.npc_keys JSON + npc_locations table → inserts into location_npc_assignments
```

---

## New Tables — World Builder & Hero Persistence

*(Added after initial task creation — decisions from world builder design session)*

### `location_connections`

Defines travel routes between macro locations. Used by the World State Machine to validate movement and by the World Builder to render edges.

```sql
CREATE TABLE IF NOT EXISTS location_connections (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    from_location_key   TEXT NOT NULL,
    to_location_key     TEXT NOT NULL,
    travel_hours        REAL NOT NULL DEFAULT 1.0,
    travel_description  TEXT,
    danger_level        TEXT NOT NULL DEFAULT 'low'
        CHECK(danger_level IN ('none','low','medium','high','extreme')),
    requires_item_key   TEXT DEFAULT NULL,
    requires_flag       TEXT DEFAULT NULL,
    is_bidirectional    INTEGER NOT NULL DEFAULT 1,
    is_active           INTEGER NOT NULL DEFAULT 1,
    encounter_chance    REAL NOT NULL DEFAULT 0.1,
    -- Admin-configurable per route. 0.0 = safe, 0.8 = almost certain encounter.
    -- See 12_TRAVEL_SYSTEM.md for suggested defaults by danger_level.
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(from_location_key, to_location_key)
);
```

### `location_npc_assignments`

Replaces the `npc_keys` JSON array on `game_locations` with a proper relation. Supports assignment types (resident, visitor, quest_only).

```sql
CREATE TABLE IF NOT EXISTS location_npc_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    location_key    TEXT NOT NULL,
    npc_key         TEXT NOT NULL,
    assignment_type TEXT NOT NULL DEFAULT 'resident'
        CHECK(assignment_type IN ('resident','visitor','quest_only','patrol')),
    notes           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(location_key, npc_key)
);
```

### `location_enemy_assignments`

Replaces the `enemy_keys` JSON array on `game_locations`. Adds spawn chance and max count per encounter.

```sql
CREATE TABLE IF NOT EXISTS location_enemy_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    location_key    TEXT NOT NULL,
    enemy_key       TEXT NOT NULL,
    spawn_chance    REAL NOT NULL DEFAULT 1.0,
    max_count       INTEGER NOT NULL DEFAULT 3,
    notes           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(location_key, enemy_key)
);
```

### `character_campaign_history`

Records each campaign a hero has completed. Stores outcome and AI-generated chapter summary. Enables cross-campaign Hero Journal.

```sql
CREATE TABLE IF NOT EXISTS character_campaign_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id    INTEGER NOT NULL,
    campaign_id     INTEGER NOT NULL,
    outcome         TEXT NOT NULL DEFAULT 'active'
        CHECK(outcome IN ('active','victory','death','abandoned')),
    chapter_summary TEXT,
    xp_earned       INTEGER NOT NULL DEFAULT 0,
    gold_at_end     INTEGER NOT NULL DEFAULT 0,
    turns_count     INTEGER NOT NULL DEFAULT 0,
    completed_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_char_campaign_history
    ON character_campaign_history (character_id, completed_at);
```

### `game_sessions` — in-game clock

```sql
ALTER TABLE game_sessions ADD COLUMN ingame_hours INTEGER NOT NULL DEFAULT 9;
-- Campaigns start at 09:00 (morning). Advances on: travel, short rest (+1h), long rest (+8h).
-- Used by GM narrator for time-of-day context and by travel system for dungeon cooldown checks.
-- See 12_TRAVEL_SYSTEM.md.
```

### `game_config_xp_awards`

Admin-configurable XP award amounts. Mechanic Resolver reads from this table instead of hardcoded values. See `TASK_26_XP_CONFIG_AND_LOG.md`.

```sql
CREATE TABLE IF NOT EXISTS game_config_xp_awards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL
        CHECK(category IN ('combat','campaign','exploration','skills','narrative','session')),
    source_key  TEXT UNIQUE NOT NULL,
    label       TEXT NOT NULL,
    description TEXT,
    xp_amount   INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    is_locked   INTEGER NOT NULL DEFAULT 0,
    locked_at   TEXT DEFAULT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Seed data in `TASK_26_XP_CONFIG_AND_LOG.md` — 24 rows covering all XP sources.

### `character_quests`

Tracks active and completed quests per hero per campaign. See `15_QUEST_SYSTEM.md`.

```sql
CREATE TABLE IF NOT EXISTS character_quests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id        INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    campaign_id         INTEGER NOT NULL REFERENCES campaigns(id),
    quest_type          TEXT NOT NULL DEFAULT 'main'
        CHECK(quest_type IN ('main','side')),
    title               TEXT NOT NULL,
    narrative           TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active','completed','failed')),
    resolution          TEXT DEFAULT NULL,
    resolution_narrative TEXT DEFAULT NULL,
    created_turn        INTEGER,
    completed_turn      INTEGER DEFAULT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_character_quests_active
    ON character_quests (character_id, status, campaign_id);
```

### `character_xp_grants` — additional columns

```sql
-- Already exists. Add these columns for XP log tracing (TASK_26):
ALTER TABLE character_xp_grants ADD COLUMN source_key TEXT DEFAULT NULL;
ALTER TABLE character_xp_grants ADD COLUMN campaign_id INTEGER DEFAULT NULL;
ALTER TABLE character_xp_grants ADD COLUMN turn_number INTEGER DEFAULT NULL;
ALTER TABLE character_xp_grants ADD COLUMN detail TEXT DEFAULT NULL;
```

### `character_dungeon_runs`

Tracks dungeon cooldowns for the farmable dungeon run system.

```sql
CREATE TABLE IF NOT EXISTS character_dungeon_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id    INTEGER NOT NULL,
    location_key    TEXT NOT NULL,
    cleared_at      TEXT NOT NULL,
    cooldown_until  TEXT NOT NULL,
    run_count       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(character_id, location_key)
);
```

## New Columns — World Builder & Hero Persistence

```sql
-- World Builder map positioning
ALTER TABLE game_locations ADD COLUMN map_x REAL DEFAULT NULL;
ALTER TABLE game_locations ADD COLUMN map_y REAL DEFAULT NULL;
ALTER TABLE game_locations ADD COLUMN map_icon TEXT NOT NULL DEFAULT 'town'
    CHECK(map_icon IN ('town','dungeon','forest','ruin','castle','cave','road','camp','port'));
ALTER TABLE game_locations ADD COLUMN visible_before_visit INTEGER NOT NULL DEFAULT 0;

-- Hero persistence
ALTER TABLE characters ADD COLUMN hero_status TEXT NOT NULL DEFAULT 'active'
    CHECK(hero_status IN ('active','fallen','retired'));
ALTER TABLE characters ADD COLUMN visited_location_keys TEXT NOT NULL DEFAULT '[]';
-- JSON array of location keys — persists across campaigns

-- Dungeon run tracking on campaign_ideas
ALTER TABLE campaign_ideas ADD COLUMN cooldown_hours INTEGER NOT NULL DEFAULT 0;
-- 0 = non-repeatable (story dungeon), >0 = cooldown duration
```

---

## Migration Code Pattern

Each block in `run_admin_migrations()` should follow this pattern:

```python
# v2: action_log table
try:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS action_log (
            ...
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_action_log_campaign ON action_log (campaign_id, turn_number)")
    conn.commit()
    logger.info("migration applied", label="v2-action-log-table")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        logger.debug("migration already applied", label="v2-action-log-table")
    else:
        raise
```

For ALTER TABLE:
```python
# v2: safe_for_rest on game_locations
try:
    conn.execute("ALTER TABLE game_locations ADD COLUMN safe_for_rest INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    logger.info("migration applied", label="v2-safe-for-rest")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        logger.debug("migration already applied", label="v2-safe-for-rest")
    else:
        raise
```

---

## Files Modified

| File | Change |
|---|---|
| `backend/app/migrations_admin.py` | Add all migration blocks inside `run_admin_migrations()` |
| `backend/app/models.py` (or equivalent SQLModel file) | Add Python model classes for `ActionLog`, `CharacterCondition`, `EnemyBehaviorProfile`, `CombatLoot`, `CampaignIdea` |
| `backend/app/main.py` | Verify `run_admin_migrations()` is called in lifespan (it already is — just confirm) |

No router or service files are modified in this task. The tables are created now; they are used starting in TASK_02.

---

## Edge Cases

1. **Partial migration re-run:** The server restarts and `run_admin_migrations()` runs again. All `CREATE TABLE IF NOT EXISTS` are idempotent. All `ALTER TABLE` blocks catch `duplicate column name`. No data loss.

2. **`character_conditions` with no expiry:** `expires_at = NULL` must not be mistakenly interpreted as "expired". The query for active conditions must use `WHERE expires_at IS NULL OR expires_at > current_turn_or_datetime`.

3. **`enemy_behavior_profiles` with no profile:** Many enemies in `game_config_enemies` will have `behavior_profile_key = NULL` until profiles are defined. The World State Machine must handle this gracefully by falling back to a default behavior (attack lowest-HP target).

4. **`combat_loot` orphan on campaign delete:** `ON DELETE CASCADE` on `campaign_id` handles cleanup automatically. The same cascade must be verified for `action_log`.

5. **`campaign_ideas` full-text search on tags:** The `tags` column is JSON. SQLite has no JSON index. The Python layer must parse tags in-memory when filtering by tag. For large ideas banks (>10,000 rows), add a virtual FTS5 table in a later migration — out of scope for TASK_01 but note it here.

6. **`keyword_triggers` with `is_secret` and no DC:** The NPC dialogue resolver must check whether the NPC definition has a `secret_reveal_dc` field. If not present, default to DC 14. This field is not added in this task (no column for it yet) — use `15` as a hard-coded fallback in the resolver until a later task adds it.

7. **`hit_location_table` values not validated at DB level:** SQLite has no CHECK constraints for this column in this migration. The combat resolver must validate the value against a Python enum and fall back to `standard` if the value is unrecognized. A CHECK constraint can be added later via a recreate migration.

---

## Test Checklist

- [ ] Run migration on a fresh DB — all tables created, all indexes present
- [ ] Run migration on existing V1 DB — all ALTER TABLE succeed, no data lost
- [ ] Re-run migration on already-migrated DB — no errors, idempotent
- [ ] Insert a row into `action_log` with valid `mechanic_result` JSON — verify retrieval
- [ ] Insert a `character_conditions` row with `expires_at = NULL` — verify active query returns it
- [ ] Insert a `character_conditions` row with a past `expires_at` — verify active query excludes it
- [ ] Insert an `enemy_behavior_profiles` row — verify FK to `game_config_enemies` is respected
- [ ] Insert a `game_locations` row without specifying `safe_for_rest` — verify default is `0`
- [ ] Insert an `npc_definitions` row with `keyword_triggers` JSON array — verify retrieval and JSON parsing
- [ ] Insert a `campaign_ideas` row with `structured_data` for each category — verify no schema errors
- [ ] Delete a campaign — verify `action_log` and `combat_loot` rows cascade-delete
- [ ] Query `campaign_ideas` filtered by `category = 'encounter'` and `review_status = 'approved'` — verify index is used (EXPLAIN QUERY PLAN)
