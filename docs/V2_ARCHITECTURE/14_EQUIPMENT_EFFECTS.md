# AI-GM V2 — Equipment Effects Application

> How item effects (stat boosts, skill bonuses, HP bonuses, temp buffs) are applied to character stats and rolls.

---

## Decisions Made

| Question | Answer |
|----------|--------|
| Effect application timing | Calculated fresh every roll — no cached state |
| HP bonus on equip | Current HP also rises. At full HP → stays full at new cap |
| HP on unequip | Current HP capped at new (lower) max |
| Temp buff duration (in combat) | `duration_turns` combat rounds |
| Temp buff duration (out of combat) | `duration_hours` in-game hours |

---

## Effect Types Catalogue

All item effects live in `effect_json` (TEXT column on game_config_items and game_config_consumables). Defined format per type:

| Type key | Applies to | Example |
|---|---|---|
| `stat_mods` | Equipped items | `{"stat_mods":{"CON":1,"STR":1}}` |
| `hp_bonus` | Equipped items | `{"hp_bonus":3}` |
| `ac_bonus` | Armor (use `ac_bonus` column directly) | — |
| `spell_bonus` | Equipped spell focus | `{"spell_bonus":1}` |
| `skill_bonus` | Equipped items | `{"skill_bonus":{"stealth":2}}` |
| `magic_resistance` | Equipped items | `{"magic_resistance":0.1}` — future |
| `temp_stat_mods` | Consumables | `{"temp_stat_mods":{"DEX":4},"duration_turns":3,"duration_hours":1}` |
| `temp_weapon_bonus` | Consumables (weapon coating) | `{"temp_weapon_bonus":{"damage_bonus":1},"duration_turns":3}` |
| `apply_to_weapon` | Consumables | `{"apply_to_weapon":true,"on_hit_condition":"poisoned","save":"CON","dc":13}` |
| `remove_condition` | Consumables | `{"remove_condition":"bleeding"}` |
| `rest_bonus` | Consumables/misc | `{"rest_bonus":{"HP":2}}` |
| `light_radius_m` | Misc | `{"light_radius_m":9,"duration_minutes":60}` |
| `enables` | Misc | `{"enables":["climbing","lockpicking"]}` |
| `as_weapon` | Misc (improvised) | `{"as_weapon":{"damage_die":"d4","damage_type":"fire"}}` |

---

## Effective Stats Calculation

Every time a stat or modifier is needed, the system calculates fresh from:
1. Base stats in `sheet_json.stats`
2. `stat_mods` from all currently equipped items
3. `stat_mods` from all active conditions (temp buffs)

```python
def get_effective_stats(character_id: int) -> tuple[dict, dict]:
    """Returns (effective_stats, modifiers). Called before every roll."""
    
    sheet = db.get_character_sheet(character_id)
    effective = dict(sheet["stats"])   # base copy
    
    # Layer 1: equipped item stat_mods
    for item in db.get_equipped_items(character_id):
        effect = json.loads(item.effect_json or "{}")
        for stat, mod in effect.get("stat_mods", {}).items():
            if stat == "AC":
                continue  # AC calculated separately
            effective[stat] = effective.get(stat, 10) + mod
    
    # Layer 2: active condition stat_mods (temp buffs, wounds)
    for cond in db.get_active_conditions(character_id):
        effect = json.loads(cond.effect_json or "{}")
        for stat, mod in effect.get("stat_mods", {}).items():
            effective[stat] = effective.get(stat, 10) + mod
    
    modifiers = {s: (v - 10) // 2 for s, v in effective.items()}
    return effective, modifiers


def get_effective_ac(character_id: int) -> int:
    """Full AC: base 10 + armour ac_bonus + misc stat_mods[AC] + condition AC bonuses."""
    
    ac = 10
    
    for item in db.get_equipped_items(character_id):
        ac += item.ac_bonus   # direct column on game_config_items
        effect = json.loads(item.effect_json or "{}")
        ac += effect.get("stat_mods", {}).get("AC", 0)
    
    # Arcane Shield and similar condition-based AC bonuses
    for cond in db.get_active_conditions(character_id):
        effect = json.loads(cond.effect_json or "{}")
        ac += effect.get("ac_bonus", 0)
    
    return ac


def get_effective_max_hp(character_id: int) -> int:
    """Base HP formula + hp_bonus from equipped items."""
    
    sheet = db.get_character_sheet(character_id)
    archetype = db.get_archetype(sheet["archetype"])
    xp_total = db.get_xp_total(character_id)
    level = max(1, xp_total // 100)
    
    # Effective CON (includes ring bonuses)
    _, mods = get_effective_stats(character_id)
    con_mod = mods.get("CON", 0)
    
    base_hp = archetype.hp_base + (con_mod * level)
    
    # HP bonus from equipped items
    hp_bonus = sum(
        json.loads(item.effect_json or "{}").get("hp_bonus", 0)
        for item in db.get_equipped_items(character_id)
    )
    
    return max(1, base_hp + hp_bonus)


def get_effective_skill_bonus(character_id: int, skill_key: str) -> int:
    """Total equipment bonus to a specific skill."""
    
    bonus = 0
    for item in db.get_equipped_items(character_id):
        effect = json.loads(item.effect_json or "{}")
        bonus += effect.get("skill_bonus", {}).get(skill_key, 0)
    return bonus
```

