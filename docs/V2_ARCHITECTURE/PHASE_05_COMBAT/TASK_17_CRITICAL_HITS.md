# TASK 17: Critical Hits & Hit Location Table

## Overview

A critical hit occurs when an attack roll exceeds the target's Armor Class (AC) by a configurable threshold, or when a natural 20 is rolled. Critical hits deal doubled damage and trigger a d6 hit location roll. Each location applies a mechanical condition to the target — never just a flat damage bonus. The LLM narrates the wound vividly after the location and condition are resolved by the backend.

**Design intent:** Critical hits should feel brutal and consequential in the WFRP spirit. A head hit dazes, a leg hit cripples movement, an arm hit costs weapon effectiveness. Conditions create meaningful tactical state, not just numbers.

**CONDITIONS FULLY SPECIFIED:** All wound conditions (DAZED, WINDED, ARM_WOUND, LEG_WOUND for player; STUNNED, BLEEDING, DISARMED, HOBBLED for enemies) fully specified in `11_CONDITIONS_SYSTEM.md`. Crit threshold confirmed: 5 over AC (or Nat 20). See `10_ALL_OPEN_DECISIONS_RESOLVED.md`.

---

## 1. Critical Hit Threshold

### Default Configuration

```
crit_threshold = 5
```

A critical hit triggers when:
```
attack_roll_total >= target_AC + crit_threshold
```

Example: Player has attack total 18, enemy AC 12 → 18 >= 12+5 → CRIT (threshold met).
Example: Player has attack total 16, enemy AC 12 → 16 >= 17? No → normal hit.
Example: Player has attack total 17, enemy AC 12 → exactly 17 = threshold met → CRIT.

### Natural 20 Override

A roll of natural 20 always crits, regardless of AC difference. Even if the enemy has AC 1 and the player rolls a 20, it is treated as a critical hit.

```python
is_crit = (raw_roll == 20) or (attack_total >= target_ac + crit_threshold)
```

### Admin Configuration

`crit_threshold` is stored in `game_config_settings` with key `"combat_crit_threshold"`. Defaults to 5. Admin Panel → Settings → Combat section allows changing this value.

```sql
INSERT OR IGNORE INTO game_config_settings (key, value, description)
VALUES ('combat_crit_threshold', '5',
        'Attack total must exceed target AC by this amount to trigger a critical hit.');
```

---

## 2. Critical Hit Damage

On a critical hit, damage is doubled before applying any other modifiers.

```python
base_damage = roll_weapon_damage(weapon)  # e.g. 1d6 → rolls 4
crit_damage = base_damage * 2             # → 8
final_damage = crit_damage - target_damage_reduction  # after DR, if any
```

This applies to both natural 20 crits and threshold-exceeded crits.

---

## 3. Hit Location Roll

After confirming a critical hit, the system rolls 1d6 for hit location:

| d6 Result | Location |
|---|---|
| 1 | Head |
| 2 | Torso |
| 3 | Right Arm |
| 4 | Left Arm |
| 5 | Right Leg |
| 6 | Left Leg |

The hit location determines which condition is applied. Arms (3 or 4) share the same condition. Legs (5 or 6) share the same condition.

---

## 4. Hit Location Effects: On the PLAYER (enemy crits player)

When an enemy scores a critical hit against the player:

### Head (1) — DAZED

**Effect:** Player loses their next action. Their turn is skipped automatically.

**Mechanical implementation:**
- Apply `character_conditions` entry: `condition_type = "dazed"`, `expires_at_round = current_round + 1`
- On player's next turn: if DAZED condition active, skip turn, decrement condition

**Narrative context for LLM:** "Player struck on the head. Helmet dented / skull ringing. Vision blurs momentarily."

### Torso (2) — WINDED

**Effect:** STR-based actions at disadvantage (-2 to roll) for 2 rounds. Narrative: blow to the midsection, breath knocked out.

**Mechanical implementation:**
- Apply condition: `condition_type = "winded"`, `expires_at_round = current_round + 2`
- When player makes STR-based attack or check while WINDED: apply -2 modifier

**STR-based actions definition:** Melee attacks using a STR-based weapon (swords, axes, maces, bludgeons). Ranged attacks (DEX-based) are not penalized.

**Narrative context:** "Player struck in the torso. Ribs bruised. Every swing costs them."

### Arm Wound (3 or 4) — ARM WOUND

