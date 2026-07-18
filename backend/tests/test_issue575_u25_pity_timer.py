"""TDD: Issue #575 — U25 Pity timer afiksów (drop boss-kill + reroll u craftera).

Acceptance (game_mechanics.md CZĘŚĆ AH §U25):
- Drop: licznik boss-killów bez afiksowanej broni per postać; po 3 bez afiksu →
  4. drop broni gwarantowanie z afiksem T1+ (licznik reset po dropie z afiksem).
- Reroll: po 3 rerollach tego samego przedmiotu bez zmiany afiksu → 4. reroll
  gwarantuje INNY afiks niż obecny (reset po zmianie).
- Liczniki w tabeli affix_pity — przeżywają restart (zapis w DB, nie w pamięci).
"""
import sys
sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import json
import random
import sqlite3
import pytest

from app.services import affix_pity_service as pity
from app.services.loot_service import roll_weapon_affixes
from app.services.crafter_service import reroll_affix


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        """ + table_sql("game_config_affixes") + """
        INSERT INTO game_config_affixes VALUES ('sharp', 'Ostry',  1, 'weapon', '{}', 1);
        INSERT INTO game_config_affixes VALUES ('swift', 'Zwinny', 1, 'weapon', '{}', 1);
        INSERT INTO game_config_affixes VALUES ('keen',  'Wyostrzony', 2, 'weapon', '{}', 1);
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def craft_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (id INTEGER PRIMARY KEY, gold_gp INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            weapon_key TEXT, item_key TEXT, consumable_key TEXT,
            quantity INTEGER DEFAULT 1, equipped INTEGER DEFAULT 0,
            affixes_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, delta INTEGER, source TEXT, meta_json TEXT
        );
        """ + table_sql("game_config_affixes") + """
        -- exactly two T1 affixes so excluding the current one leaves exactly one candidate
        INSERT INTO game_config_affixes VALUES ('sharp', 'Ostry',  1, 'weapon', '{}', 1);
        INSERT INTO game_config_affixes VALUES ('swift', 'Zwinny', 1, 'weapon', '{}', 1);
        INSERT INTO characters VALUES (1, 100000);
        INSERT INTO character_inventory (character_id, weapon_key, affixes_json)
            VALUES (1, 'sword', '["sharp"]');
    """)
    conn.commit()
    yield conn
    conn.close()


def _affixes(conn, inv_id):
    row = conn.execute("SELECT affixes_json FROM character_inventory WHERE id=?", (inv_id,)).fetchone()
    return json.loads(row["affixes_json"] or "[]")


# ─── DROP pity: licznik bossów ─────────────────────────────────────────────────

def test_boss_drop_not_guaranteed_below_threshold(db):
    """Poniżej progu (domyślnie 3) gwarancja afiksu NIE jest aktywna."""
    pity.record_boss_drop(db, 1, got_affix=False)
    pity.record_boss_drop(db, 1, got_affix=False)
    assert pity.boss_drop_guaranteed(db, 1) is False


def test_boss_drop_guaranteed_after_three_misses(db):
    """3 boss-kille bez afiksu → 4. drop broni ma gwarancję afiksu."""
    for _ in range(3):
        pity.record_boss_drop(db, 1, got_affix=False)
    assert pity.boss_drop_guaranteed(db, 1) is True


def test_boss_drop_counter_resets_on_affix(db):
    """Drop z afiksem zeruje licznik bossa."""
    for _ in range(3):
        pity.record_boss_drop(db, 1, got_affix=False)
    pity.record_boss_drop(db, 1, got_affix=True)
    assert pity.get_counter(db, 1, "boss_drop") == 0
    assert pity.boss_drop_guaranteed(db, 1) is False


def test_force_affix_guarantees_one_even_for_poor_tier(db):
    """roll_weapon_affixes(force_min_one=True) daje ≥1 afiks T1 nawet bez loot_tier."""
    random.seed(1)
    rolled = roll_weapon_affixes(None, db, force_min_one=True)
    assert len(rolled) >= 1
    assert rolled[0] in ("sharp", "swift")


def test_no_force_no_affix_for_poor_tier(db):
    """Bez force i bez loot_tier afiksów brak — gwarancja działa TYLKO przez pity."""
    random.seed(1)
    assert roll_weapon_affixes(None, db, force_min_one=False) == []


def test_counter_persists_in_table_not_memory(db):
    """Licznik zapisany w tabeli affix_pity (przeżywa restart)."""
    pity.record_boss_drop(db, 1, got_affix=False)
    row = db.execute(
        "SELECT counter FROM affix_pity WHERE character_id=1 AND scope='boss_drop'"
    ).fetchone()
    assert row is not None and int(row["counter"]) == 1


# ─── REROLL pity: licznik na przedmiot ──────────────────────────────────────────

def test_reroll_not_guaranteed_below_threshold(db):
    pity.record_reroll(db, 1, inv_id=10, changed=False)
    pity.record_reroll(db, 1, inv_id=10, changed=False)
    assert pity.reroll_guaranteed_different(db, 1, 10) is False


def test_reroll_guaranteed_different_after_three_no_change(db):
    """3 rerolle bez zmiany → 4. reroll gwarantuje inny afiks."""
    for _ in range(3):
        pity.record_reroll(db, 1, inv_id=10, changed=False)
    assert pity.reroll_guaranteed_different(db, 1, 10) is True


def test_reroll_counter_resets_on_change(db):
    for _ in range(3):
        pity.record_reroll(db, 1, inv_id=10, changed=False)
    pity.record_reroll(db, 1, inv_id=10, changed=True)
    assert pity.reroll_guaranteed_different(db, 1, 10) is False


def test_reroll_pity_is_per_item(db):
    """Liczniki rerolla są niezależne per inventory_id."""
    for _ in range(3):
        pity.record_reroll(db, 1, inv_id=10, changed=False)
    assert pity.reroll_guaranteed_different(db, 1, 11) is False


# ─── REROLL integration: crafter wymusza inny afiks po pity ─────────────────────

def test_reroll_forces_different_key_when_pity_active(craft_db):
    """4. reroll (po 3 bez zmiany) MUSI dać inny klucz niż obecny ('sharp')."""
    # prime: 3 rerolls without change recorded for this item (inv_id=1)
    for _ in range(3):
        pity.record_reroll(craft_db, 1, inv_id=1, changed=False)
    assert pity.reroll_guaranteed_different(craft_db, 1, 1) is True
    # current affix is 'sharp'; pool {sharp,swift} → exclusion leaves only 'swift'
    result = reroll_affix(craft_db, 1, 1, affix_key="sharp")
    assert result["ok"] is True
    assert _affixes(craft_db, 1) == ["swift"]  # guaranteed different
    # successful change resets the per-item counter
    assert pity.reroll_guaranteed_different(craft_db, 1, 1) is False


# ─── Backward compat ────────────────────────────────────────────────────────────

def test_roll_weapon_affixes_legacy_signature(db):
    """Stare wywołanie roll_weapon_affixes(tier, conn) nadal działa (poor → [])."""
    assert roll_weapon_affixes("poor", db) == []


def test_reroll_without_pity_unchanged(craft_db):
    """Bez aktywnego pity reroll zachowuje dotychczasowe zachowanie (klucz z puli T1)."""
    random.seed(3)
    result = reroll_affix(craft_db, 1, 1, affix_key="sharp")
    assert result["ok"] is True
    assert _affixes(craft_db, 1)[0] in ("sharp", "swift")
