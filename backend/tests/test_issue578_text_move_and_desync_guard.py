"""TDD: Issue #578 — text directional move on JSON /turns + anti-desync guard wired into live tor.

(A) `execute_directional_travel` — shared helper that resolves a directional MOVE intent
    mechanically (used by both create_turn JSON and create_turn_stream), so "idę na północ"
    moves the hex on the JSON endpoint too (parity with the streaming player UI).
(B) `guard_travel_desync` — logs `travel_narrated_without_move` to llm_tag_errors when the
    narrative claims travel but no mechanical move happened (U30.4, never wired into the live tor).
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import turn_pipeline as tp


def _mem_conn(hex_q: int = 1, hex_r: int = 0) -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT)")
    c.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?, ?)",
        (999, json.dumps({"current_hex": {"q": hex_q, "r": hex_r}})),
    )
    c.execute(
        "CREATE TABLE llm_tag_errors "
        "(id INTEGER PRIMARY KEY, campaign_id INTEGER, turn_number INTEGER, "
        " tag_raw TEXT, error_type TEXT, ts TEXT)"
    )
    c.commit()
    return c


# ─── (A) shared directional-travel helper ─────────────────────────────────────

def test_execute_directional_travel_moves_hex(monkeypatch):
    """JSON path: a directional MOVE intent resolves travel mechanically and returns a fact."""
    c = _mem_conn(1, 0)
    captured: dict = {}

    def fake_travel(**kw):
        captured.update(kw)
        return {
            "ok": True,
            "arrived_hex": {"q": 1, "r": -1},
            "hex_data": {"hex_type": "forest"},
            "total_hours": 1.0,
            "encounter": None,
        }

    monkeypatch.setattr("app.services.hex_travel_service.resolve_chain_travel", fake_travel)
    monkeypatch.setattr("app.services.clock_service.advance_clock", lambda *a, **k: None)

    res = tp.execute_directional_travel(c, 999, 2, {}, "idę na północ")

    assert res["executed"] is True
    # North from (1,0) → (1,-1) per _DIRECTION_KEYWORDS offset (0,-1)
    assert captured["to_hex"] == (1, -1)
    assert "Podróż wykonana mechanicznie" in res["system_fact"]


def test_execute_directional_travel_refusal_returns_fact(monkeypatch):
    """When the mechanic refuses, helper does not mark executed but still feeds the LLM a fact."""
    c = _mem_conn(1, 0)
    monkeypatch.setattr(
        "app.services.hex_travel_service.resolve_chain_travel",
        lambda **kw: {"ok": False, "error": "nieprzejezdny teren"},
    )
    res = tp.execute_directional_travel(c, 999, 2, {}, "idę na północ")
    assert res["executed"] is False
    assert "mechanika odmówiła" in res["system_fact"]


def test_execute_directional_travel_no_intent():
    """Non-movement message → no travel, no fact (LLM handles it normally)."""
    c = _mem_conn(1, 0)
    res = tp.execute_directional_travel(c, 999, 2, {}, "rozglądam się po izbie")
    assert res["executed"] is False
    assert res["system_fact"] is None


# ─── (B) anti-desync guard ────────────────────────────────────────────────────

def test_guard_logs_travel_narrated_without_move():
    """Narrative claims travel but no move happened → log row + return True."""
    c = _mem_conn()
    fired = tp.guard_travel_desync(
        c, 999, "Wyruszasz w długą podróż przez mroczny las.", move_executed=False, turn_number=5
    )
    assert fired is True
    row = c.execute(
        "SELECT error_type FROM llm_tag_errors WHERE campaign_id=999"
    ).fetchone()
    assert row is not None
    assert row["error_type"] == "travel_narrated_without_move"


def test_guard_skips_when_move_executed():
    """If the move did fire mechanically, the guard must not flag a desync."""
    c = _mem_conn()
    fired = tp.guard_travel_desync(
        c, 999, "Wyruszasz w podróż.", move_executed=True, turn_number=5
    )
    assert fired is False
    assert c.execute("SELECT COUNT(*) FROM llm_tag_errors").fetchone()[0] == 0


def test_guard_skips_when_no_travel_language():
    """No travel markers in narrative → no false positive."""
    c = _mem_conn()
    fired = tp.guard_travel_desync(
        c, 999, "Siadasz przy ogniu i czyścisz miecz.", move_executed=False, turn_number=5
    )
    assert fired is False
    assert c.execute("SELECT COUNT(*) FROM llm_tag_errors").fetchone()[0] == 0


# ─── backward compatibility ───────────────────────────────────────────────────

def test_detect_move_intent_still_works():
    """Existing keyword fast-path is unchanged."""
    mv = tp.detect_move_intent("idę na północ", {"q": 0, "r": 0})
    assert mv is not None
    assert mv["action_type"] == "MOVEMENT"
    assert mv["params"]["destination_q"] == 0
    assert mv["params"]["destination_r"] == -1


def test_detect_move_intent_wracam_zawracam_cofam():
    # #1114: "Wracam na północ" nie łapało się na fast-path (wzorzec wymagał końca
    # słowa na "wraca", 1. os. "wracam" miała trailing "m") → narrator opisywał
    # powrót, a hex stał w miejscu (desync narracja↔stan).
    for phrase in (
        "Wracam na północ, ku traktowi.",
        "Zawracam na południe.",
        "Cofam się na wschód.",
    ):
        mv = tp.detect_move_intent(phrase, {"q": 5, "r": 5})
        assert mv is not None, phrase
        assert mv["action_type"] == "MOVEMENT"
