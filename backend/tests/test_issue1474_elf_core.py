"""Issue #1474 — elf leśny: rdzeń rasy (staty, bramka archetypu, kraina, strefa startu).

Zakres tego pliku = warstwa „rasa istnieje i jest spójna":
  * modyfikatory rasowe DEX +2 / WIS +1 / CON −1,
  * Wojownik zamknięty dla elfa (backend jest bramką, nie UI),
  * kraina ojczysta = Czarnobór → dopóki region ma status `coming`, rasa jest
    dostępna wyłącznie dla testera (ta sama bramka co #1478/#1479),
  * elf-Zwiadowca (rogue) otwiera walkę na DYSTANSIE, nie w zwarciu,
  * brak wpisu w `RACE_START` — Czarnobór nie ma jeszcze heksów (#1489), więc elf
    startuje jak człowiek, zamiast kotwiczyć się w pustym regionie.

Cechy rasowe (odskok, zmierzchowy wzrok, zniknięcie w kniei, szkoła Stroiciela)
mają własne pliki testów.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import race_start_service as rss
from app.services.actor_stats import RACIAL_STAT_MODS, apply_racial_modifiers
from app.services.combat_service import (
    ZONE_ENGAGED,
    ZONE_RANGED,
    _default_zone_for_player,
)
from app.services.world_region_service import (
    RACE_HOME_REGION,
    RACE_LABELS,
    race_availability,
)


# ─── Staty rasowe ────────────────────────────────────────────────────────────

def test_elf_stat_modifiers():
    assert RACIAL_STAT_MODS["elf"] == {"DEX": +2, "WIS": +1, "CON": -1}


def test_apply_racial_modifiers_elf():
    sheet = {"stats": {"STR": 10, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10}}
    out = apply_racial_modifiers(sheet, "elf")
    assert out["stats"]["DEX"] == 14
    assert out["stats"]["WIS"] == 11
    assert out["stats"]["CON"] == 11
    # Reszta nietknięta — modyfikator dotyka tylko trzech cech.
    assert out["stats"]["STR"] == 10 and out["stats"]["CHA"] == 10


def test_human_and_dwarf_unchanged():
    """Zero regresji na istniejących rasach."""
    assert RACIAL_STAT_MODS["human"] == {}
    assert RACIAL_STAT_MODS["dwarf"] == {"CON": +2, "STR": +1, "CHA": -1, "DEX": -1}


# ─── Bramka archetypu ────────────────────────────────────────────────────────

def test_elf_cannot_be_warrior():
    assert rss.archetype_allowed("elf", "warrior") is False
    reason = rss.archetype_block_reason("elf", "warrior")
    assert reason and "Zwiadowca" in reason


@pytest.mark.parametrize("arch", ["rogue", "scholar"])
def test_elf_allowed_archetypes(arch):
    assert rss.archetype_allowed("elf", arch) is True


def test_blocked_list_for_creator():
    assert rss.blocked_archetypes_for_race("elf") == ["warrior"]
    # Krasnolud bez zmian (#1477).
    assert rss.blocked_archetypes_for_race("dwarf") == ["rogue"]
    assert rss.blocked_archetypes_for_race("human") == []


# ─── Kraina ojczysta i dostępność ────────────────────────────────────────────

def test_elf_home_region_is_czarnobor():
    assert RACE_HOME_REGION["elf"] == "czarnobor"
    assert RACE_LABELS["elf"] == "Elf leśny"


def _regions_conn(status: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE world_regions (key TEXT PRIMARY KEY, label TEXT, status TEXT)")
    conn.execute(
        "INSERT INTO world_regions (key, label, status) VALUES ('czarnobor','Czarnobór',?)",
        (status,),
    )
    conn.commit()
    return conn


def _entry(rows: list[dict], key: str) -> dict:
    return next(r for r in rows if r["key"] == key)


def test_elf_locked_for_normal_player_while_czarnobor_is_coming():
    conn = _regions_conn("coming")
    try:
        elf = _entry(race_availability(conn, include_coming=False), "elf")
        assert elf["available"] is False
        assert "Czarnobór" in (elf["reason"] or "")
        assert elf["blocked_archetypes"] == ["warrior"]
    finally:
        conn.close()


def test_elf_open_for_tester_while_czarnobor_is_coming():
    conn = _regions_conn("coming")
    try:
        elf = _entry(race_availability(conn, include_coming=True), "elf")
        assert elf["available"] is True
    finally:
        conn.close()


def test_elf_open_for_everyone_when_czarnobor_goes_live():
    conn = _regions_conn("live")
    try:
        elf = _entry(race_availability(conn, include_coming=False), "elf")
        assert elf["available"] is True
    finally:
        conn.close()


# ─── Start kampanii ──────────────────────────────────────────────────────────

def test_elf_start_anchor_is_czarnobor():
    """CB-8 (#1474 §9) — hub Czarnoboru istnieje, więc elf ma kotwicę startową.

    Odwrócenie `test_elf_has_no_start_anchor_yet`: whitelist startowa =
    Gościnne Drzewo (Szept Koron, default) + Ostęp Graniczny (wariant).
    """
    spec = rss.RACE_START["elf"]
    assert spec["region"] == "czarnobor"
    assert spec["default"] == "szept_goscinne_drzewo"
    assert set(spec["variants"]) == {"szept_goscinne_drzewo", "ostep_graniczny"}


def test_elf_plan_hint_carries_lore_hooks():
    """Plan-hint elfa niesie haki §9: Aerlin + spór Cathel/Nimriel."""
    hint = rss.RACE_PLAN_HINT["elf"]
    assert "Czarnobór" in hint
    assert "Gościnne Drzewo" in hint
    assert "Aerlin" in hint
    assert "Cathel" in hint and "Nimriel" in hint


# ─── Strefa startowa walki ───────────────────────────────────────────────────

def test_elf_scout_starts_at_range():
    assert _default_zone_for_player({"archetype": "rogue"}, "elf") == ZONE_RANGED


def test_human_rogue_still_starts_engaged():
    assert _default_zone_for_player({"archetype": "rogue"}, "human") == ZONE_ENGAGED
    assert _default_zone_for_player({"archetype": "rogue"}) == ZONE_ENGAGED


def test_scholar_of_any_race_starts_at_range():
    assert _default_zone_for_player({"archetype": "scholar"}, "elf") == ZONE_RANGED
    assert _default_zone_for_player({"archetype": "scholar"}, "human") == ZONE_RANGED


def test_race_can_come_from_sheet_too():
    """Rasa może przyjść argumentem albo z arkusza — obie drogi działają."""
    assert _default_zone_for_player({"archetype": "rogue", "race": "elf"}) == ZONE_RANGED
