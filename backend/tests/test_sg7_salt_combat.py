"""SG-7 (#1481) — sól w PRAWDZIWEJ walce (nie tylko w prymitywach salt_service).

Dwa dowody na żywym silniku walki, oba z nieumarłym po drugiej stronie:
  1. Solona klinga faktycznie dokłada obrażenia cięciu w istotę Rdzenia — i NIE
     dokłada ich żywemu bandycie.
  2. Krąg soli zatrzymuje doskok nieumarłego do zwarcia — a żywy wróg doskakuje
     mimo soli.

Wzorzec fikstury: test_issue1465_combat_conditions.py (patch COMBAT_DB_PATH + initiate_combat).
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

SALT_BLADE_EJ = {
    "schema_version": 1,
    "effect_category": "character_condition",
    "clear_on": "combat_end",
    "effects": [{"type": "salt_edge", "bonus_dice": "1d4"}],
}
SALT_CIRCLE_EJ = {
    "schema_version": 1,
    "effect_category": "character_condition",
    "clear_on": "combat_end",
    "on_apply": "push_core_beings",
    "effects": [{"type": "salt_ward", "expires": "duration_rounds:3"}],
}


def _schema_sql() -> str:
    sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
        "current_hp": 40, "max_hp": 40, "defense": {"base": 12},
        "equipped_weapon": "sword", "conditions": [], "level": 3,
    }
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'SG7','fantasy','m',1);
    CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
      name TEXT, system_id TEXT, sheet_json TEXT);
    INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
      VALUES (1,1,1,'Brunhilda','fantasy','{sj}');
    {table_sql("game_config_weapons")}
    INSERT INTO game_config_weapons (key,label,damage_die,linked_stat,allowed_classes)
      VALUES ('sword','Miecz','1d8','STR','warrior');
    {table_sql("game_config_enemies")}
    ALTER TABLE game_config_enemies ADD COLUMN creature_type TEXT;
    INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,dex_modifier,damage_die,drop_chance,skills_json)
      VALUES ('widmo_lodowe','Widmo Lodowe',60,10,3,0,'1d6',0.0,'{{}}');
    INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,dex_modifier,damage_die,drop_chance,skills_json)
      VALUES ('troll_gorski','Troll Górski',60,10,3,0,'1d6',0.0,'{{}}');
    UPDATE game_config_enemies SET creature_type='undead' WHERE key='widmo_lodowe';
    {table_sql("game_config_conditions")}
    CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
      character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
      combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
      loot_pool TEXT, created_at TEXT, updated_at TEXT);
    CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
      turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
      target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
      created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
    """


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "sg7.db"
    conn = sqlite3.connect(str(p))
    try:
        conn.executescript(_schema_sql())
        conn.commit()
    finally:
        conn.close()
    cs.salt_service._CREATURE_TYPE_CACHE.clear()
    with patch.object(cs, "COMBAT_DB_PATH", str(p)):
        yield p


def _patch_combat(db_path: Path, *, player_condition: dict | None = None,
                  player_zone: str | None = None, enemy_zone: str | None = None,
                  current_turn: str | None = None) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row["combatants"] or "[]")
        for c in combatants:
            if c.get("id") == "player":
                if player_condition is not None:
                    c["conditions"] = [player_condition]
                if player_zone:
                    c["zone"] = player_zone
            elif enemy_zone:
                c["zone"] = enemy_zone
        sql = "UPDATE active_combat SET combatants=?"
        args: list = [json.dumps(combatants, ensure_ascii=False)]
        if current_turn:
            sql += ", current_turn=?"
            args.append(current_turn)
        sql += " WHERE campaign_id=1"
        conn.execute(sql, args)
        conn.commit()
    finally:
        conn.close()


def _condition(key: str, effect_json: dict) -> dict:
    return {"key": key, "label": key, "applied_at": "test",
            "effect_json": json.dumps(effect_json, ensure_ascii=False), "runtime": {}}


