"""KN-9 (#1500) — losowy start człowieka: Kresy vs Vilnograd.

§8 koronne_niziny.md: człowiek dostaje LOSOWY start 50/50 — gospoda „Pod Złamanym
Rogiem" na Kresach ALBO Vilnograd, stolica Korony. Wariant miejski dobiera sub do
archetypu (łotrzyk → Dzielnica Złodziei, kanon; reszta → zajazd przy Targu Wielkim).

Pod testem:
  1. Rozkład losowania ≈ 50/50 (wartość startowa ``HUMAN_VILNOGRAD_START_CHANCE``).
  2. Poprawny heks startu obu wariantów (Kresy = gospoda, Vilnograd = heks huba).
  3. Sub Vilnogradu wg archetypu (łotrzyk → Dzielnica Złodziei).
  4. Losowanie pada RAZ i jest trwałe (idempotencja przez ``sheet_json.kn9_start``).
  5. Vilnograd nie zaseedowany → zawsze Kresy (§8 aktywacja).
  6. Inne rasy bez zmian; plan-hint miejski niesie haki, wiejski jest pusty.
"""
import json
import random
import sqlite3

import pytest

from app.services import race_start_service as rss
from app.services.race_start_service import (
    race_plan_hint,
    resolve_human_start_variant,
    resolve_race_start,
)


