"""TDD: Issue #443 — E28 Tutorial kampania 'Moja Pierwsza Przygoda'."""
import sys, json, sqlite3
sys.path.insert(0, "/app")
import pytest
from fastapi.testclient import TestClient

DB_PATH = "/data/ai_gm.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_migrations():
    from app.main import app
    with TestClient(app):
        pass


# ─── Migracja DB ─────────────────────────────────────────────────────────────

def test_campaigns_has_is_tutorial_column():
    """Tabela campaigns musi mieć kolumnę is_tutorial po migracji."""
    _ensure_migrations()
    conn = _get_db()
    try:
        cols = {r["name"] for r in conn.execute("SELECT name FROM pragma_table_info('campaigns')")}
        assert "is_tutorial" in cols, (
            "Brak kolumny 'is_tutorial' w tabeli campaigns. "
            "E28 wymaga migracji ALTER TABLE campaigns ADD COLUMN is_tutorial INTEGER DEFAULT 0."
        )
    finally:
        conn.close()


# ─── API — tworzenie kampanii z is_tutorial ───────────────────────────────────

def test_create_campaign_accepts_is_tutorial_flag():
    """POST /api/campaigns musi akceptować is_tutorial w body."""
    from app.main import app
    client = TestClient(app)
    # Get demo user and hero
    conn = _get_db()
    try:
        user_row = conn.execute("SELECT id FROM users WHERE username='demo' LIMIT 1").fetchone()
        user_id = user_row["id"] if user_row else 1
        hero_row = conn.execute(
            "SELECT id FROM characters WHERE user_id=? AND status='idle' LIMIT 1",
            (user_id,),
        ).fetchone()
        if not hero_row:
            hero_row = conn.execute(
                "SELECT id FROM characters WHERE user_id=? LIMIT 1", (user_id,)
            ).fetchone()
        hero_id = hero_row["id"] if hero_row else None
    finally:
        conn.close()

    if not hero_id:
        pytest.skip("No hero for demo user — skipping campaign creation test")

    resp = client.post("/api/campaigns", json={
        "title": "Test Tutorial #443",
        "system_id": "fantasy",
        "model_id": "default",
        "owner_user_id": user_id,
        "language": "pl",
        "is_tutorial": True,
    })
    # Any 2xx response (not 422 = validation error)
    assert resp.status_code not in (422, 400), (
        f"POST /api/campaigns odrzucił is_tutorial: status={resp.status_code}, body={resp.text[:200]}"
    )
    if resp.status_code in (200, 201):
        camp_id = (resp.json().get("campaign") or {}).get("id") or resp.json().get("id")
        if camp_id:
            conn = _get_db()
            try:
                row = conn.execute("SELECT is_tutorial FROM campaigns WHERE id=?", (camp_id,)).fetchone()
                assert row is not None
                assert int(row["is_tutorial"] or 0) == 1, (
                    f"is_tutorial powinno być 1 w DB, got {row['is_tutorial']}"
                )
            finally:
                conn.close()
                # cleanup
                try:
                    conn2 = _get_db()
                    conn2.execute("DELETE FROM campaigns WHERE id=?", (camp_id,))
                    conn2.commit()
                    conn2.close()
                except Exception:
                    pass


# ─── Endpoint sprawdzający czy gracz ma kampanie ─────────────────────────────

def test_user_has_campaigns_endpoint():
    """GET /api/users/{id}/has-campaigns musi istnieć (dla logiki 'pokaż tutorial')."""
    from app.main import app
    client = TestClient(app)
    conn = _get_db()
    try:
        row = conn.execute("SELECT id FROM users WHERE username='demo' LIMIT 1").fetchone()
        user_id = row["id"] if row else 1
    finally:
        conn.close()

    resp = client.get(f"/api/users/{user_id}/has-campaigns")
    assert resp.status_code != 404, (
        "Endpoint GET /api/users/{id}/has-campaigns nie istnieje (#443). "
        "Wymagany do decyzji 'czy pokazać ofertę tutorialu'."
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "has_campaigns" in body, "Odpowiedź musi zawierać klucz 'has_campaigns' (bool)"
    assert isinstance(body["has_campaigns"], bool)
