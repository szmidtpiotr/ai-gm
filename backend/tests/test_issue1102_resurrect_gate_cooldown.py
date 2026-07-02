"""TDD: Issue #1102 — petla wskrzeszen (5x resurrect w 2 min bez smierci).

Bramka `resurrect_hero` (characters.py:1328) traktuje BRAK klucza `current_hp`
w sheet_json jak zgon (`sheet.get("current_hp") or 0` -> 0 -> "martwy"), wiec
kazdy nadpisany/niepelny sheet po wskrzeszeniu znow wpuszcza gracza do
/resurrect. Fix: brak klucza != zgon + cooldown 60s jako backstop niezaleznie
od zrodla powtorki.
"""
import sys
sys.path.insert(0, "/app")

import json
import sqlite3

import pytest

from app.api import characters as characters_module
from app.services import resurrection_service as resurrection_svc
from _fixtures_schema import table_sql


SCHEMA = (
    table_sql("game_config_meta")
    + """
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
        name TEXT, location TEXT, sheet_json TEXT DEFAULT '{}',
        status TEXT DEFAULT 'active', gold_gp INTEGER DEFAULT 0
    );
    CREATE TABLE campaigns (
        id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active',
        system_id TEXT, model_id TEXT, language TEXT DEFAULT 'pl',
        owner_user_id INTEGER, death_reason TEXT, ended_at TEXT, epitaph TEXT
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
    CREATE TABLE combat_state (
        campaign_id INTEGER PRIMARY KEY, active INTEGER DEFAULT 0, state_json TEXT
    );
    CREATE TABLE campaign_turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, character_id INTEGER,
        user_text TEXT, route TEXT, assistant_text TEXT, turn_number INTEGER
    );
    """
    + table_sql("game_config_weapons")
    + table_sql("game_config_items")
    + table_sql("game_config_consumables")
    + """
    INSERT INTO users (id, username, resurrection_enabled, resurrection_cost_mode)
        VALUES (1, 'tester', 1, 'admin_free');
    INSERT INTO game_config_meta (key, value) VALUES
        ('resurrection_config', '{"enabled": true, "mode": "admin_free", "value": 25, "cap_percent": 50, "default_uses": null}');
    INSERT INTO campaigns (id, title, status, owner_user_id) VALUES (200, 'Run', 'active', 1);
    """
)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    p = tmp_path / "test.db"
    conn = sqlite3.connect(str(p))
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    monkeypatch.setattr(characters_module, "DB_PATH", str(p))
    monkeypatch.setattr(resurrection_svc, "get_user_llm_settings_full", lambda uid: {"model": "stub"})
    monkeypatch.setattr(resurrection_svc, "generate_chat", lambda **kw: "stub narration")
    return p


def _insert_char(db_path, status, sheet):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, status, gold_gp, sheet_json)"
        " VALUES (30, 200, 1, 'Mizel', ?, 50, ?)",
        (status, json.dumps(sheet)),
    )
    conn.commit()
    conn.close()


def _read_char(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status, sheet_json FROM characters WHERE id=30").fetchone()
    conn.close()
    return row["status"], json.loads(row["sheet_json"])


# ─── Test główny — brak klucza current_hp NIE jest zgonem ─────────────────

def test_missing_current_hp_key_not_treated_as_dead(db_path):
    """Zywy bohater bez klucza current_hp w sheet nie powinien przejsc bramki /resurrect."""
    _insert_char(db_path, "active", {"archetype": "warrior", "level": 4, "max_hp": 16})
    with pytest.raises(Exception) as exc_info:
        characters_module.resurrect_hero(30, user_id=1, authorization=None)
    assert getattr(exc_info.value, "status_code", None) == 409


# ─── Test — cooldown blokuje szybkie powtorzenie ──────────────────────────

def test_second_resurrect_within_60s_blocked_by_cooldown(db_path):
    """Nawet jesli bohater znow 'wyglada' na martwego (np. nadpisany sheet), drugi
    POST /resurrect w <60s po udanym musi dostac 409 zamiast znow wskrzeszac."""
    _insert_char(db_path, "dead", {"archetype": "warrior", "level": 4, "current_hp": 0, "max_hp": 16})

    result = characters_module.resurrect_hero(30, user_id=1, authorization=None)
    assert result["revived_hp"] == 8

    status, sheet = _read_char(db_path)
    assert status == "active"
    assert sheet["current_hp"] == 8

    # Simulate the reported overwrite bug: something wipes current_hp back to 0
    # but the cooldown stamp survives (it lives in the same sheet_json blob).
    sheet["current_hp"] = 0
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE characters SET status='dead', sheet_json=? WHERE id=30", (json.dumps(sheet),))
    conn.commit()
    conn.close()

    with pytest.raises(Exception) as exc_info:
        characters_module.resurrect_hero(30, user_id=1, authorization=None)
    assert exc_info.value.status_code == 409
    assert "cooldown" in exc_info.value.detail.lower()


# ─── Backward compat — bohater faktycznie martwy nadal wskrzeszany ────────

def test_truly_dead_hero_still_resurrects(db_path):
    """Stare zachowanie: current_hp jawnie <=0 -> resurrect dziala jak dawniej."""
    _insert_char(db_path, "dead", {"archetype": "scholar", "level": 2, "current_hp": 0, "max_hp": 10})
    result = characters_module.resurrect_hero(30, user_id=1, authorization=None)
    assert result["revived_hp"] == 5
    status, sheet = _read_char(db_path)
    assert status == "active"
    assert sheet["current_hp"] == 5
