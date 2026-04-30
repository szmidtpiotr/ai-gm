"""Phase 9A-1 — migration tests for NPC schema and starter seed."""

import json
import sqlite3

import pytest


@pytest.fixture
def fresh_db_path(tmp_path):
    return str(tmp_path / "test_phase9a_npc_schema.db")


@pytest.fixture
def migrations_module(fresh_db_path):
    from app import migrations_admin

    original = migrations_admin.DB_PATH
    migrations_admin.DB_PATH = fresh_db_path
    try:
        yield migrations_admin
    finally:
        migrations_admin.DB_PATH = original


@pytest.fixture
def db_connection(fresh_db_path, migrations_module):
    migrations_module.run_admin_migrations()
    conn = sqlite3.connect(fresh_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn, migrations_module
    finally:
        conn.close()


def test_npcs_table_exists(db_connection):
    conn, _ = db_connection
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='npcs'"
    ).fetchone()
    assert row is not None


def test_npc_locations_table_exists(db_connection):
    conn, _ = db_connection
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='npc_locations'"
    ).fetchone()
    assert row is not None


def test_npc_seed_has_4_records(db_connection):
    conn, _ = db_connection
    n = conn.execute("SELECT COUNT(*) FROM npcs").fetchone()[0]
    assert int(n) >= 4


def test_merchant_aldric_is_shop(db_connection):
    conn, _ = db_connection
    row = conn.execute("SELECT is_shop FROM npcs WHERE key='merchant_aldric'").fetchone()
    assert row is not None
    assert int(row["is_shop"] or 0) == 1


def test_innkeeper_is_not_shop(db_connection):
    conn, _ = db_connection
    row = conn.execute("SELECT is_shop FROM npcs WHERE key='innkeeper_marta'").fetchone()
    assert row is not None
    assert int(row["is_shop"] or 0) == 0


def test_personality_json_is_valid(db_connection):
    conn, _ = db_connection
    rows = conn.execute("SELECT key, personality_json FROM npcs").fetchall()
    assert rows
    for row in rows:
        parsed = json.loads(row["personality_json"] or "{}")
        assert isinstance(parsed, dict), f"{row['key']} personality_json must be object"


def test_npc_locations_marta_assigned_when_inn_main_exists(db_connection):
    conn, migrations = db_connection
    conn.execute(
        "INSERT OR IGNORE INTO game_locations (key, label, location_type) VALUES (?, ?, ?)",
        ("inn_main", "Karczma", "sub"),
    )
    conn.commit()

    # Re-run migrations/seeds to apply conditional INSERT for Marta location.
    migrations.run_admin_migrations()

    conn2 = sqlite3.connect(migrations.DB_PATH)
    conn2.row_factory = sqlite3.Row
    try:
        row = conn2.execute(
            """
            SELECT nl.location_key
            FROM npc_locations nl
            JOIN npcs n ON n.id = nl.npc_id
            WHERE n.key = 'innkeeper_marta'
            """
        ).fetchone()
    finally:
        conn2.close()
    assert row is not None
    assert row["location_key"] == "inn_main"


def test_global_npcs_have_no_location_rows(db_connection):
    conn, _ = db_connection
    rows = conn.execute(
        """
        SELECT n.key
        FROM npcs n
        LEFT JOIN npc_locations nl ON nl.npc_id = n.id
        WHERE n.key IN ('merchant_aldric', 'quest_giver_eldran', 'blacksmith_goran')
          AND nl.id IS NOT NULL
        """
    ).fetchall()
    assert rows == []
