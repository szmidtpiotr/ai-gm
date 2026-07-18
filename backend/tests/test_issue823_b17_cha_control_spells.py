"""TDD: Issue #823 (B17) — czary kontroli umysłu: charm_person + mass_fear.

Decyzja D3 (Piotr, 2026-06-21): czary maga wchodzą na **INT** (spójnie z resztą D-spell),
NIE na CHA. Stat rzucający = INT_mod, jak każdy inny czar nie-atakujący.

Zakres:
  • charm_person — single-target effect → kondycja `charmed` (reużycie istniejącej ścieżki
    `_resolve_effect_spell_in_combat`; pojedynek INT vs WIS celu). Zero zmian w silniku.
  • mass_fear — NOWY spell_type `effect_aoe` → kondycja `feared` na WSZYSTKICH żywych wrogach
    (pojedynek INT vs WIS per wróg). Łapie → feared; opór → ten wróg bez kondycji; Nat1 → miscast.
    Mana = pełny koszt z góry, BEZ zwrotu (czar obszarowy płaci jak attack_aoe). Zero obrażeń.
  • Backward compat: istniejące czary effect / attack_aoe nietknięte.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _fixtures_schema import table_sql

from app.services import combat_service, spell_service


class _FakeRng:
    def __init__(self, values):
        self._values = list(values)

    def randint(self, a, b):
        return self._values.pop(0)


# ─── D3 lock: pojedynek charm/fear używa INT rzucającego, NIE CHA ─────────────

def test_d3_charm_resolved_via_int_not_cha():
    """Mag INT 16 (+3) / CHA 6 (-2). Cel WIS 10 (0). Remis kości → mag wygrywa DZIĘKI INT.

    Gdyby silnik liczył CHA (-2), mag by przegrał. landed=True dowodzi: casting stat = INT (D3)."""
    caster = {"stats": {"INT": 16, "CHA": 6}}
    target_stats = {"WIS": 10}
    rng = _FakeRng([10, 10])  # remis kości → decyduje modyfikator rzucającego
    save = spell_service.resolve_spell_opposed_save(caster, target_stats, "charmed", rng=rng)
    assert save["landed"] is True
    assert save["save_stat"] == "WIS"
    assert save["int_mod"] == 3  # +3 z INT 16 — NIE -2 z CHA 6


def test_charm_and_fear_defend_with_wis():
    """Obie kondycje kontroli umysłu bronią się WIS (umysł), nie ciałem."""
    assert spell_service.spell_save_stat("charmed") == "WIS"
    assert spell_service.spell_save_stat("feared") == "WIS"


# ─── Integracja z silnikiem walki ────────────────────────────────────────────

def _combat_db(tmp_path, *, int_stat=16, mana=10, max_mana=10,
               g1_wis=8, g2_wis=8):
    db = tmp_path / "b17.db"
    player = {
        "id": "player", "type": "player", "name": "Mag",
        "hp_current": 12, "hp_max": 12, "defense": 10, "zone": "ranged",
        "stats": {"STR": 8, "DEX": 10, "CON": 8, "INT": int_stat, "WIS": 12, "CHA": 10},
        "conditions": [],
    }
    g1 = {
        "id": "goblin1", "type": "enemy", "enemy_key": "goblin", "name": "Goblin A",
        "hp_current": 20, "hp_max": 20, "defense": 10, "attack_bonus": 0,
        "damage_dice": "1d6", "zone": "ranged", "conditions": [],
        "stats": {"STR": 10, "DEX": 10, "CON": 8, "INT": 7, "WIS": g1_wis, "CHA": 8},
    }
    g2 = {
        "id": "goblin2", "type": "enemy", "enemy_key": "goblin", "name": "Goblin B",
        "hp_current": 20, "hp_max": 20, "defense": 10, "attack_bonus": 0,
        "damage_dice": "1d6", "zone": "ranged", "conditions": [],
        "stats": {"STR": 10, "DEX": 10, "CON": 8, "INT": 7, "WIS": g2_wis, "CHA": 8},
    }
    sheet = {
        "archetype": "scholar", "level": 3,
        "stats": player["stats"], "current_hp": 12, "max_hp": 12,
        "current_mana": mana, "max_mana": max_mana, "conditions": [], "skills": {},
    }
    combatants = json.dumps([player, g1, g2], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active',
          mode TEXT DEFAULT 'solo');
        INSERT INTO campaigns (id,title) VALUES (1,'B17');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Mag','fantasy','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, boss_defeated INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'["player","goblin1","goblin2"]','player','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        """ + table_sql("game_config_conditions") + """
        INSERT INTO game_config_conditions (key,label,effect_json,is_active,stackable) VALUES
          ('charmed','Zaczarowany','{{"effects":[{{"type":"static_stat_modifier","stat":"WIS","value":-3}}]}}',1,0),
          ('feared','Przerażony','{{"effects":[{{"type":"static_stat_modifier","stat":"WIS","value":-3}},{{"type":"behavior_override","behavior":"flee"}}]}}',1,0);
        """ + table_sql("game_config_spells") + """
        INSERT INTO game_config_spells (key,label,spell_type,effect_type,effect_stat,effect_duration,mana_cost,tier,damage_die,aoe) VALUES
          ('charm_person','Zauroczenie','effect','charmed','WIS',3,3,2,NULL,0),
          ('mass_fear','Fala Strachu','effect_aoe','feared','WIS',2,4,3,NULL,1),
          ('frost_grip','Lodowy Uścisk','effect','slowed','WIS',2,2,1,NULL,0),
          ('fireball','Kula Ognia','attack_aoe',NULL,NULL,1,6,5,'3d6',1);
        CREATE TABLE character_spells (character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1,
          learned_at_level INTEGER DEFAULT 1);
        """ + table_sql("game_config_enemies") + """
        INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,damage_die,dex_modifier,skills_json,stats_json,tier,loot_table_key,drop_chance,xp_award)
          VALUES ('goblin','Goblin',20,10,0,'1d6',0,NULL,NULL,'minion',NULL,0,10);
        """)
        # slowed condition for backward-compat test
        conn.execute("INSERT INTO game_config_conditions (key,label,effect_json,is_active,stackable) "
                     "VALUES ('slowed','Spowolniony','{\"effects\":[]}',1,0)")
        conn.commit()
    finally:
        conn.close()
    return db


