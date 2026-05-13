# TASK 15: Enemy AI — Rule-Based Behavior Profiles

**Status:** ✅ Done — commit `b22299d` (2026-05-13)

## Overview

Enemy decisions are resolved by deterministic Python logic, not the LLM. Each enemy type has a `behavior_profile_key` that points to a row in `enemy_behavior_profiles`. On each enemy turn, `enemy_behavior_service.py` reads the profile, evaluates conditions in priority order, and returns a structured action. The LLM never touches the decision — it only receives the resolved action as narration context.

**Why rule-based?** LLM decisions introduce latency, non-determinism, and cost on every enemy turn. Tactical behavior can be fully expressed as threshold logic and priority tables. The LLM's role is flavor, not tactics.

---

## 1. Data Model

### game_config_enemies (existing, add column)

```sql
ALTER TABLE game_config_enemies
ADD COLUMN behavior_profile_key TEXT NOT NULL DEFAULT 'default_aggressive';
```

### enemy_behavior_profiles (new table)

```sql
CREATE TABLE IF NOT EXISTS enemy_behavior_profiles (
    key                          TEXT PRIMARY KEY,
    display_name                 TEXT NOT NULL,
    default_action               TEXT NOT NULL
        CHECK(default_action IN ('attack_player','attack_weakest','random','defend')),
    hp_threshold_flee            REAL NOT NULL DEFAULT 0.0,
        -- 0.0 = never flee; 0.25 = flee when HP < 25%
    flee_dex_bonus               INTEGER NOT NULL DEFAULT 0,
    special_ability_key          TEXT,
        -- NULL = no special ability
    special_ability_cooldown_turns INTEGER NOT NULL DEFAULT 0,
    fear_aura                    INTEGER NOT NULL DEFAULT 0 CHECK(fear_aura IN (0,1)),
    fear_dc                      INTEGER NOT NULL DEFAULT 0,
    dialogue_on_aggro            TEXT,
        -- Passed to Narrator, displayed when enemy enters combat
    dialogue_on_death            TEXT,
        -- Passed to Narrator, displayed on enemy death
    created_at                   TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### active_combat combatants JSON — per-enemy runtime state

Each enemy entry in the `active_combat.combatants` JSON array carries a `cooldown_counter` field that starts at 0 and counts down each turn:

```json
{
  "id": "goblin_001",
  "name": "Goblin Scout",
  "hp": 8,
  "max_hp": 8,
  "dex_modifier": 1,
  "initiative": 14,
  "conditions": [],
  "behavior_profile_key": "goblin_standard",
  "cooldown_counter": 0,
  "is_alive": true
}
```

---

## 2. Behavior Profile Fields Reference

| Field | Type | Description |
|---|---|---|
| `key` | TEXT | Unique identifier, referenced by enemy row |
| `default_action` | ENUM | Fallback action when no condition triggers |
| `hp_threshold_flee` | FLOAT | HP fraction below which flee is attempted (0 = never) |
| `flee_dex_bonus` | INT | Bonus to enemy DEX roll when fleeing (cowardly enemies run fast) |
| `special_ability_key` | TEXT? | Key into `enemy_special_abilities` table; NULL = none |
| `special_ability_cooldown_turns` | INT | Turns between special ability uses (0 = every turn) |
| `fear_aura` | BOOL | Whether this enemy triggers a Fear check on player (see TASK_16) |
| `fear_dc` | INT | DC for the Fear saving throw; 0 if `fear_aura` is false |
| `dialogue_on_aggro` | TEXT? | Flavor line passed to Narrator when enemy engages |
| `dialogue_on_death` | TEXT? | Flavor line passed to Narrator when enemy dies |

---

## 3. Special Abilities Table

```sql
CREATE TABLE IF NOT EXISTS enemy_special_abilities (
    key              TEXT PRIMARY KEY,
    display_name     TEXT NOT NULL,
    ability_type     TEXT NOT NULL
        CHECK(ability_type IN (
            'damage_aoe','ranged_attack','self_heal','buff_allies',
            'debuff_player','charming_gaze','pack_tactics','throw_rock'
        )),
    effect_json      TEXT NOT NULL,
        -- JSON blob with effect parameters, e.g. {"damage": "1d4", "range": 2}
    trigger_condition TEXT NOT NULL DEFAULT 'always'
        CHECK(trigger_condition IN ('always','hp_below_50','allies_present','player_adjacent'))
);
```

---

## 4. Behavior Decision Logic (Pseudocode)

`enemy_behavior_service.decide_action(enemy: dict, combat_state: CombatState) -> EnemyAction`

```python
def decide_action(enemy: dict, combat_state: CombatState) -> EnemyAction:
    profile = load_profile(enemy["behavior_profile_key"])
    hp_pct = enemy["hp"] / enemy["max_hp"]

    # Priority 1: Flee check
    if profile.hp_threshold_flee > 0 and hp_pct < profile.hp_threshold_flee:
        if not is_location_enclosed(combat_state.location_id):
            return EnemyAction(
                type="flee",
                dex_roll=roll_d20() + enemy_dex_modifier + profile.flee_dex_bonus
            )

    # Priority 2: Special ability (if available and conditions met)
    if profile.special_ability_key is not None:
        if enemy["cooldown_counter"] == 0:
            ability = load_special_ability(profile.special_ability_key)
            if check_trigger_condition(ability.trigger_condition, enemy, combat_state):
                enemy["cooldown_counter"] = profile.special_ability_cooldown_turns
                return EnemyAction(
                    type="special_ability",
                    ability_key=profile.special_ability_key,
                    ability=ability
                )

    # Decrement cooldown regardless of action taken
    if enemy["cooldown_counter"] > 0:
        enemy["cooldown_counter"] -= 1

    # Priority 3: Default action
    if profile.default_action == "attack_player":
        target = combat_state.player
    elif profile.default_action == "attack_weakest":
        target = get_lowest_hp_target(combat_state)
    elif profile.default_action == "random":
        target = random.choice(combat_state.valid_targets)
    else:  # defend
        return EnemyAction(type="defend")

    return EnemyAction(
        type="attack",
        target=target,
        roll=roll_d20() + enemy_attack_modifier
    )
