"""T07: GET /api/campaigns/{id} omits gm_plan_json unless viewer is owner, admin, or campaign gm/admin."""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api import campaigns as campaigns_api
from app.main import app


def _init_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT,
              is_admin INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE campaigns (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              system_id TEXT NOT NULL,
              model_id TEXT NOT NULL,
              owner_user_id INTEGER NOT NULL,
              language TEXT NOT NULL DEFAULT 'pl',
              mode TEXT NOT NULL DEFAULT 'solo',
              status TEXT NOT NULL DEFAULT 'active',
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              gm_plan_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE campaign_members (
              campaign_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              role TEXT NOT NULL,
              PRIMARY KEY (campaign_id, user_id)
            );
            """
        )
        conn.execute(
            "INSERT INTO users (id, username, is_admin) VALUES (5, 'admin', 1)"
        )
        conn.execute(
            "INSERT INTO users (id, username, is_admin) VALUES (10, 'owner', 0)"
        )
        conn.execute(
            "INSERT INTO users (id, username, is_admin) VALUES (99, 'player', 0)"
        )
        conn.execute(
            "INSERT INTO users (id, username, is_admin) VALUES (100, 'cogm', 0)"
        )
        plan = json.dumps({"arcs": {"a": {"label": "secret arc"}}}, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id, gm_plan_json)
            VALUES (1, 'T', 'fantasy', 'm', 10, ?)
            """,
            (plan,),
        )
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, role) VALUES (1, 99, 'player')"
        )
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, role) VALUES (1, 100, 'gm')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "t07.db"
    _init_db(db)
    with patch.object(campaigns_api, "DB_PATH", str(db)):
        yield TestClient(app)


def test_get_campaign_no_user_id_hides_plan(client):
    r = client.get("/api/campaigns/1")
    assert r.status_code == 200
    body = r.json()
    assert "gm_plan_json" not in body


def test_get_campaign_player_member_hides_plan(client):
    r = client.get("/api/campaigns/1", params={"user_id": 99})
    assert r.status_code == 200
    assert "gm_plan_json" not in r.json()


def test_get_campaign_owner_sees_plan(client):
    r = client.get("/api/campaigns/1", params={"user_id": 10})
    assert r.status_code == 200
    data = r.json()
    assert "gm_plan_json" in data
    assert isinstance(data["gm_plan_json"], str)
    parsed = json.loads(data["gm_plan_json"])
    assert "arcs" in parsed


def test_get_campaign_global_admin_sees_plan(client):
    r = client.get("/api/campaigns/1", params={"user_id": 5})
    assert r.status_code == 200
    assert "gm_plan_json" in r.json()


def test_get_campaign_role_gm_sees_plan(client):
    r = client.get("/api/campaigns/1", params={"user_id": 100})
    assert r.status_code == 200
    assert "gm_plan_json" in r.json()
