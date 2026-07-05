"""Issue #1043 / #1245 (R5): narrative movement vs. the map pin.

#1043 originally BLOCKED a >1-hex narrative jump (loc changed, pin frozen). Piotr's
frozen decision on #1245 (2026-07-05) supersedes that with **variant A**: a narrative
move to a placed location >1 hex away is now a REAL journey (time + encounters + the pin
advances with the hero) via ``execute_travel``. The block-and-freeze semantics are gone,
so the old "hex must NOT change" assertions are removed here — the live promotion path is
covered in ``test_issue1245_pin_narrative_consistency.py``. The distance/intent helpers
below are unchanged and still guard the directional fast-path.
"""
import sys

sys.path.insert(0, "/app")


# ─── hex_distance helper (sanity) ─────────────────────────────────────────────

def test_hex_distance_calc():
    """Verify hex_distance formula: Wolanka (21,1) to far corner (40,-53) > 1."""
    from app.services.hex_travel_service import hex_distance

    d = hex_distance(21, 1, 40, -53)
    assert d > 1, f"Expected large distance, got {d}"

    d_near = hex_distance(21, 1, 22, 1)
    assert d_near == 1, f"Adjacent hex should be distance 1, got {d_near}"

    d_same = hex_distance(21, 1, 21, 1)
    assert d_same == 0, f"Same hex should be distance 0, got {d_same}"


# ─── Directional fast-path unaffected by variant A ────────────────────────────

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
