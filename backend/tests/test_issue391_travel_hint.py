"""TDD: Issue #391 — TRAVEL_HINT pills injected alongside STORY_STALE."""
import json

from app.services.game_engine import build_travel_hint_block


def test_travel_hint_block_generation():
    """Test that TRAVEL_HINT block is built correctly from discovered_hexes."""
    # arrange
    discovered_hexes = [
        {"q": 0, "r": -1, "name": "Leśne Ruiny"},
        {"q": 1, "r": -1, "name": "Brzeg Rzeki"},
        {"q": -1, "r": 0, "name": "Grota"},
    ]
    turns_at_location = 7

    # act
    hint = build_travel_hint_block(discovered_hexes, turns_at_location)

    # assert
    assert hint is not None, "TRAVEL_HINT block should be generated when turns >= 5"
    assert "[Leśne Ruiny]" in hint, "First location missing"
    assert "[Brzeg Rzeki]" in hint, "Second location missing"
    assert "[Grota]" in hint, "Third location missing"
    assert "wskaż bohaterowi bezpieczne kierunki" in hint


def test_no_travel_hint_without_discovered_locations():
    """TRAVEL_HINT not generated if no nearby discovered hexes."""
    # arrange
    discovered_hexes = []
    turns_at_location = 8

    # act
    hint = build_travel_hint_block(discovered_hexes, turns_at_location)

    # assert
    assert hint is None, "TRAVEL_HINT should NOT be generated with empty discovered_hexes"


def test_no_travel_hint_below_threshold():
    """TRAVEL_HINT not generated if turns_at_location < 5."""
    # arrange
    discovered_hexes = [
        {"q": 0, "r": -1, "name": "Leśne Ruiny"},
    ]
    turns_at_location = 3

    # act
    hint = build_travel_hint_block(discovered_hexes, turns_at_location)

    # assert
    assert hint is None, "TRAVEL_HINT should NOT be generated when turns < 5"


def test_travel_hint_limited_to_5_locations_max():
    """TRAVEL_HINT shows max 5 location pills (limit shown to LLM)."""
    # arrange
    discovered_hexes = [
        {"q": 0, "r": -1, "name": "Leśne Ruiny"},
        {"q": 1, "r": -1, "name": "Brzeg Rzeki"},
        {"q": -1, "r": 0, "name": "Grota"},
        {"q": 1, "r": 0, "name": "Stara Wiedźźma"},
        {"q": 0, "r": 1, "name": "Opuszczone Miasto"},
        {"q": -1, "r": 1, "name": "Legowisko Bestii"},  # 6th — should be truncated
    ]
    turns_at_location = 10

    # act
    hint = build_travel_hint_block(discovered_hexes, turns_at_location)

    # assert
    assert hint is not None
    assert "Leśne Ruiny" in hint
    assert "Legowisko Bestii" not in hint, "6th location should be truncated to max 5"
    # Count location pills (opening brackets for locations, not for [TRAVEL_HINT:)
    pill_count = hint.count("] [") + 1  # N-1 separators + 1 = N pills
    assert pill_count == 5, f"Should have exactly 5 pills, got {pill_count}"
