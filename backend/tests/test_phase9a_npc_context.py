"""Phase 9A-3 — NPC context block injection and filtering tests."""

import sqlite3

import pytest

from app.services.game_engine import build_npc_context_block, _inject_npc_llm_context


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL
        );
        CREATE TABLE game_sessions (
            id TEXT PRIMARY KEY,
            campaign_id INTEGER,
            current_location_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            npc_type TEXT NOT NULL,
            description TEXT,
            personality_json TEXT NOT NULL DEFAULT '{}',
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE npc_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            npc_id INTEGER NOT NULL,
            location_key TEXT NOT NULL,
            UNIQUE(npc_id, location_key)
        );
        """
    )
    c.execute("INSERT INTO game_locations(id, key, label) VALUES (1, 'inn_main', 'Karczma')")
    c.execute("INSERT INTO game_locations(id, key, label) VALUES (2, 'market', 'Rynek')")
    c.execute("INSERT INTO game_sessions(id, campaign_id, current_location_id) VALUES ('7', 7, 1)")
    c.execute(
        """
        INSERT INTO npcs(key, label, npc_type, description, personality_json, is_active)
        VALUES
        ('merchant_aldric', 'Aldric', 'merchant', 'Kupiec', '{"personality":"sknerski","topics":["handel"],"secret":null}', 1),
        ('innkeeper_marta', 'Marta', 'neutral', 'Karczmarka', '{"personality":"serdeczna","topics":["plotki"],"secret":null}', 1),
        ('quest_eldran', 'Eldran', 'quest_giver', 'Mag', '{"personality":"enigmatyczny","topics":["artefakty"],"secret":"tom"}', 1),
        ('inactive_npc', 'Nieaktywny', 'neutral', 'Nieaktywny', '{"personality":"cichy","topics":[],"secret":null}', 0)
        """
    )
    # Marta assigned to inn_main; Aldric and Eldran remain global.
    c.execute(
        "INSERT INTO npc_locations(npc_id, location_key) SELECT id, 'inn_main' FROM npcs WHERE key='innkeeper_marta'"
    )
    c.commit()
    try:
        yield c
    finally:
        c.close()


def test_build_npc_context_returns_all_global_npcs_without_session_location(conn):
    conn.execute("UPDATE game_sessions SET current_location_id = NULL WHERE campaign_id = 7")
    conn.commit()
    block = build_npc_context_block(conn, 7)
    assert block
    assert "Aldric" in block
    assert "Eldran" in block
    assert "Marta" not in block  # location-bound should not appear without current location


def test_build_npc_context_filters_by_location(conn):
    block = build_npc_context_block(conn, 7)
    assert block
    assert "Marta" in block  # assigned to inn_main
    assert "Aldric" in block  # global
    assert "Eldran" in block  # global


def test_build_npc_context_excludes_inactive_npcs(conn):
    block = build_npc_context_block(conn, 7)
    assert block
    assert "Nieaktywny" not in block


def test_build_npc_context_returns_empty_when_no_npcs(conn):
    conn.execute("UPDATE npcs SET is_active = 0")
    conn.commit()
    assert build_npc_context_block(conn, 7) is None


def test_build_npc_context_includes_personality(conn):
    block = build_npc_context_block(conn, 7)
    assert block
    assert "personality: sknerski" in block
    assert "topics: handel" in block


def test_npc_context_injected_in_messages(conn):
    messages = [{"role": "system", "content": "base prompt"}]
    _inject_npc_llm_context(conn, 7, messages)
    assert len(messages) == 2
    assert messages[1]["role"] == "system"
    assert "[NPC CONTEXT]" in messages[1]["content"]
