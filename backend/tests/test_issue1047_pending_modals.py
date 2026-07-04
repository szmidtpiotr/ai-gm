"""TDD: Issue #1047 — Pending modals: required fields, locations, AI fill endpoint."""
import sys
import sqlite3
import pytest

sys.path.insert(0, '/app')

DB_PATH = "/data/ai_gm.db"
_ENEMY_KEY = "test_enemy_issue1047_xyz"
_LOC_KEY   = "test_loc_issue1047_xyz"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _admin_headers():
    """#1154: world_review wymaga teraz tokena admina."""
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    for u, p in (("admin", "admin"), ("demo", "demo")):
        r = c.post("/api/admin/dev-login", json={"username": u, "password": p})
        if r.status_code == 200:
            return {"Authorization": f"Bearer {r.json()['token']}"}
    return {}


@pytest.fixture(autouse=True)
def seed_and_cleanup():
    conn = _conn()
    conn.execute("""
        INSERT OR REPLACE INTO game_config_enemies
        (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
         tier, review_status)
        VALUES (?,?,20,12,3,0,'1d6','standard','pending_review')
    """, (_ENEMY_KEY, 'Testowy Bandyta 1047'))
    conn.execute("""
        INSERT OR REPLACE INTO game_locations (key, label, review_status, is_active)
        VALUES (?,?,'pending_review',1)
    """, (_LOC_KEY, 'Testowa Lokacja 1047'))
    conn.commit()
    conn.close()
    yield
    conn2 = _conn()
    conn2.execute("DELETE FROM game_config_enemies WHERE key = ?", (_ENEMY_KEY,))
    conn2.execute("DELETE FROM game_locations WHERE key = ?", (_LOC_KEY,))
    conn2.commit()
    conn2.close()


# ─── Test 1: pending enemies must return combat fields ───────────────────────

def test_pending_enemies_returns_full_combat_fields():
    """get_pending_enemies must return ac_base, attack_bonus, damage_die, dex_modifier."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.get('/api/admin/world/pending/enemies', headers=_admin_headers())
    assert r.status_code == 200
    items = r.json().get('items', [])
    our = next((i for i in items if i['key'] == _ENEMY_KEY), None)
    assert our is not None, f"Test enemy not in pending list (keys: {[i['key'] for i in items[:5]]})"
    assert 'ac_base' in our,       "ac_base missing from pending enemies"
    assert 'attack_bonus' in our,  "attack_bonus missing"
    assert 'damage_die' in our,    "damage_die missing"
    assert 'dex_modifier' in our,  "dex_modifier missing"
    assert 'min_level' in our,     "min_level missing"
    assert our['ac_base'] == 12
    assert our['damage_die'] == '1d6'


# ─── Test 2: pending locations must include created_at ───────────────────────

def test_pending_locations_returns_created_at():
    """get_pending_locations must include created_at so frontend can show date."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.get('/api/admin/world/pending/locations', headers=_admin_headers())
    assert r.status_code == 200
    items = r.json().get('items', [])
    our = next((i for i in items if i['key'] == _LOC_KEY), None)
    assert our is not None, "Test location not in pending list"
    assert 'created_at' in our, "created_at missing from pending locations"


# ─── Test 3: fill endpoint must exist ────────────────────────────────────────

def test_pending_fill_endpoint_exists_not_404():
    """POST /api/admin/world/pending/fill/enemy/{key} must be registered (not 404)."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.post(f'/api/admin/world/pending/fill/enemy/{_ENEMY_KEY}', headers=_admin_headers())
    assert r.status_code != 404, \
        f"Endpoint not registered — got 404. Register POST /pending/fill/{{entity_type}}/{{key}}"


# ─── Test 4: fill returns {suggestions: dict} ────────────────────────────────

def test_pending_fill_returns_suggestions_dict():
    """fill endpoint must return JSON with 'suggestions' key (dict)."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.post(f'/api/admin/world/pending/fill/enemy/{_ENEMY_KEY}', headers=_admin_headers())
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert 'suggestions' in data, f"Missing 'suggestions' key in: {data}"
    assert isinstance(data['suggestions'], dict), "'suggestions' must be a dict"
