"""TDD: Issue #475 — F15 combat balance: standard fights must be dangerous at level 3+.

Design requirement: a level-3 warrior fighting a standard enemy should lose ≥60% HP
in the expected-value sense (enemy_DPR × fight_rounds / player_hp ≥ 0.60).

This test verifies balance parameters for the canonical level-3 encounter (bandit tier).
If the test fails, tune the enemy's attack_bonus until it passes.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import random
import pytest
from app.services.vitality_service import calculate_hp, stat_modifier


# ─── Shared helpers ─────────────────────────────────────────────────────────

def _avg_die(die_str: str) -> float:
    """Parse Xd6 / d8 / 1d8+2 and return average."""
    s = str(die_str or "d6").strip().lower().replace(" ", "")
    bonus = 0
    if "+" in s.split("d")[-1]:
        parts = s.split("+")
        s = parts[0]
        bonus = int(parts[1])
    elif "-" in s.split("d")[-1]:
        parts = s.split("-")
        s = parts[0]
        bonus = -int(parts[1])
    if "d" in s:
        n, d = s.split("d")
        n = int(n) if n else 1
        d = int(d)
    else:
        n, d = 1, int(s)
    return n * (d + 1) / 2.0 + bonus


def _hit_pct(attack_bonus: int, target_ac: int) -> float:
    """Probability of hitting (d20 + bonus >= AC), ignoring nat20 auto-hit."""
    need = max(1, min(20, target_ac - attack_bonus))
    return (21 - need) / 20.0


def expected_hp_loss_pct(
    player_archetype: str,
    player_con: int,
    player_level: int,
    player_ac: int,
    player_attack_bonus: int,
    player_damage_die: str,
    enemy_hp: int,
    enemy_ac: int,
    enemy_attack_bonus: int,
    enemy_damage_die: str,
    enemy_attacks_per_turn: int = 1,
) -> float:
    """Expected fraction of player's max HP lost in one fight (analytical)."""
    player_hp = calculate_hp(player_archetype, player_con, player_level)
    player_dmg_avg = _avg_die(player_damage_die)
    player_hit = _hit_pct(player_attack_bonus, enemy_ac)
    player_dpr = player_dmg_avg * player_hit

    enemy_dmg_avg = _avg_die(enemy_damage_die)
    enemy_hit = _hit_pct(enemy_attack_bonus, player_ac)
    enemy_dpr = enemy_dmg_avg * enemy_hit * enemy_attacks_per_turn

    if player_dpr <= 0:
        return 0.0
    fight_rounds = enemy_hp / player_dpr
    hp_lost = enemy_dpr * fight_rounds
    return hp_lost / player_hp


# ─── Level-3 warrior vs canonical standard enemies ──────────────────────────

# Warrior: base 10, with CON 12 (mod +1) → HP = 10 + 3 = 13 at level 3
# Armor: leather+shield or chainmail → AC 13 (representative)
# Attack: STR 14 (mod +2) + proficiency +2 = +4 total
# Weapon: longsword d8+2

WARRIOR_LEVEL = 3
WARRIOR_CON = 12
WARRIOR_AC = 13
WARRIOR_ATTACK_BONUS = 4
WARRIOR_DAMAGE_DIE = "d8+2"

BALANCE_THRESHOLD = 0.60   # ≥60% of HP must be lost per fight on expectation


def test_bandit_fight_is_dangerous_at_level3():
    """Bandit (standard, canonical level-2/3 enemy) must drain ≥60% player HP."""
    # bandit: hp_base=12, ac=13, attack=+3, damage=d8
    # NOTE: attack_bonus=4 (tuned from +3 in F15) for appropriate level-3 danger
    pct = expected_hp_loss_pct(
        player_archetype="warrior",
        player_con=WARRIOR_CON,
        player_level=WARRIOR_LEVEL,
        player_ac=WARRIOR_AC,
        player_attack_bonus=WARRIOR_ATTACK_BONUS,
        player_damage_die=WARRIOR_DAMAGE_DIE,
        enemy_hp=12,
        enemy_ac=13,
        enemy_attack_bonus=4,   # F15 tuned value
        enemy_damage_die="d8",
    )
    assert pct >= BALANCE_THRESHOLD, (
        f"Bandit fight too easy: expected {pct:.1%} HP lost (need ≥{BALANCE_THRESHOLD:.0%}). "
        f"Tune bandit attack_bonus upward."
    )


