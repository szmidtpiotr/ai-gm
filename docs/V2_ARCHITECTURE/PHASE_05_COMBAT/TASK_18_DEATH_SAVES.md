# TASK 18: Death Save System

## Overview

When a player character reaches 0 HP, they do not die immediately. They enter a Death Save state, rolling **pure d20** against an escalating DC ladder. The ladder makes each subsequent near-death moment within the same combat harder to survive — a character who has been dropped multiple times is genuinely closer to the grave. Three failures mean death.

**Design intent (confirmed):** The escalating DC ladder (10→13→16→19) is itself the "gets harder" mechanic. No CON modifier — death is pure fate. A warrior's resilience shows in their higher max HP and healing options, not in death save rolls. See `10_ALL_OPEN_DECISIONS_RESOLVED.md`.

---

## 1. DC Ladder

| 0-HP Hit in Current Combat | DC |
|---|---|
| 1st | 10 |
| 2nd | 13 |
| 3rd | 16 |
| 4th and beyond | 19 |

`death_save_count` in `active_combat` tracks how many times the player has reached 0 HP in this combat. It increments on each 0-HP hit, determining which DC applies.

The DC ladder applies per combat. Once combat ends — win, lose, or escape — the counter is not carried to the next encounter.

---

## 2. Death Save Roll

```
Roll: d20 (NO modifier — pure fate)
DC: from ladder above

Nat 20: automatic success regardless of DC
Nat 1: counts as 2 failures (gut-punch of bad luck)
```

### Success

Player survives with 1 HP. They regain consciousness and can act on their next turn.

- `death_save_failures` not incremented (or incremented then checked: failures < 3)
- Player HP set to 1
- `active_combat.status` returns to `PLAYER_TURN`
- The Narrator receives: `"death_save": {"outcome": "survived", "roll": X, "total": Y, "dc": Z}`

### Failure

One failure recorded.

- `death_save_failures` incremented by 1 (or 2 on Nat 1)
- Player remains at 0 HP
- All enemies with remaining turns in this round still act (player is down but not dead)
- Player's turn is skipped next round (unconscious at 0 HP)
- On the player's next "turn", if they are at 0 HP, trigger another death save if another damage event occurred, or simply remain unconscious until healed or until next damage event

**Nat 1 special case:** 2 failures at once. A player who has already suffered 2 failures and rolls Nat 1 goes from 2 failures to 4 — instant death, even though the ladder only requires 3.

---

## 3. Death (3+ Failures)

When `death_save_failures >= 3`:

- `active_combat.status` set to `DEFEAT`
- Character status set to `DEAD` in the characters table (or `INCAPACITATED` — GM preference)
- Session marked as ended
- No loot awarded
- Narrator receives: `"death_save": {"outcome": "death", "total_failures": 3}`

The Narrator describes the character's final moments. Dark, but not gratuitous. WFRP-appropriate: death is ignoble, sudden, and real.

### Character Recovery (Out of Scope for This Task)

Post-death recovery options (resurrection, character replacement) are handled by a separate system. This task only covers the death state transition.

---

## 4. Death Save State Storage

`death_save_state` is stored as a JSON field inside `active_combat`:

```json
{
  "death_save_count": 2,
  "death_save_failures": 1,
  "death_save_in_progress": false
}
```

| Field | Type | Description |
|---|---|---|
| `death_save_count` | INT | Times player has reached 0 HP in this combat; determines DC |
| `death_save_failures` | INT | Accumulated failures (3 = death) |
| `death_save_in_progress` | BOOL | True when player is at 0 HP awaiting a roll |

---

## 5. Reset Conditions

### What Resets the Counter

- Combat ends (victory, defeat, or successful flee)
- Long rest

### What Does NOT Reset the Counter

- Healing mid-combat (potions, spells, ally aid). If a player is healed from 0 HP to 5 HP, their `death_save_failures` counter remains. Healing a wound does not un-nearly-die. If they drop to 0 HP again later in the same combat, `death_save_count` increments and a higher DC applies.

**Rationale (WFRP spirit):** Near-death trauma accumulates. A character who has been dropped twice in a fight and gets back up is structurally fragile. The game should communicate this tension.

---

## 6. Special Case: Mutual Kill (Victory Takes Priority)

If the player's action kills the last surviving enemy in the same round that the player would drop to 0 HP:

> **The player survives at 1 HP. No death save is required.**

This means:

- Player attacks goblin. Goblin would die.
- Before player's attack resolves, enemy's earlier initiative attack would have brought player to 0 HP.
- Since the goblin dies in this round and is the last enemy, the victory condition is checked first.
- Player survives at 1 HP. Combat status: VICTORY.

**Implementation:** In round resolution, after all actions are collected (but before applying HP changes), check if last enemy dies and player would reach 0. If so, set player HP to 1 and mark VICTORY without triggering death save.

```python
def check_mutual_kill(player_action_result, enemy_actions_results, current_hp, combat_state):
    last_enemy_dies = all(e["hp_after"] <= 0 for e in enemy_actions_results
                         if e["was_alive_at_start"])
    player_would_die = current_hp - total_enemy_damage <= 0

    if last_enemy_dies and player_would_die:
        return "mutual_kill_player_survives"
    return None
```