---

## Equip / Unequip HP Handling

### Equipping an item with `hp_bonus`

```python
def on_equip_item(character_id: int, item_id: int):
    old_max = get_effective_max_hp(character_id)
    current = db.get_current_hp(character_id)
    
    db.equip_item(character_id, item_id)  # set equipped=True in inventory
    
    new_max = get_effective_max_hp(character_id)
    delta = new_max - old_max
    
    if delta > 0:
        if current == old_max:
            # Was at full HP → stay at full HP under new cap
            db.set_current_hp(character_id, new_max)
        else:
            # Was wounded → current also rises by same delta
            db.set_current_hp(character_id, min(current + delta, new_max))
```

| Before equip | After equip Ring (+3 HP) |
|---|---|
| 10/12 HP | 13/15 HP (current + delta) |
| 12/12 HP (full) | 15/15 HP (full at new cap) |
| 3/12 HP | 6/15 HP (current + delta) |

### Unequipping an item with `hp_bonus`

```python
def on_unequip_item(character_id: int, item_id: int):
    current = db.get_current_hp(character_id)
    
    db.unequip_item(character_id, item_id)  # set equipped=False
    
    new_max = get_effective_max_hp(character_id)
    
    # Cap current HP at new (lower) max
    if current > new_max:
        db.set_current_hp(character_id, new_max)
```

| Before unequip | After unequip Ring (-3 HP) |
|---|---|
| 15/15 HP | 12/12 HP |
| 13/15 HP | 12/12 HP (capped) |
| 6/15 HP | 6/12 HP (unchanged, already below) |
| 3/15 HP | 3/12 HP (unchanged) |

---

## Temporary Buff Consumables

### DB Schema Addition

`game_config_consumables.effect_json` needs two duration fields for dual-context buffs:

```json
{
  "temp_stat_mods": {"DEX": 4},
  "duration_turns": 3,
  "duration_hours": 1
}
```

`duration_turns`: rounds in combat
`duration_hours`: in-game hours outside combat

### Application on Use

```python
def apply_consumable_effect(character_id: int, item: Consumable, in_combat: bool):
    effect = json.loads(item.effect_json or "{}")
    
    if "temp_stat_mods" in effect or "temp_weapon_bonus" in effect:
        # Create a condition with appropriate duration
        if in_combat:
            db.apply_condition(character_id, {
                "condition_type": f"buff_{item.key}",
                "effect_json": json.dumps(effect),
                "rounds_remaining": effect.get("duration_turns", 3),
                "expires_at": None  # time-based not used in combat
            })
        else:
            ingame_hours = db.get_ingame_hours(character_id)
            db.apply_condition(character_id, {
                "condition_type": f"buff_{item.key}",
                "effect_json": json.dumps(effect),
                "rounds_remaining": None,  # round-based not used out of combat
                "expires_at": ingame_hours + effect.get("duration_hours", 1)
            })
    
    elif "remove_condition" in effect:
        db.remove_condition_by_type(character_id, effect["remove_condition"])
    
    elif "heal" in effect:
        # Handled by healing system (Task 23)
        apply_heal(character_id, effect["heal"])
    
    # Consume the item
    db.reduce_item_quantity(character_id, item.id, 1)
```

