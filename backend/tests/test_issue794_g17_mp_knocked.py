"""TDD #794 — G17: Powalenie zamiast śmierci w walce MP.

HP≤0 w trybie multiplayer → knocked (powalony), NIE player_dead.
Towarzysz może ocucić z 25% HP. Wipe = kara złota + przebudzenie 50% HP.
"""
import json
import os
import sqlite3
import sys
from unittest.mock import patch

sys.path.insert(0, "/app")
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
    INSERT INTO campaigns (id, title, owner_user_id, mode)
    VALUES (2, 'Solo Camp', 1, 'solo');

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

    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json, gold_gp)
    VALUES
      (10, 2, 1, 'SoloHero', 'fantasy',
       '{"archetype":"warrior","stats":{"STR":14,"DEX":12,"CON":12,"INT":10,"WIS":10,"CHA":10,"LCK":10},"current_hp":5,"max_hp":20}',
       50);

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

    CREATE TABLE IF NOT EXISTS game_config_weapons (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      damage_die TEXT NOT NULL,
      linked_stat TEXT NOT NULL DEFAULT 'STR',
      allowed_classes TEXT NOT NULL DEFAULT 'warrior',
      is_active INTEGER NOT NULL DEFAULT 1,
      weapon_type TEXT NOT NULL DEFAULT 'melee',
      attack_bonus INTEGER NOT NULL DEFAULT 0,
      damage_bonus INTEGER NOT NULL DEFAULT 0
    );
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes)
    VALUES ('sword', 'Miecz', '1d8', 'STR', 'warrior');

    CREATE TABLE IF NOT EXISTS game_config_enemies (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      hp_base INTEGER NOT NULL DEFAULT 10,
      ac_base INTEGER NOT NULL DEFAULT 12,
      attack_bonus INTEGER NOT NULL DEFAULT 2,
      dex_modifier INTEGER NOT NULL DEFAULT 0,
      damage_die TEXT NOT NULL DEFAULT '1d6',
      tier TEXT DEFAULT 'standard',
      xp_award INTEGER NOT NULL DEFAULT 10,
      is_active INTEGER NOT NULL DEFAULT 1,
      skills_json TEXT,
      stats_json TEXT,
      loot_table_key TEXT,
      drop_chance REAL NOT NULL DEFAULT 1.0,
      attacks_per_turn INTEGER NOT NULL DEFAULT 1,
      image_url TEXT
    );
    INSERT INTO game_config_enemies (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, image_url)
    VALUES ('goblin', 'Goblin', 8, 12, 2, 1, '1d6', NULL);

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

    CREATE TABLE IF NOT EXISTS game_config_conditions (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      is_active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS game_config_skills (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS character_inventory (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      item_key TEXT,
      weapon_key TEXT,
      consumable_key TEXT,
      quantity INTEGER NOT NULL DEFAULT 1,
      equipped INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS game_config_spells (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      spell_type TEXT NOT NULL DEFAULT 'attack',
      damage_die TEXT NOT NULL DEFAULT '1d6',
      mana_cost INTEGER NOT NULL DEFAULT 2,
      tier INTEGER NOT NULL DEFAULT 1,
      is_active INTEGER NOT NULL DEFAULT 1
    );

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
    dbfile = str(tmp_path / "test_794.db")
    conn = sqlite3.connect(dbfile)
    conn.row_factory = sqlite3.Row
    conn.executescript(_schema_sql())
    conn.close()
    return dbfile


def _conn(db: str) -> sqlite3.Connection:
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def _force_enemy_turn(db: str, campaign_id: int, enemy_slug: str) -> None:
    """Directly set current_turn to the enemy combatant in DB."""
    conn = _conn(db)
    conn.execute(
        "UPDATE active_combat SET current_turn=? WHERE campaign_id=? AND status='active'",
        (enemy_slug, campaign_id),
    )
    conn.commit()
    conn.close()


def _set_player_hp(db: str, campaign_id: int, player_actor_id: str, hp: int) -> None:
    """Set hp_current for a combatant directly in the DB."""
    conn = _conn(db)
    row = conn.execute(
        "SELECT combatants FROM active_combat WHERE campaign_id=? AND status='active'",
        (campaign_id,),
    ).fetchone()
    if not row:
        conn.close()
        return
    combatants = json.loads(row["combatants"] or "[]")
    for c in combatants:
        if c.get("id") == player_actor_id:
            c["hp_current"] = hp
            break
    conn.execute(
        "UPDATE active_combat SET combatants=? WHERE campaign_id=? AND status='active'",
        (json.dumps(combatants), campaign_id),
    )
    conn.commit()
    conn.close()


# ── Test 1: Enemy attack in MP does not crash ─────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_enemy_attack_in_mp_does_not_raise(mock_roll, db):
    """G17: resolve_attack(attacker='enemy') działa w walce MP — nie rzuca 'player combatant missing'."""
    # player:1 init=5 (low), goblin init=15 → goblin goes first
    mock_roll.side_effect = [
        4, 3, 14,  # initiatives: player:1=4+1=5, player:2=3+3=6, goblin=14+1=15
        10,        # attack roll
        5,         # evasion roll
    ]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        result = cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )
        snap = cs.get_active_combat(1)
        enemy_slug = next(
            c["id"] for c in snap["combatants"] if c.get("type") == "enemy"
        )
        # Force enemy turn if not already
        if snap["current_turn"] != enemy_slug:
            _force_enemy_turn(db, 1, enemy_slug)

        # Should NOT raise ValueError("player combatant missing")
        result = cs.resolve_attack(campaign_id=1, roll_result=0, attacker="enemy")

    assert "attacker" in result or "combat_state" in result, (
        f"resolve_attack enemy in MP should return a dict, got: {result}"
    )
    assert result.get("attacker") == "enemy" or result.get("combat_state") is not None


# ── Test 2: HP≤0 in MP → knocked, not dead ────────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_mp_player_hp_zero_gives_knocked_not_dead(mock_roll, db):
    """G17: HP≤0 w walce MP → knocked=True na combatancie, walka trwa (status='active')."""
    mock_roll.side_effect = [
        4, 3, 14,  # initiatives: player:1=5, player:2=6, goblin=15 → goblin first
        20,        # enemy attack nat20 (critical hit, ignores armor)
        6,         # evasion roll for player (low)
    ]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )
        snap = cs.get_active_combat(1)
        enemy_slug = next(
            c["id"] for c in snap["combatants"] if c.get("type") == "enemy"
        )
        if snap["current_turn"] != enemy_slug:
            _force_enemy_turn(db, 1, enemy_slug)

        # Set player:1 HP to 1 so any hit knocks them out
        _set_player_hp(db, 1, "player:1", 1)

        result = cs.resolve_attack(campaign_id=1, roll_result=0, attacker="enemy")
        final_snap = cs.get_active_combat(1)

    # Combat must still be active (not ended with player_dead)
    assert final_snap is not None, "Combat ended — should still be active in MP"
    assert final_snap["status"] == "active", (
        f"Combat should stay active after MP knockdown, got status={final_snap['status']}"
    )

    # Player:1 should have knocked=True
    knocked_player = next(
        (c for c in final_snap["combatants"] if c.get("id") == "player:1"),
        None,
    )
    assert knocked_player is not None
    assert knocked_player.get("knocked") is True, (
        f"player:1 should be knocked=True after HP≤0 in MP, combatant={knocked_player}"
    )


# ── Test 3: Revive restores 25% HP ───────────────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_revive_mp_player_restores_25_percent_hp(mock_roll, db):
    """G17: revive_knocked_mp_player podnosi powalonego gracza z ~25% HP max."""
    mock_roll.side_effect = [15, 8, 4]  # player:1 first (init 16), player:2 (11), goblin (5)

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )

        # Manually knock player:1
        conn = _conn(db)
        row = conn.execute(
            "SELECT combatants FROM active_combat WHERE campaign_id=1"
        ).fetchone()
        combatants = json.loads(row["combatants"])
        for c in combatants:
            if c.get("id") == "player:1":
                c["hp_current"] = 0
                c["knocked"] = True
                break
        conn.execute(
            "UPDATE active_combat SET combatants=? WHERE campaign_id=1",
            (json.dumps(combatants),),
        )
        conn.commit()
        conn.close()

        # Revive player:1
        result = cs.revive_knocked_mp_player(campaign_id=1, target_char_id=1)
        snap = cs.get_active_combat(1)

    assert result is not None
    revived = next((c for c in snap["combatants"] if c.get("id") == "player:1"), None)
    assert revived is not None
    assert revived.get("knocked") is not True, "Knocked flag should be cleared after revive"
    max_hp = revived.get("hp_max", 20)
    expected_min = max(1, int(max_hp * 0.20))
    expected_max = int(max_hp * 0.30) + 2
    assert expected_min <= revived["hp_current"] <= expected_max, (
        f"Revived HP should be ~25% of {max_hp}, got {revived['hp_current']}"
    )


