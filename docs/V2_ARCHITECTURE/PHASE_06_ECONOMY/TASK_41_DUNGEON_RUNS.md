# TASK 41 — Dungeon Runs

**Phase:** 06 — Economy
**Status:** ✅ Done

## Implementation Status

- DB: `game_dungeons` table (key, label, location_key, rooms, enemy_pool, boss_enemy, loot_tier, atmosphere, cooldown_hours, min_level) + 3 seeds (goblin_warren, rat_tunnels, crypt_of_bones)
- DB: `character_dungeon_runs` table (UNIQUE per character+location, run_count, cooldown_until)
- `dungeon_service.py`: get_dungeon/list_dungeons, check_cooldown, complete_dungeon, enter_dungeon, advance_room, generate_dungeon_instance, scale_enemy_stats, get_active_dungeon_run
- Enemy scaling: ×0.75 (L1-2) → ×1.0 (L3-4) → ×1.25 (L5-6) → ×1.5 (L7-8) → ×2.0 (L9+); boss one tier above; damage die stepped up at ≥1.5×
- `dungeons.py` endpoints: GET /dungeons, GET /dungeons/{key}, POST /dungeons/{key}/enter (423 if cooldown), POST /dungeons/advance-room, GET /campaigns/{id}/dungeon-run, POST /dungeons/{key}/complete
- Admin panel: Świat → Lochy tab (list, create, edit, delete dungeons via /api/admin/dungeons)
- Note: World Builder integration (TASK 40) needed for map node authoring; dungeon backend works standalone
**Depends on:** TASK 40 (World Builder — dungeon nodes), TASK 14 (Combat)

---

## Overview

Dungeons are standalone combat-and-exploration content that can be entered directly from the world map. They are distinct from campaign story content — a dungeon has no narrative arc, no plan beats, and no LLM-driven plot. The GM generates atmospheric descriptions for rooms and encounters, but the dungeon structure itself is data-driven and admin-authored. Exploration dungeons are repeatable with a cooldown timer, functioning as farmable content that rewards grinding without breaking the campaign economy.

---

## Two Types of Dungeon

### Story Dungeons

- Part of a campaign's narrative plot (e.g., the final boss lives here).
- Authored directly into the campaign plan by the LLM during generation.
- Not repeatable — cleared once, marked done.
- No cooldown. No entry from the world map outside the campaign context.
- Not covered by this task — handled by campaign plan flow (TASK 07 / TASK 13).

### Exploration Dungeons

- Standalone. Available at all times outside active campaign story.
- Accessible as nodes on the world map (icon: `dungeon`).
- Repeatable with configurable cooldown.
- No story context — GM narrates atmosphere and combat only.
- This task covers exploration dungeons exclusively.

---

## Dungeon Seed Format

Exploration dungeons are defined by a `campaign_ideas` record with `category='dungeon_seed'`. The `structured_data` JSON field holds the dungeon configuration:

```json
{
  "category": "dungeon_seed",
  "title": "Goblin Warren",
  "location_key": "goblin_warren",
  "rooms": 7,
  "enemy_pool": ["goblin", "goblin_archer", "goblin_shaman"],
  "boss_enemy": "goblin_warchief",
  "loot_tier": "standard",
  "atmosphere": "cramped tunnels, smell of rot, flickering torchlight",
  "cooldown_hours": 72
}
```

| Field | Type | Description |
|---|---|---|
| `category` | string | Always `"dungeon_seed"` |
| `title` | string | Display name of the dungeon |
| `location_key` | string | Must match a `game_locations.key` with `map_icon='dungeon'` |
| `rooms` | integer | Number of rooms to generate (3–15 range recommended) |
| `enemy_pool` | string[] | Keys from `enemy_definitions` — drawn randomly for non-boss rooms |
| `boss_enemy` | string | Key from `enemy_definitions` — spawns in the final room |
| `loot_tier` | string | `"poor"` / `"standard"` / `"rich"` / `"legendary"` |
| `atmosphere` | string | Injected into every GM narrator prompt for this dungeon |
| `cooldown_hours` | integer | Hours before dungeon respawns after being cleared |

---

## World Map Integration

Admin creates an exploration dungeon in two steps:

1. **Create the location node** in World Builder (TASK 40): set `map_icon='dungeon'`, define connections to adjacent nodes as normal.
2. **Create the dungeon seed** in Ideas Workshop: create a `campaign_ideas` record with `category='dungeon_seed'` and `location_key` matching the location node created above.

The dungeon becomes available on the player world map as a `dungeon` icon node. The hero must physically travel to the dungeon location before entering — normal map traversal rules apply (movement actions, travel time, danger checks).

---

## Repeatability and Cooldown

**CONFIRMED:** Cooldown is admin-configurable per dungeon seed via `campaign_ideas.cooldown_hours`. Suggested defaults: easy=48h, standard=72h, hard/rare=168h. No global default. See `10_ALL_OPEN_DECISIONS_RESOLVED.md`.

### New Table — character_dungeon_runs

```sql
CREATE TABLE character_dungeon_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    location_key    TEXT NOT NULL,
    cleared_at      TEXT NOT NULL,
    -- ISO 8601 timestamp of most recent clear
    cooldown_until  TEXT NOT NULL,
    -- cleared_at + cooldown_hours. Entry blocked until this time passes.
    run_count       INTEGER DEFAULT 1
    -- Incremented on each subsequent clear of this dungeon
);
```

One record per (character, location_key) pair. Updated on each subsequent clear — no historical rows.

### Cooldown Logic

