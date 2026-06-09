"""TDD: Issue #458 (SB-5) — When committed_d20 is set, regular turn must auto-resolve skill test.

Bug: After the #457 (SB-3/SB-4) guard, ANY turn while SKILL_TEST_PENDING re-surfaces the
pending test — even when committed_d20 is already set. Since _commit_pending_skill_test()
always auto-commits a d20 when creating a pending test, the player can never get past the
re-surface loop through the regular turns endpoint alone.

Fix: in the _kw_scan_already_pending guard, when committed_d20 is present, auto-resolve
the skill test inline (call resolve_skill_test + generate narrative + clear state) instead
of re-surfacing the pending.
"""

import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

DB_PATH = "/data/ai_gm.db"

TEST_CAMPAIGN_ID = 999445
TEST_CHARACTER_ID = 999377
DEMO_USER_ID = 1

_cached_token = None


def _token() -> str:
    global _cached_token
    if not _cached_token:
        r = client.post("/api/auth/login", json={"username": "demo", "password": "demo"})
        assert r.status_code == 200, f"Login failed: {r.text}"
        _cached_token = r.json()["access_token"]
    return _cached_token


def _debug_cmd(text: str) -> dict:
    r = client.post(
        "/api/debug/command",
        json={"character_id": TEST_CHARACTER_ID, "user_id": DEMO_USER_ID, "text": text},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert r.status_code == 200, f"debug cmd failed: {r.status_code} {r.text[:200]}"
    return r.json()


def _read_session_flags() -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (TEST_CAMPAIGN_ID,),
        ).fetchone()
        if not row:
            return {}
        return json.loads(row["session_flags"] or "{}") or {}
    finally:
        conn.close()


def _post_turn(text: str) -> dict:
    r = client.post(
        f"/api/campaigns/{TEST_CAMPAIGN_ID}/turns",
        json={"character_id": TEST_CHARACTER_ID, "text": text},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    return r.json()


def _clear_pending_skill_test() -> None:
    """Remove pending_skill_test from session_flags and reset state=NARRATIVE."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (TEST_CAMPAIGN_ID,),
        ).fetchone()
        if not row:
            return
        sf = json.loads(row["session_flags"] or "{}") or {}
        sf.pop("pending_skill_test", None)
        sf["state"] = "NARRATIVE"
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(sf, ensure_ascii=False), TEST_CAMPAIGN_ID),
        )
        conn.commit()
    finally:
        conn.close()


def _set_pending_with_committed_d20(skill_test_id: str = "st-sbt-committed") -> int:
    """Directly write a pending_skill_test WITH committed_d20 set. Returns the committed roll."""
    import random
    committed = random.randint(1, 20)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (TEST_CAMPAIGN_ID,),
        ).fetchone()
        sf = json.loads(row["session_flags"] or "{}") if row else {}
        sf["state"] = "SKILL_TEST_PENDING"
        sf["pending_skill_test"] = {
            "skill_test_id": skill_test_id,
            "skill_key": "athletics",
            "skill_label": "Atletyka (test)",
            "dc": 12,
            "counter": {"counter_type": "dc", "dc": 12},
            "modifier_breakdown": {
                "governing_stat": "STR",
                "stat_mod": 0,
                "skill_rank": 0,
                "proficiency": 0,
                "total": 0,
            },
            "committed_d20": committed,
        }
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(sf, ensure_ascii=False), TEST_CAMPAIGN_ID),
        )
        conn.commit()
    finally:
        conn.close()
    return committed


def _set_pending_without_committed_d20(skill_test_id: str = "st-sbt-no-commit") -> None:
    """Directly write a pending_skill_test WITHOUT committed_d20 — for backward compat test."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (TEST_CAMPAIGN_ID,),
        ).fetchone()
        sf = json.loads(row["session_flags"] or "{}") if row else {}
        sf["state"] = "SKILL_TEST_PENDING"
        sf["pending_skill_test"] = {
            "skill_test_id": skill_test_id,
            "skill_key": "athletics",
            "skill_label": "Atletyka (test)",
            "dc": 12,
            "counter": {"counter_type": "dc", "dc": 12},
            "modifier_breakdown": {
                "governing_stat": "STR",
                "stat_mod": 0,
                "skill_rank": 0,
                "proficiency": 0,
                "total": 0,
            },
            # NOTE: committed_d20 intentionally absent
        }
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(sf, ensure_ascii=False), TEST_CAMPAIGN_ID),
        )
        conn.commit()
    finally:
        conn.close()


