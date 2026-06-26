"""TDD: Issue #975 — Rdzeń-magia krasnoludów (miscast flavor + exkluzywne czary)."""
import sys
sys.path.insert(0, "/app")

from app.services.spell_service import (
    is_miscast,
    resolve_miscast,
    resolve_dwarf_spell_side_effect,
    DWARF_MISCAST_THRESHOLD,
    DWARF_SCHOLAR_STARTING_SPELLS,
    HUMAN_SCHOLAR_STARTING_SPELLS,
)


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_dwarf_miscast_threshold_is_2():
    assert DWARF_MISCAST_THRESHOLD == 2


def test_human_miscast_only_nat1():
    """Człowiek: miscast tylko na Nat 1."""
    assert is_miscast(1, "human") is True
    assert is_miscast(2, "human") is False
    assert is_miscast(10, "human") is False


def test_dwarf_miscast_nat1_and_nat2():
    """Krasnolud: miscast na Nat 1 i Nat 2."""
    assert is_miscast(1, "dwarf") is True
    assert is_miscast(2, "dwarf") is True
    assert is_miscast(3, "dwarf") is False
    assert is_miscast(10, "dwarf") is False


def test_dwarf_miscast_narrative_different():
    """Krasnolud miscast ma inny opis niż ludzki."""
    sheet = {"level": 1, "current_hp": 20}
    human_res = resolve_miscast(sheet.copy(), {}, None, race="human")
    dwarf_res = resolve_miscast(sheet.copy(), {}, None, race="dwarf")
    assert human_res["narrative"] != dwarf_res["narrative"], (
        "Krasnolud i człowiek powinni mieć różne opisy miscastu"
    )
    assert dwarf_res.get("rdzen_miscast") is True
    assert human_res.get("rdzen_miscast") is False


def test_dwarf_spell_side_effect_returns_string():
    """Efekt uboczny czaru krasnoludzkiego = niepusty string."""
    result = resolve_dwarf_spell_side_effect("vein_tremor")
    assert isinstance(result, str) and len(result) > 0


def test_no_side_effect_for_unknown_spell():
    """Nieznany klucz czaru = brak efektu ubocznego."""
    result = resolve_dwarf_spell_side_effect("unknown_human_spell")
    assert result == ""


def test_dwarf_starting_spells_are_rdzen():
    """Krasnolud startuje z czarami Rdzenia, nie z ludzkimi."""
    assert "vein_tremor" in DWARF_SCHOLAR_STARTING_SPELLS
    assert "rdzen_shield" in DWARF_SCHOLAR_STARTING_SPELLS
    # Ludzkie czary niedostępne w startowym zestawie
    assert "fire_bolt" not in DWARF_SCHOLAR_STARTING_SPELLS
    assert "magic_bolt" not in DWARF_SCHOLAR_STARTING_SPELLS


def test_human_starting_spells_not_rdzen():
    """Człowiek nie startuje z krasnoludzkimi czarami."""
    assert "vein_tremor" not in HUMAN_SCHOLAR_STARTING_SPELLS
    assert "rdzen_shield" not in HUMAN_SCHOLAR_STARTING_SPELLS


def test_dwarf_spells_in_db():
    """6 czarów krasnoludów musi być w game_config_spells z race_lock='dwarf'."""
    import sqlite3
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT key, race_lock FROM game_config_spells WHERE race_lock = 'dwarf'"
    ).fetchall()
    conn.close()
    keys = [r["key"] for r in rows]
    for expected in ("vein_tremor", "rdzen_pulse", "vein_bleed", "rdzen_shield", "deep_quake", "black_vein"):
        assert expected in keys, f"Brak czaru '{expected}' w DB z race_lock='dwarf'. Dostępne: {keys}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_is_miscast_no_race_defaults_human():
    """is_miscast bez race = human (tylko Nat 1)."""
    assert is_miscast(1) is True
    assert is_miscast(2) is False
