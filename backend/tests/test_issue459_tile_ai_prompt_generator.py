"""TDD: Issue #459 (E19b) — Dungeon tile AI prompt generator + ai-create endpoint.

Two new endpoints:
  POST /api/admin/dungeon-tiles/generate-image-prompt  → LLM → English FLUX prompt
  POST /api/admin/dungeon-tiles/ai-create              → LLM → create tile (label + prompt)
"""

import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
DB_PATH = "/data/ai_gm.db"

_admin_token_cache = None


def _admin_token() -> str:
    global _admin_token_cache
    if not _admin_token_cache:
        r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
        assert r.status_code == 200, f"admin login failed: {r.text}"
        _admin_token_cache = r.json()["token"]
    return _admin_token_cache


def _auth():
    return {"Authorization": f"Bearer {_admin_token()}"}


def _first_active_category() -> str:
    """Return the key of the first active tile category from DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT key FROM dungeon_tile_categories WHERE is_active = 1 ORDER BY sort_order LIMIT 1"
        ).fetchone()
        return row["key"] if row else "loch"
    finally:
        conn.close()


def _created_tile_ids():
    """Helper — list tile IDs created by AI during tests (label starts with [TEST])."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id FROM dungeon_tiles WHERE label LIKE '[TEST]%'"
        ).fetchall()
        return [r["id"] for r in rows]
    finally:
        conn.close()


def _cleanup_test_tiles():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM dungeon_tiles WHERE label LIKE '[TEST]%'")
        conn.commit()
    finally:
        conn.close()


# ── generate-image-prompt ──────────────────────────────────────────────────────

class TestGenerateImagePrompt:
    """POST /api/admin/dungeon-tiles/generate-image-prompt returns English FLUX prompt."""

    def test_endpoint_returns_200_with_prompt(self):
        """Endpoint returns 200 and non-empty image_gen_prompt string."""
        cat_key = _first_active_category()
        r = client.post(
            "/api/admin/dungeon-tiles/generate-image-prompt",
            json={"category_key": cat_key},
            headers=_auth(),
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert "image_gen_prompt" in body, f"missing image_gen_prompt in: {body}"
        assert isinstance(body["image_gen_prompt"], str), "image_gen_prompt must be string"
        assert len(body["image_gen_prompt"]) > 20, "prompt too short — LLM probably failed"

    def test_prompt_is_english(self):
        """Generated prompt must be in English (for FLUX) — no Polish keywords."""
        cat_key = _first_active_category()
        r = client.post(
            "/api/admin/dungeon-tiles/generate-image-prompt",
            json={"category_key": cat_key, "description_hint": "stara izba strażnicza"},
            headers=_auth(),
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        prompt = r.json().get("image_gen_prompt", "")
        # Must not be empty; Polish-heavy response would be a bug
        assert len(prompt) > 10
        # Simple sanity: common Polish function words should not dominate
        polish_words = {"który", "która", "które", "jest", "są", "oraz", "przez", "jako"}
        words_lower = set(prompt.lower().split())
        overlap = polish_words & words_lower
        assert len(overlap) < 3, f"prompt looks Polish (overlap={overlap}): {prompt[:120]}"

    def test_missing_category_key_returns_422(self):
        """Missing category_key → validation error 422."""
        r = client.post(
            "/api/admin/dungeon-tiles/generate-image-prompt",
            json={},
            headers=_auth(),
        )
        assert r.status_code in (400, 422), f"expected 400/422, got {r.status_code}"

    def test_nonexistent_category_returns_404(self):
        """Unknown category_key → 404."""
        r = client.post(
            "/api/admin/dungeon-tiles/generate-image-prompt",
            json={"category_key": "nonexistent_xyz_category"},
            headers=_auth(),
        )
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"

    def test_requires_admin_auth(self):
        """Endpoint rejects unauthenticated requests."""
        cat_key = _first_active_category()
        r = client.post(
            "/api/admin/dungeon-tiles/generate-image-prompt",
            json={"category_key": cat_key},
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ── ai-create ─────────────────────────────────────────────────────────────────

class TestAiCreateTile:
    """POST /api/admin/dungeon-tiles/ai-create creates a tile with LLM-generated name + prompt."""

    def teardown_method(self):
        _cleanup_test_tiles()

    def test_ai_create_returns_200_with_tile(self):
        """Endpoint returns 200 and tile object with id, label, image_gen_prompt."""
        cat_key = _first_active_category()
        r = client.post(
            "/api/admin/dungeon-tiles/ai-create",
            json={"category_key": cat_key},
            headers=_auth(),
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert "tile" in body, f"missing 'tile' key in: {body}"
        tile = body["tile"]
        assert "id" in tile and tile["id"] > 0
        assert "label" in tile and len(tile["label"]) > 2, "label too short"
        assert "image_gen_prompt" in tile and len(tile["image_gen_prompt"]) > 20, "prompt too short"
        assert tile["category_key"] == cat_key

    def test_ai_create_persists_to_db(self):
        """Created tile is actually saved in dungeon_tiles table."""
        cat_key = _first_active_category()
        r = client.post(
            "/api/admin/dungeon-tiles/ai-create",
            json={"category_key": cat_key},
            headers=_auth(),
        )
        assert r.status_code == 200
        tile_id = r.json()["tile"]["id"]
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT * FROM dungeon_tiles WHERE id = ?", (tile_id,)).fetchone()
            assert row is not None, f"tile {tile_id} not found in DB"
            assert row["category_key"] == cat_key
            assert row["image_gen_prompt"]
        finally:
            conn.close()

    def test_ai_create_missing_category_returns_422(self):
        """Missing category_key → 400/422."""
        r = client.post(
            "/api/admin/dungeon-tiles/ai-create",
            json={},
            headers=_auth(),
        )
        assert r.status_code in (400, 422), f"expected 400/422, got {r.status_code}"

    def test_ai_create_nonexistent_category_returns_404(self):
        """Unknown category_key → 404."""
        r = client.post(
            "/api/admin/dungeon-tiles/ai-create",
            json={"category_key": "nonexistent_xyz"},
            headers=_auth(),
        )
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"

    def test_ai_create_requires_admin_auth(self):
        """Unauthenticated request → 401."""
        cat_key = _first_active_category()
        r = client.post(
            "/api/admin/dungeon-tiles/ai-create",
            json={"category_key": cat_key},
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}"
