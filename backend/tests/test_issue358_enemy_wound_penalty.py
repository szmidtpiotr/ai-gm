"""TDD: Issue #358 — C5 wound_penalty dla wrogów: niski HP → malus do rzutu ataku."""
import sys
import os
import json
import sqlite3
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch


# ─── DB helper ───────────────────────────────────────────────────────────────

def _make_combat_db(enemy_hp_current: int, enemy_hp_max: int, attack_bonus: int = 2) -> str:
    """Create a minimal SQLite DB with one active combat. Returns file path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("""
        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL UNIQUE,
            character_id INTEGER NOT NULL,
            round INTEGER NOT NULL DEFAULT 1,
            turn_order TEXT NOT NULL,
            current_turn TEXT NOT NULL,
            combatants TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            ended_reason TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            location_tag TEXT DEFAULT NULL,
            loot_persisted INTEGER NOT NULL DEFAULT 0,
            post_combat_loot_json TEXT,
            loot_pool TEXT DEFAULT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE combat_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            combat_id INTEGER NOT NULL,
            campaign_id INTEGER NOT NULL,
            turn_number REAL NOT NULL,
            actor TEXT NOT NULL,
            event_type TEXT NOT NULL,
            roll_value INTEGER,
            damage INTEGER,
            hp_after INTEGER,
            target_id TEXT,
            target_name TEXT,
            hit INTEGER,
            narrative TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            user_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL DEFAULT 'Test',
            system_id TEXT NOT NULL DEFAULT 'v1',
            sheet_json TEXT NOT NULL,
            location TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            gold INTEGER NOT NULL DEFAULT 0,
            gold_gp INTEGER NOT NULL DEFAULT 0,
            hero_status TEXT NOT NULL DEFAULT 'active',
            visited_location_keys TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'idle'
        )
    """)

    sheet = json.dumps({
        "archetype": "warrior",
        "level": 1,
        "current_hp": 30,
        "max_hp": 30,
        "stats": {
            "STR": 12, "DEX": 10, "CON": 12,
            "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10,
        },
    })
    conn.execute(
        "INSERT INTO characters (id, user_id, name, system_id, sheet_json) VALUES (1, 1, 'Hero', 'v1', ?)",
        (sheet,),
    )

    combatants = json.dumps([
        {
            "id": "player",
            "type": "player",
            "name": "Hero",
            "hp_current": 30,
            "hp_max": 30,
            "defense": 12,
            "zone": "engaged",
        },
        {
            "id": "goblin_1",
            "type": "enemy",
            "name": "Goblin",
            "enemy_key": "goblin",
            "hp_current": enemy_hp_current,
            "hp_max": enemy_hp_max,
            "attack_bonus": attack_bonus,
            "defense": 10,
            "damage_dice": "1d6",
            "dex_modifier": 0,
            "zone": "engaged",
        },
    ])
    conn.execute(
        """INSERT INTO active_combat
           (campaign_id, character_id, round, turn_order, current_turn, combatants)
           VALUES (1, 1, 1, '["goblin_1", "player"]', 'goblin_1', ?)""",
        (combatants,),
    )
    conn.commit()
    conn.close()
    return tmp.name


def _run_enemy_attack(db_path: str, raw_d20: int = 10):
    """Patch DB path + dice, then run enemy resolve_attack. Returns out dict."""
    import app.services.combat_service as cs

    def _fake_roll():
        return raw_d20

    with (
        patch.object(cs, "COMBAT_DB_PATH", db_path),
        patch("app.services.combat_service.roll_d20", _fake_roll),
        patch("app.services.combat_service.evaluate_current_turn_conditions",
              return_value={"blocked": False, "events": [], "actor_id": "goblin_1"}),
        patch("app.services.combat_service.load_combat_snapshot", return_value=None),
        patch("app.services.combat_service.end_combat", return_value=None),
    ):
        return cs.resolve_attack(campaign_id=1, roll_result=None, attacker="enemy")


# ─── Test 1: wound_penalty key exists in enemy attack result ─────────────────

def test_enemy_attack_result_has_wound_penalty_key():
    """resolve_attack(enemy) musi zawierać klucz wound_penalty w wyniku."""
    db = _make_combat_db(enemy_hp_current=20, enemy_hp_max=100)  # <25% → -4
    try:
        result = _run_enemy_attack(db)
        assert "wound_penalty" in result, (
            f"Brak klucza 'wound_penalty' w wyniku ataku wroga. Klucze: {list(result.keys())}"
        )
    finally:
        os.unlink(db)


# ─── Test 2: critically wounded enemy (<25% HP) → -4 penalty ─────────────────

def test_critically_wounded_enemy_penalty_minus4():
    """Wróg z <25% HP → wound_penalty == -4."""
    db = _make_combat_db(enemy_hp_current=20, enemy_hp_max=100)  # 20% HP
    try:
        result = _run_enemy_attack(db)
        assert result["wound_penalty"] == -4, (
            f"Oczekiwano -4, dostaliśmy {result.get('wound_penalty')}"
        )
    finally:
        os.unlink(db)


# ─── Test 3: penalty actually reduces attack_roll ─────────────────────────────

def test_critically_wounded_enemy_attack_roll_reduced():
    """Wróg z <25% HP: attack_roll == raw + bonus + (-4)."""
    attack_bonus = 2
    raw = 10
    db = _make_combat_db(enemy_hp_current=20, enemy_hp_max=100, attack_bonus=attack_bonus)
    try:
        result = _run_enemy_attack(db, raw_d20=raw)
        expected = raw + attack_bonus + (-4)   # 10 + 2 - 4 = 8
        assert result["attack_roll"] == expected, (
            f"Oczekiwano attack_roll={expected}, dostaliśmy {result.get('attack_roll')}"
        )
    finally:
        os.unlink(db)


# ─── Test 4: lightly wounded enemy (26-50% HP) → -2 penalty ─────────────────

def test_lightly_wounded_enemy_penalty_minus2():
    """Wróg z 26-50% HP → wound_penalty == -2."""
    db = _make_combat_db(enemy_hp_current=40, enemy_hp_max=100)  # 40% HP
    try:
        result = _run_enemy_attack(db)
        assert result["wound_penalty"] == -2, (
            f"Oczekiwano -2, dostaliśmy {result.get('wound_penalty')}"
        )
    finally:
        os.unlink(db)


# ─── Test 5: moderately wounded enemy (51-75% HP) → -1 penalty ───────────────

def test_moderately_wounded_enemy_penalty_minus1():
    """Wróg z 51-75% HP → wound_penalty == -1."""
    db = _make_combat_db(enemy_hp_current=60, enemy_hp_max=100)  # 60% HP
    try:
        result = _run_enemy_attack(db)
        assert result["wound_penalty"] == -1, (
            f"Oczekiwano -1, dostaliśmy {result.get('wound_penalty')}"
        )
    finally:
        os.unlink(db)


# ─── Test 6: full HP enemy → no penalty ──────────────────────────────────────

def test_full_hp_enemy_no_penalty():
    """Wróg z pełnym HP → wound_penalty == 0."""
    db = _make_combat_db(enemy_hp_current=100, enemy_hp_max=100)
    try:
        result = _run_enemy_attack(db)
        assert result["wound_penalty"] == 0, (
            f"Oczekiwano 0, dostaliśmy {result.get('wound_penalty')}"
        )
    finally:
        os.unlink(db)


# ─── Test 7: full HP enemy attack_roll unaffected ────────────────────────────

def test_full_hp_enemy_attack_roll_unmodified():
    """Wróg z pełnym HP: attack_roll == raw + bonus (bez modyfikatora)."""
    attack_bonus = 2
    raw = 10
    db = _make_combat_db(enemy_hp_current=100, enemy_hp_max=100, attack_bonus=attack_bonus)
    try:
        result = _run_enemy_attack(db, raw_d20=raw)
        expected = raw + attack_bonus  # 10 + 2 = 12
        assert result["attack_roll"] == expected, (
            f"Oczekiwano attack_roll={expected}, dostaliśmy {result.get('attack_roll')}"
        )
    finally:
        os.unlink(db)


# ─── Test 8: wound_penalty respects hp_max=0 guard ───────────────────────────

def test_enemy_with_zero_hp_max_no_crash():
    """Wróg z hp_max=0 nie crash — wound_penalty == 0 (guard)."""
    db = _make_combat_db(enemy_hp_current=0, enemy_hp_max=0)
    try:
        result = _run_enemy_attack(db)
        assert result.get("wound_penalty") == 0
    finally:
        os.unlink(db)
