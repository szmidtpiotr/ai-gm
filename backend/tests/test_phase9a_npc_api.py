"""Phase 9A-2 — NPC CRUD API tests."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def test_db_path(tmp_path):
    return str(tmp_path / "test_phase9a_npc_api.db")


@pytest.fixture
def client_with_db(test_db_path):
    from app import migrations_admin
    from app.api import npcs as npcs_api

    old_mig = migrations_admin.DB_PATH
    old_npcs = npcs_api.DB_PATH
    migrations_admin.DB_PATH = test_db_path
    npcs_api.DB_PATH = test_db_path
    try:
        migrations_admin.run_admin_migrations()
        with TestClient(app) as c:
            yield c, test_db_path
    finally:
        migrations_admin.DB_PATH = old_mig
        npcs_api.DB_PATH = old_npcs


def test_list_npcs_returns_seeded_records(client_with_db):
    client, _ = client_with_db
    r = client.get("/api/npcs")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 4


def test_get_npc_by_id(client_with_db):
    client, _ = client_with_db
    all_data = client.get("/api/npcs").json()["data"]
    npc_id = int(all_data[0]["id"])
    r = client.get(f"/api/npcs/{npc_id}")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert int(r.json()["data"]["id"]) == npc_id


def test_get_npc_not_found_returns_404(client_with_db):
    client, _ = client_with_db
    r = client.get("/api/npcs/999999")
    assert r.status_code == 404


def test_create_npc(client_with_db):
    client, _ = client_with_db
    r = client.post(
        "/api/npcs",
        json={
            "key": "test_npc_create",
            "label": "Test NPC",
            "npc_type": "neutral",
            "personality_json": "{}",
            "shop_inventory_json": "[]",
            "is_shop": 0,
            "is_active": 1,
            "location_keys": [],
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert int(r.json()["id"]) > 0


def test_create_npc_duplicate_key_returns_409(client_with_db):
    client, _ = client_with_db
    payload = {
        "key": "dup_npc",
        "label": "Dup",
        "npc_type": "neutral",
        "personality_json": "{}",
        "shop_inventory_json": "[]",
        "location_keys": [],
    }
    r1 = client.post("/api/npcs", json=payload)
    assert r1.status_code == 200
    r2 = client.post("/api/npcs", json=payload)
    assert r2.status_code == 409


def test_create_npc_with_location_keys(client_with_db):
    client, db_path = client_with_db
    r = client.post(
        "/api/npcs",
        json={
            "key": "loc_npc",
            "label": "Loc NPC",
            "npc_type": "neutral",
            "personality_json": "{}",
            "shop_inventory_json": "[]",
            "location_keys": ["village_square", "inn_main"],
        },
    )
    assert r.status_code == 200
    npc_id = int(r.json()["id"])

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT location_key FROM npc_locations WHERE npc_id = ? ORDER BY location_key",
            (npc_id,),
        ).fetchall()
    finally:
        conn.close()
    assert [row[0] for row in rows] == ["inn_main", "village_square"]


def test_patch_npc_label(client_with_db):
    client, _ = client_with_db
    created = client.post(
        "/api/npcs",
        json={
            "key": "patch_label_npc",
            "label": "Before",
            "npc_type": "neutral",
            "personality_json": "{}",
            "shop_inventory_json": "[]",
        },
    )
    npc_id = int(created.json()["id"])
    pr = client.patch(f"/api/npcs/{npc_id}", json={"label": "After"})
    assert pr.status_code == 200
    gr = client.get(f"/api/npcs/{npc_id}")
    assert gr.json()["data"]["label"] == "After"


def test_patch_npc_invalid_json_returns_400(client_with_db):
    client, _ = client_with_db
    created = client.post(
        "/api/npcs",
        json={
            "key": "patch_json_npc",
            "label": "Json",
            "npc_type": "neutral",
            "personality_json": "{}",
            "shop_inventory_json": "[]",
        },
    )
    npc_id = int(created.json()["id"])
    pr = client.patch(f"/api/npcs/{npc_id}", json={"personality_json": "{bad"})
    assert pr.status_code == 400


def test_patch_npc_location_keys_replace(client_with_db):
    client, _ = client_with_db
    created = client.post(
        "/api/npcs",
        json={
            "key": "patch_loc_npc",
            "label": "Loc",
            "npc_type": "neutral",
            "personality_json": "{}",
            "shop_inventory_json": "[]",
            "location_keys": ["village_square"],
        },
    )
    npc_id = int(created.json()["id"])
    pr = client.patch(f"/api/npcs/{npc_id}", json={"location_keys": []})
    assert pr.status_code == 200
    gr = client.get(f"/api/npcs/{npc_id}")
    assert gr.json()["data"]["location_keys"] == []


def test_delete_npc_cascades_locations(client_with_db):
    client, db_path = client_with_db
    created = client.post(
        "/api/npcs",
        json={
            "key": "delete_npc",
            "label": "Delete NPC",
            "npc_type": "neutral",
            "personality_json": "{}",
            "shop_inventory_json": "[]",
            "location_keys": ["village_square"],
        },
    )
    npc_id = int(created.json()["id"])

    dr = client.delete(f"/api/npcs/{npc_id}")
    assert dr.status_code == 200

    conn = sqlite3.connect(db_path)
    try:
        npc_rows = conn.execute("SELECT 1 FROM npcs WHERE id = ?", (npc_id,)).fetchall()
        loc_rows = conn.execute(
            "SELECT 1 FROM npc_locations WHERE npc_id = ?",
            (npc_id,),
        ).fetchall()
    finally:
        conn.close()
    assert npc_rows == []
    assert loc_rows == []
