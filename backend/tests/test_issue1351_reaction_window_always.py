"""TDD: Issue #1351 (WALKA-T5, 5e) — okno reakcji ZAWSZE w trybie single-player.

Decyzja designowa Piotra (2026-07-12): silnik NIGDY nie rozstrzyga uniku za gracza.
Przy KAŻDYM trafieniu wroga w gracza (poza Nat 1 wroga = auto-pudło) otwiera się okno
reakcji — nawet gdy postać nie ma żadnej wyszkolonej reakcji (brak dodge/shield/many,
albo cap #1322 wyczerpany / lockout). Wtedy `pending_reaction.options == []` i jedyną
możliwą decyzją jest „Przyjmij cios" (`resolve_reaction("take")`).

Automatyczna ścieżka `player_evasion` (silnik sam rzuca d20+DEX i aplikuje obrażenia,
bez pytania) ZOSTAJE WYŁĄCZNIE dla multiplayer (sweep nieobecnych graczy: combatant
`player:N`). W single-player (`id="player"`) auto-evasion znika.

Regresja pilnowana: `combat_turns` event `reaction_window` ma `hp_after` = HP SPRZED ciosu.
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


# ─── DB fixtures ──────────────────────────────────────────────────────────────

def _combat_db(tmp_path, *, mp=False, dodge_rank=0, attack_bonus=10, round_n=1,
               reaction_used_round=0, reaction_locked_round=0, second_enemy=False):
    """Buduje walkę 1 gracz vs wróg. mp=True → combatant `player:1` (multiplayer)."""
    db = tmp_path / "t5.db"
    player_id = "player:1" if mp else "player"
    player_type = "player"
    player = {
        "id": player_id, "type": player_type, "name": "Drundor",
        "hp_current": 20, "hp_max": 20, "defense": 10, "zone": "engaged",
        "stats": {"STR": 12, "DEX": 14, "CON": 10, "INT": 14, "WIS": 10, "CHA": 10},
        "conditions": [],
    }
    if reaction_used_round:
        player["reaction_used_round"] = reaction_used_round
    if reaction_locked_round:
        player["reaction_locked_round"] = reaction_locked_round
    enemy = {
        "id": "bandit", "type": "enemy", "enemy_key": "bandit", "name": "Bandyta",
        "hp_current": 40, "hp_max": 40, "attack_bonus": attack_bonus,
        "damage_dice": "1d8", "zone": "engaged",
    }
    comb = [player, enemy]
    order = ["bandit", player_id]
    if second_enemy:
        comb.append({
            "id": "bandit2", "type": "enemy", "enemy_key": "bandit", "name": "Bandyta II",
            "hp_current": 40, "hp_max": 40, "attack_bonus": attack_bonus,
            "damage_dice": "1d8", "zone": "engaged",
        })
        order = ["bandit", "bandit2", player_id]
    sheet = {"stats": player["stats"], "current_hp": 20, "max_hp": 20,
             "defense": {"base": 10}, "conditions": [],
             "skills": {"dodge": dodge_rank, "shield_block": 0}}
    combatants = json.dumps(comb, ensure_ascii=False).replace("'", "''")
    order_json = json.dumps(order).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'T5');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Drundor','fantasy','{sj}');
        """ + table_sql("game_config_weapons") + """
        CREATE TABLE character_inventory (id INTEGER PRIMARY KEY AUTOINCREMENT,
          character_id INTEGER, weapon_key TEXT, item_key TEXT, equipped INTEGER DEFAULT 0,
          durability_current INTEGER, durability_max INTEGER, affixes_json TEXT);
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,{round_n},'{order_json}','bandit','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def _player_hp(db, cid="player"):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        for c in json.loads(row[0]):
            if c.get("id") == cid:
                return int(c.get("hp_current", -1))
    finally:
        conn.close()
    return -1


def _pending(db, cid="player"):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
        for c in json.loads(row[0]):
            if c.get("id") == cid:
                return c.get("pending_reaction")
    finally:
        conn.close()
    return None


def _reaction_window_log(db):
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT hp_after, narrative FROM combat_turns WHERE actor='enemy' AND event_type='attack'"
        ).fetchall()
    finally:
        conn.close()
    for hp_after, narr in rows:
        try:
            n = json.loads(narr or "{}")
        except Exception:
            n = {}
        if n.get("reaction_window"):
            return {"hp_after": hp_after, "narrative": n}
    return None


# ─── Test główny 5e: single-player bez skilla → OKNO (take-only), NIE auto-evasion ──

def test_sp_hit_no_skill_opens_reaction_window(tmp_path, monkeypatch):
    """Single-player, postać BEZ reakcji obronnych, wróg trafia → okno reakcji z pustą
    listą opcji (tylko „Przyjmij"). Obrażenia NIE naliczone, HP nietknięte, `player_evasion`
    NIE użyte (silnik nie rzucił uniku za gracza)."""
    db = _combat_db(tmp_path, mp=False, dodge_rank=0, attack_bonus=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)   # atak 20 (raw != 1)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 5)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d8", "rolls": [5], "sides": 8, "n": 1})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out["hit"] is True
    assert out.get("reaction_window") is True
    assert out.get("reaction_options") == []          # brak wyszkolonych reakcji → tylko „Przyjmij"
    assert out.get("player_evasion") is None          # silnik NIE rzucił uniku za gracza
    assert _player_hp(db) == 20                        # obrażenia wstrzymane do resolve_reaction
    pend = _pending(db)
    assert pend is not None
    assert pend.get("options") == []
    assert int(pend.get("damage", 0)) > 0


def test_sp_take_only_window_resolve_take_applies_full_damage(tmp_path, monkeypatch):
    """Po oknie take-only: resolve_reaction("take") nalicza pełne obrażenia i czyści pending.
    #826: 5 baza + margines (atak 20 − obrona 10 = 10 → 2 progi → +2), pancerz 0 → 7."""
    db = _combat_db(tmp_path, mp=False, dodge_rank=0, attack_bonus=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 5)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d8", "rolls": [5], "sides": 8, "n": 1})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_attack(1, 0, attacker="enemy")
        out = combat_service.resolve_reaction(1, "take")
    assert out["damage"] == 7
    assert out["player_hp_remaining"] == 13
    assert _player_hp(db) == 13
    assert _pending(db) is None


def test_sp_reaction_window_log_hp_before_hit(tmp_path, monkeypatch):
    """Regresja: event `reaction_window` w combat_turns ma hp_after = HP SPRZED ciosu (20)."""
    db = _combat_db(tmp_path, mp=False, dodge_rank=0, attack_bonus=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 5)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d8", "rolls": [5], "sides": 8, "n": 1})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_attack(1, 0, attacker="enemy")
    log = _reaction_window_log(db)
    assert log is not None
    assert log["hp_after"] == 20


def test_sp_window_opens_even_when_reaction_capped(tmp_path, monkeypatch):
    """5e: nawet gdy cap #1322 wyczerpany (reaction_used_round + swarm ≥2 wrogów) →
    w single-player OKNO nadal się otwiera (take-only), zamiast cichego naliczenia."""
    db = _combat_db(tmp_path, mp=False, dodge_rank=2, attack_bonus=10, round_n=1,
                    reaction_used_round=1, second_enemy=True)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 6)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d8", "rolls": [6], "sides": 8, "n": 1})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out.get("reaction_window") is True
    assert out.get("reaction_options") == []          # cap wyczerpany → opcje obronne puste
    assert _player_hp(db) == 20


