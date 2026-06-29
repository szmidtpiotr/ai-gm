"""TDD: Issue #1026 — travel_hint and STORY_STALE thresholds raised from 5 to 12."""
import sys
import os
sys.path.insert(0, "/app")

from unittest.mock import patch, MagicMock

# ─── Test 1: build_travel_hint_block no longer fires at 5 turns ──────────────

def test_travel_hint_does_not_fire_at_5_turns():
    """After fix, travel hint must NOT appear after only 5 turns at location."""
    from app.services.game_engine import build_travel_hint_block

    hexes = [{"name": "Vilnograd"}, {"name": "Wachstein"}]
    result = build_travel_hint_block(hexes, turns_at_location=5)
    assert result is None, (
        f"travel_hint fired at 5 turns — should only fire at >= 12; got: {result!r}"
    )


def test_travel_hint_does_not_fire_at_9_turns():
    """travel hint must not fire at 9 turns (old threshold was 5)."""
    from app.services.game_engine import build_travel_hint_block

    hexes = [{"name": "Czarnstein"}]
    result = build_travel_hint_block(hexes, turns_at_location=9)
    assert result is None, (
        f"travel_hint fired at 9 turns — should only fire at >= 12; got: {result!r}"
    )


def test_travel_hint_fires_at_new_threshold():
    """travel hint MUST fire at the new default threshold (12 turns)."""
    from app.services.game_engine import build_travel_hint_block

    hexes = [{"name": "Wilczburg"}, {"name": "Grodnov"}]
    result = build_travel_hint_block(hexes, turns_at_location=12)
    assert result is not None, "travel_hint must fire at turns_at_location=12"
    assert "Wilczburg" in result


# ─── Test 2: custom threshold parameter respected ────────────────────────────

def test_travel_hint_accepts_custom_threshold():
    """build_travel_hint_block must accept an explicit threshold parameter."""
    from app.services.game_engine import build_travel_hint_block

    hexes = [{"name": "Sternfeld"}]
    # with threshold=8, should fire at 8
    result = build_travel_hint_block(hexes, turns_at_location=8, threshold=8)
    assert result is not None, "custom threshold=8 should trigger at 8 turns"

    # with threshold=8, should NOT fire at 7
    result2 = build_travel_hint_block(hexes, turns_at_location=7, threshold=8)
    assert result2 is None, "custom threshold=8 should NOT trigger at 7 turns"


# ─── Test 3: story_gravity defaults raised ───────────────────────────────────

def test_story_gravity_default_turns_l1_raised():
    """Default turns_l1 must be 10 (was 5)."""
    from app.services.story_gravity_service import _DEFAULTS
    assert _DEFAULTS["turns_l1"] >= 10, (
        f"turns_l1 default too low: {_DEFAULTS['turns_l1']} (expected >= 10)"
    )


def test_story_gravity_default_travel_hint_threshold():
    """story_gravity_config must have travel_hint_threshold default >= 12."""
    from app.services.story_gravity_service import _DEFAULTS
    assert "travel_hint_threshold" in _DEFAULTS, (
        "travel_hint_threshold missing from _DEFAULTS — must be admin-configurable"
    )
    assert _DEFAULTS["travel_hint_threshold"] >= 12, (
        f"travel_hint_threshold too low: {_DEFAULTS['travel_hint_threshold']}"
    )


# ─── Test 4: get_travel_hint_threshold helper returns sensible default ────────

def test_get_travel_hint_threshold_returns_default():
    """get_travel_hint_threshold() must return >= 12 when no DB config present."""
    from app.services.story_gravity_service import get_travel_hint_threshold

    with patch("app.services.story_gravity_service.sqlite3.connect") as mock_conn:
        mock_conn.return_value.__enter__ = lambda s: s
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.close = MagicMock()

        threshold = get_travel_hint_threshold()
    assert threshold >= 12, f"default threshold too low: {threshold}"


# ─── Test 5: backward compat — empty hex list still returns None ──────────────

def test_travel_hint_returns_none_for_empty_hexes():
    """No hexes → no travel hint, regardless of turns (unchanged behavior)."""
    from app.services.game_engine import build_travel_hint_block

    assert build_travel_hint_block([], turns_at_location=99) is None
    assert build_travel_hint_block(None, turns_at_location=99) is None


# ─── Test 6: context_injector STORY_STALE threshold raised ───────────────────

def test_context_injector_stale_threshold_raised():
    """ContextInjector._STORY_STALE_THRESHOLD must be >= 12 (was 5)."""
    from app.services.context_injector import ContextInjector

    assert ContextInjector._STORY_STALE_THRESHOLD >= 12, (
        f"_STORY_STALE_THRESHOLD still too low: {ContextInjector._STORY_STALE_THRESHOLD}"
    )
