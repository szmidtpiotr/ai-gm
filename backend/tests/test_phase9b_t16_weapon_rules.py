"""T16 — weapon_type ↔ attack, finesse and two-handed runtime rules."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import combat_service as cs
from app.services.weapon_rules import (
    effective_damage_stat_for_weapon,
    resolve_attack_roll_for_weapon,
    resolve_sheet_weapon,
    weapon_key_from_inventory,
)


def _weapon_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE game_config_weapons (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            damage_die TEXT NOT NULL,
            linked_stat TEXT NOT NULL,
            weapon_type TEXT NOT NULL DEFAULT 'melee',
            two_handed INTEGER NOT NULL DEFAULT 0,
            finesse INTEGER NOT NULL DEFAULT 0,
            range_m REAL
        );
        INSERT INTO game_config_weapons
            (key, label, damage_die, linked_stat, weapon_type, two_handed, finesse, range_m)
        VALUES
            ('shortbow', 'Shortbow', '1d6', 'DEX', 'ranged', 0, 0, 90),
            ('rapier', 'Rapier', '1d8', 'STR', 'melee', 0, 1, NULL),
            ('greatsword', 'Greatsword', '2d6', 'STR', 'melee', 1, 0, NULL);
        """
    )
    return conn


def test_ranged_weapon_maps_to_ranged_attack_and_dex():
    conn = _weapon_db()
    sheet = {
        "equipped_weapon": "shortbow",
        "stats": {"STR": 10, "DEX": 16, "INT": 10},
        "skills": {"ranged_attack": 2},
    }
    weapon = resolve_sheet_weapon(conn, sheet)
    roll = resolve_attack_roll_for_weapon(sheet, raw_roll=11, weapon_row=weapon)
    conn.close()

    assert roll["test"] == "ranged_attack"
    assert roll["attack_stat"] == "DEX"
    assert roll["stat_mod"] == 3
    assert roll["modifier"] == 5  # DEX +3, skill +2, no proficiency yet
    assert roll["total"] == 16


def test_finesse_weapon_uses_better_of_str_and_dex():
    conn = _weapon_db()
    sheet = {
        "equipped_weapon": "rapier",
        "stats": {"STR": 12, "DEX": 18, "INT": 10},
        "skills": {"melee_attack": 1},
    }
    weapon = resolve_sheet_weapon(conn, sheet)
    roll = resolve_attack_roll_for_weapon(sheet, raw_roll=10, weapon_row=weapon)
    dmg_stat = effective_damage_stat_for_weapon(sheet, weapon)
    conn.close()

    assert roll["test"] == "melee_attack"
    assert roll["attack_stat"] == "DEX"
    assert roll["modifier"] == 5  # DEX +4, melee skill +1
    assert roll["total"] == 15
    assert dmg_stat == "DEX"


def test_two_handed_skill_changes_attack_modifier():
    conn = _weapon_db()
    base_sheet = {
        "equipped_weapon": "greatsword",
        "stats": {"STR": 14, "DEX": 10, "INT": 10},
        "skills": {"melee_attack": 2},
    }
    weapon = resolve_sheet_weapon(conn, base_sheet)
    no_training = resolve_attack_roll_for_weapon(base_sheet, raw_roll=10, weapon_row=weapon)
    trained_sheet = {
        **base_sheet,
        "skills": {"melee_attack": 2, "two_handed": 1},
    }
    trained = resolve_attack_roll_for_weapon(trained_sheet, raw_roll=10, weapon_row=weapon)
    conn.close()

    assert no_training["weapon_bonus"] == -2
    assert trained["weapon_bonus"] == 1
    assert trained["total"] - no_training["total"] == 3


