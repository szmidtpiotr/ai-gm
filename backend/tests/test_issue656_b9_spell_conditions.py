"""TDD: Issue #656 (B9) — czary NIE-atakujące (kondycja) w walce: model trafienia D-spell.

Czar kontroli (frost_grip/hex/poison_touch/blind/confusion/stun_bolt) w aktywnej walce:
  • NIE rzut na unik (jak broń), tylko POJEDYNEK PRZECIWNY: d20+INT_mag vs d20+stat_obrony_celu
    (WIS umysł / CON ciało) — decyzja D-spell, CZĘŚĆ AK.6. Czary ATAKUJĄCE nietknięte (#475).
  • łapie  → apply_condition_to_combatant (reużycie kondycji FAZY S, zero duplikatu), pełna mana
  • opór   → kondycja NIE nałożona, ½ many zwrócona (kara = tylko tura, jak pudło wojownika)
  • Nat 1  → miscast, pełna mana (bez zwrotu), bez kondycji
  • obrażeń BRAK (to nie atak).
`sleep` (effect_type=`sleeping`) wykluczony — brak kondycji `sleeping` w katalogu FAZY S.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import combat_service, spell_service


class _FakeRng:
    """randint zwraca kolejne wartości z listy — deterministyczne testy."""
    def __init__(self, values):
        self._values = list(values)

    def randint(self, a, b):
        return self._values.pop(0)


# ─── Pure helper: resolve_combat_effect_spell (logika trafienia + mana) ───────

def test_effect_spell_lands_full_mana():
    """Mag wygrywa pojedynek → outcome=landed, kondycja do nałożenia, ZERO zwrotu many."""
    caster = {"stats": {"INT": 16}}            # +3
    target_stats = {"CON": 8}                  # -1
    rng = _FakeRng([10, 10])                   # remis kości → mag wygrywa
    res = spell_service.resolve_combat_effect_spell(
        caster, target_stats, "slowed", mana_cost=2, raw_d20=10, rng=rng,
    )
    assert res["outcome"] == "landed"
    assert res["condition_applied"] is True
    assert res["mana_refund"] == 0
    assert res["save_stat"] == "CON"          # slowed = ciało


def test_effect_spell_resisted_refunds_half_mana():
    """Cel wygrywa pojedynek → outcome=resisted, brak kondycji, ½ many (floor) zwrócona."""
    caster = {"stats": {"INT": 8}}             # -1
    target_stats = {"WIS": 16}                 # +3
    rng = _FakeRng([5, 18])                    # cel zdecydowanie wygrywa
    res = spell_service.resolve_combat_effect_spell(
        caster, target_stats, "cursed", mana_cost=3, raw_d20=12, rng=rng,
    )
    assert res["outcome"] == "resisted"
    assert res["condition_applied"] is False
    assert res["mana_refund"] == 1            # floor(3/2)
    assert res["save_stat"] == "WIS"          # cursed = umysł


def test_effect_spell_nat1_miscast_keeps_full_mana():
    """Nat 1 → miscast: bez kondycji, bez zwrotu many (kara pełna)."""
    res = spell_service.resolve_combat_effect_spell(
        {"stats": {"INT": 16}}, {"WIS": 8}, "blinded", mana_cost=3, raw_d20=1,
    )
    assert res["outcome"] == "miscast"
    assert res["condition_applied"] is False
    assert res["mana_refund"] == 0


@pytest.mark.parametrize("cond,stat", [
    ("slowed", "CON"), ("poisoned", "CON"), ("stunned", "CON"),
    ("cursed", "WIS"), ("blinded", "WIS"), ("confused", "WIS"),
])
def test_supported_conditions_use_correct_save_stat(cond, stat):
    """6 wspieranych kondycji B9 mapuje się na poprawny stat obrony (ciało/umysł)."""
    assert spell_service.spell_save_stat(cond) == stat


# ─── Integracja z prawdziwym silnikiem walki (resolve_attack, spell_type=effect) ──

def _combat_db(tmp_path, *, int_stat=16, enemy_con=8, enemy_wis=8, mana=10, max_mana=10):
    db = tmp_path / "b9.db"
    player = {
        "id": "player", "type": "player", "name": "Mag",
        "hp_current": 12, "hp_max": 12, "defense": 10, "zone": "ranged",
        "stats": {"STR": 8, "DEX": 10, "CON": 8, "INT": int_stat, "WIS": 12, "CHA": 10},
        "conditions": [],
    }
    enemy = {
        "id": "goblin", "type": "enemy", "enemy_key": "goblin", "name": "Goblin",
        "hp_current": 20, "hp_max": 20, "defense": 10, "attack_bonus": 0,
        "damage_dice": "1d6", "zone": "ranged", "conditions": [],
        "stats": {"STR": 10, "DEX": 10, "CON": enemy_con, "INT": 7, "WIS": enemy_wis, "CHA": 8},
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
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active');
        INSERT INTO campaigns (id,title) VALUES (1,'B9');
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
          ('slowed','Spowolniony','{{"effects":[{{"type":"static_stat_modifier","stat":"DEX","value":-2}}]}}',1,0),
          ('cursed','Przeklęty','{{"effects":[{{"type":"static_stat_modifier","stat":"LCK","value":-2}}]}}',1,0);
        CREATE TABLE game_config_spells (key TEXT PRIMARY KEY, label TEXT, spell_type TEXT,
          effect_type TEXT, effect_stat TEXT, effect_duration INTEGER, mana_cost INTEGER,
          tier INTEGER, damage_die TEXT, is_active INTEGER DEFAULT 1);
        INSERT INTO game_config_spells (key,label,spell_type,effect_type,effect_stat,effect_duration,mana_cost,tier,damage_die) VALUES
          ('frost_grip','Lodowy Uścisk','effect','slowed','WIS',2,2,1,NULL),
          ('hex','Klątwa','effect','cursed','WIS',3,2,2,NULL),
          ('sleep','Sen','effect','sleeping','WIS',1,3,2,NULL),
          ('fire_bolt','Ognisty Pocisk','attack',NULL,NULL,1,2,1,'1d8');
        CREATE TABLE character_spells (character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1,
          learned_at_level INTEGER DEFAULT 1);
        CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT, hp_base INTEGER,
          ac_base INTEGER, attack_bonus INTEGER, damage_die TEXT, dex_modifier INTEGER,
          skills_json TEXT, stats_json TEXT, tier TEXT, loot_table_key TEXT,
          drop_chance REAL, xp_award INTEGER);
        INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,damage_die,dex_modifier,skills_json,stats_json,tier,loot_table_key,drop_chance,xp_award)
          VALUES ('goblin','Goblin',20,10,0,'1d6',0,NULL,NULL,'minion',NULL,0,10);
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def _enemy_conditions(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row[0])
    finally:
        conn.close()
    enemy = next(c for c in combatants if c.get("type") == "enemy")
    return [str(x.get("key")) for x in (enemy.get("conditions") or [])]


def _mana(db):
    conn = sqlite3.connect(str(db))
    try:
        sj = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()[0]
    finally:
        conn.close()
    return int(json.loads(sj).get("current_mana"))


def test_effect_spell_landed_applies_condition_no_damage(tmp_path, monkeypatch):
    """frost_grip łapie → goblin slowed, pełna mana zdjęta (10→8), ZERO obrażeń."""
    db = _combat_db(tmp_path, mana=10)
    monkeypatch.setattr(spell_service, "resolve_spell_opposed_save",
                        lambda *a, **k: {"landed": True, "save_stat": "CON",
                                          "caster_total": 15, "target_total": 7})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                            spell_key="frost_grip")
    assert out.get("spell_type") == "effect"
    assert out.get("condition_applied") is True
    assert int(out.get("damage") or 0) == 0          # czar kontroli nie zadaje obrażeń
    assert "slowed" in _enemy_conditions(db)
    assert _mana(db) == 8                             # 10 - 2 (pełny koszt)


def test_effect_spell_resisted_refunds_half_no_condition(tmp_path, monkeypatch):
    """hex opór → brak kondycji, ½ many zwrócona (10 - 2 + 1 = 9)."""
    db = _combat_db(tmp_path, mana=10)
    monkeypatch.setattr(spell_service, "resolve_spell_opposed_save",
                        lambda *a, **k: {"landed": False, "save_stat": "WIS",
                                          "caster_total": 7, "target_total": 18})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                            spell_key="hex")
    assert out.get("condition_applied") is False
    assert "cursed" not in _enemy_conditions(db)
    assert int(out.get("mana_refund") or 0) == 1
    assert _mana(db) == 9                             # 10 - 2 + 1 (zwrot ½)


def test_unsupported_effect_sleep_does_not_crash(tmp_path, monkeypatch):
    """sleep→sleeping: brak kondycji FAZY S → łagodne odbicie, brak kondycji, silnik nie pada."""
    db = _combat_db(tmp_path, mana=10)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=12,
                                            spell_key="sleep")
    assert out.get("block_reason") == "unsupported_effect"
    assert _enemy_conditions(db) == []


def test_attack_spell_unchanged_still_deals_damage(tmp_path, monkeypatch):
    """fire_bolt (attack) NIE wchodzi w gałąź effect — nadal rzut/obrażenia (#475 nietknięte)."""
    db = _combat_db(tmp_path, mana=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda *a, **k: 5)  # niski unik wroga
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, None, attacker="player", raw_d20=18,
                                            spell_key="fire_bolt")
    # attack path ustawia attack_roll/weapon_type=spell, NIE spell_type=effect
    assert out.get("spell_type") != "effect"
    assert "spell_effect" not in out
