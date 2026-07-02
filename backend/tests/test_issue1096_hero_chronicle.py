"""TDD: Issue #1096 — Hero Chronicle / Kronika bohatera między kampaniami."""
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE character_campaign_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            campaign_id INTEGER NOT NULL,
            outcome TEXT NOT NULL DEFAULT 'active',
            chapter_summary TEXT,
            xp_earned INTEGER NOT NULL DEFAULT 0,
            gold_at_end INTEGER NOT NULL DEFAULT 0,
            turns_count INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def _seed_history(conn, character_id=1, n=3):
    """Insert n completed campaigns with chapter summaries, each a day apart (oldest first)."""
    for i in range(1, n + 1):
        conn.execute("""
            INSERT INTO character_campaign_history
            (character_id, campaign_id, outcome, chapter_summary, turns_count, completed_at)
            VALUES (?, ?, 'victory', ?, 10, datetime('now', ? || ' days'))
        """, (character_id, 100 + i, f"Podsumowanie rozdziału {i}: bohater pokonał smoka nr {i}.", str(i - n - 1)))
    conn.commit()


# ─── Test 1: empty when no history ──────────────────────────────────────────


def test_get_hero_chronicle_empty_when_no_history():
    """get_hero_chronicle returns empty string when character has no history."""
    from app.services.chapter_summary_service import get_hero_chronicle

    conn = _make_db()
    result = get_hero_chronicle(conn, character_id=99, limit=3)
    assert result == "", f"Expected empty string, got: {result!r}"


# ─── Test 2: returns chronicle block with summaries ──────────────────────────


def test_get_hero_chronicle_returns_block_with_summaries():
    """get_hero_chronicle returns a non-empty block with chapter summaries."""
    from app.services.chapter_summary_service import get_hero_chronicle

    conn = _make_db()
    _seed_history(conn, character_id=1, n=2)

    result = get_hero_chronicle(conn, character_id=1, limit=3)
    assert result, "Expected non-empty chronicle block"
    assert "KRONIKA" in result.upper() or "Rozdział" in result or "rozdziału" in result, \
        f"Expected chronicle header or chapter in result, got: {result[:200]!r}"
    assert "smoka nr 1" in result
    assert "smoka nr 2" in result


# ─── Test 3: limit respected ────────────────────────────────────────────────


def test_get_hero_chronicle_respects_limit():
    """get_hero_chronicle returns at most `limit` chapters."""
    from app.services.chapter_summary_service import get_hero_chronicle

    conn = _make_db()
    _seed_history(conn, character_id=1, n=5)

    result = get_hero_chronicle(conn, character_id=1, limit=2)
    # only 2 newest should appear; 3 oldest dropped
    assert "smoka nr 4" in result or "smoka nr 5" in result, \
        "Expected newest chapters in result"
    count = result.count("smoka nr")
    assert count <= 2, f"Expected at most 2 chapters, got {count}"


# ─── Test 4: generate_v2_campaign_plan injects chronicle ─────────────────────


