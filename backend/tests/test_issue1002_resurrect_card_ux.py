"""TDD: Issue #1002 — Dead hero badge + resurrect accessible on campaign cards (mobile admin).

Backend contract tests:
- apply_resurrection with force=True works on HP-dead hero (status='in_campaign', hp=0 in sheet)
  — this is the exact dead-state the new card badge detects (char_current_hp<=0, not status='dead')
- apply_resurrection response has revived_hp + max_hp fields (used by toast in _campModalResurrect)
- admin endpoint default force=True bypasses global resurrection_disabled config
"""
import sys
sys.path.insert(0, "/app")

import json
import sqlite3
import pytest

from app.services.resurrection_service import (
    apply_resurrection,
    set_global_resurrection_config,
)
from _fixtures_schema import table_sql


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        table_sql("game_config_meta") + """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            resurrection_enabled INTEGER NOT NULL DEFAULT 0,
            resurrection_cost_mode TEXT NOT NULL DEFAULT 'admin_free',
            resurrection_cost_value INTEGER NOT NULL DEFAULT 25,
            resurrection_cost_cap_percent INTEGER NOT NULL DEFAULT 50,
            resurrection_uses_remaining INTEGER
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            user_id INTEGER,
            name TEXT,
            sheet_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'active',
            gold_gp INTEGER DEFAULT 0
        );
        CREATE TABLE character_xp_grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, amount INTEGER,
            created_at TEXT DEFAULT '2026-01-01', reverted_at TEXT
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, delta INTEGER, source TEXT,
            meta_json TEXT, game_clock_day INTEGER,
            wall_clock_at TEXT DEFAULT '2026-01-01', reverted_at TEXT
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, item_key TEXT, weapon_key TEXT,
            consumable_key TEXT, quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0, slot TEXT, label TEXT, meta_json TEXT
        );
        CREATE TABLE character_spells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, spell_key TEXT,
            rank INTEGER DEFAULT 1, learned_at_level INTEGER
        );
        CREATE TABLE character_dungeon_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, dungeon_key TEXT, cooldown_until TEXT
        );
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_items") + """
        """ + table_sql("game_config_consumables") + """

        INSERT INTO users (id, username) VALUES (1, 'tester');
        -- Hero with status='in_campaign' but hp=0 in sheet (the other dead state the card detects).
        -- campaign_id=NULL: skips get_clock_state (no game_sessions table in :memory: fixture).
        INSERT INTO characters (id, user_id, campaign_id, name, status, gold_gp, sheet_json)
            VALUES (20, 1, NULL, 'HP-Dead Hero', 'in_campaign', 100,
                '{"archetype":"warrior","level":3,"current_hp":0,"max_hp":18}');
    """
    )
    return conn


# ─── Test główny 1 — force resurrect działa na HP-dead hero (nie status='dead') ──────

def test_admin_force_resurrect_hp_dead_hero(db):
    """Force=True wskrzesza bohatera z HP=0/status=in_campaign (stan wykrywany przez badge na kafelku)."""
    result = apply_resurrection(20, 1, db, force=True)
    assert result["revived_hp"] > 0, "HP musi być > 0 po wskrzeszeniu"
    assert result["max_hp"] == 18
    # HP w bazie zaktualizowane
    char = db.execute("SELECT sheet_json, status FROM characters WHERE id=20").fetchone()
    sheet = json.loads(char["sheet_json"])
    assert sheet["current_hp"] == 9, f"revived_hp = max_hp//2 = 9, got {sheet['current_hp']}"
    assert char["status"] == "active"


# ─── Test główny 2 — response shape ma pola potrzebne przez toast w _campModalResurrect ──

def test_admin_force_resurrect_response_shape(db):
    """Odpowiedź zawiera revived_hp + max_hp — używane przez toast 'Wskrzeszony — HP X/Y'."""
    result = apply_resurrection(20, 1, db, force=True)
    assert "revived_hp" in result
    assert "max_hp" in result
    assert "character_id" in result
    assert result["cost_applied"]["mode"] == "admin_free"


# ─── Test główny 3 — force=True bypasses disabled global config ───────────────────────

def test_admin_force_bypasses_global_disabled(db):
    """Admin force resurrect działa nawet gdy globalne wskrzeszenia wyłączone (wymagane przez kryterium #3)."""
    set_global_resurrection_config(db, enabled=False)
    # force=True nie powinien rzucać PermissionError
    result = apply_resurrection(20, 1, db, force=True)
    assert result["revived_hp"] > 0


# ─── Backward compat — istniejące testy nie powinny eksplodować ──────────────────────

def test_backward_compat_status_dead_still_works(db):
    """Status='dead' hero też wskrzeszany poprawnie (istniejąca ścieżka)."""
    db.execute("UPDATE characters SET status='dead' WHERE id=20")
    db.commit()
    result = apply_resurrection(20, 1, db, force=True)
    assert result["revived_hp"] > 0
    char = db.execute("SELECT status FROM characters WHERE id=20").fetchone()
    assert char["status"] == "active"
