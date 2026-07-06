"""TDD: R8 (#1248) — granica Kresy ↔ Siwe Granie (wariant B: mur + przełęcz).

Decyzja Piotra (zamrożona, komentarz #1248): Siwe Granie przysunięte bliżej Kresów
(offset Δr=+24), a między krainami stoi prawdziwa granica: rząd hexów ``grania``
(is_passable=0 → wykluczone z grafu podróży, mur) z jednym wąskim przejściem —
2 hexy ``przelecz`` (is_passable=1). ``find_path`` z Kresów do Siwych Grań musi
prowadzić PRZEZ przełęcz i NIE może przechodzić przez grań. Przejście działa tylko
gdy region ``siwe_granie`` jest ``live``.

Ten test odtwarza minimalny wycinek granicy (nie całą mapę) i weryfikuje kontrakt
przez publiczny ``_load_hex_graph`` + ``find_path``.
"""
import sys
import sqlite3
import pytest

sys.path.insert(0, "/app")

from app.services.hex_travel_service import (  # noqa: E402
    _load_hex_graph,
    _load_hex_type_config,
    find_path,
)

SCHEMA = """
CREATE TABLE world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER NOT NULL, r INTEGER NOT NULL,
    hex_type TEXT NOT NULL DEFAULT 'plains',
    label TEXT, atmosphere TEXT,
    encounter_chance REAL NOT NULL DEFAULT 0.0,
    encounter_pool TEXT NOT NULL DEFAULT '[]',
    location_key TEXT, region TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    parent_hex_id INTEGER, map_level INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE hex_type_config (
    hex_type TEXT PRIMARY KEY,
    travel_hours REAL NOT NULL DEFAULT 1.0,
    encounter_base_chance REAL NOT NULL DEFAULT 0.0,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_passable INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE hex_teleport_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_q INTEGER, from_r INTEGER, to_q INTEGER, to_r INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_bidirectional INTEGER NOT NULL DEFAULT 1, travel_hours REAL
);
CREATE TABLE world_regions (
    key TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'coming'
);
"""

# Minimalny wycinek granicy wokół przełęczy (q 4..6), zgodny z geometrią produkcyjną:
# Kresy poniżej (r większe), Siwe powyżej (r mniejsze), mur w rzędzie między nimi,
# przełęcz w jednej kolumnie jako jedyne przejście.
#   r=-2  S S S     (siwe)
#   r=-1  # P #     (grania / PRZEŁĘCZ / grania)
#   r= 0  K K K     (kresy)
KRESY = [(4, 0), (5, 0), (6, 0), (4, 1), (5, 1), (6, 1)]
SIWE = [(4, -2), (5, -2), (6, -2), (4, -3), (5, -3), (6, -3)]
WALL = [(4, -1), (6, -1)]        # grania — mur (is_passable=0)
PASS = [(5, -1)]                 # przelecz — jedyne przejście (is_passable=1)


def _mk_db(siwe_status="live", pass_type="przelecz"):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO hex_type_config (hex_type, travel_hours, is_passable) VALUES (?,?,?)",
        [("plains", 1.0, 1), ("tundra", 1.0, 1), ("grania", 3.0, 0), ("przelecz", 2.0, 1)],
    )
    conn.executemany(
        "INSERT INTO world_regions (key, status) VALUES (?,?)",
        [("kresy", "live"), ("siwe_granie", siwe_status)],
    )

    def ins(cells, htype, region):
        conn.executemany(
            "INSERT INTO world_hexes (q, r, hex_type, region) VALUES (?,?,?,?)",
            [(q, r, htype, region) for q, r in cells],
        )

    ins(KRESY, "plains", "kresy")
    ins(SIWE, "tundra", "siwe_granie")
    ins(WALL, "grania", "siwe_granie")
    ins(PASS, pass_type, "siwe_granie")
    conn.commit()
    return conn


def test_crossing_goes_through_pass_not_wall():
    """find_path Kresy→Siwe prowadzi PRZEZ przełęcz, nie przez grań."""
    conn = _mk_db()
    hexes = _load_hex_graph(conn)
    cfg = _load_hex_type_config(conn)

    path = find_path((5, 1), (5, -3), hexes, cfg)

    assert path is not None, "ścieżka Kresy→Siwe powinna istnieć przez przełęcz"
    assert (5, -1) in path, "ścieżka musi przechodzić przez hex przełęczy (5,-1)"
    # żaden hex grań nie może być w ścieżce (mur wykluczony z grafu)
    grania_in_path = [p for p in path if hexes.get(p, {}).get("hex_type") == "grania"]
    assert grania_in_path == [], f"grań nie może być w ścieżce, jest: {grania_in_path}"


def test_wall_is_excluded_from_graph():
    """Hexy grań (is_passable=0) nie trafiają do grafu podróży."""
    conn = _mk_db()
    hexes = _load_hex_graph(conn)
    for cell in WALL:
        assert cell not in hexes, f"grań {cell} nie powinna być w grafie"
    for cell in PASS:
        assert cell in hexes, f"przełęcz {cell} powinna być w grafie"


def test_no_crossing_when_pass_is_wall():
    """Bez przejezdnej przełęczy (cała granica = grań) find_path zwraca None."""
    conn = _mk_db(pass_type="grania")  # zamurowana przełęcz
    hexes = _load_hex_graph(conn)
    cfg = _load_hex_type_config(conn)

    path = find_path((5, 1), (5, -3), hexes, cfg)
    assert path is None, "bez przełęczy krainy muszą być rozłączone (mur szczelny)"


def test_no_crossing_when_siwe_not_live():
    """Przejście działa tylko gdy region siwe_granie jest 'live'."""
    conn = _mk_db(siwe_status="coming")  # kraina jeszcze zablokowana
    hexes = _load_hex_graph(conn)
    cfg = _load_hex_type_config(conn)

    # cele Siwych w ogóle nie ma w grafie, więc brak ścieżki
    assert (5, -3) not in hexes, "hexy niezaktywowanej krainy nie są w grafie"
    path = find_path((5, 1), (5, -3), hexes, cfg)
    assert path is None, "podróż do niezaktywowanej krainy niemożliwa"
