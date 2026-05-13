# TASK 19: Flee Mechanic

## Overview

A player can attempt to flee combat on their turn. Fleeing uses an opposed DEX roll — player vs. the fastest enemy pursuing them. Success escapes combat; failure wastes the player's turn while enemies still get to attack. Loot from the encounter is abandoned. XP is not awarded.

**Design intent:** Fleeing should be a genuine tactical option, not a guaranteed escape or a reliable fallback. In a WFRP-spirit game, running from monsters is smart. Running from fast monsters is desperate. Running when cornered is impossible.

---

## 1. Flee Roll

### Player Roll

```
Player DEX total = d20 + DEX modifier
```

### Enemy Roll (Pursuer)

```
Enemy total = d20 + highest DEX modifier among living enemies
```

The fastest enemy pursues. If there are three enemies with DEX modifiers +1, +2, and -1, the d20 roll uses +2.

### Result

| Outcome | Condition |
|---|---|
| Player total > Enemy total | Success — player escapes |
| Player total <= Enemy total | Failure — turn wasted, enemies still act |
| Tie | Failure (player must exceed, not merely match, to escape) |

---

## 2. Success: Fleeing the Combat

When the flee roll succeeds:

### Location Change

- Player moves to the **connected parent location** of the current location
- Location is determined by the location graph: `current_location.parent_location_id`
- If a location has no parent (is a root/overworld location), flee still succeeds but player remains in place (they flee "into the open", combat ends)

### Combat State

- `active_combat.status` set to `FLED`
- `active_combat` record not deleted, marked as ended with outcome `"fled"`
- Loot records set to `abandoned = true` (see Section 5)
- XP is **not** awarded

### Turn Order After Successful Flee

Enemies do **not** get a free attack when the player successfully flees. The flee action is the player's action for that turn and if it succeeds, the round ends. Enemies do not fire.

### Narrator Context

```python
{
  "flee_result": "success",
  "player_dex_roll": 14,
  "player_dex_total": 16,
  "pursuer_name": "Goblin Scout",
  "pursuer_dex_total": 11,
  "location_escaped_to": "Forest Path"
}
```

The Narrator describes the desperate sprint, the enemy's howl of frustration behind them, the gasped breath as they reach safety.

---

## 3. Failure: Flee Attempt Failed

When the flee roll fails:

### Mechanical Effect

- Player's action for this turn is consumed (turn wasted)
- Combat continues to ENEMY_TURNS phase normally
- All living enemies act in initiative order
- `active_combat.status` returns to `PLAYER_TURN` after enemy turns

### Retry

The player may attempt to flee again on their next turn. There is no penalty for multiple failed flee attempts beyond the lost turns (and the beating received from enemies).

### Narrator Context

```python
{
  "flee_result": "failed",
  "player_dex_roll": 9,
  "player_dex_total": 10,
  "pursuer_name": "Wolf",
  "pursuer_dex_total": 14
}
```

The Narrator describes the player being cut off, grabbed, or simply outpaced.

---

## 4. Cannot-Flee Conditions

### At 0 HP

A player at 0 HP cannot attempt to flee. They must first succeed on a Death Save (which sets them to 1 HP). Once at 1 HP or above, flee is available on their next turn.

**Frontend:** The [Flee] button is disabled and greyed out when player HP = 0. Tooltip: "Cannot flee while unconscious. Survive first."

### No Exit Location

If the current location has `has_exits = false` (an enclosed room — dungeon cell, cave chamber, sealed vault), there is no connected exit to flee to. The [Flee] button is disabled.

**Frontend:** [Flee] button disabled. Tooltip: "No exit. There is nowhere to run."

**Location flag:** `game_config_locations.has_exits` boolean column (or inferred from having no children/parent in the location graph).

### BREAK Condition (Fear System)

A player with the BREAK condition (from TASK_16) is not restricted from fleeing — in fact, they are *forced* to flee. The [Attack] and [Use Item] buttons are disabled for a BREAK character; Flee is their only option and fires automatically on their turn. See TASK_16 for BREAK mechanics.

### FRIGHTENED Condition

