"""Smoke tests for finalize-sheet helpers + generate-identity models (no DB).

Run: pytest backend/tests/test_finalize_sheet_smoke.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import HTTPException  # noqa: E402

from app.api.characters import (  # noqa: E402
    CREATION_SKILL_POOL,
    FinalizeSheetRequest,
    GeneratedIdentityPreview,
    IdentityOverrideIn,
    _build_character_sheet,
    _core_bases_from_stored_stats,
    _stat_modifier,
    _validate_creation_skills_after_swap,
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

    def test_skill_level_budget_swap_same_rank_costs_zero(self):
        orig = {k: 0 for k in CREATION_SKILL_POOL}
        orig["survival"] = 1
        orig["arcana"] = 0
        fin = {k: 0 for k in CREATION_SKILL_POOL}
        fin["survival"] = 0
        fin["arcana"] = 1
        assert _validate_creation_skills_after_swap(orig, fin, {"survival": "arcana"}) == 0

    def test_skill_level_budget_rank_change_costs_abs_delta(self):
        orig = {k: 0 for k in CREATION_SKILL_POOL}
        orig["athletics"] = 1
        fin = {k: 0 for k in CREATION_SKILL_POOL}
        fin["athletics"] = 2
        assert _validate_creation_skills_after_swap(orig, fin, None) == 1

    def test_skill_level_budget_rejects_orphan_rank(self):
        orig = {k: 0 for k in CREATION_SKILL_POOL}
        orig["athletics"] = 1
        orig["arcana"] = 2
        fin = {k: 0 for k in CREATION_SKILL_POOL}
        fin["athletics"] = 1
        fin["arcana"] = 2
        fin["stealth"] = 1
        with pytest.raises(HTTPException) as ei:
            _validate_creation_skills_after_swap(orig, fin, None)
        assert ei.value.status_code == 400

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
        assert r.skills is None
        assert r.skill_slot_current is None
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
