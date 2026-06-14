"""TDD: Issue #604 — FAZA S / S9: prymityw `stacking_levels` + kondycja `exhausted`.

Pokrywa:
- nowy, schema-zgodny typ efektu `stacking_levels` (max_level / per_level_effects /
  threshold_effects) waliduje się U10; seed `exhausted` waliduje się,
- `_combatant_stat_modifier` skaluje kary `per_level_effects` ×poziom (level 1 = −3,
  level 2 = −6); brak runtime → poziom 1,
- threshold_effects: poziom ≥ 2 → block_action w T24 (omdlenie), poziom 1 → brak blokady,
- `apply_condition_to_combatant`: ponowne nałożenie kondycji stackable podbija `runtime.level`
  (klamp do max_level) zamiast duplikować wiersz na liście conditions,
- zdejmowanie poziomami: short rest = −1 poziom (usuwa przy 0), long rest = wszystkie.
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


# ─── effect_json kontrakt exhausted (identyczny z seedem) ──────────────────────

EXHAUSTED = {
    "schema_version": 1,
    "effect_category": "character_condition",
    "effects": [
        {
            "type": "stacking_levels",
            "max_level": 2,
            "per_level_effects": [
                {"type": "static_stat_modifier", "stat": "STR", "value": -3},
                {"type": "static_stat_modifier", "stat": "DEX", "value": -3},
                {"type": "static_stat_modifier", "stat": "CON", "value": -3},
            ],
            "threshold_effects": {"2": {"type": "block_action"}},
        }
    ],
}


def _exh(level: int = 1) -> dict:
    return {
        "key": "exhausted",
        "label": "Wyczerpany",
        "effect_json": json.dumps(EXHAUSTED),
        "runtime": {"level": level},
    }


def _sheet(stats: dict, conditions: list[dict]) -> dict:
    return {"stats": stats, "current_hp": 30, "max_hp": 30, "conditions": conditions}


# ─── 1. Schemat U10 akceptuje stacking_levels + seed exhausted ──────────────────

class TestStackingSchema:
    def test_exhausted_validates(self):
        assert validate_effect_json_payload(EXHAUSTED) == []

    def test_max_level_required_positive(self):
        bad = json.loads(json.dumps(EXHAUSTED))
        bad["effects"][0]["max_level"] = 0
        assert validate_effect_json_payload(bad) != []

    def test_per_level_effects_required(self):
        bad = {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [{"type": "stacking_levels", "max_level": 2, "per_level_effects": []}],
        }
        assert validate_effect_json_payload(bad) != []

    def test_threshold_effects_optional(self):
        ok = {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [{
                "type": "stacking_levels", "max_level": 3,
                "per_level_effects": [{"type": "static_stat_modifier", "stat": "STR", "value": -1}],
            }],
        }
        assert validate_effect_json_payload(ok) == []

    def test_bad_sub_effect_rejected(self):
        bad = json.loads(json.dumps(EXHAUSTED))
        # per_level_effect bez stat → static_stat_modifier niepoprawny
        bad["effects"][0]["per_level_effects"] = [{"type": "static_stat_modifier", "value": -3}]
        assert validate_effect_json_payload(bad) != []


# ─── 2. _combatant_stat_modifier skaluje per_level_effects ×poziom ─────────────

class TestPerLevelScaling:
    def test_level_1_single_penalty(self):
        sheet = _sheet({"STR": 10}, [_exh(level=1)])
        assert cs._combatant_stat_modifier({}, sheet=sheet, stat="STR") == -3

    def test_level_2_double_penalty(self):
        sheet = _sheet({"STR": 10}, [_exh(level=2)])
        assert cs._combatant_stat_modifier({}, sheet=sheet, stat="STR") == -6

    def test_missing_runtime_treated_as_level_1(self):
        cond = {"key": "exhausted", "label": "X", "effect_json": json.dumps(EXHAUSTED)}
        sheet = _sheet({"DEX": 10}, [cond])
        assert cs._combatant_stat_modifier({}, sheet=sheet, stat="DEX") == -3

    def test_unaffected_stat_unchanged(self):
        sheet = _sheet({"STR": 10, "INT": 14}, [_exh(level=2)])
        assert cs._combatant_stat_modifier({}, sheet=sheet, stat="INT") == 2  # INT nietknięty

    def test_enemy_combatant_path(self):
        enemy = {"stats": {"CON": 12}, "conditions": [_exh(level=2)]}
        assert cs._combatant_stat_modifier(enemy, sheet=None, stat="CON") == -5  # +1 −6


# ─── 3. Rest hooks: zdejmowanie poziomami ──────────────────────────────────────

class TestRestRemoval:
    def test_short_rest_decrements_one_level(self):
        new, changed = cs.reduce_stacking_conditions([_exh(level=2)], remove_all=False)
        assert changed is True
        assert len(new) == 1
        assert cs._condition_level(new[0]) == 1

    def test_short_rest_removes_at_zero(self):
        new, changed = cs.reduce_stacking_conditions([_exh(level=1)], remove_all=False)
        assert changed is True
        assert new == []

    def test_long_rest_removes_all(self):
        new, changed = cs.reduce_stacking_conditions([_exh(level=2)], remove_all=True)
        assert changed is True
        assert new == []

    def test_non_stacking_condition_untouched(self):
        other = {"key": "blinded", "label": "X",
                 "effect_json": json.dumps({"schema_version": 1, "effect_category": "character_condition",
                                            "effects": [{"type": "block_action"}]})}
        new, changed = cs.reduce_stacking_conditions([other], remove_all=True)
        assert changed is False
        assert new == [other]


# ─── 4. Integracja w walce: bump level + threshold block_action ────────────────

def _schema_sql() -> str:
    sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 18, "CHA": 10},
        "current_hp": 30, "max_hp": 30, "defense": {"base": 15},
        "equipped_weapon": "sword", "conditions": [],
    }
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    exh = json.dumps(EXHAUSTED, ensure_ascii=False).replace("'", "''")
    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'S9','fantasy','m',1);
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
      VALUES ('exhausted','Wyczerpany','{exh}','Wyczerpanie.',1,1);
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
def s9_db(tmp_path):
    db = tmp_path / "s9.db"
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


def _bandit(snap):
    return next(c for c in snap["combatants"] if c.get("enemy_key") == "bandit")


class TestApplyConditionBumpsLevel:
    def test_reapply_stackable_bumps_level_no_duplicate(self, s9_db):
        cs.initiate_combat(1, 1, ["bandit"])
        r1 = cs.apply_condition_to_combatant(1, "bandit", "exhausted")
        assert r1["ok"] is True
        r2 = cs.apply_condition_to_combatant(1, "bandit", "exhausted")
        assert r2["ok"] is True
        snap = cs.get_active_combat(1)
        bandit = _bandit(snap)
        exh = [c for c in bandit["conditions"] if c["key"] == "exhausted"]
        assert len(exh) == 1, "stackable nie może duplikować wiersza"
        assert cs._condition_level(exh[0]) == 2

    def test_clamp_to_max_level(self, s9_db):
        cs.initiate_combat(1, 1, ["bandit"])
        for _ in range(4):
            cs.apply_condition_to_combatant(1, "bandit", "exhausted")
        snap = cs.get_active_combat(1)
        exh = [c for c in _bandit(snap)["conditions"] if c["key"] == "exhausted"]
        assert len(exh) == 1
        assert cs._condition_level(exh[0]) == 2  # max_level


class TestThresholdBlockAction:
    def _set_player_exhausted(self, db, level):
        snap = cs.get_active_combat(1)
        player = _player(snap)
        player["conditions"] = [_exh(level=level)]
        with sqlite3.connect(str(db)) as c:
            c.execute("UPDATE active_combat SET combatants=?, current_turn='player' WHERE campaign_id=1",
                      (json.dumps(snap["combatants"], ensure_ascii=False),))
            c.commit()

    def test_level_2_blocks_action(self, s9_db):
        cs.initiate_combat(1, 1, ["bandit"])
        self._set_player_exhausted(s9_db, level=2)
        out = cs.evaluate_current_turn_conditions(1)
        assert out["blocked"] is True
        assert any(e["type"] == "block_action" for e in out["events"])

    def test_level_1_does_not_block(self, s9_db):
        cs.initiate_combat(1, 1, ["bandit"])
        self._set_player_exhausted(s9_db, level=1)
        out = cs.evaluate_current_turn_conditions(1)
        assert out["blocked"] is False
