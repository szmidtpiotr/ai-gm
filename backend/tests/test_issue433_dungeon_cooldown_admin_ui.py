"""TDD: Issue #433 (E18) — Dungeon cooldown_hours editable from Admin Panel.

PATCH /admin/dungeons/{key} must accept cooldown_hours and dungeon_difficulty.
Both fields must update the DB. UI form coverage verified via API contract.
"""

import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
DB_PATH = "/data/ai_gm.db"
TEST_DUNGEON_KEY = "goblin_warren"

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


def _get_dungeon_from_db(key: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT cooldown_hours, dungeon_difficulty FROM game_dungeons WHERE key = ?", (key,)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def _reset_dungeon(key: str, cooldown: int = 48, difficulty: int = 1):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE game_dungeons SET cooldown_hours = ?, dungeon_difficulty = ? WHERE key = ?",
            (cooldown, difficulty, key),
        )
        conn.commit()
    finally:
        conn.close()


# ── FAZA 1: PATCH cooldown_hours ──────────────────────────────────────────────

class TestPatchCooldownHours:
    """PATCH /admin/dungeons/{key} must update cooldown_hours in DB."""

    def setup_method(self):
        _reset_dungeon(TEST_DUNGEON_KEY, cooldown=48)

    def teardown_method(self):
        _reset_dungeon(TEST_DUNGEON_KEY, cooldown=48)

    def test_patch_cooldown_returns_200(self):
        """PATCH with valid cooldown_hours returns 200."""
        r = client.patch(
            f"/api/admin/dungeons/{TEST_DUNGEON_KEY}",
            json={"cooldown_hours": 24},
            headers=_auth(),
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_patch_cooldown_updates_db(self):
        """PATCH cooldown_hours actually changes value in game_dungeons table."""
        r = client.patch(
            f"/api/admin/dungeons/{TEST_DUNGEON_KEY}",
            json={"cooldown_hours": 12},
            headers=_auth(),
        )
        assert r.status_code == 200
        row = _get_dungeon_from_db(TEST_DUNGEON_KEY)
        assert row["cooldown_hours"] == 12, (
            f"Expected cooldown_hours=12 after PATCH, got {row['cooldown_hours']}"
        )

    def test_patch_cooldown_returns_ok_true(self):
        """PATCH returns {ok: True} on success."""
        r = client.patch(
            f"/api/admin/dungeons/{TEST_DUNGEON_KEY}",
            json={"cooldown_hours": 96},
            headers=_auth(),
        )
        assert r.status_code == 200
        assert r.json().get("ok") is True, f"Expected ok=True: {r.json()}"

    def test_patch_cooldown_requires_auth(self):
        """PATCH without admin token → 401/403."""
        r = client.patch(
            f"/api/admin/dungeons/{TEST_DUNGEON_KEY}",
            json={"cooldown_hours": 12},
        )
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_patch_cooldown_nonexistent_dungeon_returns_404(self):
        """PATCH on unknown dungeon key returns 404."""
        r = client.patch(
            "/api/admin/dungeons/this_key_does_not_exist",
            json={"cooldown_hours": 24},
            headers=_auth(),
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"


# ── FAZA 1: PATCH dungeon_difficulty ──────────────────────────────────────────

class TestPatchDungeonDifficulty:
    """PATCH /admin/dungeons/{key} must accept dungeon_difficulty (E17 column)."""

    def setup_method(self):
        _reset_dungeon(TEST_DUNGEON_KEY, difficulty=1)

    def teardown_method(self):
        _reset_dungeon(TEST_DUNGEON_KEY, difficulty=1)

    def test_patch_dungeon_difficulty_returns_200(self):
        """PATCH with dungeon_difficulty must return 200 (not 400 ignored/filtered)."""
        r = client.patch(
            f"/api/admin/dungeons/{TEST_DUNGEON_KEY}",
            json={"dungeon_difficulty": 3},
            headers=_auth(),
        )
        assert r.status_code == 200, (
            f"Expected 200 for dungeon_difficulty PATCH, got {r.status_code}: {r.text}"
        )

    def test_patch_dungeon_difficulty_updates_db(self):
        """PATCH dungeon_difficulty=3 must change game_dungeons.dungeon_difficulty to 3."""
        r = client.patch(
            f"/api/admin/dungeons/{TEST_DUNGEON_KEY}",
            json={"dungeon_difficulty": 3},
            headers=_auth(),
        )
        assert r.status_code == 200, f"PATCH failed: {r.text}"
        row = _get_dungeon_from_db(TEST_DUNGEON_KEY)
        assert row["dungeon_difficulty"] == 3, (
            f"Expected dungeon_difficulty=3 after PATCH, got {row['dungeon_difficulty']}"
        )

    def test_patch_dungeon_difficulty_range_1_to_5(self):
        """dungeon_difficulty values 1-5 all accepted."""
        for diff in range(1, 6):
            _reset_dungeon(TEST_DUNGEON_KEY, difficulty=1)
            r = client.patch(
                f"/api/admin/dungeons/{TEST_DUNGEON_KEY}",
                json={"dungeon_difficulty": diff},
                headers=_auth(),
            )
            assert r.status_code == 200, f"D{diff} PATCH failed: {r.text}"
            row = _get_dungeon_from_db(TEST_DUNGEON_KEY)
            assert row["dungeon_difficulty"] == diff, (
                f"D{diff}: expected {diff}, got {row['dungeon_difficulty']}"
            )

    def test_patch_cooldown_and_difficulty_together(self):
        """PATCH with both fields simultaneously — both must be saved."""
        r = client.patch(
            f"/api/admin/dungeons/{TEST_DUNGEON_KEY}",
            json={"cooldown_hours": 36, "dungeon_difficulty": 2},
            headers=_auth(),
        )
        assert r.status_code == 200
        row = _get_dungeon_from_db(TEST_DUNGEON_KEY)
        assert row["cooldown_hours"] == 36, f"cooldown_hours not saved: {row}"
        assert row["dungeon_difficulty"] == 2, f"dungeon_difficulty not saved: {row}"


# ── FAZA 1: List endpoint includes both fields ────────────────────────────────

class TestDungeonListFields:
    """GET /admin/dungeons must include cooldown_hours and dungeon_difficulty in response."""

    def test_list_dungeons_returns_200(self):
        r = client.get("/api/admin/dungeons", headers=_auth())
        assert r.status_code == 200, f"List dungeons failed: {r.text}"

    def test_list_dungeons_includes_cooldown_hours(self):
        r = client.get("/api/admin/dungeons", headers=_auth())
        assert r.status_code == 200
        dungeons = r.json().get("items", [])
        assert len(dungeons) > 0, "No dungeons in list"
        for dg in dungeons:
            assert "cooldown_hours" in dg, f"Dungeon {dg.get('key')} missing cooldown_hours"

    def test_list_dungeons_includes_dungeon_difficulty(self):
        """GET /admin/dungeons must return dungeon_difficulty field for each dungeon."""
        r = client.get("/api/admin/dungeons", headers=_auth())
        assert r.status_code == 200
        dungeons = r.json().get("items", [])
        assert len(dungeons) > 0, "No dungeons in list"
        for dg in dungeons:
            assert "dungeon_difficulty" in dg, (
                f"Dungeon {dg.get('key')} missing dungeon_difficulty in list response"
            )
