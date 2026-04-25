import sqlite3
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.routers import locations as locations_router  # noqa: E402


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE game_locations (
          id            INTEGER PRIMARY KEY,
          key           TEXT UNIQUE NOT NULL,
          label         TEXT NOT NULL,
          description   TEXT,
          parent_id     INTEGER REFERENCES game_locations(id),
          location_type TEXT DEFAULT 'macro' CHECK(location_type IN ('macro', 'sub')),
          rules         TEXT,
          enemy_keys    TEXT DEFAULT '[]',
          npc_keys      TEXT DEFAULT '[]',
          is_active     INTEGER DEFAULT 1,
          created_at    TEXT DEFAULT (datetime('now')),
          updated_at    TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def _seed_locations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO game_locations (id, key, label, parent_id, location_type, enemy_keys, npc_keys, is_active)
        VALUES (1, 'city_varen', 'Miasto Varen', NULL, 'macro', '[]', '[]', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO game_locations (id, key, label, parent_id, location_type, enemy_keys, npc_keys, is_active)
        VALUES (2, 'tavern_hanged_man', 'Karczma Pod Wisielcem', 1, 'sub', '[]', '[]', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO game_locations (id, key, label, parent_id, location_type, enemy_keys, npc_keys, is_active)
        VALUES (3, 'old_ruins', 'Stare Ruiny', NULL, 'macro', '[]', '[]', 0)
        """
    )
    conn.commit()


def _build_client(monkeypatch):
    # Shared in-memory DB across connections.
    db_uri = "file:phase8d_locations_api?mode=memory&cache=shared"
    keeper = sqlite3.connect(db_uri, uri=True)
    _init_schema(keeper)
    _seed_locations(keeper)
    monkeypatch.setattr(locations_router, "DB_PATH", db_uri)
    monkeypatch.setattr(locations_router, "verify_admin_token", lambda token: token == "ok-admin")

    app = FastAPI()
    app.include_router(locations_router.router, prefix="/api")
    return TestClient(app), keeper


def test_get_locations_tree_and_filters(monkeypatch):
    client, keeper = _build_client(monkeypatch)
    try:
        resp = client.get("/api/locations")
        assert resp.status_code == 200
        payload = resp.json()
        assert len(payload) == 1
        assert payload[0]["key"] == "city_varen"
        assert payload[0]["children"][0]["key"] == "tavern_hanged_man"

        resp_sub = client.get("/api/locations", params={"type": "sub"})
        assert resp_sub.status_code == 200
        assert len(resp_sub.json()) == 1
        assert resp_sub.json()[0]["key"] == "tavern_hanged_man"

        resp_parent = client.get("/api/locations", params={"parent_id": 1})
        assert resp_parent.status_code == 200
        assert len(resp_parent.json()) == 1
        assert resp_parent.json()[0]["key"] == "city_varen"
    finally:
        keeper.close()


def test_post_locations_happy_and_errors(monkeypatch):
    client, keeper = _build_client(monkeypatch)
    try:
        body = {
            "key": "city_gate",
            "label": "Brama Miejska",
            "description": "Północna brama",
            "parent_id": 1,
            "location_type": "sub",
            "rules": {"enter_requires": "pass"},
            "enemy_keys": ["guard_captain"],
            "npc_keys": ["gate_keeper"],
        }
        resp = client.post("/api/locations", json=body, headers={"X-Internal-Role": "gm"})
        assert resp.status_code == 201
        payload = resp.json()
        assert payload["key"] == "city_gate"
        assert payload["parent_id"] == 1
        assert payload["rules"] == {"enter_requires": "pass"}
        assert payload["enemy_keys"] == ["guard_captain"]

        dup = client.post("/api/locations", json=body, headers={"Authorization": "Bearer ok-admin"})
        assert dup.status_code == 422

        bad_parent = dict(body)
        bad_parent["key"] = "forest_hidden"
        bad_parent["parent_id"] = 999
        resp_bad_parent = client.post(
            "/api/locations",
            json=bad_parent,
            headers={"Authorization": "Bearer ok-admin"},
        )
        assert resp_bad_parent.status_code == 404

        unauth = client.post("/api/locations", json=bad_parent)
        assert unauth.status_code == 401
    finally:
        keeper.close()


def test_get_location_detail_happy_and_not_found(monkeypatch):
    client, keeper = _build_client(monkeypatch)
    try:
        resp = client.get("/api/locations/city_varen")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["key"] == "city_varen"
        assert payload["parent"] is None
        assert len(payload["children"]) == 1
        assert payload["children"][0]["key"] == "tavern_hanged_man"

        resp_sub = client.get("/api/locations/tavern_hanged_man")
        assert resp_sub.status_code == 200
        assert resp_sub.json()["parent"] == {"key": "city_varen", "label": "Miasto Varen"}

        hidden = client.get("/api/locations/old_ruins")
        assert hidden.status_code == 404
    finally:
        keeper.close()
