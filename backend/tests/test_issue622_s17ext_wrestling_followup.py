"""TDD: Issue #622 — S17-EXT (Część A solo): follow-up zapasów gated za wrestling rank ≥ 3.

Po naprawie #621 zapasy są tempo-neutralne (zużywają turę gracza, odbierają turę wrogowi),
ale bez „nagrody" w chwili wykonania. Bezwarunkowy darmowy atak = zapasy ściśle lepsze od
„Ataku" → łamie balans. Decyzja Piotra (2026-06-15): gate za inwestycję w skill (rank ≥ 3,
spójnie z proficiency).

Reguła (Część A — SOLO, wartości startowe Numbers Policy):
  • Wyzwalacz: udane zapasy (SUCCESS / CRITICAL_SUCCESS) ORAZ wrestling rank ≥ 3.
  • Efekt: SŁABSZY darmowy cios w tej samej turze — rzut bronią gracza, obrażenia ÷2
    (floor, min 1), BEZ nat-20-double, BEZ ponownego wyzwalania zapasów. Jeden cios na zapasy.
  • Reuse ekonomii `extra_action` (S12): follow-up NIE konsumuje kolejnej akcji — wrestling
    i tak woła advance_turn raz. Brak rekurencji (jeden inline event, nie pętla).
  • Rank 1–2 = czysta kontrola jak dziś (baza nietknięta = balans chroniony).

Część B (MP — schwytany wróg daje przewagę sojusznikowi) jest ⛔ ODŁOŻONA do FAZY 5
(wymaga towarzyszy/MP + systemu reakcji) — NIE testowana tutaj.

RZUTY ATAKU W WALCE (nat 20 / nat 1, podwójne obrażenia) NIETKNIĘTE — follow-up to osobny,
słabszy cios.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import combat_service


# ─── Harness: minimalna baza walki (wzorzec test_issue612_s17_wrestling) ──────

def _combat_db(tmp_path, *, player_str=14, enemy_str=10, wrestling_rank=1,
               player_zone="engaged", enemy_zone="engaged", enemy_hp=40):
    db = tmp_path / "wrestle_ext.db"
    player = {
        "id": "player", "type": "player", "name": "Aldric",
        "hp_current": 20, "hp_max": 20, "defense": 10, "zone": player_zone,
        "stats": {"STR": player_str, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "conditions": [],
    }
    enemy = {
        "id": "bandit", "type": "enemy", "enemy_key": "bandit", "name": "Bandyta",
        "hp_current": enemy_hp, "hp_max": 40, "defense": 10, "attack_bonus": 0,
        "damage_dice": "1d6", "zone": enemy_zone, "conditions": [],
        "stats": {"STR": enemy_str, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
    }
    sheet = {"stats": player["stats"], "current_hp": 20, "max_hp": 20,
             "conditions": [], "skills": {"wrestling": wrestling_rank}}
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'S17EXT');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Aldric','fantasy','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'["player","bandit"]','player','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        CREATE TABLE game_config_conditions (key TEXT PRIMARY KEY, label TEXT, effect_json TEXT,
          is_active INTEGER DEFAULT 1, stackable INTEGER DEFAULT 0);
        INSERT INTO game_config_conditions (key,label,effect_json,is_active,stackable) VALUES
          ('slowed','Spowolniony','{{"effects":[{{"type":"static_stat_modifier","stat":"DEX","value":-2}}]}}',1,0),
          ('stunned','Ogłuszony','{{"effects":[{{"type":"skip_turn"}}]}}',1,0);
        CREATE TABLE skill_counters (player_skill_key TEXT PRIMARY KEY, counter_type TEXT DEFAULT 'dc',
          counter_key TEXT, default_dc INTEGER DEFAULT 12,
          on_success_condition TEXT, on_crit_condition TEXT, on_critfail_self_condition TEXT);
        INSERT INTO skill_counters
          (player_skill_key,counter_type,counter_key,default_dc,on_success_condition,on_crit_condition,on_critfail_self_condition)
          VALUES ('wrestling','opposed','STR',12,'slowed','stunned','slowed');
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def _seq_d20(values):
    it = iter(values)
    return lambda *a, **k: next(it)


def _enemy_hp(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
    finally:
        conn.close()
    enemy = next(c for c in json.loads(row[0]) if c.get("type") == "enemy")
    return int(enemy.get("hp_current", 0) or 0)


def _followup_events(db):
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT damage, narrative FROM combat_turns WHERE event_type='wrestling_followup'"
        ).fetchall()
    finally:
        conn.close()
    return rows


# ─── Test główny: rank 3 sukces → jeden follow-up cios ÷2 ─────────────────────

def test_rank3_success_triggers_halved_followup(tmp_path, monkeypatch):
    """Rank ≥ 3 + SUCCESS → follow-up: enemy traci obrażenia, log 'wrestling_followup' raz,
    damage = floor(rzut/2), min 1. Brak nat-20-double (followup nie używa rzutu ataku)."""
    db = _combat_db(tmp_path, player_str=14, enemy_str=10, wrestling_rank=3, enemy_hp=40)
    # player: STR+2 + rank3 + proficiency2 = +7; d20=12 → 19. enemy: +0; d20=16 → 16.
    # margines +3 → SUCCESS (nie crit, nie porażka).
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([12, 16]))
    # roll_damage_dice deterministyczny: surowe obrażenia = 7 → połowa = 3.
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_wrestling(1)
    assert out["ok"] is True
    assert out["outcome"] == "SUCCESS"
    fu = out.get("followup")
    assert fu is not None, "rank 3 sukces musi dać follow-up cios"
    assert fu["damage"] == 3, "obrażenia ÷2 (floor): 7 // 2 = 3"
    # enemy 40 - 3 = 37
    assert _enemy_hp(db) == 37
    rows = _followup_events(db)
    assert len(rows) == 1, "dokładnie jeden cios na zapasy (brak rekurencji/pętli)"
    assert int(rows[0][0]) == 3


def test_rank3_critical_success_triggers_followup(tmp_path, monkeypatch):
    """Krytyk identycznie jak sukces — follow-up ÷2, jeden cios."""
    db = _combat_db(tmp_path, player_str=18, enemy_str=8, wrestling_rank=3, enemy_hp=40)
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([15, 8]))  # margines ≥ +5
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 8)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_wrestling(1)
    assert out["outcome"] == "CRITICAL_SUCCESS"
    assert out["followup"] is not None
    assert out["followup"]["damage"] == 4  # 8 // 2
    assert _enemy_hp(db) == 36
    assert len(_followup_events(db)) == 1


def test_followup_damage_min_one(tmp_path, monkeypatch):
    """Połowa zaokrąglona w dół, ale nigdy < 1 (rzut 1 → 1 // 2 = 0 → clamp do 1)."""
    db = _combat_db(tmp_path, player_str=14, enemy_str=10, wrestling_rank=3, enemy_hp=40)
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([12, 12]))
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 1)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_wrestling(1)
    assert out["followup"]["damage"] == 1
    assert _enemy_hp(db) == 39


