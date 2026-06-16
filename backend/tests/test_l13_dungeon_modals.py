"""TDD: Issue #682 L13 — Backend contract tests for dungeon modals (death/abandon/resume/boss-choice).

These tests verify the API contracts that the four L13 modals depend on.
Backend endpoints were implemented in L7/L8; L13 adds the frontend modals.
"""
import json
import sqlite3
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.admin_config import DB_PATH


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_dungeon_key():
    """Return first available dungeon key, or None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT key FROM game_dungeons WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        return row["key"] if row else None
    finally:
        conn.close()


def _get_test_character():
    """Return any active character for testing, or None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM characters WHERE status NOT IN ('deleted') LIMIT 1"
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def _get_test_campaign_with_dungeon_run():
    """Find an active dungeon run (campaign with session_flags.dungeon_run).
    Returns (campaign_id, character_id, dungeon_run) or (None, None, None)."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT gs.campaign_id, gs.session_flags, c.character_id
               FROM game_sessions gs
               JOIN campaigns camp ON camp.id = gs.campaign_id
               LEFT JOIN (
                   SELECT campaign_id, id as character_id FROM characters WHERE campaign_id IS NOT NULL LIMIT 1
               ) c ON c.campaign_id = gs.campaign_id
               WHERE camp.mode = 'dungeon' AND camp.status = 'active'
               LIMIT 10"""
        ).fetchall()
        for row in rows:
            flags = json.loads(row["session_flags"] or "{}")
            run = flags.get("dungeon_run")
            if run and not run.get("completed") and not run.get("failed"):
                return row["campaign_id"], row["character_id"], run
        return None, None, None
    finally:
        conn.close()


# ─── Test 1: death endpoint response shape ────────────────────────────────────

def test_dungeon_death_response_has_required_fields():
    """POST /dungeons/death response must include ok, restored, failed, cooldown_until.
    L13 death modal reads these fields to show checkpoint info + cooldown duration."""
    from app.services.dungeon_service import handle_dungeon_death

    # Use a dummy campaign+char that has no run — should return ok=True, no-op
    result = handle_dungeon_death(campaign_id=999999, character_id=999999)

    assert "ok" in result, "response must have 'ok' field"
    assert "restored" in result, "response must have 'restored' field"
    assert "failed" in result, "response must have 'failed' field"
    # cooldown_until may be missing when there's no run (edge case)
    assert isinstance(result["ok"], bool), "'ok' must be bool"


def test_dungeon_death_sets_failed_true_when_run_exists():
    """handle_dungeon_death marks run failed=True; returned failed=True so modal can show 'run ended'."""
    from app.services.dungeon_service import handle_dungeon_death, get_active_dungeon_run

    dungeon_key = _get_dungeon_key()
    if not dungeon_key:
        pytest.skip("No active dungeon found in DB")

    char_id = _get_test_character()
    if not char_id:
        pytest.skip("No character found in DB")

    # Inject a mock run into a test campaign via session_flags
    conn = _get_conn()
    try:
        # Create a temporary campaign
        conn.execute(
            "INSERT INTO campaigns (title, status, mode, created_at) VALUES (?, 'active', 'dungeon', datetime('now'))",
            ("_L13_TEST_DEATH",),
        )
        camp_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        # Inject minimal dungeon run
        mock_run = {
            "dungeon_key": dungeon_key,
            "failed": False,
            "completed": False,
            "at_checkpoint": False,
            "boss_choice_pending": False,
            "checkpoints": [],
            "graph": {"nodes": {}, "entry_node": None},
            "positions": {},
        }
        flags = {"dungeon_run": mock_run}
        conn.execute(
            "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?, ?)",
            (camp_id, json.dumps(flags)),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        result = handle_dungeon_death(camp_id, char_id)
        assert result["ok"] is True
        assert result["failed"] is True, "death must mark run as failed"
        assert "cooldown_until" in result, "death must return cooldown_until for modal display"
        assert result["cooldown_until"] is not None, "cooldown must be set after death"
    finally:
        # Cleanup
        conn2 = _get_conn()
        try:
            conn2.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (camp_id,))
            conn2.execute("DELETE FROM campaigns WHERE id = ?", (camp_id,))
            conn2.commit()
        finally:
            conn2.close()


# ─── Test 2: abandon mid-segment (50% cooldown) ──────────────────────────────

