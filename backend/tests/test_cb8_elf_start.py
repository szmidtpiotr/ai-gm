"""CB-8 (#1474 §9) — start kampanii elfa w Czarnoborze.

Warunek wstępny (#1514/CB-5): rasa elfa wdrożona, hub „Szept Koron" istnieje
w `game_locations` na heksie 74,-12, region ma zaseedowane heksy. CB-8 dokłada
WYŁĄCZNIE kotwicę startową:

  1. `RACE_START["elf"]` — whitelist: default Gościnne Drzewo (sub Szept Koron,
     dziedziczy heks huba) + wariant Ostęp Graniczny (własny heks 74,8).
  2. `RACE_PLAN_HINT["elf"]` — haki §9: Aerlin („kolejne drzewo zgasło")
     + spór Cathel vs Nimriel (dwie strony werbują gracza).

Regresja: człowiek (Kresy) i krasnolud (Kamienny Gród) startują jak dotąd.
"""
import sqlite3

import pytest

from app.services.race_start_service import (
    RACE_PLAN_HINT,
    RACE_START,
    race_plan_hint,
    resolve_race_start,
)


@pytest.fixture()
def conn():
    """Mini-Czarnobór: hub Szept Koron (heks 74,-12) + sub Gościnne Drzewo
    (bez własnego heksa — dziedziczy rodzica) + Ostęp Graniczny (heks 74,8)."""
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
            ("szept_koron", "Szept Koron", "macro", None, 74, -12),
            ("szept_goscinne_drzewo", "Szept Koron: Gościnne Drzewo", "sub",
             "szept_koron", None, None),
            ("ostep_graniczny", "Ostęp Graniczny", "macro", None, 74, 8),
            ("bor_zmarlych", "Bór Zmarłych", "macro", None, 69, -17),
        ],
    )
    c.executemany(
        "INSERT INTO world_hexes (q,r,map_level,hex_type,label) VALUES (?,?,0,?,?)",
        [
            (74, -12, "forest", None),
            (74, 8, "village", "Ostęp Graniczny"),
            (69, -17, "forest", "Bór Zmarłych"),
        ],
    )
    c.executemany(
        "INSERT INTO characters (id, campaign_id, race) VALUES (?,?,?)",
        [(1, 100, "elf"), (2, 200, "human")],
    )
    c.commit()
    yield c
    c.close()


# ── Whitelist startowa ──────────────────────────────────────────────────────

def test_elf_starts_in_the_hospitable_tree_by_default(conn):
    start = resolve_race_start(conn, character_id=1, requested_location_name=None)
    assert start is not None
    assert start["loc_key"] == "szept_goscinne_drzewo"
    assert (start["q"], start["r"]) == (74, -12)  # heks huba Szept Koron (dziedziczony)
    assert start["region"] == "czarnobor"


@pytest.mark.parametrize(
    "requested,expected_key",
    [
        ("Ostęp Graniczny", "ostep_graniczny"),
        ("ostep graniczny", "ostep_graniczny"),  # bez ogonków
        ("Gościnne Drzewo", "szept_goscinne_drzewo"),
    ],
)
def test_plan_may_pick_a_whitelisted_variant(conn, requested, expected_key):
    start = resolve_race_start(conn, character_id=1, requested_location_name=requested)
    assert start["loc_key"] == expected_key


@pytest.mark.parametrize("requested", ["Bór Zmarłych", "Trzęsawiska Mgieł", "gdziekolwiek"])
def test_off_whitelist_name_falls_back_to_default(conn, requested):
    start = resolve_race_start(conn, character_id=1, requested_location_name=requested)
    assert start["loc_key"] == "szept_goscinne_drzewo"
    assert (start["q"], start["r"]) == (74, -12)


def test_ostep_graniczny_resolves_to_its_own_hex(conn):
    start = resolve_race_start(conn, character_id=1, requested_location_name="Ostęp Graniczny")
    assert (start["q"], start["r"]) == (74, 8)


def test_no_hex_seeded_means_no_anchor(conn):
    """Fail-open — brak mapy nie wywraca tworzenia kampanii."""
    conn.execute("DELETE FROM world_hexes")
    conn.commit()
    assert resolve_race_start(conn, character_id=1) is None


# ── Regresja innych ras ─────────────────────────────────────────────────────

def test_human_still_has_no_anchor(conn):
    assert resolve_race_start(conn, character_id=2) is None


def test_whitelist_matches_lore():
    spec = RACE_START["elf"]
    assert spec["region"] == "czarnobor"
    assert spec["default"] == "szept_goscinne_drzewo"
    assert set(spec["variants"]) == {"szept_goscinne_drzewo", "ostep_graniczny"}


# ── Plan-hint (haki §9) ─────────────────────────────────────────────────────

def test_plan_hint_for_elf_carries_both_hooks(conn):
    hint = race_plan_hint(conn, campaign_id=100)
    assert "Czarnobór" in hint
    assert "Gościnne Drzewo" in hint
    assert "Aerlin" in hint
    assert "Cathel" in hint and "Nimriel" in hint


def test_plan_hint_empty_for_human(conn):
    assert race_plan_hint(conn, campaign_id=200) == ""


def test_elf_plan_hint_is_registered():
    assert "elf" in RACE_PLAN_HINT
    assert "elf" in RACE_START
