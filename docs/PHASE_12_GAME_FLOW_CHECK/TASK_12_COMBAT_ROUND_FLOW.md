# TASK 12 — Combat Round Flow (Enemy Auto-Turn)

**Status:** 🔶 Partially Built
**Blocking:** N6 — confirm backend auto-fires full round vs frontend pings per enemy
**Depends on:** Task 11 (clean combat entry)
**Unlocks:** Task 13 (Narrative), Task 14 (Death Saves), Task 15 (Flee)

---

## Overview

Combat currently requires the frontend to manually call `POST /combat/enemy-turn` after each player action. This creates a soft-lock risk and fragile coordination between frontend and backend. Decision D22 specifies a clean, fully automatic flow: once a player takes their action, the backend processes ALL remaining turns in the initiative order (all enemies acting in sequence) and returns the full round result in one response. The frontend receives a structured log of what happened and animates it.

---

## Design Context

### Why backend-driven full-round resolution?
The current model requires the frontend to know "is it an enemy's turn now? Okay, call /enemy-turn. Is it another enemy's turn? Call again." This is polling logic that can fail if:
- The frontend is slow or disconnected mid-round
- The player navigates away and back
- A round has 3 enemies — the frontend must make 3 sequential calls

Backend-driven resolution means: player takes action → one POST → backend returns complete round result (all enemy actions, all damage, all narrative triggers) → frontend displays the log in order. Simpler, more reliable, impossible to soft-lock.

### Why does the player still click "Roll" for their attack?
The player's attack roll is the only interactive element — it's the tactile moment of agency in combat. Everything else (enemy rolls, damage calculation, death checks) is automatic. Keeping the player's roll interactive preserves the TTRPG feel of "I rolled a 17!" without slowing down the rest of the round.

---

## Decision Required — N6

> **Backend resolves full round in one call, or frontend pings per enemy?**
> Recommendation: **backend resolves full round**

