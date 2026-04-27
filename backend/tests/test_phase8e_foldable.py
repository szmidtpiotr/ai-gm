"""Phase 8E-2 — public UI settings GET and admin PATCH merge."""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routers import settings as settings_mod
from app.routers.settings import router as settings_router
from app.services import ui_panel_settings as ui_mod


def _make_db(path: Path) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE game_config_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def tmp_ui_db(tmp_path):
    p = tmp_path / "ui_settings_test.db"
    _make_db(p)
    with patch.object(ui_mod, "DB_PATH", str(p)):
        yield str(p)


def test_ui_settings_get_returns_defaults(tmp_ui_db):
    app = FastAPI()
    app.include_router(settings_router, prefix="/api")
    client = TestClient(app)
    r = client.get("/api/settings/ui")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    panels = body["data"]["panels"]
    assert panels["stats"] == "expanded"
    assert panels["skills"] == "expanded"
    assert panels["identity"] == "expanded"
    assert panels["inventory"] == "expanded"


def test_ui_settings_patch_merges_correctly(tmp_ui_db):
    app = FastAPI()
    app.include_router(settings_router, prefix="/api")
    app.dependency_overrides[settings_mod._require_admin_bearer] = lambda: None
    client = TestClient(app)
    r = client.patch("/api/settings/ui", json={"panels": {"stats": "collapsed"}})
    assert r.status_code == 200
    merged = r.json()["data"]["panels"]
    assert merged["stats"] == "collapsed"
    assert merged["skills"] == "expanded"
    g = client.get("/api/settings/ui").json()["data"]["panels"]
    assert g["stats"] == "collapsed"


def test_ui_settings_patch_unknown_panel_ignored(tmp_ui_db):
    app = FastAPI()
    app.include_router(settings_router, prefix="/api")
    app.dependency_overrides[settings_mod._require_admin_bearer] = lambda: None
    client = TestClient(app)
    r = client.patch(
        "/api/settings/ui",
        json={"panels": {"stats": "collapsed", "bogus": "collapsed", "x": "expanded"}},
    )
    assert r.status_code == 200
    panels = r.json()["data"]["panels"]
    assert "bogus" not in panels
    assert panels["stats"] == "collapsed"


def test_ui_settings_get_after_patch_reflects_change(tmp_ui_db):
    app = FastAPI()
    app.include_router(settings_router, prefix="/api")
    app.dependency_overrides[settings_mod._require_admin_bearer] = lambda: None
    client = TestClient(app)
    client.patch("/api/settings/ui", json={"panels": {"skills": "collapsed", "inventory": "collapsed"}})
    g = client.get("/api/settings/ui").json()["data"]["panels"]
    assert g["skills"] == "collapsed"
    assert g["inventory"] == "collapsed"
    assert g["stats"] == "expanded"
    conn = sqlite3.connect(tmp_ui_db)
    row = conn.execute("SELECT value FROM game_config_meta WHERE key = ?", ("ui_panel_defaults",)).fetchone()
    conn.close()
    assert row
    stored = json.loads(row[0])
    assert stored["skills"] == "collapsed"
