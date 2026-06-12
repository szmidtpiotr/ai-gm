"""TDD: Issue #529 — admin known-npcs endpoint uses location_npc_assignments (V2), not deprecated npc_locations."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


def _make_db():
    """Minimal DB with V2 NPC assignment tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            ai_generated INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            current_location_id INTEGER,
            session_flags TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL,
            label TEXT NOT NULL,
            npc_type TEXT NOT NULL DEFAULT 'neutral',
            is_ally INTEGER NOT NULL DEFAULT 0,
            description TEXT DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY,
            location_key TEXT NOT NULL,
            npc_key TEXT NOT NULL,
            assignment_type TEXT NOT NULL DEFAULT 'resident',
            notes TEXT DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(location_key, npc_key)
        );
        CREATE TABLE npc_locations (
            id INTEGER PRIMARY KEY,
            npc_id INTEGER NOT NULL,
            location_key TEXT NOT NULL
        );
        CREATE TABLE campaign_known_npcs (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            npc_name TEXT NOT NULL,
            notes TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY
        );
    """)
    return conn


def _query_world_npcs(conn, loc_keys: list) -> list:
    """Replicate the fixed query from admin.py — uses location_npc_assignments."""
    if not loc_keys:
        return []
    placeholders = ",".join("?" * len(loc_keys))
    rows = conn.execute(
        f"""SELECT n.key, n.label, n.npc_type, n.is_ally, n.description,
                   GROUP_CONCAT(lna.location_key) AS location_keys
            FROM npcs n
            JOIN location_npc_assignments lna ON n.key = lna.npc_key
            WHERE lna.location_key IN ({placeholders}) AND lna.is_active = 1
            GROUP BY n.id""",
        loc_keys,
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Tests ──────────────────────────────────────────────────────────────────

def test_world_npc_returned_via_location_npc_assignments():
    """NPC assigned in location_npc_assignments is returned by the fixed query."""
    conn = _make_db()
    conn.execute("INSERT INTO npcs (id, key, label, npc_type) VALUES (1, 'innkeeper', 'Karczmarz', 'neutral')")
    conn.execute("INSERT INTO location_npc_assignments (location_key, npc_key, is_active) VALUES ('tavern', 'innkeeper', 1)")
    conn.commit()

    result = _query_world_npcs(conn, ["tavern"])
    assert len(result) == 1, "Expected 1 NPC from location_npc_assignments"
    assert result[0]["key"] == "innkeeper", f"Got {result[0]['key']}"


def test_inactive_assignment_not_returned():
    """NPC with is_active=0 in location_npc_assignments must NOT appear in results."""
    conn = _make_db()
    conn.execute("INSERT INTO npcs (id, key, label, npc_type) VALUES (2, 'ghost', 'Duch', 'neutral')")
    conn.execute("INSERT INTO location_npc_assignments (location_key, npc_key, is_active) VALUES ('ruins', 'ghost', 0)")
    conn.commit()

    result = _query_world_npcs(conn, ["ruins"])
    assert len(result) == 0, "Inactive NPC should not appear"


def test_deprecated_npc_locations_not_used():
    """NPC in old npc_locations table (no entry in location_npc_assignments) does NOT appear."""
    conn = _make_db()
    conn.execute("INSERT INTO npcs (id, key, label, npc_type) VALUES (3, 'oldguard', 'Stary strażnik', 'neutral')")
    # Insert only into deprecated table, NOT into location_npc_assignments
    conn.execute("INSERT INTO npc_locations (npc_id, location_key) VALUES (3, 'fortress')")
    conn.commit()

    result = _query_world_npcs(conn, ["fortress"])
    assert len(result) == 0, "Deprecated npc_locations table must NOT be used"


def test_multiple_npcs_multiple_locations():
    """Multiple NPCs at multiple locations all returned correctly."""
    conn = _make_db()
    conn.execute("INSERT INTO npcs (id, key, label, npc_type) VALUES (4, 'merchant', 'Kupiec', 'neutral')")
    conn.execute("INSERT INTO npcs (id, key, label, npc_type) VALUES (5, 'guard', 'Strażnik', 'neutral')")
    conn.execute("INSERT INTO location_npc_assignments (location_key, npc_key, is_active) VALUES ('market', 'merchant', 1)")
    conn.execute("INSERT INTO location_npc_assignments (location_key, npc_key, is_active) VALUES ('gate', 'guard', 1)")
    conn.commit()

    result = _query_world_npcs(conn, ["market", "gate"])
    keys = {r["key"] for r in result}
    assert keys == {"merchant", "guard"}
