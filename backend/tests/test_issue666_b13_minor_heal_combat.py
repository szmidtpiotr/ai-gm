"""TDD: Issue #666 (B13) — minor_heal dispatch w walce (bug: wpadał w ścieżkę ataku).

Bug: spell_type='heal' nie miał dispatcha w resolve_attack → minor_heal atakował wroga
zamiast leczyć gracza. Fix: `_resolve_heal_spell_in_combat` + dispatch blok.

Testy:
  • minor_heal leczy gracza (HP wzrasta), mana spada
  • minor_heal nie atakuje wroga (HP wroga bez zmian)
  • minor_heal cap na max_hp (nie przekracza)
  • blocked gdy za mało many
  • spell_heal log event w combat_turns
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _fixtures_schema import table_sql

from app.services import combat_service


def _combat_db(tmp_path, *, player_hp=5, max_hp=8, mana=5, max_mana=9):
    db = tmp_path / "b13_heal.db"
    player = {
        "id": "player", "type": "player", "name": "Mag",
        "hp_current": player_hp, "hp_max": max_hp, "defense": 10, "zone": "ranged",
        "stats": {"STR": 8, "DEX": 10, "CON": 10, "INT": 14, "WIS": 12, "CHA": 10},
        "conditions": [],
    }
    enemy = {
        "id": "goblin", "type": "enemy", "enemy_key": "goblin", "name": "Goblin",
        "hp_current": 10, "hp_max": 10, "defense": 10, "attack_bonus": 0,
        "damage_dice": "1d4", "zone": "ranged", "conditions": [],
        "stats": {"STR": 8, "DEX": 10, "CON": 8, "INT": 7, "WIS": 8, "CHA": 8},
    }
    sheet = {
        "archetype": "scholar", "level": 1,
        "stats": player["stats"], "current_hp": player_hp, "max_hp": max_hp,
        "current_mana": mana, "max_mana": max_mana, "conditions": [], "skills": {},
    }
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'B13');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Mag','fantasy','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, boss_defeated INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'["player","goblin"]','player','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER,
          campaign_id INTEGER, turn_number REAL, actor TEXT, event_type TEXT,
          roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        """ + table_sql("game_config_conditions") + """
        CREATE TABLE character_spells (character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1,
          learned_at_level INTEGER DEFAULT 1, use_count INTEGER DEFAULT 0);
        """ + table_sql("game_config_spells") + """
        INSERT INTO game_config_spells
          (key,label,spell_type,effect_type,mana_cost,tier,damage_die,heal_die,is_active) VALUES
          ('minor_heal','Leczniczy Dotyk','heal',NULL,1,1,NULL,'1d6',1),
          ('fire_bolt','Ognisty Pocisk','attack',NULL,2,1,'1d8',NULL,1);
        """ + table_sql("game_config_enemies") + """
        INSERT INTO game_config_enemies
          (key,label,hp_base,ac_base,attack_bonus,damage_die,dex_modifier,tier,xp_award)
          VALUES ('goblin','Goblin',10,10,0,'1d4',0,'minion',10);
        """)
        conn.execute(
            "INSERT INTO character_spells (character_id, spell_key, rank) "
            "SELECT c.id, s.key, 1 FROM characters c, game_config_spells s"
        )  # #1431: bramka wymaga znanego czaru — seeduj czary jako znane
        conn.commit()
    finally:
        conn.close()
    return db


def _player_hp(db):
    conn = sqlite3.connect(str(db))
    try:
        sj = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()[0]
        return int(json.loads(sj).get("current_hp", 0))
    finally:
        conn.close()


def _enemy_hp(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        for c in json.loads(row[0]):
            if c.get("type") == "enemy":
                return c.get("hp_current")
    finally:
        conn.close()


def _mana(db):
    conn = sqlite3.connect(str(db))
    try:
        sj = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()[0]
        return int(json.loads(sj).get("current_mana", 0))
    finally:
        conn.close()


def _last_event_type(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT event_type FROM combat_turns ORDER BY turn_number DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _player_combatant_hp(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        for c in json.loads(row[0]):
            if c.get("type") == "player":
                return c.get("hp_current")
    finally:
        conn.close()


# ── Testy core ────────────────────────────────────────────────────────────────

def test_minor_heal_in_combat_heals_player(tmp_path):
    """minor_heal w walce → spell_type='heal', HP gracza rośnie, mana spada."""
    db = _combat_db(tmp_path, player_hp=4, max_hp=8, mana=3)
    hp_before = _player_hp(db)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", spell_key="minor_heal")
    assert out.get("spell_type") == "heal", f"Oczekiwano heal, dostano {out.get('spell_type')}"
    assert out.get("hit") is True
    assert out.get("healed", 0) > 0, "Powinno coś wyleczyć"
    assert _player_hp(db) > hp_before, "HP gracza powinno wzrosnąć"
    assert _mana(db) == 2, f"Mana 3→2 (koszt 1), jest {_mana(db)}"


def test_minor_heal_does_not_attack_enemy(tmp_path):
    """Regresja: minor_heal nie trafia wroga — HP wroga bez zmian."""
    db = _combat_db(tmp_path, player_hp=4, max_hp=8, mana=3)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", spell_key="minor_heal")
    assert int(out.get("damage") or 0) == 0, "minor_heal nie powinno zadać obrażeń wrogowi"
    assert _enemy_hp(db) == 10, "HP wroga powinno być bez zmian"


def test_minor_heal_capped_at_max_hp(tmp_path):
    """Heal nie przekracza max_hp (full-HP gracz → hp_after == max_hp)."""
    db = _combat_db(tmp_path, player_hp=8, max_hp=8, mana=3)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", spell_key="minor_heal")
    assert _player_hp(db) == 8, "HP nie może przekroczyć max"
    assert _player_combatant_hp(db) == 8


def test_minor_heal_insufficient_mana_blocked(tmp_path):
    """Za mało many (0) → blocked, HP bez zmian."""
    db = _combat_db(tmp_path, player_hp=4, max_hp=8, mana=0)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", spell_key="minor_heal")
    assert out.get("blocked") is True, "Powinno być zablokowane przy mana=0"
    assert _player_hp(db) == 4, "HP bez zmian przy braku many"


def test_minor_heal_logs_spell_heal_event(tmp_path):
    """spell_heal event zalogowany w combat_turns."""
    db = _combat_db(tmp_path, player_hp=4, max_hp=8, mana=3)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_attack(1, None, attacker="player", spell_key="minor_heal")
    assert _last_event_type(db) == "spell_heal", "Oczekiwano spell_heal event w combat_turns"


def test_minor_heal_updates_combatant_hp(tmp_path):
    """hp_current combatanta gracza aktualizuje się po healowaniu."""
    db = _combat_db(tmp_path, player_hp=3, max_hp=8, mana=3)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", spell_key="minor_heal")
    assert _player_combatant_hp(db) > 3, "hp_current combatanta powinno wzrosnąć"
    assert _player_combatant_hp(db) == out.get("hp_after")
