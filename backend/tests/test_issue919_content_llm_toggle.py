"""TDD: Issue #919 (H4b) — persisted admin toggle for the content/offline LLM profile.

Rozszerza #818: profil treści (admin AI Kreator → Ollama .170) sterowany z panelu i
zapisywany w DB (`game_config_meta`), nie tylko env. Priorytet: DB > env > default.
Rozdzielenie kanałów z #818 zachowane (nie dotyka runtime rozgrywki).
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services import llm_service as ls
from app.services import llm_admin_service as las


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    for var in (
        "CONTENT_LLM_PROVIDER", "CONTENT_LLM_BASE_URL", "CONTENT_LLM_MODEL",
        "CONTENT_LLM_API_KEY", "CONTENT_LLM_ENABLED",
        "LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    ls.set_runtime_config("", "", "", "")
    ls._hydrate_attempted = True
    # temp DB z game_config_meta dla persystencji profilu treści
    db = tmp_path / "meta.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        "CREATE TABLE game_config_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL, "
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP);"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(las, "DB_PATH", str(db))
    yield
    ls.set_runtime_config("", "", "", "")


# ─── Persystencja w DB (round-trip) ──────────────────────────────────────────

def test_set_then_get_content_profile_roundtrips_and_masks_key():
    las.set_content_llm_profile(
        enabled=True, provider="ollama",
        base_url="http://192.168.1.170:11434", model="gemma4:12b", api_key="secret123",
    )
    prof = las.get_content_llm_profile()
    assert prof is not None
    assert prof["enabled"] is True
    assert prof["model"] == "gemma4:12b"
    assert prof["base_url"] == "http://192.168.1.170:11434"
    assert prof.get("api_key", "") != "secret123"  # zamaskowany


def test_get_content_profile_none_when_unset():
    assert las.get_content_llm_profile() is None


# ─── Resolver: DB > env > default ────────────────────────────────────────────

def test_db_profile_overrides_env_model(monkeypatch):
    monkeypatch.setenv("CONTENT_LLM_MODEL", "env-model")
    las.set_content_llm_profile(enabled=True, model="db-model")
    assert ls.resolve_content_llm_config()["model"] == "db-model"


def test_env_used_when_no_db_profile(monkeypatch):
    monkeypatch.setenv("CONTENT_LLM_MODEL", "env-model")
    assert ls.resolve_content_llm_config()["model"] == "env-model"


def test_default_when_neither_db_nor_env():
    cfg = ls.resolve_content_llm_config()
    assert cfg["provider"] == "ollama"
    assert "11434" in cfg["base_url"]
    assert cfg["model"]  # jakiś domyślny model


# ─── Toggle enabled z DB ─────────────────────────────────────────────────────

def test_db_disabled_overrides_env_enabled_default():
    # env default = ON; DB enabled=False musi wygrać → content-gen wraca na preset
    las.set_content_llm_profile(enabled=False)
    assert ls.content_llm_enabled() is False


def test_db_enabled_true():
    las.set_content_llm_profile(enabled=True)
    assert ls.content_llm_enabled() is True


# ─── Brak wycieku do rozgrywki (separacja jak #818) ──────────────────────────

def test_content_profile_does_not_mutate_gameplay_runtime():
    ls.set_runtime_config("openai", "https://api.openai.com", "gpt-4.1-mini", "sk-secret")
    las.set_content_llm_profile(enabled=True, model="db-model")
    _ = ls.resolve_content_llm_config()
    gameplay = ls.get_effective_config(strict=True)
    assert gameplay["provider"] == "openai"
    assert gameplay["model"] == "gpt-4.1-mini"