```

### check_trigger_condition logic

```python
def check_trigger_condition(condition: str, enemy: dict, state: CombatState) -> bool:
    if condition == "always":
        return True
    if condition == "hp_below_50":
        return enemy["hp"] / enemy["max_hp"] < 0.50
    if condition == "allies_present":
        alive_enemies = [e for e in state.combatants if e["is_alive"] and e["id"] != enemy["id"]]
        return len(alive_enemies) > 0
    if condition == "player_adjacent":
        return state.player_in_melee_range  # determined by location type
    return False
```

---

## 5. Example Behavior Profiles

### goblin_standard

```json
{
  "key": "goblin_standard",
  "display_name": "Goblin Scout",
  "default_action": "attack_player",
  "hp_threshold_flee": 0.25,
  "flee_dex_bonus": 2,
  "special_ability_key": "throw_rock",
  "special_ability_cooldown_turns": 2,
  "fear_aura": false,
  "fear_dc": 0,
  "dialogue_on_aggro": "Yargh! Smash the soft one!",
  "dialogue_on_death": "No... not like this..."
}
```

Behavior: Attacks the player by default. Throws a rock every other turn (1d4 ranged, trigger=always). Runs when below 25% HP.

### bandit_raider

```json
{
  "key": "bandit_raider",
  "display_name": "Bandit Raider",
  "default_action": "attack_weakest",
  "hp_threshold_flee": 0.0,
  "flee_dex_bonus": 0,
  "special_ability_key": null,
  "special_ability_cooldown_turns": 0,
  "fear_aura": false,
  "fear_dc": 0,
  "dialogue_on_aggro": "Your coin or your life, traveler.",
  "dialogue_on_death": null
}
```

Behavior: Targets the weakest combatant. Never flees — bandits fight to the death or until knocked down. No special ability.

### wolf_pack

```json
{
  "key": "wolf_pack",
  "display_name": "Wolf",
  "default_action": "attack_player",
  "hp_threshold_flee": 0.15,
  "flee_dex_bonus": 1,
  "special_ability_key": "pack_tactics",
  "special_ability_cooldown_turns": 0,
  "fear_aura": false,
  "fear_dc": 0,
  "dialogue_on_aggro": null,
  "dialogue_on_death": null
}
```

Behavior: Uses pack_tactics (trigger=allies_present) — attacks with advantage (+2 to hit) when at least one other wolf is alive. Falls back to normal attack when alone. Flees at 15% HP.

Pack tactics special ability:
```json
{
  "key": "pack_tactics",
  "display_name": "Pack Tactics",
  "ability_type": "buff_allies",
  "effect_json": {"attack_bonus": 2},
  "trigger_condition": "allies_present"
}
```

### skeleton_warrior

```json
{
  "key": "skeleton_warrior",
  "display_name": "Skeleton Warrior",
  "default_action": "attack_player",
  "hp_threshold_flee": 0.0,
  "flee_dex_bonus": 0,
  "special_ability_key": null,
  "special_ability_cooldown_turns": 0,
  "fear_aura": true,
  "fear_dc": 12,
  "dialogue_on_aggro": null,
  "dialogue_on_death": null
}
```

Behavior: Mindlessly attacks the player. Never flees (undead). Triggers Fear check on encounter (fear_dc 12). No dialogue — skeletons do not speak.

### troll_cave

```json
{
  "key": "troll_cave",
  "display_name": "Cave Troll",
  "default_action": "attack_player",
  "hp_threshold_flee": 0.0,
  "flee_dex_bonus": 0,
  "special_ability_key": "regenerate",
  "special_ability_cooldown_turns": 0,
  "fear_aura": true,
  "fear_dc": 12,
  "dialogue_on_aggro": "*low guttural roar*",
  "dialogue_on_death": "*crashes to ground with earth-shaking finality*"
}
```

Behavior: Regenerates 2 HP at the start of every turn (trigger=always, cooldown=0). Never flees. Triggers Fear check.

Regenerate special ability:
```json
{
  "key": "regenerate",
  "display_name": "Troll Regeneration",
  "ability_type": "self_heal",
  "effect_json": {"heal": 2},
  "trigger_condition": "always"
}
```

### vampire_thrall

```json
{
  "key": "vampire_thrall",
  "display_name": "Vampire Thrall",
  "default_action": "attack_player",
  "hp_threshold_flee": 0.0,
  "flee_dex_bonus": 0,
  "special_ability_key": "charming_gaze",
  "special_ability_cooldown_turns": 3,
  "fear_aura": true,
  "fear_dc": 16,
  "dialogue_on_aggro": "Serve the master. Become still.",
  "dialogue_on_death": "...freed... at last..."
}
```

Behavior: Charming Gaze every 3 turns — debuffs player (cannot attack, can only flee or use item, for 1 turn), trigger=always. Never flees. Triggers Fear check (DC 16 — terrifying).

Charming gaze special ability:
```json
{
  "key": "charming_gaze",
  "display_name": "Charming Gaze",
  "ability_type": "debuff_player",
  "effect_json": {
    "condition": "charmed",
    "duration_turns": 1,
    "restrictions": ["cannot_attack"]
  },
  "trigger_condition": "always"
}
```

---

## 6. Dialogue Integration with the Narrator

`dialogue_on_aggro` and `dialogue_on_death` are stored as plain text in the profile. They are **not** spoken by the LLM — they are passed as context so the Narrator can weave them in:

```python
narrator_context = {
    "round_log": round_log,
    "enemy_aggro_dialogue": [
        {"enemy_name": "Goblin Scout", "line": "Yargh! Smash the soft one!"}
    ],
    "enemy_death_dialogue": [],
    "tone": "dark_fantasy"
}
```

The Narrator prompt instructs it: "If an enemy dialogue line is provided for aggro or death, incorporate its sentiment into your narration. Do not use it verbatim unless it is clearly a dramatic last word."

If `dialogue_on_aggro` is null (e.g. skeletons), the Narrator receives no dialogue hint and invents appropriate atmospheric description.

---

## 7. Implementation Notes

### New File: `backend/app/services/enemy_behavior_service.py`

- `load_profile(key: str) -> BehaviorProfile`
- `decide_action(enemy: dict, combat_state: CombatState) -> EnemyAction`
- `check_trigger_condition(condition: str, enemy: dict, state: CombatState) -> bool`
- `resolve_special_ability(ability: SpecialAbility, enemy: dict, target: dict) -> AbilityResult`

### Migration

Add to `backend/app/db/migrations/0011_enemy_behavior.sql`:

```sql
CREATE TABLE IF NOT EXISTS enemy_behavior_profiles ( ... );
CREATE TABLE IF NOT EXISTS enemy_special_abilities ( ... );
ALTER TABLE game_config_enemies ADD COLUMN behavior_profile_key TEXT NOT NULL DEFAULT 'default_aggressive';

