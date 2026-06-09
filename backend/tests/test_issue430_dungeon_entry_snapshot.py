"""TDD: Issue #430 (E15) — World State snapshot saved on dungeon entry.

When player enters a dungeon, a snapshot with source='dungeon_enter' must be
written to world_state_snapshots containing current HP, max HP, gold, and inventory.
"""

import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

DB_PATH = "/data/ai_gm.db"
TEST_CAMPAIGN_ID = 999445
TEST_CHARACTER_ID = 999377
DUNGEON_KEY = "goblin_warren"

_player_token_cache = None


def _player_token() -> str:
    global _player_token_cache
    if not _player_token_cache:
        r = client.post("/api/auth/login", json={"username": "demo", "password": "demo"})
        assert r.status_code == 200, f"login failed: {r.text}"
        _player_token_cache = r.json()["access_token"]
    return _player_token_cache


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _clear_dungeon_state():
    """Remove dungeon cooldown + active dungeon_run so tests start clean."""
    conn = _db()
    try:
        # Remove cooldown for test character
        conn.execute(
            "DELETE FROM character_dungeon_runs WHERE character_id = ? AND location_key = ?",
            (TEST_CHARACTER_ID, DUNGEON_KEY),
        )
        # Clear dungeon_run from session_flags
        sf_row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (TEST_CAMPAIGN_ID,),
        ).fetchone()
        if sf_row and sf_row["session_flags"]:
            sf = json.loads(sf_row["session_flags"] or "{}")
            sf.pop("dungeon_run", None)
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                (json.dumps(sf, ensure_ascii=False), TEST_CAMPAIGN_ID),
            )
        conn.commit()
    finally:
        conn.close()


def _clear_test_snapshots():
    """Remove dungeon_enter snapshots for test campaign."""
    conn = _db()
    try:
        conn.execute(
            "DELETE FROM world_state_snapshots WHERE campaign_id = ? AND snapshot_source = 'dungeon_enter'",
            (TEST_CAMPAIGN_ID,),
        )
        conn.commit()
    finally:
        conn.close()


def _get_dungeon_enter_snapshot() -> dict | None:
    """Fetch most recent dungeon_enter snapshot for test campaign."""
    conn = _db()
    try:
        row = conn.execute(
            """SELECT snapshot_json FROM world_state_snapshots
               WHERE campaign_id = ? AND snapshot_source = 'dungeon_enter'
               ORDER BY id DESC LIMIT 1""",
            (TEST_CAMPAIGN_ID,),
        ).fetchone()
        if not row:
            return None
        return json.loads(row["snapshot_json"])
    finally:
        conn.close()


def _enter_dungeon() -> dict:
    r = client.post(
        f"/api/dungeons/{DUNGEON_KEY}/enter",
        json={"campaign_id": TEST_CAMPAIGN_ID, "character_id": TEST_CHARACTER_ID},
        headers={"Authorization": f"Bearer {_player_token()}"},
    )
    return {"status": r.status_code, "body": r.json() if r.status_code < 500 else r.text}


# ── FAZA 1: RED tests ─────────────────────────────────────────────────────────

class TestDungeonEntrySnapshotCreated:
    """E15: entering dungeon must save a world_state_snapshots row."""

    def setup_method(self):
        _clear_dungeon_state()
        _clear_test_snapshots()

    def teardown_method(self):
        _clear_dungeon_state()
        _clear_test_snapshots()

    def test_snapshot_row_exists_after_entry(self):
        """world_state_snapshots must have a row with source='dungeon_enter' after entering."""
        result = _enter_dungeon()
        assert result["status"] == 200, f"Enter dungeon failed: {result}"

        snapshot = _get_dungeon_enter_snapshot()
        assert snapshot is not None, (
            "No dungeon_enter snapshot found in world_state_snapshots after POST /dungeons/enter"
        )

    def test_snapshot_source_is_dungeon_enter(self):
        """Snapshot row must use source='dungeon_enter' to distinguish from auto snapshots."""
        conn = _db()
        try:
            _enter_dungeon()
            row = conn.execute(
                """SELECT snapshot_source FROM world_state_snapshots
                   WHERE campaign_id = ? AND snapshot_source = 'dungeon_enter'
                   ORDER BY id DESC LIMIT 1""",
                (TEST_CAMPAIGN_ID,),
            ).fetchone()
            assert row is not None, "No row with snapshot_source='dungeon_enter' found"
            assert row["snapshot_source"] == "dungeon_enter"
        finally:
            conn.close()

    def test_snapshot_contains_current_hp(self):
        """Snapshot JSON must have current_hp field."""
        _enter_dungeon()
        snapshot = _get_dungeon_enter_snapshot()
        assert snapshot is not None
        assert "current_hp" in snapshot, f"Snapshot missing 'current_hp': {list(snapshot.keys())}"
        assert snapshot["current_hp"] is not None, "current_hp must not be None"

    def test_snapshot_contains_max_hp(self):
        """Snapshot JSON must have max_hp field."""
        _enter_dungeon()
        snapshot = _get_dungeon_enter_snapshot()
        assert snapshot is not None
        assert "max_hp" in snapshot, f"Snapshot missing 'max_hp': {list(snapshot.keys())}"

    def test_snapshot_contains_gold(self):
        """Snapshot JSON must have gold field (from characters.gold column)."""
        _enter_dungeon()
        snapshot = _get_dungeon_enter_snapshot()
        assert snapshot is not None
        assert "gold" in snapshot, f"Snapshot missing 'gold': {list(snapshot.keys())}"

    def test_snapshot_contains_inventory(self):
        """Snapshot JSON must have inventory field (list of equipped/carried items)."""
        _enter_dungeon()
        snapshot = _get_dungeon_enter_snapshot()
        assert snapshot is not None
        assert "inventory" in snapshot, f"Snapshot missing 'inventory': {list(snapshot.keys())}"
        assert isinstance(snapshot["inventory"], list), (
            f"inventory must be list, got: {type(snapshot['inventory'])}"
        )


class TestDungeonEntrySnapshotBackwardCompat:
    """Entering dungeon without snapshot support must still return ok=True."""

    def setup_method(self):
        _clear_dungeon_state()
        _clear_test_snapshots()

    def teardown_method(self):
        _clear_dungeon_state()
        _clear_test_snapshots()

    def test_enter_dungeon_still_returns_ok_true(self):
        """Enter endpoint must still return {'ok': True, ...} after adding snapshot logic."""
        result = _enter_dungeon()
        assert result["status"] == 200, f"Unexpected status: {result}"
        assert result["body"].get("ok") is True, f"Expected ok=True: {result['body']}"

    def test_enter_dungeon_still_returns_dungeon_run(self):
        """dungeon_run key must still be present in response."""
        result = _enter_dungeon()
        assert result["status"] == 200
        assert "dungeon_run" in result["body"], f"Missing dungeon_run: {result['body']}"