The implication: `POST /campaigns/{id}/combat/resolve-attack` (player's action) returns:
```json
{
  "player_action": {...},
  "enemy_actions": [
    {"enemy_key": "goblin_1", "action": "attack", "roll": 14, "hit": true, "damage": 5, "narrative": "..."},
    {"enemy_key": "goblin_2", "action": "attack", "roll": 8, "hit": false, "damage": 0, "narrative": "..."}
  ],
  "round_end_state": {
    "player_hp": 8,
    "enemies": [{"key": "goblin_1", "hp": 3}, {"key": "goblin_2", "hp": 0}],
    "combat_status": "active",
    "next_actor": "player"
  }
}
```

Frontend animates this log sequentially — showing each action with a short delay between them.

---

## Full Specification

### Combat State Machine

```
[Combat initiated]
  → Initiative rolled for all (player + all enemies), order locked
  → Store in active_combat.combatants JSON

[Each Round]
  → Iterate through initiative order
  
  IF current actor is ENEMY:
    → Backend auto-resolves: ATK roll, hit check vs player AC, damage
    → GM narration generated (Task 13)
    → If player HP ≤ 0: trigger Death Save (Task 14)
    → Advance to next actor
  
  IF current actor is PLAYER:
    → Frontend presents: [Attack] [Flee] [Use Item]
    → Wait for player action POST
    
    → IF Attack:
        → Frontend sends player's d20 roll (rolled client-side with animation)
        → Backend receives roll, calculates total, resolves vs enemy AC
        → Enemy HP reduced if hit
        → If enemy HP ≤ 0: enemy defeated, check if all enemies defeated
        → If all enemies defeated: → VICTORY
        → Advance to next actor
        → Backend auto-resolves all ENEMY actors until next PLAYER slot
        → Return full action log
    
    → IF Flee:
        → Backend resolves opposed DEX roll (Task 15)
        → Success: combat ends, escape
        → Fail: player loses turn, advance to next actor → enemies act → return log
    
    → IF Use Item:
        → Backend resolves item effect (healing potion, etc.)
        → Return updated HP
        → Advance to next actor → enemies act → return log

[Victory]
  → All enemies HP ≤ 0
  → GM generates victory narration
  → Loot popup triggered
  → XP granted automatically

[Defeat]
  → Player fails all death saves
  → Campaign end flow triggered
```

### Initiative Roll (Already Implemented — Verify)

```python
# Player: d20 + DEX modifier
# Enemy: d20 + enemy.dex_modifier (from game_config_enemies)
# Ties: player wins (intentional — no change needed)
# Roll ONCE at combat start, order locked for entire combat
```

Already implemented in `combat_service.py`. Verify it's correct and add a test.

### Combat Action Log Format

Each entry in the returned log:

```json
{
  "actor": "goblin_1",
  "actor_type": "enemy",
  "action_type": "attack",
  "roll": 14,
  "total": 15,
  "vs_ac": 13,
  "hit": true,
  "damage_roll": 6,
  "damage_dealt": 6,
  "target_hp_before": 11,
  "target_hp_after": 5,
  "narrative_key": "hit_glancing_blow",
  "narrative_text": "Goblin's blade finds a gap in your armor."
}
```

The `narrative_text` is generated by the LLM per action (Task 13). Frontend plays these entries sequentially with ~1 second delay between each.

### Use Item in Combat

When player selects [Use Item]:
- Opens item picker showing only usable combat items (potions, bandages NOT shown — bandages are out-of-combat only)
- Player selects item
- `POST /campaigns/{id}/combat/use-item` with `{item_id}`
- Backend: deduct from inventory, apply effect (HP restoration), return updated state
- Player loses their combat turn (item use counts as the turn action)
- Round continues with next actor (enemy turns auto-fire)

### Multiple Enemies

Example: 3 goblins, initiative order: Goblin_2 (18) > Player (15) > Goblin_1 (10) > Goblin_3 (7)

Round 1:
1. Goblin_2 acts (auto) — attacks player
2. Player acts — rolls attack on target Goblin_2
3. Goblin_1 acts (auto) — attacks player
4. Goblin_3 acts (auto) — attacks player
→ Round 2 begins

When player submits their attack (step 2), backend:
- Resolves player's attack on Goblin_2
- Immediately auto-resolves Goblin_1 and Goblin_3
- Returns full log for steps 2-4
- Frontend animates all three in sequence

---

## API Changes

### `POST /campaigns/{id}/combat/resolve-attack`

**Change:** After resolving player's attack, backend immediately resolves all subsequent enemy turns until the next player turn.

**Request:** `{player_roll: 17, target_enemy_key: "goblin_1"}`

**Response:** Full action log as described above + updated combat state

### Remove: `POST /campaigns/{id}/combat/enemy-turn`

This endpoint becomes internal-only (called within the backend's round resolution logic, not by frontend). Remove from public API or gate as admin-only debug endpoint.

---

## Edge Cases

- **Player kills last enemy on their turn:** Backend detects all enemies at 0 HP, skips remaining actor slots, triggers victory immediately
- **Player uses healing potion, gets killed before next turn:** HP restored first, then enemy acts; if enemy kills them after the potion, death save still triggers
- **Round has only 1 enemy:** Round resolution is still one player action → one enemy action → return. Same flow, simpler.
- **Enemy tries to attack but player already fled successfully:** Combat state = ended, enemy action skipped
- **Player disconnects mid-round:** On reconnect, GET /combat returns current state. If it's the player's turn, they can still act. If it was in the middle of enemy auto-turns, the backend already completed them and stored the result.

---

## Test Plan

1. Start combat with 1 goblin → player attacks → verify enemy attacks back automatically, no second call needed
2. Start combat with 3 enemies in various initiative positions → verify all 3 act in order each round
3. Player uses healing potion → verify it costs the player's turn, enemies act afterward
4. Kill last enemy on player turn → verify immediate victory, no extra round
5. Player disconnects mid-round → reconnect → verify combat state is consistent
6. Retrieve `GET /campaigns/{id}/combat/turns` → verify all actions from all actors are logged

---

## Related Tasks
- Task 11 (Combat Entry) — clean entry feeds into this
- Task 13 (Combat Narrative) — generates narrative_text for each action log entry
- Task 14 (Death Saves) — triggered when player HP ≤ 0 during enemy auto-turn
- Task 15 (Flee) — [Flee] button in player combat choices
- Task 16 (Healing System) — [Use Item] in combat uses healing items
