"""TDD: Issue #608 — S13: prymityw `on_zero_hp_save` + kondycja `blessed`.

Prymityw raz, kondycja danymi (Zasada 1 FAZY S): silnik NIE zna `blessed` z nazwy —
czyta efekt `on_zero_hp_save` z effect_json kondycji. Gdy obrażenia sprowadziłyby HP
gracza do ≤0, a aktor ma aktywny `on_zero_hp_save` z pozostałym budżetem `uses`,
MECHANIKA rzuca d20+stat_mod vs DC i przy sukcesie zostawia 1 HP zamiast nieprzytomności.

Rzuty ataku w walce (nat 20/nat 1, podwójne obrażenia) NIETYKALNE — hook tylko w momencie HP≤0.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import combat_service
from app.services.admin_config import validate_effect_json_payload

# effect_json kondycji `blessed` (jak seed S13): +2 defensywny (stat="save") + on_zero_hp_save CON DC 12.
BLESSED_EFFECT_JSON = {
    "schema_version": 1,
    "effect_category": "character_condition",
    "effects": [
        {"type": "static_stat_modifier", "stat": "save", "value": 2},
        {"type": "on_zero_hp_save", "stat": "CON", "value": 12, "result": "stay_at_1hp", "uses": 1},
    ],
}


def _blessed_combatant():
    """Combatant gracza z kondycją blessed (CON 10 → mod 0; o sukcesie decyduje rzut + save +2)."""
    return {
        "type": "player",
        "name": "Bohater",
        "hp_current": 8,
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10},
        "conditions": [
            {"key": "blessed", "label": "Pobłogosławiony",
             "effect_json": json.dumps(BLESSED_EFFECT_JSON, ensure_ascii=False), "runtime": {}},
        ],
    }


# ─── Test główny — prymityw on_zero_hp_save ───────────────────────────────────

def test_on_zero_hp_save_keeps_at_1hp_on_success(monkeypatch):
    """Wysoki rzut → udany save CON: helper zwraca saved=True, hp=1 (zamiast nieprzytomności)."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 18)
    c = _blessed_combatant()
    res = combat_service._on_zero_hp_save(c, sheet=None)
    assert res is not None
    assert res["saved"] is True
    assert res["hp"] == 1
    assert res["condition_key"] == "blessed"
    # rzut 18 + CON mod 0 + save +2 = 20 ≥ DC 12
    assert res["total"] == 20
    assert res["dc"] == 12


def test_on_zero_hp_save_consumes_use(monkeypatch):
    """Budżet uses=1: pierwszy save działa, drugi (już zużyty) nie ratuje (None)."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 18)
    c = _blessed_combatant()
    first = combat_service._on_zero_hp_save(c, sheet=None)
    assert first and first["saved"] is True
    second = combat_service._on_zero_hp_save(c, sheet=None)
    assert second is None, "drugi cios w tej samej scenie nie ma już budżetu — brak ratunku"


def test_on_zero_hp_save_failed_roll_no_save(monkeypatch):
    """Niski rzut → save nieudany: saved=False, brak hp (nieprzytomność)."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 2)
    c = _blessed_combatant()
    res = combat_service._on_zero_hp_save(c, sheet=None)
    assert res is not None
    assert res["saved"] is False
    assert res.get("hp") in (None, 0)


def test_no_blessed_no_save():
    """Brak kondycji z on_zero_hp_save → helper zwraca None (silnik idzie normalną ścieżką)."""
    plain = {"type": "player", "name": "Bohater", "hp_current": 5,
             "stats": {"CON": 12}, "conditions": []}
    assert combat_service._on_zero_hp_save(plain, sheet=None) is None


# ─── +2 defensywny (fold w _combatant_stat_modifier) ──────────────────────────

def test_defensive_save_bonus_folds():
    """Blessed daje +2 do testów obronnych przez derived stat 'save' (data-driven, nie if-key)."""
    c = _blessed_combatant()
    assert combat_service._combatant_stat_modifier(c, sheet=None, stat="save") == 2


def test_no_blessed_no_save_bonus():
    """Bez blessed derived 'save' = 0 (backward compat — nikt inny nie dostaje bonusu)."""
    plain = {"type": "player", "stats": {"CON": 12}, "conditions": []}
    assert combat_service._combatant_stat_modifier(plain, sheet=None, stat="save") == 0


# ─── Zgodność z U10 (effect schema lockdown) ──────────────────────────────────

