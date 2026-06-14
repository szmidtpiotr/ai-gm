"""TDD: Issue #607 — FAZA S / S12: prymitywy `extra_action` + `on_expire_apply` + kondycja `hasted`.

Pokrywa:
- nowe, schema-zgodne typy efektu `extra_action` (action_kind=move_only) i `on_expire_apply`
  (condition_key + value=poziom) walidują się U10; seed `hasted` waliduje się,
- walidacja: extra_action wymaga poprawnego action_kind; on_expire_apply wymaga condition_key,
- `change_player_zone`: gracz z aktywną, niewykorzystaną `extra_action` zmienia strefę BEZ
  utraty tury (pierwszy raz w turze darmowy); druga zmiana w tej samej turze zużywa turę,
- brak `hasted` → zmiana strefy zużywa turę jak dotąd (backward compat),
- `evaluate_current_turn_conditions`: po wygaśnięciu `hasted` (duration_rounds→0) aktor
  dostaje `exhausted` poziom 1 (on_expire_apply), a `hasted` znika,
- `apply_condition_to_player`: nakłada kondycję na combatanta gracza z czasem trwania
  z effect.expires (duration_rounds) i runtime.level.

Rzuty ataku w walce (nat 20/nat 1) NIETYKALNE — to zadanie nie dotyka resolve_attack.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import combat_service as cs
from app.services.admin_config import validate_effect_json_payload


# ─── effect_json kontrakty (identyczne z seedem) ───────────────────────────────

HASTED = {
    "schema_version": 1,
    "effect_category": "character_condition",
    "effects": [
        {"type": "static_stat_modifier", "stat": "DEX", "value": 2},
        {"type": "extra_action", "action_kind": "move_only", "expires": "duration_rounds:3"},
        {"type": "on_expire_apply", "condition_key": "exhausted", "value": 1},
    ],
}

EXHAUSTED = {
    "schema_version": 1,
    "effect_category": "character_condition",
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


# ─── 1. Schemat U10 akceptuje nowe typy + seed hasted ──────────────────────────

class TestSchema:
    def test_hasted_validates(self):
        assert validate_effect_json_payload(HASTED) == []

    def test_extra_action_bad_action_kind_rejected(self):
        bad = json.loads(json.dumps(HASTED))
        bad["effects"][1]["action_kind"] = "full_attack"
        assert validate_effect_json_payload(bad) != []

    def test_extra_action_default_action_kind_ok(self):
        ok = {
            "schema_version": 1, "effect_category": "character_condition",
            "effects": [{"type": "extra_action"}],
        }
        assert validate_effect_json_payload(ok) == []

    def test_on_expire_apply_requires_condition_key(self):
        bad = {
            "schema_version": 1, "effect_category": "character_condition",
            "effects": [{"type": "on_expire_apply"}],
        }
        assert validate_effect_json_payload(bad) != []

    def test_on_expire_apply_ok(self):
        ok = {
            "schema_version": 1, "effect_category": "character_condition",
            "effects": [{"type": "on_expire_apply", "condition_key": "exhausted", "value": 1}],
        }
        assert validate_effect_json_payload(ok) == []


# ─── DB fixture (1v1) ──────────────────────────────────────────────────────────

def _schema_sql() -> str:
    sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
        "current_hp": 30, "max_hp": 30, "defense": {"base": 15},
        "equipped_weapon": "sword", "conditions": [],
    }
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    hasted = json.dumps(HASTED, ensure_ascii=False).replace("'", "''")
    exh = json.dumps(EXHAUSTED, ensure_ascii=False).replace("'", "''")
    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'S12','fantasy','m',1);
    CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
      name TEXT, system_id TEXT, sheet_json TEXT);
    INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
      VALUES (1,1,1,'Aldric','fantasy','{sj}');
    CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT, damage_die TEXT,
      linked_stat TEXT, allowed_classes TEXT DEFAULT 'warrior', is_active INTEGER DEFAULT 1);
    INSERT INTO game_config_weapons (key,label,damage_die,linked_stat,allowed_classes)
      VALUES ('sword','Sword','1d8','STR','warrior');
    CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT, hp_base INTEGER, ac_base INTEGER,
      attack_bonus INTEGER, dex_modifier INTEGER DEFAULT 0, damage_die TEXT, tier TEXT DEFAULT 'standard',
      xp_award INTEGER DEFAULT 0, description TEXT, is_active INTEGER DEFAULT 1,
      loot_table_key TEXT, drop_chance REAL DEFAULT 0.0, skills_json TEXT, stats_json TEXT);
    INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,dex_modifier,damage_die,drop_chance,skills_json)
      VALUES ('bandit','Bandit',40,13,3,1,'1d8',0.0,'{{}}');
    CREATE TABLE game_config_conditions (key TEXT PRIMARY KEY, label TEXT, effect_json TEXT,
      description TEXT, is_active INTEGER DEFAULT 1, stackable INTEGER NOT NULL DEFAULT 0);
    INSERT INTO game_config_conditions (key,label,effect_json,description,is_active,stackable)
      VALUES ('hasted','Przyśpieszony','{hasted}','Przyśpieszenie.',1,0),
             ('exhausted','Wyczerpany','{exh}','Wyczerpanie.',1,1);
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
def s12_db(tmp_path):
    db = tmp_path / "s12.db"
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


def _force_player_turn(db, conditions, *, zone="engaged", round_n=1):
    """Ustaw turę gracza + jego kondycje + strefę w aktywnej walce."""
    snap = cs.get_active_combat(1)
    player = _player(snap)
    player["conditions"] = conditions
    player["zone"] = zone
    with sqlite3.connect(str(db)) as c:
        c.execute(
            "UPDATE active_combat SET combatants=?, current_turn='player', round=? WHERE campaign_id=1",
            (json.dumps(snap["combatants"], ensure_ascii=False), int(round_n)),
        )
        c.commit()


def _hasted_cond(duration_rounds=None):
    cond = {"key": "hasted", "label": "Przyśpieszony", "effect_json": json.dumps(HASTED), "runtime": {}}
    if duration_rounds is not None:
        cond["duration_rounds"] = int(duration_rounds)
    return cond


# ─── 2. extra_action: darmowa zmiana strefy raz na turę ────────────────────────

class TestExtraAction:
    def test_hasted_zone_change_does_not_consume_turn(self, s12_db):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_player_turn(s12_db, [_hasted_cond()])
        res = cs.change_player_zone(1)
        assert res["ok"] is True
        # pierwsza zmiana = darmowa: nadal tura gracza
        snap = cs.get_active_combat(1)
        assert snap["current_turn"] == "player"

    def test_second_zone_change_same_turn_consumes(self, s12_db):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_player_turn(s12_db, [_hasted_cond()])
        cs.change_player_zone(1)            # darmowa
        cs.change_player_zone(1)            # ta zużywa turę
        snap = cs.get_active_combat(1)
        assert snap["current_turn"] != "player"

    def test_no_hasted_zone_change_consumes_turn(self, s12_db):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_player_turn(s12_db, [])      # brak hasted
        cs.change_player_zone(1)
        snap = cs.get_active_combat(1)
        assert snap["current_turn"] != "player"


# ─── 3. on_expire_apply: hasted → exhausted po wygaśnięciu ─────────────────────

class TestOnExpireApply:
    def test_hasted_expiry_applies_exhausted(self, s12_db):
        cs.initiate_combat(1, 1, ["bandit"])
        # duration_rounds=1 → ten przebieg evaluate zdejmie hasted
        _force_player_turn(s12_db, [_hasted_cond(duration_rounds=1)])
        out = cs.evaluate_current_turn_conditions(1)
        keys = {str(e.get("type")) for e in out["events"]}
        assert "condition_removed" in keys
        snap = cs.get_active_combat(1)
        conds = {c["key"]: c for c in _player(snap)["conditions"]}
        assert "hasted" not in conds, "hasted powinien zniknąć po wygaśnięciu"
        assert "exhausted" in conds, "on_expire_apply powinien nałożyć exhausted"
        assert cs._condition_level(conds["exhausted"]) == 1

    def test_hasted_not_expired_keeps_condition(self, s12_db):
        cs.initiate_combat(1, 1, ["bandit"])
        _force_player_turn(s12_db, [_hasted_cond(duration_rounds=3)])
        cs.evaluate_current_turn_conditions(1)
        snap = cs.get_active_combat(1)
        conds = {c["key"] for c in _player(snap)["conditions"]}
        assert "hasted" in conds
        assert "exhausted" not in conds


# ─── 4. apply_condition_to_player: nałożenie buffa na gracza ───────────────────

class TestApplyConditionToPlayer:
    def test_apply_hasted_sets_duration_from_expires(self, s12_db):
        cs.initiate_combat(1, 1, ["bandit"])
        res = cs.apply_condition_to_player(1, "hasted")
        assert res["ok"] is True
        snap = cs.get_active_combat(1)
        hasted = next(c for c in _player(snap)["conditions"] if c["key"] == "hasted")
        assert int(hasted["duration_rounds"]) == 3  # z effect.expires=duration_rounds:3

    def test_apply_unknown_condition_rejected(self, s12_db):
        cs.initiate_combat(1, 1, ["bandit"])
        res = cs.apply_condition_to_player(1, "nonexistent_xyz")
        assert res["ok"] is False