-- Seed default profiles
INSERT INTO enemy_behavior_profiles VALUES ('goblin_standard', ...);
INSERT INTO enemy_behavior_profiles VALUES ('bandit_raider', ...);
INSERT INTO enemy_behavior_profiles VALUES ('wolf_pack', ...);
INSERT INTO enemy_behavior_profiles VALUES ('skeleton_warrior', ...);
INSERT INTO enemy_behavior_profiles VALUES ('troll_cave', ...);
INSERT INTO enemy_behavior_profiles VALUES ('vampire_thrall', ...);
```

### Admin Panel

A new "Enemy Behavior Profiles" section in the Admin Panel should allow CRUD on `enemy_behavior_profiles` and `enemy_special_abilities`, and allow assigning a `behavior_profile_key` to each enemy in the enemy editor.

### Testing

```bash
docker exec ai-gm-dev-backend-1 pytest backend/tests/test_enemy_behavior.py -v

# Verify LLM is not called during enemy turn resolution
# (mock llm_service, confirm call count = 0 during resolve_enemy_turns)
```

Key test cases:
- Goblin flees at 24% HP, does not flee at 26% HP
- Troll regenerates 2 HP even when cooldown=0 (every turn)
- Wolf pack_tactics +2 only fires when ally alive, not when solo
- Vampire thrall charming_gaze cooldown resets correctly after 3 turns
- Skeleton never flees regardless of HP
- Enemy with no special_ability_key never triggers ability branch
