"""TDD: Issue #614 — FAZA S / S19: kondycja `hidden` (untargetable + ambush_bonus).

Pokrywa:
- dwa nowe, schema-zgodne typy efektów: `untargetable` (aktor pomijany przy wyborze celu)
  i `ambush_bonus` (+Nk6 do pierwszego ataku, value=kość); nowe top-level klucze
  `granted_by: {skill, dc}` i `detect_dc`,
- walidacja: ambush_bonus wymaga value-kości; granted_by.dc z zamka {8,12,16,20,24}; seed `hidden` waliduje się,
- helper `_combatant_is_untargetable` — True dla gracza z hidden, False bez,
- ENEMY: gracz z hidden jest untargetable — wróg NIE atakuje (HP gracza bez zmian), próbuje wykryć,
- ENEMY detekcja: nat 20 WIS save zdejmuje hidden (gracz wykryty),
- PLAYER: atak z hidden dolicza +2k6 RAZ (oddzielny add po mnożniku) i zdejmuje hidden,
- drugi atak (już bez hidden) — brak bonusu zasadzki,
- nat 20 gracza: zasadzka NIE podwaja się (oddzielny add, nie mnożona na cricie),
- wejście: skill_service `_match_grantable_condition` zwraca ('hidden', 14) dla stealth; pending dostaje grants_condition_self,
- `add_condition_to_character` nakłada hidden na sheet + combatanta gracza,
- backward compat: wróg bez kondycji atakuje normalnie nie-ukrytego gracza.

Rzuty ataku w walce (nat 20/nat 1, podwójne obrażenia) NIETYKALNE — zasadzka to oddzielny add po mnożniku.
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
from app.services import skill_service as ss
from app.services.admin_config import validate_effect_json_payload


# ─── effect_json kontrakt (identyczny z seedem) ────────────────────────────────

HIDDEN = {
    "schema_version": 1, "effect_category": "character_condition",
    "effects": [
        {"type": "untargetable"},
        {"type": "ambush_bonus", "value": "2d6"},
    ],
    "granted_by": {"skill": "stealth", "dc": 14},
    "detect_dc": 14,
}


# ─── 1. Schemat U10 akceptuje nowe typy + seed ─────────────────────────────────

class TestSchema:
    def test_hidden_validates(self):
        assert validate_effect_json_payload(HIDDEN) == []

    def test_untargetable_minimal_validates(self):
        ok = {"schema_version": 1, "effect_category": "character_condition",
              "effects": [{"type": "untargetable"}]}
        assert validate_effect_json_payload(ok) == []

    def test_ambush_bonus_requires_dice_value(self):
        bad = {"schema_version": 1, "effect_category": "character_condition",
               "effects": [{"type": "ambush_bonus", "value": "potato"}]}
        assert validate_effect_json_payload(bad) != []

    def test_ambush_bonus_numeric_value_ok(self):
        ok = {"schema_version": 1, "effect_category": "character_condition",
              "effects": [{"type": "ambush_bonus", "value": 5}]}
        assert validate_effect_json_payload(ok) == []

    def test_granted_by_dc_must_be_positive_int(self):
        bad = json.loads(json.dumps(HIDDEN))
        bad["granted_by"]["dc"] = "fourteen"  # nie-int = błąd
        assert validate_effect_json_payload(bad) != []

    def test_granted_by_intermediate_dc_ok(self):
        ok = json.loads(json.dumps(HIDDEN))
        ok["granted_by"]["dc"] = 14  # próg pośredni dozwolony (design doc)
        assert validate_effect_json_payload(ok) == []

    def test_granted_by_bad_skill(self):
        bad = json.loads(json.dumps(HIDDEN))
        bad["granted_by"]["skill"] = "Not A Key"
        assert validate_effect_json_payload(bad) != []

    def test_detect_dc_must_be_int(self):
        bad = json.loads(json.dumps(HIDDEN))
        bad["detect_dc"] = "soon"
        assert validate_effect_json_payload(bad) != []


# ─── DB fixtures (real-engine combat) ──────────────────────────────────────────

def _schema_sql() -> str:
    sheet = {
        "stats": {"STR": 14, "DEX": 16, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
        "current_hp": 30, "max_hp": 30, "defense": {"base": 15},
        "equipped_weapon": "dagger", "conditions": [],
    }
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")

    def j(d):
        return json.dumps(d, ensure_ascii=False).replace("'", "''")

    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'S19','fantasy','m',1);
    CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
      name TEXT, system_id TEXT, sheet_json TEXT);
    INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
      VALUES (1,1,1,'Aldric','fantasy','{sj}');
    {table_sql("game_config_weapons")}
    INSERT INTO game_config_weapons (key,label,damage_die,linked_stat,allowed_classes,weapon_type)
      VALUES ('dagger','Sztylet','1d4','DEX','rogue','melee');
    {table_sql("game_config_enemies")}
    INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,dex_modifier,damage_die,drop_chance,skills_json,stats_json)
      VALUES ('bandit','Bandit',40,8,2,0,'1d6',0.0,'{{}}','{{"WIS":10}}');
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
def s19_db(tmp_path):
    db = tmp_path / "s19.db"
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


def _has_hidden(combatant) -> bool:
    return any(str(c.get("key") or "").lower() == "hidden"
               for c in (combatant.get("conditions") or []))


# ─── 2. Helper _combatant_is_untargetable ──────────────────────────────────────

class TestUntargetableHelper:
    def test_player_with_hidden_is_untargetable(self):
        pc = {"id": "player", "type": "player", "conditions": []}
        _add_condition(pc, "hidden", HIDDEN)
        assert cs._combatant_is_untargetable(pc) is True

    def test_plain_player_not_untargetable(self):
        pc = {"id": "player", "type": "player", "conditions": []}
        assert cs._combatant_is_untargetable(pc) is False


# ─── 3. ENEMY nie atakuje ukrytego gracza (untargetable) ───────────────────────

class TestEnemySkipsHidden:
    def test_enemy_cannot_damage_hidden_player(self, s19_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        en = _enemies(snap)[0]
        en["zone"] = "engaged"
        _player(snap)["zone"] = "engaged"
        _add_condition(_player(snap), "hidden", HIDDEN)
        _set_combatants(s19_db, snap["combatants"], current_turn=en["id"])
        # WIS detect fails (roll 5) → gracz pozostaje ukryty, brak ataku.
        with patch.object(cs, "roll_d20", return_value=5):
            out = cs.resolve_attack(1, 0, attacker="enemy")
        snap2 = cs.get_active_combat(1)
        assert int(_player(snap2)["hp_current"]) == 30, "ukryty gracz nie powinien dostać obrażeń"
        assert out.get("detection") is not None, "wróg powinien podjąć próbę wykrycia"
        assert out["detection"].get("detected") is False
        assert _has_hidden(_player(snap2)) is True

    def test_enemy_nat20_detects_and_reveals(self, s19_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        en = _enemies(snap)[0]
        en["zone"] = "engaged"
        _player(snap)["zone"] = "engaged"
        _add_condition(_player(snap), "hidden", HIDDEN)
        _set_combatants(s19_db, snap["combatants"], current_turn=en["id"])
        with patch.object(cs, "roll_d20", return_value=20):  # auto-success detekcji
            out = cs.resolve_attack(1, 0, attacker="enemy")
        assert out.get("detection", {}).get("detected") is True
        snap2 = cs.get_active_combat(1)
        assert _has_hidden(_player(snap2)) is False, "wykrycie powinno zdjąć hidden"


# ─── 4. PLAYER zasadzka: +2k6 raz, atak zdejmuje hidden ────────────────────────

class TestAmbush:
    def test_first_attack_gets_ambush_and_consumes(self, s19_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        _enemies(snap)[0]["zone"] = "engaged"
        _player(snap)["zone"] = "engaged"
        _add_condition(_player(snap), "hidden", HIDDEN)
        _set_combatants(s19_db, snap["combatants"], current_turn="player")
        # roll_damage_dice: 1. broń = 4, 2. zasadzka 2k6 = 7. roll_d20 = dodge (1 → fumble → trafienie).
        with patch.object(cs, "roll_d20", return_value=1), \
             patch.object(cs, "roll_damage_dice", side_effect=[4, 7]):
            out = cs.resolve_attack(1, 25, attacker="player", raw_d20=15)
        assert out.get("hit") is True, out
        assert int(out.get("ambush_bonus") or 0) == 7, out
        assert int(out.get("damage") or 0) >= 4 + 7, out
        snap2 = cs.get_active_combat(1)
        assert _has_hidden(_player(snap2)) is False, "atak powinien zdjąć hidden"

    def test_second_attack_no_ambush(self, s19_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        _enemies(snap)[0]["zone"] = "engaged"
        _player(snap)["zone"] = "engaged"
        # gracz NIE jest ukryty (drugi atak)
        _set_combatants(s19_db, snap["combatants"], current_turn="player")
        with patch.object(cs, "roll_d20", return_value=1), \
             patch.object(cs, "roll_damage_dice", side_effect=[4]):
            out = cs.resolve_attack(1, 25, attacker="player", raw_d20=15)
        assert not out.get("ambush_bonus"), "bez hidden nie ma zasadzki"

    def test_ambush_not_doubled_on_crit(self, s19_db):
        """nat20 gracza podwaja obrażenia broni, ale NIE zasadzkę (oddzielny add po mnożniku)."""
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        _enemies(snap)[0]["zone"] = "engaged"
        _player(snap)["zone"] = "engaged"
        _add_condition(_player(snap), "hidden", HIDDEN)
        _set_combatants(s19_db, snap["combatants"], current_turn="player")
        # broń = 4 → ×2 (crit) = 8; zasadzka = 7 (NIE podwajana) → razem 15.
        with patch.object(cs, "roll_d20", return_value=1), \
             patch.object(cs, "roll_damage_dice", side_effect=[4, 7]):
            out = cs.resolve_attack(1, 25, attacker="player", raw_d20=20)
        assert int(out.get("ambush_bonus") or 0) == 7, out
        assert int(out.get("damage_multiplier") or 1) == 2, out
        # zasadzka doliczona po mnożniku: 8 (broń×2) + 7 = 15.
        assert int(out.get("damage") or 0) == 15, out


# ─── 5. Wejście: grant przez udany SKILL_TEST stealth ──────────────────────────

class TestGrantViaSkill:
    def _grant_db(self, tmp_path):
        db = tmp_path / "grant.db"
        conn = sqlite3.connect(str(db))
        conn.executescript(f"""
            CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT);
            INSERT INTO characters (id, sheet_json) VALUES (1, '{{"conditions":[]}}');
            """ + table_sql("game_config_conditions") + f"""
            INSERT INTO game_config_conditions (key, effect_json, is_active)
              VALUES ('hidden', '{json.dumps(HIDDEN).replace("'", "''")}', 1);
        """)
        conn.commit()
        return conn

    def test_match_grantable_returns_hidden_for_stealth(self, tmp_path):
        conn = self._grant_db(tmp_path)
        key, dc = ss._match_grantable_condition(conn, "stealth")
        assert key == "hidden"
        assert dc == 14

    def test_match_grantable_none_for_other_skill(self, tmp_path):
        conn = self._grant_db(tmp_path)
        key, dc = ss._match_grantable_condition(conn, "athletics")
        assert key is None


# ─── 6. add_condition_to_character — nakłada hidden na sheet + combat ───────────

class TestAddCondition:
    def test_add_condition_writes_combat_and_sheet(self, s19_db):
        cs.initiate_combat(1, 1, ["bandit"])
        with sqlite3.connect(str(s19_db)) as conn:
            n = cs.add_condition_to_character(conn, 1, 1, "hidden")
        assert n >= 1
        snap = cs.get_active_combat(1)
        assert _has_hidden(_player(snap)) is True


# ─── 7. Backward compat — wróg bez kondycji atakuje normalnie ──────────────────

class TestBackwardCompat:
    def test_plain_enemy_attacks_non_hidden_player(self, s19_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        en = _enemies(snap)[0]
        en["zone"] = "engaged"
        _player(snap)["zone"] = "engaged"
        _set_combatants(s19_db, snap["combatants"], current_turn=en["id"])
        with patch.object(cs, "roll_d20", return_value=18):
            out = cs.resolve_attack(1, 0, attacker="enemy")
        snap2 = cs.get_active_combat(1)
        assert int(_player(snap2)["hp_current"]) < 30, "zwykły wróg powinien trafić gracza"
        assert out.get("detection") is None
