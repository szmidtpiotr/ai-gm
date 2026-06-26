"""TDD: Issue #972 — Twardy jak kamień: redukcja obrażeń trucizna/mrok dla krasnoludów."""
import sys
sys.path.insert(0, "/app")

from app.services.combat_service import apply_defense_model


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_dwarf_poison_damage_reduced():
    """Krasnolud: trucizna −2 dmg (min 1)."""
    result_human = apply_defense_model(5, 15, 10, ignore_armor=True, race="human", damage_type="poison")
    result_dwarf = apply_defense_model(5, 15, 10, ignore_armor=True, race="dwarf", damage_type="poison")
    assert result_dwarf["final"] == result_human["final"] - 2, (
        f"Krasnolud powinien dostać o 2 mniej trucizny: human={result_human['final']}, dwarf={result_dwarf['final']}"
    )


def test_dwarf_dark_damage_reduced():
    """Krasnolud: mrok −2 dmg (bez margin bonus — attack==defense)."""
    result_dwarf = apply_defense_model(4, 10, 10, ignore_armor=True, race="dwarf", damage_type="dark")
    assert result_dwarf["final"] == 2, f"Oczekiwano 2, jest {result_dwarf['final']}"


def test_dwarf_rdzen_damage_reduced():
    """Krasnolud: skażenie Rdzenia −2 dmg."""
    result_dwarf = apply_defense_model(6, 10, 10, ignore_armor=True, race="dwarf", damage_type="rdzen")
    assert result_dwarf["final"] == 4, f"Oczekiwano 4, jest {result_dwarf['final']}"


def test_dwarf_toughness_min_1():
    """Redukcja nie schodzi poniżej 1 (min 1 obrażeń)."""
    result_dwarf = apply_defense_model(1, 15, 10, ignore_armor=True, race="dwarf", damage_type="poison")
    assert result_dwarf["final"] == 1, "Minimalne obrażenia to 1"


def test_dwarf_physical_damage_normal():
    """Krasnolud: fizyczne obrażenia bez zmiany."""
    result_human = apply_defense_model(5, 15, 10, ignore_armor=True, race="human", damage_type="physical")
    result_dwarf = apply_defense_model(5, 15, 10, ignore_armor=True, race="dwarf", damage_type="physical")
    assert result_dwarf["final"] == result_human["final"], "Fizyczne obrażenia nie powinny być redukowane"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_apply_defense_model_no_race_arg_still_works():
    """apply_defense_model bez race/damage_type — zachowanie bez zmian."""
    result = apply_defense_model(5, 15, 10, ignore_armor=False)
    assert "final" in result
    assert result["final"] >= 1
