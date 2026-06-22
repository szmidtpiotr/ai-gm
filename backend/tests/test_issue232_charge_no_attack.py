"""Issue #232 — a melee enemy that charges (zone-change) must NOT also attack the
same round. Regression for a double-advance bug: the charge path in
``resolve_attack`` advanced the turn internally while the API caller
(``post_enemy_turn``) advanced it again, returning the turn to the same enemy and
letting it attack right after charging — skipping the player's turn.

The fix removes the internal ``advance_turn`` from the charge path so it matches
the normal enemy-attack path (caller is solely responsible for advancing).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.services import combat_service as cs


def _schema_sql() -> str:
    player_sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 12, "CHA": 10},
        "current_hp": 20,
        "max_hp": 20,
        "defense": {"base": 15},
        "equipped_weapon": "sword",
        "conditions": [],
    }
    psj = json.dumps(player_sheet, ensure_ascii=False).replace("'", "''")
    return f"""
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL, display_name TEXT NOT NULL
    );
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');

    CREATE TABLE campaigns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, system_id TEXT NOT NULL,
      model_id TEXT NOT NULL, owner_user_id INTEGER NOT NULL,
      language TEXT NOT NULL DEFAULT 'pl', mode TEXT NOT NULL DEFAULT 'solo',
      status TEXT NOT NULL DEFAULT 'active'
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id)
    VALUES (1,'I232','fantasy','m',1);

    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL, name TEXT NOT NULL, system_id TEXT NOT NULL,
      sheet_json TEXT NOT NULL
    );
    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
    VALUES (1,1,1,'Aldric','fantasy','{psj}');

    {table_sql("game_config_weapons")}
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes)
    VALUES ('sword','Sword','1d8','STR','warrior');

    {table_sql("game_config_enemies")}
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, drop_chance, skills_json)
    VALUES ('bandit','Bandit',12,13,3,1,'1d8',0.0,'{{}}');

    CREATE TABLE active_combat (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL UNIQUE,
      character_id INTEGER NOT NULL, round INTEGER NOT NULL DEFAULT 1,
      turn_order TEXT NOT NULL, current_turn TEXT NOT NULL, combatants TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active', ended_reason TEXT,
      location_tag TEXT DEFAULT NULL, loot_pool TEXT DEFAULT NULL,
      created_at TEXT, updated_at TEXT
    );

    CREATE TABLE combat_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER NOT NULL,
      campaign_id INTEGER NOT NULL, turn_number REAL NOT NULL, actor TEXT NOT NULL,
      event_type TEXT NOT NULL, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
      target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );
    """


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "i232.db"
    conn = sqlite3.connect(str(p))
    try:
        conn.executescript(_schema_sql())
        conn.commit()
    finally:
        conn.close()
    with patch.object(cs, "COMBAT_DB_PATH", str(p)):
        yield p


def _force_charge_setup(db: Path) -> str:
    """Put combat into the charge-triggering state: player in ranged, melee enemy in
    engaged, and it is the enemy's turn. Returns the enemy combatant id."""
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT combatants, turn_order FROM active_combat WHERE campaign_id = 1"
        ).fetchone()
        combatants = json.loads(row["combatants"] or "[]")
        enemy_id = ""
        for c in combatants:
            if c.get("type") == "player":
                c["zone"] = "engaged"  # player will be moved to ranged below
            else:
                c["zone"] = "engaged"  # melee enemy, same as player initially
                enemy_id = str(c.get("id"))
        # Player flees to ranged so the melee enemy is now out of range and must charge.
        for c in combatants:
            if c.get("type") == "player":
                c["zone"] = "ranged"
        conn.execute(
            "UPDATE active_combat SET combatants = ?, current_turn = ? WHERE campaign_id = 1",
            (json.dumps(combatants, ensure_ascii=False), enemy_id),
        )
        conn.commit()
        return enemy_id
    finally:
        conn.close()


def _current_turn(db: Path) -> str:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return str(
            conn.execute(
                "SELECT current_turn FROM active_combat WHERE campaign_id = 1"
            ).fetchone()["current_turn"]
        )
    finally:
        conn.close()


@patch("app.services.combat_service.roll_d20")
def test_charging_enemy_does_not_attack_same_round(mock_r20, db):
    mock_r20.return_value = 10
    cs.initiate_combat(1, 1, ["bandit"])
    enemy_id = _force_charge_setup(db)

    out = cs.resolve_attack(1, 0, attacker="enemy")

    # Enemy charged, did not attack
    assert out.get("zone_change", {}).get("charged") is True
    assert out["hit"] is False
    assert int(out.get("damage") or 0) == 0

    # CRITICAL: the charge path must NOT advance the turn internally. The current
    # turn must still be the enemy so the caller (post_enemy_turn) advances exactly
    # once — to the player. Before the fix it advanced here too, so the caller's
    # second advance handed the turn straight back to the same enemy.
    assert _current_turn(db) == enemy_id

    # Simulate the single caller-side advance → player's turn, not the enemy again.
    nxt = cs.advance_turn(1)
    assert nxt == "player"
