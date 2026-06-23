"""TDD: Issue #914 — W13 Szwy wzrostu: email capture + i18n scaffold + SEO."""
import os
import sqlite3
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("AI_TEST_MODE", "1")

import pytest
from fastapi.testclient import TestClient


def get_client():
    from app.main import app
    return TestClient(app)


# ─── Email subscribe endpoint ─────────────────────────────────────────────────

def test_subscribe_valid_email():
    """POST /api/showcase/subscribe z prawidłowym emailem → 200, ok=True."""
    client = get_client()
    r = client.post("/api/showcase/subscribe", json={"email": "test914_valid@example.com"})
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_subscribe_invalid_email():
    """POST z nieprawidłowym emailem → 422 (walidacja Pydantic EmailStr)."""
    client = get_client()
    r = client.post("/api/showcase/subscribe", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_subscribe_empty_body():
    """POST bez emaila → 422."""
    client = get_client()
    r = client.post("/api/showcase/subscribe", json={})
    assert r.status_code == 422


def test_subscribe_duplicate_idempotent():
    """Podwójny zapis tego samego emaila nie crashuje — oba zwracają 200."""
    client = get_client()
    email = "dup914_test@example.com"
    r1 = client.post("/api/showcase/subscribe", json={"email": email})
    assert r1.status_code == 200
    r2 = client.post("/api/showcase/subscribe", json={"email": email})
    assert r2.status_code == 200


def test_subscribe_stored_in_db():
    """Email jest zapisany w showcase_subscribers w DB."""
    from app.core.db_runtime import resolve_db_path
    client = get_client()
    email = "stored914@example.com"
    client.post("/api/showcase/subscribe", json={"email": email})
    conn = sqlite3.connect(resolve_db_path())
    row = conn.execute(
        "SELECT email FROM showcase_subscribers WHERE email=?", (email,)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == email


def test_subscribe_table_has_created_at():
    """Tabela showcase_subscribers ma kolumnę created_at."""
    from app.core.db_runtime import resolve_db_path
    conn = sqlite3.connect(resolve_db_path())
    cols = [r[1] for r in conn.execute("PRAGMA table_info(showcase_subscribers)").fetchall()]
    conn.close()
    assert "created_at" in cols
    assert "email" in cols


# ─── Backward compat ──────────────────────────────────────────────────────────

def test_api_health_still_works():
    """GET /api/health nadal odpowiada 200 — brak regresji."""
    client = get_client()
    r = client.get("/api/health")
    assert r.status_code == 200
