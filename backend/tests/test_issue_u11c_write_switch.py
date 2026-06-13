"""TDD U11c — dual-write: create_weapon/create_item also insert into game_items.

Tests verify that after U11c:
  - create_weapon() writes weapon to game_items (kind='weapon', weapon_data JSON)
  - create_item(item_type='armor') writes to game_items (kind='armor', item_data JSON)
  - create_item(item_type='consumable') writes to game_items (kind='consumable')
  - create_item(item_type='misc') writes to game_items (kind='item')
  - approve_entity('weapon', key) sets game_items.approved=1
  - approve_entity('item', key) sets game_items.approved=1
  - smart_entry _db_insert for game_config_weapons writes to game_items
  - old tables still populated (backward compat)
"""

import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, "/app")

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")

SUFFIX = str(int(time.time()) % 100000)


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cleanup(keys: list[str]):
    conn = _conn()
    for key in keys:
        conn.execute("DELETE FROM game_config_weapons WHERE key = ?", (key,))
        conn.execute("DELETE FROM game_config_items WHERE key = ?", (key,))
        conn.execute("DELETE FROM game_items WHERE key = ?", (key,))
    conn.commit()
    conn.close()


# ─── create_weapon dual-write ────────────────────────────────────────────────

def test_create_weapon_writes_to_game_items():
    """create_weapon() must insert into game_items (kind='weapon', weapon_data JSON)."""
    from app.services.admin_config import create_weapon
    key = f"test_u11c_weapon_{SUFFIX}"
    _cleanup([key])
    try:
        create_weapon(
            key=key,
            label="Miecz Testowy U11c",
            damage_die="1d8",
            weapon_type="melee",
            linked_stat="STR",
            allowed_classes=["warrior"],
            two_handed=False,
            finesse=False,
            range_m=None,
            targeting="single",
            aoe_radius_m=None,
            magic_school=None,
            value_gp=15,
            weight_kg=1.5,
            description="Testowa broń U11c",
            note=None,
            effect_json=None,
            weapon_slot="main_hand",
            is_active=True,
        )
        conn = _conn()
        row = conn.execute("SELECT * FROM game_items WHERE key = ?", (key,)).fetchone()
        conn.close()
        assert row is not None, f"game_items nie zawiera '{key}' po create_weapon()"
        assert row["kind"] == "weapon", f"kind={row['kind']!r}, oczekiwano 'weapon'"
        wdata = json.loads(row["weapon_data"] or "{}")
        assert wdata.get("damage_die") == "1d8", f"weapon_data.damage_die={wdata.get('damage_die')!r}"
        assert wdata.get("weapon_type") == "melee", f"weapon_data.weapon_type={wdata.get('weapon_type')!r}"
        assert wdata.get("linked_stat") == "STR", f"weapon_data.linked_stat={wdata.get('linked_stat')!r}"
    finally:
        _cleanup([key])


def test_create_weapon_still_writes_to_old_table():
    """create_weapon() must still insert into game_config_weapons (backward compat)."""
    from app.services.admin_config import create_weapon
    key = f"test_u11c_wcompat_{SUFFIX}"
    _cleanup([key])
    try:
        create_weapon(
            key=key,
            label="Broń Compat U11c",
            damage_die="1d6",
            weapon_type="melee",
            linked_stat="STR",
            allowed_classes=["warrior"],
            two_handed=False,
            finesse=False,
            range_m=None,
            targeting="single",
            aoe_radius_m=None,
            magic_school=None,
            value_gp=10,
            weight_kg=1.0,
            description="",
            note=None,
            effect_json=None,
            weapon_slot="main_hand",
            is_active=True,
        )
        conn = _conn()
        old = conn.execute("SELECT key FROM game_config_weapons WHERE key = ?", (key,)).fetchone()
        conn.close()
        assert old is not None, f"game_config_weapons nie zawiera '{key}' — backward compat zepsuta"
    finally:
        _cleanup([key])


# ─── create_item dual-write ──────────────────────────────────────────────────

def test_create_item_armor_writes_to_game_items():
    """create_item(item_type='armor') must insert into game_items (kind='armor')."""
    from app.services.admin_config import create_item
    key = f"test_u11c_armor_{SUFFIX}"
    _cleanup([key])
    try:
        create_item(
            key=key,
            label="Kolczuga Testowa U11c",
            item_type="armor",
            description="Testowa zbroja U11c",
            value_gp=50,
            weight_kg=5.0,
            ac_bonus=3,
            armor_coverage="torso",
            is_active=True,
        )
        conn = _conn()
        row = conn.execute("SELECT * FROM game_items WHERE key = ?", (key,)).fetchone()
        conn.close()
        assert row is not None, f"game_items nie zawiera '{key}' po create_item(armor)"
        assert row["kind"] == "armor", f"kind={row['kind']!r}, oczekiwano 'armor'"
        idata = json.loads(row["item_data"] or "{}")
        assert idata.get("ac_bonus") == 3, f"item_data.ac_bonus={idata.get('ac_bonus')!r}"
        assert idata.get("armor_coverage") == "torso"
    finally:
        _cleanup([key])


def test_create_item_misc_writes_to_game_items_as_item():
    """create_item(item_type='misc') must insert into game_items (kind='item')."""
    from app.services.admin_config import create_item
    key = f"test_u11c_misc_{SUFFIX}"
    _cleanup([key])
    try:
        create_item(
            key=key,
            label="Przedmiot Misc U11c",
            item_type="misc",
            description="Testowy misc U11c",
            value_gp=5,
            is_active=True,
        )
        conn = _conn()
        row = conn.execute("SELECT * FROM game_items WHERE key = ?", (key,)).fetchone()
        conn.close()
        assert row is not None, f"game_items nie zawiera '{key}' po create_item(misc)"
        assert row["kind"] == "item", f"kind={row['kind']!r}, oczekiwano 'item'"
    finally:
        _cleanup([key])


