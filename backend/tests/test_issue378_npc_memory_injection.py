"""TDD: Issue #378 acceptance #2 — NPC memory context injection into LLM messages."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    """In-memory SQLite with minimal schema for NPC memory injection tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE campaign_known_npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            npc_id INTEGER,
            npc_name TEXT NOT NULL,
            role TEXT,
            first_met_location TEXT,
            first_met_turn INTEGER,
            notes TEXT,
            relation_status TEXT NOT NULL DEFAULT 'neutral',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            purchase_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(campaign_id, npc_name)
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            npc_type TEXT,
            description TEXT,
            personality_json TEXT,
            is_shop INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            current_location_id INTEGER,
            session_flags TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT
        );
        CREATE TABLE npc_locations (
            npc_id INTEGER NOT NULL,
            location_key TEXT NOT NULL
        );
    """)
    return conn


def _make_messages() -> list[dict]:
    return [
        {"role": "system", "content": "System prompt here."},
        {"role": "user", "content": "Wchodzę do wioski."},
    ]


# ── FAZA 1: RED tests ─────────────────────────────────────────────────────────

def test_known_npc_memory_injected_into_messages():
    """When campaign_known_npcs has entries, messages must contain ### ZNANI NPC block."""
    conn = _make_db()
    conn.execute(
        """INSERT INTO campaign_known_npcs
           (campaign_id, npc_name, notes, relation_status)
           VALUES (42, 'Borun', 'bohater pomógł mu naprawić kowadło i oddał pilnik', 'friendly')"""
    )
    conn.commit()

    messages = _make_messages()

    from app.services.game_engine import _inject_known_npc_memory_context
    _inject_known_npc_memory_context(conn, campaign_id=42, messages=messages)

    all_content = " ".join(m["content"] for m in messages)
    assert "ZNANI NPC" in all_content, (
        "Messages do not contain ### ZNANI NPC block — NPC memory was NOT injected"
    )
    assert "Borun" in all_content, "NPC name 'Borun' missing from injected context"
    assert "naprawić kowadło" in all_content, "NPC notes missing from injected context"


def test_known_npc_memory_empty_when_no_npcs():
    """When campaign_known_npcs is empty, no extra system message is added."""
    conn = _make_db()
    messages = _make_messages()
    original_len = len(messages)

    from app.services.game_engine import _inject_known_npc_memory_context
    _inject_known_npc_memory_context(conn, campaign_id=99, messages=messages)

    assert len(messages) == original_len, (
        f"Messages grew from {original_len} to {len(messages)} despite no known NPCs"
    )


# ── Backward compatibility ────────────────────────────────────────────────────

def test_build_npc_context_block_unaffected():
    """Existing _inject_npc_llm_context (world NPCs) still works without change."""
    from app.services.game_engine import build_npc_context_block
    conn = _make_db()
    # No NPCs in DB → must return None (not raise)
    result = build_npc_context_block(conn, campaign_id=1)
    assert result is None or result == "", (
        "build_npc_context_block broke — backward compat failed"
    )


def test_format_known_npcs_block_output():
    """format_known_npcs_block returns correct block header and NPC line."""
    from app.services.npc_memory_service import format_known_npcs_block
    rows = [{"npc_name": "Lyra", "role": "strażniczka", "notes": "nieufna wobec obcych",
             "relation_status": "neutral", "first_met_location": None,
             "purchase_count": 0, "catalog_description": None, "catalog_personality_json": None, "is_shop": 0}]
    block = format_known_npcs_block(rows)
    assert "ZNANI NPC" in block
    assert "Lyra" in block
    assert "nieufna wobec obcych" in block
