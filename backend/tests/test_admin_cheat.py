"""Phase 8G Admin Commands — backend cheat API tests."""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import admin_cheat
from app.routers.admin import require_admin_token


def _seed_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER,
              location TEXT,
              sheet_json TEXT,
              gold_gp INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE character_inventory (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              character_id INTEGER NOT NULL,
              item_key TEXT,
              weapon_key TEXT,
              consumable_key TEXT,
              quantity INTEGER NOT NULL DEFAULT 1,
              equipped INTEGER NOT NULL DEFAULT 0,
              slot TEXT
            );

            CREATE TABLE active_combat (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'active',
              ended_reason TEXT
            );

            CREATE TABLE game_config_weapons (
              key TEXT PRIMARY KEY,
              label TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE game_config_items (
              key TEXT PRIMARY KEY,
              label TEXT NOT NULL DEFAULT '',
              item_type TEXT NOT NULL DEFAULT 'misc'
            );

            CREATE TABLE game_config_consumables (
              key TEXT PRIMARY KEY,
              label TEXT NOT NULL DEFAULT ''
            );

            INSERT INTO characters(id, campaign_id, location, sheet_json, gold_gp)
            VALUES (
              1,
              101,
              'start_village',
              '{"current_hp":5,"max_hp":10,"level":2,"stats":{"STR":3},"quests_active":["quest_intro"],"quests_completed":[]}',
              50
            );

            INSERT INTO character_inventory(character_id, item_key) VALUES (1, 'rope');
            INSERT INTO active_combat(campaign_id, status) VALUES (101, 'active');
            """
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def test_db_path(tmp_path):
    return str(tmp_path / "test_admin_cheat.db")


@pytest.fixture
def client_with_auth(test_db_path):
    old_db_path = admin_cheat.DB_PATH
    admin_cheat.DB_PATH = test_db_path
    _seed_schema(test_db_path)

    app = FastAPI()
    app.include_router(admin_cheat.router, prefix="/api")
    app.dependency_overrides[require_admin_token] = lambda: None
    try:
        with TestClient(app) as client:
            yield client, test_db_path
    finally:
        app.dependency_overrides.clear()
        admin_cheat.DB_PATH = old_db_path


def _post(client: TestClient, cmd: str, **kwargs):
    payload = {"cmd": cmd}
    payload.update(kwargs)
    return client.post("/api/admin/cheat/1", json=payload)


def test_add_gold_increases_balance(client_with_auth):
    client, _ = client_with_auth
    r = _post(client, "add gold", value=25)
    assert r.status_code == 200
    assert r.json()["result"]["gold_gp"] == 75


def test_set_gold_exact_value(client_with_auth):
    client, _ = client_with_auth
    r = _post(client, "set gold", value=999)
    assert r.status_code == 200
    assert r.json()["result"]["gold_gp"] == 999


def test_set_health_max(client_with_auth):
    client, _ = client_with_auth
    r = _post(client, "set health", value="max")
    assert r.status_code == 200
    assert r.json()["result"]["current_hp"] == 10
    assert r.json()["result"]["max_hp"] == 10


def test_set_health_value_capped_at_max(client_with_auth):
    client, _ = client_with_auth
    r = _post(client, "set health", value=999)
    assert r.status_code == 200
    assert r.json()["result"]["current_hp"] == 10


def test_add_stat_str(client_with_auth):
    client, _ = client_with_auth
    r = _post(client, "add stat", stat="STR", value=2)
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["stat"] == "STR"
    assert body["result"]["new_value"] == 5


def test_add_item(client_with_auth):
    client, db_path = client_with_auth
    r = _post(client, "add item", key="weapon_axe")
    assert r.status_code == 200
    body = r.json()["result"]
    assert body["added"] == "weapon_axe"
    assert body.get("equipped_slot") == "main_hand"

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT weapon_key, equipped, slot FROM character_inventory WHERE character_id = ? ORDER BY id DESC LIMIT 1",
            (1,),
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "weapon_axe"
    assert row[1] == 1
    assert row[2] == "main_hand"


def test_add_item_maps_prefixed_weapon_to_catalog_key(client_with_auth):
    """Frontend used to send weapon_longsword while catalog key is longsword — store canonical key."""
    client, db_path = client_with_auth
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS game_config_weapons (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            "INSERT INTO game_config_weapons (key, label) VALUES ('longsword', 'Longsword')",
        )
        conn.commit()
    finally:
        conn.close()

    r = _post(client, "add item", key="weapon_longsword")
    assert r.status_code == 200
    res = r.json()["result"]
    assert res["added"] == "longsword"
    assert res.get("equipped_slot") == "main_hand"

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT weapon_key, equipped, slot FROM character_inventory WHERE character_id = ? ORDER BY id DESC LIMIT 1",
            (1,),
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "longsword"
    assert row[1] == 1
    assert row[2] == "main_hand"

    r2 = _post(client, "add item", key="longsword")
    assert r2.status_code == 200
    res2 = r2.json()["result"]
    assert res2["added"] == "longsword"
    assert res2.get("equipped_slot") == "off_hand"


def test_add_item_prefers_consumable_catalog_over_wrong_items_row(client_with_auth):
    """game_config_items marked quest must not shadow keys present in game_config_consumables (8H /admin add item)."""
    client, db_path = client_with_auth
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS game_config_items (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL DEFAULT '',
                item_type TEXT NOT NULL DEFAULT 'misc'
            );
            CREATE TABLE IF NOT EXISTS game_config_consumables (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO game_config_items (key, label, item_type)
            VALUES ('hp_conflict', 'Wrong catalog row', 'quest');
            INSERT INTO game_config_consumables (key, label)
            VALUES ('hp_conflict', 'Small Health Potion');
            """
        )
        conn.commit()
    finally:
        conn.close()

    r = _post(client, "add item", key="hp_conflict")
    assert r.status_code == 200
    assert r.json()["result"]["added"] == "hp_conflict"

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT item_key, weapon_key, consumable_key
            FROM character_inventory
            WHERE character_id = 1
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "hp_conflict"
    assert row[1] is None
    assert row[2] is None


