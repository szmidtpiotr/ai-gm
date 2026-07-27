"""WL-9 (#1504 §10 / #1476) — start kampanii wyspiarza w Czarnogrodzie.

Warunek wstępny: rasa wyspiarzy (#1476) wdrożona, WL-6 zbudowane — hub
„Czarnogród, Port" istnieje w `game_locations` na heksie −19,65 z subami
Dzielnica Wyspiarzy i Nabrzeże (dziedziczą heks huba). WL-9 dokłada WYŁĄCZNIE
kotwicę startową:

  1. `RACE_START["wyspiarze"]` — whitelist: default Dzielnica Wyspiarzy
     (sub Czarnogrodu, dziedziczy heks huba) + wariant Nabrzeże (ten sam heks).
  2. `RACE_PLAN_HINT["wyspiarze"]` — haki §10: pusty fotel w Radzie, blokada
     Korony (Kapitan Roggen), Dziadek Florian szuka śmiałka.

KLUCZOWE (diaspora): RACE_START ustawia tylko *miejsce startu*, a NIE bramkuje
dostępności rasy — `RACE_HOME_REGION["wyspiarze"]` zostaje `None`, więc wyspiarz
jest nadal dostępny wszędzie (regresja niżej).

Regresja: człowiek (Kresy), krasnolud (Kamienny Gród) i dostępność wyspiarza
bez zmian.
"""
import sqlite3

import pytest

from app.services.race_start_service import (
    RACE_PLAN_HINT,
    RACE_START,
    race_plan_hint,
    resolve_race_start,
)
from app.services.world_region_service import RACE_HOME_REGION


@pytest.fixture()
def conn():
    """Mini-Czarnogród: hub Port (heks −19,65) + sub Dzielnica Wyspiarzy i
    Nabrzeże (bez własnego heksa — dziedziczą rodzica) + obca lokacja."""
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
            ("czarnogrod_port", "Czarnogród, Port", "macro", None, -19, 65),
            ("czarnogrod_dzielnica_wyspiarzy", "Czarnogród: Dzielnica Wyspiarzy",
             "sub", "czarnogrod_port", None, None),
            ("czarnogrod_nabrzeze", "Czarnogród: Nabrzeże",
             "sub", "czarnogrod_port", None, None),
            ("zatoka_topielcow", "Zatoka Topielców", "macro", None, -25, 102),
        ],
    )
    c.executemany(
        "INSERT INTO world_hexes (q,r,map_level,hex_type,label) VALUES (?,?,0,?,?)",
        [
            (-19, 65, "town", "Czarnogród"),
            (-25, 102, "coast", "Zatoka Topielców"),
        ],
    )
    c.executemany(
        "INSERT INTO characters (id, campaign_id, race) VALUES (?,?,?)",
        [(1, 100, "wyspiarze"), (2, 200, "human")],
    )
    c.commit()
    yield c
    c.close()


# ── Whitelist startowa ──────────────────────────────────────────────────────

def test_wyspiarz_starts_in_the_diaspora_quarter_by_default(conn):
    start = resolve_race_start(conn, character_id=1, requested_location_name=None)
    assert start is not None
    assert start["loc_key"] == "czarnogrod_dzielnica_wyspiarzy"
    assert (start["q"], start["r"]) == (-19, 65)  # heks huba Czarnogród (dziedziczony)
    assert start["region"] == "wybrzeze_lez"


@pytest.mark.parametrize(
    "requested,expected_key",
    [
        ("Nabrzeże", "czarnogrod_nabrzeze"),
        ("nabrzeze", "czarnogrod_nabrzeze"),  # bez ogonków
        ("Dzielnica Wyspiarzy", "czarnogrod_dzielnica_wyspiarzy"),
    ],
)
def test_plan_may_pick_a_whitelisted_variant(conn, requested, expected_key):
    start = resolve_race_start(conn, character_id=1, requested_location_name=requested)
    assert start["loc_key"] == expected_key


@pytest.mark.parametrize("requested", ["Zatoka Topielców", "Latarnia Topielców", "gdziekolwiek"])
def test_off_whitelist_name_falls_back_to_default(conn, requested):
    start = resolve_race_start(conn, character_id=1, requested_location_name=requested)
    assert start["loc_key"] == "czarnogrod_dzielnica_wyspiarzy"
    assert (start["q"], start["r"]) == (-19, 65)


def test_both_variants_share_the_hub_hex(conn):
    # Nabrzeże nie ma własnego heksa → dziedziczy heks huba Port jak Dzielnica.
    nabrzeze = resolve_race_start(conn, character_id=1, requested_location_name="Nabrzeże")
    assert (nabrzeze["q"], nabrzeze["r"]) == (-19, 65)


def test_no_hex_seeded_means_no_anchor(conn):
    """Fail-open — brak mapy nie wywraca tworzenia kampanii."""
    conn.execute("DELETE FROM world_hexes")
    conn.commit()
    assert resolve_race_start(conn, character_id=1) is None


# ── Diaspora: kotwica startu NIE bramkuje dostępności rasy ───────────────────

def test_wyspiarze_home_region_stays_none_despite_start_anchor():
    # RACE_START daje miejsce startu, ale dostępność rasy nadal „wszędzie".
    assert RACE_HOME_REGION["wyspiarze"] is None


# ── Regresja innych ras ─────────────────────────────────────────────────────

def test_human_still_has_no_anchor(conn):
    assert resolve_race_start(conn, character_id=2) is None


def test_whitelist_matches_lore():
    spec = RACE_START["wyspiarze"]
    assert spec["region"] == "wybrzeze_lez"
    assert spec["default"] == "czarnogrod_dzielnica_wyspiarzy"
    assert set(spec["variants"]) == {
        "czarnogrod_dzielnica_wyspiarzy",
        "czarnogrod_nabrzeze",
    }


# ── Plan-hint (haki §10) ────────────────────────────────────────────────────

def test_plan_hint_for_wyspiarz_carries_all_three_hooks(conn):
    hint = race_plan_hint(conn, campaign_id=100)
    assert "Czarnogród" in hint
    assert "Dzielnica Wyspiarzy" in hint
    assert "Nabrzeże" in hint
    # trzy haki §10
    assert "fotel" in hint.lower()            # pusty fotel w Radzie
    assert "Roggen" in hint                   # blokada Korony
    assert "Florian" in hint                  # Florian szuka śmiałka


def test_plan_hint_keeps_the_diaspora_everywhere_thread(conn):
    # Wątek §7 zachowany: obecni wszędzie, u siebie tam, gdzie sól.
    hint = race_plan_hint(conn, campaign_id=100)
    assert "WSZĘDZIE" in hint or "wszędzie" in hint


def test_plan_hint_empty_for_human(conn):
    assert race_plan_hint(conn, campaign_id=200) == ""


def test_wyspiarze_start_is_registered():
    assert "wyspiarze" in RACE_PLAN_HINT
    assert "wyspiarze" in RACE_START