def _enemy_conditions(db, enemy_id):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row[0])
    finally:
        conn.close()
    e = next(c for c in combatants if c.get("id") == enemy_id)
    return [str(x.get("key")) for x in (e.get("conditions") or [])]


def _mana(db):
    conn = sqlite3.connect(str(db))
    try:
        sj = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()[0]
    finally:
        conn.close()
    return int(json.loads(sj).get("current_mana"))


# ─── charm_person (single-target effect — reużycie ścieżki, casting INT) ──────

def test_charm_person_lands_applies_charmed_no_damage(tmp_path, monkeypatch):
    """charm_person łapie → cel `charmed`, pełna mana (10→7), ZERO obrażeń."""
    db = _combat_db(tmp_path, mana=10)
    monkeypatch.setattr(spell_service, "resolve_spell_opposed_save",
                        lambda *a, **k: {"landed": True, "save_stat": "WIS",
                                         "caster_total": 15, "target_total": 7})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, "goblin1", attacker="player", raw_d20=12,
                                            spell_key="charm_person")
    assert out.get("spell_type") == "effect"
    assert out.get("condition_applied") is True
    assert int(out.get("damage") or 0) == 0
    assert "charmed" in _enemy_conditions(db, "goblin1")
    assert _mana(db) == 7  # 10 - 3


# ─── mass_fear (NOWY effect_aoe — kondycja na WSZYSTKICH wrogach) ─────────────

