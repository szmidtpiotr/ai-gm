import os
import sqlite3
from pathlib import Path
import sys
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

import app.routers.settings as settings_router_module
from app.routers.settings import router as settings_router
from app.services import llm_admin_service, llm_service, user_llm_settings


def _init_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            """ + table_sql("game_config_meta") + """
            CREATE TABLE user_llm_settings (
                user_id INTEGER PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'custom',
                provider TEXT NOT NULL,
                base_url TEXT NOT NULL,
                model TEXT NOT NULL,
                api_key TEXT NOT NULL DEFAULT '',
                api_key_set INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE llm_connection_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL,
                base_url TEXT NOT NULL,
                model TEXT NOT NULL,
                api_key TEXT NOT NULL DEFAULT '',
                api_key_set INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _make_settings_client(db_path: Path) -> TestClient:
    app = FastAPI()
    app.include_router(settings_router, prefix="/api")
    user_llm_settings.DB_PATH = str(db_path)
    llm_admin_service.DB_PATH = str(db_path)
    return TestClient(app)


def test_default_mode_without_row_uses_server_env(tmp_path):
    db_path = tmp_path / "t27_default_env.db"
    _init_db(db_path)
    with patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "openai",
            "LLM_BASE_URL": "https://api.example.test/v1",
            "LLM_MODEL": "gpt-4.1",
            "LLM_API_KEY": "env-secret",
        },
        clear=False,
    ):
        llm_service.set_runtime_config("", "", "", "")
        user_llm_settings.DB_PATH = str(db_path)
        masked = user_llm_settings.get_user_llm_settings_masked(101)
        full = user_llm_settings.get_user_llm_settings_full(101)

    assert masked["mode"] == "default"
    assert masked["source"] == "server_default"
    assert masked["provider"] == "openai"
    assert masked["base_url"] == "https://api.example.test"
    assert masked["model"] == "gpt-4.1"
    assert masked["api_key_set"] is True
    assert full["api_key"] == "env-secret"


def test_custom_mode_wins_but_can_fall_back_to_env_api_key(tmp_path):
    db_path = tmp_path / "t27_custom.db"
    _init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO user_llm_settings (user_id, mode, provider, base_url, model, api_key, api_key_set)
            VALUES (1, 'custom', 'openai', 'https://custom.example.test/v1', 'gpt-4o-mini', '', 0)
            """
        )
        conn.commit()
    finally:
        conn.close()

    with patch.dict(os.environ, {"LLM_API_KEY": "fallback-secret"}, clear=False):
        llm_service.set_runtime_config("", "", "", "")
        user_llm_settings.DB_PATH = str(db_path)
        full = user_llm_settings.get_user_llm_settings_full(1)

    assert full["mode"] == "custom"
    assert full["source"] == "user_custom"
    assert full["provider"] == "openai"
    assert full["base_url"] == "https://custom.example.test"
    assert full["model"] == "gpt-4o-mini"
    assert full["api_key"] == "fallback-secret"


def test_default_mode_row_ignores_saved_custom_values(tmp_path):
    db_path = tmp_path / "t27_default_row.db"
    _init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO user_llm_settings (user_id, mode, provider, base_url, model, api_key, api_key_set)
            VALUES (2, 'default', 'openai', 'https://should-not-win.invalid', 'ignored-model', 'ignored-key', 1)
            """
        )
        conn.commit()
    finally:
        conn.close()

    with patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "ollama",
            "LLM_BASE_URL": "http://env-ollama:11434",
            "LLM_MODEL": "gemma4:e4b",
            "LLM_API_KEY": "",
        },
        clear=False,
    ):
        llm_service.set_runtime_config("", "", "", "")
        user_llm_settings.DB_PATH = str(db_path)
        masked = user_llm_settings.get_user_llm_settings_masked(2)

    assert masked["mode"] == "default"
    assert masked["provider"] == "ollama"
    assert masked["base_url"] == "http://env-ollama:11434"
    assert masked["model"] == "gemma4:e4b"
    assert masked["api_key_set"] is False


