"""TDD: Issue #485 — Effect JSON Builder UI (gear_bonus format processing).

Frontend builder generates: {schema_version:1, effect_category:"gear_bonus", effects:[...]}
Verify backend correctly processes all 6 supported F1 types:
  damage_bonus, heal_on_hit, ac_bonus, static_stat_modifier, apply_condition, narrative_only
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pytest

from app.services.combat_service import (
    _decode_effect_json,
    _weapon_effects_of_type,
    _weapon_flat_damage_bonus,
    _weapon_heal_on_hit,
    _weapon_ac_bonus,
    _weapon_stat_modifiers,
)


def _weapon(effects: list) -> dict:
    """Build a mock weapon row with gear_bonus effect_json."""
    return {
        "effect_json": json.dumps({
            "schema_version": 1,
            "effect_category": "gear_bonus",
            "effects": effects,
        })
    }


# ─── _decode_effect_json ──────────────────────────────────────────────────────

def test_decode_returns_dict_for_gear_bonus():
    """_decode_effect_json parses gear_bonus JSON string into dict."""
    raw = json.dumps({"schema_version": 1, "effect_category": "gear_bonus", "effects": []})
    result = _decode_effect_json(raw)
    assert isinstance(result, dict)
    assert result["schema_version"] == 1
    assert result["effect_category"] == "gear_bonus"


def test_decode_returns_none_for_null():
    assert _decode_effect_json(None) is None


def test_decode_returns_none_for_invalid_json():
    assert _decode_effect_json("not-json{") is None


# ─── damage_bonus ─────────────────────────────────────────────────────────────

def test_damage_bonus_extracted():
    """Weapon with damage_bonus effect → _weapon_flat_damage_bonus returns value."""
    w = _weapon([{"type": "damage_bonus", "value": 5}])
    assert _weapon_flat_damage_bonus(w) == 5


def test_damage_bonus_multiple_stacked():
    """Multiple damage_bonus effects are summed."""
    w = _weapon([{"type": "damage_bonus", "value": 3}, {"type": "damage_bonus", "value": 2}])
    assert _weapon_flat_damage_bonus(w) == 5


def test_damage_bonus_zero_when_no_effects():
    """No effects → 0 damage bonus."""
    w = _weapon([])
    assert _weapon_flat_damage_bonus(w) == 0


# ─── heal_on_hit ──────────────────────────────────────────────────────────────

def test_heal_on_hit_extracted():
    """Weapon with heal_on_hit effect → _weapon_heal_on_hit returns value."""
    w = _weapon([{"type": "heal_on_hit", "value": 3}])
    assert _weapon_heal_on_hit(w) == 3


# ─── ac_bonus ────────────────────────────────────────────────────────────────

def test_ac_bonus_extracted():
    """Weapon/armor with ac_bonus effect → _weapon_ac_bonus returns value."""
    w = _weapon([{"type": "ac_bonus", "value": 2}])
    assert _weapon_ac_bonus(w) == 2


# ─── static_stat_modifier ─────────────────────────────────────────────────────

def test_static_stat_modifier_extracted():
    """Weapon with static_stat_modifier → _weapon_stat_modifiers returns {STAT: value}."""
    w = _weapon([{"type": "static_stat_modifier", "stat": "STR", "value": 2}])
    mods = _weapon_stat_modifiers(w)
    assert mods.get("STR") == 2


def test_static_stat_modifier_multiple_stats():
    """Multiple stat modifiers are all collected."""
    w = _weapon([
        {"type": "static_stat_modifier", "stat": "STR", "value": 2},
        {"type": "static_stat_modifier", "stat": "DEX", "value": 1},
    ])
    mods = _weapon_stat_modifiers(w)
    assert mods.get("STR") == 2
    assert mods.get("DEX") == 1


# ─── narrative_only ───────────────────────────────────────────────────────────

def test_narrative_only_causes_zero_damage_bonus():
    """narrative_only effect doesn't contribute to damage_bonus."""
    w = _weapon([{"type": "narrative_only"}])
    assert _weapon_flat_damage_bonus(w) == 0


def test_narrative_only_causes_zero_ac_bonus():
    """narrative_only effect doesn't contribute to ac_bonus."""
    w = _weapon([{"type": "narrative_only"}])
    assert _weapon_ac_bonus(w) == 0


def test_narrative_only_mixed_with_damage_bonus():
    """narrative_only + damage_bonus → only damage_bonus counts."""
    w = _weapon([{"type": "narrative_only"}, {"type": "damage_bonus", "value": 4}])
    assert _weapon_flat_damage_bonus(w) == 4


# ─── Mixed effects ────────────────────────────────────────────────────────────

def test_mixed_effects_type_isolation():
    """_weapon_effects_of_type returns only the requested type."""
    w = _weapon([
        {"type": "damage_bonus", "value": 3},
        {"type": "ac_bonus", "value": 1},
        {"type": "heal_on_hit", "value": 2},
    ])
    dmg = _weapon_effects_of_type(w, "damage_bonus")
    assert len(dmg) == 1
    assert dmg[0]["value"] == 3


def test_none_weapon_row_returns_safe_defaults():
    """None weapon row → all helpers return 0 / empty without error."""
    assert _weapon_flat_damage_bonus(None) == 0
    assert _weapon_heal_on_hit(None) == 0
    assert _weapon_ac_bonus(None) == 0
    assert _weapon_stat_modifiers(None) == {}
