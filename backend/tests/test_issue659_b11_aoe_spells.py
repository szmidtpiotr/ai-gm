"""TDD: Issue #659 (B11) — AoE multi-target maga (attack_aoe).

Czary `attack_aoe` (`burning_arc`/`chain_lightning`/`fireball`) rzucone W WALCE uderzają
wielu wrogów jednym rzutem rzucania. Mechanika:
  • 1 rzut d20+INT vs unik celu głównego (jak czar atakujący #475) — wynik = hit/miss dla CAŁEGO AoE
  • aoe=1 (obszar): trafienie → ta sama kość obrażeń na WSZYSTKICH żywych wrogach
  • aoe=0 (łańcuch, np. chain_lightning "do 3"): maks 3 cele
  • mana zdjęta z góry; brak many → blocked (jak inne czary)
  • Nat 1 → miscast (pełna mana stracona, zero obrażeń)
  • każdy zabity wróg → loot + XP + death log (reuse ścieżki single-target)
  • zwycięstwo gdy wszyscy padną

Założenia (CZĘŚĆ AK.4/AK.5, Numbers Policy #659):
  • burning_arc     (T2, 4 mana, 1d6, aoe=1)
  • chain_lightning (T4, 5 mana, 2d6, aoe=0 → maks 3)
  • fireball        (T5, 6 mana, 3d6, aoe=1)
Czary single-target atak (#475), kontroli (B9), obrony (B10) nietknięte.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _fixtures_schema as fx  # noqa: E402
from app.services import combat_service


# ─── Pure helper: liczba celów AoE ────────────────────────────────────────────

def test_aoe_target_count_area_hits_all():
    """aoe=1 → wszyscy żywi wrogowie (bez limitu)."""
    living = ["a", "b", "c", "d"]
    assert combat_service._aoe_target_ids(living, aoe_flag=1) == ["a", "b", "c", "d"]


def test_aoe_target_count_chain_caps_at_three():
    """aoe=0 (łańcuch) → maks 3 cele, w kolejności living."""
    living = ["a", "b", "c", "d", "e"]
    assert combat_service._aoe_target_ids(living, aoe_flag=0) == ["a", "b", "c"]


def test_aoe_target_count_fewer_than_cap():
    """Mniej wrogów niż limit → wszyscy."""
    assert combat_service._aoe_target_ids(["a", "b"], aoe_flag=0) == ["a", "b"]


# ─── Integracja z silnikiem walki (resolve_attack, spell_type=attack_aoe) ─────

def _combat_db(tmp_path, *, mana=12, max_mana=12, n_enemies=3, enemy_hp=8):
    db = tmp_path / "b11.db"
    player = {
        "id": "player", "type": "player", "name": "Mag",
        "hp_current": 12, "hp_max": 12, "defense": 10, "zone": "ranged",
        "stats": {"STR": 8, "DEX": 10, "CON": 8, "INT": 16, "WIS": 12, "CHA": 10},
        "conditions": [],
    }
    combatants = [player]
    order = ["player"]
    for i in range(n_enemies):
        eid = f"goblin{i}"
        combatants.append({
            "id": eid, "type": "enemy", "enemy_key": "goblin", "name": f"Goblin {i}",
            "hp_current": enemy_hp, "hp_max": enemy_hp, "defense": 8, "attack_bonus": 0,
            "damage_dice": "1d6", "zone": "ranged", "conditions": [],
            "dex_modifier": 0, "xp_award": 10, "tier": "minion",
            "stats": {"STR": 10, "DEX": 8, "CON": 10, "INT": 7, "WIS": 8, "CHA": 8},
        })
        order.append(eid)
    sheet = {
        "archetype": "scholar", "level": 5,
        "stats": player["stats"], "current_hp": 12, "max_hp": 12,
        "current_mana": mana, "max_mana": max_mana, "conditions": [], "skills": {},
    }
    combatants_s = json.dumps(combatants, ensure_ascii=False).replace("'", "''")
    order_s = json.dumps(order, ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        fx.create_tables(conn, "game_config_conditions", "game_config_spells", "game_config_enemies")
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'B11');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Mag','fantasy','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, boss_defeated INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'{order_s}','player','{combatants_s}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        INSERT INTO game_config_spells (key,label,spell_type,effect_type,effect_stat,effect_duration,mana_cost,tier,damage_die,aoe,effect_json) VALUES
          ('burning_arc','Pałająca Ścieżka','attack_aoe',NULL,NULL,1,4,2,'1d6',1,NULL),
          ('chain_lightning','Łańcuch Błyskawic','attack_aoe',NULL,NULL,1,5,4,'2d6',0,NULL),
          ('fireball','Kula Ognia','attack_aoe',NULL,NULL,1,6,5,'3d6',1,NULL),
          ('fire_bolt','Ognisty Pocisk','attack',NULL,NULL,1,2,1,'1d8',0,NULL);
        CREATE TABLE character_spells (character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1,
          learned_at_level INTEGER DEFAULT 1);
        INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,damage_die,dex_modifier,skills_json,stats_json,tier,loot_table_key,drop_chance,xp_award)
          VALUES ('goblin','Goblin',8,8,0,'1d6',0,NULL,NULL,'minion',NULL,0,10);
        """)
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


