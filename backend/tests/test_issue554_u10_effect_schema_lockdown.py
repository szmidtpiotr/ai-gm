"""TDD: Issue #554 — U10 Effect schema lockdown (decyzja C: hybryda).

Zakres:
- effect_schema.json jako pojedyncze źródło prawdy (walidator czyta z niego enumy).
- Enum statów rozszerzony o LCK + cele pochodne ac/attack_bonus/damage_bonus/initiative.
- NIE zmieniamy nazw typów (zostaje periodic_save/static_stat_modifier/block_action).
- Walidacja nadal odrzuca śmieci, przyjmuje poprawny format (backward compat).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import admin_config as ac


# ─── helpers ──────────────────────────────────────────────────────────────────

def _stat_mod_payload(stat, value=-1, category="character_condition"):
    return {
        "schema_version": 1,
        "effect_category": category,
        "effects": [{"type": "static_stat_modifier", "stat": stat, "value": value}],
    }


# ─── Test główny — nowy enum statów ───────────────────────────────────────────

class TestStatEnumExtended:
    def test_lck_is_accepted(self):
        """LCK (7. statystyka) musi być dozwolona — dziś brak (CLAUDE.md wymaga 7)."""
        errors = ac.validate_effect_json_payload(_stat_mod_payload("LCK"))
        assert errors == [], f"LCK powinno przejść walidację, błędy: {errors}"

    @pytest.mark.parametrize("target", ["ac", "attack_bonus", "damage_bonus", "initiative"])
    def test_derived_stat_targets_accepted(self, target):
        """Cele pochodne (intencja U10) dozwolone jako stat dla static_stat_modifier."""
        errors = ac.validate_effect_json_payload(
            _stat_mod_payload(target, value=2, category="gear_bonus")
        )
        assert errors == [], f"{target} powinno przejść walidację, błędy: {errors}"

    def test_unknown_stat_still_rejected(self):
        """Losowy stat dalej odrzucany — lockdown trzyma."""
        errors = ac.validate_effect_json_payload(_stat_mod_payload("FOO"))
        assert any("stat" in e for e in errors), f"FOO powinno być odrzucone, błędy: {errors}"


# ─── Test — effect_schema.json jest pojedynczym źródłem prawdy ─────────────────

class TestSchemaFileSingleSource:
    def test_schema_file_exists(self):
        path = Path(ac.__file__).resolve().parent.parent / "schemas" / "effect_schema.json"
        assert path.exists(), f"brak pliku schematu: {path}"

    def test_schema_file_drives_stats_enum(self):
        """Enumy w walidatorze pochodzą z pliku (single source)."""
        path = Path(ac.__file__).resolve().parent.parent / "schemas" / "effect_schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        # base stats z pliku == runtime
        assert set(schema["stats"]) == set(ac.ALLOWED_EFFECT_JSON_STATS)
        # typy efektów z pliku == runtime
        assert set(schema["effect_types"]) == set(ac.ALLOWED_EFFECT_JSON_TYPES)
        # kategorie z pliku == runtime
        assert set(schema["categories"]) == set(ac.ALLOWED_EFFECT_JSON_CATEGORIES)

    def test_lck_present_in_schema_file(self):
        path = Path(ac.__file__).resolve().parent.parent / "schemas" / "effect_schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert "LCK" in schema["stats"]


# ─── Decyzja C — nazwy spec NIE są przyjmowane (nie zrobiliśmy rename) ─────────

class TestNoSpecRename:
    @pytest.mark.parametrize("spec_type", ["damage_over_time", "stat_mod", "skip_turn"])
    def test_spec_type_names_rejected(self, spec_type):
        payload = {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [{"type": spec_type}],
        }
        errors = ac.validate_effect_json_payload(payload)
        assert any("type" in e for e in errors), (
            f"{spec_type} NIE powinno być rozpoznane (decyzja C — zostają nazwy z kodu)"
        )


# ─── Backward compatibility ───────────────────────────────────────────────────

class TestBackwardCompat:
    def test_str_static_stat_modifier_still_valid(self):
        errors = ac.validate_effect_json_payload(_stat_mod_payload("STR"))
        assert errors == [], errors

    def test_periodic_save_still_valid(self):
        payload = {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [
                {"type": "periodic_save", "tick": "start_turn", "expires": "save_success", "value": 3}
            ],
        }
        assert ac.validate_effect_json_payload(payload) == []

    def test_heal_hp_dice_still_valid(self):
        payload = {
            "schema_version": 1,
            "effect_category": "consumable_immediate",
            "effects": [{"type": "heal_hp", "value": "2d4"}],
        }
        assert ac.validate_effect_json_payload(payload) == []

    def test_bad_schema_version_still_rejected(self):
        payload = {"schema_version": 2, "effect_category": "aura", "effects": [{"type": "narrative_only"}]}
        errors = ac.validate_effect_json_payload(payload)
        assert any("schema_version" in e for e in errors)

    def test_non_dict_rejected(self):
        assert ac.validate_effect_json_payload("nope")
