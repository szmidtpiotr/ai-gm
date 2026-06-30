"""TDD: Issue #1055 — suggested_actions.py schema drift (game_npcs, lc.to_key)."""
import sqlite3
import sys
import os

sys.path.insert(0, "/app")

from app.services.suggested_actions import _get_npc_actions, _get_exit_actions


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL,
            label TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY,
            location_key TEXT NOT NULL,
            npc_key TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL,
            label TEXT NOT NULL,
            npc_keys TEXT,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE location_connections (
            id INTEGER PRIMARY KEY,
            from_location_key TEXT NOT NULL,
            to_location_key TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        );
    """)
    return conn


# ─── Exit actions ────────────────────────────────────────────────────────────

def test_exit_actions_returns_connections():
    """_get_exit_actions should find exits using from_location_key/to_location_key."""
    conn = _make_conn()
    conn.execute("INSERT INTO game_locations(key, label) VALUES ('loc_a', 'Taverna')")
    conn.execute("INSERT INTO game_locations(key, label) VALUES ('loc_b', 'Rynek')")
    conn.execute(
        "INSERT INTO location_connections(from_location_key, to_location_key) VALUES ('loc_a', 'loc_b')"
    )
    conn.commit()

    actions = _get_exit_actions(conn, "loc_a")
    assert len(actions) == 1, f"Expected 1 exit action, got {len(actions)}"
    assert actions[0].action == "MOVEMENT:loc_b"
    assert "Rynek" in actions[0].label


def test_exit_actions_empty_when_no_connections():
    """No connections → empty list (backward compat)."""
    conn = _make_conn()
    conn.execute("INSERT INTO game_locations(key, label) VALUES ('loc_a', 'Taverna')")
    conn.commit()

    actions = _get_exit_actions(conn, "loc_a")
    assert actions == []


# ─── NPC actions ─────────────────────────────────────────────────────────────

def test_npc_actions_via_assignment_table():
    """_get_npc_actions should query 'npcs' table (not game_npcs) via location_npc_assignments."""
    conn = _make_conn()
    conn.execute("INSERT INTO npcs(key, label) VALUES ('karczmar', 'Stary Karczmar')")
    conn.execute(
        "INSERT INTO location_npc_assignments(location_key, npc_key) VALUES ('karczma', 'karczmar')"
    )
    conn.commit()

    actions = _get_npc_actions(conn, "karczma")
    assert len(actions) == 1, f"Expected 1 NPC action, got {len(actions)}"
    assert actions[0].action == "DIALOGUE:karczmar"
    assert "Stary Karczmar" in actions[0].label


def test_npc_actions_fallback_via_game_locations():
    """Fallback path: npc_keys JSON in game_locations should also use 'npcs' table."""
    conn = _make_conn()
    conn.execute("INSERT INTO npcs(key, label) VALUES ('kowal', 'Mistrz Kowal')")
    conn.execute(
        "INSERT INTO game_locations(key, label, npc_keys) VALUES ('kuźnia', 'Kuźnia', '[\"kowal\"]')"
    )
    conn.commit()

    actions = _get_npc_actions(conn, "kuźnia")
    assert len(actions) == 1, f"Expected 1 NPC action (fallback), got {len(actions)}"
    assert actions[0].action == "DIALOGUE:kowal"
    assert "Mistrz Kowal" in actions[0].label


def test_npc_actions_empty_when_no_npcs():
    """No NPCs assigned → empty list (backward compat)."""
    conn = _make_conn()
    actions = _get_npc_actions(conn, "pusty_hex")
    assert actions == []
