"""TDD: Issue #968 — history-aware GM plan regeneration.

When a campaign already has played turns, regeneration must CONTINUE the story
(feed a 'story so far' block + continuation instruction into the LLM prompt)
instead of restarting from the opening scene. Zero-turn campaigns keep the old
start-of-campaign behaviour.
"""
import json
import sqlite3

import pytest

from app.services import gm_plan_generation_service as gps

_VALID_PLAN = json.dumps(
    {
        "roadmap": "Kontynuacja: bohater rusza za zbiegłym kultystą.",
        "scene_goals": ["Dogoń kultystę", "Przesłuchaj świadka"],
        "hooks": {"npcs": ["Kultysta"], "locations": ["Port"]},
        "title": "Pościg",
    },
    ensure_ascii=False,
)


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            title TEXT, system_id TEXT, model_id TEXT, language TEXT,
            owner_user_id INTEGER,
            gm_plan_json TEXT NOT NULL DEFAULT '{}',
            plan_degraded INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, name TEXT,
            system_id TEXT, sheet_json TEXT, location TEXT
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL, character_id INTEGER,
            user_text TEXT NOT NULL, route TEXT NOT NULL DEFAULT 'narrative',
            assistant_text TEXT, turn_number INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE campaign_ai_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL, summary_text TEXT NOT NULL,
            model_used TEXT, included_turn_count INTEGER,
            audience TEXT NOT NULL DEFAULT 'player',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    return conn


# ─── Test główny — story_so_far trafia do promptu + instrukcja kontynuacji ───

def test_generation_includes_story_and_continuation_when_provided(monkeypatch):
    conn = _mem_conn()
    conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (1, '{}')")

    captured = {}

    def _fake_chat(messages, model=None, llm_config=None):
        captured["messages"] = messages
        return _VALID_PLAN

    monkeypatch.setattr(gps, "generate_chat", _fake_chat)

    ok, err = gps.generate_initial_gm_plan_with_retries(
        conn,
        campaign_id=1,
        campaign_title="Test",
        campaign_language="pl",
        system_id="sys",
        char_summary="Postać: Aldo, Wojownik.",
        user_id=1,
        model="m",
        llm_config={},
        story_so_far="Bohater pokonał smoka w wieży i uwolnił więźniów.",
    )
    assert ok
    blob = json.dumps(captured["messages"], ensure_ascii=False).lower()
    assert "smoka w wieży" in blob, "historia rozgrywki musi trafić do promptu"
    assert "kontynu" in blob, "prompt musi instruować KONTYNUACJĘ fabuły"


# ─── Backward compat — brak historii = tryb startowy (bez markera kontynuacji) ─

def test_generation_start_mode_when_no_story(monkeypatch):
    conn = _mem_conn()
    conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (1, '{}')")

    captured = {}

    def _fake_chat(messages, model=None, llm_config=None):
        captured["messages"] = messages
        return _VALID_PLAN

    monkeypatch.setattr(gps, "generate_chat", _fake_chat)

    ok, _ = gps.generate_initial_gm_plan_with_retries(
        conn,
        campaign_id=1,
        campaign_title="Test",
        campaign_language="pl",
        system_id="sys",
        char_summary="Postać: Aldo, Wojownik.",
        user_id=1,
        model="m",
        llm_config={},
    )
    assert ok
    blob = json.dumps(captured["messages"], ensure_ascii=False).lower()
    # Stary tryb startowy — pierwsza scena startowa, bez bloku historii.
    assert "startowej" in blob
    assert "dotychczasowa rozgrywka" not in blob


# ─── retry_* buduje story_so_far z tur kampanii i przekazuje do generacji ─────

def test_retry_feeds_recent_turns_into_prompt(monkeypatch):
    conn = _mem_conn()
    conn.execute(
        "INSERT INTO campaigns (id, title, system_id, model_id, language, owner_user_id, gm_plan_json) "
        "VALUES (1, 'Camp', 'sys', 'gpt-test', 'pl', 7, '{}')"
    )
    conn.execute(
        "INSERT INTO characters (id, campaign_id, name, system_id, sheet_json, location) "
        "VALUES (10, 1, 'Aldo', 'sys', ?, 'Port')",
        (json.dumps({"archetype": "warrior", "max_hp": 30, "stats": {"STR": 14}}),),
    )
    conn.executemany(
        "INSERT INTO campaign_turns (campaign_id, character_id, user_text, assistant_text, turn_number) "
        "VALUES (1, 10, ?, ?, ?)",
        [
            ("Wchodzę do nawiedzonej kopalni.", "Mrok pochłania korytarz.", 1),
            ("Atakuję wodza goblinów.", "Cios trafia w cel, wódz pada.", 2),
        ],
    )
    conn.commit()

    captured = {}

    def _fake_chat(messages, model=None, llm_config=None):
        captured["messages"] = messages
        return _VALID_PLAN

    monkeypatch.setattr(gps, "generate_chat", _fake_chat)
    monkeypatch.setattr(
        "app.services.user_llm_settings.get_user_llm_settings_full",
        lambda uid: {"model": "gpt-test"},
    )

    ok, err = gps.retry_initial_gm_plan_for_campaign(conn, campaign_id=1, owner_user_id=7)
    assert ok, err
    blob = json.dumps(captured["messages"], ensure_ascii=False).lower()
    assert "wodza goblinów" in blob or "nawiedzonej kopalni" in blob, \
        "rozegrane tury muszą trafić do promptu regeneracji"
    assert "kontynu" in blob