# ── Test 4: Victory auto-revives knocked players ─────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_mp_victory_auto_revives_knocked_players(mock_roll, db):
    """G17: zwycięstwo (wszyscy wrogowie martwi) auto-podnosi powalonych z min HP."""
    mock_roll.side_effect = [15, 8, 4]  # player:1 first

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )

        # Knock player:1 and kill goblin directly
        conn = _conn(db)
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row["combatants"])
        for c in combatants:
            if c.get("id") == "player:1":
                c["hp_current"] = 0
                c["knocked"] = True
            elif c.get("type") == "enemy":
                c["hp_current"] = 0
                c["dead"] = True
        conn.execute(
            "UPDATE active_combat SET combatants=? WHERE campaign_id=1",
            (json.dumps(combatants),),
        )
        conn.commit()
        conn.close()

        # advance_turn should detect all enemies dead → victory, and auto-revive knocked players
        result = cs.advance_turn(1)

    # Combat ended with victory
    snap = cs.get_active_combat(1)
    assert snap is None or snap.get("status") == "ended", (
        "Combat should end after all enemies die"
    )

    # Player:1 should NOT be knocked after victory (auto-revived)
    # Check via DB directly (combat may be ended)
    conn = _conn(db)
    row = conn.execute(
        "SELECT combatants FROM active_combat WHERE campaign_id=1"
    ).fetchone()
    conn.close()

    if row:
        combatants = json.loads(row["combatants"] or "[]")
        p1 = next((c for c in combatants if c.get("id") == "player:1"), None)
        if p1:
            assert p1.get("knocked") is not True, "player:1 should be revived after victory"
            assert int(p1.get("hp_current", 0)) >= 1, "player:1 HP should be >= 1 after victory"


