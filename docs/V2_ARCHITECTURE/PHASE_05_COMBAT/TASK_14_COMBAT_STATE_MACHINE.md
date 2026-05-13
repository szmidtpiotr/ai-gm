# TASK 14: Combat State Machine

**Status:** ✅ Done — commit `b22299d` (2026-05-13)

## Overview

Combat in AI-GM is a fully server-resolved loop. The backend resolves a complete round — player action, all enemy reactions, condition ticks, loot checks — and returns a structured log. The LLM only narrates the resolved result. There is no real-time back-and-forth between the frontend and backend for individual enemy turns.

**Architecture principle:** _mechanics first, narration second_. The backend resolves all dice, modifiers, conditions, and outcomes before the Narrator ever sees the data.

---

## 1. Combat Entry

### Trigger Sources

Combat begins through one of two paths:

**Path A — Intent Parser (player-initiated)**
The Intent Parser (`app/services/intent_parser.py`) detects the `ATTACK` intent from free-text input (e.g. "I attack the goblin", "charge the bandit", "draw my sword"). When `ATTACK` intent is confirmed, the game engine calls `combat_service.start_combat()`.

**Path B — GM Narrative trigger (enemy-initiated)**
The GM Plan (`app/services/gm_plan_service.py`) can flag an encounter as `auto_aggro=true`. When the player enters a flagged location or crosses a narrative threshold, the backend begins combat without waiting for player intent.

### Entry Conditions Checked Before Combat Starts

- Player is not already in an active combat (`active_combat` record exists for session)
- Player HP > 0
- Target enemies exist in the current location's enemy roster
- Current session is in ACTIVE state

### Combat Record Created

On entry, a row is inserted into `active_combat`:

```json
{
  "session_id": "<uuid>",
  "character_id": "<uuid>",
  "location_id": "<uuid>",
  "combatants": [
    {
      "id": "<enemy_instance_id>",
      "name": "Goblin Scout",
      "hp": 8,
      "max_hp": 8,
      "dex_modifier": 1,
      "initiative": null,
      "conditions": [],
      "behavior_profile_key": "goblin_standard",
      "is_alive": true
    }
  ],
  "turn_order": [],
  "current_turn_index": 0,
  "round_number": 1,
  "death_save_count": 0,
  "combat_loot": [],
  "started_at": "<iso8601>",
  "status": "INITIATIVE"
}
```

---

## 2. Initiative Phase

### Roll

Initiative is rolled **once** at the start of combat and **locked for the entire encounter**. It does not re-roll each round.

```
initiative = d20 + DEX_modifier
```

All combatants roll simultaneously. The player's roll is returned to the frontend for display. Enemy rolls are resolved server-side without player input.

### Tie-Breaking

1. Higher DEX modifier wins
2. If still tied: player wins (player-favorable design choice)
3. If enemy vs enemy tie: lower index in combatants array goes first

### Result

`active_combat.turn_order` is populated as an ordered array of combatant IDs:

```json
"turn_order": ["player", "goblin_001", "goblin_002"]
```

`active_combat.status` transitions from `INITIATIVE` to `PLAYER_TURN`.

---

## 3. State Machine

