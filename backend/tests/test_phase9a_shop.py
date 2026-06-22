"""Phase 9A-4 — NPC shop service and Open Shop cue tests."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixtures_schema as fx


def _seed_minimal_shop_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        # game_config_* przez helper (#928 — pełny schemat z price_gp/etc.)
        fx.create_tables(conn, "game_config_weapons", "game_config_items", "game_config_consumables")
        conn.executescript(
            """
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                name TEXT,
                gold_gp INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE npcs (
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE,
                label TEXT,
                npc_type TEXT,
                is_shop INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_crafter INTEGER NOT NULL DEFAULT 0,
                shop_inventory_json TEXT
            );
            CREATE TABLE game_items (
                id INTEGER PRIMARY KEY,
                key TEXT NOT NULL,
                kind TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                description TEXT DEFAULT '',
                price_gp REAL DEFAULT 0,
                effect_json TEXT DEFAULT NULL,
                equip_slot TEXT DEFAULT NULL,
                rarity INTEGER DEFAULT 1,
                min_level INTEGER DEFAULT 1,
                location_tags TEXT DEFAULT '[]',
                created_by TEXT DEFAULT 'seed',
                approved INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                weapon_data TEXT DEFAULT '{}',
                item_data TEXT DEFAULT '{}',
                weight_kg REAL DEFAULT 0,
                note TEXT DEFAULT NULL,
                locked_at TEXT DEFAULT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE character_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL,
                item_key TEXT,
                weapon_key TEXT,
                consumable_key TEXT,
                quantity INTEGER NOT NULL DEFAULT 1,
                equipped INTEGER NOT NULL DEFAULT 0,
                slot TEXT,
                acquired_at TEXT DEFAULT (datetime('now')),
                source TEXT,
                meta_json TEXT,
                label TEXT,
                durability_max INTEGER,
                durability_current INTEGER,
                game_item_key TEXT,
                affixes_json TEXT
            );
            """
        )
        conn.execute("INSERT INTO characters(id, name, gold_gp) VALUES (1, 'Hero', 100)")
        conn.execute(
            """
            INSERT INTO npcs(id, key, label, npc_type, is_shop, is_active, shop_inventory_json)
            VALUES (1, 'merchant_aldric', 'Aldric', 'merchant', 1, 1, ?)
            """,
            (
                '[{"type":"weapon","key":"shortsword"},{"type":"consumable","key":"health_potion"},{"type":"item","key":"quest_trinket"}]',
            ),
        )
        conn.execute(
            "INSERT INTO game_config_items(key, label, description, value_gp, is_active) VALUES ('quest_trinket', 'Quest', 'No price', 0, 1)"
        )
        conn.execute(
            "INSERT INTO game_config_weapons(key, label, description, value_gp, is_active) VALUES (?, ?, ?, ?, 1)",
            ("shortsword", "Krótki miecz", "Broń", 15),
        )
        conn.execute(
            "INSERT INTO game_config_consumables(key, label, description, base_price, is_active) VALUES (?, ?, ?, ?, 1)",
            ("health_potion", "Mikstura zdrowia", "Leczy", 10),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def shop_db_path(tmp_path):
    p = str(tmp_path / "phase9a_shop.db")
    _seed_minimal_shop_db(p)
    return p


@pytest.fixture
def patch_shop_db(shop_db_path):
    from app.services import loot_service, shop_service

    old_loot = loot_service.LOOT_DB_PATH
    old_shop = shop_service.LOOT_DB_PATH
    loot_service.LOOT_DB_PATH = shop_db_path
    shop_service.LOOT_DB_PATH = shop_db_path
    try:
        yield shop_service
    finally:
        loot_service.LOOT_DB_PATH = old_loot
        shop_service.LOOT_DB_PATH = old_shop


def test_shop_inventory_by_key_returns_items_and_gold(patch_shop_db):
    data = patch_shop_db.get_shop_inventory_by_key("merchant_aldric", character_id=1)
    assert data["npc"]["key"] == "merchant_aldric"
    assert data["character_gold"] == 100
    assert len(data["items"]) == 2
    keys = {it["key"] for it in data["items"]}
    assert "shortsword" in keys
    assert "health_potion" in keys
    assert "quest_trinket" not in keys


def test_buy_item_deducts_gold_and_adds_inventory(patch_shop_db):
    out = patch_shop_db.buy_item(character_id=1, npc_id=1, item_type="weapon", item_key="shortsword")
    assert out["gold_gp"] == 85
    conn = sqlite3.connect(patch_shop_db.LOOT_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        inv = conn.execute(
            "SELECT weapon_key, quantity FROM character_inventory WHERE character_id = 1"
        ).fetchone()
    finally:
        conn.close()
    assert inv is not None
    assert inv["weapon_key"] == "shortsword"
    assert int(inv["quantity"] or 0) == 1


def test_sell_item_removes_one_and_adds_half_price_gold(patch_shop_db):
    conn = sqlite3.connect(patch_shop_db.LOOT_DB_PATH)
    try:
        conn.execute(
            "INSERT INTO character_inventory(character_id, consumable_key, quantity, source) VALUES (1, 'health_potion', 2, 'loot')"
        )
        inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    out = patch_shop_db.sell_item(character_id=1, inventory_id=inv_id)
    assert out["earned_gp"] == 5
    assert out["gold_gp"] == 105

    conn2 = sqlite3.connect(patch_shop_db.LOOT_DB_PATH)
    try:
        qty = conn2.execute(
            "SELECT quantity FROM character_inventory WHERE id = ?",
            (inv_id,),
        ).fetchone()[0]
    finally:
        conn2.close()
    assert int(qty) == 1


def test_extract_grant_cues_parses_open_shop_and_strips_line():
    from app.api.turns import extract_grant_cues

    text = "Aldric rozkłada towary na ladzie.\nOpen Shop merchant_aldric"
    clean, item, gold, open_shop = extract_grant_cues(text)
    assert clean == "Aldric rozkłada towary na ladzie."
    assert item is None
    assert gold is None
    assert open_shop == "merchant_aldric"


def test_open_shop_cue_detected_in_json_narrative():
    import json
    from app.api.turns import _extract_narrative_for_cues, _repack_narrative, extract_grant_cues

    raw = json.dumps(
        {"narrative": "Aldric kiwa głową.\nOpen Shop merchant_aldric", "location_intent": None},
        ensure_ascii=False,
    )
    narrative, parsed = _extract_narrative_for_cues(raw)
    clean, _, _, shop_key = extract_grant_cues(narrative)
    result = _repack_narrative(raw, clean, parsed)

    assert shop_key == "merchant_aldric"
    assert "Open Shop" not in json.loads(result)["narrative"]


def test_trade_user_intent_matches_polish_offer():
    from app.api.turns import _TRADE_USER_INTENT_RE

    assert _TRADE_USER_INTENT_RE.search("pokaż co masz do sprzedania")
    assert _TRADE_USER_INTENT_RE.search("ile kosztuje miecz")
    assert not _TRADE_USER_INTENT_RE.search("tylko pogoda jest brzydka")


def test_pick_shop_npc_key_prefers_name_in_narrative():
    from app.api.turns import _pick_shop_npc_key

    assert (
        _pick_shop_npc_key("Mówi Aldric i wzrusza ramionami.", ["merchant_aldric", "other"])
        == "merchant_aldric"
    )


def test_grant_gold_cue_detected_in_json_narrative():
    import json
    from app.api.turns import _extract_narrative_for_cues, _repack_narrative, extract_grant_cues

    raw = json.dumps(
        {"narrative": "Oto twoja nagroda.\nGrant Gold 50", "location_intent": None},
        ensure_ascii=False,
    )
    narrative, parsed = _extract_narrative_for_cues(raw)
    clean, _, gold, _ = extract_grant_cues(narrative)
    assert gold == 50
    assert "Grant Gold" not in json.loads(_repack_narrative(raw, clean, parsed))["narrative"]


def test_migration_adds_value_gp_to_weapons(tmp_path):
    from app import migrations_admin

    db_path = str(tmp_path / "phase9a_shop_migration.db")
    old_db_path = migrations_admin.DB_PATH
    migrations_admin.DB_PATH = db_path
    try:
        migrations_admin.run_admin_migrations()
        conn = sqlite3.connect(db_path)
        try:
            cols = conn.execute("PRAGMA table_info(game_config_weapons)").fetchall()
        finally:
            conn.close()
    finally:
        migrations_admin.DB_PATH = old_db_path

    col_names = {str(c[1]) for c in cols}
    assert "value_gp" in col_names
