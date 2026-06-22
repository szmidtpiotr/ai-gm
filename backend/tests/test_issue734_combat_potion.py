"""TDD: Issue #734 — gracz może użyć leczniczej mikstury W TRAKCIE walki jako akcji tury.

Pokrywa:
- `use_consumable_in_combat`: w turze gracza wypicie leczniczej mikstury z plecaka
  podnosi PŻ (sync do active_combat) i KONSUMUJE turę (current_turn != player),
- mikstura jest faktycznie zużyta z plecaka (quantity -1 / usunięta),
- wymaga tury gracza — poza turą gracza ValueError,
- brak aktywnej walki → ValueError,
- backward compat: użycie mikstury POZA walką (loot_service.use_inventory_item)
  nadal działa bez zmian i NIE dotyka tury.
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
from app.services import loot_service as ls


HEAL_EFFECT = {"effects": [{"type": "heal_hp", "value": 8}]}


def _schema_sql() -> str:
    sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
        "current_hp": 3, "max_hp": 12, "defense": {"base": 15},
        "equipped_weapon": "sword", "conditions": [],
    }
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    heal = json.dumps(HEAL_EFFECT, ensure_ascii=False).replace("'", "''")
    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'734','fantasy','m',1);
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
      loot_table_key TEXT, drop_chance REAL DEFAULT 0.0, skills_json TEXT, stats_json TEXT,
      attacks_per_turn INTEGER DEFAULT 1, image_url TEXT);
    INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,dex_modifier,damage_die,drop_chance,skills_json)
      VALUES ('bandit','Bandit',40,13,3,1,'1d8',0.0,'{{}}');
    CREATE TABLE game_config_items (key TEXT PRIMARY KEY, label TEXT, item_type TEXT,
      effect_json TEXT, effect_type TEXT, effect_dice TEXT, effect_bonus INTEGER, effect_target TEXT,
      is_active INTEGER DEFAULT 1);
    INSERT INTO game_config_items (key,label,item_type,effect_json)
      VALUES ('potion_healing_minor','Mała mikstura lecznicza','consumable','{heal}');
    CREATE TABLE game_config_consumables (key TEXT PRIMARY KEY, label TEXT, effect_json TEXT,
      effect_type TEXT, effect_dice TEXT, effect_bonus INTEGER, effect_target TEXT, is_active INTEGER DEFAULT 1);
    CREATE TABLE character_inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER,
      item_key TEXT, weapon_key TEXT, consumable_key TEXT, quantity INTEGER DEFAULT 1, equipped_slot TEXT);
    INSERT INTO character_inventory (id,character_id,item_key,quantity)
      VALUES (1,1,'potion_healing_minor',2);
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
def db734(tmp_path):
    db = tmp_path / "i734.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(_schema_sql())
        conn.commit()
    finally:
        conn.close()
    with patch.object(cs, "COMBAT_DB_PATH", str(db)), patch.object(ls, "LOOT_DB_PATH", str(db)):
        yield db


def _player(snap):
    return next(c for c in snap["combatants"] if c["id"] == "player")


def _force_player_turn(db):
    snap = cs.get_active_combat(1)
    with sqlite3.connect(str(db)) as c:
        c.execute(
            "UPDATE active_combat SET combatants=?, current_turn='player', round=1 WHERE campaign_id=1",
            (json.dumps(snap["combatants"], ensure_ascii=False),),
        )
        c.commit()


# ─── Test główny — mikstura w walce leczy i zużywa turę ────────────────────────

def test_combat_potion_heals_and_consumes_turn(db734):
    cs.initiate_combat(1, 1, ["bandit"])
    _force_player_turn(db734)

    hp_before = int(_player(cs.get_active_combat(1)).get("hp_current", 0) or 0)
    assert hp_before == 3

    res = cs.use_consumable_in_combat(1, 1)
    assert res["ok"] is True

    snap = cs.get_active_combat(1)
    hp_after = int(_player(snap).get("hp_current", 0) or 0)
    assert hp_after > hp_before, "PŻ powinno wzrosnąć po wypiciu mikstury"
    assert snap["current_turn"] != "player", "użycie mikstury w walce zużywa turę"


def test_combat_potion_decrements_stack(db734):
    cs.initiate_combat(1, 1, ["bandit"])
    _force_player_turn(db734)
    cs.use_consumable_in_combat(1, 1)
    with sqlite3.connect(str(db734)) as c:
        qty = c.execute("SELECT quantity FROM character_inventory WHERE id=1").fetchone()
    assert qty is not None and int(qty[0]) == 1, "mikstura powinna zostać zużyta (2→1)"


def test_use_outside_player_turn_rejected(db734):
    cs.initiate_combat(1, 1, ["bandit"])
    with sqlite3.connect(str(db734)) as c:
        c.execute("UPDATE active_combat SET current_turn='enemy_0' WHERE campaign_id=1")
        c.commit()
    with pytest.raises(ValueError):
        cs.use_consumable_in_combat(1, 1)


def test_use_without_active_combat_rejected(db734):
    with pytest.raises(ValueError):
        cs.use_consumable_in_combat(1, 1)


# ─── Backward compat — użycie poza walką bez zmian ─────────────────────────────

def test_use_inventory_item_outside_combat_still_heals(db734):
    # brak active_combat → loot_service.use_inventory_item leczy sheet jak dotąd
    out = ls.use_inventory_item(1, 1)
    healed = [e for e in out["effects_applied"] if e.get("type") == "heal_hp"]
    assert healed and healed[0]["amount"] > 0
    assert out["character_state"]["current_hp"] > 3
