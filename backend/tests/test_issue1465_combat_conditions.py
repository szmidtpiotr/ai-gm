"""TDD: Issue #1465 (Faza AUDIT / G3) — stany bojowe zgodne z Księgą.

Księga (spec): docs/V2_ARCHITECTURE/11_CONDITIONS_SYSTEM.md.

Pokrywa 4 poprawki seedów `game_config_conditions` + wpięcie w silnik:
  1. poisoned — obok STR−2 dochodzi DoT 1k4/turę (typ `dot`, łapany przez pętlę
     w evaluate_current_turn_conditions). Wartość startowa, Sandbox-tunable.
  2. frozen  — obok DEX−4 dochodzi `block_action` (odbiera akcje); dopóki nie
     padnie udany rzut CON DC 14, tura przepada.
  3. slowed  — obok skip_turn dochodzi −2 do obrony (`static_stat_modifier` stat
     `ac`), faktycznie doliczane do `defense_stat` #826 przez `_effective_defense_stat`.
  4. bleeding — flat 1 PŻ/rundę (zgodnie z Księgą „-1 HP end of each round"),
     zamiast poprzedniego zepsutego `{"damage":"1d3"}` (klucz ignorowany przez DoT).
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


# ─── effect_json kontraktów #1465 (identyczne z seedem game_config_conditions) ──

def _ej(*effects: dict, **extra) -> dict:
    payload = {
        "schema_version": 1,
        "effect_category": "character_condition",
        "effects": list(effects),
    }
    payload.update(extra)
    return payload


POISONED = _ej(
    {"type": "static_stat_modifier", "stat": "STR", "value": -2, "expires": "duration_rounds:3"},
    {"type": "dot", "value": "1d4", "damage_type": "poison", "tick": "start_turn", "expires": "duration_rounds:3"},
)
FROZEN = _ej(
    {"type": "static_stat_modifier", "stat": "DEX", "value": -4},
    {"type": "block_action"},
    {"type": "periodic_save", "stat": "CON", "value": 14, "tick": "start_turn", "expires": "save_success"},
)
SLOWED = _ej(
    {"type": "skip_turn", "chance": 0.5, "duration_rounds": 2},
    {"type": "static_stat_modifier", "stat": "ac", "value": -2},
    clear_on="duration",
)
BLEEDING = _ej(
    {"type": "dot", "value": 1, "damage_type": "physical", "tick": "start_turn", "expires": "duration_rounds:3"},
    clear_on="duration",
)


# ─── Fixtura walki (wzorzec z test_issue603_s8_conditions) ─────────────────────

def _schema_sql() -> str:
    sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 18, "CHA": 10},
        "current_hp": 30, "max_hp": 30, "defense": {"base": 15},
        "equipped_weapon": "sword", "conditions": [],
    }
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'G3','fantasy','m',1);
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
def db(tmp_path):
    p = tmp_path / "g3.db"
    conn = sqlite3.connect(str(p))
    try:
        conn.executescript(_schema_sql())
        conn.commit()
    finally:
        conn.close()
    with patch.object(cs, "COMBAT_DB_PATH", str(p)):
        yield p


def _set_actor_condition(db_path: Path, condition_ej: dict, *, key: str, label: str) -> None:
    """Wstaw kondycję na aktora bieżącej tury (wzorzec z test_issue621_skip_turn)."""
    condition = {"key": key, "label": label, "applied_at": "test",
                 "effect_json": json.dumps(condition_ej, ensure_ascii=False), "runtime": {}}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT combatants, current_turn FROM active_combat WHERE campaign_id=1").fetchone()
        combatants = json.loads(row["combatants"] or "[]")
        for c in combatants:
            if isinstance(c, dict) and str(c.get("id") or "") == str(row["current_turn"] or ""):
                c["conditions"] = [condition]
        conn.execute("UPDATE active_combat SET combatants=? WHERE campaign_id=1",
                     (json.dumps(combatants, ensure_ascii=False),))
        conn.commit()
    finally:
        conn.close()


# ─── 1. poisoned zadaje DoT co turę ────────────────────────────────────────────

class TestPoisonedDot:
    @patch("app.services.combat_service.roll_d20")
    def test_poisoned_deals_dot(self, _mock_r20, db):
        """poisoned: obok STR−2 tyka DoT 1k4/turę (event condition_damage, typ poison)."""
        _mock_r20.return_value = 10
        cs.initiate_combat(1, 1, ["bandit"])
        _set_actor_condition(db, POISONED, key="poisoned", label="Poisoned")

        out = cs.evaluate_current_turn_conditions(1)
        dmg_events = [e for e in out["events"] if e["type"] == "condition_damage"]
        assert dmg_events, f"trucizna nie zadała obrażeń; events={out['events']}"
        dmg = dmg_events[0]["damage"]
        assert 1 <= dmg <= 4, f"1k4 poza zakresem: {dmg}"
        assert dmg_events[0]["damage_type"] == "poison"

    def test_poisoned_still_applies_str_penalty(self, db):
        """Regresja: STR−2 nadal się folduje obok nowego DoT."""
        sheet = {"stats": {"STR": 14}, "conditions": [
            {"key": "poisoned", "label": "P", "effect_json": json.dumps(POISONED)}]}
        assert cs._combatant_stat_modifier({}, sheet=sheet, stat="STR") == 0  # +2 −2


# ─── 2. frozen odbiera akcję (block_action), póki nie padnie CON save ──────────

class TestFrozenSkipsTurn:
    @patch("app.services.combat_service.roll_d20")
    def test_frozen_skips_turn(self, mock_r20, db):
        """frozen: nieudany CON save (roll 2 → 3 < DC 14) → block_action blokuje turę."""
        mock_r20.return_value = 2
        cs.initiate_combat(1, 1, ["bandit"])
        _set_actor_condition(db, FROZEN, key="frozen", label="Zmrożony")

        out = cs.evaluate_current_turn_conditions(1)
        assert out["blocked"] is True, f"lód nie odebrał akcji; events={out['events']}"
        assert any(e["type"] == "block_action" for e in out["events"])

    @patch("app.services.combat_service.roll_d20")
    def test_frozen_released_on_successful_save(self, mock_r20, db):
        """Udany CON save (nat 20) zdejmuje frozen PRZED block_action → aktor działa."""
        mock_r20.return_value = 20
        cs.initiate_combat(1, 1, ["bandit"])
        _set_actor_condition(db, FROZEN, key="frozen", label="Zmrożony")

        out = cs.evaluate_current_turn_conditions(1)
        assert out["blocked"] is False


# ─── 3. slowed obniża obronę o 2 (faktycznie doliczane do defense_stat #826) ───

class TestSlowedDefensePenalty:
    def _enemy(self, conditions):
        return {"id": "e1", "defense": 15, "dex_modifier": 1, "conditions": conditions}

    def test_slowed_defense_penalty(self):
        """slowed folduje stat `ac` −2 do obrony obrońcy."""
        slowed = {"key": "slowed", "label": "Spowolniony", "effect_json": json.dumps(SLOWED)}
        enemy = self._enemy([slowed])
        assert cs._combatant_stat_modifier(enemy, sheet=None, stat="ac") == -2
        assert cs._effective_defense_stat(15, enemy) == 13

    def test_no_condition_defense_unchanged(self):
        enemy = self._enemy([])
        assert cs._effective_defense_stat(15, enemy) == 15

    def test_slowed_defender_takes_more_damage(self):
        """Niższa obrona → większy margines / mniejsza redukcja pancerza → ≥ obrażeń."""
        slowed = {"key": "slowed", "label": "Spowolniony", "effect_json": json.dumps(SLOWED)}
        enemy_slowed = self._enemy([slowed])
        enemy_ok = self._enemy([])
        base_dmg, attack_total = 8, 20
        dmg_slowed = cs.apply_defense_model(
            base_dmg, attack_total,
            cs._effective_defense_stat(15, enemy_slowed), ignore_armor=False)["final"]
        dmg_ok = cs.apply_defense_model(
            base_dmg, attack_total,
            cs._effective_defense_stat(15, enemy_ok), ignore_armor=False)["final"]
        assert dmg_slowed >= dmg_ok
        assert dmg_slowed > dmg_ok or base_dmg <= 1  # przy sensownych liczbach realnie boli bardziej


# ─── 4. bleeding — flat 1 PŻ/rundę (zgodnie z Księgą) ─────────────────────────

class TestBleedingFlat:
    @patch("app.services.combat_service.roll_d20")
    def test_bleeding_deals_flat_one(self, _mock_r20, db):
        _mock_r20.return_value = 10
        cs.initiate_combat(1, 1, ["bandit"])
        _set_actor_condition(db, BLEEDING, key="bleeding", label="Krwawienie")

        out = cs.evaluate_current_turn_conditions(1)
        dmg_events = [e for e in out["events"] if e["type"] == "condition_damage"]
        assert dmg_events, f"krwawienie nie zadało obrażeń; events={out['events']}"
        assert dmg_events[0]["damage"] == 1, "Księga: -1 PŻ/rundę (flat)"
