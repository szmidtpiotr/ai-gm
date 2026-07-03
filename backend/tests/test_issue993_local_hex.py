"""TDD: Issue #993 — Local hex map (map_level=1) for hub sub-locations.

Tests verify:
- Hub with ≥2 sub-locs gets local hexes auto-assigned on sub-loc creation
- Single sub-loc (below threshold) does NOT get a hex
- auto_assign_local_hex is idempotent (no duplicates)
- get_local_hexes returns only map_level=1 hexes for the correct hub
- Local hexes inherit safe_for_rest → encounter_chance (0.0 safe / 0.20 risky)
- hex_travel_service._load_hex_graph filters map_level=0 only (no local hex pollution)
"""
import sys
import sqlite3
import json

sys.path.insert(0, "/app")

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER NOT NULL,
    r INTEGER NOT NULL,
    hex_type TEXT NOT NULL DEFAULT 'plains',
    label TEXT,
    atmosphere TEXT,
    encounter_chance REAL NOT NULL DEFAULT 0.15,
    encounter_pool TEXT NOT NULL DEFAULT '[]',
    location_key TEXT,
    discovered_in_campaign_id INTEGER,
    created_by_gm INTEGER NOT NULL DEFAULT 0,
    created_by_campaign_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    parent_hex_id INTEGER,
    map_level INTEGER NOT NULL DEFAULT 0,
    region TEXT NOT NULL DEFAULT 'kresy'
);
CREATE TABLE IF NOT EXISTS game_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER,
    parent_key TEXT DEFAULT NULL,
    location_type TEXT DEFAULT 'macro',
    safe_for_rest INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    world_hex_q INTEGER,
    world_hex_r INTEGER
);
CREATE TABLE IF NOT EXISTS game_sessions (
    id TEXT PRIMARY KEY,
    campaign_id INTEGER,
    session_flags TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS hex_teleport_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_q INTEGER NOT NULL,
    from_r INTEGER NOT NULL,
    to_q INTEGER NOT NULL,
    to_r INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_bidirectional INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS hex_type_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hex_type TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);
