"""TDD: Issue #982 — _get_location_npcs parent-fallback for sub-locations."""
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.location_context_injector import _get_location_npcs


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL,
            label TEXT,
            parent_id INTEGER,
            is_active INTEGER DEFAULT 1,
            approved INTEGER DEFAULT 1
        );
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY,
            location_key TEXT NOT NULL,
            npc_key TEXT NOT NULL,
            assignment_type TEXT DEFAULT 'resident',
            is_active INTEGER DEFAULT 1
        );
    """)
    return conn


def test_sublocation_inherits_parent_npcs_when_own_empty():
    """Sub-location with 0 NPCs returns hub NPCs via parent-fallback."""
    conn = _make_db()
    conn.execute("INSERT INTO game_locations (id, key, label) VALUES (1, 'wolanka', 'Wolanka')")
    conn.execute("INSERT INTO game_locations (id, key, label, parent_id) VALUES (2, 'wolanka_kuznia', 'Wolanka: Kuźnia Wujka', 1)")
    conn.execute("INSERT INTO location_npc_assignments (location_key, npc_key, assignment_type) VALUES ('wolanka', 'kowal_wolanka', 'resident')")
    conn.commit()

    npcs = _get_location_npcs(conn, "wolanka_kuznia")
    assert len(npcs) == 1, f"Expected 1 NPC from parent fallback, got {len(npcs)}"
    assert npcs[0]["npc_key"] == "kowal_wolanka"


def test_sublocation_own_npcs_not_overridden():
    """Sub-location with own NPCs must NOT get parent NPCs on top."""
    conn = _make_db()
    conn.execute("INSERT INTO game_locations (id, key, label) VALUES (1, 'wolanka', 'Wolanka')")
    conn.execute("INSERT INTO game_locations (id, key, label, parent_id) VALUES (2, 'wolanka_kuznia', 'Wolanka: Kuźnia Wujka', 1)")
    conn.execute("INSERT INTO location_npc_assignments (location_key, npc_key, assignment_type) VALUES ('wolanka', 'kowal_wolanka', 'resident')")
    conn.execute("INSERT INTO location_npc_assignments (location_key, npc_key, assignment_type) VALUES ('wolanka_kuznia', 'pomocnik_kuzni', 'resident')")
    conn.commit()

    npcs = _get_location_npcs(conn, "wolanka_kuznia")
    keys = [n["npc_key"] for n in npcs]
    assert "pomocnik_kuzni" in keys, "Own NPC must be present"
    assert "kowal_wolanka" not in keys, "Parent NPC must NOT appear when sub has own NPCs"
    assert len(npcs) == 1


def test_hub_location_backward_compat():
    """Hub location (no parent) works exactly as before."""
    conn = _make_db()
    conn.execute("INSERT INTO game_locations (id, key, label) VALUES (1, 'wolanka', 'Wolanka')")
    conn.execute("INSERT INTO location_npc_assignments (location_key, npc_key, assignment_type) VALUES ('wolanka', 'starszy_gornik_wolanka', 'resident')")
    conn.commit()

    npcs = _get_location_npcs(conn, "wolanka")
    assert len(npcs) == 1
    assert npcs[0]["npc_key"] == "starszy_gornik_wolanka"


def test_no_npcs_anywhere_returns_empty():
    """Neither sub nor parent has NPCs → return []."""
    conn = _make_db()
    conn.execute("INSERT INTO game_locations (id, key, label) VALUES (1, 'ghost_hub', 'Ghost Hub')")
    conn.execute("INSERT INTO game_locations (id, key, label, parent_id) VALUES (2, 'ghost_sub', 'Ghost Sub', 1)")
    conn.commit()

    npcs = _get_location_npcs(conn, "ghost_sub")
    assert npcs == []
