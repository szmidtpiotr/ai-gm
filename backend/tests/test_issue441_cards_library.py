"""TDD: Issue #441 — E26 Biblioteka kart: gracz może wrócić do przeczytanych."""
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


def _cleanup(user_id, *keys):
    conn = _get_db()
    try:
        for k in keys:
            conn.execute("DELETE FROM seen_mechanics WHERE user_id=? AND mechanic_key=?", (user_id, k))
        conn.commit()
    finally:
        conn.close()


def _mark_seen(user_id, key):
    conn = _get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO seen_mechanics (user_id, mechanic_key) VALUES (?,?)", (user_id, key)
        )
        conn.commit()
    finally:
        conn.close()


# ─── Endpoint GET /users/{id}/mechanic-cards (biblioteka) ────────────────────

def test_mechanic_cards_endpoint_exists():
    """GET /api/users/{id}/mechanic-cards musi istnieć."""
    from app.main import app
    client = TestClient(app)
    user_id = _get_demo_user_id()
    resp = client.get(f"/api/users/{user_id}/mechanic-cards")
    assert resp.status_code != 404, (
        "Endpoint GET /api/users/{id}/mechanic-cards nie istnieje (#441). "
        "Wymagany dla biblioteki kart onboarding."
    )


def test_mechanic_cards_returns_full_cards_for_seen():
    """GET mechanic-cards zwraca pełne karty (title+content) dla widzianych mechanik."""
    from app.main import app
    client = TestClient(app)
    user_id = _get_demo_user_id()
    _cleanup(user_id, "dice_roll")
    _mark_seen(user_id, "dice_roll")
    try:
        resp = client.get(f"/api/users/{user_id}/mechanic-cards")
        assert resp.status_code == 200, f"Oczekiwano 200, got {resp.status_code}"
        body = resp.json()
        assert "cards" in body, "Odpowiedź musi zawierać klucz 'cards'"
        assert isinstance(body["cards"], list), "'cards' musi być listą"
        keys = [c["mechanic_key"] for c in body["cards"]]
        assert "dice_roll" in keys, "dice_roll jest widziana — powinna być w bibliotece"
        card = next(c for c in body["cards"] if c["mechanic_key"] == "dice_roll")
        assert card.get("title"), "Karta musi zawierać title"
        assert card.get("content"), "Karta musi zawierać content"
    finally:
        _cleanup(user_id, "dice_roll")


def test_mechanic_cards_empty_for_fresh_user():
    """GET mechanic-cards zwraca pustą listę gdy user nic nie widział."""
    from app.main import app
    client = TestClient(app)
    user_id = 999999
    _cleanup(user_id, "dice_roll", "combat_start", "damage_taken", "xp_gained", "gold_gained", "death_save")
    resp = client.get(f"/api/users/{user_id}/mechanic-cards")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["cards"]) == 0, (
        f"Nowy użytkownik powinien mieć 0 kart, got {len(body['cards'])}"
    )


def test_mechanic_cards_includes_seen_at():
    """Karty w bibliotece zawierają pole seen_at (kiedy po raz pierwszy widziana)."""
    from app.main import app
    client = TestClient(app)
    user_id = _get_demo_user_id()
    _cleanup(user_id, "xp_gained")
    _mark_seen(user_id, "xp_gained")
    try:
        resp = client.get(f"/api/users/{user_id}/mechanic-cards")
        body = resp.json()
        card = next((c for c in body["cards"] if c["mechanic_key"] == "xp_gained"), None)
        assert card is not None, "xp_gained powinna być w kartach"
        assert "seen_at" in card, "Karta musi zawierać seen_at"
    finally:
        _cleanup(user_id, "xp_gained")
