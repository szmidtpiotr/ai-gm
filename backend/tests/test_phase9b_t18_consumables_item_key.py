"""T18 — consumables runtime, conditions, and item_key canonical path."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.inventory import router as inventory_router
from app.services import loot_service as loot_mod
from app.services import shop_service as shop_mod


def _seed_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                campaign_id INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL,
                sheet_json TEXT NOT NULL DEFAULT '{}',
                gold_gp INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE game_config_items (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                item_type TEXT NOT NULL DEFAULT 'misc',
                description TEXT NOT NULL DEFAULT '',
                value_gp INTEGER NOT NULL DEFAULT 0,
                weight REAL NOT NULL DEFAULT 0.0,
                weight_kg REAL NOT NULL DEFAULT 0.0,
                effect_type TEXT,
                effect_dice TEXT,
                effect_bonus INTEGER NOT NULL DEFAULT 0,
                effect_target TEXT NOT NULL DEFAULT 'self',
                charges INTEGER NOT NULL DEFAULT 1,
                effect_json TEXT,
                approved INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE game_config_conditions (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                effect_json TEXT NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                stackable INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE game_config_weapons (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                value_gp INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE game_config_consumables (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                description TEXT,
                base_price INTEGER NOT NULL DEFAULT 0,
                effect_type TEXT,
                effect_dice TEXT,
                effect_bonus INTEGER NOT NULL DEFAULT 0,
                effect_target TEXT NOT NULL DEFAULT 'self',
                is_active INTEGER NOT NULL DEFAULT 1
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
                acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
                source TEXT,
                meta_json TEXT
            );

            CREATE TABLE active_combat (
                campaign_id INTEGER NOT NULL,
                character_id INTEGER NOT NULL,
                combatants TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT
            );

            CREATE TABLE npcs (
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE,
                label TEXT,
                npc_type TEXT,
                is_shop INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                shop_inventory_json TEXT
            );
            """
        )

        char_sheet = {
            "current_hp": 3,
            "max_hp": 10,
            "current_mana": 1,
            "max_mana": 4,
            "conditions": [],
        }
        conn.execute(
            "INSERT INTO characters(id, campaign_id, name, sheet_json, gold_gp) VALUES (1, 1, 'Hero', ?, 100)",
            (json.dumps(char_sheet, ensure_ascii=False),),
        )
        conn.execute(
            "INSERT INTO active_combat(campaign_id, character_id, combatants, updated_at) VALUES (1, 1, ?, datetime('now'))",
            (
                json.dumps(
                    [
                        {"id": "player", "type": "player", "hp_current": 3, "hp_max": 10, "conditions": []},
                        {"id": "goblin_01", "type": "enemy", "hp_current": 5, "hp_max": 5, "conditions": []},
                    ],
                    ensure_ascii=False,
                ),
            ),
        )

        poisoned_effect = {
            "schema_version": 1,
            "effect_category": "character_condition",
            "effects": [{"type": "periodic_save", "dc_key": "easy", "tick": "each_round", "expires": "save_success"}],
        }
        conn.execute(
            "INSERT INTO game_config_conditions(key, label, effect_json, description, is_active, stackable) VALUES ('poisoned', 'Poisoned', ?, 'test', 1, 0)",
            (json.dumps(poisoned_effect, ensure_ascii=False),),
        )

        health_effect = {
            "schema_version": 1,
            "effect_category": "consumable_immediate",
            "effects": [{"type": "heal_hp", "value": 5}],
        }
        poison_effect = {
            "schema_version": 1,
            "effect_category": "consumable_immediate",
            "effects": [{"type": "apply_condition", "condition_key": "poisoned"}],
        }
        antidote_effect = {
            "schema_version": 1,
            "effect_category": "consumable_immediate",
            "effects": [{"type": "remove_condition", "condition_key": "poisoned"}],
        }
        conn.executemany(
            """
            INSERT INTO game_config_items
                (key, label, item_type, description, value_gp, effect_type, effect_dice, effect_bonus, effect_target, effect_json, approved, is_active)
            VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, 1, 1)
            """,
            [
                ("health_potion", "Health Potion", "consumable", 10, None, None, 0, "self", json.dumps(health_effect, ensure_ascii=False)),
                ("poison_vial", "Poison Vial", "consumable", 12, None, None, 0, "self", json.dumps(poison_effect, ensure_ascii=False)),
                ("antidote", "Antidote", "consumable", 11, None, None, 0, "self", json.dumps(antidote_effect, ensure_ascii=False)),
                ("mana_potion", "Mana Potion", "consumable", 8, "restore_mana", None, 3, "self", None),
                ("rope", "Rope", "misc", 2, None, None, 0, "self", None),
            ],
        )
        conn.execute(
            "INSERT INTO game_config_weapons(key, label, value_gp, is_active) VALUES ('dagger', 'Dagger', 5, 1)"
        )
        conn.execute(
            """
            INSERT INTO npcs(id, key, label, npc_type, is_shop, is_active, shop_inventory_json)
            VALUES (1, 'merchant', 'Merchant', 'merchant', 1, 1, ?)
            """,
            ('[{"type":"consumable","key":"health_potion"},{"type":"weapon","key":"dagger"}]',),
        )

        conn.executemany(
            """
            INSERT INTO character_inventory(character_id, item_key, quantity, source)
            VALUES (1, ?, ?, ?)
            """,
            [
                ("health_potion", 2, "loot"),
                ("poison_vial", 1, "loot"),
                ("antidote", 1, "loot"),
                ("mana_potion", 1, "loot"),
                ("rope", 1, "loot"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def t18_db(tmp_path, monkeypatch):
    db = tmp_path / "t18.db"
    _seed_db(db)
    monkeypatch.setattr(loot_mod, "LOOT_DB_PATH", str(db))
    monkeypatch.setattr(shop_mod, "LOOT_DB_PATH", str(db))
    return db


@pytest.fixture
def client(t18_db):
    app = FastAPI()
    app.include_router(inventory_router, prefix="/api")
    return TestClient(app)


def _fetch_sheet(db: Path) -> dict:
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = 1").fetchone()
        return json.loads(row[0] or "{}")
    finally:
        conn.close()


def _fetch_combatants(db: Path) -> list[dict]:
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id = 1 AND character_id = 1").fetchone()
        return json.loads(row[0] or "[]")
    finally:
        conn.close()


def test_inventory_use_consumable_heals_hp_and_decrements_stack(client, t18_db):
    resp = client.post("/api/inventory/1/use", json={"inventory_id": 1})
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["remaining_quantity"] == 1
    assert body["character_state"]["current_hp"] == 8

    sheet = _fetch_sheet(t18_db)
    assert int(sheet["current_hp"]) == 8
    combatants = _fetch_combatants(t18_db)
    player = next(x for x in combatants if x["id"] == "player")
    assert int(player["hp_current"]) == 8


def test_inventory_use_can_apply_and_remove_condition(client, t18_db):
    apply_resp = client.post("/api/inventory/1/use", json={"inventory_id": 2})
    assert apply_resp.status_code == 200, apply_resp.text
    sheet = _fetch_sheet(t18_db)
    assert [c["key"] for c in sheet.get("conditions") or []] == ["poisoned"]

    remove_resp = client.post("/api/inventory/1/use", json={"inventory_id": 3})
    assert remove_resp.status_code == 200, remove_resp.text
    sheet2 = _fetch_sheet(t18_db)
    assert sheet2.get("conditions") == []


def test_inventory_use_legacy_restore_mana_still_works(client, t18_db):
    resp = client.post("/api/inventory/1/use", json={"inventory_id": 4})
    assert resp.status_code == 200, resp.text
    sheet = _fetch_sheet(t18_db)
    assert int(sheet["current_mana"]) == 4


def test_inventory_use_non_consumable_returns_400(client):
    resp = client.post("/api/inventory/1/use", json={"inventory_id": 5})
    assert resp.status_code == 400


def test_shop_buy_consumable_grants_item_key_not_consumable_key(t18_db):
    out = shop_mod.buy_item(character_id=1, npc_id=1, item_type="consumable", item_key="health_potion")
    assert out["item"]["type"] == "consumable"

    conn = sqlite3.connect(str(t18_db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT item_key, consumable_key, quantity
            FROM character_inventory
            WHERE character_id = 1 AND item_key = 'health_potion'
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["item_key"] == "health_potion"
    assert row["consumable_key"] is None
    assert int(row["quantity"] or 0) >= 3


def test_shop_sell_item_key_consumable_reports_consumable_type(t18_db):
    conn = sqlite3.connect(str(t18_db))
    try:
        conn.execute(
            "INSERT INTO character_inventory(character_id, item_key, quantity, source) VALUES (1, 'health_potion', 1, 'loot')"
        )
        inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    out = shop_mod.sell_item(character_id=1, inventory_id=inv_id)
    assert out["sold_item"]["type"] == "consumable"
