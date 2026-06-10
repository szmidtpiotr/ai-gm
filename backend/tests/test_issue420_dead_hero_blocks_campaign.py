"""TDD: Issue #420 E5 — dead hero blocks campaign access."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    """In-memory SQLite with minimal schema for dead hero blocking tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'idle',
            campaign_id INTEGER,
            sheet_json TEXT DEFAULT '{}'
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            owner_user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            system_id TEXT DEFAULT 'fantasy',
            model_id TEXT DEFAULT 'default',
            language TEXT DEFAULT 'pl',
            mode TEXT DEFAULT 'solo',
            created_at TEXT DEFAULT (datetime('now')),
            gm_plan_json TEXT DEFAULT '{}'
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            character_id INTEGER,
            session_flags TEXT DEFAULT '{}'
        );
    """)
    return conn


# ─── Test główny: dead hero blocks campaign ──────────────────────────────────

def test_dead_hero_campaign_returns_blocked_flag():
    """When hero_status=dead, campaign response must include hero_blocked=true."""
    conn = _make_db()
    conn.execute(
        """INSERT INTO characters (id, name, status, campaign_id)
           VALUES (1, 'Martwy Bohater', 'dead', 100)"""
    )
    conn.execute(
        """INSERT INTO campaigns (id, title, owner_user_id)
           VALUES (100, '#420', 1)"""
    )
    conn.execute(
        """INSERT INTO game_sessions (campaign_id, character_id)
           VALUES (100, 1)"""
    )
    conn.commit()

    # Fetch campaign with dead hero
    from app.api.campaigns import _get_campaign_with_hero_state
    campaign = _get_campaign_with_hero_state(conn, campaign_id=100)

    assert campaign is not None, "Campaign must be found"
    assert campaign.get("hero_blocked") == True, (
        "Campaign with dead hero must have hero_blocked=True"
    )
    assert campaign.get("hero_status") == "dead", (
        "Campaign response must include hero_status field"
    )


def test_dead_hero_blocks_turns_endpoint():
    """POST /api/campaigns/{id}/turns must reject if hero_status=dead."""
    conn = _make_db()
    conn.execute(
        """INSERT INTO characters (id, name, status, campaign_id)
           VALUES (2, 'Inny Bohater', 'dead', 101)"""
    )
    conn.execute(
        """INSERT INTO campaigns (id, title, owner_user_id)
           VALUES (101, '#420-test', 1)"""
    )
    conn.execute(
        """INSERT INTO game_sessions (campaign_id, character_id)
           VALUES (101, 2)"""
    )
    conn.commit()

    from app.api.campaigns import _check_hero_dead
    is_blocked = _check_hero_dead(conn, campaign_id=101, character_id=2)

    assert is_blocked == True, (
        "Campaign with dead hero must be blocked from turns"
    )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_alive_hero_campaign_not_blocked():
    """When hero_status=in_campaign, hero_blocked must be False."""
    conn = _make_db()
    conn.execute(
        """INSERT INTO characters (id, name, status, campaign_id)
           VALUES (3, 'Żywy Bohater', 'in_campaign', 102)"""
    )
    conn.execute(
        """INSERT INTO campaigns (id, title, owner_user_id)
           VALUES (102, '#420-alive', 1)"""
    )
    conn.execute(
        """INSERT INTO game_sessions (campaign_id, character_id)
           VALUES (102, 3)"""
    )
    conn.commit()

    from app.api.campaigns import _get_campaign_with_hero_state
    campaign = _get_campaign_with_hero_state(conn, campaign_id=102)

    assert campaign.get("hero_blocked") == False or campaign.get("hero_blocked") is None, (
        "Alive hero campaign must NOT be blocked"
    )