def test_add_item_prefers_consumable_key_when_items_catalog_marks_consumable(client_with_auth):
    """Same key in items (item_type=consumable) + consumables → inventory must use consumable_key."""
    client, db_path = client_with_auth
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS game_config_items (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL DEFAULT '',
                item_type TEXT NOT NULL DEFAULT 'misc'
            );
            CREATE TABLE IF NOT EXISTS game_config_consumables (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO game_config_items (key, label, item_type)
            VALUES ('g_test_potion', 'GP item', 'consumable');
            INSERT INTO game_config_consumables (key, label)
            VALUES ('g_test_potion', 'GP cons');
            """
        )
        conn.commit()
    finally:
        conn.close()

    r = _post(client, "add item", key="g_test_potion")
    assert r.status_code == 200
    assert r.json()["result"]["added"] == "g_test_potion"

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT item_key, weapon_key, consumable_key
            FROM character_inventory
            WHERE character_id = 1
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()
    assert row[0] is None
    assert row[1] is None
    assert row[2] == "g_test_potion"


def test_add_item_respects_explicit_consumable_hint(client_with_auth):
    client, db_path = client_with_auth
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS game_config_items (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL DEFAULT '',
                item_type TEXT NOT NULL DEFAULT 'misc'
            );
            INSERT INTO game_config_items (key, label, item_type)
            VALUES ('only_item_potion', 'Only item', 'consumable');
            """
        )
        conn.commit()
    finally:
        conn.close()

    r = _post(client, "add item", key="only_item_potion", kind="consumable")
    assert r.status_code == 200
    assert r.json()["result"]["added"] == "only_item_potion"

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT item_key, weapon_key, consumable_key
            FROM character_inventory
            WHERE character_id = 1
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()
    assert row[0] is None
    assert row[1] is None
    assert row[2] == "only_item_potion"


def test_remove_item(client_with_auth):
    client, _ = client_with_auth
    _post(client, "add item", key="consumable_potion")
    r = _post(client, "remove item", key="consumable_potion")
    assert r.status_code == 200
    assert r.json()["result"]["removed"] == "consumable_potion"


def test_clear_inventory(client_with_auth):
    client, db_path = client_with_auth
    _post(client, "add item", key="weapon_sword")
    r = _post(client, "clear inventory")
    assert r.status_code == 200
    assert r.json()["result"]["cleared"] is True

    conn = sqlite3.connect(db_path)
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM character_inventory WHERE character_id = ?",
            (1,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert cnt == 0


def test_combat_end(client_with_auth):
    client, db_path = client_with_auth
    r = _post(client, "combat end")
    assert r.status_code == 200
    assert r.json()["result"]["combat_ended"] is True

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT status, ended_reason FROM active_combat WHERE campaign_id = ? LIMIT 1",
            (101,),
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "ended"
    assert row[1] == "admin_cheat"


def test_quest_add(client_with_auth):
    client, _ = client_with_auth
    r = _post(client, "quest add", key="quest_side_1")
    assert r.status_code == 200
    assert "quest_side_1" in r.json()["result"]["quests_active"]


def test_quest_complete(client_with_auth):
    client, _ = client_with_auth
    r = _post(client, "quest complete", key="quest_intro")
    assert r.status_code == 200
    body = r.json()["result"]
    assert "quest_intro" not in body["quests_active"]
    assert "quest_intro" in body["quests_completed"]


def test_show_state_returns_full_snapshot(client_with_auth):
    client, _ = client_with_auth
    r = _post(client, "show state")
    assert r.status_code == 200
    state = r.json()["result"]
    assert set(state.keys()) == {
        "current_hp",
        "max_hp",
        "gold_gp",
        "level",
        "location",
        "stats",
        "quests_active",
        "quests_completed",
        "inventory",
    }
    assert isinstance(state["inventory"], list)


def test_unknown_cmd_returns_422(client_with_auth):
    client, _ = client_with_auth
    r = _post(client, "teleport to moon")
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "unknown_cmd"
    assert "show state" in detail["available"]


def test_no_token_returns_401_or_403(test_db_path):
    old_db_path = admin_cheat.DB_PATH
    admin_cheat.DB_PATH = test_db_path
    _seed_schema(test_db_path)

    app = FastAPI()
    app.include_router(admin_cheat.router, prefix="/api")
    try:
        with TestClient(app) as client:
            r = client.post("/api/admin/cheat/1", json={"cmd": "add gold", "value": 100})
    finally:
        admin_cheat.DB_PATH = old_db_path
    assert r.status_code in (401, 403)
