"""Krok 4 AUDIT — walidacja i mechaniki magii w walce (combat_service + spell_service).

Pokrywa 3 issue (Faza AUDIT):

#1431 (P0) — bramka znajomości czaru PRZED dispatchem: rzucenie nieznanego/za-wysokiego/
             cudzego (race_lock) czaru w walce → blocked, mana i tura NIETKNIĘTE.
#1432 (P1) — rangi R2/R3 działają w walce (mana/kość), Nat20 kondycje data-driven
             (effect_json z katalogu), krasnoludzki miscast na Nat 2, drain_life leczy.
#1433 (P2) — sleep rzucalny (kondycja `sleeping`), defense poza walką zablokowany,
             mana_cost=0 respektowany (0 to legalna wartość, nie falsy-fallback do 2).
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


# ─────────────────────────────── schema / helpers ────────────────────────────────

def _schema_sql() -> str:
    return """
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password_hash TEXT
    );
    INSERT INTO users (id, username, password_hash) VALUES (1, 'u', 'x');

    CREATE TABLE campaigns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active'
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id)
    VALUES (1, 'T', 'fantasy', 'm', 1);

    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, user_id INTEGER,
      name TEXT, system_id TEXT, race TEXT DEFAULT 'human', sheet_json TEXT,
      location TEXT, is_active INTEGER DEFAULT 1
    );

    CREATE TABLE game_config_spells (
      key TEXT PRIMARY KEY, label TEXT, tier INTEGER DEFAULT 1, mana_cost INTEGER DEFAULT 2,
      spell_type TEXT DEFAULT 'attack', damage_die TEXT, heal_die TEXT, effect_stat TEXT,
      effect_type TEXT, effect_duration INTEGER DEFAULT 1, target_zone TEXT DEFAULT 'any',
      aoe INTEGER DEFAULT 0, description TEXT, race_lock TEXT,
      rank2_json TEXT, rank3_json TEXT, is_active INTEGER DEFAULT 1, effect_json TEXT
    );

    CREATE TABLE character_spells (
      id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, spell_key TEXT,
      rank INTEGER DEFAULT 1, use_count INTEGER DEFAULT 0, learned_at_level INTEGER DEFAULT 1
    );

    CREATE TABLE game_config_conditions (
      key TEXT PRIMARY KEY, label TEXT, effect_json TEXT, description TEXT,
      is_active INTEGER DEFAULT 1, stackable INTEGER DEFAULT 0, auto_remove TEXT
    );
    INSERT INTO game_config_conditions (key, label, effect_json, is_active, auto_remove) VALUES
      ('stunned', 'Ogłuszony', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"skip_turn","duration_rounds":1}],"clear_on":"duration"}', 1, 'on_turn_start'),
      ('sleeping', 'Uśpiony', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"skip_turn","duration_rounds":2}],"clear_on":"damage_taken"}', 1, 'on_damage');

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


def _sheet(*, archetype="scholar", level=5, hp=30, mana=10):
    return json.dumps({
        "archetype": archetype, "level": level,
        "stats": {"STR": 12, "DEX": 12, "CON": 12, "INT": 16, "WIS": 10, "CHA": 10},
        "current_hp": hp, "max_hp": 30, "defense": {"base": 14},
        "current_mana": mana, "max_mana": 10,
    })


def _fresh_db(name: str, *, race="human", sheet=None) -> Path:
    tmp = Path("/tmp") / name
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    conn.executescript(_schema_sql())
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, system_id, race, sheet_json) "
        "VALUES (1, 1, 1, 'Mag', 'fantasy', ?, ?)",
        (race, sheet if sheet is not None else _sheet()),
    )
    conn.commit()
    conn.close()
    return tmp


def _add_spell(tmp: Path, key, **cols):
    conn = sqlite3.connect(str(tmp))
    cols.setdefault("label", key)
    keys = ["key"] + list(cols.keys())
    vals = [key] + list(cols.values())
    conn.execute(
        f"INSERT INTO game_config_spells ({','.join(keys)}) VALUES ({','.join(['?']*len(keys))})",
        vals,
    )
    conn.commit()
    conn.close()