---

## 7. Mid-Combat Healing from Exactly 0 HP

When a player is at 0 HP and is healed (e.g. uses a potion, which requires a previous successful death save to regain their turn):

- HP is set to the healing amount
- Player can act normally on their next turn
- `death_save_failures` is **not** cleared (see Section 5)
- `death_save_in_progress` is set to `false`
- `death_save_count` is **not** decremented (they already hit 0)

---

## 8. Frontend: Death Save Modal

When the player reaches 0 HP, the game freezes normal combat UI and renders the Death Save modal.

```
┌──────────────────────────────────────────────┐
│         *** CLINGING TO LIFE ***             │
│                                              │
│  You crumple to the ground, the world        │
│  going grey at the edges.                    │
│                                              │
│  Death Save — DC 10                          │
│  (2nd time down this fight: DC would be 13) │
│                                              │
│  d20 + CON modifier (+2)                     │
│  Failures: ●○○  (1 of 3)                     │
│                                              │
│  [ Roll to Survive ]                         │
└──────────────────────────────────────────────┘
```

Modal elements:

| Element | Description |
|---|---|
| Flavor text | Dark atmospheric text — changes per roll attempt |
| DC | The current death save DC (shown explicitly) |
| CON modifier | Player's CON modifier, shown as reminder |
| Failure tracker | Visual ●○○ indicator, up to 3 slots |
| Roll button | Triggers the d20 roll animation |

On result:
- Survive: modal closes, player HP shows 1, brief narrative from Narrator
- Fail (not death): modal closes, failure counter updates, combat continues with player unconscious
- Death: modal transitions to death screen, session ends

---

## 9. Code Changes

### Replace Fixed DC in `solo_death_service.py`

Current implementation (example — replace this pattern):

```python
# OLD — fixed DC 10
DEATH_SAVE_DC = 10
roll = roll_d20() + character.con_modifier
if roll >= DEATH_SAVE_DC:
    ...
```

New implementation:

```python
# NEW — escalating ladder
DEATH_SAVE_DC_LADDER = {1: 10, 2: 13, 3: 16}
DEATH_SAVE_DC_MAX = 19

def get_death_save_dc(death_save_count: int) -> int:
    return DEATH_SAVE_DC_LADDER.get(death_save_count, DEATH_SAVE_DC_MAX)

def resolve_death_save(character, active_combat: dict) -> DeathSaveResult:
    active_combat["death_save_count"] += 1
    dc = get_death_save_dc(active_combat["death_save_count"])

    raw_roll = roll_d20()
    total = raw_roll + character.con_modifier

    # Nat 20 auto-success
    if raw_roll == 20:
        return DeathSaveResult(outcome="survived", roll=raw_roll, total=total, dc=dc)

    # Nat 1 = 2 failures
    failures_to_add = 2 if raw_roll == 1 else 1

    if total >= dc:
        # Success
        return DeathSaveResult(outcome="survived", roll=raw_roll, total=total, dc=dc)
    else:
        active_combat["death_save_failures"] += failures_to_add
        if active_combat["death_save_failures"] >= 3:
            return DeathSaveResult(outcome="death", roll=raw_roll, total=total, dc=dc,
                                   total_failures=active_combat["death_save_failures"])
        return DeathSaveResult(outcome="failed", roll=raw_roll, total=total, dc=dc,
                               failures=active_combat["death_save_failures"])
```

### active_combat Table

`death_save_state` is embedded in the existing `active_combat` JSON blob — no new column needed. The JSON schema documented in Section 4 should be validated on read to ensure backwards compatibility.

---

## 10. Implementation Notes

### Files to Modify

| File | Change |
|---|---|
| `backend/app/services/solo_death_service.py` | Replace fixed DC with escalating ladder; add mutual-kill check |
| `backend/app/services/combat_service.py` | Track `death_save_count` in active_combat JSON; trigger death save correctly |
| `frontend/js/combat_death.js` | Death Save modal with DC display, failure tracker |
| `frontend/js/combat_ui.js` | Hide action buttons when `death_save_in_progress=true` |

### Testing

```bash
docker exec ai-gm-dev-backend-1 pytest backend/tests/test_death_saves.py -v
```

Key test cases:

| Test | Scenario | Expected |
|---|---|---|
| `test_dc_ladder_first_death` | First 0-HP hit | DC = 10 |
| `test_dc_ladder_second_death` | Second 0-HP hit same combat | DC = 13 |
| `test_dc_ladder_fourth_death` | 4th+ 0-HP hit | DC = 19 (capped) |
| `test_nat20_auto_success` | Roll = 20, DC = 19 | survived |
| `test_nat1_double_failure` | Roll = 1 | +2 failures |
| `test_nat1_on_2_failures` | 2 failures, roll = 1 | death (2+2=4>=3) |
| `test_mutual_kill` | Player kills last enemy same round | survive at 1 HP, no death save |
| `test_heal_no_reset_failures` | Healed from 0 HP | death_save_failures unchanged |
| `test_counter_resets_after_combat` | New combat after previous | death_save_count = 0 |
| `test_3_failures_death` | 3 sequential failures | character death triggered |
