"""TDD: Issue #613 — FAZA S / S18: prymityw `behavior_override` + pełne `confused`/`berserk`/`panicked`.

Pokrywa:
- nowy, schema-zgodny typ efektu `behavior_override` (pole `behavior` ∈ {random_table_k4,
  attack_nearest, flee}) waliduje się U10; seedy confused/berserk/panicked walidują się,
- walidacja: behavior_override wymaga `behavior` z enuma; zła/brakująca wartość = błąd,
- forced_behavior aktora bieżącej tury wyznaczany generycznie (zero `if condition_key ==`):
  random_table_k4 → k4 (1 stoi / 2 atak losowy / 3 ucieczka / 4 normalnie),
  attack_nearest → atak najbliższego, flee → ucieczka,
- ENEMY: berserk atakuje najbliższego **niezależnie od frakcji** — w walce 2 wrogów bije
  drugiego wroga (nowa ścieżka obrażeń wróg→wróg + obsługa śmierci celu),
- ENEMY: panicked → zmiana strefy na ranged (ucieczka),
- ENEMY: confused k4=1 stoi (brak obrażeń), k4=4 normalnie (atakuje gracza),
- berserk: +3 atak / +3 obrażenia foldują się w atak wroga (static_stat_modifier attack_bonus/damage_bonus),
- PLAYER: forced_behavior wystawiany na turze gracza (banner + k4, tura nie przejęta w całości),
- backward compat: wróg bez kondycji atakuje gracza normalnie (charakteryzacja, zero regresji).

Rzuty ataku w walce (nat 20/nat 1, podwójne obrażenia) NIETYKALNE — to zadanie nie dotyka rzutu ataku gracza.
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
from app.services.admin_config import validate_effect_json_payload


# ─── effect_json kontrakty (identyczne z seedem) ───────────────────────────────

CONFUSED = {
    "schema_version": 1, "effect_category": "character_condition",
    "effects": [
        {"type": "static_stat_modifier", "stat": "INT", "value": -3},
        {"type": "static_stat_modifier", "stat": "WIS", "value": -3},
        {"type": "behavior_override", "behavior": "random_table_k4"},
        {"type": "periodic_save", "stat": "WIS", "value": 14, "tick": "start_turn", "expires": "save_success"},
    ],
}
BERSERK = {
    "schema_version": 1, "effect_category": "character_condition",
    "effects": [
        {"type": "behavior_override", "behavior": "attack_nearest", "expires": "duration_rounds:6"},
        {"type": "static_stat_modifier", "stat": "attack_bonus", "value": 3},
        {"type": "static_stat_modifier", "stat": "damage_bonus", "value": 3},
        {"type": "static_stat_modifier", "stat": "ac", "value": -3},
        {"type": "periodic_save", "stat": "WIS", "value": 14, "tick": "start_turn", "expires": "save_success"},
    ],
}
PANICKED = {
    "schema_version": 1, "effect_category": "character_condition",
    "effects": [
        {"type": "static_stat_modifier", "stat": "CHA", "value": -4},
        {"type": "static_stat_modifier", "stat": "WIS", "value": -4},
        {"type": "behavior_override", "behavior": "flee"},
        {"type": "periodic_save", "stat": "WIS", "value": 14, "tick": "start_turn", "expires": "save_success"},
    ],
}


# ─── 1. Schemat U10 akceptuje nowy typ + seedy ─────────────────────────────────

class TestSchema:
    def test_confused_validates(self):
        assert validate_effect_json_payload(CONFUSED) == []

    def test_berserk_validates(self):
        assert validate_effect_json_payload(BERSERK) == []

    def test_panicked_validates(self):
        assert validate_effect_json_payload(PANICKED) == []

    def test_behavior_override_requires_behavior(self):
        bad = {
            "schema_version": 1, "effect_category": "character_condition",
            "effects": [{"type": "behavior_override"}],
        }
        assert validate_effect_json_payload(bad) != []

    def test_behavior_override_bad_value_rejected(self):
        bad = {
            "schema_version": 1, "effect_category": "character_condition",
            "effects": [{"type": "behavior_override", "behavior": "teleport"}],
        }
        assert validate_effect_json_payload(bad) != []

    def test_behavior_override_each_valid_value(self):
        for b in ("random_table_k4", "attack_nearest", "flee"):
            ok = {
                "schema_version": 1, "effect_category": "character_condition",
                "effects": [{"type": "behavior_override", "behavior": b}],
            }
            assert validate_effect_json_payload(ok) == [], b


# ─── DB fixtures ───────────────────────────────────────────────────────────────

def _schema_sql(extra_enemy: bool = False) -> str:
    sheet = {
        "stats": {"STR": 14, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
        "current_hp": 30, "max_hp": 30, "defense": {"base": 15},
        "equipped_weapon": "sword", "conditions": [],
    }
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")

    def j(d):
        return json.dumps(d, ensure_ascii=False).replace("'", "''")

    enemy_rows = (
        "INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,dex_modifier,damage_die,drop_chance,skills_json)\n"
        "  VALUES ('bandit','Bandit',40,8,2,0,'1d6',0.0,'{}'),\n"
        "         ('thug','Thug',40,8,2,0,'1d6',0.0,'{}');"
    )
    return f"""
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT);
    INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'u','x','U');
    CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
      owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active');
    INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'S18','fantasy','m',1);
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
    {enemy_rows}
    CREATE TABLE game_config_conditions (key TEXT PRIMARY KEY, label TEXT, effect_json TEXT,
      description TEXT, is_active INTEGER DEFAULT 1, stackable INTEGER NOT NULL DEFAULT 0);
    INSERT INTO game_config_conditions (key,label,effect_json,description,is_active,stackable)
      VALUES ('confused','Zdezorientowany','{j(CONFUSED)}','Dezorientacja.',1,0),
             ('berserk','Berserk','{j(BERSERK)}','Szał.',1,0),
             ('panicked','Spanikowany','{j(PANICKED)}','Panika.',1,0);
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
def s18_db(tmp_path):
    db = tmp_path / "s18.db"
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