def _learn(tmp: Path, spell_key, rank=1, char_id=1):
    conn = sqlite3.connect(str(tmp))
    conn.execute(
        "INSERT INTO character_spells (character_id, spell_key, rank) VALUES (?,?,?)",
        (char_id, spell_key, rank),
    )
    conn.commit()
    conn.close()


def _write_combat(tmp: Path, *, current_turn="player", combatants=None, character_id=1):
    conn = sqlite3.connect(str(tmp))
    conn.execute(
        """INSERT INTO active_combat
           (campaign_id, character_id, round, turn_order, current_turn, combatants, status)
           VALUES (1, ?, 1, ?, ?, ?, 'active')""",
        (character_id, json.dumps(["player", "bandit_01"]), current_turn,
         json.dumps(combatants if combatants is not None else [_player(), _enemy()])),
    )
    conn.commit()
    conn.close()


def _read_char_sheet(tmp: Path, char_id=1):
    conn = sqlite3.connect(str(tmp))
    r = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (char_id,)).fetchone()
    conn.close()
    return json.loads(r[0]) if r and r[0] else {}


def _player():
    return {"id": "player", "type": "player", "name": "Mag", "hp_current": 30,
            "hp_max": 30, "defense": 14, "zone": "engaged",
            "stats": {"STR": 12, "DEX": 12, "CON": 12, "INT": 16, "WIS": 10, "CHA": 10}}


def _enemy(cid="bandit_01", hp=40, zone="engaged"):
    return {"id": cid, "type": "enemy", "enemy_key": "bandit", "name": "Bandit",
            "hp_current": hp, "hp_max": 40, "defense": 10, "attack_bonus": 3,
            "dex_modifier": -10, "xp_award": 25, "tier": "standard", "zone": zone,
            "stats": {"STR": 12, "DEX": 8, "CON": 12, "INT": 8, "WIS": 8, "CHA": 8}}


def _ctx(tmp):
    """Wspólny patch DB-path dla combat + admin + spell_service."""
    return [
        patch.object(cs, "COMBAT_DB_PATH", str(tmp)),
        patch.object(admin_config, "DB_PATH", str(tmp)),
        patch.object(spell_service, "DB_PATH", str(tmp)),
    ]


def _cast(tmp, spell_key, raw_d20, *, target_id="bandit_01"):
    """Rzuca czar w walce ścieżką resolve_attack (authoritative=False → raw_d20 z argumentu)."""
    ctxs = _ctx(tmp) + [patch("app.services.combat_service.roll_d20", return_value=raw_d20)]
    for c in ctxs:
        c.start()
    try:
        return cs.resolve_attack(1, None, "player", raw_d20=raw_d20,
                                 spell_key=spell_key, target_id=target_id, authoritative=False)
    finally:
        for c in ctxs:
            c.stop()


# ═══════════════════════════════ #1431 — bramka znajomości ════════════════════════

def test_spell_not_known_blocked():
    """Scholar L5 rzuca `fireball` (tier 5, nienauczony) → blocked spell_not_known,
    mana NIETKNIĘTA (jedyną bramką NIE jest już sam koszt many)."""
    tmp = _fresh_db("_c4_1431a.db")
    _add_spell(tmp, "fireball", tier=5, mana_cost=6, spell_type="attack_aoe", damage_die="6d6", aoe=1)
    _write_combat(tmp)
    res = _cast(tmp, "fireball", 15)
    assert res.get("blocked") is True
    assert res.get("block_reason") == "spell_not_known"
    # mana nietknięta
    assert _read_char_sheet(tmp).get("current_mana") == 10


