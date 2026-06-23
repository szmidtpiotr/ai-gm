"""TDD #962 — revive action must run enemy auto-resolve loop.

submit_mp_combat_action(action_type='revive') had an early return that skipped
the enemy auto-resolve loop (lines 2038-2054 in multiplayer_round_service.py).
After revive, current_turn pointed at an enemy — the next player couldn't act.

Fix: run the auto-resolve loop before returning from the revive branch.
"""
import json
import os
import sqlite3
import sys
from unittest.mock import patch

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest

from app.services import admin_config
from app.services import combat_service as cs
from app.services import multiplayer_round_service as mrs


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
      status TEXT NOT NULL DEFAULT 'active',
      gold_gp INTEGER NOT NULL DEFAULT 0
    );
    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json, gold_gp)
    VALUES
      (1, 1, 1, 'Aldric', 'fantasy',
       '{"archetype":"warrior","level":5,"stats":{"STR":14,"DEX":12,"CON":12,"INT":10,"WIS":10,"CHA":10,"LCK":10},"current_hp":20,"max_hp":20,"defense":{"base":15},"equipped_weapon":"sword"}',
       100),
      (2, 1, 2, 'Mira', 'fantasy',
       '{"archetype":"warrior","level":5,"stats":{"STR":12,"DEX":16,"CON":10,"INT":10,"WIS":10,"CHA":10,"LCK":10},"current_hp":18,"max_hp":18,"defense":{"base":13},"equipped_weapon":"sword"}',
       30);

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
    VALUES ('sword', 'Miecz', '1d6', 'STR', 'warrior');

    """ + table_sql("game_config_enemies") + """
    INSERT INTO game_config_enemies (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, image_url)
    VALUES ('goblin', 'Goblin', 12, 12, 2, 1, '1d6', NULL);

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
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      combat_turn_deadline TEXT
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

    CREATE TABLE IF NOT EXISTS state_changes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER,
      character_id INTEGER,
      combat_id INTEGER,
      resource TEXT NOT NULL,
      before_val INTEGER,
      after_val INTEGER,
      cause TEXT,
      meta TEXT DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS character_gold_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      delta INTEGER NOT NULL,
      reason TEXT,
      campaign_id INTEGER,
      game_clock_day INTEGER NOT NULL DEFAULT 1,
      wall_clock_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS character_spells (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      spell_key TEXT NOT NULL,
      rank INTEGER NOT NULL DEFAULT 1,
      UNIQUE(character_id, spell_key)
    );
    """


@pytest.fixture
def db(tmp_path):
    dbfile = str(tmp_path / "test_962.db")
    conn = sqlite3.connect(dbfile)
    conn.row_factory = sqlite3.Row
    conn.executescript(_schema_sql())
    conn.close()
    return dbfile


def _conn(db: str) -> sqlite3.Connection:
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def _knock_player(db: str, campaign_id: int, player_actor_id: str) -> None:
    """Set a combatant as knocked (hp=0, knocked=True)."""
    conn = _conn(db)
    row = conn.execute(
        "SELECT combatants FROM active_combat WHERE campaign_id=? AND status='active'",
        (campaign_id,),
    ).fetchone()
    assert row, "no active combat"
    combatants = json.loads(row["combatants"] or "[]")
    for c in combatants:
        if c.get("id") == player_actor_id:
            c["hp_current"] = 0
            c["knocked"] = True
            break
    conn.execute(
        "UPDATE active_combat SET combatants=? WHERE campaign_id=? AND status='active'",
        (json.dumps(combatants), campaign_id),
    )
    conn.commit()
    conn.close()


def _set_current_turn(db: str, campaign_id: int, actor_id: str) -> None:
    """Force current_turn to a specific actor."""
    conn = _conn(db)
    conn.execute(
        "UPDATE active_combat SET current_turn=? WHERE campaign_id=? AND status='active'",
        (actor_id, campaign_id),
    )
    conn.commit()
    conn.close()


# ── Test główny ───────────────────────────────────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_revive_action_runs_enemy_auto_resolve(mock_roll, db):
    """#962: After revive, enemy turns must be auto-resolved (not skipped by early return).

    Turn order: player:1 → player:2 → goblin_01
    player:1 knocked, player:2 casts revive.
    Expected: goblin auto-resolves its turn; result['enemy_results'] is non-empty;
    combat_state.current_turn ends up on a player, not goblin.
    """
    # Initiatives: player:1 high (20), player:2 medium (9), goblin low (3)
    # → turn order: player:1, player:2, goblin_01
    # Enemy auto-resolve: attack=10, defense roll=5
    mock_roll.side_effect = [
        19,  # player:1 init (19 + DEX_mod=1 = 20)
        8,   # player:2 init (8 + DEX_mod=3 = 11)
        2,   # goblin init (2 + dex_modifier=1 = 3)
        10,  # enemy attack roll during auto-resolve
        5,   # player defense roll during auto-resolve
    ]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db), \
         patch("app.services.multiplayer_round_service.resolve_db_path", return_value=db), \
         patch("app.services.multiplayer_round_service.send_push"), \
         patch("app.services.multiplayer_round_service.send_push_to_campaign_players"):

        # Start MP combat: player:1 first, player:2 second, goblin last
        cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )
        snap = cs.get_active_combat(1)
        assert snap is not None, "combat not started"
        assert snap["status"] == "active"

        # Verify turn order has goblin after player:2
        order = json.loads(snap["turn_order"]) if isinstance(snap["turn_order"], str) else snap["turn_order"]
        assert any("player" in str(s) for s in order), f"no players in order: {order}"

        # Setup: player:1 knocked, player:2's turn
        _knock_player(db, 1, "player:1")
        _set_current_turn(db, 1, "player:2")

        # Player:2 revives player:1
        result = mrs.submit_mp_combat_action(
            campaign_id=1,
            user_id=2,
            character_id=2,
            action_type="revive",
            target_id="player:1",
        )

    # KEY ASSERTION: enemy auto-resolve loop must have run
    assert result.get("enemy_results") is not None, \
        "enemy_results key missing from revive response"
    assert len(result["enemy_results"]) > 0, (
        f"enemy_results is empty after revive — auto-resolve loop was skipped. "
        f"combat_state.current_turn={result.get('combat_state', {}).get('current_turn')}"
    )

    # After enemy auto-resolve, current_turn must be a player
    final_turn = result.get("combat_state", {}).get("current_turn", "")
    assert str(final_turn).startswith("player:"), (
        f"After revive + enemy auto-resolve, current_turn should be a player, "
        f"got: '{final_turn}' — enemy blocking queue"
    )

    # player:1 must be revived (not knocked)
    combatants = result.get("combat_state", {}).get("combatants", [])
    p1 = next((c for c in combatants if c.get("id") == "player:1"), None)
    assert p1 is not None, "player:1 missing from combatants"
    assert p1.get("knocked") is not True, "player:1 still knocked after revive"
    assert p1.get("hp_current", 0) > 0, "player:1 hp still 0 after revive"


# ── Backward compatibility ────────────────────────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_attack_action_still_auto_resolves_enemies(mock_roll, db):
    """Attack action auto-resolve must not regress after #962 fix."""
    # player:2 goes first (high init), goblin second, player:1 third
    # → player:2 attacks, goblin auto-resolves, ends at player:1
    mock_roll.side_effect = [
        2,   # player:1 init (low)
        19,  # player:2 init (high → goes first)
        8,   # goblin init (mid)
        # player:2 attack:
        14,  # d20 attack roll
        5,   # player:1 defense roll
        # goblin auto-resolve:
        10,  # goblin attack
        4,   # player:2 defense
    ]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db), \
         patch("app.services.multiplayer_round_service.resolve_db_path", return_value=db), \
         patch("app.services.multiplayer_round_service.send_push"), \
         patch("app.services.multiplayer_round_service.send_push_to_campaign_players"):

        cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )
        snap = cs.get_active_combat(1)
        assert snap is not None

        # Set player:2's turn manually for deterministic test
        _set_current_turn(db, 1, "player:2")

        result = mrs.submit_mp_combat_action(
            campaign_id=1,
            user_id=2,
            character_id=2,
            action_type="attack",
            target_id=None,
            raw_d20=14,
            roll_result=14,
        )

    # Attack should also produce enemy_results (pre-existing behavior)
    assert result.get("enemy_results") is not None, "enemy_results missing from attack response"
    # Final turn should be a player
    final_turn = result.get("combat_state", {}).get("current_turn", "")
    assert str(final_turn).startswith("player:"), (
        f"After attack + goblin auto-resolve, expected player turn, got: '{final_turn}'"
    )
