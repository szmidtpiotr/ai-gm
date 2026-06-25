"""TDD: Issue #990 — timeline sort: mixed created_at formats cause wrong order after F5."""
import pytest
from app.utils.timestamp import normalize_ts_for_sort


# ─── Test główny — normalizacja formatu ──────────────────────────────────────

def test_normalize_ts_space_format():
    """Space-separated datetime normalizes to ISO-comparable string."""
    result = normalize_ts_for_sort("2026-06-25 12:58:01")
    assert result == "2026-06-25T12:58:01"


def test_normalize_ts_iso_format():
    """ISO datetime with T+Z passes through unchanged (modulo Z strip)."""
    result = normalize_ts_for_sort("2026-06-25T10:27:08Z")
    assert result == "2026-06-25T10:27:08"


def test_timeline_sort_order_correct_after_normalization():
    """Combat turn (10:27) sorts before newer campaign turn (12:58) after normalization."""
    campaign_turn_at = "2026-06-25 12:58:01"   # newer (space format)
    combat_turn_at = "2026-06-25T10:27:08Z"    # older (ISO T+Z)

    # Reproduce the bug: raw string compare puts space(0x20) < T(0x54)
    # so campaign turn ALWAYS sorts before combat turn regardless of actual time
    items_raw = [
        {"kind": "turn",   "at": campaign_turn_at},
        {"kind": "combat", "at": combat_turn_at},
    ]
    bug_order = sorted(items_raw, key=lambda x: x["at"])
    # Bug: campaign_turn (space < T) → first → wrong (it's actually newer)
    assert bug_order[0]["kind"] == "turn"   # bug confirmed: campaign sorts first (wrong)

    # Fix: normalize before sort → combat(10:27) < campaign(12:58) → correct
    fixed_order = sorted(items_raw, key=lambda x: normalize_ts_for_sort(x["at"]))
    assert fixed_order[0]["kind"] == "combat"  # older combat event first ✓
    assert fixed_order[1]["kind"] == "turn"    # newer narrative last ✓


def test_timeline_sort_combat_first_on_same_timestamp():
    """When timestamps equal, combat events sort before campaign turns (tie-break)."""
    ts = "2026-06-25T10:27:08Z"
    items = [
        {"kind": "turn",   "at": ts, "id": 5},
        {"kind": "combat", "at": ts, "id": 100},
    ]

    def sort_key(x):
        return (normalize_ts_for_sort(x["at"]), 0 if x["kind"] == "combat" else 1, x["id"])

    result = sorted(items, key=sort_key)
    assert result[0]["kind"] == "combat"
    assert result[1]["kind"] == "turn"


# ─── Backward compat — empty/None timestamps don't crash ─────────────────────

def test_normalize_ts_empty_string():
    """Empty string doesn't raise — returns empty string."""
    result = normalize_ts_for_sort("")
    assert result == ""


def test_normalize_ts_none_becomes_empty():
    """None-like (falsy) converts to empty string."""
    result = normalize_ts_for_sort(None)
    assert result == ""