```
                        ┌──────────────────────────┐
                        │         INACTIVE         │
                        └────────────┬─────────────┘
                                     │ start_combat()
                                     ▼
                        ┌──────────────────────────┐
                        │        INITIATIVE        │
                        │  Roll d20+DEX all sides  │
                        │  Lock turn order         │
                        └────────────┬─────────────┘
                                     │ initiative resolved
                                     ▼
              ┌──────────────────────────────────────────┐
              │              PLAYER_TURN                 │
              │  Wait for player action via API          │
              │  Contextual buttons shown on frontend:   │
              │    [Attack]  [Flee]  [Use Item]          │
              └───────┬────────────┬────────────┬────────┘
                      │            │            │
                 [Attack]       [Flee]     [Use Item]
                      │            │            │
                      ▼            ▼            ▼
              ┌────────────┐ ┌──────────┐ ┌──────────────┐
              │  RESOLVING │ │ FLEEING  │ │  ITEM_USE    │
              │  ROUND     │ └────┬─────┘ └──────┬───────┘
              └─────┬──────┘      │               │
                    │         flee outcome     item outcome
                    │             │               │
                    ▼             ▼               ▼
              ┌────────────────────────────────────────┐
              │              ENEMY_TURNS               │
              │  Backend resolves all enemy actions    │
              │  in initiative order (auto, no input)  │
              └────────────────┬───────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
           All enemies dead?       Player HP drops to 0?
                    │                     │
                    ▼                     ▼
           ┌──────────────┐      ┌────────────────┐
           │   VICTORY    │      │   DEATH_SAVE   │
           │  XP + loot   │      │  DC 10/13/16/  │
           │  granted     │      │  19 ladder     │
           └──────────────┘      └───────┬────────┘
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                         Save passes?         3 failures?
                              │                     │
                              ▼                     ▼
                         PLAYER_TURN          ┌───────────┐
                         (resume)             │   DEATH   │
                                              │ Char dies │
                                              └───────────┘
```

All transitions that do not require player input (ENEMY_TURNS, condition ticks, death checks) are resolved server-side within the same API call that processed the player's action.

---

## 4. Player Turn

### Frontend Display

When `active_combat.status == PLAYER_TURN`, the frontend renders three contextual action buttons alongside the free-text input:

| Button | Intent | Endpoint Called |
|---|---|---|
| [Attack] | ATTACK | POST /api/combat/resolve-attack |
| [Flee] | FLEE | POST /api/combat/resolve-attack (action_type: "flee") |
| [Use Item] | ITEM | POST /api/combat/resolve-attack (action_type: "use_item") |

Free-text input is still active. The Intent Parser classifies text input to the same three categories. The buttons are shortcuts that bypass the parser.

### What the Player Cannot Do During Combat

- Access inventory management (equip/unequip)
- Travel to a new location
- Initiate conversation with an NPC (unless NPC is a combatant with dialogue_on_aggro)
- Long rest or short rest

---

## 5. Full Round Resolution (Backend)

### Single API Call, Complete Round

The key architectural decision: **one POST, one complete round returned**.

When the player submits an action, the backend resolves:

1. Player action (attack, flee, item use)
2. Condition ticks on player (bleeding, winded, frightened rounds counted down)
3. All living enemies take their turns, in initiative order
4. Condition ticks on each enemy after their turn
5. Victory/defeat check
6. Round number incremented

The frontend receives the entire log and renders it sequentially (with optional animation delays).

### API Contract

```
POST /api/combat/resolve-attack
Authorization: Bearer <token>

Request body:
{
  "session_id": "string",
  "character_id": "string",
  "action_type": "attack" | "flee" | "use_item",
  "target_enemy_id": "string | null",
  "item_id": "string | null",
  "free_text": "string | null"
}

Response 200:
{
  "round_number": 2,
  "status": "PLAYER_TURN" | "VICTORY" | "DEFEAT" | "FLED",
  "player_action": {
    "type": "attack",
    "target": "goblin_001",
    "roll": 15,
    "modifier": 2,
    "total": 17,
    "hit": true,
    "damage": 6,
    "critical": false,
    "crit_location": null,
    "effects_applied": []
  },
  "enemy_actions": [
    {
      "enemy_id": "goblin_001",
      "enemy_name": "Goblin Scout",
      "action_type": "attack",
      "roll": 11,
      "total": 12,
      "hit": false,
      "damage": 0,
      "effects_applied": []
    }
  ],
  "condition_ticks": [
    {
      "subject": "player",
      "condition": "winded",
      "rounds_remaining": 1
    }
  ],
  "player_hp_after": 14,
  "enemies_after": [
    {
      "id": "goblin_001",
      "name": "Goblin Scout",
      "hp": 2,
      "max_hp": 8,
      "is_alive": true,
      "conditions": []
    }
  ],
  "death_save": null,
  "loot": null,
  "xp_awarded": null,
  "narrator_context": {
    "round_log": [...],
    "tone": "dark_fantasy",
    "crit_locations": [],
    "fear_events": [],
    "death_save_events": []
  }
}
```

