# TASK 15 — Flee Mechanic

**Status:** 🔶 Partially Built (endpoint exists, mechanic incomplete)
**Blocking:** None — spec complete
**Depends on:** Task 12 (Combat Round Flow — flee is a player action in the round)
**Unlocks:** Nothing directly — part of complete combat system

---

## Overview

Fleeing combat is a tactical option with real cost: it's not guaranteed to succeed, and failure costs the player their turn. Success means escape but also means abandoning any loot. The mechanic is an opposed DEX roll — both player and the fastest enemy roll, highest wins.

---

## Design Context

### Why opposed DEX roll instead of flat DC?
A flat DC (e.g., always DC 12) makes fleeing equally easy/hard regardless of what you're fighting. Running from a wolf should feel harder than running from a skeleton — wolves are fast. An opposed roll captures this naturally: the enemy's speed matters.

### Why use the HIGHEST enemy DEX when multiple enemies?
You're trying to outrun the fastest thing chasing you. Even if 3 of 4 goblins are slow, the fast one is the threat. Using the highest enemy DEX captures the "you're only as safe as your slowest pursuer" reality.

### Why does failing only cost your turn (not escalate)?
Flee should feel tense but not be a death sentence if you fail once. Losing your turn is meaningful — you're now open to enemy attacks — but you can try again next round. This preserves the player's agency to keep trying vs switching to "fight my way out."

### Why does successful fleeing abandon loot?
Loot is tied to the combat location (D16). If you flee, your character leaves that location. The loot stays behind. This creates a meaningful choice: push through the fight for the reward, or cut your losses and run. Loot can potentially be recovered if you return to the same location later (Task 18).

---

## Current State (Code)

- `POST /campaigns/{id}/combat/flee` endpoint exists in `combat.py`
- Current implementation: unclear if it resolves a real mechanic or just ends combat
- No opposed DEX roll logic exists
- No loot abandonment logic tied to flee

---

## Full Specification

### Flee Roll Resolution

When player selects [Flee]:

1. Load player's DEX modifier from character sheet
2. Load all active enemies' `dex_modifier` values from `active_combat.combatants`
3. Find `highest_enemy_dex_mod = max(enemy.dex_modifier for enemy in active enemies)`
4. Roll for player: `player_roll = d20() + player_dex_modifier`
5. Roll for enemy: `enemy_roll = d20() + highest_enemy_dex_mod`
6. Player total > Enemy total → **SUCCESS**
7. Player total ≤ Enemy total → **FAIL** (tie goes to enemy — harder to flee)

### On SUCCESS

- Combat state set to `ended` (status = "fled")
- Player location changes to "leaving combat area" — system moves player to the connected parent macro location (e.g., from dungeon room → dungeon corridor → dungeon entrance)
- Loot for this combat marked as `abandoned` — still accessible if player returns before leaving the macro location
- XP NOT granted for fled combat (no completion reward)
- GM narrates escape (Task 13 generates this)
- Return to narrative gameplay

### On FAIL

- Player loses their current turn — advance to next actor in initiative
- Enemy/enemies act in their initiative slots (auto-fire, Task 12)
- At the start of player's next turn, [Flee] button is available again
- Player CAN attempt flee every round until success or death
- GM narrates the failed escape attempt

### Loot After Flee

- `active_combat.loot_location_id` stored at combat start
- On flee success: loot table entries stay in DB with `status = "abandoned"`
- If player returns to the same macro location before long rest: loot can still be claimed
- If player long rests elsewhere: loot expires (Task 18 handles this detail)

### Special Case: Multiple Enemies

The chase represents all enemies pursuing — only the fastest one matters for the roll. But narratively, there may be multiple enemies between the player and the exit. The GM narration should reflect this ("Two goblins block the doorway, but you shoulder past before the third can grab you").

---

## Flee Roll Formula (Full)

```
Player total = d20 + DEX_modifier
Enemy total  = d20 + max(enemy.dex_modifier for active enemies)

DEX modifier = (DEX_value - 10) // 2

Examples:
  Player DEX 14 (mod +2): rolls 11 → total 13
  Enemy wolf DEX modifier +2: rolls 9 → total 11
  13 > 11 → ESCAPE

  Player DEX 10 (mod 0): rolls 8 → total 8
  Enemy wolf DEX modifier +2: rolls 14 → total 16
  8 < 16 → FAIL, player loses turn
```

---

## Edge Cases

- **Player is at 0 HP when they attempt flee:** Cannot flee at 0 HP. Must roll death save first. If they survive with 1 HP, they can flee next round.
- **All enemies have DEX modifier 0:** Still an opposed roll — pure chance. DC 10 equivalent.
- **Enemy has negative DEX modifier (e.g., troll: -2):** Player has natural advantage against slow enemies. DEX 10 player still has 50%+ chance.
- **Player succeeds flee but there's nowhere to go:** In a completely enclosed location (e.g., sealed chamber), flee should be blocked with a narrative reason. System checks if current location has an exit. If no exit → flee option is disabled/grayed out.
- **Flee on the first round before anyone acts:** Valid — player can panic and run immediately. Goblin may not have even attacked yet.

---

## API Changes

### `POST /campaigns/{id}/combat/flee`

**Request:** `{}` (no body — player has no roll to submit, both rolls are server-side)

**Response:**
```json
{
  "outcome": "success",
  "player_roll": 14,
  "player_total": 16,
  "enemy_roll": 9,
  "enemy_total": 11,
  "narrative": "Ty przekopujesz się przez tłum goblinów i znikasz w ciemnym korytarzu.",
  "new_location": {"key": "dungeon_corridor", "label": "Mroczny Korytarz"}
}
```

OR on failure:
```json
{
  "outcome": "fail",
  "player_roll": 6,
  "player_total": 8,
  "enemy_roll": 14,
  "enemy_total": 16,
  "narrative": "Goblin chwyta cię za ramię — ucieczka się nie udała.",
  "turn_lost": true
}
```

---

## Test Plan

1. Attempt flee with player DEX 14 vs slow enemy (DEX mod -1) → verify ~60% success rate over 10 tests
2. Attempt flee with player DEX 10 vs wolf (DEX mod +2) → verify ~35% success rate over 10 tests
3. Fail flee → verify player loses turn, enemies act, flee available again next round
4. Succeed flee → verify combat ends, location changes, loot marked abandoned
5. Flee in enclosed room with no exit → verify flee button disabled / blocked with message
6. Attempt flee at 0 HP → verify blocked, death save required first

---

## Related Tasks
- Task 12 (Combat Round Flow) — flee is a player action in the round flow
- Task 13 (Combat Narrative) — narrates both success and failure flee outcomes
- Task 18 (Loot System) — abandoned loot handling after successful flee
- Task 09 (Location System) — location change after successful flee
