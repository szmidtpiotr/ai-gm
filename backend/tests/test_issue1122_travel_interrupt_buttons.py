"""TDD: Issue #1122 — PT12: quick-decision buttons after a travel interrupt.

When a journey is interrupted (combat ended / dusk / forced camp) the composer must
show three mechanical buttons — Kontynuuj podróż / Odpocznij / Rozbij obóz — instead
of the normal narrative pills. Clicking = mechanical action (bypasses LLM lottery):
  - Kontynuuj podróż → TRAVEL_RESUME (POST /campaigns/{id}/travel-resume)
  - Odpocznij       → REST:long
  - Rozbij obóz     → BUILD_CAMP

forced_camp = hero collapsed → resume disabled / endpoint returns 409.
"""
import sys
import json
import sqlite3
import tempfile
import os
import pytest

sys.path.insert(0, "/app")

from app.services.suggested_actions import build_suggested_actions  # noqa: E402


def _mem_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _tp(reason: str) -> dict:
    return {
        "travel_plan": {
            "destination_hex": {"q": 3, "r": -1},
            "destination_label": "Wilczburg",
            "interrupt_reason": reason,
        }
    }


def _actions_by(actions, key):
    return {a["action"]: a for a in actions}


# ─── Test główny: 3 przyciski decyzji po przerwaniu ──────────────────────────

def test_encounter_interrupt_shows_three_decision_buttons():
    """encounter_prompted → composer shows TRAVEL_RESUME + REST:long + BUILD_CAMP."""
    conn = _mem_conn()
    actions = build_suggested_actions(
        conn, campaign_id=1, character_id=1,
        game_state="NARRATIVE", session_flags=_tp("encounter_prompted"),
    )
    by = _actions_by(actions, "action")
    assert "TRAVEL_RESUME" in by, "brak przycisku Kontynuuj podróż"
    assert "REST:long" in by, "brak przycisku Odpocznij"
    assert "BUILD_CAMP" in by, "brak przycisku Rozbij obóz"
    assert by["TRAVEL_RESUME"]["enabled"] is True


def test_dusk_interrupt_resume_enabled():
    """dusk_prompted → Kontynuuj podróż enabled (night march allowed)."""
    conn = _mem_conn()
    actions = build_suggested_actions(
        conn, 1, 1, "NARRATIVE", _tp("dusk_prompted"),
    )
    by = _actions_by(actions, "action")
    assert by.get("TRAVEL_RESUME", {}).get("enabled") is True


def test_forced_camp_disables_resume():
    """forced_camp_prompted → hero collapsed → Kontynuuj podróż disabled."""
    conn = _mem_conn()
    actions = build_suggested_actions(
        conn, 1, 1, "NARRATIVE", _tp("forced_camp_prompted"),
    )
    by = _actions_by(actions, "action")
    assert "TRAVEL_RESUME" in by
    assert by["TRAVEL_RESUME"]["enabled"] is False
    assert "REST:long" in by and "BUILD_CAMP" in by


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_no_interrupt_no_resume_button():
    """No travel_plan → normal narrative pills, no TRAVEL_RESUME."""
    conn = _mem_conn()
    actions = build_suggested_actions(
        conn, 1, 1, "NARRATIVE", {"current_location_key": "somewhere"},
    )
    assert "TRAVEL_RESUME" not in _actions_by(actions, "action")


def test_combat_state_hides_interrupt_buttons():
    """Active combat → combat actions, never the travel interrupt buttons."""
    conn = _mem_conn()
    flags = _tp("encounter_prompted")
    actions = build_suggested_actions(
        conn, 1, 1, "COMBAT", flags,
    )
    by = _actions_by(actions, "action")
    assert "TRAVEL_RESUME" not in by
    assert "ATTACK" in by


# ─── Endpoint gating: POST /campaigns/{id}/travel-resume ─────────────────────

def _seed_session(db_path: str, travel_plan: dict | None):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER, "
        "session_flags TEXT)"
    )
    flags = {"current_hex": {"q": 0, "r": 0}}
    if travel_plan is not None:
        flags["travel_plan"] = travel_plan
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (1, 42, ?)",
        (json.dumps(flags),),
    )
    conn.commit()
    conn.close()


def test_endpoint_blocked_in_combat(monkeypatch):
    """travel-resume during active combat → 409."""
    from fastapi import HTTPException
    import app.api.campaigns as campaigns_mod
    import app.services.combat_service as combat_mod

    monkeypatch.setattr(combat_mod, "get_active_combat", lambda cid: {"combat_id": 7})
    with pytest.raises(HTTPException) as exc:
        campaigns_mod.travel_resume(42)
    assert exc.value.status_code == 409


def test_endpoint_forced_camp_returns_409(monkeypatch):
    """travel-resume with forced_camp interrupt → 409 (hero collapsed)."""
    from fastapi import HTTPException
    import app.api.campaigns as campaigns_mod
    import app.services.combat_service as combat_mod

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        _seed_session(path, {"destination_hex": {"q": 1, "r": 0},
                             "destination_label": "X",
                             "interrupt_reason": "forced_camp_prompted"})
        monkeypatch.setattr(campaigns_mod, "DB_PATH", path)
        monkeypatch.setattr(combat_mod, "get_active_combat", lambda cid: None)
        with pytest.raises(HTTPException) as exc:
            campaigns_mod.travel_resume(42)
        assert exc.value.status_code == 409
    finally:
        os.unlink(path)


def test_endpoint_no_travel_plan_returns_409(monkeypatch):
    """travel-resume with no saved interrupted travel → 409."""
    from fastapi import HTTPException
    import app.api.campaigns as campaigns_mod
    import app.services.combat_service as combat_mod

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        _seed_session(path, None)
        monkeypatch.setattr(campaigns_mod, "DB_PATH", path)
        monkeypatch.setattr(combat_mod, "get_active_combat", lambda cid: None)
        with pytest.raises(HTTPException) as exc:
            campaigns_mod.travel_resume(42)
        assert exc.value.status_code == 409
    finally:
        os.unlink(path)
