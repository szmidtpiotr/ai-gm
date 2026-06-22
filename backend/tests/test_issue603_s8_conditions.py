"""TDD: Issue #603 — FAZA S / S8: batch kondycji + prymityw `dot` + APPLY_CONDITION.

Pokrywa:
- nowy, schema-zgodny typ efektu `dot` (damage-over-time) waliduje się U10,
- 7 kondycji S8 (on_fire/frozen/confused/insane/panicked/charmed/cursed) waliduje się,
- prymityw stat: `effects[static_stat_modifier]` faktycznie modyfikuje staty w silniku
  (dotąd silnik czytał TYLKO legacy `stat_mods`; seedy schema-zgodne były martwe),
- runtime `dot` tyka co turę w walce (on_fire → 2d6 obrażeń + event condition_damage),
- `apply_condition_to_combatant` dokleja effect_json z katalogu (tag staje się mechaniczny)
  i odrzuca nieznany klucz jako `invalid_reference`.
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


# ─── effect_json kontraktów S8 (identyczne z seedami w migrations_admin.py) ──────

def _ej(*effects: dict) -> dict:
    return {
        "schema_version": 1,
        "effect_category": "character_condition",
        "effects": list(effects),
    }


ON_FIRE = _ej(
    {"type": "dot", "value": "2d6", "damage_type": "fire", "tick": "start_turn"},
    {"type": "static_stat_modifier", "stat": "STR", "value": -2},
    {"type": "static_stat_modifier", "stat": "DEX", "value": -2},
    {"type": "periodic_save", "stat": "DEX", "value": 12, "tick": "start_turn", "expires": "save_success"},
)
FROZEN = _ej(
    {"type": "static_stat_modifier", "stat": "DEX", "value": -4},
    {"type": "periodic_save", "stat": "CON", "value": 14, "tick": "start_turn", "expires": "save_success"},
)
CONFUSED = _ej(
    {"type": "static_stat_modifier", "stat": "INT", "value": -3},
    {"type": "static_stat_modifier", "stat": "WIS", "value": -3},
    {"type": "periodic_save", "stat": "WIS", "value": 14, "tick": "start_turn", "expires": "save_success"},
)
INSANE = _ej({"type": "static_stat_modifier", "stat": "CHA", "value": -5})
PANICKED = _ej(
    {"type": "static_stat_modifier", "stat": "CHA", "value": -4},
    {"type": "static_stat_modifier", "stat": "WIS", "value": -4},
)
CHARMED = _ej(
    {"type": "static_stat_modifier", "stat": "WIS", "value": -3},
    {"type": "periodic_save", "stat": "WIS", "value": 16, "tick": "start_turn", "expires": "save_success"},
)
CURSED = _ej(*[
    {"type": "static_stat_modifier", "stat": s, "value": -2}
    for s in ("STR", "DEX", "CON", "INT", "WIS", "CHA")
])

ALL_SEEDS = {
    "on_fire": ON_FIRE, "frozen": FROZEN, "confused": CONFUSED, "insane": INSANE,
    "panicked": PANICKED, "charmed": CHARMED, "cursed": CURSED,
}


# ─── 1. Schemat U10 akceptuje `dot` i wszystkie 7 seedów ───────────────────────

class TestDotSchema:
    def test_dot_effect_validates(self):
        errs = validate_effect_json_payload(ON_FIRE)
        assert errs == [], f"on_fire (z dot) powinien być valid, błędy: {errs}"

    def test_dot_numeric_value_validates(self):
        payload = _ej({"type": "dot", "value": 7, "tick": "each_round"})
        assert validate_effect_json_payload(payload) == []

    def test_dot_requires_tick(self):
        payload = _ej({"type": "dot", "value": "2d6"})
        assert any("tick" in e for e in validate_effect_json_payload(payload))

    def test_dot_bad_dice_rejected(self):
        payload = _ej({"type": "dot", "value": "kupa", "tick": "start_turn"})
        assert validate_effect_json_payload(payload) != []

    @pytest.mark.parametrize("key", list(ALL_SEEDS.keys()))
    def test_all_seven_seeds_validate(self, key):
        errs = validate_effect_json_payload(ALL_SEEDS[key])
        assert errs == [], f"seed {key} niezgodny ze schematem U10: {errs}"


# ─── 2. Prymityw: effects[static_stat_modifier] folduje się do modyfikatora ─────

def _cond(effect_json: dict) -> dict:
    return {"key": "x", "label": "X", "effect_json": json.dumps(effect_json)}


def _sheet(stats: dict, conditions: list[dict]) -> dict:
    return {"stats": stats, "current_hp": 30, "max_hp": 30, "conditions": conditions}


class TestStaticStatModifierPrimitive:
    def test_schema_static_stat_modifier_applies(self):
        """frozen: DEX 12 (base +1) − 4 = −3 — przez effects[], nie stat_mods."""
        sheet = _sheet({"DEX": 12}, [_cond(FROZEN)])
        assert cs._combatant_stat_modifier({}, sheet=sheet, stat="DEX") == -3

    def test_cursed_multi_stat_via_effects(self):
        sheet = _sheet({"STR": 14, "WIS": 10}, [_cond(CURSED)])
        assert cs._combatant_stat_modifier({}, sheet=sheet, stat="STR") == 0   # +2 −2
        assert cs._combatant_stat_modifier({}, sheet=sheet, stat="WIS") == -2  # 0 −2

    def test_enemy_effects_static_stat_modifier(self):
        enemy = {"stats": {"DEX": 14}, "conditions": [_cond(FROZEN)]}
        assert cs._combatant_stat_modifier(enemy, sheet=None, stat="DEX") == -2  # +2 −4

    # ── backward compat: legacy flat stat_mods nadal działa (t29) ──
    def test_legacy_stat_mods_still_applies(self):
        sheet = _sheet({"STR": 14}, [_cond({"stat_mods": {"STR": -2}})])
        assert cs._combatant_stat_modifier({}, sheet=sheet, stat="STR") == 0

    def test_unaffected_stat_unchanged(self):
        sheet = _sheet({"STR": 14, "DEX": 12}, [_cond(FROZEN)])
        assert cs._combatant_stat_modifier({}, sheet=sheet, stat="STR") == 2  # STR nietknięty


# ─── 3 + 4. Integracja w walce: dot tyka, apply_condition dokleja effect_json ──

def _schema_sql() -> str:
    sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 18, "CHA": 10},
        "current_hp": 30, "max_hp": 30, "defense": {"base": 15},
        "equipped_weapon": "sword", "conditions": [],
    }
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    on_fire = json.dumps(ON_FIRE, ensure_ascii=False).replace("'", "''")
    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'S8','fantasy','m',1);
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
    INSERT INTO game_config_conditions (key,label,effect_json,description,is_active)
      VALUES ('on_fire','Podpalony','{on_fire}','Płonie.',1);
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
def s8_db(tmp_path):
    db = tmp_path / "s8.db"
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


class TestDotRuntime:
    @patch("app.services.combat_service.roll_d20")
    def test_on_fire_dot_ticks_each_turn(self, mock_r20, s8_db):
        # save zawsze nieudany (raw 2) → ogień nie gaśnie, dot tyka
        mock_r20.return_value = 2
        cs.initiate_combat(1, 1, ["bandit"])
        # nałóż on_fire na gracza bezpośrednio (ścieżka tag dokleja effect_json w innym teście)
        snap = cs.get_active_combat(1)
        player = _player(snap)
        player["conditions"] = [{"key": "on_fire", "label": "Podpalony",
                                 "effect_json": json.dumps(ON_FIRE), "runtime": {}}]
        with sqlite3.connect(str(s8_db)) as c:
            c.execute("UPDATE active_combat SET combatants=? WHERE campaign_id=1",
                      (json.dumps(snap["combatants"], ensure_ascii=False),))
            c.commit()

        out = cs.evaluate_current_turn_conditions(1)
        dmg_events = [e for e in out["events"] if e["type"] == "condition_damage"]
        assert dmg_events, f"brak obrażeń dot; events={out['events']}"
        dmg = dmg_events[0]["damage"]
        assert 2 <= dmg <= 12, f"2d6 poza zakresem: {dmg}"
        assert dmg_events[0]["damage_type"] == "fire"

        snap2 = cs.get_active_combat(1)
        assert _player(snap2)["hp_current"] == 30 - dmg


class TestApplyConditionCatalog:
    def test_apply_condition_attaches_effect_json(self, s8_db):
        cs.initiate_combat(1, 1, ["bandit"])
        res = cs.apply_condition_to_combatant(1, "bandit", "on_fire")
        assert res["ok"] is True
        snap = cs.get_active_combat(1)
        bandit = next(c for c in snap["combatants"] if c.get("enemy_key") == "bandit")
        cond = next(c for c in bandit["conditions"] if c["key"] == "on_fire")
        assert cond.get("effect_json"), "tag-applied kondycja musi nieść effect_json z katalogu"
        parsed = json.loads(cond["effect_json"])
        assert any(e["type"] == "dot" for e in parsed["effects"])

    def test_apply_condition_unknown_key_invalid_reference(self, s8_db):
        cs.initiate_combat(1, 1, ["bandit"])
        res = cs.apply_condition_to_combatant(1, "bandit", "nieistniejaca_kondycja")
        assert res["ok"] is False
        assert res["reason"] == "invalid_reference"
