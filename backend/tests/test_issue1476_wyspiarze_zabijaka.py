"""Issue #1476 — Wyspiarze: kit Wojownika-Zabijaki w realnym silniku walki.

Integracja (wzorzec 1:1 z test_issue612_s17_wrestling): budujemy prawdziwy wiersz
`active_combat` z bohaterem-wyspiarzem (warrior) i wrogiem, po czym wołamy funkcje
silnika bezpośrednio, kontrolując rzuty przez monkeypatch `roll_d20`.

Zdolności:
  * Groźba bosmana (CHA) — sukces → wróg dostaje `frightened`; słaby wróg (HP <30%
    max) na sukcesie panikuje i ZNIKA z walki (bez śmierci, bez łupu).
  * Chwyt sztauera (1/walka, STR) — sukces odwraca strefę wroga (ZWARCIE↔DYSTANS);
    drugie użycie w tej samej walce jest zablokowane (already_used).
  * Brudny cios (1/walka) — cios w ZWARCIU: połowiczne obrażenia + `blinded`;
    cel poza zwarciem → blokada bez konsumpcji tury.

Bramka: tylko rasa=wyspiarze ∧ archetyp=warrior — inaczej ValueError('not_zabijaka').
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


def _combat_db(
    tmp_path,
    *,
    race="wyspiarze",
    archetype="warrior",
    player_cha=16,
    player_str=16,
    enemy_wis=10,
    enemy_str=10,
    player_zone="engaged",
    enemy_zone="engaged",
    enemy_hp=40,
    grip_used=False,
    dirty_used=False,
):
    db = tmp_path / "zabijaka.db"
    player = {
        "id": "player", "type": "player", "name": "Nakea",
        "hp_current": 24, "hp_max": 24, "defense": 10, "zone": player_zone,
        "stats": {"STR": player_str, "DEX": 10, "CON": 12, "INT": 8, "WIS": 10, "CHA": player_cha},
        "conditions": [],
    }
    if grip_used:
        player["sztauer_used_combat"] = True
    if dirty_used:
        player["dirty_blow_used_combat"] = True
    enemy = {
        "id": "korsarz", "type": "enemy", "enemy_key": "korsarz", "name": "Korsarz",
        "hp_current": enemy_hp, "hp_max": 40, "defense": 10, "attack_bonus": 0,
        "damage_dice": "1d6", "zone": enemy_zone, "conditions": [],
        "stats": {"STR": enemy_str, "DEX": 10, "CON": 10, "INT": 10, "WIS": enemy_wis, "CHA": 10},
    }
    sheet = {
        "archetype": archetype, "stats": player["stats"],
        "current_hp": 24, "max_hp": 24, "conditions": [],
        "skills": {"intimidation": 1, "wrestling": 1},
    }
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'WL');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, race TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,race,sheet_json)
          VALUES (1,1,1,'Nakea','fantasy','{race}','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'["player","korsarz"]','player','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        """ + table_sql("game_config_conditions") + """
        INSERT INTO game_config_conditions (key,label,effect_json,is_active,stackable) VALUES
          ('frightened','Przerażony','{{"effects":[{{"type":"static_stat_modifier","stat":"CHA","value":-2}}]}}',1,0),
          ('blinded','Oślepiony','{{"effects":[{{"type":"static_stat_modifier","stat":"DEX","value":-4}}]}}',1,0);
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def _seq_d20(values):
    it = iter(values)
    return lambda *a, **k: next(it)


def _combatants(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants, current_turn FROM active_combat WHERE campaign_id=1").fetchone()
    finally:
        conn.close()
    return json.loads(row[0]), row[1]


def _enemy(combatants):
    return next((c for c in combatants if c.get("type") == "enemy"), None)


def _player(combatants):
    return next(c for c in combatants if c.get("type") == "player")


# ─── Groźba bosmana ──────────────────────────────────────────────────────────

def test_threat_success_frightens_enemy(tmp_path, monkeypatch):
    db = _combat_db(tmp_path, player_cha=16, enemy_wis=10, enemy_hp=40)  # player +3, enemy +0
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([14, 8]))  # margines duży → sukces
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_boatswain_threat(1)
    assert out["ok"] is True and out["success"] is True and out["fled"] is False
    combatants, current = _combatants(db)
    enemy = _enemy(combatants)
    assert enemy is not None
    assert "frightened" in [str(c.get("key")) for c in (enemy.get("conditions") or [])]
    assert current == "korsarz"  # tura skonsumowana


def test_threat_weak_enemy_flees(tmp_path, monkeypatch):
    db = _combat_db(tmp_path, player_cha=16, enemy_wis=8, enemy_hp=10)  # HP 10/40 = 25% < 30%
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([15, 6]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_boatswain_threat(1)
    assert out["success"] is True and out["fled"] is True
    combatants, _ = _combatants(db)
    assert _enemy(combatants) is None  # spanikowany wróg zniknął z walki


def test_threat_requires_zabijaka(tmp_path, monkeypatch):
    db = _combat_db(tmp_path, race="human")  # nie-wyspiarz
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([14, 8]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        with pytest.raises(ValueError, match="not_zabijaka"):
            combat_service.resolve_boatswain_threat(1)


def test_threat_blocked_for_wyspiarz_rogue(tmp_path, monkeypatch):
    db = _combat_db(tmp_path, archetype="rogue")  # Kombinator nie ma kitu Zabijaki
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([14, 8]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        with pytest.raises(ValueError, match="not_zabijaka"):
            combat_service.resolve_boatswain_threat(1)


# ─── Chwyt sztauera ──────────────────────────────────────────────────────────

def test_grip_flips_enemy_zone(tmp_path, monkeypatch):
    db = _combat_db(tmp_path, player_str=18, enemy_str=8, enemy_zone="engaged")
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([15, 6]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_stevedore_grip(1)
    assert out["success"] is True
    assert out["from_zone"] == "engaged" and out["to_zone"] == "ranged"
    combatants, _ = _combatants(db)
    assert _enemy(combatants)["zone"] == "ranged"
    assert _player(combatants).get("sztauer_used_combat") is True  # ładunek zużyty


def test_grip_second_use_blocked(tmp_path, monkeypatch):
    db = _combat_db(tmp_path, grip_used=True)  # ładunek już zużyty
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([15, 6]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_stevedore_grip(1)
    assert out["ok"] is False and out["block_reason"] == "already_used"
    _, current = _combatants(db)
    assert current == "player"  # tura NIE skonsumowana


# ─── Brudny cios ─────────────────────────────────────────────────────────────

def test_dirty_blow_damages_and_blinds(tmp_path, monkeypatch):
    db = _combat_db(tmp_path, enemy_zone="engaged", enemy_hp=40)
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([12, 12]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_dirty_blow(1)
    assert out["ok"] is True and out["damage"] >= 1
    combatants, current = _combatants(db)
    enemy = _enemy(combatants)
    assert enemy["hp_current"] < 40
    assert "blinded" in [str(c.get("key")) for c in (enemy.get("conditions") or [])]
    assert _player(combatants).get("dirty_blow_used_combat") is True
    assert current == "korsarz"


def test_dirty_blow_zone_gate_blocks_ranged(tmp_path, monkeypatch):
    db = _combat_db(tmp_path, enemy_zone="ranged")
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([12, 12]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_dirty_blow(1)
    assert out["ok"] is False and out["block_reason"] == "out_of_range"
    _, current = _combatants(db)
    assert current == "player"  # tura nie skonsumowana


def test_dirty_blow_requires_zabijaka(tmp_path, monkeypatch):
    db = _combat_db(tmp_path, race="dwarf")
    monkeypatch.setattr(combat_service, "roll_d20", _seq_d20([12, 12]))
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        with pytest.raises(ValueError, match="not_zabijaka"):
            combat_service.resolve_dirty_blow(1)
