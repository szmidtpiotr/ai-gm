"""TDD: Issue #985 — resurrection must end active combat to prevent enemy-turn death loop."""
from _fixtures_schema import table_sql
import json
import sqlite3
import pytest
from unittest.mock import patch, MagicMock

from app.services.resurrection_service import (
    apply_resurrection,
    set_global_resurrection_config,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        """ + table_sql("game_config_meta") + """
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
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            status TEXT DEFAULT 'active',
            death_reason TEXT,
            ended_at TEXT,
            epitaph TEXT
        );
        CREATE TABLE character_xp_grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            amount INTEGER,
            created_at TEXT DEFAULT '2026-01-01',
            reverted_at TEXT
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            delta INTEGER,
            source TEXT,
            meta_json TEXT,
            game_clock_day INTEGER,
            wall_clock_at TEXT DEFAULT '2026-01-01',
            reverted_at TEXT
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT,
            quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0,
            slot TEXT,
            label TEXT,
            meta_json TEXT
        );
        CREATE TABLE character_spells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            spell_key TEXT,
            rank INTEGER DEFAULT 1,
            learned_at_level INTEGER
        );
        CREATE TABLE character_dungeon_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            dungeon_key TEXT,
            cooldown_until TEXT
        );
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_items") + """
        """ + table_sql("game_config_consumables") + """
        INSERT INTO users (id, username) VALUES (1, 'tester');
        INSERT INTO characters (id, user_id, campaign_id, name, status, gold_gp, sheet_json)
            VALUES (10, 1, 100, 'Wojownik', 'dead', 100,
                '{"stats":{"CON":12,"INT":10},"archetype":"warrior","level":3,"xp":250,"current_hp":0,"max_hp":10}');
        INSERT INTO campaigns (id, user_id, status, death_reason, ended_at, epitaph)
            VALUES (100, 1, 'ended', 'Poległ w walce z bandytami.', '2026-06-24T10:00:00', 'Był dzielny.');
    """)
    conn.commit()

    import app.services.clock_service as _clock
    _orig = _clock.get_clock_state
    _clock.get_clock_state = lambda cid, conn=None: {
        "day": 1, "hour": 6, "ingame_hours": 6,
        "hour_str": "06:00", "period": "Rano", "display": "Dzień 1"
    }
    yield conn
    _clock.get_clock_state = _orig
    conn.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_resurrection_ends_active_combat(db):
    """Wskrzeszenie przy aktywnej walce musi zakończyć tę walkę.

    Bez tego fix'u bohater wraca na 'turę wroga' i ginie natychmiast.
    """
    set_global_resurrection_config(db, mode="admin_free", enabled=True)

    with patch("app.services.resurrection_service.is_combat_active", return_value=True, create=True) as mock_check, \
         patch("app.services.resurrection_service.end_combat", create=True) as mock_end:
        apply_resurrection(10, 1, db, force=True)

    mock_check.assert_called_once_with(None, 100)
    mock_end.assert_called_once_with(100, "resurrected")


def test_resurrection_does_not_call_end_combat_when_no_combat(db):
    """Wskrzeszenie bez aktywnej walki nie próbuje kończyć nieistniejącej walki."""
    set_global_resurrection_config(db, mode="admin_free", enabled=True)

    with patch("app.services.resurrection_service.is_combat_active", return_value=False, create=True) as mock_check, \
         patch("app.services.resurrection_service.end_combat", create=True) as mock_end:
        apply_resurrection(10, 1, db, force=True)

    mock_check.assert_called_once_with(None, 100)
    mock_end.assert_not_called()


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_resurrection_without_campaign_skips_combat_check(db):
    """Wskrzeszenie bohatera bez kampanii (idle) nie sprawdza stanu walki."""
    db.execute("UPDATE characters SET campaign_id = NULL WHERE id = 10")
    db.commit()
    set_global_resurrection_config(db, mode="admin_free", enabled=True)

    with patch("app.services.resurrection_service.is_combat_active", create=True) as mock_check, \
         patch("app.services.resurrection_service.end_combat", create=True) as mock_end:
        result = apply_resurrection(10, 1, db, force=True)

    mock_check.assert_not_called()
    mock_end.assert_not_called()
    assert result["character_id"] == 10


def test_resurrection_end_combat_failure_does_not_block_revive(db):
    """Błąd przy kończeniu walki nie blokuje wskrzeszenia — bohater i tak wraca do życia."""
    set_global_resurrection_config(db, mode="admin_free", enabled=True)

    with patch("app.services.resurrection_service.is_combat_active", return_value=True, create=True), \
         patch("app.services.resurrection_service.end_combat", side_effect=Exception("DB error"), create=True):
        result = apply_resurrection(10, 1, db, force=True)

    char = db.execute("SELECT status, sheet_json FROM characters WHERE id = 10").fetchone()
    assert char["status"] == "active"
    sheet = json.loads(char["sheet_json"])
    assert int(sheet["current_hp"]) > 0, "HP musi być > 0 mimo błędu end_combat"
