"""TDD: Issue #821 (B15) — Summony jako kombatant-towarzysz.

Decyzja projektowa (#821, 2026-06-21, zatwierdzona przez Piotra):
  • tura summona = AUTO-ATAK najbliższego żywego wroga (preferuj tę samą strefę);
  • limit = 1 aktywny summon — nowy rzut ZASTĘPUJE poprzedniego;
  • czas życia = `lifetime_rounds` z `effect_json` (default 3) + znika po śmierci (hp<=0);
  • gdy gracz pada (hp<=0) → summon znika; `shadow_clone` używa STAŁEGO profilu z effect_json
    (NIE kopiuje statów/ekwipunku gracza — osobny backlog).

Testy:
  • rzucenie czaru summon dodaje kombatanta type=='summon' do combatants I do turn_order
  • summon atakuje WROGA we własnej turze (nie gracza), zadaje obrażenia
  • summon znika po wygaśnięciu lifetime
  • 1 aktywny summon — drugi rzut zastępuje pierwszego
  • _all_enemies_dead nadal kończy walkę gdy żyje tylko summon, a wrogowie padli
  • summon znika, gdy gracz pada (owner_down)
  • REGRESJA: walka bez summonów — advance_turn działa jak dawniej
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


def _solo_combat_db(
    tmp_path, *, player_hp=10, enemy_hp=20, mana=9,
    summon_lifetime=3, summon_hp=8, with_summon_in_combat=False,
    summon_lifetime_remaining=3, enemy_dead=False,
):
    """Walka solo: scholar 'player' + 'goblin'. Opcjonalnie wstawiony summon."""
    db = tmp_path / "b15.db"
    player = {
        "id": "player", "type": "player", "name": "Mag",
        "hp_current": player_hp, "hp_max": 10, "defense": 10, "zone": "ranged",
        "stats": {"STR": 8, "DEX": 10, "CON": 10, "INT": 14, "WIS": 12, "CHA": 10},
        "conditions": [],
    }
    enemy = {
        "id": "goblin", "type": "enemy", "enemy_key": "goblin", "name": "Goblin",
        "hp_current": 0 if enemy_dead else enemy_hp, "hp_max": enemy_hp,
        "defense": 10, "attack_bonus": 0, "damage_dice": "1d4", "zone": "engaged",
        "conditions": [], "stats": {"STR": 8, "DEX": 10, "CON": 8, "INT": 7, "WIS": 8, "CHA": 8},
    }
    combatant_list = [player, enemy]
    order = ["player", "goblin"]
    if with_summon_in_combat:
        summon = {
            "id": "summon:1", "type": "summon", "owner_id": "player",
            "summon_key": "summon_familiar", "name": "Chowaniec",
            "hp_current": summon_hp, "hp_max": summon_hp, "defense": 10,
            "attack_bonus": 2, "damage_dice": "1d6", "damage_stat": "STR",
            "lifetime_remaining": summon_lifetime_remaining, "zone": "engaged",
            "conditions": [], "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        }
        combatant_list = [player, summon, enemy]
        order = ["player", "summon:1", "goblin"]
    sheet = {
        "archetype": "scholar", "level": 1, "stats": player["stats"],
        "current_hp": player_hp, "max_hp": 10,
        "current_mana": mana, "max_mana": 9, "conditions": [], "skills": {},
    }
    combatants = json.dumps(combatant_list, ensure_ascii=False).replace("'", "''")
    order_s = json.dumps(order, ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    fam_eff = json.dumps(
        {"hp": summon_hp, "attack_bonus": 2, "damage_die": "1d6",
         "lifetime_rounds": summon_lifetime, "zone": "engaged"},
        ensure_ascii=False,
    ).replace("'", "''")
    ele_eff = json.dumps(
        {"hp": 14, "attack_bonus": 3, "damage_die": "1d8", "lifetime_rounds": 4, "zone": "engaged"},
        ensure_ascii=False,
    ).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title,mode) VALUES (1,'B15',NULL);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Mag','fantasy','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, boss_defeated INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'{order_s}','player','{combatants}','active');
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
          (key,label,spell_type,mana_cost,tier,effect_json,is_active) VALUES
          ('summon_familiar','Przywołaj Chowańca','summon',2,2,'{fam_eff}',1),
          ('summon_elemental','Przywołaj Żywiołaka','summon',4,3,'{ele_eff}',1);
        """ + table_sql("game_config_enemies") + """
        INSERT INTO game_config_enemies
          (key,label,hp_base,ac_base,attack_bonus,damage_die,dex_modifier,tier,xp_award)
          VALUES ('goblin','Goblin',20,10,0,'1d4',0,'minion',10);
        """)
        conn.execute(
            "INSERT INTO character_spells (character_id, spell_key, rank) "
            "SELECT c.id, s.key, 1 FROM characters c, game_config_spells s"
        )  # #1431: bramka wymaga znanego czaru — seeduj czary jako znane
        conn.commit()
    finally:
        conn.close()
    return db


