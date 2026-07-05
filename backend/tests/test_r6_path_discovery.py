"""TDD: R6 (#1246) — Odkrywanie trasy podróży.

Decyzja Piotra (zamrożona): hexy faktycznie przebyte trasą → status ``known``
(PM1). Cel podróży + hexy walki/noclegu → ``discovered`` (bez zmian). Przerwana
podróż → known do miejsca przerwania (hex przerwania i tak robi się discovered).

``resolve_chain_travel`` zapisuje przebyte-pośrednie hexy do
``campaign_hex_data.known=1``, a cel/hex-przerwania do ``discovered=1``.
"""
import sys
import json
import sqlite3
import pytest

sys.path.insert(0, "/app")

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_hexes (
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
CREATE TABLE IF NOT EXISTS game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL, label TEXT NOT NULL,
    canonical INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    world_hex_q INTEGER, world_hex_r INTEGER
);
CREATE TABLE IF NOT EXISTS hex_type_config (
    hex_type TEXT PRIMARY KEY,
    travel_hours REAL NOT NULL DEFAULT 1.0,
    encounter_chance REAL NOT NULL DEFAULT 0.0,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS hex_teleport_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_q INTEGER, from_r INTEGER, to_q INTEGER, to_r INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_bidirectional INTEGER NOT NULL DEFAULT 1, travel_hours REAL
);
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY, campaign_id INTEGER,
    current_location_id INTEGER, session_flags TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS campaign_hex_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL, hex_q INTEGER NOT NULL, hex_r INTEGER NOT NULL,
    discovered INTEGER NOT NULL DEFAULT 0,
    known INTEGER NOT NULL DEFAULT 0,
    encounter_cleared INTEGER NOT NULL DEFAULT 0,
    UNIQUE(campaign_id, hex_q, hex_r)
);
CREATE TABLE IF NOT EXISTS active_combat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER UNIQUE, character_id INTEGER,
    status TEXT DEFAULT 'active', ended_reason TEXT
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER, sheet_json TEXT NOT NULL DEFAULT '{}'
);
"""


def _seed(conn, encounter_hex=None):
    """Flat 5-hex row (0,0)…(4,0), plains. Optional guaranteed encounter hex."""
    conn.execute("INSERT INTO hex_type_config (hex_type, travel_hours) VALUES ('plains', 1.0)")
    for q in range(0, 5):
        enc = 1.0 if encounter_hex == (q, 0) else 0.0
        pool = '["goblin_scout"]' if enc else "[]"
        conn.execute(
            "INSERT INTO world_hexes (q, r, hex_type, label, encounter_chance, encounter_pool, is_active, map_level)"
            " VALUES (?,?,'plains',?,?,?,1,0)",
            (q, 0, f"Hex{q}", enc, pool),
        )
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES ('s1', 1, ?)",
        (json.dumps({"current_hex": {"q": 0, "r": 0}}),),
    )
    conn.commit()


def _hex_status(conn, q, r):
    row = conn.execute(
        "SELECT discovered, known FROM campaign_hex_data WHERE campaign_id=1 AND hex_q=? AND hex_r=?",
        (q, r),
    ).fetchone()
    return None if row is None else (row["discovered"], row["known"])


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def test_full_route_intermediate_hexes_known_destination_discovered(conn):
    """Trasa 4-hexowa (0,0)→(3,0): cel discovered, hexy pośrednie known."""
    _seed(conn)
    from app.services.hex_travel_service import resolve_chain_travel

    result = resolve_chain_travel(
        campaign_id=1, character_id=None,
        from_hex=(0, 0), to_hex=(3, 0),
        character_sheet={}, conn=conn,
    )
    assert result.get("arrived_hex") == {"q": 3, "r": 0}, result.get("arrived_hex")

    # Destination → discovered
    d, k = _hex_status(conn, 3, 0)
    assert d == 1, "cel podróży musi być discovered"

    # Travelled-through hexes → known (not discovered)
    for q in (0, 1, 2):
        st = _hex_status(conn, q, 0)
        assert st is not None, f"hex ({q},0) musi mieć wpis"
        d_i, k_i = st
        assert k_i == 1, f"hex pośredni ({q},0) musi być known, got known={k_i}"
        assert d_i == 0, f"hex pośredni ({q},0) NIE może być discovered, got discovered={d_i}"


def test_interrupted_route_known_up_to_break_point(conn):
    """Przerwana walką na (2,0): (0,0),(1,0) known; (2,0) discovered (hex walki)."""
    _seed(conn, encounter_hex=(2, 0))
    from app.services.hex_travel_service import resolve_chain_travel

    result = resolve_chain_travel(
        campaign_id=1, character_id=None,
        from_hex=(0, 0), to_hex=(4, 0),
        character_sheet={}, conn=conn,
    )
    assert result.get("encounter") is not None, "oczekiwano encountera na (2,0)"
    assert result.get("arrived_hex") == {"q": 2, "r": 0}, result.get("arrived_hex")

    # Break-point hex (arrival) → discovered
    d2, k2 = _hex_status(conn, 2, 0)
    assert d2 == 1, "hex przerwania (walki) musi być discovered"

    # Hexes travelled before the break → known
    for q in (0, 1):
        st = _hex_status(conn, q, 0)
        assert st is not None, f"hex ({q},0) musi mieć wpis"
        d_i, k_i = st
        assert k_i == 1, f"przebyty hex ({q},0) musi być known, got known={k_i}"

    # Hexes never reached → no row at all
    assert _hex_status(conn, 3, 0) is None, "hex za punktem przerwania nie może istnieć"
    assert _hex_status(conn, 4, 0) is None, "cel (nieosiągnięty) nie może istnieć"
