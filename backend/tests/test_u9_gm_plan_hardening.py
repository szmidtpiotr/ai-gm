"""TDD U9 — GM Plan hardening: retry with error context + fallback plan."""
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_db():
    """In-memory SQLite with minimal campaigns table (including plan_degraded)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'Test',
            system_id TEXT NOT NULL DEFAULT 'default',
            model_id TEXT,
            language TEXT NOT NULL DEFAULT 'pl',
            owner_user_id INTEGER NOT NULL DEFAULT 1,
            gm_plan_json TEXT NOT NULL DEFAULT '{}',
            plan_degraded INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("INSERT INTO campaigns (id, title) VALUES (1, 'Kampania testowa')")
    conn.commit()
    return conn


def _dummy_llm_config():
    return {"provider": "openai", "api_key": "test", "base_url": "http://localhost:9999"}


VALID_PLAN_JSON = json.dumps({
    "roadmap": "Bohater musi odnaleźć zaginiony artefakt.",
    "scene_goals": ["Dotarcie do wioski", "Rozmowa z karczmarką"],
    "hooks": {"npcs": ["Karczmarkowa Anna"], "locations": ["Karczma Pod Wieżą"]},
    "title": "Zaginiony artefakt",
})

GARBAGE = "To nie jest JSON!!! <broken>"


# ─── Test 1: retry dołącza błąd do promptu ───────────────────────────────────

def test_retry_includes_error_in_prompt(monkeypatch):
    """Przy retry (attempt=2) messages zawierają poprzednią złą odpowiedź + komunikat błędu."""
    from app.services import gm_plan_generation_service as svc

    calls = []

    def mock_generate_chat(messages, model, llm_config, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return GARBAGE
        return VALID_PLAN_JSON

    monkeypatch.setattr(svc, "generate_chat", mock_generate_chat)

    conn = _make_db()
    ok, err = svc.generate_initial_gm_plan_with_retries(
        conn,
        campaign_id=1,
        campaign_title="Test",
        campaign_language="pl",
        system_id="default",
        char_summary="Wojownik z przeszłością",
        user_id=1,
        model="gpt-4o",
        llm_config=_dummy_llm_config(),
        max_attempts=2,
    )

    assert ok is True, f"Powinno się udać na 2. próbie, błąd: {err}"
    assert len(calls) == 2, f"Oczekiwano 2 calls LLM, dostano {len(calls)}"

    second_call_messages = calls[1]
    roles = [m["role"] for m in second_call_messages]
    contents = [m["content"] for m in second_call_messages]

    # Drugi call musi mieć assistant message z garbage + user message z informacją o błędzie
    assert "assistant" in roles, "Brak roli 'assistant' w 2. call — retry nie dołączył złej odpowiedzi"
    assistant_idx = roles.index("assistant")
    assert GARBAGE in contents[assistant_idx], "assistant message nie zawiera poprzedniej złej odpowiedzi"

    # User message po assisstant musi wspominać o JSON i błędzie
    user_retry_messages = [
        m["content"] for m in second_call_messages[assistant_idx:]
        if m["role"] == "user"
    ]
    assert user_retry_messages, "Brak user message po assistant w retry"
    retry_user_text = user_retry_messages[0]
    assert "JSON" in retry_user_text, f"User retry message nie mówi o JSON: {retry_user_text}"
    conn.close()


# ─── Test 2: fallback plan po wyczerpaniu wszystkich prób ────────────────────

def test_fallback_plan_on_all_failures(monkeypatch):
    """Gdy LLM zawsze zwraca garbage, powstaje fallback plan i plan_degraded=1."""
    from app.services import gm_plan_generation_service as svc

    monkeypatch.setattr(svc, "generate_chat", lambda **kwargs: GARBAGE)

    conn = _make_db()
    ok, err = svc.generate_initial_gm_plan_with_retries(
        conn,
        campaign_id=1,
        campaign_title="Test",
        campaign_language="pl",
        system_id="default",
        char_summary="Złodziej z przeszłością",
        user_id=1,
        model="gpt-4o",
        llm_config=_dummy_llm_config(),
        max_attempts=2,
    )

    assert ok is True, "Kampania powinna startować nawet gdy LLM zawodzi (fallback)"
    assert err is None, f"err powinien być None po fallbacku, dostano: {err}"

    row = conn.execute("SELECT gm_plan_json, plan_degraded FROM campaigns WHERE id=1").fetchone()
    assert row is not None

    plan = json.loads(row["gm_plan_json"])
    # Plan musi mieć podstawową strukturę (roadmap lub cele)
    from app.services.gm_plan_schema import gm_plan_is_ready
    assert gm_plan_is_ready(row["gm_plan_json"]), "Fallback plan musi przejść gm_plan_is_ready()"

    assert int(row["plan_degraded"]) == 1, f"plan_degraded powinno być 1, dostano: {row['plan_degraded']}"
    conn.close()


# ─── Test 3: regeneracja czyści flagę degradacji ─────────────────────────────

def test_degraded_cleared_on_regenerate(monkeypatch):
    """retry_initial_gm_plan_for_campaign po sukcesie ustawia plan_degraded=0."""
    from app.services import gm_plan_generation_service as svc

    monkeypatch.setattr(svc, "generate_chat", lambda **kwargs: VALID_PLAN_JSON)

    # Patch get_user_llm_settings_full żeby nie otwierało prawdziwego DB
    import app.services.user_llm_settings as uls
    monkeypatch.setattr(
        uls, "get_user_llm_settings_full",
        lambda user_id: {
            "model": "gpt-4o",
            "llm_config": _dummy_llm_config(),
        }
    )

    conn = _make_db()
    conn.execute("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            user_id INTEGER DEFAULT 1,
            name TEXT DEFAULT 'Bohater',
            system_id TEXT DEFAULT 'default',
            sheet_json TEXT DEFAULT '{}',
            location TEXT DEFAULT 'Miasto'
        )
    """)
    conn.execute("INSERT INTO characters (id, campaign_id, user_id) VALUES (1, 1, 1)")
    # Kampania startuje z plan_degraded=1 (symulacja poprzedniej degradacji)
    conn.execute("UPDATE campaigns SET plan_degraded=1 WHERE id=1")
    conn.commit()

    before = conn.execute("SELECT plan_degraded FROM campaigns WHERE id=1").fetchone()
    assert int(before["plan_degraded"]) == 1, "setup: plan_degraded musi być 1 przed testem"

    ok, err = svc.retry_initial_gm_plan_for_campaign(
        conn,
        campaign_id=1,
        owner_user_id=1,
    )

    assert ok is True, f"Regeneracja powinna się udać przy działającym LLM: {err}"

    after = conn.execute("SELECT plan_degraded FROM campaigns WHERE id=1").fetchone()
    assert int(after["plan_degraded"]) == 0, \
        f"plan_degraded powinno być 0 po udanej regeneracji, dostano: {after['plan_degraded']}"
    conn.close()


# ─── Test 4: normalna kampania nie ma degraded ────────────────────────────────

def test_successful_plan_no_degraded(monkeypatch):
    """Gdy LLM działa poprawnie, plan_degraded pozostaje 0."""
    from app.services import gm_plan_generation_service as svc

    monkeypatch.setattr(svc, "generate_chat", lambda **kwargs: VALID_PLAN_JSON)

    conn = _make_db()
    ok, err = svc.generate_initial_gm_plan_with_retries(
        conn,
        campaign_id=1,
        campaign_title="Test",
        campaign_language="pl",
        system_id="default",
        char_summary="Uczony szukający wiedzy",
        user_id=1,
        model="gpt-4o",
        llm_config=_dummy_llm_config(),
        max_attempts=3,
    )

    assert ok is True
    row = conn.execute("SELECT plan_degraded FROM campaigns WHERE id=1").fetchone()
    assert int(row["plan_degraded"]) == 0, "Udana generacja nie może ustawiać plan_degraded=1"
    conn.close()
