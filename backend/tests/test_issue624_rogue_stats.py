"""TDD: Issue #624 (B1) — Rogue dostaje DEX+2/LCK+1, nie INT+2/WIS+1."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.characters import _build_character_sheet, _core_bases_from_stored_stats

BASE_STATS = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10}


def _build(archetype):
    return _build_character_sheet({"stats": dict(BASE_STATS), "level": 1}, archetype)


# ─── Test główny: łotrzyk = DEX+2/LCK+1 ──────────────────────────────────────

def test_rogue_gets_dex_and_lck_bonus():
    """Łotrzyk: DEX+2 i LCK+1 (canon AK.2), zgodnie z obietnicą kreatora."""
    sheet = _build("rogue")
    stats = sheet["stats"]
    assert stats["DEX"] == 12, f"rogue DEX powinno być 12 (10+2), jest {stats['DEX']}"
    assert stats["LCK"] == 11, f"rogue LCK powinno być 11 (10+1), jest {stats['LCK']}"


def test_rogue_does_not_get_mage_stats():
    """Łotrzyk NIE dostaje bonusów maga (INT/WIS) — to był bug #624."""
    stats = _build("rogue")["stats"]
    assert stats["INT"] == 10, f"rogue INT nie powinno mieć bonusu, jest {stats['INT']}"
    assert stats["WIS"] == 10, f"rogue WIS nie powinno mieć bonusu, jest {stats['WIS']}"


def test_rogue_skill_minimums_are_thief_oriented():
    """Łotrzyk dostaje minimalne ranki złodziejskie, nie magowskie."""
    skills = _build("rogue")["skills"]
    assert skills.get("stealth", 0) >= 2
    assert skills.get("sleight_of_hand", 0) >= 2
    assert skills.get("awareness", 0) >= 1
    # NIE forsuje skilli maga
    assert skills.get("arcana", 0) == 0
    assert skills.get("spell_attack", 0) == 0


def test_rogue_core_bases_reverse():
    """Odwrotność: redystrybucja statów łotrzyka odejmuje DEX-2/LCK-1, nie INT/WIS."""
    stored = {"STR": 10, "DEX": 12, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 11}
    bases = _core_bases_from_stored_stats(stored, "rogue")
    assert bases["DEX"] == 10, f"baza DEX po odjęciu bonusu = 10, jest {bases['DEX']}"
    assert bases["LCK"] == 10, f"baza LCK po odjęciu bonusu = 10, jest {bases['LCK']}"
    assert bases["INT"] == 10 and bases["WIS"] == 10


# ─── Backward compatibility: warrior i scholar bez zmian ─────────────────────

def test_warrior_stats_unchanged():
    stats = _build("warrior")["stats"]
    assert stats["STR"] == 12 and stats["CON"] == 11
    assert stats["DEX"] == 10 and stats["LCK"] == 10


def test_scholar_stats_unchanged():
    stats = _build("scholar")["stats"]
    assert stats["INT"] == 12 and stats["WIS"] == 11
    assert stats["DEX"] == 10 and stats["LCK"] == 10


def test_scholar_core_bases_reverse_unchanged():
    stored = {"STR": 10, "DEX": 10, "CON": 10, "INT": 12, "WIS": 11, "CHA": 10, "LCK": 10}
    bases = _core_bases_from_stored_stats(stored, "scholar")
    assert bases["INT"] == 10 and bases["WIS"] == 10
