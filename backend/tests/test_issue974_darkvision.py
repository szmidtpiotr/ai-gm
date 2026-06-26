"""TDD: Issue #974 — Wzrok górnika / darkvision (dungeon engine FAZA L)."""
import sys
sys.path.insert(0, "/app")

from app.services.dungeon_service import (
    get_darkvision_bonus,
    DWARF_DARKVISION_BONUS,
    HUMAN_DARKNESS_PENALTY,
)


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_darkvision_constants_exist():
    """Stałe darkvision muszą istnieć."""
    assert DWARF_DARKVISION_BONUS == 3, f"Oczekiwano 3, jest {DWARF_DARKVISION_BONUS}"
    assert HUMAN_DARKNESS_PENALTY == -4, f"Oczekiwano -4, jest {HUMAN_DARKNESS_PENALTY}"


def test_darkvision_bonus_outside_dungeon_is_zero():
    """Poza lochami darkvision = 0 dla obu ras."""
    result = get_darkvision_bonus(999999, is_dungeon=False)
    assert result["perception_bonus"] == 0
    assert result["darkness_penalty"] == 0


def test_human_darkness_penalty_in_dungeon():
    """Człowiek ma malus w ciemności dungeon."""
    # Użyj fikcyjnego character_id — fallback 'human'
    result = get_darkvision_bonus(999999, is_dungeon=True)
    assert result["darkness_penalty"] == HUMAN_DARKNESS_PENALTY, (
        f"Człowiek powinien mieć karę {HUMAN_DARKNESS_PENALTY}, jest {result['darkness_penalty']}"
    )
    assert result["perception_bonus"] == 0


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_get_darkvision_bonus_returns_dict_with_required_keys():
    """get_darkvision_bonus zawsze zwraca dict z wymaganymi kluczami."""
    result = get_darkvision_bonus(1, is_dungeon=True)
    assert "perception_bonus" in result
    assert "darkness_penalty" in result
    assert "race" in result