A FRIGHTENED player can still flee (FRIGHTENED restricts item use, not fleeing). In fact, the fear system may make the player *want* to flee more.

---

## 5. Loot: Abandoned on Flee

### combat_loot Table

```sql
CREATE TABLE IF NOT EXISTS combat_loot (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    session_id      TEXT NOT NULL,
    character_id    TEXT NOT NULL,
    combat_id       TEXT NOT NULL,
    location_id     TEXT NOT NULL,
    loot_json       TEXT NOT NULL,
        -- JSON array of {item_id, item_name, quantity}
    abandoned       INTEGER NOT NULL DEFAULT 0 CHECK(abandoned IN (0,1)),
    recovered       INTEGER NOT NULL DEFAULT 0 CHECK(recovered IN (0,1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (combat_id) REFERENCES active_combat(id)
);
```

### On Successful Flee

When `flee_result = "success"`:

```python
db.execute("""
    UPDATE combat_loot
    SET abandoned = 1
    WHERE combat_id = ? AND recovered = 0
""", [combat_id])
```

The loot is not lost permanently — it remains at the original location.

### Loot Recovery

If the player returns to the **same macro-location** before taking a long rest:

- A prompt appears: "Discarded loot from your previous encounter is here. [Take loot] [Leave it]"
- Recovery sets `combat_loot.recovered = 1` and adds items to inventory
- "Same macro-location" means same `location_id` or its direct parent (loot does not move)

**Expiry:** Loot that is abandoned is cleared on long rest. After a long rest, assume scavengers or decay have claimed it.

```python
# On long rest trigger:
db.execute("""
    UPDATE combat_loot
    SET abandoned = 1
    WHERE session_id = ? AND recovered = 0
""", [session_id])
# Abandoned loot is then ineligible for recovery
```

---

## 6. Flee Resolution Flow (Backend Pseudocode)

```python
def resolve_flee(character, combat_state: CombatState) -> FleeResult:
    # Pre-condition checks
    if character.hp <= 0:
        return FleeResult(success=False, blocked_reason="hp_zero")

    location = load_location(combat_state.location_id)
    if not location_has_exit(location):
        return FleeResult(success=False, blocked_reason="no_exit")

    if has_condition(character.id, "break", encounter_id=combat_state.combat_id):
        # BREAK auto-flee — still use the roll but BREAK doesn't restrict fleeing
        pass

    # Roll
    player_roll = roll_d20()
    player_total = player_roll + character.dex_modifier

    pursuers = [e for e in combat_state.combatants if e["is_alive"]]
    highest_enemy_dex = max(e["dex_modifier"] for e in pursuers) if pursuers else -5
    enemy_roll = roll_d20()
    enemy_total = enemy_roll + highest_enemy_dex
    pursuer_name = next(
        e["name"] for e in pursuers if e["dex_modifier"] == highest_enemy_dex
    )

    if player_total > enemy_total:
        # Success
        new_location_id = location.parent_location_id or location.id
        mark_loot_abandoned(combat_state.combat_id)
        end_combat(combat_state, outcome="fled")
        move_player_to_location(character.id, new_location_id)
        return FleeResult(
            success=True,
            player_roll=player_roll,
            player_total=player_total,
            pursuer_name=pursuer_name,
            enemy_total=enemy_total,
            new_location_id=new_location_id
        )
    else:
        # Failure — enemies still act this round
        return FleeResult(
            success=False,
            blocked_reason="caught",
            player_roll=player_roll,
            player_total=player_total,
            pursuer_name=pursuer_name,
            enemy_total=enemy_total
        )
```

---

## 7. API Integration

Flee is submitted through the same endpoint as attacks (see TASK_14):

```
POST /api/combat/resolve-attack
{
  "session_id": "...",
  "character_id": "...",
  "action_type": "flee",
  "target_enemy_id": null,
  "item_id": null
}
```

Response includes `flee_result` field:

