# TASK 09 — Location System (Badge + Safe-for-Rest)

**Status:** 🔶 Partially Built
**Blocking:** None — spec complete
**Depends on:** Nothing (core system already mostly exists)
**Unlocks:** Task 16 (Rest Mechanics — needs safe_for_rest), Task 18 (Loot — needs location tracking)

---

## Overview

The location system already has solid foundations: `validate_move()` enforces movement logic, `game_sessions.current_location_id` tracks where the character is, and a location integrity log records blocked moves. What's missing:
1. **Frontend location badge** — the player should always see where they are
2. **`safe_for_rest` field** — needed for short/long rest mechanics (Task 16)

This is primarily a gap-filling task, not a new system.

---

## Design Context

### Why always show current location?
Players in text-based games lose spatial orientation easily. Without a persistent "you are here" indicator, players don't know if they've moved, where they can go, or how to describe where they want to be. A location badge eliminates this confusion. It also serves a mechanical purpose: the player can see at a glance whether they're in a "safe" location (can rest) or not.

### Why system-enforced location, not LLM-declared?
If the LLM declares the player's location, a player can manipulate the LLM into putting them anywhere: "I walk to the vault" and the LLM says "you are in the vault." This breaks the world simulation. The system maintains the authoritative location state; the LLM can describe the journey, but the SYSTEM records the destination.

### What is safe_for_rest?
A location is safe for rest when the player can sleep there without reasonable fear of interruption. Examples:
- Inn room: safe
- Town square: not safe (public, exposed)
- Wilderness camp: conditional (player must have camping gear — future feature, for now location-based)
- Dungeon corridor: not safe
- Dungeon boss room (post-combat): safe (boss defeated, no threat)

---

## Current State (Code)

**What EXISTS:**
- `game_sessions.current_location_id` — FK to `game_locations`
- `validate_move()` in turns.py — validates location transitions, logs integrity checks
- `location_integrity_log` table in migrations_admin.py
- `game_locations` table with: id, key, label, description, parent_id, location_type (macro/sub), rules, enemy_keys, npc_keys, is_active

**What is MISSING:**
- `safe_for_rest` field on `game_locations`
- Frontend location badge UI component
- API endpoint to get current location for frontend
- Seed data for typical rest-safe locations (inn rooms) needs `safe_for_rest = 1`

---

## Full Specification

### 1. Database — Add safe_for_rest Field

**Migration:**
```sql
ALTER TABLE game_locations ADD COLUMN safe_for_rest INTEGER DEFAULT 0;
```

**Rules for safe_for_rest:**
- `1` (true): player can initiate short or long rest here
- `0` (false): rest attempts blocked with system message "This is not a safe place to rest"

**Default values for common location types:**
| Location type | safe_for_rest |
|---|---|
| Inn / Tavern room | 1 |
| Private dwelling | 1 |
| Safe camp (wilderness) | 1 |
| Town square | 0 |
| Wilderness road | 0 |
| Dungeon corridor | 0 |
| Dungeon room (active enemies) | 0 |
| Dungeon room (cleared) | 0 — must be explicitly marked safe by GM after clearing |

Admin can toggle `safe_for_rest` per location in the admin panel.

### 2. Frontend — Location Badge

**Visual design:**
- Always-visible badge in the top area of the chat panel (or below character name in right panel)
- Format: `📍 {location_label}`
- Example: `📍 Karczma Pod Złotym Pucharem`
- Color: neutral gray normally; green tint if `safe_for_rest = true`; red if in active combat

**When it updates:**
- After every turn where the player's location changes (backend returns new `current_location` in turn response)
- Immediately after opening scene loads (initial location set)

**Data source:**
- Include `current_location: {key, label, safe_for_rest}` in the turn response payload
- Frontend stores current location in state and updates badge on each turn response

### 3. API — Expose Location in Turn Response

The turn endpoint (`POST /campaigns/{id}/turns/stream`) should include in its final SSE event:

```json
{
  "type": "turn_complete",
  "current_location": {
    "key": "golden_cup_inn",
    "label": "Karczma Pod Złotym Pucharem",
    "safe_for_rest": true
  }
}
```

Also: `GET /api/campaigns/{id}/current-location` — standalone endpoint for initial page load.

### 4. Admin Panel — safe_for_rest Toggle

In the "Locations" section of admin panel, each location card/row gets a toggle: "Safe for rest: ON/OFF"

---

## Location Types Reference

```
macro location: large geographic area
  Examples: Graustein (town), The Thornwood (forest), Dungeon of Shadows

sub location: specific area within a macro
  Examples: Golden Cup Tavern (sub of Graustein town), Main Corridor (sub of dungeon)

Movement rules:
  - Between subs in same macro: described narratively, no validation required
  - Between macros: requires logical path, time must pass
  - To an unknown location: only if GM has declared it reachable in narrative
```

---

## Edge Cases

- **Character is in transit between locations (traveling):** Location badge shows last confirmed location with "→ {destination}" indicator
- **Opening scene sets initial location but location doesn't exist in DB:** Auto-create as `pending_review` (Task 10 handles this pattern)
- **Player attempts rest in non-safe location:** Backend rejects with system message: "You cannot rest here — it's not safe." GM narrates why.
- **safe_for_rest location is entered during active combat:** Combat overrides — rest is blocked until combat ends, even in an inn

---

## Test Plan

1. Open game → verify location badge shows starting location from opening scene
2. Navigate to inn → verify badge updates to inn label
3. Attempt rest in town square → verify rejection with system message
4. Attempt rest in inn room → verify allowed (Task 16 test, but location check tested here)
5. Admin toggles `safe_for_rest` on a location → verify rest behavior changes immediately
6. Combat starts in inn → verify rest is blocked until combat ends

---

## Related Tasks
- Task 16 (Healing System — rest mechanics) — reads `safe_for_rest` from current location
- Task 18 (Loot System) — reads `current_location_id` to check loot availability
- Task 10 (Data Tables Source of Truth) — auto-created locations start as `pending_review`