def test_generate_v2_campaign_plan_contains_chronicle(monkeypatch):
    """generate_v2_campaign_plan includes KRONIKA BOHATERA block in prompt when hero_chronicle set."""
    captured_prompt = {}

    def _fake_generate_chat(messages, model=None, llm_config=None):
        # Capture user message to verify chronicle was injected
        for m in messages:
            if m.get("role") == "user":
                captured_prompt["content"] = m["content"]
        # Return minimal valid V2 plan JSON
        return '{"title":"Test","acts":[{"act_number":1,"title":"Akt 1","key_beats":[{"beat_key":"B1","title":"Beat 1","description":"desc","location_hint":"","npc_hint":"","is_finale":false}],"ending_hint":""}],"endings":[]}'

    from app.services import campaign_plan_service
    monkeypatch.setattr(campaign_plan_service, "generate_chat", _fake_generate_chat)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            gm_plan_json TEXT,
            engine_private_json TEXT,
            plan_degraded INTEGER DEFAULT 0
        )
    """)
    conn.execute("INSERT INTO campaigns (id) VALUES (1)")
    conn.commit()

    from app.services.campaign_plan_service import generate_v2_campaign_plan

    character_data = {
        "name": "Alaric",
        "archetype": "warrior",
        "background_note": "Były rycerz",
        "identity": {},
        "gm_only": {},
    }

    hero_chronicle = "=== KRONIKA BOHATERA ===\nRozdział 1: Alaric pokonał smoka.\n"

    generate_v2_campaign_plan(
        conn,
        campaign_id=1,
        character_data=character_data,
        model="stub",
        llm_config={},
        max_attempts=1,
        hero_chronicle=hero_chronicle,
    )

    assert "captured_prompt" in captured_prompt or "content" in captured_prompt, \
        "LLM was never called"
    content = captured_prompt.get("content", "")
    assert "KRONIKA" in content.upper(), \
        f"Chronicle block not found in user prompt. Got: {content[:400]!r}"


# ─── Test 5: generate_initial_gm_plan_v2 injects chronicle ───────────────────


def test_generate_initial_gm_plan_v2_contains_chronicle(monkeypatch):
    """generate_initial_gm_plan_v2_with_retries injects hero_chronicle into user_content."""
    captured = {}

    def _fake_generate_chat(messages, model=None, llm_config=None):
        for m in messages:
            if m.get("role") == "user":
                captured["content"] = m["content"]
        return '{"title":"T","acts":[{"act_number":1,"title":"A1","key_beats":[{"beat_key":"B1","title":"B1","description":"d","location_hint":"","npc_hint":"","is_finale":false}],"ending_hint":""}],"endings":[]}'

    from app.services import gm_plan_generation_service
    monkeypatch.setattr(gm_plan_generation_service, "generate_chat", _fake_generate_chat)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            gm_plan_json TEXT,
            engine_private_json TEXT,
            plan_degraded INTEGER DEFAULT 0
        )
    """)
    conn.execute("INSERT INTO campaigns (id) VALUES (1)")
    conn.commit()

    from app.services.gm_plan_generation_service import generate_initial_gm_plan_v2_with_retries

    hero_chronicle = "=== KRONIKA BOHATERA ===\nRozdział 1: Pokonał goblinów.\n"

    generate_initial_gm_plan_v2_with_retries(
        conn,
        campaign_id=1,
        campaign_title="Nowa Kampania",
        campaign_language="pl",
        system_id="fantasy",
        char_summary="Postać: Kira, Wojownik, HP: 20",
        user_id=1,
        model="stub",
        llm_config={},
        max_attempts=1,
        hero_chronicle=hero_chronicle,
    )

    content = captured.get("content", "")
    assert "KRONIKA" in content.upper(), \
        f"Chronicle block not found in user_content. Got: {content[:400]!r}"


# ─── Test 6: ContextInjector._build_hero_chronicle_block ─────────────────────


def test_context_injector_hero_chronicle_block_with_history():
    """_build_hero_chronicle_block returns block when character has campaign history."""
    conn = _make_db()
    _seed_history(conn, character_id=7, n=2)

    from app.services.context_injector import ContextInjector
    injector = ContextInjector(conn)
    result = injector._build_hero_chronicle_block(7)
    assert result, "Expected non-empty block when history exists"
    assert "smoka nr" in result


def test_context_injector_hero_chronicle_block_empty_for_new_character():
    """_build_hero_chronicle_block returns empty string for character with no history."""
    conn = _make_db()

    from app.services.context_injector import ContextInjector
    injector = ContextInjector(conn)
    result = injector._build_hero_chronicle_block(999)
    assert result == "", f"Expected empty string for new character, got: {result!r}"


# ─── Test 7: no regression — hero without history starts clean ───────────────


def test_get_hero_chronicle_no_regression_first_campaign():
    """First-campaign hero has no chronicle → no block injected → no error."""
    from app.services.chapter_summary_service import get_hero_chronicle

    conn = _make_db()
    # character_id 42 has no rows
    result = get_hero_chronicle(conn, character_id=42, limit=3)
    assert result == ""
    assert "KRONIKA" not in result.upper()