@patch("app.services.combat_service.roll_damage_dice", return_value=7)
@patch("app.services.combat_service.roll_d20", return_value=5)
def test_combat_resolve_attack_returns_weapon_based_attack_roll(_d20, _dmg, tmp_path):
    db = tmp_path / "t16_combat.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
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
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
        VALUES (
          1, 1, 1, 'Aldric', 'fantasy',
          '{"stats":{"STR":12,"DEX":16,"INT":10},"skills":{"ranged_attack":2},"current_hp":20,"max_hp":20,"defense":{"base":15},"equipped_weapon":"shortbow"}'
        );
        CREATE TABLE game_config_weapons (
          key TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          damage_die TEXT NOT NULL,
          linked_stat TEXT NOT NULL,
          allowed_classes TEXT NOT NULL DEFAULT 'warrior',
          weapon_type TEXT NOT NULL DEFAULT 'melee',
          two_handed INTEGER NOT NULL DEFAULT 0,
          finesse INTEGER NOT NULL DEFAULT 0,
          range_m REAL,
          is_active INTEGER NOT NULL DEFAULT 1,
          locked_at TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO game_config_weapons
          (key, label, damage_die, linked_stat, allowed_classes, weapon_type, two_handed, finesse, range_m)
        VALUES ('shortbow', 'Shortbow', '1d6', 'DEX', 'warrior', 'ranged', 0, 0, 90);
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
          locked_at TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now')),
          loot_table_key TEXT,
          drop_chance REAL NOT NULL DEFAULT 1.0
        );
        INSERT INTO game_config_enemies
          (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, loot_table_key, drop_chance)
        VALUES ('bandit', 'Bandit', 12, 13, 3, 1, '1d8', NULL, 0.0);
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
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE combat_turns (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          combat_id INTEGER NOT NULL,
          campaign_id INTEGER NOT NULL,
          round INTEGER NOT NULL DEFAULT 1,
          turn_number REAL NOT NULL DEFAULT 1,
          actor TEXT NOT NULL,
          event_type TEXT NOT NULL,
          roll_value INTEGER,
          damage INTEGER,
          hp_after INTEGER,
          target_id TEXT,
          target_name TEXT,
          hit INTEGER,
          summary TEXT NOT NULL DEFAULT '',
          narrative TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE game_sessions (
          id TEXT PRIMARY KEY,
          campaign_id INTEGER NOT NULL,
          session_flags TEXT DEFAULT '{}',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()

    old = cs.COMBAT_DB_PATH
    cs.COMBAT_DB_PATH = str(db)
    try:
        cs.initiate_combat(1, 1, ["bandit"])
        out = cs.resolve_attack(1, None, attacker="player", raw_d20=12)
    finally:
        cs.COMBAT_DB_PATH = old

    assert out["attack_total"] == 17  # d20 12 + DEX 3 + ranged_attack 2
    assert out["attack_test"] == "ranged_attack"
    assert out["weapon_type"] == "ranged"
    assert out["attack_roll"]["attack_stat"] == "DEX"

    verify = sqlite3.connect(str(db))
    verify.row_factory = sqlite3.Row
    row = verify.execute(
        "SELECT narrative FROM combat_turns WHERE actor = 'player' AND event_type = 'attack' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    verify.close()

    meta = json.loads(row["narrative"])
    assert meta["attack_label"] == "ATAK DYSTANSOWY"
    assert meta["attack_stat"] == "DEX"


def test_weapon_key_from_inventory_main_hand():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE character_inventory (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          character_id INTEGER NOT NULL,
          item_key TEXT,
          weapon_key TEXT,
          consumable_key TEXT,
          quantity INTEGER NOT NULL DEFAULT 1,
          equipped INTEGER NOT NULL DEFAULT 0,
          slot TEXT,
          CONSTRAINT inv_xor CHECK (
            (CASE WHEN item_key IS NOT NULL THEN 1 ELSE 0 END +
             CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END +
             CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END) = 1
          )
        );
        INSERT INTO character_inventory (character_id, weapon_key, quantity, equipped, slot)
        VALUES (7, 'weapon_shortbow', 1, 1, 'main_hand');
        """
    )
    assert weapon_key_from_inventory(conn, 7) == "weapon_shortbow"
    conn.close()


@patch("app.services.combat_service.roll_damage_dice", return_value=7)
@patch("app.services.combat_service.roll_d20", return_value=5)
def test_combat_uses_inventory_main_hand_when_sheet_has_no_equipped_weapon(_d20, _dmg, tmp_path):
    """8E inventory: broń w slocie main_hand — sheet_json bez equipped_weapon (jak w UI)."""
    db = tmp_path / "t16_inv_combat.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
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
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json)
        VALUES (
          1, 1, 1, 'Aldric', 'fantasy',
          '{"stats":{"STR":12,"DEX":16,"INT":10},"skills":{"ranged_attack":2,"melee_attack":1},"current_hp":20,"max_hp":20,"defense":{"base":15}}'
        );
        CREATE TABLE character_inventory (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          character_id INTEGER NOT NULL,
          item_key TEXT,
          weapon_key TEXT,
          consumable_key TEXT,
          quantity INTEGER NOT NULL DEFAULT 1,
          equipped INTEGER NOT NULL DEFAULT 0,
          slot TEXT,
          CONSTRAINT inv_xor CHECK (
            (CASE WHEN item_key IS NOT NULL THEN 1 ELSE 0 END +
             CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END +
             CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END) = 1
          )
        );
        INSERT INTO character_inventory (character_id, weapon_key, quantity, equipped, slot)
        VALUES (1, 'shortbow', 1, 1, 'main_hand');
        CREATE TABLE game_config_weapons (
          key TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          damage_die TEXT NOT NULL,
          linked_stat TEXT NOT NULL,
          allowed_classes TEXT NOT NULL DEFAULT 'warrior',
          weapon_type TEXT NOT NULL DEFAULT 'melee',
          two_handed INTEGER NOT NULL DEFAULT 0,
          finesse INTEGER NOT NULL DEFAULT 0,
          range_m REAL,
          is_active INTEGER NOT NULL DEFAULT 1,
          locked_at TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO game_config_weapons
          (key, label, damage_die, linked_stat, allowed_classes, weapon_type, two_handed, finesse, range_m)
        VALUES
          ('club', 'Club', '1d4', 'STR', 'warrior', 'melee', 0, 0, NULL),
          ('shortbow', 'Shortbow', '1d6', 'DEX', 'warrior', 'ranged', 0, 0, 90);
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
          locked_at TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now')),
          loot_table_key TEXT,
          drop_chance REAL NOT NULL DEFAULT 1.0
        );
        INSERT INTO game_config_enemies
          (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, loot_table_key, drop_chance)
        VALUES ('bandit', 'Bandit', 12, 13, 3, 1, '1d8', NULL, 0.0);
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
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE combat_turns (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          combat_id INTEGER NOT NULL,
          campaign_id INTEGER NOT NULL,
          round INTEGER NOT NULL DEFAULT 1,
          turn_number REAL NOT NULL DEFAULT 1,
          actor TEXT NOT NULL,
          event_type TEXT NOT NULL,
          roll_value INTEGER,
          damage INTEGER,
          hp_after INTEGER,
          target_id TEXT,
          target_name TEXT,
          hit INTEGER,
          summary TEXT NOT NULL DEFAULT '',
          narrative TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE game_sessions (
          id TEXT PRIMARY KEY,
          campaign_id INTEGER NOT NULL,
          session_flags TEXT DEFAULT '{}',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()

    old = cs.COMBAT_DB_PATH
    cs.COMBAT_DB_PATH = str(db)
    try:
        cs.initiate_combat(1, 1, ["bandit"])
        out = cs.resolve_attack(1, None, attacker="player", raw_d20=12)
    finally:
        cs.COMBAT_DB_PATH = old

    assert out["attack_test"] == "ranged_attack"
    assert out["weapon_type"] == "ranged"
    assert out["attack_roll"]["attack_stat"] == "DEX"
