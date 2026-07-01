"""TDD: Issue #1074 — Player inventory drop button + confirmation.

Verifies backend API contract for DELETE /inventory/{char_id}/{inv_id}:
- Non-equipped items can be deleted freely
- Equipped items are blocked unless force=True
- Quest-type items are NOT blocked server-side (frontend guards this)
- Unknown char/item returns 404-equivalent error
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest


# ── In-memory DB helpers ──────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            item_key TEXT,
            weapon_key TEXT,
            consumable_key TEXT,
            quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0,
            slot TEXT,
            source TEXT DEFAULT 'loot',
            acquired_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (character_id) REFERENCES characters(id)
        );
    """)
    conn.commit()
    return conn


def _seed(conn, char_id=1, item_key="health_potion", equipped=0, slot=None, qty=1):
    conn.execute("INSERT OR IGNORE INTO characters (id, name) VALUES (?, 'TestHero')", (char_id,))
    cur = conn.execute(
        "INSERT INTO character_inventory (character_id, item_key, quantity, equipped, slot) VALUES (?, ?, ?, ?, ?)",
        (char_id, item_key, qty, int(equipped), slot),
    )
    conn.commit()
    return cur.lastrowid


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_delete_nonequipped_item_succeeds():
    """Non-equipped backpack item can be freely deleted."""
    from app.services import loot_service
    conn = _make_db()
    inv_id = _seed(conn, item_key="health_potion", equipped=0)

    # Patch service connection
    original = loot_service._conn
    loot_service._conn = lambda: conn
    try:
        result = loot_service.delete_inventory_item(1, inv_id, force=False)
        assert result["id"] == inv_id
        assert result["item_key"] == "health_potion"
        # Verify actually deleted
        row = conn.execute("SELECT id FROM character_inventory WHERE id=?", (inv_id,)).fetchone()
        assert row is None
    finally:
        loot_service._conn = original


def test_delete_equipped_item_blocked_without_force():
    """Equipped item raises ValueError without force=True."""
    from app.services import loot_service
    conn = _make_db()
    inv_id = _seed(conn, item_key="iron_sword", equipped=1, slot="main_hand")

    original = loot_service._conn
    loot_service._conn = lambda: conn
    try:
        with pytest.raises(ValueError, match="equipped item requires force"):
            loot_service.delete_inventory_item(1, inv_id, force=False)
        # Item must still be in DB
        row = conn.execute("SELECT id FROM character_inventory WHERE id=?", (inv_id,)).fetchone()
        assert row is not None
    finally:
        loot_service._conn = original


def test_delete_equipped_item_allowed_with_force():
    """Equipped item can be deleted with force=True (admin drop)."""
    from app.services import loot_service
    conn = _make_db()
    inv_id = _seed(conn, item_key="iron_sword", equipped=1, slot="main_hand")

    original = loot_service._conn
    loot_service._conn = lambda: conn
    try:
        result = loot_service.delete_inventory_item(1, inv_id, force=True)
        assert result["id"] == inv_id
        row = conn.execute("SELECT id FROM character_inventory WHERE id=?", (inv_id,)).fetchone()
        assert row is None
    finally:
        loot_service._conn = original


def test_delete_quest_item_not_blocked_server_side():
    """Backend does NOT block quest items — frontend is responsible for the guard.

    This is intentional: force=True from admin can remove any item.
    The no-drop protection for quest items is purely a UI/frontend concern.
    """
    from app.services import loot_service
    conn = _make_db()
    inv_id = _seed(conn, item_key="quest_amulet_of_doom", equipped=0)

    original = loot_service._conn
    loot_service._conn = lambda: conn
    try:
        result = loot_service.delete_inventory_item(1, inv_id, force=False)
        assert result["id"] == inv_id
    finally:
        loot_service._conn = original


def test_delete_missing_character_raises():
    """Unknown character_id raises ValueError."""
    from app.services import loot_service
    conn = _make_db()

    original = loot_service._conn
    loot_service._conn = lambda: conn
    try:
        with pytest.raises(ValueError, match="character not found"):
            loot_service.delete_inventory_item(9999, 1, force=False)
    finally:
        loot_service._conn = original


def test_delete_missing_inventory_entry_raises():
    """Unknown inventory_id raises ValueError."""
    from app.services import loot_service
    conn = _make_db()
    conn.execute("INSERT INTO characters (id, name) VALUES (1, 'TestHero')")
    conn.commit()

    original = loot_service._conn
    loot_service._conn = lambda: conn
    try:
        with pytest.raises(ValueError, match="inventory entry not found"):
            loot_service.delete_inventory_item(1, 9999, force=False)
    finally:
        loot_service._conn = original


# ── Backward compat ───────────────────────────────────────────────────────────

def test_delete_stacked_item_removes_whole_entry():
    """Stacked items (qty > 1) are fully removed — no partial-drop yet."""
    from app.services import loot_service
    conn = _make_db()
    inv_id = _seed(conn, item_key="arrows", qty=20, equipped=0)

    original = loot_service._conn
    loot_service._conn = lambda: conn
    try:
        result = loot_service.delete_inventory_item(1, inv_id, force=False)
        assert result["quantity"] == 20
        row = conn.execute("SELECT id FROM character_inventory WHERE id=?", (inv_id,)).fetchone()
        assert row is None
    finally:
        loot_service._conn = original
