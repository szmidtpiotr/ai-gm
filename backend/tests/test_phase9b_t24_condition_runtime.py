"""T24 - runtime turn handling for condition effect_json in combat."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import combat_service as cs


def _schema_sql(player_conditions: list[dict] | None = None) -> str:
    player_sheet = {
        "stats": {
            "STR": 14,
            "DEX": 12,
            "CON": 12,
            "INT": 10,
            "WIS": 18,
            "CHA": 10,
        },
        "current_hp": 20,
        "max_hp": 20,
        "defense": {"base": 15},
        "equipped_weapon": "sword",
        "conditions": player_conditions or [],
    }
    player_sheet_json = json.dumps(player_sheet, ensure_ascii=False).replace("'", "''")

    return f"""
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      display_name TEXT NOT NULL
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
      status TEXT NOT NULL DEFAULT 'active'
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id)
    VALUES (1, 'T24', 'fantasy', 'm', 1);

    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      system_id TEXT NOT NULL,
      sheet_json TEXT NOT NULL
    );
    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
    VALUES (1, 1, 1, 'Aldric', 'fantasy', '{player_sheet_json}');

    CREATE TABLE game_config_weapons (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      damage_die TEXT NOT NULL,
      linked_stat TEXT NOT NULL,
      allowed_classes TEXT NOT NULL DEFAULT 'warrior',
      is_active INTEGER NOT NULL DEFAULT 1
    );
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes)
    VALUES ('sword', 'Sword', '1d8', 'STR', 'warrior');

    CREATE TABLE game_config_enemies (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      hp_base INTEGER NOT NULL,
      ac_base INTEGER NOT NULL,
      attack_bonus INTEGER NOT NULL,
      dex_modifier INTEGER NOT NULL DEFAULT 0,
      damage_die TEXT NOT NULL,
      tier TEXT DEFAULT 'standard',
      xp_award INTEGER NOT NULL DEFAULT 0,
      description TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      loot_table_key TEXT,
      drop_chance REAL NOT NULL DEFAULT 0.0,
      skills_json TEXT,
      attacks_per_turn INTEGER NOT NULL DEFAULT 1,
      stats_json TEXT,
      image_url TEXT
    );
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, drop_chance, skills_json)
    VALUES ('bandit', 'Bandit', 12, 13, 3, 1, '1d8', 0.0, '{{}}');

    CREATE TABLE active_combat (
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
      created_at TEXT,
      updated_at TEXT
    );

    CREATE TABLE combat_turns (
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
    """


def _fear_condition(*, dc_key: str = "easy") -> dict:
    effect_json = {
        "schema_version": 1,
        "effect_category": "character_condition",
        "effects": [
            {
                "type": "periodic_save",
                "dc_key": dc_key,
                "stat": "WIS",
                "tick": "start_turn",
                "expires": "save_success",
            },
            {"type": "block_action"},
        ],
    }
    return {
        "key": "fear",
        "label": "Fear",
        "effect_json": json.dumps(effect_json, ensure_ascii=False),
        "source_item_key": "fear_powder",
        "applied_at": "test",
    }


@pytest.fixture
def t24_db(tmp_path):
    db = tmp_path / "t24_condition_runtime.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(_schema_sql(player_conditions=[_fear_condition()]))
        conn.commit()
    finally:
        conn.close()
    with patch.object(cs, "COMBAT_DB_PATH", str(db)):
        yield db


def _fetch_sheet(db: Path) -> dict:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = 1").fetchone()
        return json.loads(row["sheet_json"] or "{}")
    finally:
        conn.close()


def _set_enemy_condition(db: Path, condition: dict) -> None:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT combatants, current_turn FROM active_combat WHERE campaign_id = 1").fetchone()
        combatants = json.loads(row["combatants"] or "[]")
        for combatant in combatants:
            if isinstance(combatant, dict) and str(combatant.get("id") or "") == str(row["current_turn"] or ""):
                combatant["conditions"] = [condition]
        conn.execute(
            "UPDATE active_combat SET combatants = ? WHERE campaign_id = 1",
            (json.dumps(combatants, ensure_ascii=False),),
        )
        conn.commit()
    finally:
        conn.close()


@patch("app.services.combat_service.roll_d20")
def test_periodic_save_success_removes_condition_before_block(mock_r20, t24_db):
    mock_r20.side_effect = [18, 10, 8]
    cs.initiate_combat(1, 1, ["bandit"])

    out = cs.evaluate_current_turn_conditions(1)
    assert out["blocked"] is False
    assert any(evt["type"] == "periodic_save" and evt["success"] for evt in out["events"])
    assert any(evt["type"] == "condition_removed" for evt in out["events"])

    snap = cs.get_active_combat(1)
    player = next(c for c in snap["combatants"] if c["id"] == "player")
    assert player.get("conditions") == []

    sheet = _fetch_sheet(t24_db)
    assert sheet.get("conditions") == []


@patch("app.services.combat_service.roll_d20")
def test_player_attack_is_blocked_when_periodic_save_fails(mock_r20, t24_db):
    mock_r20.side_effect = [18, 10, 2]
    cs.initiate_combat(1, 1, ["bandit"])

    out = cs.resolve_attack(1, 14, attacker="player", raw_d20=12)
    assert out["blocked"] is True
    assert out["hit"] is False
    assert "nie możesz wykonać akcji" in str(out["message"]).lower()

    snap = cs.get_active_combat(1)
    player = next(c for c in snap["combatants"] if c["id"] == "player")
    assert len(player.get("conditions") or []) == 1


@patch("app.services.combat_service.roll_d20")
def test_enemy_turn_can_be_blocked_without_dealing_damage(mock_r20, t24_db):
    mock_r20.side_effect = [5, 18]
    cs.initiate_combat(1, 1, ["bandit"])

    block_only = {
        "key": "stun",
        "label": "Stun",
        "effect_json": json.dumps(
            {
                "schema_version": 1,
                "effect_category": "character_condition",
                "effects": [{"type": "block_action"}],
            },
            ensure_ascii=False,
        ),
        "applied_at": "test",
    }
    _set_enemy_condition(t24_db, block_only)

    out = cs.resolve_attack(1, 0, attacker="enemy")
    assert out["blocked"] is True
    assert out["hit"] is False

    sheet = _fetch_sheet(t24_db)
    assert int(sheet.get("current_hp") or 0) == 20
