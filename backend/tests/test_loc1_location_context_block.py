"""8D-LOC-1: build_location_context_block + graf known_locations (Opcja A)."""

import sqlite3

import pytest

from app.services.location_context_injector import (
    build_location_context_block,
    get_session_id_for_campaign,
)


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE game_sessions (
            id TEXT PRIMARY KEY,
            campaign_id INTEGER,
            current_location_id INTEGER,
            session_flags TEXT DEFAULT '{}',
            created_at TEXT DEFAULT 'now'
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            parent_id INTEGER REFERENCES game_locations(id),
            location_type TEXT DEFAULT 'macro',
            is_active INTEGER DEFAULT 1,
            approved INTEGER DEFAULT 1
        );
        """
    )
    return c


def test_build_location_context_block_returns_block(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO game_locations (id, key, label, location_type, parent_id) VALUES (1, 'village', 'Wioska', 'macro', NULL)"
    )
    conn.execute(
        "INSERT INTO game_locations (id, key, label, location_type, parent_id) VALUES (2, 'tavern', 'Karczma', 'sub', 1)"
    )
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id) VALUES ('42', 100, 2)"
    )
    conn.commit()

    block = build_location_context_block("42", conn)
    assert block is not None
    assert "[LOCATION CONTEXT]" in block
    assert "current_location:" in block
    assert '"key": "tavern"' in block
    assert "known_locations:" in block
    assert "village" in block and "Karczma" in block


def test_build_location_context_block_none_without_current(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id) VALUES ('1', 1, NULL)"
    )
    conn.commit()
    assert build_location_context_block("1", conn) is None


def test_get_session_id_for_campaign(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id) VALUES ('c9', 9, NULL)"
    )
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id) VALUES ('c9b', 9, NULL)"
    )
    conn.commit()
    # Newest by created_at same — order by id DESC → c9b
    sid = get_session_id_for_campaign(conn, 9)
    assert sid == "c9b"