def _combatants(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        return json.loads(row[0])
    finally:
        conn.close()


def _turn_order(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT turn_order FROM active_combat WHERE campaign_id=1").fetchone()
        return json.loads(row[0])
    finally:
        conn.close()


def _combatant(db, cid):
    for c in _combatants(db):
        if str(c.get("id")) == cid:
            return c
    return None


def _mana(db, char_id=1):
    conn = sqlite3.connect(str(db))
    try:
        sj = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (char_id,)).fetchone()[0]
        return int(json.loads(sj).get("current_mana", 0))
    finally:
        conn.close()


def _set_current_turn(db, tid):
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("UPDATE active_combat SET current_turn=? WHERE campaign_id=1", (tid,))
        conn.commit()
    finally:
        conn.close()


# ─── Test główny: rzucenie summona dodaje kombatanta ──────────────────────────

def test_summon_spell_adds_summon_combatant_to_turn_order(tmp_path):
    """Rzut czaru summon → combatant type=='summon' w combatants I w turn_order, mana zdjęta."""
    db = _solo_combat_db(tmp_path, mana=9)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(
            1, None, attacker="player", spell_key="summon_familiar",
        )
    assert out.get("spell_type") == "summon"
    assert out.get("hit") is True
    summons = [c for c in _combatants(db) if c.get("type") == "summon"]
    assert len(summons) == 1, "Powinien powstać dokładnie jeden summon"
    sid = str(summons[0]["id"])
    assert sid in _turn_order(db), "Summon musi trafić do turn_order"
    assert int(summons[0]["hp_current"]) == 8, "HP summona z effect_json"
    assert int(summons[0]["lifetime_remaining"]) == 3, "lifetime z effect_json"
    assert _mana(db, 1) == 7, "Mana 9→7 (koszt 2)"


def test_summon_attacks_enemy_on_its_turn(tmp_path):
    """W turze summona atakuje WROGA (nie gracza) i zadaje obrażenia."""
    db = _solo_combat_db(tmp_path, enemy_hp=20, with_summon_in_combat=True)
    _set_current_turn(db, "summon:1")
    enemy_hp_before = _combatant(db, "goblin")["hp_current"]
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", return_value=20):
        out = combat_service.resolve_summon_turn(1)
    assert out.get("hit") is True
    assert str(out.get("target_id")) == "goblin", "Summon celuje we wroga, nie w gracza"
    assert int(out.get("damage", 0)) >= 1
    assert _combatant(db, "goblin")["hp_current"] < enemy_hp_before, "Wróg traci HP"
    assert _combatant(db, "player")["hp_current"] == 10, "Gracz nietknięty"


def test_summon_vanishes_after_lifetime(tmp_path):
    """Summon z lifetime_remaining=1 atakuje raz, potem znika w kolejnej turze."""
    db = _solo_combat_db(
        tmp_path, enemy_hp=99, with_summon_in_combat=True, summon_lifetime_remaining=1,
    )
    _set_current_turn(db, "summon:1")
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", return_value=20):
        out1 = combat_service.resolve_summon_turn(1)
        assert out1.get("hit") is True
        assert int(out1.get("lifetime_remaining")) == 0
        _set_current_turn(db, "summon:1")
        out2 = combat_service.resolve_summon_turn(1)
    assert out2.get("vanished") is True
    assert _combatant(db, "summon:1") is None, "Summon znika z combatants po wygaśnięciu"
    assert "summon:1" not in _turn_order(db), "Summon znika z turn_order"


def test_one_active_summon_replaces_previous(tmp_path):
    """Drugi rzut summona ZASTĘPUJE pierwszego (limit 1 aktywny)."""
    db = _solo_combat_db(tmp_path, mana=9)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_attack(1, None, attacker="player", spell_key="summon_familiar")
        combat_service.resolve_attack(1, None, attacker="player", spell_key="summon_elemental")
    summons = [c for c in _combatants(db) if c.get("type") == "summon"]
    assert len(summons) == 1, "Tylko jeden aktywny summon naraz"
    assert summons[0]["summon_key"] == "summon_elemental", "Nowy summon zastąpił starego"
    assert _turn_order(db).count("summon:1") == 1, "Brak duplikatów w turn_order"


def test_all_enemies_dead_ends_combat_with_summon_alive(tmp_path):
    """Gdy wrogowie padli, a żyje gracz + summon → advance_turn kończy walkę zwycięstwem."""
    db = _solo_combat_db(tmp_path, with_summon_in_combat=True, enemy_dead=True)
    _set_current_turn(db, "player")
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        result = combat_service.advance_turn(1)
    assert result == "ended", "Walka kończy się mimo żywego summona"


def test_summon_vanishes_when_player_down(tmp_path):
    """Gdy gracz pada (hp<=0), summon znika w swojej turze (owner_down)."""
    db = _solo_combat_db(tmp_path, player_hp=0, with_summon_in_combat=True)
    _set_current_turn(db, "summon:1")
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_summon_turn(1)
    assert out.get("vanished") is True
    assert out.get("vanish_reason") == "owner_down"
    assert _combatant(db, "summon:1") is None


# ─── Regresja: walka bez summonów ─────────────────────────────────────────────

def test_no_summon_regression_advance_turn(tmp_path):
    """REGRESJA: walka bez summona — advance_turn przechodzi player→goblin jak dawniej."""
    db = _solo_combat_db(tmp_path)
    _set_current_turn(db, "player")
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        nxt = combat_service.advance_turn(1)
    assert nxt == "goblin", "Bez summona kolejka działa bez zmian"
    assert all(c.get("type") != "summon" for c in _combatants(db))
