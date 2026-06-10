"""TDD: Issue #479 — F19 global NPC death states.

When an NPC is killed in one campaign, they remain dead globally.
The is_dead flag on the npcs table is the single source of truth.

Design:
  - npcs.is_dead (INTEGER DEFAULT 0) — global death flag
  - mark_npc_dead_global(conn, npc_key) — sets is_dead=1
  - is_npc_dead_global(conn, npc_key) — checks the flag
  - get_living_npcs(conn) — returns only is_dead=0 NPCs
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlite3
import pytest

from app.services.npc_global_death_service import (
    mark_npc_dead_global,
    is_npc_dead_global,
    get_living_npcs,
    revive_npc,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            is_dead INTEGER DEFAULT 0
        );
        INSERT INTO npcs (key, label) VALUES
          ('innkeeper_jan', 'Karczmar Jan'),
          ('blacksmith_anna', 'Kowal Anna'),
          ('merchant_piotr', 'Kupiec Piotr');
    """)
    conn.commit()
    return conn


# ─── mark_npc_dead_global ────────────────────────────────────────────────────

def test_mark_npc_dead_sets_flag(db):
    """mark_npc_dead_global sets is_dead=1 on the NPC row."""
    mark_npc_dead_global(db, "innkeeper_jan")
    row = db.execute("SELECT is_dead FROM npcs WHERE key = 'innkeeper_jan'").fetchone()
    assert row["is_dead"] == 1


def test_mark_unknown_npc_is_noop(db):
    """Marking a nonexistent NPC key does nothing (no exception)."""
    mark_npc_dead_global(db, "nonexistent_npc")  # must not raise
    count = db.execute("SELECT COUNT(*) FROM npcs WHERE is_dead = 1").fetchone()[0]
    assert count == 0


def test_mark_already_dead_npc_is_idempotent(db):
    """Marking an already-dead NPC twice is idempotent."""
    mark_npc_dead_global(db, "innkeeper_jan")
    mark_npc_dead_global(db, "innkeeper_jan")  # second call must not raise
    row = db.execute("SELECT is_dead FROM npcs WHERE key = 'innkeeper_jan'").fetchone()
    assert row["is_dead"] == 1


# ─── is_npc_dead_global ──────────────────────────────────────────────────────

def test_living_npc_not_dead(db):
    """An NPC not marked dead returns False."""
    assert not is_npc_dead_global(db, "innkeeper_jan")


def test_dead_npc_is_dead(db):
    """After mark, is_npc_dead_global returns True."""
    mark_npc_dead_global(db, "innkeeper_jan")
    assert is_npc_dead_global(db, "innkeeper_jan")


def test_unknown_npc_not_dead(db):
    """Unknown NPC key returns False (not dead = doesn't exist)."""
    assert not is_npc_dead_global(db, "ghost_npc")


# ─── get_living_npcs ─────────────────────────────────────────────────────────

def test_get_living_npcs_excludes_dead(db):
    """get_living_npcs excludes NPCs with is_dead=1."""
    mark_npc_dead_global(db, "innkeeper_jan")
    living = get_living_npcs(db)
    keys = [n["key"] for n in living]
    assert "innkeeper_jan" not in keys
    assert "blacksmith_anna" in keys
    assert "merchant_piotr" in keys


def test_get_living_npcs_all_alive_initially(db):
    """Without any deaths, all NPCs returned."""
    living = get_living_npcs(db)
    assert len(living) == 3


def test_get_living_npcs_empty_when_all_dead(db):
    """All dead → empty list."""
    for key in ("innkeeper_jan", "blacksmith_anna", "merchant_piotr"):
        mark_npc_dead_global(db, key)
    assert get_living_npcs(db) == []


# ─── revive_npc ──────────────────────────────────────────────────────────────

def test_revive_npc_clears_flag(db):
    """revive_npc resets is_dead=0 (for admin use / narrative resurrection)."""
    mark_npc_dead_global(db, "innkeeper_jan")
    assert is_npc_dead_global(db, "innkeeper_jan")
    revive_npc(db, "innkeeper_jan")
    assert not is_npc_dead_global(db, "innkeeper_jan")


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_npc_without_is_dead_column_handled_gracefully():
    """Table without is_dead column (old schema) doesn't crash get_living_npcs."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE npcs (id INTEGER PRIMARY KEY, key TEXT UNIQUE, label TEXT, is_active INTEGER DEFAULT 1);
        INSERT INTO npcs (key, label) VALUES ('old_npc', 'Old NPC');
    """)
    conn.commit()
    # Should not raise — returns all NPCs when column missing
    try:
        result = get_living_npcs(conn)
        # Either works or returns all NPCs gracefully
    except Exception as e:
        pytest.fail(f"get_living_npcs raised on missing column: {e}")
