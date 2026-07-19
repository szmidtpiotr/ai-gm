"""AUDIT #1453 (P1) — in MP, a player's spell must persist under the ACTIVE caster
(ch_id), never under row["character_id"] (the host / first combatant).

Repro: 2-character MP party (host warrior char 100 + scholar char 101). The scholar
casts magic_bolt on their turn. Before the fix, the scholar's full sheet was written
to characters[100].sheet_json → permanent corruption of the host's character. After
the fix, host char 100 is untouched and the scholar's mana is deducted (CCS 101).
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if "httpx" not in sys.modules:
    sys.modules["httpx"] = MagicMock()

from _fixtures_schema import table_sql  # noqa: E402
from app.services import admin_config  # noqa: E402
from app.services import combat_service as cs  # noqa: E402
from app.services import spell_service  # noqa: E402


def _schema_sql() -> str:
    return """
    CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password_hash TEXT);
    INSERT INTO users (id, username, password_hash) VALUES (101,'host','x'),(102,'caster','x');

    CREATE TABLE campaigns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, mode TEXT DEFAULT 'multiplayer', status TEXT DEFAULT 'active'
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id, mode)
    VALUES (1, 'MP', 'fantasy', 'm', 101, 'multiplayer');

    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, user_id INTEGER,
      name TEXT, system_id TEXT, race TEXT DEFAULT 'human', sheet_json TEXT,
      location TEXT, is_active INTEGER DEFAULT 1
    );

    CREATE TABLE character_campaign_state (
      id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL, campaign_id INTEGER NOT NULL,
      current_hp INTEGER NOT NULL DEFAULT 0, max_hp INTEGER NOT NULL DEFAULT 0,
      current_mana INTEGER NOT NULL DEFAULT 0, max_mana INTEGER NOT NULL DEFAULT 0,
      conditions_json TEXT NOT NULL DEFAULT '[]', position_json TEXT,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(character_id, campaign_id)
    );

    CREATE TABLE game_config_spells (
      key TEXT PRIMARY KEY, label TEXT, tier INTEGER DEFAULT 1, mana_cost INTEGER DEFAULT 2,
      spell_type TEXT DEFAULT 'attack', damage_die TEXT, heal_die TEXT, effect_stat TEXT,
      effect_type TEXT, effect_duration INTEGER DEFAULT 1, target_zone TEXT DEFAULT 'any',
      aoe INTEGER DEFAULT 0, description TEXT, race_lock TEXT,
      rank2_json TEXT, rank3_json TEXT, is_active INTEGER DEFAULT 1, effect_json TEXT
    );
    INSERT INTO game_config_spells (key, label, tier, mana_cost, spell_type, damage_die)
    VALUES ('magic_bolt', 'Pocisk', 1, 2, 'attack', '2d6');

    CREATE TABLE character_spells (
      id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, spell_key TEXT,
      rank INTEGER DEFAULT 1, use_count INTEGER DEFAULT 0, learned_at_level INTEGER DEFAULT 1
    );
    INSERT INTO character_spells (character_id, spell_key, rank) VALUES (101, 'magic_bolt', 1);

    CREATE TABLE game_config_conditions (
      key TEXT PRIMARY KEY, label TEXT, effect_json TEXT, description TEXT,
      is_active INTEGER DEFAULT 1, stackable INTEGER DEFAULT 0, auto_remove TEXT
    );

    """ + table_sql("game_config_weapons") + """
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes)
    VALUES ('sword', 'Sword', '1d8', 'STR', 'warrior');

    """ + table_sql("game_config_enemies") + """
    INSERT INTO game_config_enemies
      (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, xp_award, skills_json, loot_table_key, drop_chance)
    VALUES ('bandit', 'Bandit', 40, 10, 3, -10, '1d8', 25, '{}', NULL, 0.0);

    """ + table_sql("game_config_meta") + """

    CREATE TABLE IF NOT EXISTS active_combat (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE, character_id INTEGER,
      round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT, combatants TEXT,
      status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT, loot_pool TEXT,
      loot_persisted INTEGER DEFAULT 0, post_combat_loot_json TEXT, boss_defeated INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS combat_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
      turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER,
      hp_after INTEGER, target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
      created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );
    CREATE TABLE IF NOT EXISTS campaign_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, character_id INTEGER,
      user_text TEXT, route TEXT, assistant_text TEXT, turn_number INTEGER,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS game_sessions (
      id TEXT PRIMARY KEY, campaign_id INTEGER, session_flags TEXT DEFAULT '{}',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """


# Host warrior sheet carries a unique marker so any clobber is detectable.
_HOST_SHEET = {
    "archetype": "warrior", "level": 5, "__host_marker__": "DO_NOT_OVERWRITE",
    "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 8, "WIS": 10, "CHA": 10},
    "current_hp": 40, "max_hp": 40, "defense": {"base": 16}, "equipped_weapon": "sword",
}
_CASTER_SHEET = {
    "archetype": "scholar", "level": 5,
    "stats": {"STR": 10, "DEX": 12, "CON": 12, "INT": 16, "WIS": 10, "CHA": 10},
    "current_hp": 30, "max_hp": 30, "defense": {"base": 14},
    "current_mana": 10, "max_mana": 10,
}


def _player_comb(cid, name, hp, defense):
    return {"id": cid, "type": "player", "name": name, "hp_current": hp, "hp_max": hp,
            "defense": defense, "zone": "engaged",
            "stats": {"STR": 12, "DEX": 12, "CON": 12, "INT": 16, "WIS": 10, "CHA": 10}}


def _enemy_comb():
    return {"id": "bandit_01", "type": "enemy", "enemy_key": "bandit", "name": "Bandit",
            "hp_current": 40, "hp_max": 40, "defense": 10, "attack_bonus": 3,
            "dex_modifier": -10, "xp_award": 25, "tier": "standard", "zone": "engaged",
            "stats": {"STR": 12, "DEX": 8, "CON": 12, "INT": 8, "WIS": 8, "CHA": 8}}


def _fresh_db(name: str) -> Path:
    tmp = Path("/tmp") / name
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    conn.executescript(_schema_sql())
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, system_id, race, sheet_json) "
        "VALUES (100, 1, 101, 'Aldric', 'fantasy', 'human', ?)", (json.dumps(_HOST_SHEET),))
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, system_id, race, sheet_json) "
        "VALUES (101, 1, 102, 'Mira', 'fantasy', 'human', ?)", (json.dumps(_CASTER_SHEET),))
    conn.execute("INSERT INTO character_campaign_state (character_id, campaign_id, current_hp, max_hp, current_mana, max_mana) "
                 "VALUES (100,1,40,40,0,0),(101,1,30,30,10,10)")
    # active combat: host char is character_id (row["character_id"]=100); it's the SCHOLAR's turn.
    conn.execute(
        "INSERT INTO active_combat (campaign_id, character_id, round, turn_order, current_turn, combatants, status) "
        "VALUES (1, 100, 1, ?, 'player:101', ?, 'active')",
        (json.dumps(["player:100", "player:101", "bandit_01"]),
         json.dumps([_player_comb("player:100", "Aldric", 40, 16),
                     _player_comb("player:101", "Mira", 30, 14),
                     _enemy_comb()])),
    )
    conn.commit()
    conn.close()
    return tmp


def _read_sheet(tmp, cid):
    conn = sqlite3.connect(str(tmp))
    r = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (cid,)).fetchone()
    conn.close()
    return json.loads(r[0]) if r and r[0] else {}


def _read_ccs_mana(tmp, cid):
    conn = sqlite3.connect(str(tmp))
    r = conn.execute("SELECT current_mana FROM character_campaign_state WHERE character_id=? AND campaign_id=1", (cid,)).fetchone()
    conn.close()
    return int(r[0]) if r else None


def test_mp_spell_mana_saves_to_caster_sheet():
    """Scholar (player:101) casts magic_bolt → host char 100 sheet untouched, caster mana down."""
    tmp = _fresh_db("_1453_mp_caster.db")
    host_before = _read_sheet(tmp, 100)

    ctxs = [
        patch.object(cs, "COMBAT_DB_PATH", str(tmp)),
        patch.object(admin_config, "DB_PATH", str(tmp)),
        patch.object(spell_service, "DB_PATH", str(tmp)),
        patch("app.services.combat_service.roll_d20", return_value=15),
    ]
    for c in ctxs:
        c.start()
    try:
        res = cs.resolve_attack(1, None, "player:101", raw_d20=15,
                                spell_key="magic_bolt", target_id="bandit_01",
                                authoritative=False)
    finally:
        for c in ctxs:
            c.stop()

    # spell actually resolved (not blocked)
    assert res.get("block_reason") != "spell_not_known", res
    assert res.get("mana_spent") == 2, res

    # HOST char 100 sheet must be byte-for-byte the same (no clobber with scholar's sheet).
    host_after = _read_sheet(tmp, 100)
    assert host_after == host_before, "host char 100 sheet was clobbered by the caster's spell"
    assert host_after.get("__host_marker__") == "DO_NOT_OVERWRITE"
    assert host_after.get("archetype") == "warrior"

    # Caster's mana was deducted (routed to CCS under char 101).
    assert _read_ccs_mana(tmp, 101) == 8, "caster mana not deducted from CCS(101)"
    # Host's mana pool untouched.
    assert _read_ccs_mana(tmp, 100) == 0