"""


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _seed_hub(conn: sqlite3.Connection, hub_key: str = "osada_radomierz", q: int = 5, r: int = 3):
    """Insert a hub location with a world hex."""
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, label, location_key, map_level) "
        "VALUES (?, ?, 'settlement', ?, ?, 0)",
        (q, r, hub_key, hub_key),
    )
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, world_hex_q, world_hex_r) "
        "VALUES (?, ?, 'macro', ?, ?)",
        (hub_key, "Osada Radomierz", q, r),
    )
    conn.commit()


def _seed_subloc(
    conn: sqlite3.Connection,
    key: str,
    label: str,
    parent_key: str,
    safe_for_rest: int = 0,
):
    """Insert a sub-location under parent_key."""
    parent_row = conn.execute(
        "SELECT id FROM game_locations WHERE key = ?", (parent_key,)
    ).fetchone()
    parent_id = parent_row["id"] if parent_row else None
    conn.execute(
        "INSERT INTO game_locations (key, label, location_type, parent_id, parent_key, safe_for_rest) "
        "VALUES (?, ?, 'sub', ?, ?, ?)",
        (key, label, parent_id, parent_key, safe_for_rest),
    )
    conn.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_local_hex_assigned_on_second_subloc():
    """Hub with 2 sub-locs → both get map_level=1 hexes after second is created."""
    from app.services.local_hex_service import auto_assign_local_hex, get_local_hexes

    conn = _make_conn()
    _seed_hub(conn)
    _seed_subloc(conn, "kuźnia", "Kuźnia", "osada_radomierz", safe_for_rest=0)
    _seed_subloc(conn, "karczma", "Karczma", "osada_radomierz", safe_for_rest=1)

    # Trigger after second sub-loc creation
    result = auto_assign_local_hex(conn, "karczma", "osada_radomierz")

    assert result is not None, "Should return the new hex for the created sub-loc"
    assert result["map_level"] == 1

    # Both sub-locs must have local hexes
    local = get_local_hexes(conn, "osada_radomierz")
    assert len(local) == 2, f"Expected 2 local hexes, got {len(local)}"
    loc_keys = {h["location_key"] for h in local}
    assert "kuźnia" in loc_keys
    assert "karczma" in loc_keys


def test_no_local_hex_below_threshold():
    """Single sub-loc → no hex created (below threshold of 2)."""
    from app.services.local_hex_service import auto_assign_local_hex, get_local_hexes

    conn = _make_conn()
    _seed_hub(conn)
    _seed_subloc(conn, "kuźnia", "Kuźnia", "osada_radomierz")

    result = auto_assign_local_hex(conn, "kuźnia", "osada_radomierz")

    assert result is None, "Should return None when below threshold"
    local = get_local_hexes(conn, "osada_radomierz")
    assert len(local) == 0, "No local hexes below threshold"


def test_auto_assign_local_hex_idempotent():
    """Calling auto_assign twice for same sub-loc does not create duplicate hexes."""
    from app.services.local_hex_service import auto_assign_local_hex, get_local_hexes

    conn = _make_conn()
    _seed_hub(conn)
    _seed_subloc(conn, "kuźnia", "Kuźnia", "osada_radomierz")
    _seed_subloc(conn, "karczma", "Karczma", "osada_radomierz")

    auto_assign_local_hex(conn, "karczma", "osada_radomierz")
    auto_assign_local_hex(conn, "karczma", "osada_radomierz")  # second call

    local = get_local_hexes(conn, "osada_radomierz")
    assert len(local) == 2, f"Idempotent: still 2 hexes, got {len(local)}"


def test_local_hex_encounter_chance_from_safe_for_rest():
    """#1147: safe_for_rest=True → encounter_chance=0.10 (NOT 0.0 — rest-safety
    must not kill street events like pickpocket/guard-check); False → 0.20."""
    from app.services.local_hex_service import (
        auto_assign_local_hex,
        get_local_hexes,
        SAFE_ENCOUNTER_CHANCE,
        RISKY_ENCOUNTER_CHANCE,
    )

    conn = _make_conn()
    _seed_hub(conn)
    _seed_subloc(conn, "karczma", "Karczma", "osada_radomierz", safe_for_rest=1)
    _seed_subloc(conn, "ulica_targowa", "Ulica Targowa", "osada_radomierz", safe_for_rest=0)

    auto_assign_local_hex(conn, "ulica_targowa", "osada_radomierz")

    local = get_local_hexes(conn, "osada_radomierz")
    by_key = {h["location_key"]: h for h in local}

    assert by_key["karczma"]["encounter_chance"] == SAFE_ENCOUNTER_CHANCE, \
        "Safe loc → SAFE_ENCOUNTER_CHANCE (>0, #1147)"
    assert by_key["karczma"]["encounter_chance"] > 0.0, "Safe loc must still roll encounters"
    assert by_key["ulica_targowa"]["encounter_chance"] == RISKY_ENCOUNTER_CHANCE, \
        "Risky loc → RISKY_ENCOUNTER_CHANCE"


def test_get_local_hexes_filters_by_hub():
    """get_local_hexes returns only hexes for the queried hub, not another hub's."""
    from app.services.local_hex_service import auto_assign_local_hex, get_local_hexes

    conn = _make_conn()
    _seed_hub(conn, "osada_radomierz", q=5, r=3)
    _seed_hub(conn, "zamek_kresowy", q=10, r=7)

    _seed_subloc(conn, "kuźnia_r", "Kuźnia", "osada_radomierz")
    _seed_subloc(conn, "karczma_r", "Karczma", "osada_radomierz")
    _seed_subloc(conn, "wieża_z", "Wieża", "zamek_kresowy")
    _seed_subloc(conn, "dziedziniec_z", "Dziedziniec", "zamek_kresowy")

    auto_assign_local_hex(conn, "karczma_r", "osada_radomierz")
    auto_assign_local_hex(conn, "dziedziniec_z", "zamek_kresowy")

    local_r = get_local_hexes(conn, "osada_radomierz")
    local_z = get_local_hexes(conn, "zamek_kresowy")

    assert len(local_r) == 2
    assert len(local_z) == 2

    keys_r = {h["location_key"] for h in local_r}
    keys_z = {h["location_key"] for h in local_z}
    assert keys_r.isdisjoint(keys_z), "Two hubs must not share local hexes"


def test_load_hex_graph_excludes_local_hexes():
    """hex_travel_service._load_hex_graph must only include map_level=0 hexes."""
    from app.services.hex_travel_service import _load_hex_graph

    conn = _make_conn()
    # World hex at (5,3) — should be in graph
    # Local hexes at (0,0) and (1,0) — must NOT pollute the world graph
    conn.executescript("""
        INSERT INTO world_hexes (q, r, hex_type, map_level) VALUES (5, 3, 'plains', 0);
        INSERT INTO world_hexes (q, r, hex_type, map_level, parent_hex_id)
            VALUES (0, 0, 'settlement', 1, 1);
        INSERT INTO world_hexes (q, r, hex_type, map_level, parent_hex_id)
            VALUES (1, 0, 'settlement', 1, 1);
    """)
    conn.commit()

    graph = _load_hex_graph(conn)
    assert (5, 3) in graph, "World hex must be in graph"
    assert (0, 0) not in graph, "Local hex (0,0) must not pollute world graph"
    assert (1, 0) not in graph, "Local hex (1,0) must not pollute world graph"
    assert len(graph) == 1, f"Only 1 world hex, got {len(graph)}: {list(graph.keys())}"


def test_third_subloc_gets_hex_immediately():
    """After threshold is crossed, each new sub-loc gets its hex right away."""
    from app.services.local_hex_service import auto_assign_local_hex, get_local_hexes

    conn = _make_conn()
    _seed_hub(conn)
    _seed_subloc(conn, "kuźnia", "Kuźnia", "osada_radomierz")
    _seed_subloc(conn, "karczma", "Karczma", "osada_radomierz")
    auto_assign_local_hex(conn, "karczma", "osada_radomierz")

    # Add third sub-loc
    _seed_subloc(conn, "kościół", "Kościół", "osada_radomierz")
    result = auto_assign_local_hex(conn, "kościół", "osada_radomierz")

    assert result is not None
    local = get_local_hexes(conn, "osada_radomierz")
    assert len(local) == 3
