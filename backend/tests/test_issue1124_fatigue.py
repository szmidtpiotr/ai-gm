"""TDD: Issue #1124 — PT-D1 Zmęczenie (fatigue) stacks za marsz >8h i brak noclegu.

Fatigue modeled on the existing stackable `exhausted` condition. Numbers live in
game_config_conditions.exhausted.effect_json (sandbox-tunable). New primitives:
`test_penalty` (per_level), `initiative_penalty` + `regen_multiplier` (threshold_effects).

Verification (z issue):
- 9h marszu → 1 stack i -1 do testu
- nocleg → 0 stacków
- 3 stacki → połowa regeneracji
"""
import sys

sys.path.insert(0, "/app")

import pytest

from app.services import fatigue_service as fs


# Nowy effect_json kondycji `exhausted` (PT-D1). Trzymamy go w teście jako kontrakt
# — migracja musi wyprodukować dokładnie te prymitywy.
EXHAUSTED_EFFECT_JSON = (
    '{"schema_version":1,"effect_category":"character_condition","effects":['
    '{"type":"stacking_levels","max_level":3,'
    '"per_level_effects":[{"type":"test_penalty","value":-1}],'
    '"threshold_effects":{'
    '"2":{"type":"initiative_penalty","value":-2},'
    '"3":{"type":"regen_multiplier","value":0.5}}}]}'
)


def _exhausted(level: int) -> dict:
    return {
        "key": "exhausted",
        "label": "Wyczerpany",
        "effect_json": EXHAUSTED_EFFECT_JSON,
        "runtime": {"level": level},
    }


# ─── Trigger: nabijanie stacków ──────────────────────────────────────────────

def test_bump_from_empty_adds_level_1():
    """Pierwsze przekroczenie 8h marszu → exhausted poziom 1."""
    conds, level = fs.bump_fatigue_stack([], _exhausted(1), max_level=3)
    assert level == 1
    assert fs.read_fatigue_level(conds) == 1


def test_bump_increments_existing_level():
    """Kolejny dzień/przekroczenie podbija poziom, nie dubluje kondycji."""
    start = [_exhausted(1)]
    conds, level = fs.bump_fatigue_stack(start, _exhausted(1), max_level=3)
    assert level == 2
    assert len([c for c in conds if c["key"] == "exhausted"]) == 1
    assert fs.read_fatigue_level(conds) == 2


def test_bump_caps_at_max_level_3():
    """Max 3 stacki — czwarte nabicie nic nie zmienia."""
    conds = [_exhausted(3)]
    conds, level = fs.bump_fatigue_stack(conds, _exhausted(1), max_level=3)
    assert level == 3
    assert fs.read_fatigue_level(conds) == 3


# ─── Kara do testów (-1 / -2 / -3 per stack) ─────────────────────────────────

def test_test_penalty_scales_with_level():
    assert fs.compute_test_penalty([_exhausted(1)]) == -1
    assert fs.compute_test_penalty([_exhausted(2)]) == -2
    assert fs.compute_test_penalty([_exhausted(3)]) == -3


def test_no_fatigue_no_penalty():
    assert fs.compute_test_penalty([]) == 0
    assert fs.read_fatigue_level([]) == 0


def test_penalty_reaches_skill_roll_total():
    """9h marszu → 1 stack → -1 do sumy modyfikatora testu (calc_skill_modifier_info)."""
    from app.services.skill_service import calc_skill_modifier_info

    base_sheet = {"stats": {"STR": 14, "DEX": 10}, "skills": {"athletics": 0}}
    tired_sheet = {**base_sheet, "conditions": [_exhausted(1)]}

    base = calc_skill_modifier_info(base_sheet, "athletics")["total"]
    tired = calc_skill_modifier_info(tired_sheet, "athletics")["total"]
    assert tired == base - 1


def test_skill_roll_backward_compatible_without_conditions():
    """Bez kondycji suma modyfikatora się nie zmienia (regresja)."""
    from app.services.skill_service import calc_skill_modifier_info

    sheet = {"stats": {"STR": 16}, "skills": {"athletics": 3}}
    info = calc_skill_modifier_info(sheet, "athletics")
    # STR 16 → +3, rank 3 → proficiency +2, skill_rank 3 → total 3+3+2 = 8
    assert info["total"] == 8


# ─── Inicjatywa (gorsza od 2 stacków) ────────────────────────────────────────

def test_initiative_penalty_from_2_stacks():
    assert fs.compute_initiative_penalty([_exhausted(1)]) == 0
    assert fs.compute_initiative_penalty([_exhausted(2)]) == -2
    assert fs.compute_initiative_penalty([_exhausted(3)]) == -2