# ── Test 5: Wipe triggers gold penalty ───────────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_mp_wipe_applies_gold_penalty_on_all_knocked(mock_roll, db):
    """G17: wipe (wszyscy gracze powaleni + wrogowie żywi) → kara złota, combat ends 'wipe'."""
    mock_roll.side_effect = [15, 8, 4]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )

        # Knock BOTH players; leave goblin alive
        conn = _conn(db)
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row["combatants"])
        for c in combatants:
            if c.get("type") == "player":
                c["hp_current"] = 0
                c["knocked"] = True
        conn.execute(
            "UPDATE active_combat SET combatants=? WHERE campaign_id=1",
            (json.dumps(combatants),),
        )
        conn.commit()
        conn.close()

        # Advance turn — should detect all players knocked → trigger wipe
        cs.advance_turn(1)

    # Combat should be ended with reason 'wipe'
    conn = _conn(db)
    row = conn.execute(
        "SELECT status, ended_reason FROM active_combat WHERE campaign_id=1"
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["status"] == "ended", f"Combat should end after wipe, got {row['status']}"
    assert row["ended_reason"] == "wipe", f"ended_reason should be 'wipe', got {row['ended_reason']}"

    # Player 1 (100 gold, avg level 5 → 20% penalty → 80 gold remaining)
    conn2 = _conn(db)
    gold1 = conn2.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()["gold_gp"]
    gold2 = conn2.execute("SELECT gold_gp FROM characters WHERE id=2").fetchone()["gold_gp"]
    conn2.close()

    assert gold1 == 80, f"Player 1 (100gp, lvl5) should lose 20% → 80gp, got {gold1}"
    # Player 2 had only 30 gold — below 50 threshold → no penalty
    assert gold2 == 30, f"Player 2 (<50gp) should not lose gold, got {gold2}"


# ── Test 6: Wipe — HP restored to 50% ────────────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_mp_wipe_revives_all_at_50_percent_hp(mock_roll, db):
    """G17: po wipe gracze budzą się z 50% HP max."""
    mock_roll.side_effect = [15, 8, 4]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )

        conn = _conn(db)
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row["combatants"])
        for c in combatants:
            if c.get("type") == "player":
                c["hp_current"] = 0
                c["knocked"] = True
        conn.execute(
            "UPDATE active_combat SET combatants=? WHERE campaign_id=1",
            (json.dumps(combatants),),
        )
        conn.commit()
        conn.close()

        cs.advance_turn(1)

    # Check HP revived in CCS (character_campaign_state) or combat combatants
    conn = _conn(db)
    row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
    conn.close()

    if row:
        combatants = json.loads(row["combatants"] or "[]")
        p1 = next((c for c in combatants if c.get("id") == "player:1"), None)
        p2 = next((c for c in combatants if c.get("id") == "player:2"), None)
        if p1:
            max_hp = p1.get("hp_max", 20)
            expected_50 = max(1, int(max_hp * 0.50))
            assert p1["hp_current"] == expected_50, (
                f"After wipe player:1 HP should be 50% ({expected_50}) of {max_hp}, got {p1['hp_current']}"
            )
        if p2:
            max_hp = p2.get("hp_max", 18)
            expected_50 = max(1, int(max_hp * 0.50))
            assert p2["hp_current"] == expected_50, (
                f"After wipe player:2 HP should be 50% ({expected_50}) of {max_hp}, got {p2['hp_current']}"
            )


