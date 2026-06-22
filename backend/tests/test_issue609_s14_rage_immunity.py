"""TDD: Issue #609 — FAZA S / S14: prymityw `condition_immunity` + klucz `broken_by` + kondycja `rage`.

Pokrywa:
- nowy, schema-zgodny typ efektu `condition_immunity` (pole `immune_to` = niepusta lista kluczy)
  i nowy top-level klucz `broken_by` (lista kluczy kondycji) walidują się U10; seed `rage` waliduje się,
- walidacja: condition_immunity wymaga niepustej listy `immune_to`; `broken_by` musi być listą stringów,
- IMMUNITY (blok): aktor z aktywną kondycją niosącą condition_immunity NIE przyjmuje kondycji z `immune_to`
  (np. rage + slowed → odrzucone; rage czyta immune_to[slowed,weakened]),
- IMMUNITY (czyszczenie): nałożenie kondycji z immune_to zdejmuje już aktywne kondycje z tej listy
  (np. założenie rage czyści aktywne slowed),
- BROKEN_BY: nałożenie kondycji wymienionej w `broken_by` nosiciela zdejmuje nosiciela
  (np. nałożenie stunned/confused zdejmuje rage),
- prymityw aktor-agnostyczny: immunitet działa też na wrogu (apply_condition_to_combatant),
- on_expire_apply: po wygaśnięciu rage (duration_rounds→0) aktor dostaje exhausted poziom 1, rage znika,
- backward compat: bez rage slowed nakłada się normalnie (brak immunitetu).

Rzuty ataku w walce (nat 20/nat 1, podwójne obrażenia) NIETYKALNE — to zadanie nie dotyka rzutu ataku.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.services import combat_service as cs
from app.services.admin_config import validate_effect_json_payload


# ─── effect_json kontrakty (identyczne z seedem) ───────────────────────────────

RAGE = {
    "schema_version": 1,
    "effect_category": "character_condition",
    "effects": [
        {"type": "static_stat_modifier", "stat": "STR", "value": 2},
        {"type": "static_stat_modifier", "stat": "damage_bonus", "value": 3},
        {"type": "condition_immunity", "immune_to": ["slowed", "weakened"], "expires": "duration_rounds:6"},
        {"type": "on_expire_apply", "condition_key": "exhausted", "value": 1},
    ],
    "broken_by": ["stunned", "confused"],
}

SLOWED = {
    "schema_version": 1, "effect_category": "character_condition",
    "effects": [{"type": "static_stat_modifier", "stat": "DEX", "value": -2, "expires": "duration_rounds:2"}],
}
WEAKENED = {
    "schema_version": 1, "effect_category": "character_condition",
    "effects": [{"type": "static_stat_modifier", "stat": "STR", "value": -3, "expires": "duration_rounds:2"}],
}
STUNNED = {
    "schema_version": 1, "effect_category": "character_condition",
    "effects": [{"type": "block_action"}],
}
CONFUSED = {
    "schema_version": 1, "effect_category": "character_condition",
    "effects": [{"type": "static_stat_modifier", "stat": "WIS", "value": -3}],
}
EXHAUSTED = {
    "schema_version": 1, "effect_category": "character_condition",
    "effects": [{
        "type": "stacking_levels", "max_level": 2,
        "per_level_effects": [
            {"type": "static_stat_modifier", "stat": "STR", "value": -3},
            {"type": "static_stat_modifier", "stat": "DEX", "value": -3},
            {"type": "static_stat_modifier", "stat": "CON", "value": -3},
        ],
        "threshold_effects": {"2": {"type": "block_action"}},
    }],
}


# ─── 1. Schemat U10 akceptuje nowy typ + klucz + seed rage ─────────────────────

class TestSchema:
    def test_rage_validates(self):
        assert validate_effect_json_payload(RAGE) == []

    def test_condition_immunity_requires_nonempty_immune_to(self):
        bad = {
            "schema_version": 1, "effect_category": "character_condition",
            "effects": [{"type": "condition_immunity", "immune_to": []}],
        }
        assert validate_effect_json_payload(bad) != []

    def test_condition_immunity_missing_immune_to_rejected(self):
        bad = {
            "schema_version": 1, "effect_category": "character_condition",
            "effects": [{"type": "condition_immunity"}],
        }
        assert validate_effect_json_payload(bad) != []

    def test_condition_immunity_ok(self):
        ok = {
            "schema_version": 1, "effect_category": "character_condition",
            "effects": [{"type": "condition_immunity", "immune_to": ["slowed"]}],
        }
        assert validate_effect_json_payload(ok) == []

    def test_broken_by_must_be_list(self):
        bad = json.loads(json.dumps(RAGE))
        bad["broken_by"] = "stunned"
        assert validate_effect_json_payload(bad) != []


# ─── DB fixture (1v1) ──────────────────────────────────────────────────────────

def _schema_sql() -> str:
    sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
        "current_hp": 30, "max_hp": 30, "defense": {"base": 15},
        "equipped_weapon": "sword", "conditions": [],
    }
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")

    def j(d):
        return json.dumps(d, ensure_ascii=False).replace("'", "''")

    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'S14','fantasy','m',1);
    CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
      name TEXT, system_id TEXT, sheet_json TEXT);
    INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
      VALUES (1,1,1,'Aldric','fantasy','{sj}');
    {table_sql("game_config_weapons")}
    INSERT INTO game_config_weapons (key,label,damage_die,linked_stat,allowed_classes)
      VALUES ('sword','Sword','1d8','STR','warrior');
    {table_sql("game_config_enemies")}
    INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,dex_modifier,damage_die,drop_chance,skills_json)
      VALUES ('bandit','Bandit',40,13,3,1,'1d8',0.0,'{{}}');
    {table_sql("game_config_conditions")}
    INSERT INTO game_config_conditions (key,label,effect_json,description,is_active,stackable)
      VALUES ('rage','Furia','{j(RAGE)}','Furia kontrolowana.',1,0),
             ('slowed','Spowolniony','{j(SLOWED)}','Spowolnienie.',1,0),
             ('weakened','Osłabiony','{j(WEAKENED)}','Osłabienie.',1,0),
             ('stunned','Ogłuszony','{j(STUNNED)}','Ogłuszenie.',1,0),
             ('confused','Zdezorientowany','{j(CONFUSED)}','Dezorientacja.',1,0),
             ('exhausted','Wyczerpany','{j(EXHAUSTED)}','Wyczerpanie.',1,1);
    CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
      character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
      combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
      loot_pool TEXT, created_at TEXT, updated_at TEXT);
    CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
      turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
      target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
      created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
    """


