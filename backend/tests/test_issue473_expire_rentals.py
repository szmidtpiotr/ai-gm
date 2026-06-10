"""TDD: Issue #473 — Background expire sweep for character_rentals."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.rental_service import expire_rentals, get_current_turn


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_db():
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
            item_key TEXT,
            weapon_key TEXT,
            consumable_key TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            source TEXT DEFAULT '',
            equipped INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            turn_number INTEGER NOT NULL DEFAULT 1
        );

        -- Expired rental (turn 5 → expires_at=3, inventory_id set)
        INSERT INTO character_rentals VALUES (1, 10, 1, 1, 'misc', 'room', 'Kwatera', 10, 10, 3, 1, 3, 42, 'active', datetime('now'), datetime('now'));
        -- Active rental (expires at turn 10 — not yet expired at turn 5)
        INSERT INTO character_rentals VALUES (2, 10, 1, 1, 'misc', 'room2', 'Kwatera2', 20, 20, 10, 1, 10, NULL, 'active', datetime('now'), datetime('now'));
        -- Already expired rental (should not be touched again)
        INSERT INTO character_rentals VALUES (3, 10, 1, 1, 'misc', 'buff', 'Buff', 5, 5, 2, 1, 2, NULL, 'expired', datetime('now'), datetime('now'));
        -- Rental with inventory item for different campaign
        INSERT INTO character_rentals VALUES (4, 10, 2, 1, 'misc', 'room', 'Kwatera', 10, 10, 3, 1, 3, 43, 'active', datetime('now'), datetime('now'));

        -- Inventory item for rental #1
        INSERT INTO character_inventory VALUES (42, 10, 'room', NULL, NULL, 1, 'rental', 0);
        -- Inventory item for rental #4 (different campaign)
        INSERT INTO character_inventory VALUES (43, 10, 'room', NULL, NULL, 1, 'rental', 0);

        -- Campaign turns: campaign 1 is at turn 5
        INSERT INTO campaign_turns VALUES (1, 1, 1);
        INSERT INTO campaign_turns VALUES (2, 1, 3);
        INSERT INTO campaign_turns VALUES (3, 1, 5);
    """)
    return conn


# ─── expire_rentals core behavior ────────────────────────────────────────────

def test_expire_rentals_returns_count_of_expired():
    conn = _make_db()
    count = expire_rentals(conn, campaign_id=1, current_turn=5)
    assert count == 1, f"Expected 1 expired, got {count}"


def test_expire_rentals_marks_status_expired():
    conn = _make_db()
    expire_rentals(conn, campaign_id=1, current_turn=5)
    row = conn.execute("SELECT status FROM character_rentals WHERE id = 1").fetchone()
    assert row["status"] == "expired"


def test_expire_rentals_removes_inventory_item():
    conn = _make_db()
    expire_rentals(conn, campaign_id=1, current_turn=5)
    # inventory_id=42 for rental#1 should be deleted
    row = conn.execute("SELECT id FROM character_inventory WHERE id = 42").fetchone()
    assert row is None, "Inventory item for expired rental should be deleted"


def test_expire_rentals_leaves_future_rentals_active():
    conn = _make_db()
    expire_rentals(conn, campaign_id=1, current_turn=5)
    row = conn.execute("SELECT status FROM character_rentals WHERE id = 2").fetchone()
    assert row["status"] == "active", "Rental expiring at turn 10 should stay active at turn 5"


def test_expire_rentals_does_not_retouch_already_expired():
    conn = _make_db()
    expire_rentals(conn, campaign_id=1, current_turn=5)
    # Rental#3 was already expired — no change expected
    row = conn.execute("SELECT status FROM character_rentals WHERE id = 3").fetchone()
    assert row["status"] == "expired"


def test_expire_rentals_only_affects_given_campaign():
    conn = _make_db()
    expire_rentals(conn, campaign_id=1, current_turn=5)
    # Rental#4 is campaign 2 — must still be active
    row = conn.execute("SELECT status FROM character_rentals WHERE id = 4").fetchone()
    assert row["status"] == "active", "Different campaign rental must not be expired"
    # Its inventory item must still exist
    inv = conn.execute("SELECT id FROM character_inventory WHERE id = 43").fetchone()
    assert inv is not None


def test_expire_rentals_returns_zero_when_nothing_to_expire():
    conn = _make_db()
    count = expire_rentals(conn, campaign_id=1, current_turn=1)
    assert count == 0


# ─── get_current_turn ────────────────────────────────────────────────────────

def test_get_current_turn_returns_max_turn():
    conn = _make_db()
    assert get_current_turn(conn, 1) == 5


def test_get_current_turn_returns_zero_for_new_campaign():
    conn = _make_db()
    assert get_current_turn(conn, 99) == 0


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_expire_rentals_no_inventory_id_does_not_crash():
    """Rental without inventory_id (e.g. buff NPC service) expires cleanly."""
    conn = _make_db()
    # Rental#2 has no inventory_id; at turn 10 it expires
    count = expire_rentals(conn, campaign_id=1, current_turn=10)
    # rental#1 already expired at turn 3 (re-called), rental#2 now expires
    assert count >= 1
    row = conn.execute("SELECT status FROM character_rentals WHERE id = 2").fetchone()
    assert row["status"] == "expired"
