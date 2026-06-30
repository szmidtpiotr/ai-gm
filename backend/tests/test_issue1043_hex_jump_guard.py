"""TDD: Issue #1043 — hex jump guard: narrative travel cannot teleport >MAX_NARRATIVE_HEX_JUMP hexes."""
import json
import sqlite3
import sys
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, "/app")


# ─── Test główny — guard w _update_hex_world_state ───────────────────────────

def test_update_hex_world_state_blocks_far_jump_via_location_key():
    """After LLM MOVEMENT with to_location_key that resolves to >15 hexes away — hex must NOT change."""
    from app.services.turn_pipeline import _update_hex_world_state

    conn = MagicMock(spec=sqlite3.Connection)

    # Player is at (21, 1) — Wolanka
    session_flags = {"current_hex": {"q": 21, "r": 1}}

    # LLM returned MOVEMENT to some location_key, destination_q/r not set (LLM path)
    mechanic_result = {
        "action_type": "MOVEMENT",
        "outcome": "SUCCESS",
        "to_location_key": "siwe_granie_hub",  # hub at (48,-24) — 27+ hexes away
        # NO destination_q / destination_r — this is the LLM (non-directional) path
    }

    # resolve_location_key_to_hex returns far coords (distance from (21,1) to (48,-24) is 48)
    far_hex = (48, -24)

    def mock_execute(query, params=()):
        m = MagicMock()
        if "resolve" in query.lower() or "location_key = ?" in query or "world_hexes" in query:
            row = MagicMock()
            row.__getitem__ = lambda s, k: {"q": 40, "r": -53}.get(k)
            m.fetchone.return_value = row
        else:
            m.fetchone.return_value = None
        return m

    conn.execute.side_effect = mock_execute

    with patch(
        "app.services.hex_travel_service.resolve_location_key_to_hex",
        return_value=far_hex,
    ):
        _update_hex_world_state(mechanic_result, session_flags, conn, campaign_id=1)

    # current_hex must NOT have changed to (40,-53)
    assert session_flags.get("current_hex") == {"q": 21, "r": 1}, (
        f"Hex jumped to {session_flags.get('current_hex')} — should stay at (21,1)"
    )


def test_update_hex_world_state_allows_close_location_key():
    """LLM MOVEMENT to location ≤15 hexes away via location_key — move IS allowed."""
    from app.services.turn_pipeline import _update_hex_world_state

    conn = MagicMock(spec=sqlite3.Connection)

    session_flags = {"current_hex": {"q": 21, "r": 1}}

    mechanic_result = {
        "action_type": "MOVEMENT",
        "outcome": "SUCCESS",
        "to_location_key": "neighbor_loc",  # 10 hexes away at (25,7)
    }

    # Distance from (21,1) to (25,7) = max(4, 6, 10) = 10 — within 15 limit
    close_hex = (25, 7)

    def mock_execute(query, params=()):
        m = MagicMock()
        if "world_hexes" in query and "location_key" in query:
            row = MagicMock()
            row.__getitem__ = lambda s, k: {"location_key": "neighbor_loc"}.get(k, None)
            m.fetchone.return_value = row
        else:
            m.fetchone.return_value = None
        return m

    conn.execute.side_effect = mock_execute

    def mock_execute(query, params=()):
        m = MagicMock()
        if "world_hexes" in query and "location_key" in query:
            row = MagicMock()
            row.__getitem__ = lambda s, k: {"location_key": "neighbor_loc"}.get(k, None)
            m.fetchone.return_value = row
        else:
            m.fetchone.return_value = None
        return m

    conn.execute.side_effect = mock_execute

    with patch(
        "app.services.hex_travel_service.resolve_location_key_to_hex",
        return_value=close_hex,
    ):
        _update_hex_world_state(mechanic_result, session_flags, conn, campaign_id=1)

    # current_hex SHOULD have moved to (25,7) — within 15-hex limit
    assert session_flags.get("current_hex") == {"q": 25, "r": 7}, (
        f"10-hex move to named location should be allowed — got {session_flags.get('current_hex')}"
    )


def test_update_hex_world_state_directional_large_jump_allowed():
    """Directional fast-path (destination_q/r explicit) is NOT blocked by distance guard."""
    from app.services.turn_pipeline import _update_hex_world_state

    conn = MagicMock(spec=sqlite3.Connection)
    session_flags = {"current_hex": {"q": 21, "r": 1}}

    # Directional path provides explicit coords (from detect_move_intent ±1 step)
    mechanic_result = {
        "action_type": "MOVEMENT",
        "outcome": "SUCCESS",
        "destination_q": 22,
        "destination_r": 1,
        "to_location_key": "",
    }

    def mock_execute(query, params=()):
        m = MagicMock()
        if "world_hexes" in query and "q = ?" in query:
            row = MagicMock()
            row.__getitem__ = lambda s, k: {"location_key": None}.get(k, None)
            m.fetchone.return_value = row
        else:
            m.fetchone.return_value = None
        return m

    conn.execute.side_effect = mock_execute

    _update_hex_world_state(mechanic_result, session_flags, conn, campaign_id=1)

    # Directional path should still work (it already validates ±1 via detect_move_intent)
    assert session_flags.get("current_hex") == {"q": 22, "r": 1}, (
        f"Directional move should succeed — got {session_flags.get('current_hex')}"
    )


# ─── Test hex_distance helper (sanity) ────────────────────────────────────────

def test_hex_distance_calc():
    """Verify hex_distance formula: Wolanka (21,1) to far corner (40,-53) > 1."""
    from app.services.hex_travel_service import hex_distance

    d = hex_distance(21, 1, 40, -53)
    assert d > 1, f"Expected large distance, got {d}"

    d_near = hex_distance(21, 1, 22, 1)
    assert d_near == 1, f"Adjacent hex should be distance 1, got {d_near}"

    d_same = hex_distance(21, 1, 21, 1)
    assert d_same == 0, f"Same hex should be distance 0, got {d_same}"


# ─── Backward compat — directional fast-path unaffected ──────────────────────

def test_detect_move_intent_still_returns_none_for_no_direction():
    """'idę dalej' still returns None from detect_move_intent (no direction keyword)."""
    from app.services.turn_pipeline import detect_move_intent

    result = detect_move_intent("idę dalej", {"q": 21, "r": 1})
    assert result is None, f"'idę dalej' should return None, got {result}"

    result2 = detect_move_intent("idę w poszukiwaniu tych którzy tędy szli", {"q": 21, "r": 1})
    assert result2 is None, f"'idę w poszukiwaniu...' should return None, got {result2}"


def test_detect_move_intent_directional_still_works():
    """Directional 'idę na północ' still resolves to ±1 hex."""
    from app.services.turn_pipeline import detect_move_intent

    result = detect_move_intent("idę na północ", {"q": 21, "r": 1})
    assert result is not None, "Directional intent must not be None"
    assert result["action_type"] == "MOVEMENT"
    # north = r - 1 in axial coords
    params = result["params"]
    assert abs(params["destination_q"] - 21) <= 1
    assert abs(params["destination_r"] - 1) <= 1
