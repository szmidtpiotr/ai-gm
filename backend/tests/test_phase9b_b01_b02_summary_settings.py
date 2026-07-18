"""B01/B02 — summary settings UI/backend and dual preview access mode."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.api import campaigns as campaigns_mod
from app.main import app
from app.routers import settings as settings_mod
from app.services import admin_auth as admin_auth_mod
from app.services.admin_auth import hash_admin_token


def _schema() -> str:
    return """
    """ + table_sql("game_config_meta") + """
    CREATE TABLE campaigns (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        system_id TEXT NOT NULL,
        model_id TEXT NOT NULL,
        owner_user_id INTEGER NOT NULL,
        language TEXT DEFAULT 'pl',
        mode TEXT DEFAULT 'solo',
        status TEXT DEFAULT 'active',
        created_at TEXT,
        gm_plan_json TEXT NOT NULL DEFAULT '{}'
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id)
    VALUES (1, 't', 'fantasy', 'm', 10);
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        is_admin INTEGER DEFAULT 0
    );
    INSERT INTO users (id, username, is_admin) VALUES
        (10, 'owner', 0),
        (11, 'other', 0);
    CREATE TABLE admin_tokens (
        token_hash TEXT PRIMARY KEY,
        label TEXT
    );
    """


def _init_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_schema())
        conn.execute(
            "INSERT INTO admin_tokens(token_hash, label) VALUES (?, ?)",
            (hash_admin_token("secret-token"), "tests"),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client_and_db(tmp_path, monkeypatch):
    db = tmp_path / "b01_b02.db"
    _init_db(db)
    monkeypatch.setattr(campaigns_mod, "DB_PATH", str(db))
    monkeypatch.setattr(settings_mod, "DB_PATH", str(db))
    monkeypatch.setattr(admin_auth_mod, "DB_PATH", str(db))
    return TestClient(app), db


def test_get_summary_settings_defaults(client_and_db):
    client, _db = client_and_db
    r = client.get("/api/settings/summary")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["summary_rollup_cooldown_turns"] == 20
    assert data["dual_summary_preview_mode"] == "owner_admin"


def test_patch_summary_settings_admin_only(client_and_db):
    client, db = client_and_db
    r = client.patch(
        "/api/settings/summary",
        headers={"Authorization": "Bearer secret-token"},
        json={
            "summary_rollup_cooldown_turns": 7,
            "dual_summary_preview_mode": "owner",
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["summary_rollup_cooldown_turns"] == 7
    assert data["dual_summary_preview_mode"] == "owner"

    conn = sqlite3.connect(str(db))
    rows = dict(conn.execute("SELECT key, value FROM game_config_meta").fetchall())
    conn.close()
    assert rows["summary_rollup_cooldown_turns"] == "7"
    assert rows["dual_summary_preview_mode"] == "owner"


def test_dual_preview_owner_blocked_without_global_admin_when_mode_owner_admin(client_and_db):
    client, _db = client_and_db
    r = client.post("/api/campaigns/1/dual-summary-preview?user_id=10")
    assert r.status_code == 403
    assert "global admin" in r.json()["detail"]


@patch.object(
    campaigns_mod,
    "generate_dual_summary_preview",
    return_value={
        "player_summary": "P",
        "gm_notes": "G",
        "leaked_plan_tokens": [],
        "model_used": "mock",
        "included_turn_count": 2,
    },
)
def test_dual_preview_owner_admin_allowed_when_mode_owner_admin(mock_preview, client_and_db):
    client, db = client_and_db
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE users SET is_admin = 1 WHERE id = 10")
    conn.commit()
    conn.close()

    r = client.post("/api/campaigns/1/dual-summary-preview?user_id=10")
    assert r.status_code == 200
    body = r.json()
    assert body["player_summary"] == "P"
    assert body["gm_notes"] == "G"
    assert body["persisted"] is False
    assert mock_preview.called


@patch.object(
    campaigns_mod,
    "generate_dual_summary_preview",
    return_value={
        "player_summary": "P2",
        "gm_notes": "G2",
        "leaked_plan_tokens": [],
        "model_used": "mock",
        "included_turn_count": 1,
    },
)
def test_dual_preview_owner_allowed_when_mode_owner(mock_preview, client_and_db):
    client, _db = client_and_db
    rp = client.patch(
        "/api/settings/summary",
        headers={"Authorization": "Bearer secret-token"},
        json={"dual_summary_preview_mode": "owner"},
    )
    assert rp.status_code == 200

    r = client.post("/api/campaigns/1/dual-summary-preview?user_id=10")
    assert r.status_code == 200
    body = r.json()
    assert body["player_summary"] == "P2"
    assert body["gm_notes"] == "G2"
    assert body["persisted"] is False
    assert mock_preview.called
