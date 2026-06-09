"""TDD: Issue #457 (SB-3/SB-4) — Keyword scan must not overwrite SKILL_TEST_PENDING state.

Bug: when session_flags.state == SKILL_TEST_PENDING, sending a free-text turn
whose text matches trigger_keywords fires the pre-LLM keyword scanner and overwrites
the existing pending_skill_test with a new one. The player never resolves the original
test and is stuck in an infinite loop.

Fix: skip the keyword scan entirely when state is already SKILL_TEST_PENDING.
"""

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# ── Constants ──────────────────────────────────────────────────────────────
# Stable test-env fixtures: demo user (user_id=1, admin) campaign + hero.
TEST_CAMPAIGN_ID = 999444
TEST_CHARACTER_ID = 999377
DEMO_USER_ID = 1


# ── Helpers ────────────────────────────────────────────────────────────────

_cached_token: str | None = None


def _token() -> str:
    global _cached_token
    if not _cached_token:
        r = client.post("/api/auth/login", json={"username": "demo", "password": "demo"})
        assert r.status_code == 200, f"Login failed: {r.text}"
        _cached_token = r.json()["access_token"]
    return _cached_token


def debug_set_state(state: str) -> dict:
    """Set session state via POST /api/debug/command."""
    r = client.post(
        "/api/debug/command",
        json={
            "character_id": TEST_CHARACTER_ID,
            "user_id": DEMO_USER_ID,
            "text": f"/debug set-state {state}",
        },
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert r.status_code == 200, f"debug set-state failed: {r.status_code} {r.text[:300]}"
    return r.json()


def read_session_flags() -> dict:
    """Read session_flags directly from DB."""
    import sqlite3
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (TEST_CAMPAIGN_ID,),
    ).fetchone()
    conn.close()
    if not row:
        return {}
    try:
        return json.loads(row["session_flags"] or "{}")
    except Exception:
        return {}


def post_turn(text: str) -> dict:
    r = client.post(
        f"/api/campaigns/{TEST_CAMPAIGN_ID}/turns",
        json={"character_id": TEST_CHARACTER_ID, "text": text},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    return r.json()


# ── Tests ─────────────────────────────────────────────────────────────────


class TestSkillTestPendingKeywordGuard:
    """SB-4: keyword scan must not fire when state is already SKILL_TEST_PENDING."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset to NARRATIVE before + after each test."""
        debug_set_state("NARRATIVE")
        yield
        debug_set_state("NARRATIVE")

    def _enter_pending(self) -> str:
        """Set SKILL_TEST_PENDING and return the auto-seeded skill_test_id."""
        debug_set_state("SKILL_TEST_PENDING")
        sf = read_session_flags()
        pending = sf.get("pending_skill_test") or {}
        skill_test_id = pending.get("skill_test_id", "")
        assert skill_test_id, (
            f"No skill_test_id after set-state SKILL_TEST_PENDING\n"
            f"session_flags: {json.dumps(sf, indent=2)[:600]}"
        )
        return skill_test_id

    def test_pending_test_id_preserved_on_keyword_text(self):
        """
        RED: 'Rozglądam się' (awareness trigger) while SKILL_TEST_PENDING
        must NOT overwrite the existing pending_skill_test.

        Before fix: keyword scan fires → new UUID in response → FAILS.
        After fix : keyword scan skipped → original_id preserved → PASSES.
        """
        original_id = self._enter_pending()

        resp = post_turn("Rozglądam się uważnie.")

        returned_pending = resp.get("skill_test_pending") or {}
        returned_id = returned_pending.get("skill_test_id", "")

        assert returned_id == original_id, (
            f"SKILL_TEST_PENDING overwritten!\n"
            f"  original_id : {original_id}\n"
            f"  returned_id : {returned_id!r} (empty = no pending in resp)\n"
            f"  route       : {resp.get('route')}\n"
            f"  response    : {json.dumps(resp, indent=2, ensure_ascii=False)[:600]}"
        )

    def test_route_not_skill_test_keyword_when_already_pending(self):
        """
        RED: route must NOT be 'skill_test_keyword' — that means scan fired.

        Before fix: route == 'skill_test_keyword' → FAILS.
        After fix : route != 'skill_test_keyword' → PASSES.
        """
        self._enter_pending()

        resp = post_turn("Rozglądam się uważnie.")

        route = resp.get("route", "")
        assert route != "skill_test_keyword", (
            f"Keyword scan fired when already SKILL_TEST_PENDING!\n"
            f"  route   : {route}\n"
            f"  response: {json.dumps(resp, indent=2, ensure_ascii=False)[:500]}"
        )
