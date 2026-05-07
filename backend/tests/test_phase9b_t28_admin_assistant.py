import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.routers.admin as admin_router_module
import app.services.admin_config as admin_config_service
from app.routers.admin import require_admin_token, router as admin_router


def _init_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE admin_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                row_key TEXT,
                operation TEXT NOT NULL,
                old_values TEXT,
                new_values TEXT,
                performed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE game_config_conditions (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                effect_json TEXT NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                stackable INTEGER NOT NULL DEFAULT 0,
                auto_remove TEXT,
                locked_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _client(db_path: Path) -> TestClient:
    app = FastAPI()
    app.include_router(admin_router, prefix="/api")
    app.dependency_overrides[require_admin_token] = lambda: None
    admin_config_service.DB_PATH = str(db_path)
    return TestClient(app)


def test_admin_assistant_condition_draft_and_save(tmp_path):
    db_path = tmp_path / "t28_conditions.db"
    _init_db(db_path)
    client = _client(db_path)
    with patch.object(
        admin_router_module,
        "generate_chat",
        return_value=(
            '{"reply":"Prepared a poison condition draft.","draft":{"key":"ashen_poison","label":"Ashen Poison",'
            '"description":"Poison that weakens the target.","stackable":false,'
            '"effect_json":{"schema_version":1,"effect_category":"character_condition",'
            '"effects":[{"type":"periodic_save","dc_key":"standard","tick":"start_turn","expires":"save_success","value":2}]}}}'
        ),
    ):
        draft_resp = client.post(
            "/api/admin/assistant/draft",
            json={"resource": "conditions", "message": "Poisoned condition dealing 2 damage each turn."},
        )
    assert draft_resp.status_code == 200, draft_resp.text
    draft_data = draft_resp.json()
    assert draft_data["valid"] is True
    assert draft_data["assistant_reply"] == "Prepared a poison condition draft."
    assert draft_data["validated_payload"]["key"] == "ashen_poison"
    assert isinstance(draft_data["validated_payload"]["effect_json"], str)

    save_resp = client.post(
        "/api/admin/assistant/save",
        json={"resource": "conditions", "payload": draft_data["validated_payload"]},
    )
    assert save_resp.status_code == 200, save_resp.text
    item = save_resp.json()["item"]
    assert item["key"] == "ashen_poison"
    assert item["label"] == "Ashen Poison"


def test_admin_assistant_draft_reports_validation_errors(tmp_path):
    db_path = tmp_path / "t28_invalid.db"
    _init_db(db_path)
    client = _client(db_path)
    with patch.object(
        admin_router_module,
        "generate_chat",
        return_value='{"reply":"Drafted it.","draft":{"key":"broken_condition"}}',
    ):
        draft_resp = client.post(
            "/api/admin/assistant/draft",
            json={"resource": "conditions", "message": "Make some broken condition."},
        )
    assert draft_resp.status_code == 200, draft_resp.text
    draft_data = draft_resp.json()
    assert draft_data["valid"] is False
    assert any("label" in err for err in draft_data["errors"])
    assert any("effect_json" in err for err in draft_data["errors"])
