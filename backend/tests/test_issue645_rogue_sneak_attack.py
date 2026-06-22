"""TDD: Issue #645 — B4 / FAZA B: Sneak Attack jako cecha klasy łotrzyka.

Decyzja D2 (Piotr 2026-06-15): sneak attack to CECHA KLASY łotrzyka — osobny,
dodatkowy add ponad generyczny `ambush_bonus` z kondycji `hidden` (S19 #614).

Pokrywa:
- helper `_sneak_attack_bonus(sheet)`: rzut kości TYLKO dla archetype 'rogue', inaczej 0,
- PLAYER łotrzyk atakujący z ukrycia (hidden) dolicza sneak attack PONAD ambush_bonus,
  jako oddzielne pole `sneak_attack` (raz, po mnożniku — NIE podwajany na nat20),
- wojownik/mag z ukrycia: tylko generyczny ambush, BRAK sneak attack,
- łotrzyk bez ukrycia: brak sneak attack (cecha wymaga okna zasadzki),
- backward compat: pole `ambush_bonus` i mechanika hidden niezmienione.

Wartość startowa kości sneak = 1d6 (Numbers Policy — tuning po B5/B13).
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


# ─── effect_json kontrakt hidden (identyczny z seedem S19) ─────────────────────

HIDDEN = {
    "schema_version": 1, "effect_category": "character_condition",
    "effects": [
        {"type": "untargetable"},
        {"type": "ambush_bonus", "value": "2d6"},
    ],
    "granted_by": {"skill": "stealth", "dc": 14},
    "detect_dc": 14,
}


# ─── DB fixtures (real-engine combat, sheet z archetype) ───────────────────────

def _schema_sql(archetype: str) -> str:
    sheet = {
        "archetype": archetype,
        "stats": {"STR": 14, "DEX": 16, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
        "current_hp": 30, "max_hp": 30, "defense": {"base": 15},
        "equipped_weapon": "blade", "conditions": [],
    }
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")

    def j(d):
        return json.dumps(d, ensure_ascii=False).replace("'", "''")

    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'B4','fantasy','m',1);
    CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
      name TEXT, system_id TEXT, sheet_json TEXT);
    INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
      VALUES (1,1,1,'Aldric','fantasy','{sj}');
    {table_sql("game_config_weapons")}
    INSERT INTO game_config_weapons (key,label,damage_die,linked_stat,allowed_classes,weapon_type)
      VALUES ('blade','Ostrze','1d6','DEX','warrior,rogue,scholar','melee');
    {table_sql("game_config_enemies")}
    INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,dex_modifier,damage_die,drop_chance,skills_json,stats_json)
      VALUES ('bandit','Bandit',60,8,2,0,'1d6',0.0,'{{}}','{{"WIS":10}}');
    {table_sql("game_config_conditions")}
    INSERT INTO game_config_conditions (key,label,effect_json,description,is_active,stackable)
      VALUES ('hidden','Ukryty','{j(HIDDEN)}','Ukrycie.',1,0);
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
def combat_db(tmp_path):
    """Factory: zbuduj DB z bohaterem o zadanym archetypie, wepnij COMBAT_DB_PATH."""
    patchers = []

    def _make(archetype: str):
        db = tmp_path / f"b4_{archetype}.db"
        conn = sqlite3.connect(str(db))
        try:
            conn.executescript(_schema_sql(archetype))
            conn.commit()
        finally:
            conn.close()
        p = patch.object(cs, "COMBAT_DB_PATH", str(db))
        p.start()
        patchers.append(p)
        return db

    try:
        yield _make
    finally:
        for p in patchers:
            p.stop()


def _player(snap):
    return next(c for c in snap["combatants"] if c["id"] == "player")


def _enemies(snap):
    return [c for c in snap["combatants"] if c.get("type") == "enemy"]


def _set_combatants(db, combatants, *, current_turn, round_n=1):
    with sqlite3.connect(str(db)) as c:
        c.execute(
            "UPDATE active_combat SET combatants=?, current_turn=?, round=? WHERE campaign_id=1",
            (json.dumps(combatants, ensure_ascii=False), str(current_turn), int(round_n)),
        )
        c.commit()


def _add_condition(combatant, key, effect_json):
    conds = combatant.get("conditions") or []
    conds.append({"key": key, "label": key.title(), "effect_json": json.dumps(effect_json),
                  "applied_at": "test", "runtime": {}})
    combatant["conditions"] = conds


def _attack_from_hidden(db, raw_d20, dice):
    """Ustaw gracza ukrytego, jego tura, wykonaj atak. dice = side_effect roll_damage_dice."""
    cs.initiate_combat(1, 1, ["bandit"])
    snap = cs.get_active_combat(1)
    _enemies(snap)[0]["zone"] = "engaged"
    _player(snap)["zone"] = "engaged"
    _add_condition(_player(snap), "hidden", HIDDEN)
    _set_combatants(db, snap["combatants"], current_turn="player")
    with patch.object(cs, "roll_d20", return_value=1), \
         patch.object(cs, "roll_damage_dice", side_effect=dice):
        return cs.resolve_attack(1, 25, attacker="player", raw_d20=raw_d20)


# ─── 1. Helper _sneak_attack_bonus — gate na archetype ─────────────────────────

class TestSneakHelper:
    def test_rogue_gets_sneak_dice(self):
        with patch.object(cs, "roll_damage_dice", return_value=5):
            assert cs._sneak_attack_bonus({"archetype": "rogue"}) == 5

    def test_warrior_gets_zero(self):
        with patch.object(cs, "roll_damage_dice", return_value=5):
            assert cs._sneak_attack_bonus({"archetype": "warrior"}) == 0

    def test_scholar_gets_zero(self):
        with patch.object(cs, "roll_damage_dice", return_value=5):
            assert cs._sneak_attack_bonus({"archetype": "scholar"}) == 0

    def test_missing_archetype_zero(self):
        assert cs._sneak_attack_bonus({}) == 0
        assert cs._sneak_attack_bonus(None) == 0


# ─── 2. PLAYER łotrzyk — sneak attack ponad ambush ─────────────────────────────

class TestRogueSneakAttack:
    def test_rogue_hidden_attack_adds_sneak_on_top_of_ambush(self, combat_db):
        db = combat_db("rogue")
        # roll_damage_dice: broń=4, ambush 2d6=7, sneak 1d6=3.
        out = _attack_from_hidden(db, raw_d20=15, dice=[4, 7, 3])
        assert out.get("hit") is True, out
        assert int(out.get("ambush_bonus") or 0) == 7, out
        assert int(out.get("sneak_attack") or 0) == 3, out
        # baza 4 + ambush 7 + sneak 3 = 14 (bez krytyka).
        assert int(out.get("damage") or 0) == 14, out

    def test_rogue_sneak_not_doubled_on_crit(self, combat_db):
        db = combat_db("rogue")
        # nat20: broń 4 → ×2 = 8; ambush 7 i sneak 3 doliczane PO mnożniku (płaskie).
        out = _attack_from_hidden(db, raw_d20=20, dice=[4, 7, 3])
        assert int(out.get("damage_multiplier") or 1) == 2, out
        assert int(out.get("sneak_attack") or 0) == 3, out
        assert int(out.get("ambush_bonus") or 0) == 7, out
        assert int(out.get("damage") or 0) == 8 + 7 + 3, out


# ─── 3. Inne klasy z ukrycia — tylko generyczny ambush, brak sneak ─────────────

class TestNonRogueNoSneak:
    def test_warrior_hidden_no_sneak(self, combat_db):
        db = combat_db("warrior")
        # broń=4, ambush 2d6=7. Brak rzutu sneak (helper zwraca 0 bez rzutu).
        out = _attack_from_hidden(db, raw_d20=15, dice=[4, 7])
        assert int(out.get("ambush_bonus") or 0) == 7, out
        assert not out.get("sneak_attack"), out
        assert int(out.get("damage") or 0) == 11, out

    def test_scholar_hidden_no_sneak(self, combat_db):
        db = combat_db("scholar")
        out = _attack_from_hidden(db, raw_d20=15, dice=[4, 7])
        assert not out.get("sneak_attack"), out


# ─── 4. Łotrzyk bez ukrycia — brak sneak (wymaga okna zasadzki) ────────────────

class TestRogueRequiresHidden:
    def test_rogue_not_hidden_no_sneak(self, combat_db):
        db = combat_db("rogue")
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        _enemies(snap)[0]["zone"] = "engaged"
        _player(snap)["zone"] = "engaged"
        # BRAK kondycji hidden.
        _set_combatants(db, snap["combatants"], current_turn="player")
        with patch.object(cs, "roll_d20", return_value=1), \
             patch.object(cs, "roll_damage_dice", side_effect=[4]):
            out = cs.resolve_attack(1, 25, attacker="player", raw_d20=15)
        assert not out.get("sneak_attack"), out
        assert not out.get("ambush_bonus"), out
