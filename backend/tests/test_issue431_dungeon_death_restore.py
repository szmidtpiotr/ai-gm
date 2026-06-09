"""TDD: Issue #431 E16 — Restore snapshot on dungeon death + restart run from room 1."""
import json
import sys
import sqlite3
import tempfile
import os

sys.path.insert(0, "/app")

import pytest

DB_PATH = "/data/ai_gm.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── helpers ──────────────────────────────────────────────────────────────────

def _setup_test_data(conn, campaign_id: int, character_id: int, user_id: int = 9431):
    """Insert minimal rows for dungeon death tests."""
    # User
    conn.execute(
        "INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (?, ?, ?)",
        (user_id, f"test_e16_{user_id}", "x")
    )
    # Campaign (owner_user_id, system_id required)
    conn.execute(
        """INSERT OR REPLACE INTO campaigns (id, owner_user_id, title, system_id, status)
           VALUES (?, ?, ?, 'fantasy', 'active')""",
        (campaign_id, user_id, f"TestCamp_E16_{campaign_id}")
    )
    # Character (system_id required, no archetype column)
    sheet = json.dumps({
        "level": 3,
        "current_hp": 15,
        "max_hp": 40,
        "conditions": [],
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
    })
    conn.execute(
        """INSERT OR REPLACE INTO characters (id, user_id, campaign_id, name, system_id, sheet_json, status, gold, gold_gp)
           VALUES (?, ?, ?, 'HeroE16', 'fantasy', ?, 'active', 30, 5)""",
        (character_id, user_id, campaign_id, sheet)
    )
    # inventory: 1 item AFTER dungeon (different from entry state)
    conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (character_id,))
    conn.execute(
        """INSERT INTO character_inventory (character_id, item_key, quantity, equipped)
           VALUES (?, 'healing_potion', 1, 0)""",
        (character_id,)
    )
    # game_sessions (id is TEXT PRIMARY KEY)
    run = {
        "dungeon_key": "crypt_of_shadows",
        "dungeon_label": "Krypta Cieni",
        "atmosphere": "Dark.",
        "rooms": [
            {"room_id": 1, "room_type": "combat", "cleared": True, "is_boss": False,
             "enemy_key": "skeleton", "enemy_count": 1, "enemy_stats": {}, "enemy_label": "Szkielet"},
            {"room_id": 2, "room_type": "combat", "cleared": True, "is_boss": False,
             "enemy_key": "zombie", "enemy_count": 1, "enemy_stats": {}, "enemy_label": "Zombie"},
            {"room_id": 3, "room_type": "boss", "cleared": False, "is_boss": True,
             "enemy_key": "lich", "enemy_count": 1, "enemy_stats": {}, "enemy_label": "Lich"},
        ],
        "total_rooms": 3,
        "current_room": 3,
        "completed": False,
        "failed": False,
        "hero_level_at_entry": 3,
        "cooldown_hours": 24,
        "loot_collected": [],
    }
    conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (campaign_id,))
    conn.execute(
        """INSERT INTO game_sessions (id, campaign_id, session_flags)
           VALUES (?, ?, ?)""",
        (f"test_e16_{campaign_id}", campaign_id, json.dumps({"dungeon_run": run}))
    )
    # Dungeon seed (so complete_dungeon would actually work if mistakenly called)
    conn.execute(
        """INSERT OR IGNORE INTO game_dungeons (key, label, location_key, rooms, enemy_pool, cooldown_hours, is_active)
           VALUES ('crypt_of_shadows', 'Krypta Cieni', 'dungeon_test', 3, '[]', 24, 1)"""
    )
    # Snapshot saved at dungeon ENTRY (the state to restore)
    conn.execute(
        "DELETE FROM world_state_snapshots WHERE campaign_id = ? AND snapshot_source = 'dungeon_enter'",
        (campaign_id,)
    )
    entry_snapshot = {
        "current_hp": 40,
        "max_hp": 40,
        "gold": 50,
        "gold_gp": 10,
        "inventory": [
            {"item_key": "torch", "weapon_key": None, "consumable_key": None, "quantity": 3, "equipped": 0},
            {"item_key": None, "weapon_key": "iron_sword", "consumable_key": None, "quantity": 1, "equipped": 1},
        ],
        "dungeon_key": "crypt_of_shadows",
    }
    conn.execute(
        """INSERT INTO world_state_snapshots (campaign_id, turn_number, snapshot_json, snapshot_source)
           VALUES (?, 5, ?, 'dungeon_enter')""",
        (campaign_id, json.dumps(entry_snapshot))
    )
    conn.commit()


