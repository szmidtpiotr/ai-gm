"""TDD: Issue #516 — character_rentals table must exist after run_admin_migrations()."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.migrations_admin import ADMIN_MIGRATIONS
from app.services.rental_service import expire_rentals


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_migrated_db() -> sqlite3.Connection:
    """Run every ADMIN_MIGRATIONS statement on a fresh in-memory DB."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")  # avoid FK deps on missing tables
    for sql in ADMIN_MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # skip stmts that need parent tables absent in isolation
    conn.commit()
    return conn


# ─── Tests ──────────────────────────────────────────────────────────────────

def test_character_rentals_table_exists_after_migration():
    """ADMIN_MIGRATIONS must create character_rentals table."""
    conn = _make_migrated_db()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "character_rentals" in tables, "character_rentals not created by ADMIN_MIGRATIONS (#516)"


def test_character_rentals_has_required_columns():
    """character_rentals must have status, expires_at_turn, inventory_id, campaign_id columns."""
    conn = _make_migrated_db()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(character_rentals)")}
    for col in ("status", "expires_at_turn", "inventory_id", "campaign_id"):
        assert col in cols, f"column '{col}' missing from character_rentals (#516)"


def test_expire_rentals_no_exception_on_migrated_db():
    """expire_rentals() must not raise on an empty-but-migrated DB."""
    conn = _make_migrated_db()
    # also need campaign_turns for get_current_turn
    conn.execute("""
        CREATE TABLE IF NOT EXISTS campaign_turns (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            turn_number INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS character_inventory (
            id INTEGER PRIMARY KEY,
            character_id INTEGER NOT NULL,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            source TEXT DEFAULT '', equipped INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    # Should not raise — empty table is fine
    expire_rentals(conn=conn, campaign_id=1, current_turn=10)


def test_existing_expire_rentals_test_still_passes():
    """Backward compat: rental_service still works with manually-created schema (test #473 pattern)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE character_rentals (
            id INTEGER PRIMARY KEY,
            character_id INTEGER NOT NULL,
            campaign_id INTEGER,
            npc_id INTEGER NOT NULL DEFAULT 1,
            item_type TEXT NOT NULL DEFAULT 'misc',
            item_key TEXT NOT NULL DEFAULT 'room',
            label TEXT NOT NULL DEFAULT 'Wynajęta kwatera',
            rental_fee_gp INTEGER NOT NULL DEFAULT 10,
            total_paid_gp INTEGER NOT NULL DEFAULT 10,
            duration_turns INTEGER NOT NULL DEFAULT 5,
            rented_at_turn INTEGER NOT NULL DEFAULT 1,
            expires_at_turn INTEGER NOT NULL,
            inventory_id INTEGER,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY,
            character_id INTEGER NOT NULL,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            source TEXT DEFAULT '', equipped INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            turn_number INTEGER NOT NULL DEFAULT 1
        );
    """)
    expire_rentals(conn=conn, campaign_id=1, current_turn=10)
