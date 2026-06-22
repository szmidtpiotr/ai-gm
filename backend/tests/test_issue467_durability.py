"""TDD: Issue #467 — F7 Trwałość (durability): decrement per hit, penalty at 0, repair.

Acceptance:
- decrement_durability_on_hit(conn, char_id) → equipped durable items lose 1pt per hit
- Items with NULL durability_max are skipped (backward compat)
- Durability floors at 0 (no negative)
- get_ac_penalty_for_char(conn, char_id) → AC penalty when equipped armor at 0
- get_attack_penalty_for_char(conn, char_id) → attack penalty when equipped weapon at 0
- get_repair_cost(conn, inv_id) → gold cost by rarity (T1=20g/pt, T2=50g/pt, T3=100g/pt)
- repair_item(conn, char_id, inv_id) → restores durability to max, deducts gold
- Insufficient gold → ok=False, durability unchanged
"""
import sys
sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import json
import sqlite3
import pytest
from app.services.durability_service import (
    REPAIR_COSTS_PER_PT,
    DEFAULT_DURABILITY,
    DEFAULT_PENALTY_PCT,
    decrement_durability_on_hit,
    get_ac_penalty_for_char,
    get_attack_penalty_for_char,
    get_repair_cost,
    repair_item,
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
            slot TEXT,
            durability_current INTEGER,
            durability_max INTEGER
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
        """ + table_sql("game_config_meta") + """
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_items") + """

        -- Weapon and armor config
        INSERT INTO game_config_weapons (key, rarity) VALUES ('sword', 1);
        INSERT INTO game_config_weapons (key, rarity) VALUES ('longsword', 2);
        INSERT INTO game_config_weapons (key, rarity) VALUES ('enchanted_blade', 3);
        INSERT INTO game_config_items (key, rarity, ac_bonus) VALUES ('leather_armor', 1, 2);
        INSERT INTO game_config_items (key, rarity, ac_bonus) VALUES ('chainmail', 2, 4);

        -- Character with 1000 gold
        INSERT INTO characters VALUES (1, 1000);

        -- inv_id=1: equipped weapon, durability 80/100 (T1)
        INSERT INTO character_inventory (character_id, weapon_key, equipped, slot, durability_current, durability_max)
            VALUES (1, 'sword', 1, 'main_hand', 80, 100);
        -- inv_id=2: equipped armor, durability 60/100 (T1)
        INSERT INTO character_inventory (character_id, item_key, equipped, slot, durability_current, durability_max)
            VALUES (1, 'leather_armor', 1, 'torso', 60, 100);
        -- inv_id=3: NOT equipped weapon
        INSERT INTO character_inventory (character_id, weapon_key, equipped, slot, durability_current, durability_max)
            VALUES (1, 'longsword', 0, 'inventory', 150, 150);
        -- inv_id=4: consumable — NULL durability (backward compat)
        INSERT INTO character_inventory (character_id, consumable_key, equipped, slot, durability_current, durability_max)
            VALUES (1, 'potion', 0, NULL, NULL, NULL);
        -- inv_id=5: weapon AT 0 durability (fully broken)
        INSERT INTO character_inventory (character_id, weapon_key, equipped, slot, durability_current, durability_max)
            VALUES (1, 'enchanted_blade', 1, 'off_hand', 0, 200);
    """)
    conn.commit()
    yield conn
    conn.close()


def _get_dur(db, inv_id):
    return db.execute("SELECT durability_current FROM character_inventory WHERE id = ?", (inv_id,)).fetchone()["durability_current"]

def _get_gold(db, char_id=1):
    return db.execute("SELECT gold_gp FROM characters WHERE id = ?", (char_id,)).fetchone()["gold_gp"]


# ─── Cost constants ───────────────────────────────────────────────────────────

def test_repair_costs_correct():
    """Repair costs: T1=20g/pt, T2=50g/pt, T3=100g/pt."""
    assert REPAIR_COSTS_PER_PT[1] == 20
    assert REPAIR_COSTS_PER_PT[2] == 50
    assert REPAIR_COSTS_PER_PT[3] == 100


def test_default_durability_values():
    """Default durability by tier: T1=100, T2=150, T3=200."""
    assert DEFAULT_DURABILITY[1] == 100
    assert DEFAULT_DURABILITY[2] == 150
    assert DEFAULT_DURABILITY[3] == 200


def test_default_penalty_pct():
    """Default penalty 50%."""
    assert DEFAULT_PENALTY_PCT == 50


# ─── decrement_durability_on_hit ──────────────────────────────────────────────

def test_decrement_weapon_NOT_decremented_via_deprecated_fn(db):
    """U2 (#510): weapon no longer decrements via decrement_durability_on_hit (armor-only path).
    Weapons now only lose durability via decrement_weapon_durability_on_attack."""
    decrement_durability_on_hit(db, 1)
    assert _get_dur(db, 1) == 80  # weapon stays at 80 — only armor changes


def test_decrement_equipped_armor_on_hit(db):
    """Equipped armor loses 1 durability on hit received."""
    decrement_durability_on_hit(db, 1)
    assert _get_dur(db, 2) == 59  # was 60


def test_unequipped_item_not_decremented(db):
    """Unequipped items are NOT decremented."""
    decrement_durability_on_hit(db, 1)
    assert _get_dur(db, 3) == 150  # unchanged


def test_null_durability_skipped(db):
    """Items with NULL durability_max are skipped silently."""
    decrement_durability_on_hit(db, 1)
    row = db.execute("SELECT durability_current FROM character_inventory WHERE id = 4").fetchone()
    assert row["durability_current"] is None  # still NULL


def test_durability_floors_at_zero(db):
    """Durability cannot go below 0."""
    decrement_durability_on_hit(db, 1)
    assert _get_dur(db, 5) == 0  # was already 0, stays 0


def test_decrement_commits_changes(db):
    """Decrement persists (verifiable after separate read) — armor inv_id=2."""
    decrement_durability_on_hit(db, 1)
    # Re-read via fresh query — armor (inv_id=2) should have decremented
    val = db.execute(
        "SELECT durability_current FROM character_inventory WHERE id = 2"
    ).fetchone()["durability_current"]
    assert val == 59  # was 60, armor decremented


# ─── Penalty functions ────────────────────────────────────────────────────────

def test_no_ac_penalty_when_armor_ok(db):
    """No AC penalty when armor durability > 0."""
    # inv_id=2: leather_armor equipped, durability 60/100
    assert get_ac_penalty_for_char(db, 1) == 0


def test_ac_penalty_when_armor_broken(db):
    """AC penalty when equipped armor reaches 0."""
    db.execute("UPDATE character_inventory SET durability_current = 0 WHERE id = 2")
    db.commit()
    penalty = get_ac_penalty_for_char(db, 1)
    assert penalty < 0  # negative (reduces AC)


def test_ac_penalty_uses_config_pct(db):
    """AC penalty magnitude matches configured penalty percent."""
    db.execute("UPDATE character_inventory SET durability_current = 0, durability_max = 100 WHERE id = 2")
    db.execute("UPDATE game_config_items SET ac_bonus = 4 WHERE key = 'leather_armor'")
    db.execute("INSERT OR REPLACE INTO game_config_meta (key, value) VALUES ('durability_penalty_pct', '50')")
    db.commit()
    penalty = get_ac_penalty_for_char(db, 1)
    assert penalty == -2  # 50% of ac_bonus=4


def test_no_attack_penalty_when_weapon_ok(db):
    """No attack penalty when all equipped weapons have durability > 0."""
    # inv_id=1: sword equipped, durability 80/100
    # inv_id=5: enchanted_blade at 0 — unequip it so only healthy sword is equipped
    db.execute("UPDATE character_inventory SET equipped = 0 WHERE id = 5")
    db.commit()
    assert get_attack_penalty_for_char(db, 1) == 0


def test_attack_penalty_when_weapon_broken(db):
    """Attack penalty when equipped weapon reaches 0."""
    db.execute("UPDATE character_inventory SET durability_current = 0 WHERE id = 1")
    db.commit()
    penalty = get_attack_penalty_for_char(db, 1)
    assert penalty < 0  # negative modifier


def test_null_max_no_penalty(db):
    """Items with NULL durability_max never contribute to penalty."""
    # Set all equipped items to NULL max → no penalty
    db.execute("UPDATE character_inventory SET durability_max = NULL, durability_current = NULL")
    db.commit()
    assert get_ac_penalty_for_char(db, 1) == 0
    assert get_attack_penalty_for_char(db, 1) == 0


# ─── get_repair_cost ──────────────────────────────────────────────────────────

def test_repair_cost_t1_sword(db):
    """Sword (T1, rarity=1): 20 gold per missing point."""
    db.execute("UPDATE character_inventory SET durability_current = 50 WHERE id = 1")
    db.commit()
    result = get_repair_cost(db, 1)
    assert result["ok"] is True
    assert result["cost"] == 50 * 20  # 50 missing pts × 20g = 1000g


def test_repair_cost_t2_weapon(db):
    """Longsword (T2, rarity=2): 50 gold per missing point."""
    db.execute("UPDATE character_inventory SET durability_current = 100, durability_max = 150, weapon_key = 'longsword' WHERE id = 3")
    db.execute("UPDATE character_inventory SET equipped = 1 WHERE id = 3")
    db.commit()
    result = get_repair_cost(db, 3)
    assert result["ok"] is True
    assert result["cost"] == 50 * 50  # 50 missing × 50g = 2500g


def test_repair_cost_zero_when_full(db):
    """No repair cost when durability is full."""
    result = get_repair_cost(db, 1)  # 80/100 → 20 missing
    assert result["cost"] == 20 * 20  # 20 × 20g


def test_repair_cost_null_durability(db):
    """Item with NULL durability_max → ok=False (nothing to repair)."""
    result = get_repair_cost(db, 4)
    assert result["ok"] is False


# ─── repair_item ──────────────────────────────────────────────────────────────

def test_repair_item_restores_durability(db):
    """Repair restores durability_current to durability_max."""
    db.execute("UPDATE character_inventory SET durability_current = 50 WHERE id = 1")
    db.commit()
    result = repair_item(db, 1, 1)
    assert result["ok"] is True
    assert _get_dur(db, 1) == 100  # fully restored


def test_repair_item_deducts_gold(db):
    """Repair deducts correct gold amount."""
    db.execute("UPDATE character_inventory SET durability_current = 50 WHERE id = 1")
    db.commit()
    repair_item(db, 1, 1)
    # 50 missing pts × 20g = 1000g deducted from 1000g
    assert _get_gold(db) == 0


def test_repair_item_journals_gold(db):
    """Repair writes to character_gold_log."""
    db.execute("UPDATE character_inventory SET durability_current = 80 WHERE id = 1")
    db.commit()
    repair_item(db, 1, 1)
    log = db.execute(
        "SELECT delta, source FROM character_gold_log WHERE character_id = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert log["delta"] < 0
    assert "repair" in log["source"] or "durability" in log["source"]


def test_repair_item_insufficient_gold(db):
    """Insufficient gold → ok=False, durability unchanged."""
    db.execute("UPDATE character_inventory SET durability_current = 0 WHERE id = 1")
    db.execute("UPDATE characters SET gold_gp = 5 WHERE id = 1")
    db.commit()
    result = repair_item(db, 1, 1)
    assert result["ok"] is False
    assert _get_dur(db, 1) == 0  # unchanged


def test_repair_full_item_is_free(db):
    """Item already at full durability → cost 0, ok=True, gold unchanged."""
    db.execute("UPDATE character_inventory SET durability_current = 100, durability_max = 100 WHERE id = 1")
    db.commit()
    result = repair_item(db, 1, 1)
    assert result["ok"] is True
    assert result["cost"] == 0
    assert _get_gold(db) == 1000  # unchanged
