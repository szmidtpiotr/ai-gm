"""U7 (#531): SKILL_CHECK safety net + DC lock tests.

Tests that:
- clamp_dc_to_scale() rounds to nearest {8, 12, 16, 20, 24}
- SKILL_CHECK tag with non-standard DC gets clamped + logged to llm_tag_errors
- SKILL_CHECK tag with standard DC is unchanged, no log
- [SKILL_CHECK: auto_success] bypasses the test
- _detect_risky_intent() matches risky player actions from game_config_skill_risk_categories
- _detect_risky_intent() returns None for benign text
- safety net: risky intent + LLM omits tag → pending_skill_test forced, skill_check_forced logged
- safety net: risky intent + LLM included [SKILL_CHECK] → no forced test
"""
import json
import sqlite3
import sys
import os

import pytest

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql


@pytest.fixture
def mem_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE llm_tag_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            turn_number INTEGER NOT NULL,
            tag_raw TEXT NOT NULL,
            error_type TEXT NOT NULL,
            ts TEXT NOT NULL
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            session_flags TEXT DEFAULT '{}'
        );
        """ + table_sql("game_config_skill_risk_categories") + """
        INSERT INTO game_config_skill_risk_categories
            (category_key, skill_key, default_dc, keywords, enabled) VALUES
            ('stealth', 'stealth', 12, 'skrad,przekrad,niepostrzeżenie,kryję,chowam,ukrywam,przemykam,cichaczem', 1),
            ('climb_jump', 'athletics', 12, 'wspinam,wspinaczka,skaczę,skok,przeskakuję,gramolę', 1),
            ('theft', 'lockpick', 12, 'kradnę,ukraść,podkradam,kieszeni,zabieram,kraść', 1),
            ('persuasion_pressure', 'persuasion', 12, 'kłamię,blefuję,przekonuję,zastraszam,szantażuję', 1),
            ('disarm', 'lockpick', 16, 'rozbrajam,unieszkodliwiam,wyważam zamek', 1),
            ('acrobatics', 'athletics', 12, 'akrobatyka,unik,uchylam,przewrót,balansując', 1);
        INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, '{}');
    """)
    return conn


# ─── (a) clamp_dc_to_scale ────────────────────────────────────────────────────

def test_clamp_dc_scale_roundtrip():
    from app.services.llm_tag_parser import clamp_dc_to_scale

    assert clamp_dc_to_scale(17) == (16, True)   # between 16 and 20 → 16 is closer
    assert clamp_dc_to_scale(8) == (8, False)     # exact — no clamp
    assert clamp_dc_to_scale(25) == (24, True)    # above max → 24
    assert clamp_dc_to_scale(12) == (12, False)   # exact
    assert clamp_dc_to_scale(1) == (8, True)      # below min → 8
    assert clamp_dc_to_scale(100) == (24, True)   # way above → 24
    assert clamp_dc_to_scale(10) == (8, True)     # 10 is between 8 and 12; 10-8=2, 12-10=2 → lower wins
    assert clamp_dc_to_scale(16) == (16, False)   # exact
    assert clamp_dc_to_scale(20) == (20, False)   # exact
    assert clamp_dc_to_scale(24) == (24, False)   # exact


# NOTE (G8 #1472): the dead SKILL_CHECK parser tests (b/c/d) were removed with
# parse_skill_check_tag — the narrator only emits [SKILL_TEST:], never [SKILL_CHECK:].
# DC clamping now lives at the [SKILL_TEST] intercept (skill_service) and is covered
# by test_skill_service_skill_test.py::test_skill_test_dc_clamped.


# ─── (e) _detect_risky_intent: stealth match ────────────────────────────────

def test_detect_risky_intent_stealth(mem_db):
    from app.services.game_engine import _detect_risky_intent

    result = _detect_risky_intent(mem_db, "skradam się obok strażnika")

    assert result is not None, "Expected stealth category match"
    assert result["category_key"] == "stealth"
    assert result["skill_key"] == "stealth"
    assert result["default_dc"] == 12


# ─── (f) _detect_risky_intent: benign text → None ───────────────────────────

def test_detect_risky_intent_benign(mem_db):
    from app.services.game_engine import _detect_risky_intent

    result = _detect_risky_intent(mem_db, "mówię dzień dobry karczmarce")

    assert result is None, f"Expected None for benign text, got {result}"


# ─── (g) safety net: risky intent + no tag → forced test ────────────────────

def test_safety_net_forces_skill_test_when_tag_missing(mem_db):
    from app.services.game_engine import _detect_risky_intent
    from app.services.llm_tag_parser import skill_check_safety_net

    risky_match = _detect_risky_intent(mem_db, "skradam się obok strażnika")
    assert risky_match is not None

    # LLM response without [SKILL_CHECK] tag
    llm_response = "Powoli suniesz wzdłuż muru, starając się nie hałasować."

    result = skill_check_safety_net(
        llm_response=llm_response,
        risky_intent=risky_match,
        existing_pending=None,
        conn=mem_db,
        campaign_id=1,
    )

    assert result is not None, "Expected forced skill test pending"
    assert result["skill_key"] == "stealth"
    assert result["dc"] == 12

    # Log entry for skill_check_forced
    row = mem_db.execute(
        "SELECT * FROM llm_tag_errors WHERE campaign_id=1 AND error_type='skill_check_forced'"
    ).fetchone()
    assert row is not None, "Expected skill_check_forced log entry"


# ─── (h) safety net: risky intent + LLM included tag → no forced test ───────

def test_safety_net_no_force_when_tag_present(mem_db):
    from app.services.game_engine import _detect_risky_intent
    from app.services.llm_tag_parser import skill_check_safety_net

    risky_match = _detect_risky_intent(mem_db, "skradam się obok strażnika")
    assert risky_match is not None

    # LLM response WITH the real [SKILL_TEST] tag
    llm_response = "Próbujesz się przemknąć [SKILL_TEST:stealth:DC:12] obok strażnika."

    result = skill_check_safety_net(
        llm_response=llm_response,
        risky_intent=risky_match,
        existing_pending=None,
        conn=mem_db,
        campaign_id=1,
    )

    assert result is None, "No forced test expected when LLM already included SKILL_TEST"


# ─── Backward compat: SKILL_TEST registry matches the real emitted format ────

def test_existing_skill_test_tag_unaffected():
    """TAG_REGISTRY['SKILL_TEST'] must match the real [SKILL_TEST:key:DC:n] format."""
    from app.services.llm_tag_parser import TAG_REGISTRY

    pattern = TAG_REGISTRY["SKILL_TEST"]
    m = pattern.search("[SKILL_TEST:stealth:DC:12]")
    assert m is not None, "SKILL_TEST pattern must match the real 3-part format"
    assert m.group(1).strip() == "stealth"
    assert m.group(2).strip().upper() == "DC"
    assert m.group(3).strip() == "12"
    # OPPOSED variant also matches
    assert pattern.search("[SKILL_TEST:haggling:OPPOSED:CHA]") is not None
