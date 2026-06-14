"""TDD: Issue #605 — FAZA S / S10: prymityw `escalating_dot` + kondycja `hemorrhage`.

Pokrywa:
- nowy, schema-zgodny typ efektu `escalating_dot` (value start / escalate_every_rounds /
  escalate_dice) waliduje się U10; seed `hemorrhage` waliduje się,
- top-level `cure: {skill, dc}` w effect_json kondycji waliduje się; zły cure odrzucony,
- formuła eskalacji: poziom = ticks // escalate_every_rounds; obrażenia rosną po 3 i 6 rundach,
  stan (licznik ticks) przeżywa między rundami (effect_state),
- engine: `escalating_dot` tyka w T24 i zdejmuje HP (log condition_damage),
- deklaratywna ścieżka cure: `_match_curable_condition` dokleja (klucz, DC z katalogu) gdy
  gracz ma kondycję leczoną tym skillem; brak kondycji / inny skill → None,
- `remove_condition_from_character` zdejmuje kondycję z sheet (i aktywnego combatanta).
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
from app.services import skill_service as ss
from app.services.admin_config import validate_effect_json_payload


# ─── effect_json kontrakt hemorrhage (identyczny z seedem) ─────────────────────

HEMORRHAGE = {
    "schema_version": 1,
    "effect_category": "character_condition",
    "effects": [
        {
            "type": "escalating_dot",
            "value": "1d4",
            "escalate_every_rounds": 3,
            "escalate_dice": "1d4",
            "damage_type": "physical",
            "tick": "start_turn",
        }
    ],
    "cure": {"skill": "medicine", "dc": 16},
}


def _hem() -> dict:
    return {
        "key": "hemorrhage",
        "label": "Krwotok",
        "effect_json": json.dumps(HEMORRHAGE),
    }


# ─── 1. Schemat U10 akceptuje escalating_dot + cure; seed hemorrhage ───────────

class TestEscalatingDotSchema:
    def test_hemorrhage_validates(self):
        assert validate_effect_json_payload(HEMORRHAGE) == []

    def test_value_required(self):
        bad = json.loads(json.dumps(HEMORRHAGE))
        bad["effects"][0].pop("value")
        assert validate_effect_json_payload(bad) != []

    def test_escalate_every_rounds_positive(self):
        bad = json.loads(json.dumps(HEMORRHAGE))
        bad["effects"][0]["escalate_every_rounds"] = 0
        assert validate_effect_json_payload(bad) != []

    def test_escalate_dice_must_be_dice_string(self):
        bad = json.loads(json.dumps(HEMORRHAGE))
        bad["effects"][0]["escalate_dice"] = "notdice"
        assert validate_effect_json_payload(bad) != []

    def test_cure_block_validates(self):
        assert validate_effect_json_payload(HEMORRHAGE) == []

    def test_bad_cure_dc_rejected(self):
        bad = json.loads(json.dumps(HEMORRHAGE))
        bad["cure"]["dc"] = 17  # poza zamkiem {8,12,16,20,24}
        assert validate_effect_json_payload(bad) != []

    def test_cure_requires_skill(self):
        bad = json.loads(json.dumps(HEMORRHAGE))
        bad["cure"] = {"dc": 16}
        assert validate_effect_json_payload(bad) != []

    def test_tick_required(self):
        bad = json.loads(json.dumps(HEMORRHAGE))
        bad["effects"][0].pop("tick")
        assert validate_effect_json_payload(bad) != []


# ─── 2. Formuła eskalacji (deterministyczna: każda kość = 1) ───────────────────

class TestEscalationFormula:
    def setup_method(self):
        self._eff = HEMORRHAGE["effects"][0]

    def test_level_0_first_three_ticks(self):
        with patch.object(cs, "roll_damage_dice", return_value=1):
            assert cs._escalating_dot_damage(self._eff, 0) == 1
            assert cs._escalating_dot_damage(self._eff, 1) == 1
            assert cs._escalating_dot_damage(self._eff, 2) == 1

    def test_level_1_after_three_rounds(self):
        with patch.object(cs, "roll_damage_dice", return_value=1):
            # tick 3 → poziom 1 → base + 1× przyrost = 1 + 1 = 2
            assert cs._escalating_dot_damage(self._eff, 3) == 2
            assert cs._escalating_dot_damage(self._eff, 5) == 2

    def test_level_2_after_six_rounds(self):
        with patch.object(cs, "roll_damage_dice", return_value=1):
            # tick 6 → poziom 2 → base + 2× przyrost = 1 + 2 = 3
            assert cs._escalating_dot_damage(self._eff, 6) == 3


# ─── 3. Engine: escalating_dot tyka i zdejmuje HP + stan między rundami ────────

def _schema_sql() -> str:
    sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 18, "CHA": 10},
        "current_hp": 60, "max_hp": 60, "defense": {"base": 15},
        "equipped_weapon": "sword", "conditions": [],
    }
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    hem = json.dumps(HEMORRHAGE, ensure_ascii=False).replace("'", "''")
    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'S10','fantasy','m',1);
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
      VALUES ('hemorrhage','Krwotok','{hem}','Krwotok.',1,0);
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
def s10_db(tmp_path):
    db = tmp_path / "s10.db"
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


def _set_player_hemorrhage(db):
    snap = cs.get_active_combat(1)
    player = _player(snap)
    player["conditions"] = [_hem()]
    with sqlite3.connect(str(db)) as c:
        c.execute("UPDATE active_combat SET combatants=?, current_turn='player' WHERE campaign_id=1",
                  (json.dumps(snap["combatants"], ensure_ascii=False),))
        c.commit()


def _bump_round(db, round_n):
    with sqlite3.connect(str(db)) as c:
        c.execute("UPDATE active_combat SET round=?, current_turn='player' WHERE campaign_id=1", (round_n,))
        c.commit()


class TestEngineEscalatingDot:
    def test_dot_deals_damage_in_combat(self, s10_db):
        cs.initiate_combat(1, 1, ["bandit"])
        _set_player_hemorrhage(s10_db)
        with patch.object(cs, "roll_damage_dice", return_value=1):
            out = cs.evaluate_current_turn_conditions(1)
        dmg_events = [e for e in out["events"] if e["type"] == "condition_damage"]
        assert dmg_events, "escalating_dot musi wygenerować condition_damage"
        assert dmg_events[0]["condition_key"] == "hemorrhage"
        assert dmg_events[0]["damage"] == 1  # poziom 0

    def test_damage_escalates_across_rounds(self, s10_db):
        cs.initiate_combat(1, 1, ["bandit"])
        _set_player_hemorrhage(s10_db)
        seen = []
        with patch.object(cs, "roll_damage_dice", return_value=1):
            for rnd in range(1, 8):  # rundy 1..7
                _bump_round(s10_db, rnd)
                out = cs.evaluate_current_turn_conditions(1)
                dmg = [e["damage"] for e in out["events"] if e["type"] == "condition_damage"]
                if dmg:
                    seen.append(dmg[0])
        # 7 tyknięć: 1,1,1,2,2,2,3 — rośnie po 3 i 6 rundach
        assert seen == [1, 1, 1, 2, 2, 2, 3], f"krzywa eskalacji błędna: {seen}"


# ─── 4. Deklaratywna ścieżka cure ──────────────────────────────────────────────

def _cure_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT);
        CREATE TABLE game_config_conditions (key TEXT PRIMARY KEY, label TEXT, effect_json TEXT,
          description TEXT, is_active INTEGER DEFAULT 1);
    """)
    conn.execute(
        "INSERT INTO game_config_conditions (key,label,effect_json) VALUES (?,?,?)",
        ("hemorrhage", "Krwotok", json.dumps(HEMORRHAGE)),
    )
    sheet = {"stats": {"CON": 12}, "conditions": [{"key": "hemorrhage", "label": "Krwotok"}]}
    conn.execute("INSERT INTO characters (id, sheet_json) VALUES (1, ?)",
                 (json.dumps(sheet, ensure_ascii=False),))
    conn.commit()
    return conn


