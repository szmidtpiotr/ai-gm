"""#1192 FAZA TW — TW8 integracja: towarzysz bojowy w prawdziwym silniku walki.

Cel: advance_turn ROZWIĄZUJE turę towarzysza serwerowo (auto-atak) i NIGDY nie
zwraca current_turn='companion_*' (bo front kieruje nie-gracza do /enemy-turn,
który 400-uje na nie-wrogu → zawieszenie kolejki). Enemy bierze obrażenia,
current_turn wraca do gracza/wroga, HP synced na końcu walki.
"""
import json
import sqlite3

import pytest

import app.services.combat_service as combat
from app.migrations_admin import _ensure_companions_schema
from app.services import companion_service as cs


@pytest.fixture
def combat_db(tmp_path, monkeypatch):
    db = str(tmp_path / "combat.db")
    monkeypatch.setattr(combat, "COMBAT_DB_PATH", db)
    monkeypatch.setattr(cs, "DB_PATH", db)
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL UNIQUE,
            character_id INTEGER NOT NULL, round INTEGER NOT NULL DEFAULT 1,
            turn_order TEXT NOT NULL, current_turn TEXT NOT NULL, combatants TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active', ended_reason TEXT,
            created_at TEXT, updated_at TEXT, location_tag TEXT, loot_pool TEXT,
            boss_defeated INTEGER DEFAULT 0, ammo_spent_json TEXT, combat_turn_deadline TEXT
        );
        CREATE TABLE combat_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
            turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER,
            hp_after INTEGER, target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
            created_at TEXT
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER, name TEXT,
            system_id TEXT, sheet_json TEXT DEFAULT '{}', gold_gp INTEGER DEFAULT 0
        );
        """
    )
    _ensure_companions_schema(c)
    c.execute("INSERT INTO characters (id, name, system_id, sheet_json, gold_gp) "
              "VALUES (1,'Hero','fantasy','{}',100)")
    c.commit()
    # neutralize world-state side effects (separate narrative DB in prod)
    monkeypatch.setattr(combat, "set_world_state_flags", lambda *a, **k: None)
    return c


def _seed_combat(c, combatants, turn_order, current):
    c.execute(
        "INSERT INTO active_combat (campaign_id, character_id, round, turn_order, current_turn, combatants, status) "
        "VALUES (1,1,1,?,?,?, 'active')",
        (json.dumps(turn_order), current, json.dumps(combatants)),
    )
    c.commit()


def _companion(hp=10):
    return {"id": "companion_1", "type": "companion", "owner_id": "player",
            "companion_row_id": 1, "companion_key": "mercenary", "name": "Najemnik",
            "hp_current": hp, "hp_max": hp, "defense": 11, "attack_bonus": 3,
            "damage_dice": "1d6", "conditions": [], "zone": "engaged",
            "stats": {"STR": 12, "DEX": 12, "CON": 12, "INT": 8, "WIS": 10, "CHA": 8}}


def _player():
    return {"id": "player", "type": "player", "name": "Hero", "hp_current": 20,
            "hp_max": 20, "defense": 12, "zone": "engaged", "conditions": []}


def _enemy(hp=30, eid="goblin_01"):
    return {"id": eid, "type": "enemy", "enemy_key": "goblin", "name": "Goblin",
            "hp_current": hp, "hp_max": hp, "defense": 8, "attack_bonus": 2,
            "damage_dice": "1d4", "zone": "engaged", "conditions": []}


def test_advance_never_stops_on_companion(combat_db):
    # order: player → companion → enemy. Player just acted → advance should auto-run
    # companion's turn and land on the enemy, never returning 'companion_1'.
    _seed_combat(combat_db,
                 [_player(), _companion(), _enemy()],
                 ["player", "companion_1", "goblin_01"], "player")
    result = combat.advance_turn(1)
    assert result == "goblin_01", f"expected enemy turn, got {result!r}"
    row = combat_db.execute("SELECT current_turn FROM active_combat WHERE campaign_id=1").fetchone()
    assert row["current_turn"] == "goblin_01"


def test_companion_damages_enemy(combat_db):
    _seed_combat(combat_db,
                 [_player(), _companion(), _enemy(hp=30)],
                 ["player", "companion_1", "goblin_01"], "player")
    # Force a guaranteed hit + fixed damage for determinism.
    import app.services.combat_service as c
    c_roll = iter([15])  # companion d20
    # roll_d20 used for the attack; patch to a hit
    orig_d20 = c.roll_d20
    c.roll_d20 = lambda *a, **k: 15
    c.roll_damage_dice = lambda expr, mod=0: 5
    try:
        combat.advance_turn(1)
    finally:
        c.roll_d20 = orig_d20
    combatants = json.loads(
        combat_db.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()["combatants"])
    goblin = next(x for x in combatants if x["id"] == "goblin_01")
    assert goblin["hp_current"] == 25, "companion attack should reduce enemy HP by 5"
    # a companion_attack event was logged
    n = combat_db.execute("SELECT COUNT(*) FROM combat_turns WHERE event_type='companion_attack'").fetchone()[0]
    assert n == 1


def test_companion_kill_triggers_victory(combat_db):
    # Real character_companions row so HP-sync on victory has something to write.
    cs.hire(combat_db, 1, "mercenary")  # → row id 1
    _seed_combat(combat_db,
                 [_player(), _companion(), _enemy(hp=3)],
                 ["player", "companion_1", "goblin_01"], "player")
    import app.services.combat_service as c
    c.roll_d20 = lambda *a, **k: 15
    c.roll_damage_dice = lambda expr, mod=0: 5
    result = combat.advance_turn(1)
    assert result == "ended"
    row = combat_db.execute("SELECT status, ended_reason FROM active_combat WHERE campaign_id=1").fetchone()
    assert row["status"] == "ended" and row["ended_reason"] == "victory"
    # HP synced back: companion survived → active with its HP
    comp = combat_db.execute(
        "SELECT state, current_hp FROM character_companions WHERE id=1").fetchone()
    assert comp["state"] == "active"
