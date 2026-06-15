"""TDD: Issue #621 — silnik walki musi honorować strukturalny `skip_turn` (slowed/stunned).

Bug: kondycje `slowed`/`stunned` deklarują pominięcie tury jako
`effects:[{"type":"skip_turn", ...}]`, ale `evaluate_current_turn_conditions`
blokował akcję tylko dla `type=="block_action"` → skip_turn martwy, zapasy „nic nie dają".
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


def _schema_sql() -> str:
    player_sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 18, "CHA": 10},
        "current_hp": 20, "max_hp": 20, "defense": {"base": 15},
        "equipped_weapon": "sword", "conditions": [],
    }
    psj = json.dumps(player_sheet, ensure_ascii=False).replace("'", "''")
    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'T','fantasy','m',1);
    CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER, name TEXT,
      system_id TEXT, sheet_json TEXT);
    INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
      VALUES (1,1,1,'Aldric','fantasy','{psj}');
    CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT, damage_die TEXT, linked_stat TEXT,
      allowed_classes TEXT DEFAULT 'warrior', is_active INTEGER DEFAULT 1);
    INSERT INTO game_config_weapons (key,label,damage_die,linked_stat,allowed_classes)
      VALUES ('sword','Sword','1d8','STR','warrior');
    CREATE TABLE game_config_enemies (key TEXT PRIMARY KEY, label TEXT, hp_base INTEGER, ac_base INTEGER,
      attack_bonus INTEGER, dex_modifier INTEGER DEFAULT 0, damage_die TEXT, tier TEXT DEFAULT 'standard',
      xp_award INTEGER DEFAULT 0, description TEXT, is_active INTEGER DEFAULT 1, loot_table_key TEXT,
      drop_chance REAL DEFAULT 0.0, skills_json TEXT, stats_json TEXT);
    INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,dex_modifier,damage_die,drop_chance,skills_json)
      VALUES ('bandit','Bandit',12,13,3,1,'1d8',0.0,'{{}}');
    CREATE TABLE active_combat (id INTEGER PRIMARY KEY, campaign_id INTEGER UNIQUE, character_id INTEGER,
      round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT, combatants TEXT, status TEXT DEFAULT 'active',
      ended_reason TEXT, location_tag TEXT, loot_pool TEXT, created_at TEXT, updated_at TEXT);
    CREATE TABLE combat_turns (id INTEGER PRIMARY KEY, combat_id INTEGER, campaign_id INTEGER, turn_number REAL,
      actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER, target_id TEXT,
      target_name TEXT, hit INTEGER, narrative TEXT,
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
    """


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "skip_turn.db"
    conn = sqlite3.connect(str(p))
    try:
        conn.executescript(_schema_sql())
        conn.commit()
    finally:
        conn.close()
    with patch.object(cs, "COMBAT_DB_PATH", str(p)):
        yield p


def _skip_turn_condition(chance=None, key="stunned", label="Ogłuszony") -> dict:
    eff = {"type": "skip_turn", "duration_rounds": 1}
    if chance is not None:
        eff["chance"] = chance
    return {
        "key": key, "label": label, "applied_at": "test",
        "effect_json": json.dumps(
            {"schema_version": 1, "effect_category": "character_condition", "effects": [eff]},
            ensure_ascii=False),
    }


def _set_current_actor_condition(db_path: Path, condition: dict) -> None:
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


# ─── Test główny: stunned (skip_turn bez chance) blokuje turę ─────────────────

@patch("app.services.combat_service.roll_d20")
def test_structured_skip_turn_blocks_actor(mock_r20, db):
    """skip_turn bez `chance` = zawsze pomija turę (stunned 100%)."""
    mock_r20.side_effect = [10, 5]
    cs.initiate_combat(1, 1, ["bandit"])
    _set_current_actor_condition(db, _skip_turn_condition())

    out = cs.evaluate_current_turn_conditions(1)
    assert out["blocked"] is True
    assert any(evt["type"] == "block_action" for evt in out["events"])


# ─── Chance: trafiony roll pomija, nietrafiony przepuszcza ────────────────────

@patch("app.services.combat_service.random.random", return_value=0.10)
@patch("app.services.combat_service.roll_d20")
def test_skip_turn_chance_hit_blocks(mock_r20, _rand, db):
    """slowed chance=0.5, roll 0.10 < 0.5 → tura pominięta."""
    mock_r20.side_effect = [10, 5]
    cs.initiate_combat(1, 1, ["bandit"])
    _set_current_actor_condition(db, _skip_turn_condition(chance=0.5, key="slowed", label="Spowolniony"))

    out = cs.evaluate_current_turn_conditions(1)
    assert out["blocked"] is True


@patch("app.services.combat_service.random.random", return_value=0.90)
@patch("app.services.combat_service.roll_d20")
def test_skip_turn_chance_miss_does_not_block(mock_r20, _rand, db):
    """slowed chance=0.5, roll 0.90 ≥ 0.5 → aktor działa normalnie."""
    mock_r20.side_effect = [10, 5]
    cs.initiate_combat(1, 1, ["bandit"])
    _set_current_actor_condition(db, _skip_turn_condition(chance=0.5, key="slowed", label="Spowolniony"))

    out = cs.evaluate_current_turn_conditions(1)
    assert out["blocked"] is False


# ─── Backward compat: block_action (strukturalny) nadal blokuje ──────────────

@patch("app.services.combat_service.roll_d20")
def test_block_action_still_blocks(mock_r20, db):
    """Istniejące kondycje block_action działają jak dotąd (brak regresji)."""
    mock_r20.side_effect = [10, 5]
    cs.initiate_combat(1, 1, ["bandit"])
    cond = {
        "key": "fear", "label": "Strach", "applied_at": "test",
        "effect_json": json.dumps(
            {"schema_version": 1, "effect_category": "character_condition",
             "effects": [{"type": "block_action"}]}, ensure_ascii=False),
    }
    _set_current_actor_condition(db, cond)

    out = cs.evaluate_current_turn_conditions(1)
    assert out["blocked"] is True
