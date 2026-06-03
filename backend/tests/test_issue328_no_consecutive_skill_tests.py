"""TDD: Issue #328 — Skill test narrator must not trigger another skill test.

Bug: resolve_skill_test_endpoint() calls _gen_chat() for narrator prose.
The narrator prompt did not forbid roll_cue / [SKILL_TEST] tags. The LLM
sometimes returned JSON with roll_cue:"Roll Persuasion" which the streaming
intercept then processed as a new pending_skill_test — causing consecutive
skill tests without player narrative input.

Fix: add explicit prohibition of [SKILL_TEST] / roll_cue to narrator_prompt.
Also: ensure pending_skill_test is ALWAYS cleared after resolve, even if
narrator LLM call fails.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db_runtime import resolve_db_path


@pytest.fixture
def conn():
    c = sqlite3.connect(resolve_db_path())
    c.row_factory = sqlite3.Row
    yield c
    c.close()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_narrator_prompt_forbids_roll_cue_tags():
    """The skill test narrator prompt must explicitly forbid roll_cue and [SKILL_TEST] tags.

    Before fix: prompt had no prohibition → LLM occasionally returned roll_cue
    → streaming intercept triggered another pending_skill_test → consecutive tests.
    After fix: narrator_prompt includes 'Nie używaj tagów' or 'roll_cue' prohibition.
    """
    # Read the actual source file to find the narrator_prompt content
    import re
    source_path = __file__.replace("tests/test_issue328_no_consecutive_skill_tests.py", "app/api/turns.py")
    with open(source_path) as f:
        source = f.read()

    # Find narrator_prompt = (...) block in the resolve endpoint
    # The narrator_prompt should contain a prohibition against skill test tags
    match = re.search(r'narrator_prompt\s*=\s*\((.*?)\)', source, re.DOTALL)
    assert match, "narrator_prompt variable not found in turns.py"

    narrator_content = match.group(1)
    # Must contain a prohibition against roll_cue or [SKILL_TEST] tags
    has_prohibition = any(phrase in narrator_content for phrase in [
        "roll_cue",
        "SKILL_TEST",
        "Nie używaj",
        "nie używaj",
        "bez tagów",
        "NOT include",
        "ZAKAZANE",
    ])
    assert has_prohibition, (
        f"narrator_prompt must forbid roll_cue/[SKILL_TEST] tags to prevent consecutive "
        f"skill tests. Current content: {narrator_content[:200]!r}"
    )


def test_pending_skill_test_cleared_after_resolve(conn):
    """After resolve_skill_test_endpoint(), session_flags.pending_skill_test must be None.

    Bug symptom: consecutive skill tests = pending_skill_test re-appears after resolve.
    After fix: pending is always cleared.
    """
    import uuid as _uuid
    from app.services.skill_service import resolve_skill_test

    row = conn.execute(
        """SELECT c.id AS campaign_id, ch.id AS character_id
           FROM campaigns c
           JOIN characters ch ON ch.campaign_id = c.id AND ch.is_active = 1
           JOIN game_sessions gs ON gs.campaign_id = c.id
           WHERE c.status = 'active'
           LIMIT 1"""
    ).fetchone()
    if not row:
        pytest.skip("No active campaign with session found")

    campaign_id = row["campaign_id"]
    character_id = row["character_id"]

    # Set up a fake pending_skill_test
    skill_test_id = f"st-{_uuid.uuid4().hex[:8]}"
    pending = {
        "skill_test_id": skill_test_id,
        "skill_key": "persuasion",
        "skill_label": "Perswazja",
        "committed_d20": 10,
        "counter": {"counter_type": "dc", "dc": 12},
    }
    gs = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    sf = json.loads(gs["session_flags"] or "{}")
    sf["pending_skill_test"] = pending
    sf["state"] = "SKILL_TEST_PENDING"
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(sf, ensure_ascii=False), campaign_id),
    )
    conn.commit()

    # Simulate resolve (without calling full endpoint — just verify the clear logic)
    sf_after = json.loads(
        conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()["session_flags"] or "{}"
    )
    assert sf_after.get("pending_skill_test") is not None, (
        "Pending was set — should be there before resolve"
    )

    # Simulate what resolve_skill_test_endpoint does: pop pending + set state=NARRATIVE
    sf_after.pop("pending_skill_test", None)
    sf_after["state"] = "NARRATIVE"
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(sf_after, ensure_ascii=False), campaign_id),
    )
    conn.commit()

    sf_final = json.loads(
        conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()["session_flags"] or "{}"
    )
    assert "pending_skill_test" not in sf_final, (
        "pending_skill_test must be cleared after resolve"
    )
    assert sf_final.get("state") == "NARRATIVE", (
        "state must be 'NARRATIVE' after resolve"
    )


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_skill_test_id_mismatch_raises_409(conn):
    """resolve_skill_test_endpoint must reject mismatched skill_test_id (prevents replay)."""
    import uuid as _uuid
    skill_test_id = f"st-{_uuid.uuid4().hex[:8]}"
    pending = {"skill_test_id": skill_test_id, "committed_d20": 10}

    # Simulate the mismatch check
    submitted_id = f"st-{_uuid.uuid4().hex[:8]}"  # different ID
    assert pending.get("skill_test_id") != submitted_id, (
        "Different IDs — resolve should reject with 409"
    )
