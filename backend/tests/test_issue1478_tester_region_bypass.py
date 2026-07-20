"""TDD: Issue #1478 — tester wchodzi do krain 'coming', 'locked' zamknięte dla wszystkich.

Decyzja Piotra: `coming` = poczekalnia (tester testuje przed udostępnieniem),
`locked` = twarda blokada (nikt, nawet tester). Bez tego jedynym sposobem
przetestowania nowej krainy byłoby udostępnienie jej wszystkim graczom.

Uruchom w kontenerze:
    docker exec ai-gm-dev-backend-1 pytest tests/test_issue1478_tester_region_bypass.py -v
"""
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services import world_region_service as wrs  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _mem_db() -> sqlite3.Connection:
    """Świat zabawkowy: 3 krainy (live/coming/locked) + 2 użytkowników (tester/gracz)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_regions (
            key TEXT PRIMARY KEY, label TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#888888',
            status TEXT NOT NULL DEFAULT 'coming'
                   CHECK(status IN ('live','coming','locked')),
            status_override TEXT DEFAULT NULL,
            entry_q INTEGER, entry_r INTEGER,
            sort_order INTEGER NOT NULL DEFAULT 0, note TEXT
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER, r INTEGER, map_level INTEGER DEFAULT 0,
            hex_type TEXT, label TEXT, region TEXT,
            encounter_chance REAL DEFAULT 0.15, encounter_pool TEXT DEFAULT '[]',
            location_key TEXT,
            parent_hex_id INTEGER, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE hex_teleport_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_q INTEGER, from_r INTEGER, to_q INTEGER, to_r INTEGER,
            travel_type TEXT, travel_hours REAL, encounter_chance REAL,
            requires_item_key TEXT, label TEXT,
            is_bidirectional INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, username TEXT,
            is_tester INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, title TEXT, owner_user_id INTEGER
        );
    """)
    conn.executemany(
        "INSERT INTO world_regions(key,label,status,sort_order) VALUES (?,?,?,?)",
        [("kresy", "Kresy", "live", 1),
         ("czarnobor", "Czarnobór", "coming", 2),
         ("martwe_pustkowia", "Martwe Pustkowia", "locked", 3)],
    )
    conn.executemany(
        "INSERT INTO world_hexes(q,r,map_level,hex_type,label,region,is_active)"
        " VALUES (?,?,0,?,?,?,1)",
        [(1, 1, "plains", "Polana", "kresy"),
         (60, 5, "forest", "Bór", "czarnobor"),
         (90, 9, "plains", "Sól", "martwe_pustkowia")],
    )
    conn.executemany("INSERT INTO users(id,username,is_tester) VALUES (?,?,?)",
                     [(1, "tester", 1), (2, "gracz", 0)])
    conn.executemany("INSERT INTO campaigns(id,title,owner_user_id) VALUES (?,?,?)",
                     [(10, "kampania testera", 1), (20, "kampania gracza", 2)])
    conn.commit()
    return conn


@pytest.fixture()
def conn():
    c = _mem_db()
    yield c
    c.close()


# ── Kto jest testerem ────────────────────────────────────────────────────────

def test_campaign_of_tester_is_tester(conn):
    assert wrs.campaign_viewer_is_tester(conn, 10) is True


def test_campaign_of_player_is_not_tester(conn):
    assert wrs.campaign_viewer_is_tester(conn, 20) is False


def test_unknown_campaign_is_not_tester(conn):
    """Nieznana kampania nigdy nie dostaje podwyższonych uprawnień."""
    assert wrs.campaign_viewer_is_tester(conn, 999) is False


def test_missing_is_tester_column_is_not_tester(conn):
    """Stary schemat bez kolumny → brak przywilejów, nie wyjątek."""
    conn.executescript("DROP TABLE users; CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);")
    conn.execute("INSERT INTO users(id,username) VALUES (1,'tester')")
    conn.commit()
    assert wrs.campaign_viewer_is_tester(conn, 10) is False


# ── Zbiór krain przechodnich ─────────────────────────────────────────────────

def test_passable_regions_default_is_live_only(conn):
    assert wrs.passable_region_keys(conn) == {"kresy"}


def test_passable_regions_for_tester_add_coming(conn):
    assert wrs.passable_region_keys(conn, include_coming=True) == {"kresy", "czarnobor"}


def test_locked_never_passable(conn):
    """`locked` nie wchodzi do puli NIGDY — także dla testera."""
    assert "martwe_pustkowia" not in wrs.passable_region_keys(conn, include_coming=True)


# ── Bramka blokady per-heks ──────────────────────────────────────────────────

def test_player_blocked_on_coming_hex(conn):
    block = wrs.region_block_for_hex(conn, 60, 5)
    assert block is not None and block["region_status"] == "coming"


def test_tester_not_blocked_on_coming_hex(conn):
    assert wrs.region_block_for_hex(conn, 60, 5, include_coming=True) is None


def test_tester_still_blocked_on_locked_hex(conn):
    block = wrs.region_block_for_hex(conn, 90, 9, include_coming=True)
    assert block is not None, "kraina 'locked' musi być zamknięta także dla testera"
    assert block["region_status"] == "locked"


def test_live_never_blocked(conn):
    """Backward compat: kraina live przechodnia w obu trybach."""
    assert wrs.region_block_for_hex(conn, 1, 1) is None
    assert wrs.region_block_for_hex(conn, 1, 1, include_coming=True) is None


# ── Graf podróży ─────────────────────────────────────────────────────────────

def test_graph_excludes_coming_for_player(conn):
    from app.services.hex_travel_service import _load_hex_graph
    hexes = _load_hex_graph(conn)
    assert (1, 1) in hexes
    assert (60, 5) not in hexes, "gracz nie ma heksów krainy 'coming' w grafie"


def test_graph_includes_coming_for_tester(conn):
    from app.services.hex_travel_service import _load_hex_graph
    hexes = _load_hex_graph(conn, include_coming=True)
    assert (60, 5) in hexes, "tester musi mieć heksy krainy 'coming' w grafie"


def test_graph_never_includes_locked(conn):
    from app.services.hex_travel_service import _load_hex_graph
    assert (90, 9) not in _load_hex_graph(conn, include_coming=True)


def test_live_regions_loader_backward_compatible(conn):
    """Stare wywołanie bez argumentu nadal zwraca same krainy live."""
    from app.services.hex_travel_service import _load_live_regions
    assert _load_live_regions(conn) == {"kresy"}
