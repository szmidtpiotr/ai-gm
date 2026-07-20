"""#1477 (SG-8) — krasnolud: brak Łotrzyka + start w Siwych Graniach.

Dwie reguły pod testem:
  1. Para rasa+archetyp — krasnolud nie gra Łotrzykiem (kreator chowa kartę,
     backend odrzuca zapis 409).
  2. Kraina startowa — krasnolud ląduje w szynku „Pod Rdzawym Młotem"
     (Kamienny Gród, Siwe Granie); plan LLM może wskazać wariant z whitelisty;
     nazwa spoza whitelisty → default. Człowiek nie dostaje kotwicy.
"""
import sqlite3

import pytest

from app.services.race_start_service import (
    RACE_START,
    archetype_allowed,
    archetype_block_reason,
    blocked_archetypes_for_race,
    race_plan_hint,
    resolve_race_start,
)


@pytest.fixture()
def conn():
    """Mini-świat: Kamienny Gród (hub + szynk) + 2 warianty whitelisty."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, race TEXT, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE game_locations (
            key TEXT PRIMARY KEY, label TEXT, location_type TEXT, parent_key TEXT,
            world_hex_q INTEGER, world_hex_r INTEGER, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE world_hexes (
            q INTEGER, r INTEGER, map_level INTEGER DEFAULT 0, hex_type TEXT,
            label TEXT, is_active INTEGER DEFAULT 1
        );
        """
    )
    c.executemany(
        "INSERT INTO game_locations (key,label,location_type,parent_key,world_hex_q,world_hex_r) "
        "VALUES (?,?,?,?,?,?)",
        [
            ("kamienny_grod", "Kamienny Gród", "macro", None, 16, -17),
            ("grod_pod_rdzawym_mlotem", "Kamienny Gród: Pod Rdzawym Młotem", "sub",
             "kamienny_grod", None, None),
            ("karawanseraj_na_trakcie", "Karawanseraj na Trakcie", "macro", None, 12, -14),
            ("wyrobisko_srebrnej_zyly", "Wyrobisko Srebrnej Żyły", "macro", None, 18, -28),
            ("wolanka", "Wolanka", "macro", None, 1, 1),
        ],
    )
    c.executemany(
        "INSERT INTO world_hexes (q,r,map_level,hex_type,label) VALUES (?,?,0,?,?)",
        [
            (16, -17, "town", "Kamienny Gród"),
            (12, -14, "road", "Karawanseraj na Trakcie"),
            (18, -28, "village", "Wyrobisko Srebrnej Żyły"),
            (1, 1, "town", "Wolanka"),
        ],
    )
    c.executemany(
        "INSERT INTO characters (id, campaign_id, race) VALUES (?,?,?)",
        [(1, 100, "dwarf"), (2, 200, "human"), (3, 300, None)],
    )
    c.commit()
    yield c
    c.close()


# ── 1. Archetyp zamknięty dla rasy ──────────────────────────────────────────

def test_dwarf_rogue_is_blocked():
    assert not archetype_allowed("dwarf", "rogue")
    reason = archetype_block_reason("dwarf", "rogue")
    assert reason and "Łotrzyk" in reason


@pytest.mark.parametrize("archetype", ["warrior", "scholar"])
def test_dwarf_keeps_its_two_paths(archetype):
    assert archetype_allowed("dwarf", archetype)


@pytest.mark.parametrize("archetype", ["warrior", "scholar", "rogue"])
def test_human_unrestricted(archetype):
    assert archetype_allowed("human", archetype)
    assert blocked_archetypes_for_race("human") == []


def test_blocked_list_for_dwarf_is_rogue_only():
    assert blocked_archetypes_for_race("dwarf") == ["rogue"]


def test_unknown_race_is_not_blocked():
    assert archetype_allowed("elf", "rogue")
    assert blocked_archetypes_for_race(None) == []


# ── 2. Kraina startowa ──────────────────────────────────────────────────────

def test_dwarf_starts_in_the_tavern_by_default(conn):
    start = resolve_race_start(conn, character_id=1, requested_location_name=None)
    assert start is not None
    assert start["loc_key"] == "grod_pod_rdzawym_mlotem"
    assert (start["q"], start["r"]) == (16, -17)  # heks huba Kamiennego Grodu
    assert start["region"] == "siwe_granie"


def test_human_has_no_race_anchor(conn):
    assert resolve_race_start(conn, character_id=2, requested_location_name=None) is None
    assert resolve_race_start(conn, character_id=2, requested_location_name="Wolanka") is None


def test_missing_race_falls_through(conn):
    assert resolve_race_start(conn, character_id=3) is None
    assert resolve_race_start(conn, character_id=None) is None


@pytest.mark.parametrize(
    "requested,expected_key",
    [
        ("Karawanseraj na Trakcie", "karawanseraj_na_trakcie"),
        ("Wyrobisko Srebrnej Żyły", "wyrobisko_srebrnej_zyly"),
        ("Pod Rdzawym Młotem", "grod_pod_rdzawym_mlotem"),
        # bez polskich znaków — plany i gracze piszą bez ogonków
        ("wyrobisko srebrnej zyly", "wyrobisko_srebrnej_zyly"),
    ],
)
def test_plan_may_pick_a_whitelisted_variant(conn, requested, expected_key):
    start = resolve_race_start(conn, character_id=1, requested_location_name=requested)
    assert start["loc_key"] == expected_key


@pytest.mark.parametrize("requested", ["Wolanka", "Lodowiec Pradawny", "Start 42"])
def test_off_whitelist_name_falls_back_to_default(conn, requested):
    start = resolve_race_start(conn, character_id=1, requested_location_name=requested)
    assert start["loc_key"] == "grod_pod_rdzawym_mlotem"
    assert (start["q"], start["r"]) == (16, -17)


def test_no_hex_seeded_means_no_anchor(conn):
    """Świeży clone bez mapy nie może wywrócić startu kampanii — fail-open."""
    conn.execute("DELETE FROM world_hexes")
    conn.commit()
    assert resolve_race_start(conn, character_id=1) is None


def test_whitelist_matches_lore(conn):
    spec = RACE_START["dwarf"]
    assert spec["default"] == "grod_pod_rdzawym_mlotem"
    assert set(spec["variants"]) == {
        "grod_pod_rdzawym_mlotem",
        "karawanseraj_na_trakcie",
        "wyrobisko_srebrnej_zyly",
    }


# ── 3. Podpowiedź do planu kampanii (haki Dagna vs Balrik) ──────────────────

def test_plan_hint_for_dwarf_carries_both_hooks(conn):
    hint = race_plan_hint(conn, campaign_id=100)
    assert "Siwe Granie" in hint
    assert "Dagna" in hint and "Balrik" in hint
    assert "Pod Rdzawym Młotem" in hint


def test_plan_hint_empty_for_human(conn):
    assert race_plan_hint(conn, campaign_id=200) == ""
    assert race_plan_hint(conn, campaign_id=None) == ""