def test_spell_race_locked_blocked():
    """Człowiek próbuje rzucić czar Rdzeń-magii (race_lock='dwarf') mimo wpisu w
    character_spells → blocked spell_race_locked (race_lock egzekwowany też w walce)."""
    tmp = _fresh_db("_c4_1431b.db", race="human")
    _add_spell(tmp, "vein_tremor", tier=1, mana_cost=2, spell_type="attack",
               damage_die="2d6", race_lock="dwarf")
    _learn(tmp, "vein_tremor", rank=1)
    _write_combat(tmp)
    res = _cast(tmp, "vein_tremor", 15)
    assert res.get("blocked") is True
    assert res.get("block_reason") == "spell_race_locked"
    assert _read_char_sheet(tmp).get("current_mana") == 10


def test_known_spell_not_blocked():
    """Regresja: wyuczony czar (magic_bolt R1) NIE jest blokowany bramką."""
    tmp = _fresh_db("_c4_1431c.db")
    _add_spell(tmp, "magic_bolt", tier=1, mana_cost=2, spell_type="attack", damage_die="2d6")
    _learn(tmp, "magic_bolt", rank=1)
    _write_combat(tmp)
    res = _cast(tmp, "magic_bolt", 15)
    assert res.get("block_reason") != "spell_not_known"
    assert "hit" in res


# ═══════════════════════════════ #1432 — rangi / miscast / drain ══════════════════

def test_spell_rank_scaling_in_combat():
    """magic_bolt R3 → w walce mana 1 i kość 3d6 (staty rangi, nie bazowe 2 / 2d6).
    Wcześniej rangi = placebo poza walką."""
    tmp = _fresh_db("_c4_1432a.db")
    _add_spell(tmp, "magic_bolt", tier=1, mana_cost=2, spell_type="attack", damage_die="2d6",
               rank2_json=json.dumps({"mana_cost": 2, "damage_die": "2d8"}),
               rank3_json=json.dumps({"mana_cost": 1, "damage_die": "3d6"}))
    _learn(tmp, "magic_bolt", rank=3)
    _write_combat(tmp)
    res = _cast(tmp, "magic_bolt", 15)
    assert res.get("hit") is True, res
    assert res.get("mana_spent") == 1, res
    assert res.get("damage_die") == "3d6", res