### No Public /enemy-turn Endpoint

There is no `POST /api/combat/enemy-turn` endpoint. Enemy turns are **internal to the combat service** and resolved inside `resolve_attack()` before the response is built. This prevents desync, cheating, and race conditions. The only public combat endpoint is `resolve-attack`.

### Other Combat Endpoints

```
GET  /api/combat/state?session_id=<id>     # Current combat state (for reconnects)
POST /api/combat/end                       # Force-end combat (admin/debug only)
GET  /api/combat/history?session_id=<id>  # Round log for current combat
```

---

## 6. Enemy Turn Execution (Internal)

After the player's action is processed, `combat_service._resolve_enemy_turns()` iterates `active_combat.turn_order`, skipping the player and any dead enemies:

```python
for combatant_id in turn_order:
    if combatant_id == "player":
        continue
    enemy = get_combatant(combatant_id)
    if not enemy["is_alive"]:
        continue
    action = behavior_service.decide_action(enemy, combat_state)
    result = resolve_enemy_action(enemy, action, combat_state)
    round_log.append(result)
    if player_hp_after <= 0:
        trigger_death_save(combat_state)
        break  # no more enemies act once player is at 0 HP
```

Enemy behavior is resolved by `enemy_behavior_service.py`, not the LLM. See TASK_15 for behavior profile details.

---

## 7. Victory Condition

Victory is declared when `len([e for e in combatants if e["is_alive"]]) == 0`.

On victory:
- XP calculated: sum of `xp_value` from all defeated enemies
- `character.xp` incremented
- Level-up check triggered
- Loot rolled from each enemy's `loot_table_key`
- `active_combat` record status set to `COMPLETED`
- `combat_loot` record created (retrievable until long rest)
- Death save counter NOT reset until after narration confirms safe

**Special case — mutual kill**: If the player's action kills the last enemy and the enemy's final attack would have killed the player in the same round, the player survives at 1 HP. Victory takes priority over death.

---

## 8. Narrator Integration

After `resolve_attack()` completes mechanical resolution, the narrator is called once:

```python
narrator_context = build_narrator_context(round_log, combat_state)
narrative_text = llm_service.narrate(narrator_context, tone="dark_fantasy")
```

The narrator receives:
- Full round log (who hit whom, for how much, with what effect)
- Any critical hit locations (for vivid wound description)
- Any fear/terror events triggered
- Any death save outcomes
- Character and enemy names

The narrator does **not** decide outcomes. It only describes what already happened.

---

## 9. Implementation Notes

### Files to Create/Modify

| File | Change |
|---|---|
| `backend/app/services/combat_service.py` | Core state machine and round resolver |
| `backend/app/api/combat.py` | Route: POST /combat/resolve-attack |
| `backend/app/services/enemy_behavior_service.py` | New file — behavior profile resolution |
| `backend/app/db/migrations/0010_combat_tables.sql` | active_combat, combat_loot tables |
| `frontend/js/combat_ui.js` | Button rendering, round log display |
| `frontend/js/combat_state.js` | Client-side state tracking |

### Database Tables Required

- `active_combat` — live combat state JSON blob
- `combat_loot` — per-combat loot records with `abandoned` flag
- `enemy_behavior_profiles` — see TASK_15
- `character_conditions` — player conditions (frightened, winded, etc.)

### Testing

```bash
# Run combat state machine tests
docker exec ai-gm-dev-backend-1 pytest backend/tests/test_combat_state_machine.py -v

# Verify no /enemy-turn endpoint is exposed
docker exec ai-gm-dev-backend-1 python3 -c "
from app.main import app
routes = [r.path for r in app.routes]
assert '/api/combat/enemy-turn' not in routes, 'enemy-turn must not be public'
print('OK: enemy-turn is internal only')
"
```
