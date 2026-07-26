"""Issue #1475 — Piętnowani: rdzeń rasy (staty, bramka archetypu, kraina, start).

Zakres tego pliku = warstwa „rasa istnieje i jest spójna":
  * modyfikatory rasowe INT +2 / WIS +1 / CON −1,
  * Wojownik i Łotrzyk zamknięte (droga rasy = Uczony albo Wojownik-Mag),
  * kraina ojczysta = Martwe Pustkowia (status `live`, MP-1..MP-7) → rasa jest
    publicznie grywalna, bez bramki testera (inaczej niż elf startowo),
  * kotwica startowa = Solny Próg (Gospoda dla Obcych default), bo hub istnieje
    w `game_locations` na heksie 64,37 i region ma 2500 heksów.

Wojownik-Mag (gish archetyp), cechy rasowe (Oswojony Rdzeń, Piętno, magia krwi)
i pula czarów mają własne pliki testów (PN-2 / PN-3).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import race_start_service as rss
from app.services.actor_stats import RACIAL_STAT_MODS, apply_racial_modifiers
from app.services.combat_service import ZONE_RANGED, _default_zone_for_player
from app.services.world_region_service import (
    RACE_HOME_REGION,
    RACE_LABELS,
    race_availability,
)


# ─── Staty rasowe ────────────────────────────────────────────────────────────

def test_pietnowani_stat_modifiers():
    assert RACIAL_STAT_MODS["pietnowani"] == {"INT": +2, "WIS": +1, "CON": -1}


def test_apply_racial_modifiers_pietnowani():
    sheet = {"stats": {"STR": 10, "DEX": 10, "CON": 12, "INT": 12, "WIS": 10, "CHA": 10, "LCK": 10}}
    out = apply_racial_modifiers(sheet, "pietnowani")
    assert out["stats"]["INT"] == 14
    assert out["stats"]["WIS"] == 11
    assert out["stats"]["CON"] == 11
    # Reszta nietknięta — modyfikator dotyka tylko trzech cech.
    assert out["stats"]["STR"] == 10 and out["stats"]["DEX"] == 10


def test_other_races_unchanged():
    """Zero regresji na istniejących rasach."""
    assert RACIAL_STAT_MODS["human"] == {}
    assert RACIAL_STAT_MODS["dwarf"] == {"CON": +2, "STR": +1, "CHA": -1, "DEX": -1}
    assert RACIAL_STAT_MODS["elf"] == {"DEX": +2, "WIS": +1, "CON": -1}


# ─── Bramka archetypu ────────────────────────────────────────────────────────

@pytest.mark.parametrize("arch", ["warrior", "rogue"])
def test_pietnowani_cannot_be_warrior_or_rogue(arch):
    assert rss.archetype_allowed("pietnowani", arch) is False
    reason = rss.archetype_block_reason("pietnowani", arch)
    assert reason and "Wojownik-Mag" in reason


def test_pietnowani_can_be_scholar():
    assert rss.archetype_allowed("pietnowani", "scholar") is True


def test_blocked_list_for_creator():
    assert rss.blocked_archetypes_for_race("pietnowani") == ["warrior", "rogue"]
    # Pozostałe rasy bez zmian.
    assert rss.blocked_archetypes_for_race("elf") == ["warrior"]
    assert rss.blocked_archetypes_for_race("dwarf") == ["rogue"]
    assert rss.blocked_archetypes_for_race("human") == []


# ─── Kraina ojczysta i dostępność ────────────────────────────────────────────

def test_pietnowani_home_region_is_martwe_pustkowia():
    assert RACE_HOME_REGION["pietnowani"] == "martwe_pustkowia"
    assert RACE_LABELS["pietnowani"] == "Piętnowany"


def _regions_conn(status: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE world_regions (key TEXT PRIMARY KEY, label TEXT, status TEXT)")
    conn.execute(
        "INSERT INTO world_regions (key, label, status) VALUES ('martwe_pustkowia','Martwe Pustkowia',?)",
        (status,),
    )
    conn.commit()
    return conn


def _entry(rows: list[dict], key: str) -> dict:
    return next(r for r in rows if r["key"] == key)


def test_pietnowani_open_for_everyone_when_region_is_live():
    """MP jest `live` (MP-1..MP-7), więc Piętnowany jest publicznie grywalny."""
    conn = _regions_conn("live")
    try:
        pn = _entry(race_availability(conn, include_coming=False), "pietnowani")
        assert pn["available"] is True
        assert pn["blocked_archetypes"] == ["warrior", "rogue"]
    finally:
        conn.close()


def test_pietnowani_locked_for_normal_player_if_region_were_coming():
    """Bramka spójna z resztą ras — gdyby MP było `coming`, tylko tester wchodzi."""
    conn = _regions_conn("coming")
    try:
        pn = _entry(race_availability(conn, include_coming=False), "pietnowani")
        assert pn["available"] is False
        assert "Martwe Pustkowia" in (pn["reason"] or "")
        tester = _entry(race_availability(conn, include_coming=True), "pietnowani")
        assert tester["available"] is True
    finally:
        conn.close()


# ─── Start kampanii ──────────────────────────────────────────────────────────

def test_pietnowani_start_anchor_is_solny_prog():
    spec = rss.RACE_START["pietnowani"]
    assert spec["region"] == "martwe_pustkowia"
    assert spec["default"] == "solny_prog_gospoda"
    assert set(spec["variants"]) == {"solny_prog_gospoda", "solny_prog_dom_starszych"}


def test_pietnowani_plan_hint_carries_lore_hooks():
    """Plan-hint niesie haki: Raszid (enklawa) vs Verena (Misja Światła)."""
    hint = rss.RACE_PLAN_HINT["pietnowani"]
    assert "Martwe Pustkowia" in hint
    assert "Solny Próg" in hint
    assert "Raszid" in hint
    assert "Verena" in hint


# ─── Strefa startowa walki ───────────────────────────────────────────────────

def test_pietnowani_scholar_starts_at_range():
    assert _default_zone_for_player({"archetype": "scholar"}, "pietnowani") == ZONE_RANGED
