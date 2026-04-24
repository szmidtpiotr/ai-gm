"""
combat_resolver.py
==================
Example flow for combat resolution with extensible damage/defense formulas.
"""

import random
import json
from typing import Dict, List, Any

def roll_die(notation: str) -> int:
    """Roll dice notation like 'd6', 'd20', '2d8'."""
    if 'd' not in notation:
        return int(notation)

    parts = notation.split('d')
    count = int(parts[0]) if parts[0] else 1
    sides = int(parts[1])

    return sum(random.randint(1, sides) for _ in range(count))


def calculate_stat_modifier(stat_value: int) -> int:
    """D&D-style modifier: floor((value - 10) / 2)"""
    return (stat_value - 10) // 2


def calculate_damage(
    attacker: Dict[str, Any],
    weapon: Dict[str, Any] = None,
    conditions: List[str] = None
) -> Dict[str, Any]:
    """
    Extensible damage calculation with placeholders for future mechanics.

    Returns: {
        'base_roll': int,
        'damage_bonus': int,
        'stat_modifier': int,
        'skill_bonus': int,        # PLACEHOLDER for future
        'condition_modifier': int, # PLACEHOLDER for buffs/debuffs
        'weapon_enchant': int,     # PLACEHOLDER for magic weapons
        'critical_multiplier': int,
        'total': int
    }
    """
    conditions = conditions or []

    # Base roll
    damage_die = weapon.get('damage_die', 'd6') if weapon else attacker.get('damage_die', 'd6')
    base_roll = roll_die(damage_die)

    # Damage bonus (from enemy record or weapon)
    damage_bonus = attacker.get('damage_bonus', 0)

    # Stat modifier (STR for melee, DEX for ranged, INT for spell)
    linked_stat = weapon.get('linked_stat', 'STR') if weapon else 'STR'
    stat_value = attacker.get('stats', {}).get(linked_stat, 10)
    stat_modifier = calculate_stat_modifier(stat_value)

    # === PLACEHOLDERS (currently 0, ready for expansion) ===
    skill_bonus = 0           # TODO: Add skill rank * multiplier
    condition_modifier = 0    # TODO: Check active buffs/debuffs
    weapon_enchant = 0        # TODO: Check if weapon has +1/+2 enchantment

    # Critical (if nat 20, multiply base roll)
    critical_multiplier = 1   # TODO: Detect nat 20 and set to 2 or 3
    effective_base = base_roll * critical_multiplier

    total = (
        effective_base
        + damage_bonus
        + stat_modifier
        + skill_bonus
        + condition_modifier
        + weapon_enchant
    )

    return {
        'base_roll': base_roll,
        'damage_bonus': damage_bonus,
        'stat_modifier': stat_modifier,
        'skill_bonus': skill_bonus,
        'condition_modifier': condition_modifier,
        'weapon_enchant': weapon_enchant,
        'critical_multiplier': critical_multiplier,
        'total': max(0, total)
    }


def calculate_defense(
    defender: Dict[str, Any],
    armor: Dict[str, Any] = None,
    conditions: List[str] = None
) -> Dict[str, Any]:
    """
    Extensible defense calculation with placeholders for armor/shields.

    Returns: {
        'defense_roll': int,
        'stat_modifier': int,
        'armor_value': int,        # PLACEHOLDER for armor system
        'shield_bonus': int,       # PLACEHOLDER for shields
        'dodge_bonus': int,        # PLACEHOLDER for dodge skill
        'condition_modifier': int, # PLACEHOLDER for buffs/debuffs
        'cover_bonus': int,        # PLACEHOLDER for environmental cover
        'total': int
    }
    """
    conditions = conditions or []

    # Base defense roll
    defense_roll = roll_die('d20')

    # Stat modifier (CON for physical attacks)
    stat_value = defender.get('stats', {}).get('CON', 10)
    stat_modifier = calculate_stat_modifier(stat_value)

    # === PLACEHOLDERS (currently 0, ready for expansion) ===
    armor_value = 0          # TODO: Read from equipped armor in inventory
    shield_bonus = 0         # TODO: +2 if shield equipped
    dodge_bonus = 0          # TODO: Add dodge skill bonus
    condition_modifier = 0   # TODO: Buffs like "Shield Spell" +3
    cover_bonus = 0          # TODO: +2/+5 if behind cover

    total = (
        defense_roll
        + stat_modifier
        + armor_value
        + shield_bonus
        + dodge_bonus
        + condition_modifier
        + cover_bonus
    )

    return {
        'defense_roll': defense_roll,
        'stat_modifier': stat_modifier,
        'armor_value': armor_value,
        'shield_bonus': shield_bonus,
        'dodge_bonus': dodge_bonus,
        'condition_modifier': condition_modifier,
        'cover_bonus': cover_bonus,
        'total': max(0, total)
    }