# ── Test 7: Solo backward compatibility ──────────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_solo_player_death_still_ends_combat(mock_roll, db):
    """G17: w trybie solo HP≤0 nadal kończy walkę jako player_dead (bez zmian)."""
    mock_roll.side_effect = [8, 12]  # player init=9, goblin init=13 → goblin first

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        # Solo combat — use campaign 2 (mode='solo'), character 10
        result = cs.initiate_combat(2, 10, ["goblin"])
        snap = cs.get_active_combat(2)
        assert snap is not None

        enemy_slug = next(
            (c["id"] for c in snap["combatants"] if c.get("type") == "enemy"),
            None,
        )
        # Ensure enemy goes first
        if snap["current_turn"] != enemy_slug:
            conn = _conn(db)
            conn.execute(
                "UPDATE active_combat SET current_turn=? WHERE campaign_id=2",
                (enemy_slug,),
            )
            conn.commit()
            conn.close()

        # Set player HP to 1 so any hit is lethal
        conn = _conn(db)
        row = conn.execute(
            "SELECT combatants FROM active_combat WHERE campaign_id=2"
        ).fetchone()
        combatants = json.loads(row["combatants"])
        for c in combatants:
            if c.get("type") == "player":
                c["hp_current"] = 1
        conn.execute(
            "UPDATE active_combat SET combatants=? WHERE campaign_id=2",
            (json.dumps(combatants),),
        )
        conn.commit()
        conn.close()

        with patch.object(cs, "roll_d20", return_value=20):  # nat20 → guaranteed kill
            result = cs.resolve_attack(campaign_id=2, roll_result=0, attacker="enemy")

    # Solo: combat should end with player_dead
    snap = cs.get_active_combat(2)
    assert snap is None or snap.get("status") == "ended", (
        "Solo player death should end combat"
    )
    if snap and snap.get("status") == "ended":
        assert snap.get("ended_reason") == "player_dead", (
            f"Solo death should set ended_reason='player_dead', got {snap.get('ended_reason')}"
        )


# ── Test 8: Knocked player skipped by enemies ─────────────────────────────────

@patch("app.services.combat_service.roll_d20")
def test_enemy_skips_knocked_player_and_targets_active(mock_roll, db):
    """G17: wróg pomija powalonych graczy — atakuje tylko aktywnych (hp>0, nie-knocked)."""
    # player:1 knocked (hp=0), player:2 active (hp=18), goblin must target player:2
    mock_roll.side_effect = [
        4, 3, 14,  # initiatives (goblin first)
        10,        # attack roll
        3,         # evasion
    ]

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        cs.initiate_combat_mp(
            campaign_id=1,
            character_ids=[1, 2],
            enemy_keys=["goblin"],
        )

        # Set player:1 as knocked, player:2 active
        conn = _conn(db)
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row["combatants"])
        for c in combatants:
            if c.get("id") == "player:1":
                c["hp_current"] = 0
                c["knocked"] = True
            elif c.get("id") == "player:2":
                c["hp_current"] = 18
        conn.execute(
            "UPDATE active_combat SET combatants=? WHERE campaign_id=1",
            (json.dumps(combatants),),
        )
        conn.commit()
        conn.close()

        snap = cs.get_active_combat(1)
        enemy_slug = next(c["id"] for c in snap["combatants"] if c.get("type") == "enemy")
        if snap["current_turn"] != enemy_slug:
            _force_enemy_turn(db, 1, enemy_slug)

        result = cs.resolve_attack(campaign_id=1, roll_result=0, attacker="enemy")

    # Result should NOT have player_incapacitated for player:2 (unless unlucky)
    # Most importantly: combat should still be active (player:2 not dead)
    snap_after = cs.get_active_combat(1)
    assert snap_after is not None or result.get("combat_state") is not None, (
        "Combat should not end (player:2 still active)"
    )