def _enemy_id(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        combatants = json.loads(
            conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()[0]
        )
        return next(c["id"] for c in combatants if c.get("id") != "player")
    finally:
        conn.close()


# ─── 1. Solona klinga w cięciu ────────────────────────────────────────────────

@patch("app.services.combat_service.roll_d20", return_value=12)
def test_salted_blade_adds_damage_against_undead(_r20, db):
    cs.initiate_combat(1, 1, ["widmo_lodowe"])
    _patch_combat(db, player_condition=_condition("salted_blade", SALT_BLADE_EJ),
                  player_zone="engaged", enemy_zone="engaged")
    out = cs.resolve_attack(1, 18, attacker="player", raw_d20=12, target_id=_enemy_id(db))
    assert out.get("hit") is True, out
    assert 1 <= int(out.get("salt_blade_bonus") or 0) <= 4, out


@patch("app.services.combat_service.roll_d20", return_value=12)
def test_salted_blade_does_nothing_against_a_living_enemy(_r20, db):
    cs.initiate_combat(1, 1, ["troll_gorski"])
    _patch_combat(db, player_condition=_condition("salted_blade", SALT_BLADE_EJ),
                  player_zone="engaged", enemy_zone="engaged")
    out = cs.resolve_attack(1, 18, attacker="player", raw_d20=12, target_id=_enemy_id(db))
    assert out.get("hit") is True, out
    assert "salt_blade_bonus" not in out, out


@patch("app.services.combat_service.roll_d20", return_value=12)
def test_no_salt_no_bonus(_r20, db):
    cs.initiate_combat(1, 1, ["widmo_lodowe"])
    _patch_combat(db, player_zone="engaged", enemy_zone="engaged")
    out = cs.resolve_attack(1, 18, attacker="player", raw_d20=12, target_id=_enemy_id(db))
    assert "salt_blade_bonus" not in out, out


# ─── 2. Krąg soli w turze wroga ───────────────────────────────────────────────

@patch("app.services.combat_service.roll_d20", return_value=12)
def test_salt_circle_stops_undead_from_closing_in(_r20, db):
    cs.initiate_combat(1, 1, ["widmo_lodowe"])
    eid = _enemy_id(db)
    _patch_combat(db, player_condition=_condition("salt_circle", SALT_CIRCLE_EJ),
                  player_zone="engaged", enemy_zone="ranged", current_turn=eid)
    out = cs.resolve_attack(1, None, attacker="enemy")
    assert out.get("salt_circle_block"), out
    assert out.get("zone_change") is None, out
    assert out.get("damage") in (0, None), out

    conn = sqlite3.connect(str(db))
    try:
        combatants = json.loads(
            conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()[0]
        )
    finally:
        conn.close()
    zones = {c["id"]: c.get("zone") for c in combatants}
    assert zones[eid] == "ranged", zones


@patch("app.services.combat_service.roll_d20", return_value=12)
def test_living_enemy_charges_through_salt(_r20, db):
    cs.initiate_combat(1, 1, ["troll_gorski"])
    eid = _enemy_id(db)
    _patch_combat(db, player_condition=_condition("salt_circle", SALT_CIRCLE_EJ),
                  player_zone="engaged", enemy_zone="ranged", current_turn=eid)
    out = cs.resolve_attack(1, None, attacker="enemy")
    assert out.get("salt_circle_block") is None, out
    assert out.get("zone_change", {}).get("charged") is True, out


@patch("app.services.combat_service.roll_d20", return_value=12)
def test_undead_charges_when_there_is_no_circle(_r20, db):
    cs.initiate_combat(1, 1, ["widmo_lodowe"])
    eid = _enemy_id(db)
    _patch_combat(db, player_zone="engaged", enemy_zone="ranged", current_turn=eid)
    out = cs.resolve_attack(1, None, attacker="enemy")
    assert out.get("salt_circle_block") is None, out
    assert out.get("zone_change", {}).get("charged") is True, out
