"""TDD: Issue #852 — admin Zawartość Czary tab stays on Ładowanie after re-navigation."""
import re
import sys
import pytest

sys.path.insert(0, "/app")

import httpx
from app.main import app
from fastapi.testclient import TestClient

DEV_URL = "https://aigm-dev.studio-colorbox.com"
client = TestClient(app)


def _admin_token():
    for creds in [{"username": "admin", "password": "admin"}, {"username": "demo", "password": "demo"}]:
        r = client.post("/api/admin/dev-login", json=creds)
        if r.status_code == 200:
            return r.json()["token"]
    pytest.skip("No admin credentials available in test DB")


# ─── Backend API sanity ───────────────────────────────────────────────────────

def test_spells_api_returns_items_list():
    """GET /api/admin/spells must return 200 with items list (backend is fine, bug is frontend-only)."""
    token = _admin_token()
    r = client.get("/api/admin/spells", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert "items" in body, f"Response must have 'items' key, got: {list(body.keys())}"
    assert isinstance(body["items"], list), "body.items must be a list"


# ─── Frontend source validation (checks deployed DEV build) ──────────────────

def test_content_js_init_clears_loaded_set():
    """content.js init() must call _loaded.clear() to reset tab-cache on re-mount (#852).

    Without this, the _loaded Set retains tab keys from the previous visit.
    When the user returns to Zawartość and clicks Czary, _loadTab('spells') hits
    `if (_loaded.has(tab)) return` and exits without fetching — DOM stays on Ładowanie….
    """
    r = httpx.get(f"{DEV_URL}/admin/sections/content.js", timeout=10)
    assert r.status_code == 200
    js = r.text
    # RED: _loaded.clear() not present in init() before fix
    assert "_loaded.clear()" in js, (
        "init() must call _loaded.clear() on entry (#852). "
        "Without it, tabs cached from previous visit never re-load after navigation away and back."
    )


def test_content_js_smart_entry_handler_handles_spells():
    """_onSmartEntrySaved must handle game_config_spells to refresh table after AI Kreator save (#852)."""
    r = httpx.get(f"{DEV_URL}/admin/sections/content.js", timeout=10)
    assert r.status_code == 200
    js = r.text
    # Extract just the _onSmartEntrySaved function body (up to next function/comment block)
    match = re.search(r'function _onSmartEntrySaved\b.*?(?=\n(?:function |//\s*──|export ))', js, re.DOTALL)
    assert match, "_onSmartEntrySaved function not found in content.js"
    handler_body = match.group(0)
    # RED: game_config_spells not in handler before fix
    assert "game_config_spells" in handler_body, (
        "_onSmartEntrySaved must handle 'game_config_spells' (#852). "
        "Without it, saving a spell via AI Kreator does not refresh the spells table.\n"
        f"Current handler:\n{handler_body}"
    )