def test_mass_fear_applies_feared_to_all_living(tmp_path, monkeypatch):
    """mass_fear, obaj wrogowie przegrywają save → OBAJ `feared`, ZERO obrażeń, pełna mana (10→6)."""
    db = _combat_db(tmp_path, mana=10)
    monkeypatch.setattr(spell_service, "resolve_spell_opposed_save",
                        lambda *a, **k: {"landed": True, "save_stat": "WIS",
                                         "caster_total": 15, "target_total": 5})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, "goblin1", attacker="player", raw_d20=12,
                                            spell_key="mass_fear")
    assert out.get("spell_type") == "effect_aoe"
    assert out.get("condition_applied") is True
    assert int(out.get("damage") or 0) == 0
    assert "feared" in _enemy_conditions(db, "goblin1")
    assert "feared" in _enemy_conditions(db, "goblin2")
    assert len(out.get("aoe_effect_hits") or []) == 2
    assert _mana(db) == 6  # 10 - 4, BEZ zwrotu (AoE)


def test_mass_fear_partial_resist(tmp_path, monkeypatch):
    """Wróg o wysokim WIS opiera się → tylko słabszy dostaje `feared`; brak zwrotu many."""
    db = _combat_db(tmp_path, g1_wis=8, g2_wis=18, mana=10)

    def _save(caster_sheet, target_stats, condition_key, rng=None):
        wis = int((target_stats or {}).get("WIS", 10) or 10)
        landed = wis < 14
        return {"landed": landed, "save_stat": "WIS",
                "caster_total": 15 if landed else 5, "target_total": 5 if landed else 18}

    monkeypatch.setattr(spell_service, "resolve_spell_opposed_save", _save)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, "goblin1", attacker="player", raw_d20=12,
                                            spell_key="mass_fear")
    assert "feared" in _enemy_conditions(db, "goblin1")      # WIS 8 → przegrał
    assert "feared" not in _enemy_conditions(db, "goblin2")  # WIS 18 → oparł się
    assert out.get("condition_applied") is True              # ≥1 wróg → hit
    assert _mana(db) == 6                                     # pełny koszt, bez zwrotu


def test_mass_fear_nat1_miscast_no_condition(tmp_path, monkeypatch):
    """Nat 1 → miscast: nikt nie dostaje `feared`, pełna mana stracona."""
    db = _combat_db(tmp_path, mana=10)
    monkeypatch.setattr(spell_service, "resolve_spell_opposed_save",
                        lambda *a, **k: {"landed": True, "save_stat": "WIS"})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, "goblin1", attacker="player", raw_d20=1,
                                            spell_key="mass_fear")
    assert out.get("condition_applied") is False
    assert _enemy_conditions(db, "goblin1") == []
    assert _enemy_conditions(db, "goblin2") == []
    assert _mana(db) == 6  # 10 - 4, miscast nie zwraca


def test_mass_fear_insufficient_mana_blocks(tmp_path):
    """Za mało many (3 < 4) → blocked, nikt nie `feared`."""
    db = _combat_db(tmp_path, mana=3)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, "goblin1", attacker="player", raw_d20=12,
                                            spell_key="mass_fear")
    assert out.get("blocked") is True
    assert out.get("mana_insufficient") is True
    assert _enemy_conditions(db, "goblin1") == []


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_existing_effect_spell_unchanged(tmp_path, monkeypatch):
    """frost_grip (single-target effect) nadal działa — effect_aoe nie zepsuł ścieżki ST."""
    db = _combat_db(tmp_path, mana=10)
    monkeypatch.setattr(spell_service, "resolve_spell_opposed_save",
                        lambda *a, **k: {"landed": True, "save_stat": "WIS",
                                         "caster_total": 15, "target_total": 5})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, "goblin1", attacker="player", raw_d20=12,
                                            spell_key="frost_grip")
    assert out.get("spell_type") == "effect"
    assert "slowed" in _enemy_conditions(db, "goblin1")


def test_attack_aoe_still_deals_damage(tmp_path, monkeypatch):
    """fireball (attack_aoe) nadal zadaje obrażenia — NIE wpada w gałąź effect_aoe."""
    db = _combat_db(tmp_path, mana=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda *a, **k: 5)  # niski unik wroga
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, "goblin1", attacker="player", raw_d20=18,
                                            spell_key="fireball")
    assert out.get("spell_type") == "attack_aoe"
    assert int(out.get("damage") or 0) > 0