def test_user_settings_route_accepts_default_mode(tmp_path):
    db_path = tmp_path / "t27_route.db"
    _init_db(db_path)
    with patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "openai",
            "LLM_BASE_URL": "https://server-default.example/v1",
            "LLM_MODEL": "gpt-4.1",
            "LLM_API_KEY": "server-key",
        },
        clear=False,
    ):
        llm_service.set_runtime_config("", "", "", "")
        client = _make_settings_client(db_path)

        put_resp = client.put("/api/users/7/llm-settings", json={"mode": "default"})
        assert put_resp.status_code == 200, put_resp.text
        payload = put_resp.json()
        assert payload["settings"]["mode"] == "default"
        assert payload["settings"]["provider"] == "openai"
        assert payload["settings"]["source"] == "server_default"

        get_resp = client.get("/api/settings/llm")
        assert get_resp.status_code == 200, get_resp.text
        default_payload = get_resp.json()
        assert default_payload["mode"] == "default"
        assert default_payload["provider"] == "openai"
        assert default_payload["source"] == "env"


def test_default_mode_keeps_saved_custom_values_for_later_reuse(tmp_path):
    db_path = tmp_path / "t27_default_preserves_custom.db"
    _init_db(db_path)
    client = _make_settings_client(db_path)

    with patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "ollama",
            "LLM_BASE_URL": "http://env-ollama:11434",
            "LLM_MODEL": "gemma4:e4b",
            "LLM_API_KEY": "",
        },
        clear=False,
    ):
        llm_service.set_runtime_config("", "", "", "")
        put_custom = client.put(
            "/api/users/9/llm-settings",
            json={
                "mode": "custom",
                "provider": "openai",
                "base_url": "https://custom.example.test/v1",
                "model": "gpt-4.1-mini",
                "api_key": "custom-secret",
            },
        )
        assert put_custom.status_code == 200, put_custom.text

        put_default = client.put("/api/users/9/llm-settings", json={"mode": "default"})
        assert put_default.status_code == 200, put_default.text
        assert put_default.json()["settings"]["mode"] == "default"
        assert put_default.json()["settings"]["provider"] == "ollama"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT mode, provider, base_url, model, api_key, api_key_set FROM user_llm_settings WHERE user_id = 9"
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["mode"] == "default"
    assert row["provider"] == "openai"
    assert row["base_url"] == "https://custom.example.test/v1"
    assert row["model"] == "gpt-4.1-mini"
    assert row["api_key"] == "custom-secret"
    assert row["api_key_set"] == 1


def test_admin_global_presets_activate_restore_and_delete(tmp_path):
    db_path = tmp_path / "t27_admin_presets.db"
    _init_db(db_path)
    client = _make_settings_client(db_path)

    with patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "openai",
            "LLM_BASE_URL": "https://server-default.example/v1",
            "LLM_MODEL": "gpt-4.1",
            "LLM_API_KEY": "server-key",
        },
        clear=False,
    ), patch.object(settings_router_module, "verify_admin_token", return_value=True):
        llm_service.set_runtime_config("", "", "", "")

        save_resp = client.post(
            "/api/settings/llm/presets",
            headers={"Authorization": "Bearer test-admin"},
            json={
                "label": "Ops Ollama",
                "provider": "ollama",
                "base_url": "http://ops-ollama:11434",
                "model": "gemma4:e4b",
                "api_key": "",
                "activate": True,
            },
        )
        assert save_resp.status_code == 200, save_resp.text
        save_payload = save_resp.json()
        preset_id = save_payload["active_preset_id"]
        assert save_payload["settings"]["provider"] == "ollama"
        assert save_payload["active_preset_label"] == "Ops Ollama"

        delete_active = client.delete(
            f"/api/settings/llm/presets/{preset_id}",
            headers={"Authorization": "Bearer test-admin"},
        )
        assert delete_active.status_code == 409, delete_active.text

        llm_service.set_runtime_config("", "", "", "")
        llm_admin_service.hydrate_runtime_from_stored_preset()
        restored = client.get("/api/settings/llm")
        assert restored.status_code == 200, restored.text
        restored_payload = restored.json()
        assert restored_payload["provider"] == "ollama"
        assert restored_payload["model"] == "gemma4:e4b"
        assert restored_payload["source"] == "runtime"

        use_env = client.post(
            "/api/settings/llm/use-env",
            headers={"Authorization": "Bearer test-admin"},
        )
        assert use_env.status_code == 200, use_env.text
        use_env_payload = use_env.json()
        assert use_env_payload["active_preset_id"] is None
        assert use_env_payload["settings"]["provider"] == "openai"

        delete_inactive = client.delete(
            f"/api/settings/llm/presets/{preset_id}",
            headers={"Authorization": "Bearer test-admin"},
        )
        assert delete_inactive.status_code == 200, delete_inactive.text
        assert delete_inactive.json()["presets"] == []
