"""Issue #1474 — cechy rasowe elfa: knieja, zmierzchowy wzrok, zniknięcie w kniei.

Warstwa czysto funkcyjna (helpery `elf_traits_service`) + limit 1/dobę na
zniknięcie liczony po zegarze kampanii. Odskok ma własny plik testów.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import elf_traits_service as elf


# ─── Rozpoznanie terenu ──────────────────────────────────────────────────────

@pytest.mark.parametrize("hex_type", [
    "forest", "forest_dense", "swamp", "swamp_bog", "marsh", "wood", "grove", "FOREST",
])
def test_home_terrain_recognised(hex_type):
    assert elf.is_wild_home_terrain(hex_type) is True


@pytest.mark.parametrize("hex_type", ["plains", "mountain", "tundra", "ruins", "city", "", None])
def test_foreign_terrain_not_home(hex_type):
    assert elf.is_wild_home_terrain(hex_type) is False


# ─── Knieja pod stopami ──────────────────────────────────────────────────────

@pytest.mark.parametrize("skill", ["stealth", "survival", "perception", "awareness", "tracking"])
def test_terrain_bonus_for_wild_skills(skill):
    assert elf.wild_terrain_bonus("elf", skill, "forest") == elf.ELF_WILD_TERRAIN_BONUS


def test_terrain_bonus_only_in_home_terrain():
    assert elf.wild_terrain_bonus("elf", "stealth", "mountain") == 0
    assert elf.wild_terrain_bonus("elf", "stealth", "") == 0


def test_terrain_bonus_only_for_wild_skills():
    assert elf.wild_terrain_bonus("elf", "persuasion", "forest") == 0
    assert elf.wild_terrain_bonus("elf", "arcana", "swamp") == 0


def test_terrain_bonus_only_for_elves():
    assert elf.wild_terrain_bonus("human", "stealth", "forest") == 0
    assert elf.wild_terrain_bonus("dwarf", "survival", "swamp") == 0
    assert elf.wild_terrain_bonus(None, "stealth", "forest") == 0


def test_starting_value_is_documented():
    assert elf.ELF_WILD_TERRAIN_BONUS == 2
    assert elf.ELF_VANISH_USES_PER_DAY == 1


# ─── Zmierzchowy wzrok ───────────────────────────────────────────────────────

def test_twilight_sight_cancels_night_perception_penalty():
    # #1463 nocą podbija DC percepcji o 2 — elfowi zdejmujemy dokładnie tyle.
    assert elf.twilight_sight_offset("elf", "perception", 2) == 2
    assert elf.twilight_sight_offset("elf", "awareness", 1) == 1


def test_twilight_sight_never_gives_daylight_bonus():
    """W dzień nie ma czego znosić — elf nie widzi LEPIEJ niż inni."""
    assert elf.twilight_sight_offset("elf", "perception", 0) == 0


def test_twilight_sight_is_race_and_skill_gated():
    assert elf.twilight_sight_offset("human", "perception", 2) == 0
    assert elf.twilight_sight_offset("elf", "stealth", 2) == 0


# ─── Zniknięcie w kniei ──────────────────────────────────────────────────────

def _sessions_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE game_sessions (campaign_id INTEGER PRIMARY KEY, session_flags TEXT)")
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, ?)",
        (json.dumps({"current_hex": {"q": 1, "r": 2}}),),
    )
    conn.commit()
    return conn


def test_vanish_available_in_forest_and_consumed_once_per_day():
    conn = _sessions_conn()
    try:
        with patch.object(elf, "_ingame_day", return_value=3):
            assert elf.vanish_available(conn, 1, "elf", "forest") is True
            elf.consume_vanish(conn, 1)
            assert elf.vanish_available(conn, 1, "elf", "forest") is False
            # Kolejna doba gry — atut wraca.
            with patch.object(elf, "_ingame_day", return_value=4):
                assert elf.vanish_available(conn, 1, "elf", "forest") is True
    finally:
        conn.close()


def test_vanish_blocked_outside_wild_terrain():
    conn = _sessions_conn()
    try:
        assert elf.vanish_available(conn, 1, "elf", "city") is False
        assert elf.vanish_available(conn, 1, "elf", "mountain") is False
    finally:
        conn.close()


def test_vanish_is_elf_only():
    conn = _sessions_conn()
    try:
        assert elf.vanish_available(conn, 1, "human", "forest") is False
        assert elf.vanish_available(conn, 1, "dwarf", "forest") is False
    finally:
        conn.close()


# ─── Odczyt heksa ────────────────────────────────────────────────────────────

def test_current_hex_type_reads_world_hexes():
    conn = _sessions_conn()
    try:
        conn.execute(
            "CREATE TABLE world_hexes (q INTEGER, r INTEGER, map_level INTEGER, hex_type TEXT)"
        )
        conn.execute("INSERT INTO world_hexes (q, r, map_level, hex_type) VALUES (1,2,0,'Forest')")
        conn.commit()
        assert elf.current_hex_type(conn, 1) == "forest"
    finally:
        conn.close()


def test_current_hex_type_survives_missing_data():
    """Brak tabeli / brak heksa nie może wywrócić testu umiejętności."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        assert elf.current_hex_type(conn, 1) == ""
    finally:
        conn.close()
