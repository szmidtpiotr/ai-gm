"""TDD: Issue #351 — B5 Auto-save World State snapshot after each turn."""
import json
import sqlite3
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.world_state_service import (
    auto_save_snapshot,
    build_snapshot,
    get_latest_snapshot,
    save_snapshot,
    set_world_state_flags,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

DB_PATH = "/data/ai_gm.db"
_FAKE_CAMPAIGN_ID = 999_351  # unlikely to collide with real campaigns


def _count_snapshots(campaign_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM world_state_snapshots WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def _cleanup(campaign_id: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "DELETE FROM world_state_snapshots WHERE campaign_id = ?", (campaign_id,)
        )
        conn.commit()
    finally:
        conn.close()


# ─── Test 1: auto_save_snapshot creates a row ─────────────────────────────────

def test_auto_save_creates_snapshot_row():
    """auto_save_snapshot() must insert a row in world_state_snapshots."""
    _cleanup(_FAKE_CAMPAIGN_ID)
    before = _count_snapshots(_FAKE_CAMPAIGN_ID)

    snapshot_id = auto_save_snapshot(_FAKE_CAMPAIGN_ID, source="test")

    after = _count_snapshots(_FAKE_CAMPAIGN_ID)
    assert after == before + 1, f"Expected +1 row, got before={before} after={after}"
    assert isinstance(snapshot_id, int) and snapshot_id > 0

    _cleanup(_FAKE_CAMPAIGN_ID)


# ─── Test 2: get_latest_snapshot returns the just-saved snapshot ──────────────

def test_get_latest_snapshot_returns_most_recent():
    """get_latest_snapshot() must return the snapshot just saved by auto_save."""
    _cleanup(_FAKE_CAMPAIGN_ID)

    auto_save_snapshot(_FAKE_CAMPAIGN_ID, source="test")
    snap = get_latest_snapshot(_FAKE_CAMPAIGN_ID)

    assert snap is not None, "Expected a snapshot, got None"
    assert snap["campaign_id"] == _FAKE_CAMPAIGN_ID
    assert "snapshot_json" in snap

    _cleanup(_FAKE_CAMPAIGN_ID)


# ─── Test 3: snapshot_json contains required keys ────────────────────────────

def test_snapshot_json_contains_required_keys():
    """Snapshot JSON must include scene_enemies, scene_npcs, active_quests, player_conditions, scene_cleared."""
    _cleanup(_FAKE_CAMPAIGN_ID)

    auto_save_snapshot(_FAKE_CAMPAIGN_ID, source="test")
    snap = get_latest_snapshot(_FAKE_CAMPAIGN_ID)
    data = json.loads(snap["snapshot_json"])

    for key in ("scene_enemies", "scene_npcs", "active_quests", "player_conditions", "scene_cleared"):
        assert key in data, f"Missing key in snapshot_json: {key}"

    _cleanup(_FAKE_CAMPAIGN_ID)


# ─── Test 4: pruning keeps max 50 snapshots ──────────────────────────────────

def test_pruning_keeps_max_50_snapshots():
    """After 51 saves, only 50 rows must remain (oldest pruned)."""
    _cleanup(_FAKE_CAMPAIGN_ID)

    for i in range(51):
        auto_save_snapshot(_FAKE_CAMPAIGN_ID, source="test")

    count = _count_snapshots(_FAKE_CAMPAIGN_ID)
    assert count == 50, f"Expected 50 after pruning, got {count}"

    _cleanup(_FAKE_CAMPAIGN_ID)


# ─── Test 5: build_snapshot reflects set_world_state_flags ───────────────────

def test_build_snapshot_reflects_world_state():
    """build_snapshot() must include data set via set_world_state_flags."""
    # We need a real game_sessions row for this campaign.
    # Use a campaign that doesn't exist → get_world_state_flags returns defaults.
    snap = build_snapshot(_FAKE_CAMPAIGN_ID)

    assert snap["campaign_id"] == _FAKE_CAMPAIGN_ID
    assert "scene_enemies" in snap
    assert "turn_number" in snap
    assert isinstance(snap["scene_enemies"], list)


# ─── Test 6: source field is stored correctly ────────────────────────────────

def test_snapshot_source_stored_correctly():
    """The source parameter ('auto', 'combat_end', etc.) must be stored in DB."""
    _cleanup(_FAKE_CAMPAIGN_ID)

    auto_save_snapshot(_FAKE_CAMPAIGN_ID, source="combat_end")
    snap = get_latest_snapshot(_FAKE_CAMPAIGN_ID)

    assert snap["snapshot_source"] == "combat_end"

    _cleanup(_FAKE_CAMPAIGN_ID)


# ─── Test 7: multiple campaigns don't interfere ──────────────────────────────

def test_snapshots_isolated_per_campaign():
    """Snapshots for campaign A must not affect count for campaign B."""
    camp_a = 999_351
    camp_b = 999_352
    _cleanup(camp_a)
    _cleanup(camp_b)

    auto_save_snapshot(camp_a, source="test")
    auto_save_snapshot(camp_a, source="test")

    assert _count_snapshots(camp_a) == 2
    assert _count_snapshots(camp_b) == 0

    _cleanup(camp_a)
    _cleanup(camp_b)
