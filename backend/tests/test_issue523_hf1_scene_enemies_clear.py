"""TDD: Issue #523 (HF-1) — scene_enemies must be cleared after victory in resolve_attack.

Bug: when the last enemy dies inside resolve_attack/_advance_turn_impl the code calls
_persist_combatants_and_maybe_end(status="ended") but never calls
set_world_state_flags(scene_enemies=[]).  end_combat() does call it; the two victory
paths that bypass end_combat() do not.

Result: Gate walki widzi niepustą listę wrogów → blokuje każdą akcję po walce (softlock P0).

Fix: po każdym _persist_combatants_and_maybe_end(status="ended") wywołać
set_world_state_flags(campaign_id, scene_enemies=[]).
"""
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import admin_config
from app.services import combat_service as cs
from app.services import world_state_service as wss


# ── Minimal schema for temp DB ─────────────────────────────────────────────

def _schema_sql() -> str:
    return """
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      display_name TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1, 'u', 'x', 'U');

    CREATE TABLE campaigns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      system_id TEXT NOT NULL,
      model_id TEXT NOT NULL,
      owner_user_id INTEGER NOT NULL,
      language TEXT NOT NULL DEFAULT 'pl',
      mode TEXT NOT NULL DEFAULT 'solo',
      status TEXT NOT NULL DEFAULT 'active',
      death_reason TEXT,
      ended_at TEXT,
      epitaph TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id)
    VALUES (1, 'T', 'fantasy', 'm', 1);

    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      system_id TEXT NOT NULL,
      sheet_json TEXT NOT NULL,
      location TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      status TEXT NOT NULL DEFAULT 'active',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
    VALUES (
      1, 1, 1, 'Aldric', 'fantasy',
      '{"archetype":"warrior","stats":{"STR":14,"DEX":12,"CON":12,"INT":10,"WIS":10,"CHA":10,"LCK":10},"current_hp":20,"max_hp":20,"defense":{"base":15},"equipped_weapon":"sword"}'
    );

    CREATE TABLE game_config_weapons (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      damage_die TEXT NOT NULL,
      linked_stat TEXT NOT NULL,
      allowed_classes TEXT NOT NULL DEFAULT 'warrior',
      weapon_type TEXT NOT NULL DEFAULT 'melee',
      attack_bonus INTEGER NOT NULL DEFAULT 0,
      damage_bonus INTEGER NOT NULL DEFAULT 0,
      effect_json TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes, weapon_type)
    VALUES ('sword', 'Sword', '1d8', 'STR', 'warrior', 'melee');

    CREATE TABLE game_config_enemies (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      hp_base INTEGER NOT NULL,
      ac_base INTEGER NOT NULL,
      attack_bonus INTEGER NOT NULL,
      dex_modifier INTEGER NOT NULL DEFAULT 0,
      damage_die TEXT NOT NULL DEFAULT '1d6',
      tier TEXT NOT NULL DEFAULT 'standard',
      xp_award INTEGER NOT NULL DEFAULT 0,
      description TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      skills_json TEXT,
      loot_table_key TEXT,
      drop_chance REAL NOT NULL DEFAULT 0.0,
      loot_tier TEXT DEFAULT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, loot_table_key, drop_chance)
    VALUES ('bandit', 'Bandit', 1, 1, 0, 0, '1d4', NULL, 0.0);

    CREATE TABLE IF NOT EXISTS game_config_meta (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS active_combat (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL UNIQUE,
      character_id INTEGER NOT NULL,
      round INTEGER NOT NULL DEFAULT 1,
      turn_order TEXT NOT NULL,
      current_turn TEXT NOT NULL,
      combatants TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      ended_reason TEXT,
      location_tag TEXT DEFAULT NULL,
      loot_pool TEXT DEFAULT NULL,
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
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );

    CREATE TABLE IF NOT EXISTS game_sessions (
      id TEXT PRIMARY KEY,
      campaign_id INTEGER,
      test_run_id TEXT,
      session_flags TEXT DEFAULT '{}',
      scene_enemies TEXT NOT NULL DEFAULT '[]',
      scene_npcs TEXT NOT NULL DEFAULT '[]',
      scene_cleared INTEGER NOT NULL DEFAULT 0,
      active_quests TEXT NOT NULL DEFAULT '[]',
      player_conditions TEXT NOT NULL DEFAULT '[]',
      ingame_hours INTEGER NOT NULL DEFAULT 9,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    INSERT INTO game_sessions (id, campaign_id, session_flags, scene_enemies)
    VALUES ('sess1', 1, '{"current_hex":{"q":0,"r":0}}', '[]');

    CREATE TABLE IF NOT EXISTS campaign_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      character_id INTEGER NOT NULL,
      user_text TEXT NOT NULL,
      route TEXT NOT NULL,
      assistant_text TEXT,
      turn_number INTEGER NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS campaign_hex_data (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      hex_q INTEGER NOT NULL,
      hex_r INTEGER NOT NULL,
      discovered INTEGER NOT NULL DEFAULT 0,
      encounter_cleared INTEGER NOT NULL DEFAULT 0,
      UNIQUE(campaign_id, hex_q, hex_r)
    );

    CREATE TABLE IF NOT EXISTS character_inventory (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      item_key TEXT,
      weapon_key TEXT,
      consumable_key TEXT,
      quantity INTEGER NOT NULL DEFAULT 1,
      equipped INTEGER NOT NULL DEFAULT 0,
      affixes_json TEXT DEFAULT NULL,
      durability_current INTEGER DEFAULT NULL,
      durability_max INTEGER DEFAULT NULL
    );

    CREATE TABLE IF NOT EXISTS character_conditions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      condition_key TEXT NOT NULL,
      duration_turns INTEGER,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS game_config_conditions (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      effect_json TEXT,
      is_active INTEGER NOT NULL DEFAULT 1
    );
    """