@pytest.fixture
def s14_db(tmp_path):
    db = tmp_path / "s14.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(_schema_sql())
        conn.commit()
    finally:
        conn.close()
    with patch.object(cs, "COMBAT_DB_PATH", str(db)):
        yield db


def _player(snap):
    return next(c for c in snap["combatants"] if c["id"] == "player")


def _enemy(snap):
    return next(c for c in snap["combatants"] if c.get("type") != "player")


def _cond(key, effect_json, duration_rounds=None):
    c = {"key": key, "label": key.title(), "effect_json": json.dumps(effect_json), "runtime": {}}
    if duration_rounds is not None:
        c["duration_rounds"] = int(duration_rounds)
    return c


def _force_player_turn(db, conditions, *, round_n=1):
    snap = cs.get_active_combat(1)
    player = _player(snap)
    player["conditions"] = conditions
    with sqlite3.connect(str(db)) as c:
        c.execute(
            "UPDATE active_combat SET combatants=?, current_turn='player', round=? WHERE campaign_id=1",
            (json.dumps(snap["combatants"], ensure_ascii=False), int(round_n)),
        )
        c.commit()


# ─── 2. IMMUNITY — blok nakładania ────────────────────────────────────────────

class TestImmunityBlock:
    def test_rage_blocks_slowed_on_player(self, s14_db):
        cs.initiate_combat(1, 1, ["bandit"])
        assert cs.apply_condition_to_player(1, "rage")["ok"] is True
        res = cs.apply_condition_to_player(1, "slowed")
        assert res["reason"] == "immune"
        snap = cs.get_active_combat(1)
        keys = {c["key"] for c in _player(snap)["conditions"]}
        assert "slowed" not in keys, "slowed nie powinien wejść na gracza z rage (immune_to)"
        assert "rage" in keys

    def test_rage_blocks_weakened_on_player(self, s14_db):
        cs.initiate_combat(1, 1, ["bandit"])
        cs.apply_condition_to_player(1, "rage")
        res = cs.apply_condition_to_player(1, "weakened")
        assert res["reason"] == "immune"
        snap = cs.get_active_combat(1)
        assert "weakened" not in {c["key"] for c in _player(snap)["conditions"]}

    def test_immunity_generic_on_enemy(self, s14_db):
        """Prymityw aktor-agnostyczny: immunitet działa też przez apply_condition_to_combatant."""
        cs.initiate_combat(1, 1, ["bandit"])
        assert cs.apply_condition_to_combatant(1, "bandit", "rage")["ok"] is True
        res = cs.apply_condition_to_combatant(1, "bandit", "slowed")
        assert res["reason"] == "immune"
        snap = cs.get_active_combat(1)
        assert "slowed" not in {c["key"] for c in _enemy(snap)["conditions"]}