# ─── Gate: rank 1–2 = brak follow-upu (baza nietknięta) ───────────────────────

def test_rank2_no_followup(tmp_path, monkeypatch):
    """Rank 2 + SUCCESS → czysta kontrola jak dziś, BEZ darmowego ciosu."""
    db = _combat_db(tmp_path, player_str=14, enemy_str=10, wrestling_rank=2, enemy_hp=40)
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([12, 12]))
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_wrestling(1)
    assert out["outcome"] == "SUCCESS"
    assert out.get("followup") is None, "rank 2 nie może dać follow-upu"
    assert _enemy_hp(db) == 40, "enemy HP nietknięte bez follow-upu"
    assert _followup_events(db) == []


def test_rank3_failure_no_followup(tmp_path, monkeypatch):
    """Rank 3 ale PORAŻKA → brak follow-upu (wyzwalacz to udane zapasy)."""
    db = _combat_db(tmp_path, player_str=8, enemy_str=18, wrestling_rank=3, enemy_hp=40)
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([3, 15]))  # margines ≤ −5
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_wrestling(1)
    assert out["outcome"] in ("FAILURE", "CRITICAL_FAILURE")
    assert out.get("followup") is None
    assert _enemy_hp(db) == 40


# ─── Backward compat: turę nadal konsumuje (follow-up nie podwaja akcji) ───────

def test_followup_does_not_consume_extra_turn(tmp_path, monkeypatch):
    """Po zapasach z follow-upem tura przechodzi do wroga RAZ (advance_turn raz, nie dwa)."""
    db = _combat_db(tmp_path, player_str=14, enemy_str=10, wrestling_rank=3, enemy_hp=40)
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([12, 12]))
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 6)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_wrestling(1)
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("SELECT current_turn FROM active_combat WHERE campaign_id=1").fetchone()[0]
    finally:
        conn.close()
    assert cur == "bandit", "follow-up nie może podwoić tury — kolej wroga"
