# TASK 42 — Persistent Hero System

**Phase:** 02 — Character
**Status:** ❌ Not Started
**Depends on:** TASK 06 (Character Creation Wizard)

---

## Overview

**Heroes are the primary entity. Campaigns and adventures are assigned TO heroes — not the other way around.**

This inverts V1, where campaigns were primary and characters were attached to campaigns. In V2:
- Player selects a hero first
- Hero can have one active adventure at a time (campaign, dungeon run, or side quest)
- A hero without an active adventure is "at rest" — can visit world map, spend XP, shop
- Player can own multiple heroes simultaneously
- A hero record persists across all adventures, accumulating XP, inventory, gold, and world knowledge

Each campaign is a chapter in the hero's life, not a separate playthrough.

---

## Data Model Changes

### Characters Table — New Fields

```sql
ALTER TABLE characters ADD COLUMN hero_status TEXT DEFAULT 'active';
-- Values: 'active' | 'fallen' | 'retired'

ALTER TABLE characters ADD COLUMN visited_location_keys TEXT DEFAULT '[]';
-- JSON array of location key strings. Persists across all campaigns.
-- Example: '["graustein", "thornwood_forest", "goblin_warren"]'
```

### New Table — character_campaign_history

```sql
CREATE TABLE character_campaign_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id),
    outcome         TEXT NOT NULL,
    -- 'victory' | 'death' | 'abandoned'
    completed_at    TEXT,
    -- ISO 8601 timestamp, NULL while campaign is active
    chapter_summary TEXT DEFAULT '',
    -- LLM-generated 2-paragraph Polish narrative summary, populated on campaign end
    xp_earned       INTEGER DEFAULT 0,
    -- XP accumulated during this specific campaign
    gold_at_close   INTEGER DEFAULT 0,
    -- Gold total at time campaign ended
    level_at_close  INTEGER DEFAULT 1
    -- Hero level when campaign ended
);
```

---

## What Persists Between Campaigns

The following carry forward from one campaign to the next without modification:

| Data | Notes |
|---|---|
| Stats (STR, DEX, CON, INT, WIS, CHA, LCK) | As earned |
| Skill ranks | As earned |
| Spells known | As earned |
| Inventory | All items, equipped state preserved |
| Gold | Full balance |
| XP total | Accumulated across all campaigns |
| Bonds and weaknesses | GM may propose evolutions (see Between Campaigns) |
| `visited_location_keys` | Hero remembers every location ever visited |
| `sheet_json.gm_only.secret_predisposition` | Permanent — set at creation, never changed |
| Campaign history records | Full chronicle, read-only |

## What Resets Between Campaigns

The following are restored or cleared when a campaign ends and before the next begins:

| Data | Reset Value |
|---|---|
| `current_hp` | Restored to `max_hp` |
| `current_mana` | Restored to `max_mana` (Scholar only) |
| Active conditions | Cleared entirely |
| Death save counter | Reset to 0 |
| Campaign-specific session state | Cleared (session_flags, active plan, current_location) |
| In-combat flags | Cleared |

HP/Mana restoration and condition clearing happen automatically when `POST /api/characters/{id}/rest` is called.

---

## Between Campaigns — Rest State

When a campaign ends (any outcome), the hero enters rest state. The player is not dropped back to a menu — rest state is interactive.

In rest state the player can:

1. **Spend pending XP** on stats, skills, and spells (see TASK_25_XP_PROGRESSION_V2).
2. **Visit accessible world map locations** — travel to towns, visit shops, speak with NPCs. Normal map traversal applies. Travel during rest does not require a campaign to be active.
3. **Review the Hero Journal** — read campaign history, see the running chronicle (see TASK 45).
4. **Choose next adventure** — see Adventure Selection below.

Rest state persists until the player starts a new adventure. There is no time limit.

---

## Adventure Selection Screen

Shown when the player clicks "Rozpocznij przygodę" in rest state (or immediately after campaign end if the player chooses not to rest).

Four options:

| Option | Label | Description |
|---|---|---|
| New campaign | "Nowa kampania" | LLM generates a full campaign from Ideas Bank, personalised to this hero's history, bonds, and weaknesses |
| Dungeon run | "Wyprawa do lochu" | Pick a dungeon node from world map (see TASK 41) |
| Commission | "Zlecenie" | Short 1-session scenario pulled from Ideas Bank where `category='scene_module'` |
| Free roam | "Eksploruj świat" | No active narrative — hero moves freely on world map, shops, talks, gathers rumours |

### Personalised Campaign Generation

When "Nowa kampania" is selected, the LLM receives:

- Full hero sheet (stats, skills, spells, inventory)
- All `character_campaign_history` records (outcomes, summaries)
- `visited_location_keys` (so the new campaign can reference known places)
- Current bonds and weaknesses
- `secret_predisposition` (GM-only — shapes the suggestion but is not surfaced to player)

The LLM returns a campaign seed: title, premise, inciting event, recommended starting location. This is used to initialise a new campaign record (same flow as TASK 07), not presented to the player as a prompt.

---

## Hero Death

Reaching 0 HP and failing death saves does not automatically destroy the hero. The player chooses:

### Option A — Restart the Campaign

- Hero survives in narrative terms (e.g., woke up days later, rescued, wrong place wrong time).
- Campaign resets: turn counter resets to 1, plan restarts from Act 1.
- `character_campaign_history` record for this campaign is updated: `outcome='abandoned'`, with a note in `chapter_summary` that the campaign restarted.
- Hero stats, XP, and inventory are NOT rolled back — only campaign narrative resets.

### Option B — Accept Death

- `hero_status` set to `'fallen'`.
- `character_campaign_history` record: `outcome='death'`.
- LLM generates a death chapter summary (tone: eulogy, not failure message).
- Player is offered: create a new hero (TASK 06 wizard). New hero starts fresh.
- Fallen hero record is preserved permanently and is accessible in the admin panel.

### Fallen Hero Legacy

Admin can promote a fallen hero to the world's NPC pool. In the admin panel, a "Fallen Heroes" section lists all `hero_status='fallen'` characters. Admin can:

- Create an `npc_definitions` entry from the fallen hero's sheet, transforming them into a historical figure, ghost, ancestor, or legend.
- The NPC entry pre-populates `personality_prompt` from the fallen hero's appearance + personality fields.
- A `[Promote to NPC]` button handles the conversion; the fallen hero's record is not modified.

---

## API Changes

### GET /api/characters/{id}/history

Returns the full `character_campaign_history` for this character, ordered by `completed_at` ascending (most recent last). Includes active campaign if present.

Response:
```json
[
  {
    "campaign_id": 1,
    "campaign_title": "Zdrada pod Graustein",
    "outcome": "victory",
    "completed_at": "2026-03-14T18:22:00",
    "chapter_summary": "Aldric przybył do Graustein jako najemnik...",
    "xp_earned": 340,
    "gold_at_close": 85,
    "level_at_close": 3
  }
]
```

### POST /api/characters/{id}/rest

Triggers the between-campaign rest state transition:

1. Restores `current_hp` to `max_hp`, `current_mana` to `max_mana`.
2. Clears all active conditions from `character_conditions`.
3. Resets death save counter.
4. Sets `hero_status='active'` if it was anything else (e.g., recovering from a near-death).
5. Returns the updated character sheet.

Request body: `{}` (no parameters needed).

### GET /api/heroes

Returns all heroes belonging to the current user, including fallen and retired. Used for the hero selection screen.

Response:
```json
[
  {
    "id": 1,
    "name": "Aldric von Kreuz",
    "archetype": "Warrior",
    "level": 5,
    "hero_status": "active",
    "campaigns_completed": 2,
    "total_xp": 780
  },
  {
    "id": 2,
    "name": "Marta Szeptem",
    "archetype": "Scholar",
    "level": 2,
    "hero_status": "fallen",
    "campaigns_completed": 0,
    "total_xp": 120
  }
]
```

---

## Implementation Notes

- `visited_location_keys` is stored as a JSON text column and should be parsed/serialised as a Python list. Helper: `character.get_visited_keys() -> list[str]` and `character.add_visited_key(key: str)`.
- When WSM confirms movement to a new location, it must call `add_visited_key` for that location — this is the only write path for `visited_location_keys`.
- The rest state is a UI state, not a DB state. No `character.in_rest` flag is needed. Rest state is inferred: character exists, no active campaign session.
- Fallen heroes must be excluded from normal hero selection but included in GET /api/heroes with a clear visual indicator in the UI.

---

## Test Checklist

1. **Persistence:** Complete a campaign, start a new one — verify stats, inventory, gold, XP, and visited locations all carry forward unchanged.
2. **Reset on new campaign:** After `POST /api/characters/{id}/rest`, verify `current_hp = max_hp`, conditions cleared, death counter = 0.
3. **Fallen hero flow:** Simulate death → accept death → verify `hero_status='fallen'`, campaign history record written with `outcome='death'`, hero excluded from active hero selection.
4. **Restart campaign after death:** Simulate death → restart → verify hero stats/XP/inventory unchanged, campaign history records `outcome='abandoned'`, new plan generated.
5. **Admin legacy promotion:** Verify `[Promote to NPC]` creates valid `npc_definitions` entry from fallen hero data, fallen hero record unmodified.