# ─── 3. IMMUNITY — czyszczenie aktywnych kondycji z immune_to ──────────────────

class TestImmunityCleanup:
    def test_rage_clears_existing_slowed(self, s14_db):
        cs.initiate_combat(1, 1, ["bandit"])
        cs.apply_condition_to_player(1, "slowed")     # najpierw slowed
        snap = cs.get_active_combat(1)
        assert "slowed" in {c["key"] for c in _player(snap)["conditions"]}
        cs.apply_condition_to_player(1, "rage")        # rage czyści slowed
        snap = cs.get_active_combat(1)
        keys = {c["key"] for c in _player(snap)["conditions"]}
        assert "slowed" not in keys, "założenie rage powinno zdjąć aktywne slowed (immune_to)"
        assert "rage" in keys


# ─── 4. BROKEN_BY — nałożenie kondycji przerywa nosiciela ──────────────────────

class TestBrokenBy:
    def test_stunned_removes_rage(self, s14_db):
        cs.initiate_combat(1, 1, ["bandit"])
        cs.apply_condition_to_player(1, "rage")
        res = cs.apply_condition_to_player(1, "stunned")
        assert res["ok"] is True
        snap = cs.get_active_combat(1)
        keys = {c["key"] for c in _player(snap)["conditions"]}
        assert "rage" not in keys, "nałożenie stunned powinno zdjąć rage (broken_by)"
        assert "stunned" in keys

    def test_confused_removes_rage(self, s14_db):
        cs.initiate_combat(1, 1, ["bandit"])
        cs.apply_condition_to_player(1, "rage")
        cs.apply_condition_to_player(1, "confused")
        snap = cs.get_active_combat(1)
        assert "rage" not in {c["key"] for c in _player(snap)["conditions"]}


# ─── 5. on_expire_apply — rage → exhausted po wygaśnięciu ──────────────────────

class TestExpiry:
    def test_rage_expiry_applies_exhausted(self, s14_db):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_player_turn(s14_db, [_cond("rage", RAGE, duration_rounds=1)])
        out = cs.evaluate_current_turn_conditions(1)
        assert "condition_removed" in {str(e.get("type")) for e in out["events"]}
        snap = cs.get_active_combat(1)
        conds = {c["key"]: c for c in _player(snap)["conditions"]}
        assert "rage" not in conds, "rage powinien zniknąć po wygaśnięciu"
        assert "exhausted" in conds, "on_expire_apply powinien nałożyć exhausted"
        assert cs._condition_level(conds["exhausted"]) == 1


# ─── 6. Backward compat — bez rage slowed nakłada się normalnie ────────────────

class TestBackwardCompat:
    def test_slowed_applies_without_rage(self, s14_db):
        cs.initiate_combat(1, 1, ["bandit"])
        res = cs.apply_condition_to_player(1, "slowed")
        assert res["ok"] is True
        snap = cs.get_active_combat(1)
        assert "slowed" in {c["key"] for c in _player(snap)["conditions"]}
