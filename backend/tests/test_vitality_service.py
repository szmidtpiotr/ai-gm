"""
Tests for Vitality Service — V2 Phase 02 Task 05
"""

import pytest
from app.services.vitality_service import (
    stat_modifier,
    calculate_hp,
    calculate_mana,
    apply_level_up,
    ARCHETYPE_BASE_HP,
    ARCHETYPE_BASE_MANA,
)


# ── stat_modifier ─────────────────────────────────────────────────────────

class TestStatModifier:
    def test_10_is_zero(self):   assert stat_modifier(10) == 0
    def test_11_is_zero(self):   assert stat_modifier(11) == 0
    def test_12_is_plus1(self):  assert stat_modifier(12) == 1
    def test_14_is_plus2(self):  assert stat_modifier(14) == 2
    def test_18_is_plus4(self):  assert stat_modifier(18) == 4
    def test_8_is_minus1(self):  assert stat_modifier(8) == -1
    def test_6_is_minus2(self):  assert stat_modifier(6) == -2
    def test_1_is_minus5(self):  assert stat_modifier(1) == -5  # (1-10)//2 = -9//2 = -5 (floor division)


# ── calculate_hp ─────────────────────────────────────────────────────────

class TestCalculateHP:
    # Spec examples table
    def test_warrior_level1_defaults(self):
        # CON 12, mod +1, level 1: 10 + 1×1 = 11
        assert calculate_hp("warrior", 12, 1) == 11

    def test_scholar_level1_defaults(self):
        # CON 10, mod 0, level 1: 6 + 0×1 = 6
        assert calculate_hp("scholar", 10, 1) == 6

    def test_warrior_level1_high_con(self):
        # CON 16, mod +3, level 1: 10 + 3×1 = 13
        assert calculate_hp("warrior", 16, 1) == 13

    def test_scholar_level1_high_con(self):
        # CON 14, mod +2, level 1: 6 + 2×1 = 8 (not 9 — base is 6 not 7)
        assert calculate_hp("scholar", 14, 1) == 8

    def test_warrior_level5_defaults(self):
        # CON 12, mod +1, level 5: 10 + 1×5 = 15
        assert calculate_hp("warrior", 12, 5) == 15

    def test_scholar_level5_defaults(self):
        # CON 10, mod 0, level 5: 6 + 0×5 = 6
        assert calculate_hp("scholar", 10, 5) == 6

    def test_minimum_is_1(self):
        # CON 1 (mod -5), level 1, Scholar: 6 + (-5×1) = 1 → still 1 (at the floor)
        assert calculate_hp("scholar", 1, 1) == 1
        # CON 1, level 10, Scholar: 6 + (-5×10) = -44 → clamped to 1
        assert calculate_hp("scholar", 1, 10) == 1

    def test_case_insensitive(self):
        assert calculate_hp("WARRIOR", 12, 1) == calculate_hp("warrior", 12, 1)

    def test_base_hp_constants(self):
        assert ARCHETYPE_BASE_HP["warrior"] == 10
        assert ARCHETYPE_BASE_HP["scholar"] == 6


# ── calculate_mana ────────────────────────────────────────────────────────

class TestCalculateMana:
    def test_scholar_level1_defaults(self):
        # INT 12, mod +1, level 1: 8 + 1×1 = 9
        assert calculate_mana("scholar", 12, 1) == 9

    def test_scholar_level5_defaults(self):
        # INT 12, mod +1, level 5: 8 + 1×5 = 13
        assert calculate_mana("scholar", 12, 5) == 13

    def test_warrior_always_zero(self):
        assert calculate_mana("warrior", 12, 1) == 0
        assert calculate_mana("warrior", 18, 5) == 0

    def test_scholar_low_int(self):
        # INT 8, mod -1, level 1: max(1, 8 + (-1×1)) = max(1, 7) = 7
        assert calculate_mana("scholar", 8, 1) == 7

    def test_minimum_is_1(self):
        # INT 1 (mod -4), level 10: max(1, 8 + (-4×10)) = max(1, -32) = 1
        assert calculate_mana("scholar", 1, 10) == 1

    def test_ranger_has_no_mana(self):
        assert calculate_mana("ranger", 14, 3) == 0

    def test_base_mana_constants(self):
        assert ARCHETYPE_BASE_MANA["warrior"] == 0
        assert ARCHETYPE_BASE_MANA["scholar"] == 8


# ── apply_level_up ────────────────────────────────────────────────────────

class TestApplyLevelUp:
    def test_warrior_gains_hp_with_positive_con(self):
        # CON 12, mod +1: hp increases by 1
        new_hp, new_mana = apply_level_up("warrior", 11, 0, 12, 10)
        assert new_hp == 12
        assert new_mana == 0

    def test_scholar_gains_hp_and_mana(self):
        # CON 10, mod 0: hp unchanged; INT 12, mod +1: mana +1
        new_hp, new_mana = apply_level_up("scholar", 6, 9, 10, 12)
        assert new_hp == 6   # 6 + 0 = 6, max(6, 6) = 6
        assert new_mana == 10  # 9 + 1 = 10

    def test_negative_con_mod_does_not_reduce_hp(self):
        # CON 8, mod -1: hp would decrease — floor to current value
        new_hp, new_mana = apply_level_up("warrior", 11, 0, 8, 10)
        assert new_hp == 11  # max(11, 11 + (-1)) = max(11, 10) = 11

    def test_negative_int_mod_does_not_reduce_mana(self):
        # INT 8, mod -1: mana would decrease — floor to current value
        new_hp, new_mana = apply_level_up("scholar", 6, 9, 10, 8)
        assert new_mana == 9  # max(9, 9 + (-1)) = max(9, 8) = 9

    def test_warrior_mana_always_stays_zero(self):
        new_hp, new_mana = apply_level_up("warrior", 11, 0, 14, 18)
        assert new_mana == 0