def test_nat20_stun_skips_enemy_turn():
    """Nat20 secondary `stunned` buduje wpis kondycji z KATALOGU (effect_json skip_turn),
    nie kosmetyczny inline dict — silnik faktycznie pominie turę wroga."""
    tmp = _fresh_db("_c4_1432b.db")
    _add_spell(tmp, "magic_bolt", tier=1, mana_cost=2, spell_type="attack", damage_die="2d6")
    _learn(tmp, "magic_bolt", rank=1)
    _write_combat(tmp)
    with patch("app.services.spell_service.resolve_spell_nat20_secondary",
               return_value={"nat20_secondary_roll": 3, "extra_damage": 0,
                             "condition": "stunned", "zone_change": False,
                             "narrative": "stun"}):
        res = _cast(tmp, "magic_bolt", 20)
    assert res.get("hit") is True, res
    # wróg dostał kondycję stunned z effect_json z katalogu (skip_turn)
    conn = sqlite3.connect(str(tmp))
    combatants = json.loads(conn.execute(
        "SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()[0])
    conn.close()
    enemy = next(c for c in combatants if c["id"] == "bandit_01")
    stun = next((c for c in (enemy.get("conditions") or [])
                 if str(c.get("key")).lower() == "stunned"), None)
    assert stun is not None, "brak kondycji stunned na wrogu"
    assert stun.get("effect_json"), "kondycja stunned bez effect_json (kosmetyczna)"
    assert "skip_turn" in json.dumps(stun["effect_json"])


def test_dwarf_miscast_nat2():
    """Krasnolud-Uczony rzuca Rdzeń-czar z raw d20 = 2 → miscast (is_miscast próg 2),
    trafienie NIE dochodzi, kara self-damage/stun przez resolve_miscast."""
    tmp = _fresh_db("_c4_1432c.db", race="dwarf")
    _add_spell(tmp, "vein_tremor", tier=1, mana_cost=2, spell_type="attack",
               damage_die="2d6", race_lock="dwarf")
    _learn(tmp, "vein_tremor", rank=1)
    _write_combat(tmp)
    res = _cast(tmp, "vein_tremor", 2)
    assert res.get("hit") is False, res
    assert res.get("miscast"), "brak miscast dla krasnoluda na Nat 2"
    assert res["miscast"].get("miscast") is True


def test_drain_life_heals_caster():
    """drain_life R3 (heal_pct=100) → rzucający leczy się o zadane obrażenia (lifesteal),
    wcześniej `heal_pct` był martwym seedem (czar = zwykły atak)."""
    tmp = _fresh_db("_c4_1432d.db", sheet=_sheet(hp=5))  # nisko HP → heal widoczny
    _add_spell(tmp, "drain_life", tier=3, mana_cost=3, spell_type="attack", damage_die="2d8",
               rank3_json=json.dumps({"mana_cost": 2, "damage_die": "3d6", "heal_pct": 100}))
    _learn(tmp, "drain_life", rank=3)
    _write_combat(tmp)
    res = _cast(tmp, "drain_life", 15)
    assert res.get("hit") is True, res
    assert res.get("lifesteal_healed", 0) > 0, res
    assert _read_char_sheet(tmp).get("current_hp") > 5


# ═══════════════════════════════ #1433 — sleep / defense OOC / mana=0 ═════════════

def test_sleep_castable_or_hidden():
    """sleep (effect_type='sleeping') NIE odbija się już jako unsupported_effect — kondycja
    `sleeping` istnieje w katalogu, więc czar wchodzi ścieżką effect."""
    tmp = _fresh_db("_c4_1433a.db")
    _add_spell(tmp, "sleep", tier=2, mana_cost=3, spell_type="effect",
               effect_type="sleeping", effect_stat="WIS")
    _learn(tmp, "sleep", rank=1)
    _write_combat(tmp)
    with patch("app.services.combat_service.apply_condition_to_combatant",
               return_value={"ok": True, "reason": "applied"}):
        res = _cast(tmp, "sleep", 15)
    assert res.get("block_reason") != "unsupported_effect", res
    assert res.get("spell_type") == "effect", res


def test_defense_ooc_blocked_or_prebuff():
    """Czar obronny rzucony POZA walką → ValueError (zablokowany jak attack/effect);
    NIE zostawia śmiecia (goły string) w sheet['conditions'] i nie traci many."""
    tmp = _fresh_db("_c4_1433b.db")
    _add_spell(tmp, "ward_of_iron", tier=1, mana_cost=3, spell_type="defense")
    _learn(tmp, "ward_of_iron", rank=1)
    for c in _ctx(tmp):
        c.start()
    try:
        with pytest.raises(ValueError):
            spell_service.cast_spell_out_of_combat(1, "ward_of_iron")
    finally:
        for c in _ctx(tmp):
            c.stop()
    sheet = _read_char_sheet(tmp)
    assert "ward_of_iron" not in (sheet.get("conditions") or [])
    assert sheet.get("current_mana") == 10  # mana nietknięta


def test_spell_zero_mana_cost_respected():
    """Czar z legalnym mana_cost=0 w walce NIE jest wyceniany na 2 (falsy 0 → fallback).
    Mana gracza po rzucie bez zmian."""
    tmp = _fresh_db("_c4_1433c.db")
    _add_spell(tmp, "free_bolt", tier=1, mana_cost=0, spell_type="attack", damage_die="1d6")
    _learn(tmp, "free_bolt", rank=1)
    _write_combat(tmp)
    res = _cast(tmp, "free_bolt", 15)
    assert res.get("hit") is True, res
    assert int(res.get("mana_spent") or 0) == 0, res
    assert _read_char_sheet(tmp).get("current_mana") == 10