### Dual Duration Examples

| Consumable | In combat | Out of combat |
|---|---|---|
| Elixir of Agility (+4 DEX) | 3 rounds | 1 in-game hour |
| Elixir of Strength (+4 STR) | 3 rounds | 1 in-game hour |
| Whetstone (+1 DMG on weapon) | 1 combat (expires after fight ends) | No effect (out of combat) |
| Elixir of Giant Strength (+6 STR) | 5 rounds | 2 in-game hours |

---

## Weapon Coating (Poison Vial, Whetstone)

`apply_to_weapon: true` in effect_json means the consumable is applied to the equipped weapon, not the character.

```python
def apply_weapon_coating(character_id: int, item: Consumable):
    effect = json.loads(item.effect_json)
    weapon = db.get_equipped_weapon(character_id)
    
    if not weapon:
        return BLOCKED, "Nie masz wyposażonej broni."
    
    # Store coating on the weapon inventory slot
    db.set_weapon_coating(character_id, weapon.inventory_id, {
        "on_hit_condition": effect.get("on_hit_condition"),
        "save_stat": effect.get("save"),
        "save_dc": effect.get("dc"),
        "damage_bonus": effect.get("damage_bonus", 0),
        "uses_remaining": 1  # single application
    })
    
    db.reduce_item_quantity(character_id, item.id, 1)
```

On weapon hit: resolver checks for active coating, applies on-hit condition to target, decrements `uses_remaining`.

---

## Roll Calculation Pipeline

Full example — attack roll with equipment effects:

```
Player attacks Goblin (AC 11) with equipped Sword + Ring of Strength (+1 STR):

1. get_effective_stats(character_id):
   Base STR: 14 (+2)
   + Ring of Strength stat_mods.STR: +1
   Effective STR: 15 (+2... wait (15-10)//2 = 2, same mod)
   
   Actually: STR 14→15 mod stays +2. But STR 16→17 would change +3→+3, 18→19 is +4→+4.
   Ring of Strength with +1 STR is more useful when it crosses a modifier threshold.

2. get_effective_skill_bonus(character_id, "combat"):
   Cloak of Shadows: no combat bonus
   Whetstone coating: +1 DMG (not ATK)
   = 0 attack bonus from equipment

3. Attack roll = d20(15) + STR_mod(+2) + combat_skill(3) + proficiency(+2)
             = 15 + 2 + 3 + 2 = 22

4. Hit check: 22 vs AC 11 → HIT (22 ≥ 11) ✓
   Crit check: 22 - 11 = 11 ≥ 5 → CRITICAL HIT

5. Damage = d8(sword) + STR_mod(+2) + whetstone_coating(+1) = 5 + 2 + 1 = 8, doubled = 16
```

---

## Test Checklist

- [ ] Equip Ring of Endurance (+1 CON, +3 HP): verify max_hp and current_hp both rise correctly
- [ ] Equip ring at full HP: stays full at new cap
- [ ] Unequip ring: current HP capped at new lower max
- [ ] Unequip ring when HP above new max: HP drops to new max
- [ ] Equip Cloak of Shadows (+2 stealth): stealth roll increases by 2
- [ ] Equip Mage Robes (+1 spell): spell attack roll increases by 1
- [ ] Use Elixir of Agility in combat: condition applied with rounds_remaining=3
- [ ] Use Elixir of Agility out of combat: condition applied with expires_at=ingame_hours+1
- [ ] Elixir expires after 3 combat rounds: stats return to base
- [ ] Elixir out-of-combat expires after 1 in-game hour of travel: stats return to base
- [ ] Apply poison vial to sword: on-hit condition applied on next sword hit
- [ ] Antidote clears POISONED condition immediately
- [ ] All stat calculations fresh per roll: equip ring mid-combat, next roll uses new STR
- [ ] get_effective_ac includes armor ac_bonus + arcane_shield condition
