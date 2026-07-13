"""TDD: Issue #1374 follow-up — założone bronie/zbroje bez trwałości.

Defekt: przedmioty wprowadzone do ekwipunku ścieżką omijającą init trwałości
(admin cheat, craft, seed setu, klon scenariusza) miały durability_max=NULL →
modal/lista nie pokazywały paska trwałości, a mechanika zużycia ich nie widziała.

Test sprawdza `_ensure_char_durability` — self-heal nadający pełną trwałość
broni i zbroi z NULL, z pominięciem reliktów/materiałów/konsumabli.
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from _fixtures_schema import table_sql

from app.services.loot_service import _ensure_char_durability  # noqa: E402


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT,
            slot TEXT, equipped INTEGER NOT NULL DEFAULT 0,
            durability_current INTEGER, durability_max INTEGER
        );
        CREATE TABLE game_items (
            key TEXT PRIMARY KEY, kind TEXT, rarity INTEGER DEFAULT 1,
            weapon_data TEXT, is_active INTEGER DEFAULT 1
        );
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_items") + """
        INSERT INTO game_items (key, kind, rarity) VALUES
            ('cloak', 'armor', 2), ('dagger', 'weapon', 2), ('totem', 'item', 2);
        INSERT INTO game_config_weapons (key, rarity, durability_base) VALUES
            ('dagger', 2, NULL), ('staff', 1, 100);
        INSERT INTO game_config_items (key, item_type, rarity) VALUES
            ('cloak', 'armor', 2), ('totem', 'relic', 2);
        """
    )
    c.commit()
    yield c
    c.close()


def _dur(conn, inv_id):
    r = conn.execute(
        "SELECT durability_current, durability_max FROM character_inventory WHERE id = ?",
        (inv_id,),
    ).fetchone()
    return (r["durability_current"], r["durability_max"])


def test_armor_and_weapon_get_full_durability(conn):
    conn.execute("INSERT INTO character_inventory (id, character_id, item_key, equipped) VALUES (1, 7, 'cloak', 1)")
    conn.execute("INSERT INTO character_inventory (id, character_id, weapon_key, equipped) VALUES (2, 7, 'dagger', 1)")
    conn.commit()
    n = _ensure_char_durability(conn, 7)
    assert n == 2
    assert _dur(conn, 1) == (150, 150)  # armor rarity 2 → 150
    assert _dur(conn, 2) == (150, 150)  # weapon rarity 2, brak durability_base → 150


def test_relic_and_material_stay_untracked(conn):
    conn.execute("INSERT INTO character_inventory (id, character_id, item_key, equipped) VALUES (3, 7, 'totem', 1)")
    conn.commit()
    n = _ensure_char_durability(conn, 7)
    assert n == 0
    assert _dur(conn, 3) == (None, None)


def test_weapon_durability_base_from_catalog(conn):
    # staff istnieje tylko w game_config_weapons z durability_base=100.
    conn.execute("INSERT INTO game_items (key, kind, rarity) VALUES ('staff', 'weapon', 1)")
    conn.execute("INSERT INTO character_inventory (id, character_id, weapon_key, equipped) VALUES (4, 7, 'staff', 1)")
    conn.commit()
    _ensure_char_durability(conn, 7)
    assert _dur(conn, 4) == (100, 100)


def test_idempotent_and_preserves_worn_values(conn):
    conn.execute("INSERT INTO character_inventory (id, character_id, weapon_key, equipped, durability_current, durability_max) VALUES (5, 7, 'dagger', 1, 61, 100)")
    conn.commit()
    n = _ensure_char_durability(conn, 7)
    assert n == 0  # already has durability_max → nietknięte
    assert _dur(conn, 5) == (61, 100)
