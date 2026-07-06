"""TDD: Issue #1160 — AoE spell damage omija model obrony #826.

`_resolve_aoe_single_target` aplikował surowy `sum(rolls)+int_mod` prosto do HP,
pomijając `apply_defense_model` — brak redukcji pancerzem, brak margin bonus, w
przeciwieństwie do każdej ścieżki single-target. Fix: przepuść AoE per-cel przez
apply_defense_model (jak :5954).
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _fixtures_schema as fx  # noqa: E402
from app.services import combat_service


def _combat_db(tmp_path, *, enemy_defense, enemy_hp=100, mana=12):
    db = tmp_path / "aoe_def.db"
    player = {
        "id": "player", "type": "player", "name": "Mag",
        "hp_current": 20, "hp_max": 20, "defense": 10, "zone": "ranged",
        "stats": {"STR": 8, "DEX": 10, "CON": 8, "INT": 16, "WIS": 12, "CHA": 10},
        "conditions": [],
    }
    enemy = {
        "id": "ogre0", "type": "enemy", "enemy_key": "ogre", "name": "Ogr",
        "hp_current": enemy_hp, "hp_max": enemy_hp, "defense": enemy_defense,
        "attack_bonus": 0, "damage_dice": "1d6", "zone": "ranged", "conditions": [],
        "dex_modifier": 0, "xp_award": 10, "tier": "minion",
        "stats": {"STR": 12, "DEX": 8, "CON": 12, "INT": 7, "WIS": 8, "CHA": 8},
    }
    combatants = [player, enemy]
    order = ["player", "ogre0"]
    sheet = {
        "archetype": "scholar", "level": 5,
        "stats": player["stats"], "current_hp": 20, "max_hp": 20,
        "current_mana": mana, "max_mana": mana, "conditions": [], "skills": {},
    }
    cs = json.dumps(combatants, ensure_ascii=False).replace("'", "''")
    os_ = json.dumps(order, ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        fx.create_tables(conn, "game_config_conditions", "game_config_spells", "game_config_enemies")
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'AOE');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Mag','fantasy','{sj}');
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, boss_defeated INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'{os_}','player','{cs}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        INSERT INTO game_config_spells (key,label,spell_type,effect_type,effect_stat,effect_duration,mana_cost,tier,damage_die,aoe,effect_json) VALUES
          ('fireball','Kula Ognia','attack_aoe',NULL,NULL,1,6,5,'3d6',1,NULL);
        CREATE TABLE character_spells (character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1,
          learned_at_level INTEGER DEFAULT 1);
        INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,damage_die,dex_modifier,skills_json,stats_json,tier,loot_table_key,drop_chance,xp_award)
          VALUES ('ogre','Ogr',100,10,0,'1d6',0,NULL,NULL,'minion',NULL,0,10);
        """)
        conn.commit()
    finally:
        conn.close()
    return db


def _enemy_hp(db):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
    finally:
        conn.close()
    for c in json.loads(row[0]):
        if c.get("type") == "enemy":
            return int(c.get("hp_current"))
    return None


def _cast_fireball(db):
    # rolls=[10] deterministyczne; roll_d20→1 obniża unik wroga → trafienie pewne.
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)), \
         patch.object(combat_service, "roll_dice_detailed", lambda die: {"rolls": [10], "die": die}), \
         patch.object(combat_service, "roll_d20", lambda *a, **k: 1):
        return combat_service.resolve_attack(1, None, attacker="player", raw_d20=10,
                                             spell_key="fireball")


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_aoe_damage_reduced_by_armor(tmp_path):
    """Pancerz wroga (defense 25 → redukcja 15) tnie AoE: 13 surowego → 1 finalne."""
    db = _combat_db(tmp_path, enemy_defense=25, enemy_hp=100)
    out = _cast_fireball(db)
    assert out.get("hit") is True
    # base = sum([10]) + INT_mod(+3) = 13; armor = 25-10 = 15 → final = max(1, 13-15) = 1
    assert out.get("damage") == 1, f"pancerz nie zredukował AoE (damage={out.get('damage')}) (#1160)"
    assert int(out.get("armor_reduction") or 0) > 0, "brak armor_reduction — model obrony pominięty"
    assert _enemy_hp(db) == 99


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_aoe_full_damage_vs_unarmored(tmp_path):
    """Wróg bez pancerza (defense 8 → redukcja 0) obrywa pełne obrażenia.

    Model #826 nadal dolicza margin bonus (atak >> obrona), więc damage >= base 13,
    ale pancerz NIC nie zredukował (armor_reduction == 0)."""
    db = _combat_db(tmp_path, enemy_defense=8, enemy_hp=100)
    out = _cast_fireball(db)
    assert out.get("hit") is True
    assert out.get("damage") >= 13, f"AoE bez pancerza zaniżone (got {out.get('damage')})"
    assert int(out.get("armor_reduction") or 0) == 0, "pancerz nie powinien redukować (defense 8)"
    assert _enemy_hp(db) == 100 - int(out["damage"])
