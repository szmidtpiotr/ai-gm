"""T21 — XP spend on core stats (`xp_stat_point_costs` meta + POST …/xp/spend-stat)."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api import characters as characters_mod
from app.main import app
from app.services import xp_service


def _seed_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE game_config_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE game_config_stats (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                description TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                locked_at TEXT
            );
            INSERT INTO game_config_stats (key, label, sort_order) VALUES
                ('str', 'Siła', 1),
                ('dex', 'Zręczność', 2);
            CREATE TABLE campaigns (id INTEGER PRIMARY KEY);
            INSERT INTO campaigns (id) VALUES (1);
            CREATE TABLE users (id INTEGER PRIMARY KEY);
            INSERT INTO users (id) VALUES (1);
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                system_id TEXT NOT NULL,
                sheet_json TEXT NOT NULL
            );
            INSERT INTO characters (campaign_id, user_id, name, system_id, sheet_json)
            VALUES (
                1, 1, 'Hero', 'test',
                '{"stats":{"str":10,"dex":12},"skills":{},"xp_available":500,"xp_lifetime_earned":500}'
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_spend_stat_point_up_unit(tmp_path):
    db = tmp_path / "u.db"
    _seed_db(str(db))
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        out = xp_service.spend_stat_point_up(conn, 1, "str")
        conn.commit()
        assert out["previous_value"] == 10
        assert out["new_value"] == 11
        assert out["xp_spent"] == 85
        assert out["xp_available"] == 500 - 85
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = 1").fetchone()
        sheet = json.loads(row["sheet_json"])
        assert sheet["stats"]["str"] == 11
    finally:
        conn.close()


def test_stat_at_ceiling(tmp_path):
    db = tmp_path / "c.db"
    _seed_db(str(db))
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            "INSERT OR REPLACE INTO game_config_meta (key, value) VALUES ('xp_stat_value_ceiling', '10')"
        )
        conn.commit()
        with pytest.raises(ValueError, match="stat_at_ceiling"):
            xp_service.spend_stat_point_up(conn, 1, "str")
    finally:
        conn.close()


@pytest.fixture
def client_and_db(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    _seed_db(str(db))
    monkeypatch.setattr(characters_mod, "DB_PATH", str(db))
    return TestClient(app)


def test_api_spend_stat_ok(client_and_db):
    r = client_and_db.post(
        "/api/characters/1/xp/spend-stat",
        json={"stat_key": "dex"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["stat_key"] == "dex"
    assert body["previous_value"] == 12
    assert body["new_value"] == 13
    assert body["xp_spent"] == 140


def test_api_unknown_stat(client_and_db):
    r = client_and_db.post(
        "/api/characters/1/xp/spend-stat",
        json={"stat_key": "arcana"},
    )
    assert r.status_code == 400
    assert "Unknown stat" in r.json()["detail"]


def test_xp_snapshot_includes_stat_costs(client_and_db):
    r = client_and_db.get("/api/characters/1/xp")
    assert r.status_code == 200
    body = r.json()
    assert "stat_point_costs" in body
    assert "stat_value_ceiling" in body
    assert body["stat_value_ceiling"] == 20
    assert body["stat_point_costs"]["11"] == 85