class TestSkillTestAutoResolveWhenCommittedD20Set:
    """SB-5: when committed_d20 is present, regular turn must resolve — not re-surface."""

    @pytest.fixture(autouse=True)
    def reset(self):
        _clear_pending_skill_test()
        yield
        _clear_pending_skill_test()

    def test_state_cleared_to_narrative_after_turn_with_committed_d20(self):
        """
        After sending a regular turn while committed_d20 is set, state must be NARRATIVE.

        Before fix: state stays SKILL_TEST_PENDING (guard re-surfaces forever).
        After fix: guard auto-resolves, state = NARRATIVE.
        """
        committed_d20 = _set_pending_with_committed_d20("st-458-state-test")
        assert committed_d20 is not None  # sanity

        _post_turn("Działam dalej.")

        sf_after = _read_session_flags()
        state_after = sf_after.get("state", "NARRATIVE")
        assert state_after != "SKILL_TEST_PENDING", (
            f"State still SKILL_TEST_PENDING after committed_d20 auto-resolve!\n"
            f"  committed_d20 was: {committed_d20}\n"
            f"  session_flags after: {json.dumps(sf_after, indent=2, ensure_ascii=False)[:400]}"
        )

    def test_prose_non_empty_after_committed_d20_resolution(self):
        """
        Response prose must be non-empty when skill test auto-resolves.

        Before fix: re-surface returns prose=None, empty narrative.
        After fix: LLM generates resolution narrative.
        """
        _set_pending_with_committed_d20("st-458-prose-test")

        resp = _post_turn("Próbuję jak najlepiej.")

        prose = resp.get("prose") or ""
        assert prose.strip(), (
            f"Prose is empty after committed_d20 auto-resolution!\n"
            f"  route: {resp.get('route')}\n"
            f"  response keys: {list(resp.keys())}\n"
            f"  full resp: {json.dumps(resp, ensure_ascii=False)[:400]}"
        )

    def test_pending_cleared_from_session_flags(self):
        """
        pending_skill_test must be removed from session_flags after resolution.

        Before fix: pending stays (state SKILL_TEST_PENDING, pending_skill_test still present).
        After fix: pending_skill_test removed.
        """
        _set_pending_with_committed_d20("st-458-clear-test")

        _post_turn("Rzucam się w wir akcji.")

        sf_after = _read_session_flags()
        assert sf_after.get("pending_skill_test") is None, (
            f"pending_skill_test still present after auto-resolution!\n"
            f"  session_flags: {json.dumps(sf_after, indent=2, ensure_ascii=False)[:400]}"
        )


class TestSkillTestResurfaceWhenNoCommittedD20:
    """Backward compat: without committed_d20, guard must re-surface pending (SB-3/SB-4)."""

    @pytest.fixture(autouse=True)
    def reset(self):
        _debug_cmd("/debug set-state NARRATIVE")
        yield
        _debug_cmd("/debug set-state NARRATIVE")

    def test_resurface_when_no_committed_d20(self):
        """
        When pending has NO committed_d20, turn must re-surface pending (not resolve).
        This is the SB-3/SB-4 guard behavior — must remain intact.
        """
        skill_test_id = "st-sbt-no-commit-bc"
        _set_pending_without_committed_d20(skill_test_id)

        resp = _post_turn("Rozglądam się uważnie.")

        route = resp.get("route", "")
        returned_pending = resp.get("skill_test_pending") or {}
        returned_id = returned_pending.get("skill_test_id", "")

        assert route == "skill_test", (
            f"Expected route=skill_test (re-surface when no committed_d20), got: {route!r}\n"
            f"  response: {json.dumps(resp, ensure_ascii=False)[:400]}"
        )
        assert returned_id == skill_test_id, (
            f"Expected re-surfaced skill_test_id={skill_test_id!r}, got: {returned_id!r}"
        )
