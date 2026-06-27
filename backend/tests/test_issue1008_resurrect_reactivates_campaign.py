"""TDD: Issue #1008 — resurrect reaktywuje zakończoną kampanię → treść znów osiągalna.

Backend invariant gwarantujący, że po wskrzeszeniu front MOŻE pobrać tury:
`get_active_campaign_or_gone` zwraca 410 dla status='ended'. apply_resurrection MUSI
przełączyć kampanię ended→active (i wyczyścić death_reason/ended_at/epitaph), inaczej
gracz po wskrzeszeniu dostaje 410 → pusty czat. Fix frontowy (enterGame→hideDeathScreen)
pokryty Playwright spec issue_1008_resurrect_death_overlay.spec.js.
"""
import sys
sys.path.insert(0, "/app")

import json
import sqlite3
import pytest

from app.services.resurrection_service import apply_resurrection
from _fixtures_schema import table_sql


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        table_sql("game_config_meta") + """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, username TEXT,
            resurrection_enabled INTEGER NOT NULL DEFAULT 0,
            resurrection_cost_mode TEXT NOT NULL DEFAULT 'admin_free',
            resurrection_cost_value INTEGER NOT NULL DEFAULT 25,
            resurrection_cost_cap_percent INTEGER NOT NULL DEFAULT 50,
            resurrection_uses_remaining INTEGER
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
            name TEXT, sheet_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'active', gold_gp INTEGER DEFAULT 0
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active',
            death_reason TEXT, ended_at TEXT, epitaph TEXT
        );
        CREATE TABLE game_sessions (
            campaign_id INTEGER, session_flags TEXT DEFAULT '{}'
        );
        CREATE TABLE character_xp_grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, amount INTEGER,
            created_at TEXT DEFAULT '2026-01-01', reverted_at TEXT
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, delta INTEGER,
            source TEXT, meta_json TEXT, game_clock_day INTEGER,
            wall_clock_at TEXT DEFAULT '2026-01-01', reverted_at TEXT
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, item_key TEXT,
            weapon_key TEXT, consumable_key TEXT, quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0, slot TEXT, label TEXT, meta_json TEXT
        );
        CREATE TABLE character_spells (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, spell_key TEXT,
            rank INTEGER DEFAULT 1, learned_at_level INTEGER
        );
        CREATE TABLE character_dungeon_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER,
            dungeon_key TEXT, cooldown_until TEXT
        );
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_items") + """
        """ + table_sql("game_config_consumables") + """

        INSERT INTO users (id, username) VALUES (1, 'tester');
        -- Solo-death state: campaign ended, hero dead, clock session present
        INSERT INTO campaigns (id, title, status, death_reason, ended_at, epitaph)
            VALUES (200, 'Ended Run', 'ended', 'solo_death', '2026-06-27 20:00:00', 'RIP');
        INSERT INTO game_sessions (campaign_id, session_flags) VALUES (200, '{"ingame_hours": 24}');
        INSERT INTO characters (id, user_id, campaign_id, name, status, gold_gp, sheet_json)
            VALUES (30, 1, 200, 'Dead Hero', 'dead', 50,
                '{"archetype":"warrior","level":2,"current_hp":0,"max_hp":14}');
    """
    )
    return conn


# ─── Test główny — resurrect reaktywuje zakończoną kampanię ──────────────────────────

def test_resurrect_reactivates_ended_campaign(db):
    """Po wskrzeszeniu kampania ended→active i death-pola wyczyszczone (inaczej /turns → 410)."""
    apply_resurrection(30, 1, db, force=True)
    camp = db.execute("SELECT status, death_reason, ended_at, epitaph FROM campaigns WHERE id=200").fetchone()
    assert camp["status"] == "active", "kampania musi wrócić do active po wskrzeszeniu"
    assert camp["death_reason"] is None
    assert camp["ended_at"] is None
    assert camp["epitaph"] is None


def test_resurrect_revives_hero_hp_and_status(db):
    """Bohater żywy z HP>0 po wskrzeszeniu (status=active)."""
    result = apply_resurrection(30, 1, db, force=True)
    assert result["revived_hp"] == 7  # max_hp//2 = 14//2
    char = db.execute("SELECT status, sheet_json FROM characters WHERE id=30").fetchone()
    assert char["status"] == "active"
    assert json.loads(char["sheet_json"])["current_hp"] == 7


# ─── Backward compat — active campaign nie jest ruszana ──────────────────────────────

def test_resurrect_does_not_touch_already_active_campaign(db):
    """Kampania już active (np. permadeath off) — reactivation no-op, brak wyjątku."""
    db.execute("UPDATE campaigns SET status='active', death_reason=NULL, ended_at=NULL WHERE id=200")
    db.commit()
    apply_resurrection(30, 1, db, force=True)
    camp = db.execute("SELECT status FROM campaigns WHERE id=200").fetchone()
    assert camp["status"] == "active"