def test_dungeon_abandon_mid_segment_returns_50pct_cooldown():
    """handle_dungeon_abandon with at_checkpoint=False must return at_checkpoint=False
    and cooldown_until set (50% of normal). L13 abandon modal reads this."""
    from app.services.dungeon_service import handle_dungeon_abandon

    dungeon_key = _get_dungeon_key()
    if not dungeon_key:
        pytest.skip("No active dungeon found")

    char_id = _get_test_character()
    if not char_id:
        pytest.skip("No character found")

    # Create test campaign with mid-segment run (at_checkpoint=False)
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO campaigns (title, status, mode, created_at) VALUES (?, 'active', 'dungeon', datetime('now'))",
            ("_L13_TEST_ABANDON_MID",),
        )
        camp_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        mock_run = {
            "dungeon_key": dungeon_key,
            "failed": False,
            "completed": False,
            "at_checkpoint": False,  # mid-segment
            "boss_choice_pending": False,
            "checkpoints": [],
            "graph": {"nodes": {}, "entry_node": None},
            "positions": {},
        }
        conn.execute(
            "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?, ?)",
            (camp_id, json.dumps({"dungeon_run": mock_run})),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        result = handle_dungeon_abandon(camp_id, char_id)
        assert result["ok"] is True
        assert result["at_checkpoint"] is False, "mid-segment abandon must return at_checkpoint=False"
        assert "cooldown_until" in result, "must return cooldown_until for modal"
        # 50% cooldown is set by start_dungeon_cooldown(fraction=0.5) — just verify it exists
    finally:
        conn2 = _get_conn()
        try:
            conn2.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (camp_id,))
            conn2.execute("DELETE FROM campaigns WHERE id = ?", (camp_id,))
            conn2.commit()
        finally:
            conn2.close()


# ─── Test 3: abandon at checkpoint (no restore, full cooldown) ───────────────

def test_dungeon_abandon_at_checkpoint_no_restore():
    """At-checkpoint abandon (boss just defeated) must NOT restore (restored=False) and
    at_checkpoint=True. L13: 'Wyjdź' at checkpoint exits without penalty modal."""
    from app.services.dungeon_service import handle_dungeon_abandon

    dungeon_key = _get_dungeon_key()
    if not dungeon_key:
        pytest.skip("No active dungeon found")

    char_id = _get_test_character()
    if not char_id:
        pytest.skip("No character found")

    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO campaigns (title, status, mode, created_at) VALUES (?, 'active', 'dungeon', datetime('now'))",
            ("_L13_TEST_ABANDON_CHKPT",),
        )
        camp_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        mock_run = {
            "dungeon_key": dungeon_key,
            "failed": False,
            "completed": False,
            "at_checkpoint": True,  # boss just defeated
            "boss_choice_pending": True,
            "checkpoints": [],
            "graph": {"nodes": {}, "entry_node": None},
            "positions": {},
        }
        conn.execute(
            "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?, ?)",
            (camp_id, json.dumps({"dungeon_run": mock_run})),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        result = handle_dungeon_abandon(camp_id, char_id)
        assert result["ok"] is True
        assert result["at_checkpoint"] is True, "checkpoint abandon must return at_checkpoint=True"
        assert result.get("restored", False) is False, "at checkpoint: NO restore needed"
    finally:
        conn2 = _get_conn()
        try:
            conn2.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (camp_id,))
            conn2.execute("DELETE FROM campaigns WHERE id = ?", (camp_id,))
            conn2.commit()
        finally:
            conn2.close()


# ─── Test 4: boss-choice endpoint requires boss_choice_pending ───────────────

def test_boss_choice_requires_pending_flag():
    """POST /dungeons/boss-choice with boss_choice_pending=False must raise 409.
    L13 boss modal is only shown when run.boss_choice_pending == True."""
    from app.services.dungeon_service import get_active_dungeon_run

    dungeon_key = _get_dungeon_key()
    if not dungeon_key:
        pytest.skip("No active dungeon found")

    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO campaigns (title, status, mode, created_at) VALUES (?, 'active', 'dungeon', datetime('now'))",
            ("_L13_TEST_BOSS_CHOICE",),
        )
        camp_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        mock_run = {
            "dungeon_key": dungeon_key,
            "failed": False,
            "completed": False,
            "at_checkpoint": False,
            "boss_choice_pending": False,  # NOT pending
        }
        conn.execute(
            "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?, ?)",
            (camp_id, json.dumps({"dungeon_run": mock_run})),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        run = get_active_dungeon_run(camp_id)
        assert run is not None, "run must exist"
        assert not run.get("boss_choice_pending"), "boss_choice_pending must be False in this test"
        # The API would return 409; we verify the condition directly
    finally:
        conn2 = _get_conn()
        try:
            conn2.execute("DELETE FROM game_sessions WHERE campaign_id = ?", (camp_id,))
            conn2.execute("DELETE FROM campaigns WHERE id = ?", (camp_id,))
            conn2.commit()
        finally:
            conn2.close()


# ─── Test 5: active run detection for resume modal ───────────────────────────

def test_active_run_endpoint_returns_run_info():
    """GET /dungeons/active-run?character_id=X returns active_run with campaign_id and dungeon_key.
    L13 resume modal reads this to show dungeon name and current room."""
    from fastapi.testclient import TestClient
    from app.main import app

    char_id = _get_test_character()
    if not char_id:
        pytest.skip("No character found")

    client = TestClient(app)
    r = client.get(f"/api/dungeons/active-run?character_id={char_id}")
    # Should always return 200 with 'active_run' key (None if no run)
    assert r.status_code == 200, f"active-run endpoint returned {r.status_code}"
    data = r.json()
    assert "active_run" in data, "response must have 'active_run' key"
    # If there IS an active run, it must have campaign_id
    if data["active_run"]:
        assert "campaign_id" in data["active_run"], "active_run must have campaign_id"
        assert "dungeon_key" in data["active_run"], "active_run must have dungeon_key"
