"""TDD: Issue #820 (B14) — czary na sojusznika (ally-target heal/shield + mass_*/group_*).

Soft-gate zdjęty: G7 (#791) wstawia żywych sojuszników do turn_order jako 'player:{id}'.
B14 dodaje kierowanie efektu wsparcia na WSKAZANEGO przyjaznego kombatanta (nie rzucającego)
oraz warianty grupowe (`group_*`/`mass_*`) na CAŁĄ przyjazną stronę.

Testy:
  • heal pojedynczy z target_id sojusznika → leczy SOJUSZNIKA, nie rzucającego
  • group_heal → leczy WSZYSTKICH żywych przyjaznych (rzucający + sojusznik)
  • group_heal nie leczy wroga
  • mana zdjęta DOKŁADNIE raz (nie per cel)
  • shield (defense) z target_id sojusznika → absorb na sojuszniku, nie na rzucającym
  • REGRESJA single-player: jeden przyjazny slot, brak target → self-cast jak dawniej
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


def _mp_combat_db(tmp_path, *, caster_hp=5, ally_hp=3, max_hp=10, mana=5, max_mana=9):
    """Walka MP: caster='player:1' (Kapłan), ally='player:2' (Wojownik, ranny), enemy."""
    db = tmp_path / "b14.db"
    caster = {
        "id": "player:1", "type": "player", "name": "Kaplan",
        "hp_current": caster_hp, "hp_max": max_hp, "defense": 10, "zone": "ranged",
        "stats": {"STR": 8, "DEX": 10, "CON": 10, "INT": 14, "WIS": 12, "CHA": 10},
        "conditions": [],
    }
    ally = {
        "id": "player:2", "type": "player", "name": "Wojownik",
        "hp_current": ally_hp, "hp_max": max_hp, "defense": 12, "zone": "engaged",
        "stats": {"STR": 14, "DEX": 10, "CON": 12, "INT": 8, "WIS": 10, "CHA": 10},
        "conditions": [],
    }
    enemy = {
        "id": "goblin", "type": "enemy", "enemy_key": "goblin", "name": "Goblin",
        "hp_current": 10, "hp_max": 10, "defense": 10, "attack_bonus": 0,
        "damage_dice": "1d4", "zone": "ranged", "conditions": [],
        "stats": {"STR": 8, "DEX": 10, "CON": 8, "INT": 7, "WIS": 8, "CHA": 8},
    }
    caster_sheet = {
        "archetype": "scholar", "level": 1, "stats": caster["stats"],
        "current_hp": caster_hp, "max_hp": max_hp,
        "current_mana": mana, "max_mana": max_mana, "conditions": [], "skills": {},
    }
    ally_sheet = {
        "archetype": "warrior", "level": 1, "stats": ally["stats"],
        "current_hp": ally_hp, "max_hp": max_hp,
        "current_mana": 0, "max_mana": 0, "conditions": [], "skills": {},
    }
    combatants = json.dumps([caster, ally, enemy], ensure_ascii=False).replace("'", "''")
    cs = json.dumps(caster_sheet, ensure_ascii=False).replace("'", "''")
    as_ = json.dumps(ally_sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title,mode) VALUES (1,'B14',NULL);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Kaplan','fantasy','{cs}'),
                 (2,1,2,'Wojownik','fantasy','{as_}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, boss_defeated INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'["player:1","player:2","goblin"]','player:1','{combatants}','active');
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
          (key,label,spell_type,effect_type,mana_cost,tier,damage_die,heal_die,effect_json,is_active) VALUES
          ('minor_heal','Leczniczy Dotyk','heal',NULL,1,1,NULL,'1d6',NULL,1),
          ('group_heal','Leczenie Grupowe','heal',NULL,2,3,NULL,'1d6',NULL,1),
          ('divine_shield_ally','Tarcza Bostwa','defense',NULL,2,3,NULL,NULL,'{{"absorb":6}}',1);
        """ + table_sql("game_config_enemies") + """
        INSERT INTO game_config_enemies
          (key,label,hp_base,ac_base,attack_bonus,damage_die,dex_modifier,tier,xp_award)
          VALUES ('goblin','Goblin',10,10,0,'1d4',0,'minion',10);
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def _char_hp(db, char_id):
    conn = sqlite3.connect(str(db))
    try:
        sj = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (char_id,)).fetchone()[0]
        return int(json.loads(sj).get("current_hp", 0))
    finally:
        conn.close()


def _combatant(db, cid):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        for c in json.loads(row[0]):
            if str(c.get("id")) == cid:
                return c
    finally:
        conn.close()


def _mana(db, char_id=1):
    conn = sqlite3.connect(str(db))
    try:
        sj = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (char_id,)).fetchone()[0]
        return int(json.loads(sj).get("current_mana", 0))
    finally:
        conn.close()


# ─── Test główny: heal na sojusznika ──────────────────────────────────────────

def test_ally_heal_targets_chosen_ally_not_caster(tmp_path):
    """minor_heal z target_id='player:2' → leczy SOJUSZNIKA, rzucający bez zmian."""
    db = _mp_combat_db(tmp_path, caster_hp=5, ally_hp=3)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(
            1, None, attacker="player:1", spell_key="minor_heal", target_id="player:2",
        )
    assert out.get("spell_type") == "heal"
    assert out.get("hit") is True
    assert _char_hp(db, 2) > 3, "Sojusznik (char 2) powinien zostać wyleczony"
    assert _char_hp(db, 1) == 5, "Rzucający (char 1) HP bez zmian — leczył kogoś innego"
    assert _combatant(db, "player:2")["hp_current"] > 3
    assert _combatant(db, "player:1")["hp_current"] == 5


def test_group_heal_covers_all_friendly_alive(tmp_path):
    """group_heal → leczy WSZYSTKICH żywych przyjaznych (rzucający + sojusznik)."""
    db = _mp_combat_db(tmp_path, caster_hp=4, ally_hp=3, mana=5)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(
            1, None, attacker="player:1", spell_key="group_heal",
        )
    assert out.get("hit") is True
    assert _char_hp(db, 1) > 4, "Rzucający powinien być wyleczony przez heal grupowy"
    assert _char_hp(db, 2) > 3, "Sojusznik powinien być wyleczony przez heal grupowy"
    targets = out.get("heal_targets") or []
    healed_ids = {t.get("target_id") for t in targets}
    assert "player:1" in healed_ids and "player:2" in healed_ids


def test_group_heal_does_not_heal_enemy(tmp_path):
    """group_heal nie dotyka wroga — HP goblina bez zmian."""
    db = _mp_combat_db(tmp_path, caster_hp=4, ally_hp=3)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_attack(1, None, attacker="player:1", spell_key="group_heal")
    assert _combatant(db, "goblin")["hp_current"] == 10, "Wróg nie może być celem heala grupowego"


def test_ally_heal_deducts_mana_once(tmp_path):
    """Mana zdjęta dokładnie raz (koszt czaru), niezależnie od liczby celów."""
    db = _mp_combat_db(tmp_path, mana=5)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_attack(1, None, attacker="player:1", spell_key="group_heal")
    assert _mana(db, 1) == 3, f"Mana 5→3 (koszt 2 raz), jest {_mana(db,1)}"


def test_shield_ally_grants_absorb_on_ally(tmp_path):
    """divine_shield_ally z target_id='player:2' → absorb na sojuszniku, nie na rzucającym."""
    db = _mp_combat_db(tmp_path, mana=5)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(
            1, None, attacker="player:1", spell_key="divine_shield_ally", target_id="player:2",
        )
    assert out.get("spell_type") == "defense"
    assert out.get("hit") is True
    assert int(_combatant(db, "player:2").get("absorb_hp") or 0) == 6, "Sojusznik dostaje absorb 6"
    assert int(_combatant(db, "player:1").get("absorb_hp") or 0) == 0, "Rzucający bez absorbu"


# ─── Regresja: single-player self-cast ────────────────────────────────────────

def _solo_combat_db(tmp_path, *, player_hp=4, max_hp=10, mana=5):
    """Jeden przyjazny slot 'player' (solo) — self-cast jak w B13."""
    db = tmp_path / "b14_solo.db"
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
        "archetype": "scholar", "level": 1, "stats": player["stats"],
        "current_hp": player_hp, "max_hp": max_hp,
        "current_mana": mana, "max_mana": 9, "conditions": [], "skills": {},
    }
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title,mode) VALUES (1,'B14solo',NULL);
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
          ('minor_heal','Leczniczy Dotyk','heal',NULL,1,1,NULL,'1d6',1);
        """ + table_sql("game_config_enemies") + """
        INSERT INTO game_config_enemies
          (key,label,hp_base,ac_base,attack_bonus,damage_die,dex_modifier,tier,xp_award)
          VALUES ('goblin','Goblin',10,10,0,'1d4',0,'minion',10);
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def test_single_player_self_cast_unchanged(tmp_path):
    """REGRESJA: solo, jeden 'player', brak target → self-heal jak w B13."""
    db = _solo_combat_db(tmp_path, player_hp=4, max_hp=10, mana=5)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", spell_key="minor_heal")
    assert out.get("spell_type") == "heal"
    assert out.get("hit") is True
    assert _char_hp(db, 1) > 4, "Solo gracz powinien wyleczyć SIEBIE"
    assert _combatant(db, "player")["hp_current"] > 4
    assert _mana(db, 1) == 4, "Mana 5→4 (koszt 1)"