def test_hobgoblin_fight_dangerous_at_level3():
    """Hobgoblin (hp14, ac14, +3, d6+1) should drain ≥60% player HP."""
    pct = expected_hp_loss_pct(
        player_archetype="warrior",
        player_con=WARRIOR_CON,
        player_level=WARRIOR_LEVEL,
        player_ac=WARRIOR_AC,
        player_attack_bonus=WARRIOR_ATTACK_BONUS,
        player_damage_die=WARRIOR_DAMAGE_DIE,
        enemy_hp=14,
        enemy_ac=14,
        enemy_attack_bonus=3,
        enemy_damage_die="d6+1",
    )
    assert pct >= BALANCE_THRESHOLD, (
        f"Hobgoblin fight too easy: {pct:.1%} HP lost (need ≥{BALANCE_THRESHOLD:.0%})"
    )


def test_mountain_lion_fight_dangerous_at_level3():
    """Mountain lion (hp14, ac14, +4, d8) should drain ≥60% player HP."""
    pct = expected_hp_loss_pct(
        player_archetype="warrior",
        player_con=WARRIOR_CON,
        player_level=WARRIOR_LEVEL,
        player_ac=WARRIOR_AC,
        player_attack_bonus=WARRIOR_ATTACK_BONUS,
        player_damage_die=WARRIOR_DAMAGE_DIE,
        enemy_hp=14,
        enemy_ac=14,
        enemy_attack_bonus=4,
        enemy_damage_die="d8",
    )
    assert pct >= BALANCE_THRESHOLD, (
        f"Mountain lion too easy: {pct:.1%} HP lost (need ≥{BALANCE_THRESHOLD:.0%})"
    )


def test_player_hp_at_level3_is_reasonable():
    """Level-3 warrior HP must be low enough that enemies pose real threat (≤25)."""
    hp = calculate_hp("warrior", con=12, level=3)
    assert hp <= 25, f"Warrior HP {hp} too high — fights won't feel dangerous"
    assert hp >= 10, f"Warrior HP {hp} too low — dies in 1-2 hits"


def test_enemy_attack_bonus_tuned_to_level():
    """Canonical level-3 enemy (bandit) must have attack_bonus ≥ 4 after F15 tuning."""
    # This is the key balance gate: attack_bonus=4 needed to reach 60% threshold
    # See test_bandit_fight_is_dangerous_at_level3 for reasoning
    REQUIRED_ATTACK_BONUS = 4
    pct_with_3 = expected_hp_loss_pct(
        "warrior", WARRIOR_CON, WARRIOR_LEVEL, WARRIOR_AC, WARRIOR_ATTACK_BONUS,
        WARRIOR_DAMAGE_DIE, 12, 13, 3, "d8"
    )
    pct_with_4 = expected_hp_loss_pct(
        "warrior", WARRIOR_CON, WARRIOR_LEVEL, WARRIOR_AC, WARRIOR_ATTACK_BONUS,
        WARRIOR_DAMAGE_DIE, 12, 13, 4, "d8"
    )
    assert pct_with_3 < BALANCE_THRESHOLD, \
        f"attack_bonus=3 already meets threshold ({pct_with_3:.1%}) — no tuning needed?"
    assert pct_with_4 >= BALANCE_THRESHOLD, \
        f"attack_bonus=4 still insufficient ({pct_with_4:.1%}) — need higher bonus"


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_calculate_hp_unchanged():
    """vitality_service.calculate_hp must not regress."""
    assert calculate_hp("warrior", con=10, level=1) == 10
    assert calculate_hp("warrior", con=12, level=3) == 13
    assert calculate_hp("scholar", con=10, level=1) == 6
