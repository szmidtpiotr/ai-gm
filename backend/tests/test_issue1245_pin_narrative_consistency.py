"""Issue #1245 (R5): the map pin and the narration NEVER diverge.

Piotr's frozen decision (2026-07-05):
- Q1 = variant A: a narrative move to a placed location >1 hex away is a REAL journey
  through ``execute_travel`` (time, encounters, the pin advances, arrival scene AFTER
  reaching the target) — no more half-jump where the location changed but the pin froze.
- Q2 = variant A: a session on a bare hex gets an explicit "wild terrain, no buildings"
  [LOCATION CONTEXT] block (outdoor scene) instead of the block silently vanishing.
"""
import json
import sqlite3
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/app")


def _char_conn(char_id=77):
    """conn whose character lookup returns a hero id."""
    conn = MagicMock(spec=sqlite3.Connection)
    row = {"id": char_id}

    def _execute(query, params=()):
        m = MagicMock()
        if "FROM characters" in query:
            m.fetchone.return_value = row
        else:
            m.fetchone.return_value = None
        return m

    conn.execute.side_effect = _execute
    return conn


# ─── Q1: >1-hex narrative move is promoted to a real journey ──────────────────

def test_narrative_travel_arrival_rewrites_and_nulls_intent():
    from app.api import turns

    conn = _char_conn()
    clean = json.dumps({
        "narrative": "Stajesz w środku młyna.",  # LLM's bogus instant-arrival prose
        "location_intent": {"action": "move", "target_label": "Młyn"},
    }, ensure_ascii=False)

    travel_result = {
        "ok": True,
        "total_hours": 6,
        "encounter": None,
        "hex_data": {"label": "Młyn"},
        "arrived_hex": {"q": 24, "r": 4},
    }
    with patch("app.services.hex_travel_service.execute_travel", return_value=travel_result) as ex:
        out = turns._run_narrative_travel(conn, 1, "mlyn", "Młyn", clean)

    ex.assert_called_once()
    _, kwargs = ex.call_args
    # execute_travel called with the location_key target + actor
    assert ex.call_args[0][2] == {"location_key": "mlyn"}
    assert kwargs["actor"] == 77

    data = json.loads(out)
    assert data["location_intent"] is None, "intent must be nulled — engine owns the move"
    assert "docierasz" in data["narrative"]
    assert "Młyn" in data["narrative"]
    assert "Stajesz w środku młyna" not in data["narrative"], "instant-arrival prose replaced"


def test_narrative_travel_encounter_does_not_claim_arrival():
    from app.api import turns

    conn = _char_conn()
    clean = json.dumps({
        "narrative": "Docierasz do młyna.",
        "location_intent": {"action": "move", "target_label": "Młyn"},
    }, ensure_ascii=False)

    travel_result = {
        "ok": True,
        "total_hours": 3,
        "encounter": {"enemy_key": "wolf"},   # road interrupted mid-way
        "hex_data": {},
        "arrived_hex": {"q": 22, "r": 2},
    }
    with patch("app.services.hex_travel_service.execute_travel", return_value=travel_result):
        out = turns._run_narrative_travel(conn, 1, "mlyn", "Młyn", clean)

    data = json.loads(out)
    assert data["location_intent"] is None
    assert "przerwana" in data["narrative"], "interrupted journey must not claim arrival"
    assert "docierasz do" not in data["narrative"].lower()


def test_narrative_travel_unplaced_location_soft_blocks_without_desync():
    from app.api import turns
    from app.services.hex_travel_service import TravelError

    conn = _char_conn()
    clean = json.dumps({
        "narrative": "Idziesz do ruin.",
        "location_intent": {"action": "move", "target_label": "Ruiny"},
    }, ensure_ascii=False)

    with patch(
        "app.services.hex_travel_service.execute_travel",
        side_effect=TravelError("location_not_placed", "not placed"),
    ):
        out = turns._run_narrative_travel(conn, 1, "ruiny", "Ruiny", clean)

    data = json.loads(out)
    # soft block: intent nulled so the bogus move is not persisted, pin never moved
    assert data["location_intent"] is None


# ─── Q2: wilderness [LOCATION CONTEXT] block instead of silent None ───────────

def _wild_conn(hex_type=None):
    conn = MagicMock(spec=sqlite3.Connection)

    def _execute(query, params=()):
        m = MagicMock()
        if "current_location_id FROM game_sessions" in query:
            m.fetchone.return_value = {"current_location_id": None}  # no anchored loc
        elif "session_flags FROM game_sessions" in query:
            sf = {"current_hex": {"q": 5, "r": 5}} if hex_type else {}
            m.fetchone.return_value = {"session_flags": json.dumps(sf)}
        elif "FROM world_hexes" in query:
            m.fetchone.return_value = {"hex_type": hex_type} if hex_type else None
        elif "FROM hex_type_config" in query:
            m.fetchone.return_value = {"label": "Las"} if hex_type else None
        else:
            m.fetchone.return_value = None
        return m

    conn.execute.side_effect = _execute
    return conn


def test_wilderness_block_emitted_when_no_location():
    from app.services.location_context_injector import build_location_context_block

    block = build_location_context_block("sess-1", _wild_conn(hex_type=None))
    assert block is not None, "block must NOT silently vanish on a wild hex"
    assert "[LOCATION CONTEXT]" in block
    assert "TERENIE DZIKIM" in block
    assert "wilderness" in block
    assert "known_locations" in block


def test_wilderness_block_includes_terrain_when_known():
    from app.services.location_context_injector import build_location_context_block

    block = build_location_context_block("sess-1", _wild_conn(hex_type="forest"))
    assert block is not None
    assert "Las" in block, "known terrain label should ground the outdoor scene"
    assert "TERENIE DZIKIM" in block