On dungeon clear:
1. Look up `character_dungeon_runs` for `(character_id, location_key)`.
2. If no record: INSERT with `cleared_at=now`, `cooldown_until=now+cooldown_hours`, `run_count=1`.
3. If record exists: UPDATE `cleared_at=now`, `cooldown_until=now+cooldown_hours`, `run_count += 1`.

On dungeon entry attempt:
1. Look up `character_dungeon_runs` for `(character_id, location_key)`.
2. If no record or `cooldown_until < now`: entry allowed, dungeon is fresh.
3. If `cooldown_until >= now`: entry blocked. Return 423 Locked with body:
   ```json
   { "error": "dungeon_on_cooldown", "cooldown_until": "2026-05-15T14:22:00" }
   ```
   Frontend displays: *"Goblin Warren powróci za 48 godzin."*

---

## Dungeon Structure at Runtime

When a dungeon is entered, the backend generates a dungeon instance in memory (not persisted between sessions):

```python
{
  "location_key": "goblin_warren",
  "rooms": [
    { "room_id": 1, "enemy_key": "goblin", "cleared": False },
    { "room_id": 2, "enemy_key": "goblin_archer", "cleared": False },
    ...
    { "room_id": 7, "enemy_key": "goblin_warchief", "cleared": False, "is_boss": True }
  ],
  "current_room": 1,
  "atmosphere": "cramped tunnels, smell of rot, flickering torchlight"
}
```

This state is stored in `game_sessions.session_flags.dungeon_run` for the duration of the run. On disconnect/reconnect, the hero resumes from the current room.

Room generation rules:
- Rooms 1 through `rooms-1`: sample `enemy_key` randomly from `enemy_pool`.
- Room `rooms` (final room): always `boss_enemy`.
- Enemy count per room: 1 + floor(hero_level / 3), minimum 1, maximum 4.

---

## Enemy Scaling

Exploration dungeons scale to the hero's current level. Level is computed as `total_xp ÷ 100` (see TASK_25_XP_PROGRESSION_V2) and used as the scaling proxy.

| Hero Level Range | Enemy Stat Multiplier | Notes |
|---|---|---|
| 1–2 | ×0.75 | Weakened for fresh heroes |
| 3–4 | ×1.0 | Base stats from `enemy_definitions` |
| 5–6 | ×1.25 | Buffed |
| 7–8 | ×1.5 | Elite tier |
| 9–10 | ×2.0 | Veteran tier |

Scaling applies to: `max_hp`, `damage_dice` (increase die size by one step: d4→d6→d8→d10→d12), `armor_class`.

Boss scaling: boss enemy is always one tier above the current enemy multiplier tier. At hero level 5–6 (×1.25 multiplier), boss uses ×1.5 stats.

Scaling is computed at dungeon entry, applied to enemy definitions in memory, and stored in `session_flags.dungeon_run.enemy_overrides`. Base `enemy_definitions` records are never modified.

---

## GM Narration in Dungeons

Dungeon runs have no campaign plan and no LLM intent parsing beyond combat. The narrator context in each room is simplified:

1. **Room entry narration:** GM receives `atmosphere`, room number, and enemy description. Generates 2–3 sentence flavour text.
2. **Combat narration:** Standard combat narrator flow (TASK 14) — no change.
3. **Room cleared narration:** GM generates 1–2 sentence "area clear" flavour.
4. **Dungeon cleared narration:** Final boss defeated → GM generates a short closing paragraph (no loot mentioned — loot display handled by system UI).

No ACTION parsing for dungeon-specific commands — only ATTACK, SKILL_TEST, ITEM_USE, and FLEE are valid inside a dungeon run.

---

## Loot System

Loot tier determines which items can appear in post-combat loot drops (see TASK 22):

| Tier | Gold Range | Item Rarity |
|---|---|---|
| `poor` | 1–15 per room | Common only |
| `standard` | 5–40 per room | Common + Uncommon |
| `rich` | 20–80 per room | Common + Uncommon + Rare |
| `legendary` | 50–200 per room | Full range including Legendary |

Loot is rolled per-room on enemy defeat, not at dungeon end. Boss room loot is rolled at ×2 the normal tier range, plus a guaranteed item roll.

---

## Admin Authoring Workflow

1. Admin opens World Builder → creates location with `map_icon='dungeon'`, sets `visible_before_visit=0` (hidden until hero discovers it), connects to nearby location nodes.
2. Admin opens Ideas Workshop → creates entry with `category='dungeon_seed'`, fills `structured_data` with the JSON format above.
3. Admin links by ensuring `location_key` in the dungeon seed matches the World Builder location key exactly.
4. Dungeon is immediately live. No restart required.

The Smart Entry assistant (TASK 03 / TASK 40) should suggest dungeon seed structured_data when a location with `map_icon='dungeon'` is created — auto-populating title, location_key, and atmosphere from the location record.

---

## Test Checklist

1. **Cooldown enforcement:** Clear a dungeon, attempt immediate re-entry — verify 423 response with correct `cooldown_until`. Wait until cooldown passes (mock time), re-enter — verify success.
2. **Enemy scaling:** Create hero at level 1, enter dungeon — verify enemy stats at ×0.75. Same dungeon with level 7 hero — verify ×1.5 multiplier applied, boss at ×2.0.
3. **Loot tier:** Enter a `loot_tier='legendary'` dungeon — verify legendary items can appear in drops. Enter `loot_tier='poor'` dungeon — verify no rare or legendary items appear.
4. **Run count increment:** Clear the same dungeon three times (advancing clock past cooldown between runs) — verify `run_count=3` in `character_dungeon_runs`.
5. **Session persistence:** Enter dungeon, clear two rooms, disconnect and reconnect — verify `current_room=3` is restored from `session_flags.dungeon_run`, rooms 1–2 show as cleared.