# ─── 2. forced_behavior wyznaczany generycznie ─────────────────────────────────

class TestForcedBehavior:
    def test_berserk_enemy_forced_attack_nearest(self, s18_db):
        cs.initiate_combat(1, 1, ["bandit", "thug"])
        snap = cs.get_active_combat(1)
        en = _enemies(snap)[0]
        _add_condition(en, "berserk", BERSERK)
        _set_combatants(s18_db, snap["combatants"], current_turn=en["id"])
        with patch.object(cs, "roll_d20", return_value=10):  # WIS save fails → berserk survives
            out = cs.evaluate_current_turn_conditions(1)
        fb = out.get("forced_behavior")
        assert fb and fb.get("action") == "attack_nearest", out

    def test_panicked_enemy_forced_flee(self, s18_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        en = _enemies(snap)[0]
        _add_condition(en, "panicked", PANICKED)
        _set_combatants(s18_db, snap["combatants"], current_turn=en["id"])
        with patch.object(cs, "roll_d20", return_value=10):
            out = cs.evaluate_current_turn_conditions(1)
        fb = out.get("forced_behavior")
        assert fb and fb.get("action") == "flee", out

    def test_confused_k4_maps_each_value(self, s18_db):
        mapping = {1: "stand", 2: "attack_random", 3: "flee", 4: "normal"}
        for roll, expected in mapping.items():
            cs.initiate_combat(1, 1, ["bandit"])
            snap = cs.get_active_combat(1)
            en = _enemies(snap)[0]
            _add_condition(en, "confused", CONFUSED)
            _set_combatants(s18_db, snap["combatants"], current_turn=en["id"])
            with patch.object(cs, "roll_d20", return_value=10), \
                 patch.object(cs, "_roll_k4", return_value=roll):
                out = cs.evaluate_current_turn_conditions(1)
            fb = out.get("forced_behavior")
            assert fb and fb.get("action") == expected, (roll, out)

    def test_no_behavior_override_no_forced(self, s18_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        _set_combatants(s18_db, snap["combatants"], current_turn=_enemies(snap)[0]["id"])
        out = cs.evaluate_current_turn_conditions(1)
        assert not out.get("forced_behavior")

    def test_save_success_removes_then_no_forced(self, s18_db):
        """Udany rzut WIS zdejmuje kondycję → brak forced_behavior (otrzeźwienie)."""
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        en = _enemies(snap)[0]
        _add_condition(en, "berserk", BERSERK)
        _set_combatants(s18_db, snap["combatants"], current_turn=en["id"])
        with patch.object(cs, "roll_d20", return_value=20):  # auto-success WIS save
            out = cs.evaluate_current_turn_conditions(1)
        assert not out.get("forced_behavior")


# ─── 3. ENEMY berserk atakuje drugiego wroga (nowa ścieżka wróg→wróg) ──────────

class TestBerserkAttacksAlly:
    def test_berserk_enemy_hits_other_enemy(self, s18_db):
        cs.initiate_combat(1, 1, ["bandit", "thug"])
        snap = cs.get_active_combat(1)
        ens = _enemies(snap)
        attacker, victim = ens[0], ens[1]
        # Berserker i ofiara w tej samej strefie; gracz w innej → najbliższy = drugi wróg.
        attacker["zone"] = "engaged"
        victim["zone"] = "engaged"
        _player(snap)["zone"] = "ranged"
        _add_condition(attacker, "berserk", BERSERK)
        _set_combatants(s18_db, snap["combatants"], current_turn=attacker["id"])
        victim_hp_before = int(victim["hp_current"])
        with patch.object(cs, "roll_d20", return_value=10):  # save fail + atak trafia (AC 8)
            out = cs.resolve_attack(1, 0, attacker="enemy")
        # Cel ataku to drugi wróg, nie gracz.
        assert str(out.get("target_id") or "") == victim["id"], out
        snap2 = cs.get_active_combat(1)
        victim2 = next(c for c in snap2["combatants"] if c["id"] == victim["id"])
        assert int(victim2["hp_current"]) < victim_hp_before, "ofiara-wróg powinna stracić HP"
        # Gracz nietknięty.
        assert int(_player(snap2)["hp_current"]) == 30


# ─── 4. ENEMY panicked → zmiana strefy (ucieczka) ──────────────────────────────

class TestPanickedFlee:
    def test_panicked_enemy_switches_to_ranged(self, s18_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        en = _enemies(snap)[0]
        en["zone"] = "engaged"
        _player(snap)["zone"] = "engaged"
        _add_condition(en, "panicked", PANICKED)
        _set_combatants(s18_db, snap["combatants"], current_turn=en["id"])
        with patch.object(cs, "roll_d20", return_value=10):
            cs.resolve_attack(1, 0, attacker="enemy")
        snap2 = cs.get_active_combat(1)
        assert _enemies(snap2)[0].get("zone") == "ranged", "spanikowany wróg powinien uciec do ranged"
        # Gracz nietknięty (ucieczka nie atakuje).
        assert int(_player(snap2)["hp_current"]) == 30


# ─── 5. ENEMY confused k4 (1 stoi / 4 normalnie) ───────────────────────────────

class TestConfusedK4:
    def test_k4_stand_no_damage(self, s18_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        en = _enemies(snap)[0]
        _add_condition(en, "confused", CONFUSED)
        _set_combatants(s18_db, snap["combatants"], current_turn=en["id"])
        with patch.object(cs, "roll_d20", return_value=10), patch.object(cs, "_roll_k4", return_value=1):
            cs.resolve_attack(1, 0, attacker="enemy")
        snap2 = cs.get_active_combat(1)
        assert int(_player(snap2)["hp_current"]) == 30, "k4=1 (stoi) nie powinno zadać obrażeń"

    def test_k4_normal_attacks_player(self, s18_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        en = _enemies(snap)[0]
        en["zone"] = "engaged"
        _player(snap)["zone"] = "engaged"
        _add_condition(en, "confused", CONFUSED)
        _set_combatants(s18_db, snap["combatants"], current_turn=en["id"])
        with patch.object(cs, "roll_d20", return_value=18), patch.object(cs, "_roll_k4", return_value=4):
            out = cs.resolve_attack(1, 0, attacker="enemy")
        # k4=4 → normalnie: atakuje gracza.
        assert str(out.get("target_id") or "player") == "player"
        snap2 = cs.get_active_combat(1)
        assert int(_player(snap2)["hp_current"]) < 30, "k4=4 (normalnie) wróg atakuje gracza"


# ─── 6. PLAYER forced_behavior wystawiany (banner + k4) ────────────────────────

class TestPlayerForcedBehavior:
    def test_player_confused_surfaces_forced_behavior(self, s18_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        _add_condition(_player(snap), "confused", CONFUSED)
        _set_combatants(s18_db, snap["combatants"], current_turn="player")
        with patch.object(cs, "roll_d20", return_value=10), patch.object(cs, "_roll_k4", return_value=2):
            out = cs.evaluate_current_turn_conditions(1)
        fb = out.get("forced_behavior")
        assert fb and fb.get("actor_id") == "player"
        assert fb.get("action") in {"stand", "attack_random", "flee", "normal"}


# ─── 7. Backward compat — wróg bez kondycji atakuje gracza normalnie ───────────

class TestBackwardCompat:
    def test_plain_enemy_attacks_player(self, s18_db):
        cs.initiate_combat(1, 1, ["bandit"])
        snap = cs.get_active_combat(1)
        en = _enemies(snap)[0]
        en["zone"] = "engaged"
        _player(snap)["zone"] = "engaged"
        _set_combatants(s18_db, snap["combatants"], current_turn=en["id"])
        with patch.object(cs, "roll_d20", return_value=18):
            out = cs.resolve_attack(1, 0, attacker="enemy")
        snap2 = cs.get_active_combat(1)
        assert int(_player(snap2)["hp_current"]) < 30, "zwykły wróg powinien trafić gracza"
        assert "forced_behavior" not in out or not out.get("forced_behavior")
