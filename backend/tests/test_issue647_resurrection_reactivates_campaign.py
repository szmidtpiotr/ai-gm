"""TDD: Issue #647 — resurrection must reactivate ended campaign."""
import json
import sqlite3
import pytest

from app.services.resurrection_service import (
    apply_resurrection,
    set_global_resurrection_config,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_config_meta (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        );
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
        CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT);
        CREATE TABLE game_config_items (key TEXT PRIMARY KEY, label TEXT, effect_json TEXT, ac_bonus INTEGER DEFAULT 0);
        CREATE TABLE game_config_consumables (key TEXT PRIMARY KEY, label TEXT, effect_type TEXT);
        INSERT INTO users (id, username) VALUES (1, 'tester');
        INSERT INTO characters (id, user_id, campaign_id, name, status, gold_gp, sheet_json)
            VALUES (10, 1, 100, 'Hero', 'dead', 100,
                '{"stats":{"CON":12,"INT":10},"archetype":"warrior","level":3,"xp":250,"current_hp":0,"max_hp":12,"max_mana":0}');
        INSERT INTO campaigns (id, user_id, status, death_reason, ended_at, epitaph)
            VALUES (100, 1, 'ended', 'Poległ w walce z goblinami.', '2026-06-18T10:00:00', 'Był dzielny.');
    """)
    conn.commit()

    # Stub clock service (no game_sessions table in in-memory DB)
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

def test_resurrection_reactivates_ended_campaign(db):
    """Po wskrzeszeniu kampania wraca do status='active', pola śmierci wyczyszczone."""
    set_global_resurrection_config(db, mode="admin_free", enabled=True)

    apply_resurrection(10, 1, db, force=True)

    campaign = db.execute("SELECT * FROM campaigns WHERE id = 100").fetchone()
    assert campaign["status"] == "active", (
        f"Kampania powinna być 'active' po wskrzeszeniu, jest: '{campaign['status']}'"
    )
    assert campaign["death_reason"] is None, "death_reason powinno być NULL"
    assert campaign["ended_at"] is None, "ended_at powinno być NULL"
    assert campaign["epitaph"] is None, "epitaph powinno być NULL"


def test_resurrection_hero_itself_reactivated(db):
    """Bohater sam w sobie też musi wrócić do status='active'."""
    set_global_resurrection_config(db, mode="admin_free", enabled=True)

    apply_resurrection(10, 1, db, force=True)

    char = db.execute("SELECT status, sheet_json FROM characters WHERE id = 10").fetchone()
    assert char["status"] == "active"
    sheet = json.loads(char["sheet_json"])
    assert int(sheet["current_hp"]) > 0, "HP musi być > 0 po wskrzeszeniu"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_resurrection_without_campaign_still_works(db):
    """Wskrzeszenie bohatera bez kampanii (idle) nie powoduje błędu."""
    # Odłącz bohatera od kampanii
    db.execute("UPDATE characters SET campaign_id = NULL WHERE id = 10")
    db.commit()

    set_global_resurrection_config(db, mode="admin_free", enabled=True)

    result = apply_resurrection(10, 1, db, force=True)
    assert result["character_id"] == 10
    char = db.execute("SELECT status FROM characters WHERE id = 10").fetchone()
    assert char["status"] == "active"


def test_resurrection_does_not_reset_active_campaign(db):
    """Jeśli kampania była już active (np. admin force na żywym), nie zmienia stanu."""
    # Ustaw kampanię jako active już teraz
    db.execute("UPDATE campaigns SET status='active', death_reason=NULL, ended_at=NULL, epitaph=NULL WHERE id=100")
    db.commit()

    set_global_resurrection_config(db, mode="admin_free", enabled=True)

    apply_resurrection(10, 1, db, force=True)

    campaign = db.execute("SELECT status FROM campaigns WHERE id = 100").fetchone()
    assert campaign["status"] == "active", "Aktywna kampania nie powinna zmieniać statusu"
