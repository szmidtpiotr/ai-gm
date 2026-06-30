"""TDD: Issue #1050 — narrator asks for destination when player gives vague travel input."""
import sys
sys.path.insert(0, "/app")

import pytest
from unittest.mock import MagicMock


# ─── detect_vague_move_intent ─────────────────────────────────────────────────

def test_vague_move_idę_dalej():
    """'idę dalej' has movement verb, no direction → vague."""
    from app.services.turn_pipeline import detect_vague_move_intent
    assert detect_vague_move_intent("idę dalej") is True


def test_vague_move_ruszamy():
    """'ruszamy' alone → vague."""
    from app.services.turn_pipeline import detect_vague_move_intent
    assert detect_vague_move_intent("ruszamy") is True


def test_vague_move_wyruszam_w_drogę():
    """'wyruszam w drogę' → vague."""
    from app.services.turn_pipeline import detect_vague_move_intent
    assert detect_vague_move_intent("wyruszam w drogę") is True


def test_vague_move_idziemy():
    """'idziemy' → vague."""
    from app.services.turn_pipeline import detect_vague_move_intent
    assert detect_vague_move_intent("idziemy") is True


def test_vague_move_podróżujemy():
    """'podróżujemy dalej w poszukiwaniu' → vague."""
    from app.services.turn_pipeline import detect_vague_move_intent
    assert detect_vague_move_intent("podróżujemy dalej w poszukiwaniu") is True


def test_not_vague_directional_north():
    """'idę na północ' has direction → NOT vague."""
    from app.services.turn_pipeline import detect_vague_move_intent
    assert detect_vague_move_intent("idę na północ") is False


def test_not_vague_directional_east():
    """'ruszam na wschód' has direction → NOT vague."""
    from app.services.turn_pipeline import detect_vague_move_intent
    assert detect_vague_move_intent("ruszam na wschód") is False


def test_not_vague_no_movement_verb():
    """'atakuję goblin' has no movement verb → NOT vague."""
    from app.services.turn_pipeline import detect_vague_move_intent
    assert detect_vague_move_intent("atakuję goblin") is False


def test_not_vague_empty_string():
    """empty string → NOT vague."""
    from app.services.turn_pipeline import detect_vague_move_intent
    assert detect_vague_move_intent("") is False


# ─── detect_move_intent backward compat (unchanged) ──────────────────────────

def test_detect_move_intent_still_none_for_vague():
    """detect_move_intent must still return None for 'idę dalej' (backward compat)."""
    from app.services.turn_pipeline import detect_move_intent
    result = detect_move_intent("idę dalej", {"q": 0, "r": 0})
    assert result is None


def test_detect_move_intent_still_works_for_directional():
    """detect_move_intent must return MOVEMENT dict for 'idę na północ'."""
    from app.services.turn_pipeline import detect_move_intent
    result = detect_move_intent("idę na północ", {"q": 5, "r": 5})
    assert result is not None
    assert result["action_type"] == "MOVEMENT"


# ─── _build_vague_move_hint ──────────────────────────────────────────────────

def test_build_vague_move_hint_contains_system_tag():
    """Hint output must contain [SYSTEM: marker."""
    from app.services.turn_pipeline import _build_vague_move_hint
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    hint = _build_vague_move_hint(conn, {"current_hex": {"q": 5, "r": 5}})
    assert "[SYSTEM:" in hint


def test_build_vague_move_hint_instructs_ask_destination():
    """Hint must instruct narrator to ask for direction."""
    from app.services.turn_pipeline import _build_vague_move_hint
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    hint = _build_vague_move_hint(conn, {"current_hex": {"q": 5, "r": 5}})
    lower = hint.lower()
    assert "dokąd" in lower or "kierunek" in lower or "cel" in lower


def test_build_vague_move_hint_forbids_travel_description():
    """Hint must contain NIE opisuj instruction."""
    from app.services.turn_pipeline import _build_vague_move_hint
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    hint = _build_vague_move_hint(conn, {"current_hex": {"q": 5, "r": 5}})
    assert "NIE opisuj" in hint


def test_build_vague_move_hint_includes_neighbor_names():
    """When DB has neighbors, hint should list them."""
    from app.services.turn_pipeline import _build_vague_move_hint
    conn = MagicMock()
    # Use a plain dict so __getitem__ works naturally
    conn.execute.return_value.fetchone.return_value = {
        "label": "Wolanka", "hex_type": "village", "location_key": None
    }
    hint = _build_vague_move_hint(conn, {"current_hex": {"q": 5, "r": 5}})
    assert "Wolanka" in hint


def test_build_vague_move_hint_works_without_current_hex():
    """Hint must not crash when current_hex is absent."""
    from app.services.turn_pipeline import _build_vague_move_hint
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    hint = _build_vague_move_hint(conn, {})
    assert "[SYSTEM:" in hint


# ─── execute_directional_travel vague path ───────────────────────────────────

def _make_conn_mock_for_travel():
    """Return a MagicMock conn that returns game_sessions row first, then None for world_hexes."""
    conn = MagicMock()
    call_count = [0]

    def execute_side(query, *args, **kwargs):
        m = MagicMock()
        if call_count[0] == 0:
            # First call: game_sessions
            m.fetchone.return_value = {"session_flags": '{"current_hex": {"q": 5, "r": 5}}'}
        else:
            # Subsequent calls: world_hexes neighbors → no data
            m.fetchone.return_value = None
        call_count[0] += 1
        return m

    conn.execute.side_effect = execute_side
    return conn


def test_execute_directional_travel_returns_hint_for_vague_move():
    """execute_directional_travel must return system_fact hint for vague move input."""
    from app.services.turn_pipeline import execute_directional_travel
    conn = _make_conn_mock_for_travel()
    result = execute_directional_travel(conn, 1, 1, {}, "idę dalej")
    assert result["executed"] is False
    assert result["system_fact"] is not None
    assert "[SYSTEM:" in result["system_fact"]


def test_execute_directional_travel_no_hint_for_non_movement():
    """execute_directional_travel must return system_fact=None for non-movement input."""
    from app.services.turn_pipeline import execute_directional_travel
    conn = _make_conn_mock_for_travel()
    result = execute_directional_travel(conn, 1, 1, {}, "atakuję goblin")
    assert result["executed"] is False
    assert result["system_fact"] is None