**Effect:** All weapon attacks at -1 for 3 rounds.

**Mechanical implementation:**
- Apply condition: `condition_type = "arm_wound"`, `expires_at_round = current_round + 3`
- All attack rolls (melee and ranged) receive -1 modifier while active

**Narrative context:** "Arm gashed — muscle torn. The weapon wavers in their grip."

### Leg Wound (5 or 6) — LEG WOUND

**Effect:** Flee DEX roll at -2 for 3 rounds. Does not affect attack rolls.

**Mechanical implementation:**
- Apply condition: `condition_type = "leg_wound"`, `expires_at_round = current_round + 3`
- When player attempts Flee while LEG WOUND: apply -2 to DEX roll (see TASK_19)

**Narrative context:** "Leg cut deep. Every step is agony. Running will be harder."

---

## 5. Hit Location Effects: On ENEMIES (player crits enemy)

Enemy conditions are stored in the `combatants` JSON array within `active_combat`, not in `character_conditions` (which is player-only).

Enemy condition structure in combatants JSON:

```json
{
  "id": "goblin_001",
  "conditions": [
    {
      "type": "stunned",
      "expires_at_round": 4,
      "applied_at_round": 3
    }
  ]
}
```

### Head (1) — STUNNED

**Effect:** Enemy skips their next turn entirely.

**Implementation:** Add `{"type": "stunned", "expires_at_round": current_round + 1}` to enemy conditions. In `_resolve_enemy_turns()`, skip enemy if STUNNED condition active.

**Narrative context:** "Head blow — the creature staggers, eyes glazed, fighting instinct temporarily overwhelmed."

### Torso (2) — BLEEDING

**Effect:** Enemy takes 1 damage at the start of each turn for 3 turns.

**Implementation:** Add `{"type": "bleeding", "expires_at_round": current_round + 3}` to enemy conditions. In `_apply_condition_ticks()`, deal 1 damage before enemy acts.

**Narrative context:** "Deep torso wound — dark blood soaks through. The creature fights on, but it is dying by inches."

### Arm (3 or 4) — DISARMED / WEAKENED

**Effect:** Enemy attack damage reduced by 2 for 3 turns. (Disarmed is flavor — mechanically, damage is impaired.)

**Implementation:** Add `{"type": "arm_wound", "damage_penalty": -2, "expires_at_round": current_round + 3}` to enemy conditions. Apply penalty in enemy damage calculation.

**Narrative context:** "Arm hacked — weapon almost drops. The creature's blows grow ragged and weak."

### Leg (5 or 6) — HOBBLED

**Effect:** Enemy cannot flee for 3 turns. If the enemy's behavior profile would trigger a flee attempt, it is suppressed while HOBBLED.

**Implementation:** Add `{"type": "hobbled", "expires_at_round": current_round + 3}` to enemy conditions. In `decide_action()`, override flee attempt if HOBBLED.

**Narrative context:** "Leg wound — it lurches and staggers. The creature is not going anywhere."

---

## 6. Condition Interaction Rules

- Multiple conditions can coexist (a player can be WINDED and have an ARM WOUND simultaneously)
- A second crit on the same location while the condition is still active **resets the duration** (does not stack damage/penalty, just refreshes timer)
- DAZED from a head crit and PANICKED from fear both cause turn loss — they do not double-skip; one application is sufficient (the later one is redundant and ignored if already skip-queued)

---

## 7. Complete Crit Resolution Flow (Backend)

