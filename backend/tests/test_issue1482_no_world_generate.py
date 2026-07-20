"""TDD: Issue #1482 — usunięcie „Generuj świat" + guard przeciw bulk-wipe world_hexes.

Świat Kresów budujemy ręcznie (Piotr + Claude). Generator całościowy i masowe
kasowanie map_level=0 to jedyne operacje zdolne w sekundę skasować godziny pracy.
Ten test pilnuje, że nie da się ich wywołać przez API.
"""
import hashlib
import sqlite3
import sys

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routers import hex_world

DB_PATH = "/data/ai_gm.db"
_TEST_ADMIN_TOKEN = "tdd_test_token_1482_map"
client = TestClient(app)


def _admin_hash() -> str:
    return hashlib.sha256(_TEST_ADMIN_TOKEN.encode()).hexdigest()


@pytest.fixture(autouse=True)
def setup_teardown():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO admin_tokens (token_hash, label) VALUES (?, 'tdd_1482')",
            (_admin_hash(),),
        )
        conn.commit()
    finally:
        conn.close()
    yield
    conn2 = sqlite3.connect(DB_PATH)
    try:
        conn2.execute("DELETE FROM admin_tokens WHERE token_hash = ?", (_admin_hash(),))
        conn2.commit()
    finally:
        conn2.close()


def _headers():
    return {"Authorization": f"Bearer {_TEST_ADMIN_TOKEN}"}


def _top_hex_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM world_hexes WHERE map_level = 0").fetchone()[0]
    finally:
        conn.close()


def _routes() -> set[str]:
    return {getattr(r, "path", "") for r in app.routes}


# ─── Test główny — generator świata martwy ────────────────────────────────────

def test_world_generate_is_gone():
    """POST /api/admin/world/generate nie generuje już świata → 410 Gone."""
    resp = client.post(
        "/api/admin/world/generate",
        json={"seed": 999482, "radius": 2},
        headers=_headers(),
    )
    assert resp.status_code == 410, (
        f"Generator świata musi być wyłączony (410), dostałem {resp.status_code}: {resp.text}"
    )


def test_world_generate_does_not_touch_map():
    """Nawet wołany z tokenem, /generate nie dokłada ani nie kasuje heksów."""
    before = _top_hex_count()
    client.post(
        "/api/admin/world/generate",
        json={"seed": 999482, "radius": 3},
        headers=_headers(),
    )
    assert _top_hex_count() == before, "POST /generate zmienił liczbę heksów map_level=0!"


# ─── Test główny — guard bulk-wipe ────────────────────────────────────────────

def test_clear_world_blocked_when_map_has_hexes():
    """DELETE /clear na niepustej mapie → 403, mapa nietknięta."""
    before = _top_hex_count()
    assert before > 0, "Test wymaga niepustej mapy świata na DEV"
    resp = client.delete("/api/admin/world/clear", headers=_headers())
    assert resp.status_code == 403, (
        f"Masowe czyszczenie mapy musi być zablokowane (403), dostałem {resp.status_code}: {resp.text}"
    )
    assert _top_hex_count() == before, "DELETE /clear skasował heksy mimo guardu!"


def test_legacy_full_restore_blocked():
    """POST /map/restore BEZ ?region= nadpisałby wszystkie krainy → 403 z podpowiedzią."""
    before = _top_hex_count()
    resp = client.post("/api/admin/world/map/restore", headers=_headers())
    assert resp.status_code == 403, (
        f"Pełny restore (wszystkie krainy) musi być zablokowany (403), dostałem {resp.status_code}: {resp.text}"
    )
    assert "region" in resp.json().get("detail", "").lower(), (
        "Komunikat 403 musi kierować na wariant per-kraina (?region=)"
    )
    assert _top_hex_count() == before, "Legacy restore nadpisał mapę mimo guardu!"


def test_guard_allows_operation_on_empty_map():
    """Guard nie blokuje, gdy mapa jest pusta (świeża baza) — inaczej nie da się jej odtworzyć."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE world_regions (key TEXT, status TEXT)")
    conn.execute("CREATE TABLE world_hexes (id INTEGER PRIMARY KEY, region TEXT, map_level INT)")
    conn.execute("INSERT INTO world_regions VALUES ('kresy', 'live')")
    # brak heksów → operacja masowa dozwolona
    hex_world._guard_bulk_wipe(conn, "test")

    conn.execute("INSERT INTO world_hexes (region, map_level) VALUES ('kresy', 0)")
    with pytest.raises(Exception) as exc:
        hex_world._guard_bulk_wipe(conn, "test")
    assert getattr(exc.value, "status_code", None) == 403
    conn.close()


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_generate_local_endpoint_still_registered():
    """Podmapy osad (generate-local, R2 #1242) zostają — to nie jest generator świata."""
    assert "/api/admin/world/generate-local" in _routes()


def test_per_region_restore_endpoint_still_registered():
    """Restore per-kraina (oficjalna ścieżka odtworzenia z gita) zostaje."""
    assert "/api/admin/world/map/restore" in _routes()


def test_single_hex_patch_still_works():
    """Edycja pojedynczego hexa (admin→Mapa) nie jest objęta guardem."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT q, r, label FROM world_hexes WHERE map_level = 0 AND parent_hex_id IS NULL "
            "ORDER BY id LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row, "Brak heksów do testu PATCH"
    resp = client.patch(
        f"/api/admin/world/hexes/{row['q']}/{row['r']}",
        json={"label": row["label"]},  # no-op: ta sama wartość
        headers=_headers(),
    )
    assert resp.status_code == 200, f"PATCH pojedynczego hexa zepsuty: {resp.status_code}: {resp.text}"


def test_world_map_endpoint_still_works():
    """GET /api/admin/world/map dalej zwraca heksy."""
    resp = client.get("/api/admin/world/map", headers=_headers())
    assert resp.status_code == 200, f"GET /map zepsuty: {resp.status_code}"
    assert "hexes" in resp.json()
