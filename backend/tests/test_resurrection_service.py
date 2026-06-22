"""
Tests for Resurrection Service — Stage 11 (issue #64, global config redesign).

Config is GLOBAL (game_config_meta); per-user only: uses_remaining.
Covers all 5 cost modes, force-bypass, uses_remaining decrement,
full state reset, and gold-journal integrity.
"""

from _fixtures_schema import table_sql
import json
import sqlite3
import pytest

from app.services.resurrection_service import (
    VALID_MODES,
    get_global_resurrection_config,
    set_global_resurrection_config,
    get_user_uses_remaining,
    set_user_uses_remaining,
    get_user_resurrection_config,
    cost_preview,
    apply_resurrection,
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

        -- Seeds
        INSERT INTO users (id, username) VALUES (1, 'tester');
        INSERT INTO characters (id, user_id, campaign_id, name, status, gold_gp, sheet_json)
            VALUES (10, 1, 100, 'Hero', 'dead', 100,
                '{"stats":{"CON":12,"INT":10},"archetype":"warrior","level":3,"xp":250,"current_hp":0,"max_hp":12,"max_mana":0}');

        INSERT INTO game_config_weapons (key, label) VALUES ('sword', 'Iron Sword');
        INSERT INTO game_config_items (key, label, ac_bonus) VALUES ('leather', 'Leather Armor', 2);
        INSERT INTO game_config_consumables (key, label, effect_type) VALUES ('potion', 'Healing Potion', 'heal_hp');

        INSERT INTO character_inventory (character_id, weapon_key, equipped, slot, label)
            VALUES (10, 'sword', 1, 'main_hand', 'Iron Sword');
        INSERT INTO character_inventory (character_id, item_key, equipped, slot, label)
            VALUES (10, 'leather', 1, 'torso', 'Leather Armor');
        INSERT INTO character_inventory (character_id, consumable_key, equipped, slot, label, quantity)
            VALUES (10, 'potion', 1, 'belt', 'Healing Potion', 2);
    """)
    conn.commit()

    # Stub the clock service
    import app.services.clock_service as _clock
    _orig = _clock.get_clock_state
    _clock.get_clock_state = lambda cid, conn=None: {
        "day": 10, "hour": 12, "ingame_hours": 240,
        "hour_str": "12:00", "period": "Popołudnie", "display": "Dzień 10"
    }
    yield conn
    _clock.get_clock_state = _orig
    conn.close()


# ── Global config CRUD ─────────────────────────────────────────────────


def test_default_global_config_disabled(db):
    cfg = get_global_resurrection_config(db)
    assert cfg["enabled"] is False
    assert cfg["mode"] == "admin_free"
    assert cfg["default_uses"] is None


def test_set_invalid_mode_raises(db):
    with pytest.raises(ValueError):
        set_global_resurrection_config(db, mode="nonsense")


def test_set_clamps_cap_percent(db):
    cfg = set_global_resurrection_config(db, cap_percent=999)
    assert cfg["cap_percent"] == 100
    cfg = set_global_resurrection_config(db, cap_percent=-5)
    assert cfg["cap_percent"] == 0


def test_per_user_uses_default_none(db):
    assert get_user_uses_remaining(1, db) is None


def test_set_per_user_uses(db):
    set_user_uses_remaining(1, db, 5)
    assert get_user_uses_remaining(1, db) == 5
    set_user_uses_remaining(1, db, None)
    assert get_user_uses_remaining(1, db) is None


# ── Preview gates ──────────────────────────────────────────────────────


def test_preview_disabled_returns_reason(db):
    p = cost_preview(10, 1, db)
    assert p["enabled"] is False
    assert p["reason"] == "resurrection_disabled"


def test_preview_no_uses_remaining(db):
    set_global_resurrection_config(db, enabled=True)
    set_user_uses_remaining(1, db, 0)
    p = cost_preview(10, 1, db)
    assert p["enabled"] is False
    assert p["reason"] == "no_uses_remaining"


# ── Cost mode previews ─────────────────────────────────────────────────


def test_preview_gold_percent(db):
    set_global_resurrection_config(db, enabled=True, mode="gold_percent", value=25)
    p = cost_preview(10, 1, db)
    assert p["cost"]["gold_lost"] == 25  # 25% of 100
    assert p["cost"]["current_gold"] == 100


def test_preview_gold_recent_days_capped(db):
    db.execute("INSERT INTO character_gold_log (character_id, delta, source, game_clock_day) VALUES (10, 80, 'loot', 8)")
    db.commit()
    set_global_resurrection_config(db, enabled=True, mode="gold_recent_days", value=5, cap_percent=30)
    p = cost_preview(10, 1, db)
    assert p["cost"]["gold_lost"] == 30        # min(80, 100*30%)
    assert p["cost"]["recent_gains_in_window"] == 80
    assert p["cost"]["cap"] == 30


def test_preview_gold_recent_days_outside_window_ignored(db):
    db.execute("INSERT INTO character_gold_log (character_id, delta, source, game_clock_day) VALUES (10, 80, 'loot', 2)")
    db.commit()
    set_global_resurrection_config(db, enabled=True, mode="gold_recent_days", value=5, cap_percent=50)
    p = cost_preview(10, 1, db)
    assert p["cost"]["recent_gains_in_window"] == 0


def test_preview_xp_revert(db):
    for amt in (30, 40, 50):
        db.execute("INSERT INTO character_xp_grants (character_id, amount) VALUES (10, ?)", (amt,))
    db.commit()
    set_global_resurrection_config(db, enabled=True, mode="xp_revert", value=60)
    p = cost_preview(10, 1, db)
    assert p["cost"]["grants_count"] == 2
    assert p["cost"]["xp_lost"] == 90   # 50+40 ≥ 60


def test_preview_item_loss_lists_eligible(db):
    set_global_resurrection_config(db, enabled=True, mode="item_loss")
    p = cost_preview(10, 1, db)
    assert p["cost"]["eligible_count"] == 3
    assert p["cost"]["fallback_to_free"] is False


def test_preview_item_loss_quest_excluded(db):
    db.execute("UPDATE character_inventory SET meta_json = '{\"is_quest_item\": true}' WHERE character_id = 10")
    db.commit()
    set_global_resurrection_config(db, enabled=True, mode="item_loss")
    p = cost_preview(10, 1, db)
    assert p["cost"]["fallback_to_free"] is True


# ── Apply paths ────────────────────────────────────────────────────────


def test_apply_disabled_raises(db):
    with pytest.raises(PermissionError):
        apply_resurrection(10, 1, db, force=False)


def test_apply_no_uses_raises(db):
    set_global_resurrection_config(db, enabled=True)
    set_user_uses_remaining(1, db, 0)
    with pytest.raises(RuntimeError):
        apply_resurrection(10, 1, db, force=False)


def test_apply_force_bypasses_disabled(db):
    result = apply_resurrection(10, 1, db, force=True)
    assert result["cost_applied"]["mode"] == "admin_free"
    assert result["revived_hp"] == 6  # max_hp 12 // 2
    assert db.execute("SELECT status FROM characters WHERE id = 10").fetchone()["status"] == "active"


def test_apply_gold_percent_deducts(db):
    set_global_resurrection_config(db, enabled=True, mode="gold_percent", value=50)
    result = apply_resurrection(10, 1, db, force=False)
    assert result["cost_applied"]["gold_lost"] == 50
    assert db.execute("SELECT gold_gp FROM characters WHERE id = 10").fetchone()["gold_gp"] == 50
    log = db.execute("SELECT delta, source FROM character_gold_log WHERE character_id = 10 ORDER BY id DESC LIMIT 1").fetchone()
    assert log["delta"] == -50
    assert "resurrection" in log["source"]


def test_apply_xp_revert_clamps_skills_above_new_level(db):
    db.execute("INSERT INTO character_xp_grants (character_id, amount) VALUES (10, 200)")
    db.commit()
    sheet = json.loads(db.execute("SELECT sheet_json FROM characters WHERE id = 10").fetchone()["sheet_json"])
    sheet["skills"] = {"athletics": {"rank": 5}}
    db.execute("UPDATE characters SET sheet_json = ? WHERE id = 10", (json.dumps(sheet),))
    db.commit()

    set_global_resurrection_config(db, enabled=True, mode="xp_revert", value=150)
    apply_resurrection(10, 1, db, force=False)
    new_sheet = json.loads(db.execute("SELECT sheet_json FROM characters WHERE id = 10").fetchone()["sheet_json"])
    assert new_sheet["level"] == 1
    assert new_sheet["skills"]["athletics"]["rank"] == 1


def test_apply_xp_revert_drops_spells_learned_above_new_level(db):
    db.execute("INSERT INTO character_xp_grants (character_id, amount) VALUES (10, 200)")
    db.execute("INSERT INTO character_spells (character_id, spell_key, rank, learned_at_level) VALUES (10, 'fireball', 1, 3)")
    db.execute("INSERT INTO character_spells (character_id, spell_key, rank, learned_at_level) VALUES (10, 'magic_bolt', 1, 1)")
    db.commit()
    set_global_resurrection_config(db, enabled=True, mode="xp_revert", value=150)
    apply_resurrection(10, 1, db, force=False)
    remaining = [r["spell_key"] for r in db.execute("SELECT spell_key FROM character_spells WHERE character_id = 10").fetchall()]
    assert "magic_bolt" in remaining
    assert "fireball" not in remaining


def test_apply_item_loss_removes_one_item(db):
    set_global_resurrection_config(db, enabled=True, mode="item_loss")
    apply_resurrection(10, 1, db, force=False)
    remaining = db.execute(
        "SELECT COUNT(*) AS c FROM character_inventory WHERE character_id = 10 AND quantity > 0"
    ).fetchone()["c"]
    assert remaining in (2, 3)


def test_apply_resets_all_death_flags(db):
    sheet = json.loads(db.execute("SELECT sheet_json FROM characters WHERE id = 10").fetchone()["sheet_json"])
    sheet["death_saves_failed"] = 3
    sheet["short_rests_used"] = 2
    sheet["conditions"] = ["dead", "bleeding"]
    db.execute("UPDATE characters SET sheet_json = ? WHERE id = 10", (json.dumps(sheet),))
    db.execute("INSERT INTO character_dungeon_runs (character_id, dungeon_key) VALUES (10, 'crypt')")
    db.commit()

    apply_resurrection(10, 1, db, force=True)
    new_sheet = json.loads(db.execute("SELECT sheet_json FROM characters WHERE id = 10").fetchone()["sheet_json"])
    assert new_sheet["death_saves_failed"] == 0
    assert new_sheet["short_rests_used"] == 0
    assert "dead" not in new_sheet.get("conditions", [])
    assert "bleeding" in new_sheet.get("conditions", [])
    assert db.execute("SELECT COUNT(*) AS c FROM character_dungeon_runs WHERE character_id = 10").fetchone()["c"] == 0


def test_apply_decrements_uses_remaining(db):
    set_global_resurrection_config(db, enabled=True, mode="admin_free")
    set_user_uses_remaining(1, db, 3)
    result = apply_resurrection(10, 1, db, force=False)
    assert result["uses_remaining_after"] == 2
    assert get_user_uses_remaining(1, db) == 2


def test_apply_force_does_not_decrement_uses(db):
    set_global_resurrection_config(db, enabled=True, mode="admin_free")
    set_user_uses_remaining(1, db, 3)
    apply_resurrection(10, 1, db, force=True)
    assert get_user_uses_remaining(1, db) == 3


# ── Schema sanity ──────────────────────────────────────────────────────


def test_valid_modes_constant_complete():
    assert set(VALID_MODES) == {"xp_revert", "gold_percent", "gold_recent_days", "item_loss", "admin_free"}
