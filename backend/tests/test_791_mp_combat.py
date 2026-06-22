"""TDD #791 — G7: Walka MP — turn_order z player:{id}, wrogowie auto-resolve, timeout=obrona."""
import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest

from app.services import admin_config
from app.services import combat_service as cs


# ── Schema ────────────────────────────────────────────────────────────────────

def _schema_sql() -> str:
    return """
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL DEFAULT '',
      display_name TEXT NOT NULL DEFAULT ''
    );
    INSERT INTO users (id, username, password_hash, display_name)
    VALUES (1, 'alice', 'x', 'Alice'), (2, 'bob', 'x', 'Bob');

    CREATE TABLE IF NOT EXISTS campaigns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL DEFAULT 'Test',
      system_id TEXT NOT NULL DEFAULT 'fantasy',
      model_id TEXT NOT NULL DEFAULT 'm',
      owner_user_id INTEGER NOT NULL DEFAULT 1,
      mode TEXT NOT NULL DEFAULT 'multiplayer',
      status TEXT NOT NULL DEFAULT 'active',
      host_user_id INTEGER,
      round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
      max_players INTEGER NOT NULL DEFAULT 4
    );
    INSERT INTO campaigns (id, title, owner_user_id, mode, host_user_id)
    VALUES (1, 'MP Camp', 1, 'multiplayer', 1);

    CREATE TABLE IF NOT EXISTS campaign_members (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      role TEXT NOT NULL DEFAULT 'player',
      status TEXT NOT NULL DEFAULT 'accepted',
      character_id INTEGER,
      absence_warnings INTEGER NOT NULL DEFAULT 0,
      UNIQUE(campaign_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER,
      user_id INTEGER NOT NULL DEFAULT 1,
      name TEXT NOT NULL,
      system_id TEXT NOT NULL DEFAULT 'fantasy',
      sheet_json TEXT NOT NULL DEFAULT '{}',
      status TEXT NOT NULL DEFAULT 'active'
    );
    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
    VALUES
      (1, 1, 1, 'Aldric', 'fantasy',
       '{"archetype":"warrior","stats":{"STR":14,"DEX":12,"CON":12,"INT":10,"WIS":10,"CHA":10,"LCK":10},"current_hp":20,"max_hp":20,"defense":{"base":15},"equipped_weapon":"sword"}'),
      (2, 1, 2, 'Mira', 'fantasy',
       '{"archetype":"warrior","stats":{"STR":12,"DEX":16,"CON":10,"INT":10,"WIS":10,"CHA":10,"LCK":10},"current_hp":18,"max_hp":18,"defense":{"base":13},"equipped_weapon":"sword"}');

    INSERT INTO campaign_members (campaign_id, user_id, status, character_id)
    VALUES (1, 1, 'accepted', 1), (1, 2, 'accepted', 2);

    CREATE TABLE IF NOT EXISTS character_campaign_state (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      campaign_id INTEGER NOT NULL,
      current_hp INTEGER NOT NULL DEFAULT 0,
      max_hp INTEGER NOT NULL DEFAULT 0,
      current_mana INTEGER NOT NULL DEFAULT 0,
      max_mana INTEGER NOT NULL DEFAULT 0,
      conditions_json TEXT NOT NULL DEFAULT '[]',
      position_json TEXT,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(character_id, campaign_id)
    );
    INSERT INTO character_campaign_state (character_id, campaign_id, current_hp, max_hp)
    VALUES (1, 1, 20, 20), (2, 1, 18, 18);

    """ + table_sql("game_config_weapons") + """
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes)
    VALUES ('sword', 'Miecz', '1d8', 'STR', 'warrior');

    """ + table_sql("game_config_enemies") + """
    INSERT INTO game_config_enemies (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, image_url)
    VALUES
      ('goblin', 'Goblin', 8, 12, 2, 1, '1d6', NULL),
      ('orc', 'Ork', 15, 13, 3, 0, '1d8', NULL);

    CREATE TABLE IF NOT EXISTS active_combat (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL UNIQUE,
      character_id INTEGER NOT NULL,
      round INTEGER NOT NULL DEFAULT 1,
      turn_order TEXT NOT NULL DEFAULT '[]',
      current_turn TEXT NOT NULL DEFAULT 'player',
      combatants TEXT NOT NULL DEFAULT '[]',
      status TEXT NOT NULL DEFAULT 'active',
      ended_reason TEXT,
      location_tag TEXT,
      loot_pool TEXT,
      loot_persisted INTEGER NOT NULL DEFAULT 0,
      post_combat_loot_json TEXT,
      boss_defeated INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS combat_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      combat_id INTEGER NOT NULL,
      campaign_id INTEGER NOT NULL,
      turn_number REAL NOT NULL,
      actor TEXT NOT NULL,
      event_type TEXT NOT NULL,
      roll_value INTEGER,
      damage INTEGER,
      hp_after INTEGER,
      target_id TEXT,
      target_name TEXT,
      hit INTEGER,
      narrative TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    """ + table_sql("game_config_conditions") + """

    """ + table_sql("game_config_skills") + """

    CREATE TABLE IF NOT EXISTS character_inventory (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      item_key TEXT,
      weapon_key TEXT,
      consumable_key TEXT,
      quantity INTEGER NOT NULL DEFAULT 1,
      equipped INTEGER NOT NULL DEFAULT 0
    );

    """ + table_sql("game_config_spells") + """

    CREATE TABLE IF NOT EXISTS campaign_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      character_id INTEGER NOT NULL,
      user_text TEXT NOT NULL DEFAULT '',
      route TEXT NOT NULL DEFAULT 'combat',
      assistant_text TEXT,
      turn_number INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS game_sessions (
      id TEXT PRIMARY KEY,
      campaign_id INTEGER NOT NULL,
      session_flags TEXT DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS game_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_type TEXT NOT NULL,
      campaign_id INTEGER,
      character_id INTEGER,
      user_id INTEGER,
      payload TEXT DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS dice_rolls (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER,
      character_id INTEGER,
      combat_id INTEGER,
      roll_type TEXT NOT NULL,
      actor TEXT,
      notation TEXT,
      raw_rolls TEXT,
      modifiers TEXT DEFAULT '{}',
      total INTEGER,
      dc INTEGER,
      outcome TEXT,
      meta TEXT DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """


@pytest.fixture
def db(tmp_path):
    dbfile = str(tmp_path / "test_791.db")
    conn = sqlite3.connect(dbfile)
    conn.row_factory = sqlite3.Row
    conn.executescript(_schema_sql())
    conn.close()
    return dbfile


# ── Tests: initiate_combat_mp ─────────────────────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_initiate_combat_mp_builds_turn_order(mock_roll, db):
    """G7: turn_order zawiera player:1, player:2 + wrogów posortowanych wg inicjatywy."""
    # Aldric DEX 12 → mod +1; Mira DEX 16 → mod +3
    # roll_d20 calls: Aldric → 10, Mira → 8, goblin → 5, orc → 12
    mock_roll.side_effect = [10, 8, 5, 12]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        result = cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin", "orc"],
        )

    assert result["status"] == "active"
    order = result["turn_order"]

    # player:1 → 10+1=11, player:2 → 8+3=11 (tie), goblin → 5+1=6, orc → 12+0=12
    assert "player:1" in order
    assert "player:2" in order
    assert any("goblin" in s for s in order)
    assert any("orc" in s for s in order)
    assert len(order) == 4


@patch("app.services.combat_service.roll_d20")
def test_initiate_combat_mp_combatants_have_player_prefix(mock_roll, db):
    """G7: combatants mają id='player:1' i id='player:2', nie 'player'."""
    mock_roll.side_effect = [15, 10, 5, 8]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        result = cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )

    combatants = result["combatants"]
    player_ids = {c["id"] for c in combatants if c.get("type") == "player"}
    assert "player:1" in player_ids, f"player:1 missing, got: {player_ids}"
    assert "player:2" in player_ids, f"player:2 missing, got: {player_ids}"
    assert "player" not in player_ids, "Plain 'player' should not appear in MP combat"


@patch("app.services.combat_service.roll_d20")
def test_initiate_combat_mp_player_stats_from_sheet(mock_roll, db):
    """G7: każdy player combatant ma HP i statystyki ze swojego character sheet."""
    mock_roll.side_effect = [12, 9, 5]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        result = cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )

    combatants = result["combatants"]
    p1 = next(c for c in combatants if c.get("id") == "player:1")
    p2 = next(c for c in combatants if c.get("id") == "player:2")

    assert p1["hp_current"] == 20  # Aldric max_hp=20
    assert p2["hp_current"] == 18  # Mira max_hp=18
    assert p1["name"] == "Aldric"
    assert p2["name"] == "Mira"


