"""TDD: Issue #657 (B10) — pula absorpcji / temp-HP dla tarcz maga.

Czary obronne (`ward_of_iron`, `mage_armor`) rzucone W WALCE nakładają na bohatera
pulę absorpcji (temp-HP) żyjącą na combatancie gracza (`combatants[].absorb_hp`).
Obrażenia wroga idą najpierw w pulę (po uniku/bloku, przed prawdziwym HP); pula 0 → tarcza znika.

Założenia (CZĘŚĆ AK.4/AK.5, Numbers Policy z #657):
  • ward_of_iron (T1, 2 mana) → absorpcja 6
  • mage_armor   (T2, 3 mana) → absorpcja 10
  • płaska, NIE stackuje (re-cast = świeża pula = wartość czaru), combat-scoped
  • rzut tarczy: pełna mana zdjęta, ZERO obrażeń wrogowi, tury nie advance
  • kolejność redukcji: unik → blok → absorpcja → HP
Czary atakujące (#475) i kontroli (B9) nietknięte.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import combat_service, spell_service


# ─── Pure helper: defense_absorb_amount (ile temp-HP daje tarcza) ─────────────

def test_absorb_amount_reads_effect_json():
    """effect_json.absorb wprost → ta wartość (ward 6, mage 10)."""
    assert spell_service.defense_absorb_amount(
        {"key": "ward_of_iron", "tier": 1, "effect_json": '{"absorb":6}'}) == 6
    assert spell_service.defense_absorb_amount(
        {"key": "mage_armor", "tier": 2, "effect_json": '{"absorb":10}'}) == 10


def test_absorb_amount_falls_back_by_tier_when_missing():
    """Brak effect_json/absorb → fallback wg tieru (T1=4, T2=8), nigdy 0."""
    assert spell_service.defense_absorb_amount(
        {"key": "x", "tier": 1, "effect_json": None}) == 4
    assert spell_service.defense_absorb_amount(
        {"key": "y", "tier": 2, "effect_json": "{}"}) == 8


# ─── Pure helper: _apply_absorption (pula pochłania obrażenia) ────────────────

def test_apply_absorption_soaks_partial():
    """Pula 6, cios 4 → 0 do HP, pula 2, out.absorbed=4."""
    p = {"absorb_hp": 6}
    out = {}
    dmg = combat_service._apply_absorption(p, 4, out)
    assert dmg == 0
    assert p["absorb_hp"] == 2
    assert out["absorbed"] == 4
    assert out["absorb_remaining"] == 2


def test_apply_absorption_depletes_and_overflows():
    """Pula 2, cios 5 → 3 do HP, pula znika (klucz usunięty), out.absorbed=2."""
    p = {"absorb_hp": 2}
    out = {}
    dmg = combat_service._apply_absorption(p, 5, out)
    assert dmg == 3
    assert "absorb_hp" not in p
    assert out["absorbed"] == 2
    assert out["absorb_remaining"] == 0


def test_apply_absorption_noop_without_pool():
    """Brak puli → obrażenia bez zmian, nic nie dopisujemy."""
    p = {}
    out = {}
    dmg = combat_service._apply_absorption(p, 4, out)
    assert dmg == 4
    assert "absorbed" not in out


# ─── Integracja z silnikiem walki (resolve_attack, spell_type=defense) ────────

def _combat_db(tmp_path, *, mana=10, max_mana=10, player_absorb=None):
    db = tmp_path / "b10.db"
    player = {
        "id": "player", "type": "player", "name": "Mag",
        "hp_current": 12, "hp_max": 12, "defense": 10, "zone": "ranged",
        "stats": {"STR": 8, "DEX": 10, "CON": 8, "INT": 16, "WIS": 12, "CHA": 10},
        "conditions": [],
    }
    if player_absorb is not None:
        player["absorb_hp"] = player_absorb
    enemy = {
        "id": "goblin", "type": "enemy", "enemy_key": "goblin", "name": "Goblin",
        "hp_current": 20, "hp_max": 20, "defense": 10, "attack_bonus": 1,
        "damage_dice": "1d6", "zone": "ranged", "conditions": [],
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 7, "WIS": 8, "CHA": 8},
    }
    sheet = {
        "archetype": "scholar", "level": 3,
        "stats": player["stats"], "current_hp": 12, "max_hp": 12,
        "current_mana": mana, "max_mana": max_mana, "conditions": [], "skills": {},
    }
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'B10');
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
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        CREATE TABLE game_config_conditions (key TEXT PRIMARY KEY, label TEXT, effect_json TEXT,
          is_active INTEGER DEFAULT 1, stackable INTEGER DEFAULT 0);
        INSERT INTO game_config_conditions (key,label,effect_json,is_active,stackable) VALUES
          ('slowed','Spowolniony','{{"effects":[]}}',1,0);
        CREATE TABLE game_config_spells (key TEXT PRIMARY KEY, label TEXT, spell_type TEXT,
          effect_type TEXT, effect_stat TEXT, effect_duration INTEGER, mana_cost INTEGER,
          tier INTEGER, damage_die TEXT, effect_json TEXT, is_active INTEGER DEFAULT 1);
        INSERT INTO game_config_spells (key,label,spell_type,effect_type,effect_stat,effect_duration,mana_cost,tier,damage_die,effect_json) VALUES
          ('ward_of_iron','Żelazna Straż','defense',NULL,NULL,1,2,1,NULL,'{{"absorb":6}}'),
          ('mage_armor','Zbroja Maga','defense',NULL,NULL,1,3,2,NULL,'{{"absorb":10}}'),
          ('frost_grip','Lodowy Uścisk','effect','slowed','WIS',2,2,1,NULL,NULL),
          ('fire_bolt','Ognisty Pocisk','attack',NULL,NULL,1,2,1,'1d8',NULL);
        CREATE TABLE character_spells (character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1,
          learned_at_level INTEGER DEFAULT 1);
        CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT, hp_base INTEGER,
          ac_base INTEGER, attack_bonus INTEGER, damage_die TEXT, dex_modifier INTEGER,
          skills_json TEXT, stats_json TEXT, tier TEXT, loot_table_key TEXT,
          drop_chance REAL, xp_award INTEGER, attacks_per_turn INTEGER DEFAULT 1,
          image_url TEXT);
        INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,damage_die,dex_modifier,skills_json,stats_json,tier,loot_table_key,drop_chance,xp_award)
          VALUES ('goblin','Goblin',20,10,1,'1d6',0,NULL,NULL,'minion',NULL,0,10);
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def _player_combatant(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row[0])
    finally:
        conn.close()
    return next(c for c in combatants if c.get("type") == "player")


def _mana(db):
    conn = sqlite3.connect(str(db))
    try:
        sj = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()[0]
    finally:
        conn.close()
    return int(json.loads(sj).get("current_mana"))


def test_cast_ward_of_iron_grants_absorb_pool(tmp_path):
    """ward_of_iron w walce → absorb_hp=6 na graczu, mana 10→8, ZERO obrażeń wrogowi."""
    db = _combat_db(tmp_path, mana=10)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                            spell_key="ward_of_iron")
    assert out.get("spell_type") == "defense"
    assert int(out.get("absorb_granted") or 0) == 6
    assert int(out.get("damage") or 0) == 0
    assert _player_combatant(db).get("absorb_hp") == 6
    assert _mana(db) == 8


def test_cast_mage_armor_grants_larger_pool(tmp_path):
    """mage_armor (T2) → absorb_hp=10, mana 10→7 (koszt 3)."""
    db = _combat_db(tmp_path, mana=10)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                            spell_key="mage_armor")
    assert int(out.get("absorb_granted") or 0) == 10
    assert _player_combatant(db).get("absorb_hp") == 10
    assert _mana(db) == 7


def test_cast_shield_insufficient_mana_blocked(tmp_path):
    """Za mało many → blocked, pula NIE nadana."""
    db = _combat_db(tmp_path, mana=1)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                            spell_key="ward_of_iron")
    assert out.get("blocked") is True
    assert out.get("mana_insufficient") is True
    assert _player_combatant(db).get("absorb_hp") in (None, 0)


def test_recast_shield_does_not_stack(tmp_path):
    """Re-cast przy aktywnej puli 6 → pula nadal 6 (świeża, NIE 12)."""
    db = _combat_db(tmp_path, mana=10, player_absorb=6)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                      spell_key="ward_of_iron")
    assert _player_combatant(db).get("absorb_hp") == 6


def test_enemy_attack_soaks_absorb_before_hp(tmp_path):
    """Wróg trafia: pula pochłania całość, HP gracza bez zmian (12).

    attack_bonus=1 → attack_roll=19, player_evasion=18 → hit, margin=1.
    #826 margin model: base roll=4 + margin_bonus=1 = 5 total damage.
    absorb_hp=6 soaks 5 → absorb_hp=1, damage_to_hp=0, HP=12.
    """
    db = _combat_db(tmp_path, mana=10, player_absorb=6)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 18), \
         patch.object(combat_service, "roll_damage_dice", lambda *a, **k: 4):
        # current_turn musi być wrogiem
        conn = sqlite3.connect(str(db))
        conn.execute("UPDATE active_combat SET current_turn='goblin' WHERE campaign_id=1")
        conn.commit(); conn.close()
        out = combat_service.resolve_attack(1, None, attacker="enemy", raw_d20=None)
    assert out.get("hit") is True
    assert int(out.get("absorbed") or 0) == 5        # 4 base + 1 margin (#826)
    assert int(out.get("damage") or 0) == 0          # całość pochłonięta
    assert int(out.get("player_hp_remaining") or 0) == 12   # HP nietknięte
    assert _player_combatant(db).get("absorb_hp") == 1      # 6 - 5 = 1


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_attack_spell_unchanged_still_deals_damage(tmp_path):
    """fire_bolt (attack) NIE wchodzi w gałąź defense — nadal atak (#475 nietknięte)."""
    db = _combat_db(tmp_path, mana=10)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 5):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=18,
                                            spell_key="fire_bolt")
    assert out.get("spell_type") != "defense"
    assert "absorb_granted" not in out


def test_effect_spell_unchanged_still_applies_condition(tmp_path, monkeypatch):
    """frost_grip (effect/B9) NIE wchodzi w gałąź defense — nadal kondycja, zero obrażeń."""
    db = _combat_db(tmp_path, mana=10)
    monkeypatch.setattr(spell_service, "resolve_spell_opposed_save",
                        lambda *a, **k: {"landed": True, "save_stat": "CON",
                                          "caster_total": 15, "target_total": 7})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                            spell_key="frost_grip")
    assert out.get("spell_type") == "effect"
    assert "absorb_granted" not in out
