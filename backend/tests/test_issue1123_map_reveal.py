"""TDD: Issue #1123 (PT13) — Map items reveal fog of war.

A map item, used from inventory, reveals a fragment of the world's fog of war
(campaign_hex_data.discovered=1) via one of three modes: radius | region | hexes.
The map is NOT consumed (one-shot reveal, stays in inventory). Idempotent.
"""
import sys
import json
import sqlite3

import pytest

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

from app.services import map_reveal_service  # noqa: E402


# ─── World fixture (overworld, map_level=0) ──────────────────────────────────

WORLD_SCHEMA = """
CREATE TABLE world_hexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q INTEGER NOT NULL,
    r INTEGER NOT NULL,
    hex_type TEXT NOT NULL DEFAULT 'plains',
    region TEXT NOT NULL DEFAULT 'kresy',
    is_active INTEGER NOT NULL DEFAULT 1,
    map_level INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE campaign_hex_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    hex_q INTEGER NOT NULL,
    hex_r INTEGER NOT NULL,
    discovered INTEGER NOT NULL DEFAULT 0,
    encounter_cleared INTEGER NOT NULL DEFAULT 0,
    UNIQUE(campaign_id, hex_q, hex_r)
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(WORLD_SCHEMA)
    # A 5x5 patch of overworld hexes, region 'kresy'
    for q in range(-2, 3):
        for r in range(-2, 3):
            c.execute(
                "INSERT INTO world_hexes (q, r, region, map_level) VALUES (?,?,?,0)",
                (q, r, "kresy"),
            )
    # One hex in a different region + one sublocation hex (map_level=1) that must be ignored
    c.execute("INSERT INTO world_hexes (q, r, region, map_level) VALUES (10, 10, 'wachstein', 0)")
    c.execute("INSERT INTO world_hexes (q, r, region, map_level) VALUES (0, 0, 'kresy', 1)")
    c.commit()
    return c


def _discovered(conn, campaign_id):
    rows = conn.execute(
        "SELECT hex_q, hex_r FROM campaign_hex_data WHERE campaign_id=? AND discovered=1",
        (campaign_id,),
    ).fetchall()
    return {(r["hex_q"], r["hex_r"]) for r in rows}


# ─── Test główny: 3 tryby silnika odkrywania ─────────────────────────────────

def test_radius_mode_reveals_hexes_within_distance(conn):
    """radius: all overworld hexes within hex-distance <= radius of center are discovered."""
    payload = {"mode": "radius", "center_q": 0, "center_r": 0, "radius": 1}
    res = map_reveal_service.reveal_from_payload(1, payload, conn=conn)
    conn.commit()
    got = _discovered(conn, 1)
    # Center + 6 neighbors of axial (0,0) at radius 1
    expected = {(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
    assert got == expected
    assert res["count"] == 7
    # map_level=1 sublocation hex at (0,0) must NOT leak (only overworld counted once)
    assert (10, 10) not in got  # different region far away, out of radius


def test_region_mode_reveals_whole_region(conn):
    """region: every overworld hex tagged with that region is discovered; other regions untouched."""
    payload = {"mode": "region", "region": "kresy"}
    res = map_reveal_service.reveal_from_payload(1, payload, conn=conn)
    conn.commit()
    got = _discovered(conn, 1)
    assert (10, 10) not in got  # 'wachstein' region excluded
    assert (0, 0) in got and (-2, -2) in got and (2, 2) in got
    assert res["count"] == 25  # 5x5 kresy overworld hexes, sublocation (map_level=1) excluded


def test_hexes_mode_reveals_explicit_list(conn):
    """hexes: exactly the listed [q,r] pairs are discovered."""
    payload = {"mode": "hexes", "list": [[1, 1], [2, 2], [-1, -1]]}
    map_reveal_service.reveal_from_payload(1, payload, conn=conn)
    conn.commit()
    assert _discovered(conn, 1) == {(1, 1), (2, 2), (-1, -1)}


def test_reveal_is_idempotent(conn):
    """Using the same map twice does not error and keeps discovered=1 (no duplicate rows)."""
    payload = {"mode": "hexes", "list": [[1, 1], [2, 2]]}
    map_reveal_service.reveal_from_payload(1, payload, conn=conn)
    map_reveal_service.reveal_from_payload(1, payload, conn=conn)
    conn.commit()
    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM campaign_hex_data WHERE campaign_id=1"
    ).fetchone()
    assert rows["n"] == 2  # no duplicates
    assert _discovered(conn, 1) == {(1, 1), (2, 2)}


# ─── extract_map_payload — flat + wrapped + backward compat ───────────────────

def test_extract_payload_flat():
    ej = json.dumps({"mode": "radius", "center_q": 3, "center_r": 4, "radius": 2})
    p = map_reveal_service.extract_map_payload(ej)
    assert p["mode"] == "radius" and p["center_q"] == 3


def test_extract_payload_wrapped_effects():
    ej = json.dumps({"effects": [{"type": "map_reveal", "mode": "region", "region": "kresy"}]})
    p = map_reveal_service.extract_map_payload(ej)
    assert p["mode"] == "region" and p["region"] == "kresy"


def test_extract_payload_none_for_heal_potion():
    """Backward compat: a normal healing consumable is NOT a map — extract returns None."""
    ej = json.dumps({"effects": [{"type": "heal_hp", "value": "2d4"}]})
    assert map_reveal_service.extract_map_payload(ej) is None


# ─── Integration przez loot_service.use_inventory_item ───────────────────────

USE_SCHEMA = WORLD_SCHEMA + """
CREATE TABLE characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    sheet_json TEXT
);
CREATE TABLE character_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    item_key TEXT,
    weapon_key TEXT,
    consumable_key TEXT,
    quantity INTEGER NOT NULL DEFAULT 1
);
""" + table_sql("game_config_items") + """
""" + table_sql("game_config_consumables") + """
"""


@pytest.fixture
def use_db(tmp_path, monkeypatch):
    db = tmp_path / "ai_gm.db"
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    c.executescript(USE_SCHEMA)
    for q in range(-1, 2):
        for r in range(-1, 2):
            c.execute("INSERT INTO world_hexes (q, r, region, map_level) VALUES (?,?,?,0)", (q, r, "kresy"))
    c.execute(
        "INSERT INTO characters (id, campaign_id, sheet_json) VALUES (7, 42, ?)",
        (json.dumps({"current_hp": 10, "max_hp": 10}),),
    )
    # Map item — radius mode, does not consume
    c.execute(
        "INSERT INTO game_config_items (key, label, item_type, effect_json) VALUES (?,?,?,?)",
        ("map_kresy", "Mapa Kresów", "map",
         json.dumps({"mode": "radius", "center_q": 0, "center_r": 0, "radius": 1})),
    )
    c.execute("INSERT INTO character_inventory (id, character_id, item_key, quantity) VALUES (100, 7, 'map_kresy', 1)")
    # Healing potion consumable — backward compat
    c.execute(
        "INSERT INTO game_config_consumables (key, label, effect_type, effect_dice) VALUES (?,?,?,?)",
        ("potion_heal", "Mikstura", "heal_hp", "2d4"),
    )
    c.execute("INSERT INTO character_inventory (id, character_id, consumable_key, quantity) VALUES (101, 7, 'potion_heal', 2)")
    c.commit()
    c.close()
    from app.services import loot_service
    monkeypatch.setattr(loot_service, "LOOT_DB_PATH", str(db))
    monkeypatch.setattr(map_reveal_service, "DB_PATH", str(db))
    return str(db)


def test_use_map_item_reveals_and_is_not_consumed(use_db):
    from app.services import loot_service
    res = loot_service.use_inventory_item(7, 100)
    assert res["item"]["item_type"] == "map"
    # Map stays in inventory
    assert res["remaining_quantity"] == 1
    c = sqlite3.connect(use_db)
    c.row_factory = sqlite3.Row
    still = c.execute("SELECT quantity FROM character_inventory WHERE id=100").fetchone()
    assert still is not None and still["quantity"] == 1
    disc = c.execute(
        "SELECT hex_q, hex_r FROM campaign_hex_data WHERE campaign_id=42 AND discovered=1"
    ).fetchall()
    got = {(r["hex_q"], r["hex_r"]) for r in disc}
    assert (0, 0) in got and (1, 0) in got and len(got) == 7
    c.close()


def test_use_consumable_potion_still_works(use_db):
    """Backward compat: healing potion still consumes + heals; map branch didn't break it."""
    from app.services import loot_service
    # drop HP first so heal is observable
    c = sqlite3.connect(use_db)
    c.execute("UPDATE characters SET sheet_json=? WHERE id=7",
              (json.dumps({"current_hp": 1, "max_hp": 10}),))
    c.commit(); c.close()
    res = loot_service.use_inventory_item(7, 101)
    assert res["item"]["item_type"] == "consumable"
    assert res["remaining_quantity"] == 1  # 2 -> 1, consumed
    assert res["character_state"]["current_hp"] > 1