```json
{
  "round_number": 3,
  "status": "FLED",
  "flee_result": {
    "success": true,
    "player_roll": 14,
    "player_dex_modifier": 2,
    "player_total": 16,
    "pursuer_name": "Goblin Scout",
    "pursuer_dex_modifier": 1,
    "enemy_roll": 10,
    "enemy_total": 11,
    "new_location": "Forest Path",
    "loot_abandoned": true
  },
  "enemy_actions": [],
  "narrative": "..."
}
```

On successful flee, `enemy_actions` is empty (enemies do not fire). On failed flee, `enemy_actions` contains the normal enemy turn results.

---

## 8. Frontend: Flee Button State Management

The [Flee] button state is driven by combat state from the backend:

| Condition | Button State |
|---|---|
| Normal combat, player HP > 0, location has exit | Enabled |
| Player HP = 0 | Disabled, tooltip "Survive first" |
| Location `has_exits = false` | Disabled, tooltip "No exit" |
| Player has BREAK condition | Only this button enabled (all others disabled) |
| Player has PANICKED condition (missing turn) | All buttons disabled |

### Flee Result Display

On successful flee, the combat panel closes and the location panel transitions to the new location. A brief narrative banner appears: "You flee into the night."

On failed flee, a red banner: "Caught! [pursuer_name] cuts off your escape." Then enemy turns play out in the round log.

---

## 9. DEX Modifier With Leg Wound Penalty

If the player has a LEG WOUND condition (from TASK_17) when they attempt to flee, their DEX total receives a -2 penalty:

```python
leg_wound = get_condition(character.id, "leg_wound", session_id)
flee_dex_penalty = -2 if leg_wound else 0
player_total = player_roll + character.dex_modifier + flee_dex_penalty
```

This is the only cross-system interaction for flee mechanics. The Narrator should be told about the leg wound when narrating a flee attempt, whether success or failure.

---

## 10. Implementation Notes

### Files to Create/Modify

| File | Change |
|---|---|
| `backend/app/services/combat_service.py` | `resolve_flee()` function; call from `resolve_attack()` when `action_type="flee"` |
| `backend/app/db/migrations/0014_combat_loot.sql` | `combat_loot` table |
| `backend/app/api/combat.py` | No new endpoint — flee uses existing resolve-attack |
| `frontend/js/combat_ui.js` | [Flee] button state management |
| `frontend/js/combat_state.js` | Handle `status: "FLED"` — close combat panel, move to new location |

### Location Data Requirement

Ensure `game_config_locations` has a `parent_location_id` column and a `has_exits` flag (or derive `has_exits` from whether a parent_location_id exists). If neither exists, add via migration:

```sql
ALTER TABLE game_config_locations ADD COLUMN parent_location_id TEXT;
ALTER TABLE game_config_locations ADD COLUMN has_exits INTEGER NOT NULL DEFAULT 1
    CHECK(has_exits IN (0,1));
```

### Testing

```bash
docker exec ai-gm-dev-backend-1 pytest backend/tests/test_flee_mechanic.py -v
```

Key test cases:

| Test | Scenario | Expected |
|---|---|---|
| `test_flee_success` | Player total 16 > enemy total 11 | status FLED, loot abandoned |
| `test_flee_failure` | Player total 10 <= enemy total 14 | action consumed, enemy turns fire |
| `test_flee_tie_is_failure` | Player total 12 = enemy total 12 | failure (must exceed) |
| `test_cannot_flee_at_zero_hp` | Player HP = 0 | blocked_reason hp_zero |
| `test_cannot_flee_no_exit` | Location has_exits=false | blocked_reason no_exit |
| `test_loot_abandoned_on_flee` | Flee success | combat_loot.abandoned=1 |
| `test_loot_recoverable` | Return same location before long rest | recovery prompt available |
| `test_loot_lost_on_long_rest` | Long rest after abandoned loot | recovery no longer available |
| `test_leg_wound_penalty` | Flee attempt with LEG WOUND | player_total -= 2 |
| `test_fastest_enemy_pursues` | 3 enemies, DEX mods +1/+2/-1 | pursuer uses +2 |
| `test_no_xp_on_flee` | Flee success | xp_awarded = 0 |
| `test_break_condition_auto_flee` | Player has BREAK | flee fires automatically, attack disabled |
