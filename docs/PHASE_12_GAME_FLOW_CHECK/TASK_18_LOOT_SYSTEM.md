# TASK 18 — Loot System (Location-Tied)

**Status:** 🔶 Partially Built
**Blocking:** None — spec complete
**Depends on:** Task 09 (Location System — needs current_location_id tracking), Task 11 (Combat Entry — combat_location_id stored at start)
**Unlocks:** Task 20 (Inventory & Shop — items from loot feed inventory)

---

## Overview

After winning combat, the player can claim loot from defeated enemies. Loot is tied to the location where the fight happened. If the player takes some items and leaves, they can return later to claim the rest — but only if they haven't moved to a different macro-location or taken a long rest. This creates a meaningful decision: take everything now (risky if more fights ahead) or come back for the rest.

---

## Design Context

### Why location-tied loot?
If loot floats with the player regardless of where they are, it removes spatial realism. In TTRPG terms, you leave the chest behind if you run. The system enforcing this (not the LLM) prevents a player from claiming loot they "narrative-said" they picked up while actually fleeing.

### Why allow partial loot claiming?
Forcing all-or-nothing loot decisions is frustrating. Players should be able to grab the most important items and leave the rest — a choice they make based on their carrying capacity, urgency, or risk tolerance. The "return to claim remaining loot" mechanic rewards players who clear an area properly rather than rushing.

### Why expire loot on long rest or macro-location change?
In narrative terms: the goblin cave's dead inhabitants get scavenged by other creatures, or local scavengers take the bodies. The world doesn't pause while you rest. Loot expiry is the price of not acting on your victory promptly.

---

## Current State (Code)

- `POST /campaigns/{id}/combat/loot/claim` endpoint exists
- Loot granted from enemy's `loot_table` JSON field
- No `combat_location_id` stored when combat starts
- No `loot_status` tracking (claimed, partial, abandoned, expired)
- No check of current location vs combat location before allowing claim

---

## Full Specification

### Loot Record Schema

**New table or extend `active_combat`:**

```sql
CREATE TABLE combat_loot (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    character_id INTEGER NOT NULL,
    combat_location_id INTEGER REFERENCES game_locations(id),
    combat_location_key TEXT,
    loot_items TEXT NOT NULL DEFAULT '[]',  -- JSON array of item keys with quantities
    status TEXT DEFAULT 'available' CHECK(status IN ('available', 'partial', 'claimed', 'abandoned', 'expired')),
    created_at TEXT DEFAULT (datetime('now')),
    expires_after_long_rest INTEGER DEFAULT 1,
    long_rest_count_at_creation INTEGER DEFAULT 0
)
```

### Combat Start — Store Location

When `[COMBAT_START]` tag is processed (Task 11):
```python
# Store the location where combat is starting
current_location = get_current_location(campaign_id)
active_combat.combat_location_id = current_location.id
active_combat.combat_location_key = current_location.key
```

### Victory — Loot Generation

When all enemies are defeated:
1. Collect loot tables from all defeated enemies
2. Merge into a single loot pool (combine same items)
3. Create `combat_loot` record with `status = "available"`
4. Return loot list to frontend — show Loot Popup

### Loot Popup (Frontend)

- Modal appears after combat victory narration
- Lists all available loot items with checkboxes
- Player selects which items to take
- "Claim Selected" button
- "Leave All" button (close without taking anything)
- If items left behind: "You leave X items behind." with option to note "You can return here to collect them."

### Claim Flow

**`POST /campaigns/{id}/combat/loot/claim`**

Request: `{item_keys: ["sword_rusty", "gold_coins"], loot_record_id: 42}`

Backend:
1. Load `combat_loot` record
2. Verify status is "available" or "partial"
3. Verify player is STILL in the same location as `combat_location_id`
   - `current_location_id == combat_loot.combat_location_id` → allow
   - Otherwise → return error "You are no longer at the combat site"
4. Add selected items to `character_inventory`
5. Remove claimed items from `loot_items` JSON
6. If all items claimed: `status = "claimed"`
7. If some items remain: `status = "partial"`

### Return to Claim Remaining Loot

- Player returns to same location, still has `partial` loot record
- Loot availability check: has player taken a long rest since combat? Has location changed to different macro?
- If available: show "Unclaimed loot from earlier combat" button/indicator
- Player can claim remaining items via same endpoint

### Loot Expiry Rules

| Event | Effect on unclaimed/partial loot |
|-------|----------------------------------|
| Player moves to DIFFERENT macro location | Loot immediately marked `expired` |
| Player takes long rest | Loot immediately marked `expired` |
| Player returns to same sub-location | Loot still `available` (can claim) |
| Player moves within same macro | Loot still `available` |
| Player flees combat | Loot marked `abandoned` (can still be recovered if returned before long rest) |

```python
def check_loot_expiry(loot_record, current_location, long_rest_taken: bool):
    if long_rest_taken:
        return "expired"
    
    # Check if player is in same macro location
    loot_macro = get_macro_location(loot_record.combat_location_id)
    current_macro = get_macro_location(current_location.id)
    
    if loot_macro != current_macro:
        return "expired"
    
    return "available"
```

### Loot Table Structure (Enemy)

In `game_config_enemies.loot_table` JSON:

```json
{
  "guaranteed": [
    {"item_key": "gold_coins", "quantity_min": 2, "quantity_max": 8}
  ],
  "random": [
    {"item_key": "sword_rusty", "chance": 0.3},
    {"item_key": "healing_potion", "chance": 0.1},
    {"item_key": "leather_armor", "chance": 0.15}
  ]
}
```

On combat victory: resolve guaranteed drops + roll each random drop. Combine all enemies' tables.

---

## Edge Cases

- **Player kills enemy in narrative (outside formal combat):** If the GM narrates a player killing an NPC without triggering `[COMBAT_START]`, no formal loot record exists. GM can grant narrative items via `POST /characters/{id}/narrative-item` (already exists).
- **Combat loot has 0 items (enemy had nothing):** Skip loot popup entirely — "The enemy had nothing worth taking."
- **Player has full inventory:** Still show loot popup — player can choose what to drop/swap (Task 20).
- **Multiple combats in same location:** Each combat creates a separate loot record. Both are claimable until they expire.
- **Loot record orphaned if player is teleported by GM:** Background job should expire loot records older than 24 hours (session cleanup).

---

## Test Plan

1. Win combat → verify loot popup shows with enemy's item drops
2. Claim only 1 of 3 items → verify `status = partial`, unclaimed items remain
3. Move to different macro location → verify loot marked `expired`, cannot claim
4. Return to combat location before moving → verify `partial` loot still claimable
5. Take long rest with partial loot → verify loot marked `expired`
6. Flee combat → verify `abandoned` status, check ability to recover loot on return
7. Enemy with empty loot table → verify no popup shown

---

## Related Tasks
- Task 09 (Location System) — `current_location_id` tracked here
- Task 11 (Combat Entry) — `combat_location_id` stored when combat starts
- Task 15 (Flee) — flee marks loot as `abandoned`
- Task 20 (Inventory & Shop) — claimed loot items go to inventory
