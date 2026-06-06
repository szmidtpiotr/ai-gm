"""TDD: Issue #240 — Skill test narrator must receive in-game clock context.

Bug: resolve_skill_test_endpoint() calls _gen_chat() with narrator_prompt that
has NO clock context. The LLM defaults to atmospheric 'darkness/night' regardless
of actual in-game time (e.g. morning). Fix #233 added _inject_clock_context() to
build_narrative_messages() but this doesn't apply to the skill test narrator path.

Fix: inject [CZAS GRY] HH:MM — period into narrator_prompt in resolve_skill_test_endpoint.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_skill_test_narrator_prompt_includes_clock_context():
    """narrator_prompt in resolve_skill_test_endpoint must include [CZAS GRY] clock block.

    Before fix: prompt had no clock context → LLM defaulted to night/darkness.
    After fix: prompt includes in-game time so narrator matches actual time of day.
    """
    source_path = Path(__file__).resolve().parent.parent / "app" / "api" / "turns.py"
    source = source_path.read_text(encoding="utf-8")

    # Find narrator_prompt = (...) block in the resolve endpoint
    match = re.search(r'narrator_prompt\s*=\s*\((.*?)\)', source, re.DOTALL)
    assert match, "narrator_prompt variable not found in turns.py"

    narrator_content = match.group(1)
    # Must contain clock context marker
    has_clock = any(phrase in narrator_content for phrase in [
        "CZAS GRY",
        "clock_hint",
        "ingame_hours",
        "get_clock_state",
        "pora dnia",
        "godzina",
    ])
    assert has_clock, (
        f"narrator_prompt in resolve_skill_test_endpoint must include in-game clock context "
        f"(CZAS GRY / clock_hint / pora dnia) to prevent night/darkness narration at morning. "
        f"Current content: {narrator_content[:300]!r}"
    )


def test_clock_service_returns_time_of_day(conn=None):
    """get_clock_state returns ingame_hours for clock injection."""
    import sqlite3
    from app.core.db_runtime import resolve_db_path
    from app.services.clock_service import get_clock_state

    c = sqlite3.connect(resolve_db_path())
    c.row_factory = sqlite3.Row
    try:
        row = c.execute(
            "SELECT id FROM campaigns WHERE status = 'active' LIMIT 1"
        ).fetchone()
        if not row:
            pytest.skip("No active campaign")
        campaign_id = row["id"]
        clock = get_clock_state(campaign_id, conn=c)
        assert "ingame_hours" in clock or "day" in clock, (
            f"get_clock_state must return time info, got: {list(clock.keys())}"
        )
    finally:
        c.close()


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_regular_narrative_still_has_clock_injection():
    """build_narrative_messages must still call _inject_clock_context (fix #233 intact)."""
    import inspect
    from app.services import game_engine
    source = inspect.getsource(game_engine)
    assert "_inject_clock_context" in source, (
        "_inject_clock_context must still be called in build_narrative_messages (#233 regression)"
    )