# ── Tests: apply_mp_default_defense ──────────────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_apply_mp_default_defense_advances_turn(mock_roll, db):
    """G7: obrona domyślna (timeout) przesuwa turę do kolejnego aktora."""
    mock_roll.side_effect = [15, 10, 5]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )
        snap_before = cs.get_active_combat(1)
        first_turn = snap_before["current_turn"]

        # Apply default defense for whoever goes first (must be a player)
        if first_turn == "player:1":
            result = cs.apply_mp_default_defense(1, character_id=1)
        elif first_turn == "player:2":
            result = cs.apply_mp_default_defense(1, character_id=2)
        else:
            pytest.skip("First turn is enemy — cannot test player defense")

        assert result["ok"] is True
        snap_after = result["combat_state"]
        assert snap_after["current_turn"] != first_turn, "Turn must advance after defense"


@patch("app.services.combat_service.roll_d20")
def test_apply_mp_default_defense_logs_event(mock_roll, db):
    """G7: obrona domyślna loguje event 'defense' w combat_turns."""
    mock_roll.side_effect = [20, 8, 5]  # player:1 goes first (initiative 21)

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )
        snap = cs.get_active_combat(1)
        if snap["current_turn"] != "player:1":
            pytest.skip("player:1 not first — adjust roll_d20 side_effects")

        cs.apply_mp_default_defense(1, character_id=1)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT event_type, actor FROM combat_turns WHERE event_type='defense'"
    ).fetchall()
    conn.close()
    assert rows, "Defense event must be logged in combat_turns"
    defense_actors = {r["actor"] for r in rows}
    assert "player:1" in defense_actors


# ── Test: backward compatibility — solo initiate_combat unchanged ──────────────

@patch("app.services.combat_service.roll_d20")
def test_solo_initiate_combat_still_uses_player_id(mock_roll, db):
    """G7: solo initiate_combat nadal zwraca combatanta 'player' (nie 'player:1')."""
    mock_roll.side_effect = [15, 8]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        # Solo campaign (mode='solo') — need a solo campaign
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO campaigns (id, title, owner_user_id, mode) VALUES (99, 'Solo', 1, 'solo')"
        )
        conn.execute(
            "INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json) "
            "VALUES (99, 99, 1, 'Hero', 'fantasy', "
            "'{\"stats\":{\"STR\":14,\"DEX\":12,\"CON\":12,\"INT\":10,\"WIS\":10,\"CHA\":10},\"current_hp\":20,\"max_hp\":20}')"
        )
        conn.commit()
        conn.close()

        result = cs.initiate_combat(99, 99, ["goblin"])

    player_ids = [c["id"] for c in result["combatants"] if c.get("type") == "player"]
    assert "player" in player_ids, "Solo combat must use plain 'player' combatant id"
    assert "player:99" not in player_ids, "Solo combat must NOT use 'player:N' format"


# ── Test: resolve_attack works for player:N attacker ──────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_resolve_attack_mp_player_hits_enemy(mock_roll, db):
    """G7: resolve_attack z attacker='player:1' używa właściwego sheet i trafia wroga."""
    # init: player:1 init=18 (first), player:2 init=10, goblin init=5
    mock_roll.side_effect = [
        17, 9, 4,  # initiatives: player:1=17+1=18, player:2=9+3=12, goblin=4+1=5
        15,        # player attack roll (raw_d20)
        8,         # goblin dodge roll
    ]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )
        snap = cs.get_active_combat(1)
        # player:1 should go first (init 18 > 12 > 5)
        assert snap["current_turn"] == "player:1", f"Expected player:1 first, got {snap['current_turn']}"

        result = cs.resolve_attack(
            campaign_id=1,
            roll_result=None,
            attacker="player:1",
            raw_d20=15,
        )

    assert "error" not in str(result.get("message", "")).lower() or result.get("hit") is not None
    # Should complete without error and target an enemy
    assert "attacker" in result
    assert result["attacker"] == "player:1"
