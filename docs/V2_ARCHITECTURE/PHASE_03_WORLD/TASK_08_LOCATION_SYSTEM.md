# TASK 08 — Location System

**Status:** ✅ Done — commit `cd4c2d1` (2026-05-13)
**Phase:** 03 — World

---

## Overview

Every game session has a current location. The location shapes what NPCs are available, what enemies can appear, and what actions make narrative sense. The location system provides: persistent badge UI, DB-backed location records, movement validation, and context injection per turn.

---

## Location Badge UI

A persistent badge is displayed in the chat panel at all times during a session.

Format: `📍 Location Name`

Visual states:

| Condition                        | Badge tint       |
|----------------------------------|------------------|
| `safe_for_rest = 1`              | Green tint       |
| Combat active (`combat_active`)  | Red tint         |
| Default (no combat, not safe)    | Neutral/no tint  |

The badge is not a button — it is display only. Location name truncates at ~30 characters with ellipsis if longer.

Update trigger: re-render on every turn response that includes a `current_location` object (see API section).

---

## Location Types

| Type  | Description                                           | Movement to/from       |
|-------|-------------------------------------------------------|------------------------|
| macro | Large-scale place: city, forest region, dungeon       | Validated              |
| sub   | Room or area within a macro: tavern room, corridor    | Narrative only         |

**Sub-locations** belong to a parent macro location (`parent_key` field). Moving between sub-locations is narrated naturally — no system validation, no explicit move action required. The player might say "I go to the bar" and the GM updates location to `tavern_common_room` without a move check.

**Macro-location** movement is validated by `validate_move()` (see below). It represents meaningful travel: leaving town, entering the dungeon, crossing the forest.

---

## `safe_for_rest` Field

New field on `game_locations`: `safe_for_rest INTEGER DEFAULT 0`.

| Value | Meaning                                               |
|-------|-------------------------------------------------------|
| 1     | Character can rest here (inn, shelter, secured room)  |
| 0     | No rest allowed (outdoors, dungeon, hostile area)     |

**Edit paths** (per `DECISIONS_2026_05_18.md` [D14, D15]):
- **Admin UI** — checkbox on location edit form (current) **and** on the hex map editor (new in Stage 2B R3)
- **LLM (GM) dynamic** — tag `[SET_SAFE_FOR_REST:location_key:on|off]` so the narrator can flip a location after a story event (e.g. "oczyściłeś karczmę z bandytów" → bezpieczna od teraz). New in Stage 2B R1.
- **Hex dziedziczy** — hex is safe ⇔ has any `game_location` on it with `safe_for_rest=1` (Stage 2B R2 helper `_hex_is_safe_for_rest`).
- **Player action "Rozbij obóz"** — creates a temporary sub-location `temp_camp` on the current hex with `safe_for_rest=1` and `temporary=1` flag. +1h game clock cost, +20% encounter risk during the long rest that follows (Stage 2B R4).

Rest endpoints `POST /api/characters/{id}/rest?type=long|short` check this flag before allowing the rest action. Implementation in Stage 2C per `ROADMAP.md`.

---

## Current Location in Session State

`game_sessions.current_location_id` (FK to `game_locations.id`, nullable).

- Set at session start from the campaign plan's first `key_locations` entry (TASK_07).
- Updated by the system when a move is validated or a narrative sub-location change occurs.
- Never set directly by player input — always mediated by the game engine.

---

## `validate_move()` in `turns.py`

**Existing function** — verify it exists and covers:

1. Target location key resolves to a real record in `game_locations`.
2. Movement makes geographical sense (optional: `connected_to` adjacency list on location, not required for MVP — skip adjacency check in MVP, log a warning instead).
3. No combat currently active in the current location (`combat_active` flag on session). Block move if true; return error: "You cannot leave while combat is active."
4. (New) If target location `safe_for_rest = 1` and origin is `safe_for_rest = 0`: no extra validation needed — moving to safety is always allowed if not in combat.

On successful validation: update `game_sessions.current_location_id` and return the new location object.

---

## API: `current_location` in Turn Response

Every `POST /api/turns` response must include:

```json
{
  "current_location": {
    "key": "string",
    "label": "string",
    "safe_for_rest": 0
  }
}
```

If `current_location_id` is null (session not yet started, or pre-location play): omit the field or return `null`.

The frontend uses this field to update the badge on every turn, regardless of whether a move occurred.

---

## Context Injection on Location Change

When the player moves to a new location (macro or sub), the game engine injects into the next turn's LLM context:

- **Enemy keys** available in the new location (`game_locations.enemy_keys` — JSON array of keys into `game_config_enemies`).
- **NPC keys** present in the new location (`game_locations.npc_keys` — JSON array of keys into `npc_definitions`).

This replaces any enemy/NPC context from the previous location. The LLM narrator uses these keys to populate encounters and dialogue.

Context format injected:

```
[LOCATION CONTEXT]
Current location: {label} ({type})
{description}
Available NPCs: [{key: name}, ...]
Possible threats: [{key: name}, ...]
```

---

## Starting Location

Set from the campaign plan's first `key_locations` entry (TASK_07).

1. Look up the location key in `game_locations`.
2. Found: use existing record.
3. Not found: create a new record from the campaign plan data with `review_status = 'pending_review'` (see TASK_10 for the full lookup-before-create pattern).
4. Set `game_sessions.current_location_id` to the resolved location ID.

---

## DB Changes

```sql
-- Add safe_for_rest to game_locations
ALTER TABLE game_locations ADD COLUMN safe_for_rest INTEGER DEFAULT 0;

-- Add review_status (also in TASK_10, add once)
ALTER TABLE game_locations ADD COLUMN review_status TEXT DEFAULT 'permanent';
```

Add these as a migration in `migrations_admin.py` or `app/db/migrations/`.

---

## Admin Panel

On the location edit form, add:
- `safe_for_rest` toggle (checkbox, label: "Safe for rest")
- `type` selector (macro / sub) if not already present
- `parent_key` text field (shown only when type = sub)

These fields already likely exist in the locations router — verify and add any missing ones.

---

## Implementation Notes
- `safe_for_rest` and `review_status` columns already added in TASK_01 migrations — no new migration needed
- `current_location` added to SSE stream DONE event: `[DONE]{"current_location":{"key":"...","label":"...","safe_for_rest":0}}`
- `get_current_location_info()` in `world_service.py` — JOIN on game_sessions.current_location_id
- Available content index (enemies/NPCs per location) built by `build_available_content_index()` in `world_service.py`
- Starting location from campaign plan (TASK_07) not yet wired — pending Turn Pipeline (TASK_11)
- 25 tests in `test_world_service.py` covering all core functions
