"""TDD: Issue #1412 — „porwanie przez nurt" przy przeprawie przez BRÓD.

Za każdy przebyty hex `brod`: test Obrony d20 + SIŁA_mod vs FORD_CROSS_DC. Nat 20 auto,
Nat 1 = porwanie. Porażka → przemoczony (+czas); porażka ≥5 lub Nat 1 → 1d6 obrażeń.
Tu testujemy ścieżkę SUKCESU (izolowaną od combat_service) + brak brodu = brak hazardu.
Porażkę/obrażenia/przemoczony weryfikujemy live na DEV.
"""
import json
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services import hex_travel_service
from app.services.hex_travel_service import maybe_ford_hazard, FORD_CROSS_DC


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT);
        CREATE TABLE world_hexes (
            q INTEGER, r INTEGER, hex_type TEXT DEFAULT 'plains',
            map_level INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, character_id INTEGER,
            turn_number INTEGER, user_text TEXT, assistant_text TEXT, route TEXT, created_at TEXT
        );
    """)
    conn.execute("INSERT INTO characters (id, sheet_json) VALUES (7, ?)",
                 (json.dumps({"stats": {"STR": 20}, "current_hp": 30, "max_hp": 30}),))
    conn.commit()
    return conn


def _ford_turn(conn):
    # #1416 — rzut brodu zapisany jako user_text „[Rzut: Przeprawa (Siła) …]" (karta rzutu).
    return conn.execute(
        "SELECT user_text, assistant_text FROM campaign_turns "
        "WHERE user_text LIKE '[Rzut: Przeprawa%' ORDER BY id DESC LIMIT 1"
    ).fetchone()


def test_no_ford_in_path_no_hazard(monkeypatch):
    """Trasa bez brodu → brak result['ford_hazard'], brak tury."""
    conn = _conn()
    conn.execute("INSERT INTO world_hexes (q,r,hex_type) VALUES (1,0,'plains')")
    conn.commit()
    result = {"ok": True, "path": [{"q": 0, "r": 0}, {"q": 1, "r": 0}], "arrived_hex": {"q": 1, "r": 0}}
    maybe_ford_hazard(conn, 42, 7, result)
    assert "ford_hazard" not in result
    assert _ford_turn(conn) is None


def test_ford_clean_crossing_nat20(monkeypatch):
    """Bród przebyty, Nat 20 → sukces: bez obrażeń, bez przemoczenia, wpis [Bród] w logu."""
    conn = _conn()
    conn.execute("INSERT INTO world_hexes (q,r,hex_type) VALUES (1,0,'brod')")
    conn.commit()
    monkeypatch.setattr(hex_travel_service.random, "randint", lambda a, b: 20)
    result = {"ok": True,
              "path": [{"q": 0, "r": 0}, {"q": 1, "r": 0}, {"q": 2, "r": 0}],
              "arrived_hex": {"q": 2, "r": 0}}
    maybe_ford_hazard(conn, 42, 7, result)

    fh = result.get("ford_hazard")
    assert fh is not None, "hazard musi się policzyć gdy przebyto bród"
    assert len(fh["events"]) == 1
    assert fh["events"][0]["success"] is True and fh["events"][0]["nat20"] is True
    assert fh["damage"] == 0 and fh["swept"] is False and fh["wet"] is False
    # HP nietknięte
    hp = json.loads(conn.execute("SELECT sheet_json FROM characters WHERE id=7").fetchone()["sheet_json"])["current_hp"]
    assert hp == 30
    # wpis w logu z rzutem
    row = _ford_turn(conn)
    assert row is not None
    # rzut w user_text jako karta „[Rzut: Przeprawa (Siła) — 20 +5 = 25 vs 12 — naturalny 20]"
    assert "vs 12" in row["user_text"] and "naturalny 20" in row["user_text"]
    # proza skutku w assistant (bez inline-tagu rzutu)
    assert "brzeg" in json.loads(row["assistant_text"])["narrative"].lower()


def test_ford_only_counts_traversed_hexes(monkeypatch):
    """Bród ZA punktem dotarcia (podróż przerwana) nie jest liczony."""
    conn = _conn()
    conn.execute("INSERT INTO world_hexes (q,r,hex_type) VALUES (2,0,'brod')")  # bród na końcu
    conn.commit()
    monkeypatch.setattr(hex_travel_service.random, "randint", lambda a, b: 20)
    # dotarł tylko do (1,0); bród (2,0) za punktem dotarcia
    result = {"ok": True,
              "path": [{"q": 0, "r": 0}, {"q": 1, "r": 0}, {"q": 2, "r": 0}],
              "arrived_hex": {"q": 1, "r": 0}}
    maybe_ford_hazard(conn, 42, 7, result)
    assert "ford_hazard" not in result, "bród za punktem dotarcia nie wchodzi"