def _enemies(db):
    return [c for c in _combatants(db) if c.get("type") == "enemy"]


def _mana(db):
    conn = sqlite3.connect(str(db))
    try:
        sj = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()[0]
    finally:
        conn.close()
    return int(json.loads(sj).get("current_mana"))


def test_burning_arc_hits_all_enemies(tmp_path):
    """burning_arc (aoe=1) przy 3 wrogach → każdy traci HP, mana 12→8."""
    db = _combat_db(tmp_path, mana=12, n_enemies=3, enemy_hp=20)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 1), \
         patch.object(combat_service, "roll_damage_dice", lambda *a, **k: 5):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=18,
                                            spell_key="burning_arc")
    assert out.get("spell_type") == "attack_aoe"
    hits = out.get("aoe_hits") or []
    assert len(hits) == 3
    for e in _enemies(db):
        assert int(e.get("hp_current")) < 20    # każdy oberwał
    assert _mana(db) == 8


def test_fireball_kills_all_and_ends_combat(tmp_path):
    """fireball za dużo dla 3 słabych wrogów → wszyscy giną, walka kończy się zwycięstwem."""
    db = _combat_db(tmp_path, mana=12, n_enemies=3, enemy_hp=6)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 1), \
         patch.object(combat_service, "roll_damage_dice", lambda *a, **k: 99):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=18,
                                            spell_key="fireball")
    hits = out.get("aoe_hits") or []
    assert len(hits) == 3
    assert all(int(e.get("hp_current")) <= 0 for e in _enemies(db))
    # walka zakończona zwycięstwem
    conn = sqlite3.connect(str(db))
    try:
        st = conn.execute("SELECT status, ended_reason FROM active_combat WHERE campaign_id=1").fetchone()
    finally:
        conn.close()
    assert st[0] == "ended"
    assert st[1] == "victory"


def test_chain_lightning_caps_at_three_targets(tmp_path):
    """chain_lightning (aoe=0) przy 5 wrogach → tylko 3 oberwą, 2 nietknięte."""
    db = _combat_db(tmp_path, mana=12, n_enemies=5, enemy_hp=20)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 1), \
         patch.object(combat_service, "roll_damage_dice", lambda *a, **k: 5):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=18,
                                            spell_key="chain_lightning")
    hits = out.get("aoe_hits") or []
    assert len(hits) == 3
    hurt = [e for e in _enemies(db) if int(e.get("hp_current")) < 20]
    assert len(hurt) == 3


def test_aoe_insufficient_mana_blocked(tmp_path):
    """Za mało many → blocked, żaden wróg nie oberwał."""
    db = _combat_db(tmp_path, mana=2, n_enemies=3, enemy_hp=20)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=18,
                                            spell_key="fireball")
    assert out.get("blocked") is True
    assert out.get("mana_insufficient") is True
    for e in _enemies(db):
        assert int(e.get("hp_current")) == 20


def test_aoe_nat1_miscast_no_damage(tmp_path):
    """Nat 1 → miscast: mana stracona, zero obrażeń wrogom."""
    db = _combat_db(tmp_path, mana=12, n_enemies=3, enemy_hp=20)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_damage_dice", lambda *a, **k: 5):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=1,
                                            spell_key="fireball")
    assert out.get("miscast") is not None or out.get("hit") is False
    for e in _enemies(db):
        assert int(e.get("hp_current")) == 20      # nikt nie oberwał
    assert _mana(db) == 6   # pełna mana stracona (12-6)


def test_aoe_grants_xp_on_kill(tmp_path):
    """Zabity wróg AoE → XP naliczone (reuse ścieżki single-target)."""
    db = _combat_db(tmp_path, mana=12, n_enemies=2, enemy_hp=4)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 1), \
         patch.object(combat_service, "roll_damage_dice", lambda *a, **k: 99):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=18,
                                            spell_key="fireball")
    assert int(out.get("xp_granted") or 0) > 0


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_single_target_attack_unchanged(tmp_path):
    """fire_bolt (attack, nie aoe) → NIE wchodzi w gałąź AoE, tylko 1 cel."""
    db = _combat_db(tmp_path, mana=12, n_enemies=3, enemy_hp=20)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 5), \
         patch.object(combat_service, "roll_damage_dice", lambda *a, **k: 5):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=18,
                                            spell_key="fire_bolt")
    assert out.get("spell_type") != "attack_aoe"
    assert "aoe_hits" not in out
    hurt = [e for e in _enemies(db) if int(e.get("hp_current")) < 20]
    assert len(hurt) <= 1
