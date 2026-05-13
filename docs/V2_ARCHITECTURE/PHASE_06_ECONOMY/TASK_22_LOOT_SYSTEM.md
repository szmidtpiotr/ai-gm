# TASK 22 — Loot System

**Phase:** 06 — Economy  
**Status:** ❌ Not Started  
**Related tasks:** TASK 05 (combat), TASK 20 (inventory), TASK 23 (healing)

---

## Overview

Loot drops after combat victory. Players choose what to take via a popup with checkboxes. They may take some, all, or none. Unclaimed loot persists at its location for a limited time, tied to the player's physical and rest state.

---

## Database

The `combat_loot` table is created in Phase 01 DB schema:

```sql
CREATE TABLE combat_loot (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id INTEGER REFERENCES campaigns(id),
  character_id INTEGER REFERENCES characters(id),
  combat_location_id INTEGER REFERENCES locations(id),
  items_json TEXT NOT NULL,       -- JSON array of loot items
  gold_amount INTEGER DEFAULT 0,  -- auto-granted (not selectable)
  status TEXT DEFAULT 'available',-- available / partial / expired / abandoned
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  expires_reason TEXT,            -- null / 'moved_away' / 'long_rest' / 'flee_long_rest'
  expired_at DATETIME
);
```

`items_json` structure:
```json
[
  { "item_key": "goblin_sword", "name": "Gobliński Miecz", "claimed": false },
  { "item_key": "health_potion", "name": "Eliksir Zdrowia", "claimed": false }
]
```

---

## Loot Generation

On combat `VICTORY` outcome, generate loot from all defeated enemies:

For each defeated enemy:
1. Load enemy definition from `enemy_definitions`
2. Read `loot_table` JSON field (list of possible drops with probability weights)
3. Roll each drop independently against its probability
4. Collect all successful drops into loot pool
5. Sum gold from all enemies' `gold_drop_range` (random within range)

**Gold handling:** Gold from loot is automatically added to `characters.gold` immediately on victory — it is not shown as a checkbox option. The gold amount is displayed as a separate line in the loot popup: *"Znalazłeś 12 sz."*

**Empty loot pool:** If no items drop (all probability rolls fail), show popup with only the gold line (if gold > 0). If gold is also 0, skip the popup entirely — no loot.

---

## Loot Popup

Appears immediately after the victory narrator prose is delivered.

```
┌─────────────────────────────────────┐
│  ŁUPY                               │
│                                     │
│  Znalazłeś 12 sz (dodano)           │
│                                     │
│  ☐  Gobliński Miecz                 │
│  ☐  Eliksir Zdrowia                 │
│  ☐  Zielona Peleryna (Wełniana)     │
│                                     │
│  [Weź Zaznaczone]  [Zostaw Wszystko]│
└─────────────────────────────────────┘
```

- Checkboxes default to unchecked. Player must actively select items.
- Gold line is display-only (already granted, no checkbox).
- [Weź Zaznaczone] button is disabled if no checkboxes selected.
- [Zostaw Wszystko] closes popup without claiming any items.

---

## Claim API

### POST /api/combat/loot/claim

```json
{
  "loot_id": 7,
  "character_id": 42,
  "claimed_item_keys": ["goblin_sword", "health_potion"]
}
```

**Backend steps:**
1. Load `combat_loot` record by `loot_id`
2. Verify `status` is `available` or `partial`
3. Verify character is still in same macro-location (see Expiry section)
4. For each `item_key` in `claimed_item_keys`: add to character inventory, mark `claimed=true` in `items_json`
5. If all items now claimed: set `status='claimed'`
6. If some items still unclaimed: set `status='partial'`
7. Return updated inventory

**Partial claim example:** Player takes the sword but leaves the potion. `status='partial'`. `items_json` shows potion `claimed=false`.

---

## Loot Expiry Rules

Unclaimed or partially-claimed loot expires when the world moves on. Expiry is checked lazily — on each turn, check if any `available` or `partial` loot for this character should be expired.

| Event | Effect | Status |
|-------|--------|--------|
| Player moves to different **macro-location** | All loot at previous location expires | `expired` |
| Player completes a **long rest** | All loot anywhere expires | `expired` |
| Player **flees** combat | Loot created with initial status `abandoned` | `abandoned` |

**Macro-location:** a logical area grouping (e.g., "Karczma" groups several sub-rooms). Loot persists across sub-room moves within the same macro. Defined by `locations.macro_location_id` FK.

**Abandoned loot:** When player flees combat, loot is created with `status='abandoned'`. It remains at the combat location. The player may return to that location before taking a long rest to reclaim it — the loot popup reappears on re-entry with a note: *"Na ziemi leżą porzucone łupy."* On long rest: `abandoned` → `expired`.

**Return to claim rest:** When player enters a location that has `partial` or `abandoned` loot for their character, the loot popup reappears automatically. No narrator call needed — handled as a location-entry check.

---

## Expiry Implementation

```python
def check_loot_expiry(character_id: int, event: str, location_id: int = None):
    """
    event: 'move' | 'long_rest' | 'enter_location'
    Call after every relevant world state update.
    """
    if event == 'move':
        # Expire all loot at locations not in new macro-location group
        expire_loot_outside_macro(character_id, location_id)
    elif event == 'long_rest':
        # Expire all pending loot
        expire_all_loot(character_id)
    elif event == 'enter_location':
        # Check if recoverable loot exists here
        return get_pending_loot(character_id, location_id)
```

---

## Test Cases

1. **Full claim:** Win combat, 3 items drop + 10 gold. Select all 3 checkboxes, click [Weź Zaznaczone]. Verify all 3 items in inventory, gold += 10, `combat_loot.status='claimed'`.

2. **Partial claim:** 3 items drop. Claim 2. Verify `status='partial'`, 2 items in inventory, 1 item still `claimed=false` in `items_json`.

3. **Move away = expired:** After partial claim, move to a different macro-location. Verify `status='expired'`, `expires_reason='moved_away'`. Returning to original location does NOT show loot popup.

4. **Flee = abandoned, recoverable:** Player flees combat. Loot created with `status='abandoned'`. Player does not rest. Player returns to combat location. Loot popup appears with message about abandoned loot. Player claims items. Verify inventory updated.

5. **Long rest expires abandoned loot:** Player flees, creates `abandoned` loot. Player takes long rest before returning. Verify loot `status='expired'`, `expires_reason='flee_long_rest'`. No popup on location re-entry.