def test_blessed_effect_json_validates_against_u10():
    """Seed blessed waliduje się wobec schematu U10 (nowy typ on_zero_hp_save + derived save)."""
    assert validate_effect_json_payload(BLESSED_EFFECT_JSON) == []


def test_on_zero_hp_save_requires_stat_and_dc():
    """Walidator odrzuca on_zero_hp_save bez statu / bez DC (kontrakt typu)."""
    bad = {"schema_version": 1, "effect_category": "character_condition",
           "effects": [{"type": "on_zero_hp_save", "result": "stay_at_1hp"}]}
    errs = validate_effect_json_payload(bad)
    assert any("on_zero_hp_save" in e for e in errs)


def test_on_zero_hp_save_rejects_unknown_result():
    """result musi być z enuma (stay_at_1hp) — inny → błąd walidacji."""
    bad = {"schema_version": 1, "effect_category": "character_condition",
           "effects": [{"type": "on_zero_hp_save", "stat": "CON", "value": 12, "result": "full_heal"}]}
    errs = validate_effect_json_payload(bad)
    assert any("result" in e for e in errs)


# ─── Backward compat — istniejące seedy S8 nadal walidują ─────────────────────

def test_on_fire_seed_still_validates():
    """Stara kondycja on_fire (S8) nie zepsuta zmianą schematu."""
    on_fire = {
        "schema_version": 1, "effect_category": "character_condition",
        "effects": [
            {"type": "dot", "value": "2d6", "damage_type": "fire", "tick": "start_turn"},
            {"type": "periodic_save", "stat": "DEX", "value": 12, "tick": "start_turn", "expires": "save_success"},
        ],
    }
    assert validate_effect_json_payload(on_fire) == []


# ─── Integracja z prawdziwym silnikiem walki (resolve_attack — ścieżka HP≤0) ───

import sqlite3
from unittest.mock import patch


def _combat_db(tmp_path, *, player_conditions):
    db = tmp_path / "blessed.db"
    blessed = json.dumps(BLESSED_EFFECT_JSON, ensure_ascii=False)
    player = {
        "id": "player", "type": "player", "name": "Aldric",
        "hp_current": 5, "hp_max": 30, "defense": 10, "zone": "engaged",
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "conditions": player_conditions,
    }
    enemy = {
        "id": "bandit", "type": "enemy", "enemy_key": "bandit", "name": "Bandit",
        "hp_current": 40, "hp_max": 40, "attack_bonus": 10, "damage_dice": "1d8", "zone": "engaged",
    }
    sheet = {"stats": player["stats"], "current_hp": 5, "max_hp": 30, "defense": {"base": 10}, "conditions": []}
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'S13');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Aldric','fantasy','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'["bandit","player"]','bandit','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def _blessed_cond():
    return [{"key": "blessed", "label": "Pobłogosławiony",
             "effect_json": json.dumps(BLESSED_EFFECT_JSON, ensure_ascii=False), "runtime": {}}]


def test_resolve_attack_blessed_survives_lethal_blow(tmp_path, monkeypatch):
    """Realny silnik: śmiertelny cios + blessed → gracz przeżywa na 1 HP, nie nieprzytomny."""
    db = _combat_db(tmp_path, player_conditions=_blessed_cond())
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 20)  # wróg trafia + save (CON) zdany
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 999)  # cios zabójczy
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out.get("on_zero_hp_save", {}).get("saved") is True
    assert out["player_hp_remaining"] == 1
    assert out["player_incapacitated"] is False


def test_resolve_attack_second_lethal_blow_no_budget_incapacitates(tmp_path, monkeypatch):
    """Drugi śmiertelny cios w tej samej scenie (budżet uses=1 wyczerpany) → nieprzytomność."""
    db = _combat_db(tmp_path, player_conditions=_blessed_cond())
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 20)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 999)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        first = combat_service.resolve_attack(1, 0, attacker="enemy")
        assert first["player_hp_remaining"] == 1
        second = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert second.get("on_zero_hp_save") is None
    assert second["player_incapacitated"] is True


def test_resolve_attack_no_blessed_incapacitates(tmp_path, monkeypatch):
    """Backward compat: bez blessed śmiertelny cios powala gracza (ścieżka bez zmian)."""
    db = _combat_db(tmp_path, player_conditions=[])
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 20)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 999)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out.get("on_zero_hp_save") is None
    assert out["player_incapacitated"] is True