# ─── Backward-compat: skill w SP → okno z opcją (bez zmian) ────────────────────

def test_sp_with_dodge_skill_window_has_dodge_option(tmp_path, monkeypatch):
    """Postać ze skillem dodge w single-player → okno reakcji z opcją „dodge" (jak #633)."""
    db = _combat_db(tmp_path, mp=False, dodge_rank=2, attack_bonus=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out.get("reaction_window") is True
    assert "dodge" in (out.get("reaction_options") or [])


def test_sp_enemy_nat1_no_window(tmp_path, monkeypatch):
    """#826 zostaje: Nat 1 wroga = auto-pudło, żadnego okna nawet w SP, HP nietknięte."""
    db = _combat_db(tmp_path, mp=False, dodge_rank=0, attack_bonus=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 1)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out["hit"] is False
    assert out.get("reaction_window") is not True
    assert _player_hp(db) == 20


# ─── Backward-compat MP: auto-evasion ZOSTAJE dla nieobecnych graczy (sweep) ────

def test_mp_no_skill_still_auto_evasion(tmp_path, monkeypatch):
    """Multiplayer (combatant `player:1`), postać bez skilla → stara ścieżka auto-evasion:
    silnik rzuca d20+DEX, brak okna reakcji (sweep nieobecnych)."""
    db = _combat_db(tmp_path, mp=True, dodge_rank=0, attack_bonus=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 5)
    monkeypatch.setattr(combat_service, "roll_dice_detailed",
                        lambda *a, **k: {"die": "1d8", "rolls": [5], "sides": 8, "n": 1})
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out.get("reaction_window") is not True     # MP bez skilla → brak okna
    assert out.get("player_evasion") is not None      # auto-evasion nadal działa
    assert _player_hp(db, cid="player:1") < 20         # obrażenia naliczone od razu