def resolve_attack(
    attacker: Dict[str, Any],
    defender: Dict[str, Any],
    weapon: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Full attack resolution: hit check → dodge → damage → defense → final HP.

    Returns: {
        'hit_check': {...},
        'dodge_check': {...},
        'damage_calc': {...},
        'defense_calc': {...},
        'final_damage': int,
        'defender_hp_after': int,
        'outcome': 'miss' | 'dodged' | 'hit'
    }
    """

    # 1. Hit check (attacker rolls d20 + attack_bonus vs AC)
    hit_roll = roll_die('d20') + attacker.get('attack_bonus', 0)
    target_ac = defender.get('ac_base', 10)
    hit_success = hit_roll >= target_ac

    if not hit_success:
        return {
            'hit_check': {'roll': hit_roll, 'target_ac': target_ac, 'success': False},
            'outcome': 'miss',
            'final_damage': 0,
            'defender_hp_after': defender['hp_current']
        }

    # 2. Dodge check (defender rolls d20 + DEX mod)
    dodge_roll = roll_die('d20') + calculate_stat_modifier(defender.get('stats', {}).get('DEX', 10))
    dodge_dc = 10 + attacker.get('attack_bonus', 0)  # Simple DC
    dodge_success = dodge_roll >= dodge_dc

    if dodge_success:
        return {
            'hit_check': {'roll': hit_roll, 'target_ac': target_ac, 'success': True},
            'dodge_check': {'roll': dodge_roll, 'dc': dodge_dc, 'success': True},
            'outcome': 'dodged',
            'final_damage': 0,
            'defender_hp_after': defender['hp_current']
        }

    # 3. Damage calculation
    damage_calc = calculate_damage(attacker, weapon)

    # 4. Defense calculation
    defense_calc = calculate_defense(defender)

    # 5. Final damage
    final_damage = max(0, damage_calc['total'] - defense_calc['total'])

    # 6. Update HP
    new_hp = max(0, defender['hp_current'] - final_damage)

    return {
        'hit_check': {'roll': hit_roll, 'target_ac': target_ac, 'success': True},
        'dodge_check': {'roll': dodge_roll, 'dc': dodge_dc, 'success': False},
        'damage_calc': damage_calc,
        'defense_calc': defense_calc,
        'final_damage': final_damage,
        'defender_hp_after': new_hp,
        'outcome': 'hit'
    }


# ============================================================
# Example usage
# ============================================================

if __name__ == '__main__':
    # Example: Arena Fighter attacks Player

    arena_fighter = {
        'id': 'enemy_1',
        'key': 'arena_fighter',
        'label': 'Gladiator Areny',
        'hp_current': 30,
        'hp_max': 30,
        'ac_base': 14,
        'attack_bonus': 5,
        'damage_die': 'd8',
        'damage_bonus': 3,
        'stats': {'STR': 16, 'DEX': 12, 'CON': 14}
    }

    player = {
        'id': 'player',
        'hp_current': 45,
        'hp_max': 50,
        'ac_base': 12,
        'stats': {'STR': 14, 'DEX': 12, 'CON': 13, 'INT': 10, 'WIS': 11, 'CHA': 9}
    }

    result = resolve_attack(arena_fighter, player)

    print("=== Attack Resolution ===")
    print(f"Outcome: {result['outcome']}")
    print(f"Final damage: {result['final_damage']}")
    print(f"Player HP: {player['hp_current']} → {result['defender_hp_after']}")

    if result.get('damage_calc'):
        print(f"\nDamage breakdown: {json.dumps(result['damage_calc'], indent=2)}")
    if result.get('defense_calc'):
        print(f"\nDefense breakdown: {json.dumps(result['defense_calc'], indent=2)}")
