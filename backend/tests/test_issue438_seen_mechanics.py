"""TDD: Issue #438 — E23 seen_mechanics tabela + endpoint mark-seen."""
import sys, json, sqlite3
sys.path.insert(0, "/app")
import pytest
from fastapi.testclient import TestClient

DB_PATH = "/data/ai_gm.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_demo_user_id():
    conn = _get_db()
    try:
        row = conn.execute("SELECT id FROM users WHERE username='demo' LIMIT 1").fetchone()
        return row["id"] if row else 1
    finally:
        conn.close()


def _cleanup(user_id, mechanic_key):
    conn = _get_db()
    try:
        conn.execute("DELETE FROM seen_mechanics WHERE user_id=? AND mechanic_key=?", (user_id, mechanic_key))
        conn.commit()
    finally:
        conn.close()


# ─── Migracja — uruchom lifespan przez TestClient żeby CREATE TABLE IF NOT EXISTS zadziałał

def _ensure_migrations():
    """Trigger app lifespan to run migrations (CREATE TABLE IF NOT EXISTS)."""
    from app.main import app
    with TestClient(app):
        pass  # lifespan runs migrations on startup


# ─── Migracja ────────────────────────────────────────────────────────────────

def test_seen_mechanics_table_exists():
    """Tabela seen_mechanics musi istnieć po migracji."""
    _ensure_migrations()
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='seen_mechanics'"
        ).fetchone()
        assert row is not None, (
            "Tabela 'seen_mechanics' nie istnieje. "
            "Wymagana migracja z kolumnami: user_id, mechanic_key, seen_at."
        )
    finally:
        conn.close()


def test_seen_mechanics_has_correct_columns():
    """seen_mechanics musi mieć kolumny: user_id, mechanic_key, seen_at."""
    _ensure_migrations()
    conn = _get_db()
    try:
        cols = {r["name"] for r in conn.execute("SELECT name FROM pragma_table_info('seen_mechanics')")}
        assert "user_id" in cols, "Brak kolumny user_id w seen_mechanics"
        assert "mechanic_key" in cols, "Brak kolumny mechanic_key w seen_mechanics"
        assert "seen_at" in cols, "Brak kolumny seen_at w seen_mechanics"
    finally:
        conn.close()


# ─── Endpoint mark-seen ───────────────────────────────────────────────────────

def test_mark_seen_endpoint_exists():
    """POST /api/users/{id}/seen-mechanics musi istnieć."""
    from app.main import app
    client = TestClient(app)
    user_id = _get_demo_user_id()
    resp = client.post(f"/api/users/{user_id}/seen-mechanics",
                       json={"mechanic_key": "dice_roll"})
    assert resp.status_code != 404, (
        "Endpoint POST /api/users/{id}/seen-mechanics nie istnieje (#438)"
    )
    _cleanup(user_id, "dice_roll")


def test_mark_seen_records_mechanic():
    """mark-seen zapisuje rekord w seen_mechanics."""
    from app.main import app
    client = TestClient(app)
    user_id = _get_demo_user_id()
    _cleanup(user_id, "dice_roll")

    resp = client.post(f"/api/users/{user_id}/seen-mechanics",
                       json={"mechanic_key": "dice_roll"})
    assert resp.status_code == 200, f"Oczekiwano 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("ok") is True

    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM seen_mechanics WHERE user_id=? AND mechanic_key=?",
            (user_id, "dice_roll")
        ).fetchone()
        assert row is not None, "Brak rekordu w seen_mechanics po mark-seen"
    finally:
        conn.close()
        _cleanup(user_id, "dice_roll")


def test_mark_seen_idempotent():
    """Wielokrotne mark-seen nie tworzy duplikatów."""
    from app.main import app
    client = TestClient(app)
    user_id = _get_demo_user_id()
    _cleanup(user_id, "combat_start")

    client.post(f"/api/users/{user_id}/seen-mechanics", json={"mechanic_key": "combat_start"})
    client.post(f"/api/users/{user_id}/seen-mechanics", json={"mechanic_key": "combat_start"})

    conn = _get_db()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM seen_mechanics WHERE user_id=? AND mechanic_key=?",
            (user_id, "combat_start")
        ).fetchone()["c"]
        assert count == 1, f"Duplikat w seen_mechanics po dwukrotnym mark-seen: count={count}"
    finally:
        conn.close()
        _cleanup(user_id, "combat_start")


# ─── Endpoint GET seen mechanics ─────────────────────────────────────────────

def test_get_seen_mechanics_endpoint_exists():
    """GET /api/users/{id}/seen-mechanics musi zwracać listę."""
    from app.main import app
    client = TestClient(app)
    user_id = _get_demo_user_id()
    resp = client.get(f"/api/users/{user_id}/seen-mechanics")
    assert resp.status_code != 404, (
        "Endpoint GET /api/users/{id}/seen-mechanics nie istnieje (#438)"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "seen" in body, "Odpowiedź musi zawierać klucz 'seen' (lista mechanic_key)"
