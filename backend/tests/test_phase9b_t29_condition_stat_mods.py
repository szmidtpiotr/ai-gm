"""T29 — condition stat_mods applied to _combatant_stat_modifier."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import combat_service as cs


# ── helpers ───────────────────────────────────────────────────────────────────

def _sheet(str_=14, dex=12, con=10, int_=10, wis=10, cha=10, conditions=None):
    return {
        "stats": {"STR": str_, "DEX": dex, "CON": con, "INT": int_, "WIS": wis, "CHA": cha},
        "current_hp": 20,
        "max_hp": 20,
        "conditions": conditions or [],
    }


def _enemy(stats=None, dex_modifier=None, conditions=None):
    e = {"conditions": conditions or []}
    if stats is not None:
        e["stats"] = stats
    if dex_modifier is not None:
        e["dex_modifier"] = dex_modifier
    return e


def _cond(effect_json: dict):
    return {"key": "test_cond", "label": "Test", "effect_json": json.dumps(effect_json)}


def mod(combatant, *, sheet=None, stat):
    return cs._combatant_stat_modifier(combatant, sheet=sheet, stat=stat)


# ── baseline: no conditions ───────────────────────────────────────────────────

class TestBaseline:
    def test_player_str_modifier(self):
        sheet = _sheet(str_=16)  # (16-10)//2 = 3
        assert mod({}, sheet=sheet, stat="STR") == 3

    def test_player_dex_modifier(self):
        sheet = _sheet(dex=8)  # (8-10)//2 = -1
        assert mod({}, sheet=sheet, stat="DEX") == -1

    def test_enemy_from_stats_dict(self):
        enemy = _enemy(stats={"STR": 18})  # (18-10)//2 = 4
        assert mod(enemy, sheet=None, stat="STR") == 4

    def test_enemy_dex_fallback(self):
        enemy = _enemy(dex_modifier=2)
        assert mod(enemy, sheet=None, stat="DEX") == 2

    def test_unknown_stat_returns_zero(self):
        assert mod({}, sheet=_sheet(), stat="LCK") == 0

    def test_none_stat_returns_zero(self):
        assert mod({}, sheet=_sheet(), stat=None) == 0


# ── single condition stat_mods ────────────────────────────────────────────────

class TestSingleCondition:
    def test_player_poisoned_str_penalty(self):
        cond = _cond({"stat_mods": {"STR": -2}})
        sheet = _sheet(str_=14, conditions=[cond])  # base +2, -2 = 0
        assert mod({}, sheet=sheet, stat="STR") == 0

    def test_player_blinded_dex_penalty(self):
        cond = _cond({"stat_mods": {"DEX": -4}, "attack_penalty": -3})
        sheet = _sheet(dex=14, conditions=[cond])  # base +2, -4 = -2
        assert mod({}, sheet=sheet, stat="DEX") == -2

    def test_enemy_frightened_str_penalty(self):
        cond = _cond({"stat_mods": {"STR": -2, "INT": -1}})
        enemy = _enemy(stats={"STR": 16}, conditions=[cond])  # base +3, -2 = 1
        assert mod(enemy, sheet=None, stat="STR") == 1

    def test_penalty_only_applies_to_correct_stat(self):
        cond = _cond({"stat_mods": {"STR": -4}})
        sheet = _sheet(dex=14, conditions=[cond])
        assert mod({}, sheet=sheet, stat="DEX") == 2  # DEX unaffected

    def test_positive_stat_mod_is_applied(self):
        cond = _cond({"stat_mods": {"STR": 2}})
        sheet = _sheet(str_=10, conditions=[cond])  # base 0, +2 = 2
        assert mod({}, sheet=sheet, stat="STR") == 2


# ── stacking conditions ───────────────────────────────────────────────────────

class TestStackingConditions:
    def test_two_conditions_stack(self):
        c1 = _cond({"stat_mods": {"STR": -2}})
        c2 = _cond({"stat_mods": {"STR": -1}})
        sheet = _sheet(str_=16, conditions=[c1, c2])  # base +3, -3 = 0
        assert mod({}, sheet=sheet, stat="STR") == 0

    def test_cursed_multi_stat(self):
        cond = _cond({"stat_mods": {"STR": -1, "DEX": -1, "INT": -1, "WIS": -1}})
        sheet = _sheet(str_=14, dex=12, int_=10, wis=10, conditions=[cond])
        assert mod({}, sheet=sheet, stat="STR") == 1   # +2 -1
        assert mod({}, sheet=sheet, stat="DEX") == 0   # +1 -1
        assert mod({}, sheet=sheet, stat="INT") == -1  # 0  -1
        assert mod({}, sheet=sheet, stat="WIS") == -1  # 0  -1

    def test_enemy_stacked_enemy_conditions(self):
        c1 = _cond({"stat_mods": {"DEX": -2}})
        c2 = _cond({"stat_mods": {"DEX": -2}})
        enemy = _enemy(stats={"DEX": 14}, conditions=[c1, c2])  # base +2, -4 = -2
        assert mod(enemy, sheet=None, stat="DEX") == -2


# ── conditions without stat_mods are ignored ─────────────────────────────────

class TestNoStatMods:
    def test_damage_per_turn_condition_ignored(self):
        cond = _cond({"damage_per_turn": 3, "damage_type": "fire"})
        sheet = _sheet(str_=14, conditions=[cond])
        assert mod({}, sheet=sheet, stat="STR") == 2  # unchanged

    def test_block_action_condition_ignored(self):
        cond = _cond({"effects": [{"type": "block_action"}]})
        sheet = _sheet(dex=12, conditions=[cond])
        assert mod({}, sheet=sheet, stat="DEX") == 1  # unchanged

    def test_null_effect_json_ignored(self):
        cond = {"key": "empty", "label": "Empty", "effect_json": None}
        sheet = _sheet(str_=14, conditions=[cond])
        assert mod({}, sheet=sheet, stat="STR") == 2

    def test_malformed_effect_json_ignored(self):
        cond = {"key": "bad", "label": "Bad", "effect_json": "not_json{{"}
        sheet = _sheet(str_=14, conditions=[cond])
        assert mod({}, sheet=sheet, stat="STR") == 2