def _teardown(conn, campaign_id: int, character_id: int, user_id: int = 9431):
    conn.execute("DELETE FROM world_state_snapshots WHERE campaign_id = ?", (campaign_id,))
    conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (campaign_id,))
    conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (character_id,))
    conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))
    conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.execute("DELETE FROM character_dungeon_runs WHERE character_id = ?", (character_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.execute("DELETE FROM game_dungeons WHERE key = 'crypt_of_shadows'")
    conn.commit()


# ─── Test główny 1: Śmierć przywraca HP z snapshotu ──────────────────────────

def test_dungeon_death_restores_hp():
    """After dungeon death, character HP is restored to dungeon_enter snapshot value."""
    from app.services.dungeon_service import handle_dungeon_death

    campaign_id, character_id = 94310, 94311
    conn = _get_db()
    try:
        _setup_test_data(conn, campaign_id, character_id)
        # Pre-check: character has low HP (15) from dungeon fight
        char_before = conn.execute(
            "SELECT sheet_json, gold, gold_gp FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        sheet_before = json.loads(char_before["sheet_json"])
        assert sheet_before["current_hp"] == 15, "Setup: character should have 15 HP (post-fight)"

        result = handle_dungeon_death(campaign_id, character_id)

        assert result.get("ok") is True
        char_after = conn.execute(
            "SELECT sheet_json, gold, gold_gp FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        sheet_after = json.loads(char_after["sheet_json"])
        # Snapshot had current_hp=40
        assert sheet_after["current_hp"] == 40, \
            f"Expected HP=40 (from snapshot), got {sheet_after['current_hp']}"
    finally:
        _teardown(conn, campaign_id, character_id)
        conn.close()


# ─── Test główny 2: Śmierć przywraca gold z snapshotu ────────────────────────

def test_dungeon_death_restores_gold():
    """After dungeon death, character gold is restored to dungeon_enter snapshot value."""
    from app.services.dungeon_service import handle_dungeon_death

    campaign_id, character_id = 94312, 94313
    conn = _get_db()
    try:
        _setup_test_data(conn, campaign_id, character_id)
        # Pre-check: character has gold=30 (spent during dungeon)
        char_before = conn.execute(
            "SELECT gold, gold_gp FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        assert char_before["gold"] == 30, "Setup: character should have 30 gold (spent during dungeon)"

        handle_dungeon_death(campaign_id, character_id)

        char_after = conn.execute(
            "SELECT gold, gold_gp FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        # Snapshot had gold=50, gold_gp=10
        assert char_after["gold"] == 50, \
            f"Expected gold=50 (from snapshot), got {char_after['gold']}"
        assert char_after["gold_gp"] == 10, \
            f"Expected gold_gp=10 (from snapshot), got {char_after['gold_gp']}"
    finally:
        _teardown(conn, campaign_id, character_id)
        conn.close()


# ─── Test główny 3: Śmierć przywraca ekwipunek z snapshotu ───────────────────

def test_dungeon_death_restores_inventory():
    """After dungeon death, character inventory is restored to dungeon_enter snapshot."""
    from app.services.dungeon_service import handle_dungeon_death

    campaign_id, character_id = 94314, 94315
    conn = _get_db()
    try:
        _setup_test_data(conn, campaign_id, character_id)
        # Pre-check: character has healing_potion (picked up during dungeon)
        inv_before = conn.execute(
            "SELECT item_key, weapon_key FROM character_inventory WHERE character_id = ?", (character_id,)
        ).fetchall()
        keys_before = {r["item_key"] for r in inv_before}
        assert "healing_potion" in keys_before, "Setup: should have healing_potion (dungeon pickup)"

        handle_dungeon_death(campaign_id, character_id)

        inv_after = conn.execute(
            "SELECT item_key, weapon_key, quantity FROM character_inventory WHERE character_id = ?", (character_id,)
        ).fetchall()
        item_keys = {r["item_key"] for r in inv_after}
        weapon_keys = {r["weapon_key"] for r in inv_after}
        # Snapshot had: torch x3, iron_sword (equipped)
        assert "torch" in item_keys, f"Expected torch in inventory after restore, got: {item_keys}"
        assert "iron_sword" in weapon_keys, f"Expected iron_sword in inventory after restore, got: {weapon_keys}"
        assert "healing_potion" not in item_keys, \
            f"healing_potion should be gone (was picked up in dungeon, not in snapshot)"
    finally:
        _teardown(conn, campaign_id, character_id)
        conn.close()


# ─── Test główny 4: Śmierć resetuje run do pokoju 1 ──────────────────────────

def test_dungeon_death_resets_run_to_room_1():
    """After dungeon death, the dungeon run is reset to room 1 with fresh state."""
    from app.services.dungeon_service import handle_dungeon_death, get_active_dungeon_run

    campaign_id, character_id = 94316, 94317
    conn = _get_db()
    try:
        _setup_test_data(conn, campaign_id, character_id)
        # Pre-check: run was at room 3
        run_before = get_active_dungeon_run(campaign_id)
        assert run_before is not None
        assert run_before["current_room"] == 3, "Setup: should be at room 3"

        handle_dungeon_death(campaign_id, character_id)

        run_after = get_active_dungeon_run(campaign_id)
        assert run_after is not None, "Dungeon run should still be active after death (not cleared)"
        assert run_after["current_room"] == 1, \
            f"Expected current_room=1 after reset, got {run_after['current_room']}"
        assert run_after.get("failed") is not True, \
            "Run should NOT be marked failed — it's being restarted"
        # All rooms should be un-cleared
        cleared_rooms = [r for r in run_after.get("rooms", []) if r.get("cleared")]
        assert len(cleared_rooms) == 0, \
            f"All rooms should be un-cleared after restart, {len(cleared_rooms)} still cleared"
    finally:
        _teardown(conn, campaign_id, character_id)
        conn.close()


# ─── Test główny 5: Śmierć NIE nakłada cooldownu ─────────────────────────────

def test_dungeon_death_no_cooldown():
    """Death resets the run, it does NOT start a cooldown timer."""
    from app.services.dungeon_service import handle_dungeon_death, check_cooldown

    campaign_id, character_id = 94318, 94319
    conn = _get_db()
    try:
        _setup_test_data(conn, campaign_id, character_id)

        handle_dungeon_death(campaign_id, character_id)

        cooldown = check_cooldown(character_id, "crypt_of_shadows")
        assert not cooldown.get("on_cooldown"), \
            f"Expected no cooldown after dungeon death, got: {cooldown}"
    finally:
        _teardown(conn, campaign_id, character_id)
        conn.close()


# ─── Test główny 6: result zawiera restored=True ─────────────────────────────

def test_dungeon_death_result_flags():
    """handle_dungeon_death returns ok=True, restored=True, restarted=True."""
    from app.services.dungeon_service import handle_dungeon_death

    campaign_id, character_id = 94320, 94321
    conn = _get_db()
    try:
        _setup_test_data(conn, campaign_id, character_id)

        result = handle_dungeon_death(campaign_id, character_id)

        assert result.get("ok") is True
        assert result.get("restored") is True, "result must have restored=True"
        assert result.get("restarted") is True, "result must have restarted=True"
        assert result.get("dungeon_key") == "crypt_of_shadows"
    finally:
        _teardown(conn, campaign_id, character_id)
        conn.close()


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_handle_dungeon_death_no_run_still_ok():
    """handle_dungeon_death with no active run still returns ok=True (no crash)."""
    from app.services.dungeon_service import handle_dungeon_death

    campaign_id, character_id = 94322, 94323
    user_id = 94324
    conn = _get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (?, ?, ?)",
            (user_id, "test_e16_norun", "x")
        )
        conn.execute(
            "INSERT OR REPLACE INTO campaigns (id, owner_user_id, title, system_id, status) VALUES (?, ?, ?, 'dnd5e', 'active')",
            (campaign_id, user_id, "NoRunCamp")
        )
        sheet = json.dumps({"level": 1, "current_hp": 10, "max_hp": 10})
        conn.execute(
            """INSERT OR REPLACE INTO characters (id, user_id, campaign_id, name, system_id, sheet_json, status, gold, gold_gp)
               VALUES (?, ?, ?, 'NoRun', 'fantasy', ?, 'active', 0, 0)""",
            (character_id, user_id, campaign_id, sheet)
        )
        conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (campaign_id,))
        conn.execute(
            "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (?, ?, ?)",
            (f"test_e16_norun_{campaign_id}", campaign_id, json.dumps({}))
        )
        conn.commit()

        result = handle_dungeon_death(campaign_id, character_id)
        assert result.get("ok") is True

    finally:
        conn.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (campaign_id,))
        conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