```python
def resolve_attack(attacker: dict, defender: dict, weapon: Weapon,
                   combat_state: CombatState) -> AttackResult:
    # 1. Roll attack
    raw_roll = roll_d20()
    attack_total = raw_roll + attacker_attack_modifier

    # 2. Hit check
    if raw_roll == 1:
        return AttackResult(hit=False, miss_type="fumble")
    if attack_total < defender_ac:
        return AttackResult(hit=False)

    # 3. Critical check
    crit_threshold = get_setting("combat_crit_threshold", default=5)
    is_crit = (raw_roll == 20) or (attack_total >= defender_ac + crit_threshold)

    # 4. Damage
    base_damage = roll_weapon_damage(weapon)
    damage = base_damage * 2 if is_crit else base_damage

    # 5. Hit location (crit only)
    hit_location = None
    condition_applied = None
    if is_crit:
        location_roll = roll_d6()
        hit_location = LOCATION_TABLE[location_roll]  # "head","torso","right_arm","left_arm","right_leg","left_leg"
        location_group = get_location_group(hit_location)  # "head","torso","arm","leg"
        condition_applied = apply_crit_condition(
            attacker_is_player=(attacker["id"] == "player"),
            location_group=location_group,
            target=defender,
            current_round=combat_state.round_number
        )

    return AttackResult(
        hit=True,
        raw_roll=raw_roll,
        attack_total=attack_total,
        damage=damage,
        is_crit=is_crit,
        hit_location=hit_location,
        condition_applied=condition_applied
    )


LOCATION_TABLE = {
    1: "head",
    2: "torso",
    3: "right_arm",
    4: "left_arm",
    5: "right_leg",
    6: "left_leg"
}

def get_location_group(location: str) -> str:
    if location == "head":   return "head"
    if location == "torso":  return "torso"
    if location in ("right_arm", "left_arm"):  return "arm"
    if location in ("right_leg", "left_leg"):  return "leg"


PLAYER_CRIT_CONDITIONS = {
    "head":  ("dazed",     1),   # (condition_type, duration_rounds)
    "torso": ("winded",    2),
    "arm":   ("arm_wound", 3),
    "leg":   ("leg_wound", 3)
}

ENEMY_CRIT_CONDITIONS = {
    "head":  ("stunned",   1),
    "torso": ("bleeding",  3),
    "arm":   ("arm_wound", 3),
    "leg":   ("hobbled",   3)
}
```

---

## 8. Narrator Context for Critical Hits

Critical hit data is passed to the Narrator as structured context:

```python
crit_events = [
    {
        "attacker": "Goblin Scout",
        "defender": "player",
        "hit_location": "right_arm",
        "location_group": "arm",
        "condition_applied": "arm_wound",
        "condition_duration_rounds": 3,
        "damage": 8
    }
]
```

Narrator prompt instruction: "For crit_events, describe the wound's location graphically but without gratuitous excess. Arm wound on the player? Their sword arm trembles. Head hit on the goblin? Its eyes roll back. Match location to physical consequence."

The Narrator receives both the location string (for anatomy) and the condition (for mechanical flavor: "stunned" → describe dazed state, "bleeding" → describe blood).

---

## 9. Admin Panel Configuration

### Settings Section — Combat Tab

| Setting Key | Label | Type | Default |
|---|---|---|---|
| `combat_crit_threshold` | Critical Hit Threshold (AC overshoot) | Integer (1–10) | 5 |

Change takes effect immediately (loaded from DB on each combat resolution). No restart required.

---

## 10. Implementation Notes

### Files to Create/Modify

| File | Change |
|---|---|
| `backend/app/services/combat_service.py` | Add crit check, location roll, condition dispatch |
| `backend/app/services/condition_service.py` | New or expanded — apply/tick/expire conditions |
| `backend/app/db/migrations/0012_character_conditions.sql` | Shared with TASK_16 |
| `backend/app/db/migrations/0013_combat_settings.sql` | `combat_crit_threshold` in game_config_settings |
| `frontend/js/combat_ui.js` | Display crit animation and location in round log |

### Test Plan

```bash
docker exec ai-gm-dev-backend-1 pytest backend/tests/test_critical_hits.py -v
```

Test cases:

| Test | Scenario | Expected |
|---|---|---|
| `test_nat20_always_crits` | Raw roll=20, enemy AC 100 | is_crit=True |
| `test_threshold_exact` | total=17, AC=12, threshold=5 | is_crit=True (17>=17) |
| `test_threshold_missed` | total=16, AC=12, threshold=5 | is_crit=False |
| `test_head_crit_player_dazed` | Crit on player, d6=1 | DAZED condition applied |
| `test_torso_crit_enemy_bleeding` | Crit on enemy, d6=2 | BLEEDING condition, -1 HP per turn |
| `test_arm_crit_enemy_damage_reduced` | Crit on enemy, d6=3 | attack damage -2 |
| `test_leg_crit_enemy_hobbled` | Crit on enemy, d6=5 | flee suppressed |
| `test_double_damage` | Any crit | damage = base * 2 |
| `test_condition_refresh` | 2nd crit same location during active condition | duration resets, no double-stack |
| `test_crit_threshold_admin` | Change `combat_crit_threshold` to 3 | threshold=3 respected in next combat |
| `test_narrator_receives_location` | Any crit | `crit_events` present in narrator_context |
