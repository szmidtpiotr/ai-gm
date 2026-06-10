"""TDD: Issue #481 — F21 World State History UI.

compute_snapshot_diff(snap_a, snap_b) → {"added": [...], "removed": [...], "changed": [...]}
GET /api/admin/campaigns/{id}/world-state/diff?a=<snap_id>&b=<snap_id>
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import sqlite3
import pytest

from app.services.world_state_diff_service import compute_snapshot_diff, flatten_snapshot


# ─── fixtures ────────────────────────────────────────────────────────────────

SNAP_A = {
    "enemies": {"bandit_01": {"hp": 20, "status": "alive"}, "wolf_02": {"hp": 10, "status": "alive"}},
    "npcs": {"aldric": {"alive": True}, "mira": {"alive": True}},
    "quests": {"main_quest": {"stage": 1}, "side_quest_1": {"stage": 0}},
    "flags": {"dungeon_cleared": False, "boss_defeated": False},
}

SNAP_B = {
    "enemies": {"bandit_01": {"hp": 0, "status": "dead"}, "wolf_02": {"hp": 10, "status": "alive"}},
    "npcs": {"aldric": {"alive": False}, "mira": {"alive": True}, "guard_new": {"alive": True}},
    "quests": {"main_quest": {"stage": 2}},
    "flags": {"dungeon_cleared": True, "boss_defeated": False},
}


# ─── compute_snapshot_diff ────────────────────────────────────────────────────

def test_diff_detects_changed_enemy():
    """bandit_01 hp/status changed between snaps."""
    diff = compute_snapshot_diff(SNAP_A, SNAP_B)
    changed_keys = [c["key"] for c in diff["changed"]]
    assert "enemies.bandit_01" in changed_keys


def test_diff_detects_removed_quest():
    """side_quest_1 present in A but not B — should appear in removed."""
    diff = compute_snapshot_diff(SNAP_A, SNAP_B)
    removed_keys = [r["key"] for r in diff["removed"]]
    assert "quests.side_quest_1" in removed_keys


def test_diff_detects_added_npc():
    """guard_new present in B but not A — should appear in added."""
    diff = compute_snapshot_diff(SNAP_A, SNAP_B)
    added_keys = [a["key"] for a in diff["added"]]
    assert "npcs.guard_new" in added_keys


def test_diff_unchanged_not_in_result():
    """wolf_02 identical in A and B — must NOT appear in changed."""
    diff = compute_snapshot_diff(SNAP_A, SNAP_B)
    all_keys = (
        [c["key"] for c in diff["changed"]]
        + [a["key"] for a in diff["added"]]
        + [r["key"] for r in diff["removed"]]
    )
    assert "enemies.wolf_02" not in all_keys


def test_diff_flag_changed():
    """dungeon_cleared changed from False to True."""
    diff = compute_snapshot_diff(SNAP_A, SNAP_B)
    changed_keys = [c["key"] for c in diff["changed"]]
    assert "flags.dungeon_cleared" in changed_keys


def test_diff_returns_dict_structure():
    """Return value has added/removed/changed lists."""
    diff = compute_snapshot_diff(SNAP_A, SNAP_B)
    assert isinstance(diff, dict)
    assert "added" in diff and "removed" in diff and "changed" in diff
    assert isinstance(diff["added"], list)
    assert isinstance(diff["removed"], list)
    assert isinstance(diff["changed"], list)


def test_diff_identical_snaps_empty():
    """Identical snapshots → all lists empty."""
    diff = compute_snapshot_diff(SNAP_A, SNAP_A)
    assert diff["added"] == []
    assert diff["removed"] == []
    assert diff["changed"] == []


def test_diff_empty_snap_a():
    """Empty snap_a → all keys in snap_b are added."""
    diff = compute_snapshot_diff({}, SNAP_B)
    assert len(diff["added"]) > 0
    assert diff["removed"] == []
    assert diff["changed"] == []


def test_diff_empty_snap_b():
    """Empty snap_b → all keys in snap_a are removed."""
    diff = compute_snapshot_diff(SNAP_A, {})
    assert len(diff["removed"]) > 0
    assert diff["added"] == []
    assert diff["changed"] == []


def test_diff_changed_entry_has_before_after():
    """Each 'changed' entry must carry before/after values."""
    diff = compute_snapshot_diff(SNAP_A, SNAP_B)
    changed = {c["key"]: c for c in diff["changed"]}
    assert "enemies.bandit_01" in changed
    entry = changed["enemies.bandit_01"]
    assert "before" in entry and "after" in entry


# ─── flatten_snapshot ─────────────────────────────────────────────────────────

def test_flatten_snapshot_produces_dot_keys():
    """flatten_snapshot converts nested dict to 'section.key' flat map."""
    flat = flatten_snapshot(SNAP_A)
    assert "enemies.bandit_01" in flat
    assert "npcs.aldric" in flat
    assert "quests.main_quest" in flat


def test_flatten_snapshot_ignores_non_dict_sections():
    """Sections that are not dicts are skipped gracefully."""
    snap = {"enemies": {"e1": {"hp": 1}}, "metadata": "some_string", "count": 42}
    flat = flatten_snapshot(snap)
    assert "enemies.e1" in flat
    # metadata and count are scalar — not included as nested entries
    assert "metadata" not in flat or flat.get("metadata") == "some_string"