class TestCureMatch:
    def test_medicine_matches_hemorrhage_with_catalog_dc(self):
        conn = _cure_conn()
        key, dc = ss._match_curable_condition(conn, 1, "medicine")
        assert key == "hemorrhage"
        assert dc == 16  # DC z katalogu, nie z taga LLM

    def test_unrelated_skill_no_match(self):
        conn = _cure_conn()
        assert ss._match_curable_condition(conn, 1, "stealth") == (None, None)

    def test_no_condition_no_match(self):
        conn = _cure_conn()
        conn.execute("UPDATE characters SET sheet_json=? WHERE id=1",
                     (json.dumps({"conditions": []}),))
        conn.commit()
        assert ss._match_curable_condition(conn, 1, "medicine") == (None, None)


class TestRemoveConditionFromCharacter:
    def test_removes_from_sheet(self):
        conn = _cure_conn()
        removed = cs.remove_condition_from_character(conn, 1, 1, "hemorrhage")
        assert removed >= 1
        row = conn.execute("SELECT sheet_json FROM characters WHERE id=1").fetchone()
        conds = json.loads(row[0]).get("conditions", [])
        assert all(c.get("key") != "hemorrhage" for c in conds)

    def test_absent_condition_returns_zero(self):
        conn = _cure_conn()
        assert cs.remove_condition_from_character(conn, 1, 1, "frozen") == 0