def _set_scene_enemies(conn: sqlite3.Connection, campaign_id: int, enemies: list) -> None:
    conn.execute(
        "UPDATE game_sessions SET scene_enemies=? WHERE campaign_id=?",
        (json.dumps(enemies, ensure_ascii=False), campaign_id),
    )
    conn.commit()


def _get_scene_enemies(db_path: str, campaign_id: int) -> list:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT scene_enemies FROM game_sessions WHERE campaign_id=? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row:
            return []
        return json.loads(row["scene_enemies"] or "[]")
    finally:
        conn.close()


# ── Test class ─────────────────────────────────────────────────────────────

class TestHF1SceneEnemiesClear(unittest.TestCase):
    """HF-1: scene_enemies must be [] after victory in resolve_attack and advance_turn paths."""

    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_hf1_test.db"
        if self._tmp.exists():
            self._tmp.unlink()
        conn = sqlite3.connect(str(self._tmp))
        conn.executescript(_schema_sql())
        conn.close()

        self._p_db = patch.object(cs, "COMBAT_DB_PATH", str(self._tmp))
        self._p_admin = patch.object(admin_config, "DB_PATH", str(self._tmp))
        self._p_wss = patch.object(wss, "DB_PATH", str(self._tmp))
        self._p_db.start()
        self._p_admin.start()
        self._p_wss.start()

    def tearDown(self):
        self._p_wss.stop()
        self._p_admin.stop()
        self._p_db.stop()
        if self._tmp.exists():
            self._tmp.unlink()

    def _seed_scene_enemies(self, entries: list) -> None:
        """Set scene_enemies to non-empty so we can verify it gets cleared."""
        conn = sqlite3.connect(str(self._tmp))
        _set_scene_enemies(conn, 1, entries)
        conn.close()

    def _read_scene_enemies(self) -> list:
        return _get_scene_enemies(str(self._tmp), 1)

    # ── Test 1: advance_turn path ──────────────────────────────────────────

    @patch("app.services.combat_service.roll_d20", return_value=10)
    def test_advance_turn_clears_scene_enemies_when_all_enemies_dead(self, _d20):
        """
        RED: advance_turn with all-dead enemies must clear scene_enemies.

        _advance_turn_impl calls _persist_combatants_and_maybe_end(status='ended')
        but currently does NOT call set_world_state_flags(scene_enemies=[]).
        After fix: scene_enemies == [] after advance_turn finds all enemies dead.
        """
        # Start combat to get a real combat row
        cs.initiate_combat(1, 1, ["bandit"])

        # Manually set scene_enemies to non-empty (simulating what happens during combat)
        self._seed_scene_enemies([{"id": "enemy_1", "hp": 0, "name": "Bandit"}])

        # Kill the enemy directly in DB to trigger the "all dead" path
        conn = sqlite3.connect(str(self._tmp))
        row = conn.execute(
            "SELECT combatants FROM active_combat WHERE campaign_id=1 AND status='active'"
        ).fetchone()
        combatants = json.loads(row[0])
        for c in combatants:
            if c.get("type") == "enemy":
                c["hp_current"] = 0
                c["dead"] = True
        conn.execute(
            "UPDATE active_combat SET combatants=? WHERE campaign_id=1",
            (json.dumps(combatants, ensure_ascii=False),),
        )
        conn.commit()
        conn.close()

        # Verify pre-condition: scene_enemies is currently non-empty (bug state)
        assert self._read_scene_enemies() != [], "Pre-condition: scene_enemies should be non-empty before test"

        # advance_turn should detect all enemies dead → status='ended' → clear scene_enemies
        result = cs.advance_turn(1)

        assert result == "ended", f"Expected 'ended', got: {result!r}"

        scene_enemies_after = self._read_scene_enemies()
        assert scene_enemies_after == [], (
            f"BUG HF-1: scene_enemies NOT cleared after advance_turn victory!\n"
            f"  Got: {scene_enemies_after}\n"
            f"  Expected: []\n"
            f"  This causes softlock: Gate walki blokuje każdą akcję po walce."
        )

    # ── Test 2: resolve_attack killing-blow path ───────────────────────────

    @patch("app.services.combat_service.roll_d20", return_value=20)       # nat20, always hit
    @patch("app.services.combat_service.roll_damage_dice", return_value=999)  # overkill damage
    @patch("app.services.loot_service.roll_loot", return_value=[])
    @patch("app.services.loot_service.roll_gold_drop", return_value=0)
    def test_resolve_attack_clears_scene_enemies_on_last_enemy_kill(
        self, _gold, _loot, _dmg, _d20
    ):
        """
        RED: resolve_attack killing the last enemy must clear scene_enemies.

        Currently _persist_combatants_and_maybe_end(status='ended') is called
        but set_world_state_flags(scene_enemies=[]) is NOT called.
        After fix: scene_enemies == [] after resolve_attack kills last enemy.
        """
        cs.initiate_combat(1, 1, ["bandit"])

        # Seed scene_enemies to non-empty (simulating combat-start sync)
        self._seed_scene_enemies([{"id": "enemy_1", "hp": 1, "name": "Bandit"}])

        # Verify pre-condition
        assert self._read_scene_enemies() != [], "Pre-condition: scene_enemies should be non-empty"

        # Player attacks with nat20 + 999 damage → bandit dies → all enemies dead
        result = cs.resolve_attack(1, roll_result=20, attacker="player", raw_d20=20)

        assert result.get("enemy_dead") is True, (
            f"Enemy should be dead: {result.get('enemy_dead')}, damage={result.get('damage')}"
        )

        scene_enemies_after = self._read_scene_enemies()
        assert scene_enemies_after == [], (
            f"BUG HF-1: scene_enemies NOT cleared after resolve_attack killing blow!\n"
            f"  Got: {scene_enemies_after}\n"
            f"  Expected: []\n"
            f"  This is the P0 softlock: next turn Gate sees enemies → blocks all actions."
        )

    # ── Test 3: backward compat — end_combat path still works ─────────────

    @patch("app.services.combat_service.roll_d20", return_value=10)
    def test_end_combat_still_clears_scene_enemies(self, _d20):
        """
        Backward compat: existing end_combat path must still clear scene_enemies.
        """
        cs.initiate_combat(1, 1, ["bandit"])
        self._seed_scene_enemies([{"id": "enemy_1", "hp": 5, "name": "Bandit"}])

        cs.end_combat(1, "victory")

        assert self._read_scene_enemies() == [], (
            "Regression: end_combat path should still clear scene_enemies!"
        )


if __name__ == "__main__":
    unittest.main()
