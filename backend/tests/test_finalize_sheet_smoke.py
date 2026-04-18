"""Smoke tests for finalize-sheet helpers + generate-identity models (no DB).

Run: pytest backend/tests/test_finalize_sheet_smoke.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.characters import (  # noqa: E402
    FinalizeSheetRequest,
    GeneratedIdentityPreview,
    IdentityOverrideIn,
    LOCKED_SKILL_NAMES,
    _apply_skill_replacements,
    _build_character_sheet,
    _core_bases_from_stored_stats,
    _skill_rank_total,
    _stat_modifier,
)


class TestFinalizeHelpers:
    def test_core_bases_warrior_strips_bonuses(self):
        stored = {"STR": 14, "DEX": 10, "CON": 11, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10}
        bases = _core_bases_from_stored_stats(stored, "warrior")
        assert bases["STR"] == 12
        assert bases["CON"] == 10

    def test_core_bases_mage_strips_bonuses(self):
        stored = {"STR": 10, "DEX": 10, "CON": 10, "INT": 14, "WIS": 11, "CHA": 10, "LCK": 10}
        bases = _core_bases_from_stored_stats(stored, "mage")
        assert bases["INT"] == 12
        assert bases["WIS"] == 10

    def test_skill_replacement_moves_rank_preserves_total(self):
        sk = {k: 0 for k in LOCKED_SKILL_NAMES}
        sk["athletics"] = 3
        sk["stealth"] = 0
        sk["arcana"] = 1
        swaps = [{"from_skill": "athletics", "to_skill": "stealth"}]
        out = _apply_skill_replacements(sk, swaps)
        assert out["athletics"] == 0
        assert out["stealth"] == 3
        assert _skill_rank_total(sk) == _skill_rank_total(out)

    def test_skill_replacement_to_alchemy(self):
        sk = {k: 0 for k in LOCKED_SKILL_NAMES}
        sk["lore"] = 2
        out = _apply_skill_replacements(sk, [{"from_skill": "lore", "to_skill": "alchemy"}])
        assert out["lore"] == 0
        assert out["alchemy"] == 2

    def test_build_sheet_recomputes_modifiers_hp_defense(self):
        sheet = {
            "archetype": "warrior",
            "stats": {"STR": 12, "DEX": 14, "CON": 13, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
            "skills": {"athletics": 2},
        }
        built = _build_character_sheet(sheet, "warrior", apply_archetype_skill_minimums=False)
        assert built["stats"]["STR"] == 14  # +2 warrior
        dex = built["stats"]["DEX"]
        assert built["stat_modifiers"]["DEX"] == _stat_modifier(dex)
        assert built["defense"]["base"] == 10 + built["stat_modifiers"]["DEX"]
        con_mod = built["stat_modifiers"]["CON"]
        assert built["max_hp"] == 12 + con_mod

    def test_build_sheet_preserves_death_save_failures(self):
        sheet = {
            "archetype": "warrior",
            "death_save_failures": 2,
            "stats": {"STR": 12, "DEX": 14, "CON": 13, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
            "skills": {"athletics": 2},
        }
        built = _build_character_sheet(sheet, "warrior", apply_archetype_skill_minimums=False)
        assert built.get("death_save_failures") == 2


class TestPydanticContracts:
    def test_finalize_request_empty_body(self):
        r = FinalizeSheetRequest()
        assert r.stat_overrides is None
        assert r.skill_swaps is None
        assert r.identity_overrides is None

    def test_identity_override_ignores_extra_keys(self):
        io = IdentityOverrideIn.model_validate(
            {"appearance": "a", "personality": "p", "flaw": "x", "secret": "y"}
        )
        assert io.appearance == "a"
        assert io.personality == "p"

    def test_generated_identity_preview_import(self):
        p = GeneratedIdentityPreview(
            appearance="1", personality="2", flaw="3", bond="4", secret="5"
        )
        assert p.flaw == "3"