def _mk_conn(vilnograd_seeded: bool = True) -> sqlite3.Connection:
    """Mini-świat: gospoda na Kresach + hub Vilnogradu z dwoma subami."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, race TEXT,
            sheet_json TEXT, is_active INTEGER DEFAULT 1
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
    locs = [
        # Kresy — gospoda „Pod Złamanym Rogiem" na własnym heksie (24,13).
        ("gospoda_pod_zlamanym_rogiem", "Gospoda Pod Złamanym Rogiem", "macro",
         None, 24, 13),
        # Vilnograd — hub na heksie (-23,22); suby dziedziczą jego heks (parent).
        ("vilnograd_dzielnica_zlodziei", "Vilnograd: Dzielnica Złodziei", "sub",
         "vilnograd_stolica", None, None),
        ("vilnograd_rynek", "Vilnograd: Targ Wielki", "sub",
         "vilnograd_stolica", None, None),
    ]
    if vilnograd_seeded:
        locs.insert(1, ("vilnograd_stolica", "Vilnograd, Stolica", "macro",
                        None, -23, 22))
    c.executemany(
        "INSERT INTO game_locations (key,label,location_type,parent_key,"
        "world_hex_q,world_hex_r) VALUES (?,?,?,?,?,?)",
        locs,
    )
    hexes = [(24, 13, "town", "Kresy: Pod Złamanym Rogiem")]
    if vilnograd_seeded:
        hexes.append((-23, 22, "city", "Vilnograd, Stolica"))
    c.executemany(
        "INSERT INTO world_hexes (q,r,map_level,hex_type,label) VALUES (?,?,0,?,?)",
        hexes,
    )
    c.commit()
    return c


def _add_human(conn: sqlite3.Connection, char_id: int, campaign_id: int,
               archetype: str = "warrior") -> None:
    conn.execute(
        "INSERT INTO characters (id, campaign_id, race, sheet_json) VALUES (?,?,?,?)",
        (char_id, campaign_id, "human", json.dumps({"archetype": archetype})),
    )
    conn.commit()


@pytest.fixture()
def conn():
    c = _mk_conn(vilnograd_seeded=True)
    yield c
    c.close()


# ── 1. Rozkład losowania ≈ 50/50 ────────────────────────────────────────────

def test_draw_distribution_is_roughly_fifty_fifty(conn):
    random.seed(1500)
    n = 600
    vilnograd = 0
    for i in range(n):
        _add_human(conn, char_id=1000 + i, campaign_id=2000 + i)
        if resolve_human_start_variant(conn, 1000 + i) == "vilnograd":
            vilnograd += 1
    frac = vilnograd / n
    assert 0.40 <= frac <= 0.60, f"rozkład poza 40–60%: {frac:.2%}"


def test_start_chance_is_a_tunable_starting_value():
    # WARTOŚĆ STARTOWA — 50/50, strojona po obserwacji (§8 / KN-9).
    assert rss.HUMAN_VILNOGRAD_START_CHANCE == 0.5


# ── 2. Poprawny heks startu obu wariantów ───────────────────────────────────

def test_vilnograd_variant_lands_on_hub_hex(conn, monkeypatch):
    monkeypatch.setattr(rss.random, "random", lambda: 0.0)  # < 0.5 → Vilnograd
    _add_human(conn, 1, 100, archetype="warrior")
    start = resolve_race_start(conn, character_id=1)
    assert start is not None
    assert start["loc_key"] == "vilnograd_rynek"           # zajazd przy Targu Wielkim
    assert (start["q"], start["r"]) == (-23, 22)           # heks huba (dziedziczony)
    assert start["region"] == "koronne_niziny"


def test_kresy_variant_lands_on_the_inn_hex(conn, monkeypatch):
    monkeypatch.setattr(rss.random, "random", lambda: 0.99)  # ≥ 0.5 → Kresy
    _add_human(conn, 1, 100, archetype="warrior")
    start = resolve_race_start(conn, character_id=1)
    assert start is not None
    assert start["loc_key"] == "gospoda_pod_zlamanym_rogiem"
    assert (start["q"], start["r"]) == (24, 13)
    assert start["region"] == "kresy"


# ── 3. Sub Vilnogradu wg archetypu ──────────────────────────────────────────

def test_rogue_starts_in_the_thieves_district(conn, monkeypatch):
    monkeypatch.setattr(rss.random, "random", lambda: 0.0)  # Vilnograd
    _add_human(conn, 1, 100, archetype="rogue")
    start = resolve_race_start(conn, character_id=1)
    assert start["loc_key"] == "vilnograd_dzielnica_zlodziei"  # kanon
    assert (start["q"], start["r"]) == (-23, 22)


@pytest.mark.parametrize("archetype", ["warrior", "scholar"])
def test_non_rogue_starts_at_the_market(conn, monkeypatch, archetype):
    monkeypatch.setattr(rss.random, "random", lambda: 0.0)
    _add_human(conn, 1, 100, archetype=archetype)
    start = resolve_race_start(conn, character_id=1)
    assert start["loc_key"] == "vilnograd_rynek"


# ── 4. Losowanie pada RAZ i jest trwałe ─────────────────────────────────────

def test_draw_is_persisted_and_idempotent(conn, monkeypatch):
    monkeypatch.setattr(rss.random, "random", lambda: 0.0)  # pierwsze losowanie → Vilnograd
    _add_human(conn, 1, 100)
    first = resolve_human_start_variant(conn, 1)
    assert first == "vilnograd"
    # zapis na bohaterze
    row = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()
    assert json.loads(row["sheet_json"])["kn9_start"] == "vilnograd"
    # kolejne wywołanie NIE losuje ponownie, choćby moneta pokazała drugą stronę
    monkeypatch.setattr(rss.random, "random", lambda: 0.99)
    assert resolve_human_start_variant(conn, 1) == "vilnograd"


def test_plan_hint_and_hex_agree_regardless_of_order(conn, monkeypatch):
    """Plan-hint losuje, a fizyczny heks czyta ten sam zapis (bez rozjazdu)."""
    monkeypatch.setattr(rss.random, "random", lambda: 0.0)  # Vilnograd
    _add_human(conn, 1, 100, archetype="rogue")
    hint = race_plan_hint(conn, campaign_id=100)             # losuje + persist
    assert "Vilnograd" in hint
    monkeypatch.setattr(rss.random, "random", lambda: 0.99)  # próba przełamania
    start = resolve_race_start(conn, character_id=1)         # czyta zapis
    assert start["loc_key"] == "vilnograd_dzielnica_zlodziei"


# ── 5. Vilnograd nie zaseedowany → zawsze Kresy (§8) ────────────────────────

def test_unseeded_vilnograd_forces_kresy(monkeypatch):
    c = _mk_conn(vilnograd_seeded=False)
    try:
        monkeypatch.setattr(rss.random, "random", lambda: 0.0)  # chciałby Vilnograd
        _add_human(c, 1, 100)
        assert resolve_human_start_variant(c, 1) == "kresy"
        start = resolve_race_start(c, character_id=1)
        assert start["loc_key"] == "gospoda_pod_zlamanym_rogiem"
        assert (start["q"], start["r"]) == (24, 13)
    finally:
        c.close()


# ── 6. Inne rasy bez zmian; plan-hint miejski vs wiejski ────────────────────

def test_vilnograd_plan_hint_carries_city_hooks(conn, monkeypatch):
    monkeypatch.setattr(rss.random, "random", lambda: 0.0)  # Vilnograd
    _add_human(conn, 1, 100, archetype="rogue")
    hint = race_plan_hint(conn, campaign_id=100)
    assert "Vilnograd" in hint
    assert "GILDII" in hint and "DŁUG" in hint and "Nocny Burmistrz" in hint
    assert "Dzielnica Złodziei" in hint  # łotrzyk → kanon


def test_kresy_plan_hint_is_empty(conn, monkeypatch):
    monkeypatch.setattr(rss.random, "random", lambda: 0.99)  # Kresy
    _add_human(conn, 1, 100)
    assert race_plan_hint(conn, campaign_id=100) == ""


def test_non_human_race_ignores_kn9_path(conn):
    # krasnolud nie ma tu kotwicy (brak Siwych Grani w fixturze) → None,
    # ale NIGDY nie wchodzi w losową ścieżkę człowieka.
    conn.execute(
        "INSERT INTO characters (id, campaign_id, race, sheet_json) VALUES (?,?,?,?)",
        (9, 900, "dwarf", json.dumps({"archetype": "warrior"})),
    )
    conn.commit()
    assert resolve_race_start(conn, character_id=9) is None
    # i sheet krasnoluda nie dostaje znacznika kn9_start
    row = conn.execute("SELECT sheet_json FROM characters WHERE id=9").fetchone()
    assert "kn9_start" not in json.loads(row["sheet_json"])