def test_create_item_consumable_writes_to_game_items():
    """create_item(item_type='consumable') must insert into game_items (kind='consumable')."""
    from app.services.admin_config import create_item
    key = f"test_u11c_cons_{SUFFIX}"
    _cleanup([key])
    try:
        create_item(
            key=key,
            label="Mikstury Testowa U11c",
            item_type="consumable",
            description="Testowa mikstura U11c",
            value_gp=8,
            charges=1,
            effect_type="heal_hp",
            effect_dice="1d6",
            effect_bonus=2,
            is_active=True,
        )
        conn = _conn()
        row = conn.execute("SELECT * FROM game_items WHERE key = ?", (key,)).fetchone()
        conn.close()
        assert row is not None, f"game_items nie zawiera '{key}' po create_item(consumable)"
        assert row["kind"] == "consumable", f"kind={row['kind']!r}, oczekiwano 'consumable'"
    finally:
        _cleanup([key])


def test_create_item_still_writes_to_old_table():
    """create_item() must still insert into game_config_items (backward compat)."""
    from app.services.admin_config import create_item
    key = f"test_u11c_icompat_{SUFFIX}"
    _cleanup([key])
    try:
        create_item(
            key=key,
            label="Item Compat U11c",
            item_type="misc",
            value_gp=1,
            is_active=True,
        )
        conn = _conn()
        old = conn.execute("SELECT key FROM game_config_items WHERE key = ?", (key,)).fetchone()
        conn.close()
        assert old is not None, f"game_config_items nie zawiera '{key}' — backward compat zepsuta"
    finally:
        _cleanup([key])


# ─── approve_entity syncs game_items.approved ───────────────────────────────

def test_approve_weapon_syncs_game_items_approved():
    """approve_entity('weapon', key) must also set game_items.approved=1."""
    from app.services.admin_config import create_weapon
    from app.services.world_service import approve_entity
    key = f"test_u11c_appw_{SUFFIX}"
    _cleanup([key])
    try:
        # Create weapon with approved=0 (pending) — need to bypass create_weapon default
        conn = _conn()
        conn.execute(
            """INSERT INTO game_config_weapons
               (key, label, weapon_type, damage_die, linked_stat, allowed_classes,
                description, ai_generated, approved, is_active, value_gp, weight_kg)
               VALUES (?, ?, 'melee', '1d6', 'STR', '[]', 'Pending', 1, 0, 1, 0, 1.0)""",
            (key, f"Pending Weapon {SUFFIX}"),
        )
        conn.execute(
            """INSERT OR IGNORE INTO game_items (key, kind, label, approved, weapon_data, item_data)
               VALUES (?, 'weapon', ?, 0, '{}', '{}')""",
            (key, f"Pending Weapon {SUFFIX}"),
        )
        conn.commit()
        conn.close()

        conn2 = _conn()
        approve_entity(conn2, "weapon", key)
        row = conn2.execute("SELECT approved FROM game_items WHERE key = ?", (key,)).fetchone()
        conn2.close()
        assert row is not None, f"game_items nie ma '{key}'"
        assert row["approved"] == 1, f"game_items.approved={row['approved']!r} po approve, oczekiwano 1"
    finally:
        _cleanup([key])


def test_approve_item_syncs_game_items_approved():
    """approve_entity('item', key) must also set game_items.approved=1."""
    from app.services.world_service import approve_entity
    key = f"test_u11c_appi_{SUFFIX}"
    _cleanup([key])
    try:
        conn = _conn()
        conn.execute(
            """INSERT INTO game_config_items
               (key, label, item_type, description, value_gp, ai_generated, approved, is_active)
               VALUES (?, ?, 'misc', 'Pending', 0, 1, 0, 1)""",
            (key, f"Pending Item {SUFFIX}"),
        )
        conn.execute(
            """INSERT OR IGNORE INTO game_items (key, kind, label, approved, weapon_data, item_data)
               VALUES (?, 'item', ?, 0, '{}', '{}')""",
            (key, f"Pending Item {SUFFIX}"),
        )
        conn.commit()
        conn.close()

        conn2 = _conn()
        approve_entity(conn2, "item", key)
        row = conn2.execute("SELECT approved FROM game_items WHERE key = ?", (key,)).fetchone()
        conn2.close()
        assert row is not None, f"game_items nie ma '{key}'"
        assert row["approved"] == 1, f"game_items.approved={row['approved']!r} po approve, oczekiwano 1"
    finally:
        _cleanup([key])


# ─── smart_entry _db_insert dual-write ──────────────────────────────────────

def test_smart_entry_db_insert_weapon_writes_to_game_items():
    """smart_entry._db_insert for game_config_weapons must also write to game_items."""
    from app.routers.smart_entry import _db_insert
    key = f"test_u11c_se_{SUFFIX}"
    _cleanup([key])
    try:
        _db_insert("game_config_weapons", {
            "key": key,
            "label": "SmartEntry Weapon U11c",
            "damage_die": "1d6",
            "weapon_type": "melee",
            "linked_stat": "STR",
            "allowed_classes": "[]",
            "is_active": 1,
            "value_gp": 5,
            "weight_kg": 1.0,
            "description": "SE test U11c",
            "two_handed": 0,
            "finesse": 0,
            "weapon_slot": "one_handed",
        })
        conn = _conn()
        row = conn.execute("SELECT * FROM game_items WHERE key = ?", (key,)).fetchone()
        conn.close()
        assert row is not None, f"game_items nie zawiera '{key}' po smart_entry _db_insert"
        assert row["kind"] == "weapon"
    finally:
        _cleanup([key])
