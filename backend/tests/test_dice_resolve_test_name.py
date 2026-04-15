"""Tests for Task 7.3 — resolve_test_name()

Runs without any external deps. Execute with:
 pytest backend/tests/test_dice_resolve_test_name.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.dice import resolve_test_name


# ---------------------------------------------------------------------------
# Known valid skill names (direct match, Phase 5.5 locked list)
# ---------------------------------------------------------------------------
class TestDirectSkillNames:
    def test_athletics(self):
        assert resolve_test_name("Athletics") == "athletics"

    def test_stealth(self):
        assert resolve_test_name("Stealth") == "stealth"

    def test_awareness(self):
        assert resolve_test_name("Awareness") == "awareness"

    def test_survival(self):
        assert resolve_test_name("Survival") == "survival"

    def test_lore(self):
        assert resolve_test_name("Lore") == "lore"

    def test_investigation(self):
        assert resolve_test_name("Investigation") == "investigation"

    def test_arcana(self):
        assert resolve_test_name("Arcana") == "arcana"

    def test_medicine(self):
        assert resolve_test_name("Medicine") == "medicine"

    def test_persuasion(self):
        assert resolve_test_name("Persuasion") == "persuasion"

    def test_intimidation(self):
        assert resolve_test_name("Intimidation") == "intimidation"

    def test_melee_attack(self):
        assert resolve_test_name("Melee Attack") == "melee_attack"

    def test_ranged_attack(self):
        assert resolve_test_name("Ranged Attack") == "ranged_attack"

    def test_spell_attack(self):
        assert resolve_test_name("Spell Attack") == "spell_attack"


# ---------------------------------------------------------------------------
# Save names (direct match)
# ---------------------------------------------------------------------------
class TestDirectSaveNames:
    def test_fortitude_save(self):
        assert resolve_test_name("Fortitude Save") == "fortitude_save"

    def test_reflex_save(self):
        assert resolve_test_name("Reflex Save") == "reflex_save"

    def test_willpower_save(self):
        assert resolve_test_name("Willpower Save") == "willpower_save"

    def test_arcane_save(self):
        assert resolve_test_name("Arcane Save") == "arcane_save"


# ---------------------------------------------------------------------------
# LLM aliases — common hallucinated names that must map to canonical names
# ---------------------------------------------------------------------------
class TestAliases:
    def test_str_save(self):
        assert resolve_test_name("Str Save") == "fortitude_save"

    def test_con_save(self):
        assert resolve_test_name("Con Save") == "fortitude_save"

    def test_dex_save(self):
        assert resolve_test_name("Dex Save") == "reflex_save"

    def test_wis_save(self):
        assert resolve_test_name("Wis Save") == "willpower_save"

    def test_int_save(self):
        assert resolve_test_name("Int Save") == "arcane_save"

    def test_cha_save(self):
        assert resolve_test_name("Cha Save") == "willpower_save"

    def test_perception_maps_to_awareness(self):
        assert resolve_test_name("Perception") == "awareness"

    def test_attack_maps_to_melee_attack(self):
        assert resolve_test_name("Attack") == "melee_attack"

    def test_initiative_maps_to_reflex_save(self):
        assert resolve_test_name("Initiative") == "reflex_save"


# ---------------------------------------------------------------------------
# Case / whitespace tolerance
# ---------------------------------------------------------------------------
class TestNormalisation:
    def test_lowercase_input(self):
        assert resolve_test_name("stealth") == "stealth"

    def test_uppercase_input(self):
        assert resolve_test_name("STEALTH") == "stealth"

    def test_mixed_case(self):
        assert resolve_test_name("sTrEnGtH SaVe") is None  # not a real name

    def test_extra_whitespace(self):
        assert resolve_test_name(" Stealth ") == "stealth"

    def test_internal_extra_space(self):
        # double space between words — should still resolve
        assert resolve_test_name("Str Save") == "fortitude_save"


# ---------------------------------------------------------------------------
# Unknown / invalid names — must return None (no crash)
# ---------------------------------------------------------------------------
class TestUnknownNames:
    def test_unknown_returns_none(self):
        assert resolve_test_name("FlyingKick") is None

    def test_agility_returns_none(self):
        assert resolve_test_name("Agility") is None

    def test_empty_string_returns_none(self):
        assert resolve_test_name("") is None

    def test_none_input_returns_none(self):
        assert resolve_test_name(None) is None

    def test_random_text_returns_none(self):
        assert resolve_test_name("SomeMadeUpSkill d20") is None
