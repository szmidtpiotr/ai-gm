import sqlite3
import sys
from pathlib import Path
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.routers import admin as admin_router  # noqa: E402


def _seed_db(uri: str) -> sqlite3.Connection:
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, session_flags TEXT)")
    conn.execute("CREATE TABLE game_config_meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        """
        CREATE TABLE location_integrity_log (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            character_id INTEGER,
            attempted_move TEXT NOT NULL,
            current_location_key TEXT,
            reason_blocked TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("INSERT INTO campaigns (id, session_flags) VALUES (42, '{\"location_integrity_enabled\": 1}')")
    conn.execute(
        """
        INSERT INTO game_config_meta (key, value) VALUES
        ('location_integrity_enabled', '1'),
        ('location_parser_json_enabled', '1'),
        ('location_parser_fallback_enabled', '1')
        """
    )
    conn.execute(
        """
        INSERT INTO location_integrity_log
        (id, campaign_id, character_id, attempted_move, current_location_key, reason_blocked, created_at)
        VALUES
        (1, 42, 7, 'Las Czarny', 'tavern_hanged_man', 'travel_required', '2026-04-25T10:32:11'),
        (2, 42, 7, 'Ruiny', 'tavern_hanged_man', 'unknown_location_without_create', '2026-04-26T10:32:11'),
        (3, 99, 1, 'Port', 'city_varen', 'travel_required', '2026-04-27T10:32:11')
        """
    )
    conn.commit()
    return conn


def _client(monkeypatch):
    uri = f"file:phase8d_admin_flags_log_{uuid.uuid4().hex}?mode=memory&cache=shared"
    keeper = _seed_db(uri)
    monkeypatch.setattr(admin_router, "ADMIN_SQLITE_PATH", uri)
    monkeypatch.setattr(admin_router, "verify_admin_token", lambda token: token == "ok-admin")
    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api")
    return TestClient(app), keeper


def test_get_patch_delete_flags(monkeypatch):
    client, keeper = _client(monkeypatch)
    try:
        headers = {"Authorization": "Bearer ok-admin"}
        resp_get = client.get("/api/admin/campaigns/42/flags", headers=headers)
        assert resp_get.status_code == 200
        payload = resp_get.json()
        assert payload["effective_flags"]["location_integrity_enabled"] == 1
        assert payload["global_defaults"]["location_parser_json_enabled"] == 1

        resp_patch = client.patch(
            "/api/admin/campaigns/42/flags",
            headers=headers,
            json={
                "location_integrity_enabled": 0,
                "location_parser_fallback_enabled": 0,
            },
        )
        assert resp_patch.status_code == 200
        patched = resp_patch.json()
        assert patched["effective_flags"]["location_integrity_enabled"] == 0
        assert patched["session_overrides"]["location_parser_fallback_enabled"] == 0

        resp_delete = client.delete(
            "/api/admin/campaigns/42/flags/location_integrity_enabled",
            headers=headers,
        )
        assert resp_delete.status_code == 200
        after_delete = resp_delete.json()
        assert "location_integrity_enabled" not in after_delete["session_overrides"]
        assert after_delete["effective_flags"]["location_integrity_enabled"] == 1
    finally:
        keeper.close()


def test_get_location_logs(monkeypatch):
    client, keeper = _client(monkeypatch)
    try:
        headers = {"Authorization": "Bearer ok-admin"}
        resp_campaign_log = client.get(
            "/api/admin/campaigns/42/location-log",
            headers=headers,
            params={"limit": 1, "since": "2026-04-26T00:00:00"},
        )
        assert resp_campaign_log.status_code == 200
        rows = resp_campaign_log.json()
        assert len(rows) == 1
        assert rows[0]["campaign_id"] == 42
        assert rows[0]["attempted_move"] == "Ruiny"

        resp_all = client.get(
            "/api/admin/location-log",
            headers=headers,
            params={"campaign_id": 99},
        )
        assert resp_all.status_code == 200
        rows_all = resp_all.json()
        assert len(rows_all) == 1
        assert rows_all[0]["campaign_id"] == 99
    finally:
        keeper.close()