# ─── Połowa regeneracji przy 3 stackach ──────────────────────────────────────

def test_regen_multiplier_half_at_3_stacks():
    assert fs.compute_regen_multiplier([_exhausted(1)]) == 1.0
    assert fs.compute_regen_multiplier([_exhausted(2)]) == 1.0
    assert fs.compute_regen_multiplier([_exhausted(3)]) == 0.5


# ─── Czyszczenie: pełny nocleg TAK, krótki odpoczynek NIE ─────────────────────

def test_long_rest_clears_all_fatigue():
    conds = fs.clear_all_fatigue([_exhausted(3)])
    assert fs.read_fatigue_level(conds) == 0
    assert not any(c.get("key") == "exhausted" for c in conds)


def test_long_rest_keeps_non_stacking_conditions():
    """Kondycje bez stacking_levels (np. cursed) pozostają nietknięte."""
    cursed = {"key": "cursed", "label": "Przeklęty", "effect_json": "{}", "runtime": {}}
    conds = fs.clear_all_fatigue([_exhausted(2), cursed])
    assert any(c.get("key") == "cursed" for c in conds)
    assert fs.read_fatigue_level(conds) == 0


# ─── Krasnolud „twardy jak kamień" — ignoruje kary 1. stacka (propozycja) ─────

def test_dwarf_ignores_first_stack_penalty():
    assert fs.compute_test_penalty([_exhausted(1)], race="dwarf") == 0
    assert fs.compute_test_penalty([_exhausted(2)], race="dwarf") == -1
    assert fs.compute_test_penalty([_exhausted(3)], race="dwarf") == -2


def test_dwarf_initiative_shifted_by_one():
    assert fs.compute_initiative_penalty([_exhausted(2)], race="dwarf") == 0
    assert fs.compute_initiative_penalty([_exhausted(3)], race="dwarf") == -2


# ─── Backward compat: silnik combatu NIE karze statów za zmęczenie ───────────

def test_fatigue_does_not_touch_combat_stat_modifier():
    """test_penalty nie jest static_stat_modifier → _combatant_stat_modifier bez zmian
    (kara dotyczy testów umiejętności, nie ataku/obrażeń w walce)."""
    from app.services.combat_service import _combatant_stat_modifier

    sheet = {"stats": {"STR": 14}, "conditions": [_exhausted(3)]}
    # STR 14 → +2, zmęczenie NIE rusza tego (brak static_stat_modifier w exhausted)
    assert _combatant_stat_modifier(sheet, sheet=None, stat="STR") == 2


# ── PT-F5 #1139: fatigue penalty reaches ATTACK rolls (not only skill tests) ───

def test_ptf5_attack_roll_reduced_by_fatigue():
    """PT-F5: an exhausted hero swings less accurately — attack total drops by the
    fatigue penalty, as a distinct term (stat modifier itself untouched)."""
    from app.services.weapon_rules import resolve_attack_roll_for_weapon
    weapon = {"key": "sword", "label": "Miecz", "weapon_type": "melee"}
    base_sheet = {"stats": {"STR": 14}, "skills": {}, "conditions": []}
    tired_sheet = {**base_sheet, "conditions": [_exhausted(2)]}  # -2 test penalty

    base = resolve_attack_roll_for_weapon(base_sheet, raw_roll=10, weapon_row=weapon)
    tired = resolve_attack_roll_for_weapon(tired_sheet, raw_roll=10, weapon_row=weapon)

    assert base.get("fatigue_penalty", 0) == 0
    assert tired["fatigue_penalty"] == -2, "2 fatigue stacks -> -2 to attack"
    assert tired["total"] == base["total"] - 2, "attack total must drop by the fatigue penalty"
    assert tired["stat_mod"] == base["stat_mod"], "stat modifier itself must be unchanged (locked formula)"


def test_ptf5_dwarf_ignores_first_stack_on_attack():
    """PT-F5: dwarf 'twardy jak kamień' ignores the 1st stack on attack too (race-wide, as decided)."""
    from app.services.weapon_rules import resolve_attack_roll_for_weapon
    weapon = {"key": "axe", "label": "Topór", "weapon_type": "melee"}
    dwarf = {"stats": {"STR": 14}, "skills": {}, "race": "dwarf", "conditions": [_exhausted(1)]}
    human = {"stats": {"STR": 14}, "skills": {}, "race": "human", "conditions": [_exhausted(1)]}
    assert resolve_attack_roll_for_weapon(dwarf, raw_roll=10, weapon_row=weapon)["fatigue_penalty"] == 0
    assert resolve_attack_roll_for_weapon(human, raw_roll=10, weapon_row=weapon)["fatigue_penalty"] == -1
