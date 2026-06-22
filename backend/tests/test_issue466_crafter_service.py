"""TDD: Issue #466 — F6 crafter_service: apply/reroll/upgrade affixes via NPC rzemieślnik.

Acceptance:
- apply_affix(conn, char_id, inv_id, tier) → adds affix key to affixes_json, deducts gold
- reroll_affix(conn, char_id, inv_id, affix_key) → replaces affix with new one of same tier, deducts gold
- upgrade_affix(conn, char_id, inv_id, affix_key) → replaces with tier+1 affix, deducts gold
- Costs: apply T1=150g T2=500g T3=1200g | reroll T1=100g T2=350g T3=700g | upgrade T1→T2=350g T2→T3=700g
- Insufficient gold → (False, reason)
"""
import sys
sys.path.insert(0, "/app")

import json
import random
import sqlite3
import pytest
from app.services.crafter_service import (
    APPLY_COSTS,
    REROLL_COSTS,
    UPGRADE_COSTS,
    apply_affix,
    reroll_affix,
    upgrade_affix,
)


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            gold_gp INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            weapon_key TEXT,
            item_key TEXT,
            consumable_key TEXT,
            quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0,
            affixes_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            delta INTEGER,
            source TEXT,
            meta_json TEXT,
            game_clock_day INTEGER DEFAULT 1,
            reverted_at TEXT
        );
        CREATE TABLE game_config_affixes (
            key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier INTEGER NOT NULL DEFAULT 1,
            allowed_item_types TEXT NOT NULL DEFAULT 'weapon',
            effect_json TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        -- Affix catalog: T1, T2, T3
        INSERT INTO game_config_affixes VALUES ('sharp',    'Ostry',     1, 'weapon', '{}', 1);
        INSERT INTO game_config_affixes VALUES ('swift',    'Zwinny',    1, 'weapon', '{}', 1);
        INSERT INTO game_config_affixes VALUES ('keen',     'Wyostrzony',2, 'weapon', '{}', 1);
        INSERT INTO game_config_affixes VALUES ('forceful', 'Mocny',     2, 'weapon', '{}', 1);
        INSERT INTO game_config_affixes VALUES ('brutal',   'Brutalny',  3, 'weapon', '{}', 1);
        INSERT INTO game_config_affixes VALUES ('deadly',   'Śmiertelny',3, 'weapon', '{}', 1);

        -- Character with 2000 gold
        INSERT INTO characters VALUES (1, 2000);

        -- Weapon inventory slot with no affixes
        INSERT INTO character_inventory (character_id, weapon_key, affixes_json)
            VALUES (1, 'sword', '[]');
        -- Weapon with one T1 affix
        INSERT INTO character_inventory (character_id, weapon_key, affixes_json)
            VALUES (1, 'axe', '["sharp"]');
        -- Weapon with T2 affix
        INSERT INTO character_inventory (character_id, weapon_key, affixes_json)
            VALUES (1, 'mace', '["keen"]');
    """)
    conn.commit()
    yield conn
    conn.close()


def _get_affixes(db, inv_id):
    row = db.execute("SELECT affixes_json FROM character_inventory WHERE id = ?", (inv_id,)).fetchone()
    return json.loads(row["affixes_json"] or "[]")

def _get_gold(db, char_id=1):
    return db.execute("SELECT gold_gp FROM characters WHERE id = ?", (char_id,)).fetchone()["gold_gp"]


# ─── Cost constants ───────────────────────────────────────────────────────────

def test_apply_costs_correct():
    """Apply costs: T1=150, T2=500, T3=1200."""
    assert APPLY_COSTS[1] == 150
    assert APPLY_COSTS[2] == 500
    assert APPLY_COSTS[3] == 1200


def test_reroll_costs_correct():
    """Reroll costs: T1=200, T2=650, T3=1500 (updated after cost rebalance)."""
    assert REROLL_COSTS[1] == 200
    assert REROLL_COSTS[2] == 650
    assert REROLL_COSTS[3] == 1500


def test_upgrade_costs_correct():
    """Upgrade costs: T1→T2=350, T2→T3=700."""
    assert UPGRADE_COSTS[1] == 350
    assert UPGRADE_COSTS[2] == 700


# ─── apply_affix ──────────────────────────────────────────────────────────────

def test_apply_affix_t1_adds_key(db):
    """Apply T1 affix: affix key appears in affixes_json."""
    random.seed(42)
    result = apply_affix(db, 1, 1, tier=1)  # inv_id=1: sword with no affixes
    assert result["ok"] is True
    affixes = _get_affixes(db, 1)
    assert len(affixes) == 1
    assert affixes[0] in ("sharp", "swift")  # only T1 affixes


def test_apply_affix_deducts_t1_cost(db):
    """Applying T1 affix deducts 150 gold."""
    apply_affix(db, 1, 1, tier=1)
    assert _get_gold(db) == 2000 - 150


def test_apply_affix_t2_costs_500(db):
    """Applying T2 affix deducts 500 gold."""
    apply_affix(db, 1, 1, tier=2)
    assert _get_gold(db) == 2000 - 500


def test_apply_affix_t3_costs_1200(db):
    """Applying T3 affix deducts 1200 gold."""
    apply_affix(db, 1, 1, tier=3)
    assert _get_gold(db) == 2000 - 1200


def test_apply_affix_journals_gold_loss(db):
    """Gold deduction written to character_gold_log."""
    apply_affix(db, 1, 1, tier=1)
    log = db.execute(
        "SELECT delta, source FROM character_gold_log WHERE character_id = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert log["delta"] == -150
    assert "craft" in log["source"] or "affix" in log["source"]


def test_apply_affix_insufficient_gold(db):
    """Insufficient gold → ok=False, gold unchanged."""
    db.execute("UPDATE characters SET gold_gp = 10 WHERE id = 1")
    db.commit()
    result = apply_affix(db, 1, 1, tier=1)
    assert result["ok"] is False
    assert _get_gold(db) == 10  # unchanged


def test_apply_affix_returns_applied_key(db):
    """Result contains the affix key that was applied."""
    random.seed(0)
    result = apply_affix(db, 1, 1, tier=1)
    assert "affix_key" in result
    assert result["affix_key"] in ("sharp", "swift")


# ─── reroll_affix ─────────────────────────────────────────────────────────────

def test_reroll_affix_replaces_key(db):
    """Reroll 'sharp' (T1) → new T1 affix key in its place."""
    random.seed(7)
    result = reroll_affix(db, 1, 2, affix_key="sharp")  # inv_id=2: axe with ['sharp']
    assert result["ok"] is True
    affixes = _get_affixes(db, 2)
    assert len(affixes) == 1
    assert affixes[0] in ("sharp", "swift")  # T1 pool


def test_reroll_affix_deducts_t1_cost(db):
    """Rerolling T1 affix deducts 200 gold."""
    reroll_affix(db, 1, 2, affix_key="sharp")
    assert _get_gold(db) == 2000 - 200


def test_reroll_affix_t2_costs_650(db):
    """Rerolling T2 affix deducts 650 gold."""
    reroll_affix(db, 1, 3, affix_key="keen")  # inv_id=3: mace with ['keen'] T2
    assert _get_gold(db) == 2000 - 650


def test_reroll_nonexistent_affix(db):
    """Rerolling affix not on item → ok=False."""
    result = reroll_affix(db, 1, 1, affix_key="sharp")  # inv_id=1 has no affixes
    assert result["ok"] is False


def test_reroll_affix_insufficient_gold(db):
    """Not enough gold for reroll → ok=False, affixes unchanged."""
    db.execute("UPDATE characters SET gold_gp = 5 WHERE id = 1")
    db.commit()
    result = reroll_affix(db, 1, 2, affix_key="sharp")
    assert result["ok"] is False
    assert _get_affixes(db, 2) == ["sharp"]  # unchanged


# ─── upgrade_affix ────────────────────────────────────────────────────────────

def test_upgrade_affix_t1_to_t2(db):
    """Upgrade 'sharp' (T1) → T2 affix replaces it."""
    random.seed(1)
    result = upgrade_affix(db, 1, 2, affix_key="sharp")  # axe with ['sharp']
    assert result["ok"] is True
    affixes = _get_affixes(db, 2)
    assert len(affixes) == 1
    # New affix should be T2
    new_key = affixes[0]
    row = db.execute("SELECT tier FROM game_config_affixes WHERE key = ?", (new_key,)).fetchone()
    assert row["tier"] == 2


def test_upgrade_affix_t1_costs_350(db):
    """T1→T2 upgrade costs 350 gold."""
    upgrade_affix(db, 1, 2, affix_key="sharp")
    assert _get_gold(db) == 2000 - 350


def test_upgrade_affix_t2_to_t3(db):
    """Upgrade 'keen' (T2) → T3 affix replaces it."""
    random.seed(2)
    result = upgrade_affix(db, 1, 3, affix_key="keen")  # mace with ['keen']
    assert result["ok"] is True
    affixes = _get_affixes(db, 3)
    new_key = affixes[0]
    row = db.execute("SELECT tier FROM game_config_affixes WHERE key = ?", (new_key,)).fetchone()
    assert row["tier"] == 3


def test_upgrade_affix_t2_costs_700(db):
    """T2→T3 upgrade costs 700 gold."""
    upgrade_affix(db, 1, 3, affix_key="keen")
    assert _get_gold(db) == 2000 - 700


def test_upgrade_t3_affix_fails(db):
    """Cannot upgrade T3 affix — already max tier."""
    db.execute("UPDATE character_inventory SET affixes_json = '[\"brutal\"]' WHERE id = 1")
    db.commit()
    result = upgrade_affix(db, 1, 1, affix_key="brutal")
    assert result["ok"] is False


def test_upgrade_affix_insufficient_gold(db):
    """Not enough gold → ok=False, affixes unchanged."""
    db.execute("UPDATE characters SET gold_gp = 50 WHERE id = 1")
    db.commit()
    result = upgrade_affix(db, 1, 2, affix_key="sharp")
    assert result["ok"] is False
    assert _get_affixes(db, 2) == ["sharp"]


# ─── Backward compat ──────────────────────────────────────────────────────────

def test_existing_affixes_json_preserved(db):
    """apply_affix appends — does not wipe existing affixes."""
    db.execute("UPDATE character_inventory SET affixes_json = '[\"sharp\"]' WHERE id = 1")
    db.commit()
    random.seed(5)
    apply_affix(db, 1, 1, tier=2)
    affixes = _get_affixes(db, 1)
    assert "sharp" in affixes  # original preserved
    assert len(affixes) == 2    # new T2 added
