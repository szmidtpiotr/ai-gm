"""T08 — per-campaign cooldown between LLM history rollup calls ([S11b])."""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.api import turns as turns_mod
from app.api import campaign_history as ch_mod
from app.main import app
from app.services import history_summary_service as hs_mod
from app.services import summary_ensure_service as ses_mod
from app.services.history_summary_service import (
    evaluate_summary_rollup_cooldown,
    get_summary_rollup_cooldown_turns,
    META_KEY_SUMMARY_ROLLUP_COOLDOWN,
)


def _schema() -> str:
    return """
    """ + table_sql("game_config_meta") + """
    INSERT INTO game_config_meta (key, value) VALUES ('summary_rollup_cooldown_turns', '3');
    CREATE TABLE campaigns (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        system_id TEXT NOT NULL,
        model_id TEXT NOT NULL,
        owner_user_id INTEGER NOT NULL,
        language TEXT DEFAULT 'pl',
        mode TEXT DEFAULT 'solo',
        status TEXT DEFAULT 'active',
        created_at TEXT,
        gm_plan_json TEXT NOT NULL DEFAULT '{}',
        last_rollup_narrative_turn_count INTEGER
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id)
    VALUES (1, 't', 'fantasy', 'm', 10);
    CREATE TABLE campaign_turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        character_id INTEGER NOT NULL DEFAULT 1,
        user_text TEXT NOT NULL,
        route TEXT NOT NULL,
        assistant_text TEXT,
        turn_number INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE campaign_ai_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        summary_text TEXT NOT NULL,
        model_used TEXT,
        included_turn_count INTEGER,
        audience TEXT NOT NULL DEFAULT 'player',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """


def _init_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_schema())
        conn.commit()
    finally:
        conn.close()


def _add_narrative_turns(path: Path, n: int, start_turn: int = 1) -> None:
    conn = sqlite3.connect(str(path))
    try:
        for i in range(n):
            conn.execute(
                """
                INSERT INTO campaign_turns (
                    campaign_id, character_id, user_text, route, assistant_text, turn_number
                )
                VALUES (1, 1, 'u', 'narrative', 'a', ?)
                """,
                (start_turn + i,),
            )
        conn.commit()
    finally:
        conn.close()


def _fake_summary():
    return {
        "summary": "Podsumowanie testowe.",
        "model_used": "mock",
        "included_turn_count": 3,
        "audience": "player",
    }


@pytest.fixture
def client_and_db(tmp_path, monkeypatch):
    db = tmp_path / "t08.db"
    _init_db(db)
    monkeypatch.setattr(turns_mod, "DB_PATH", str(db))
    monkeypatch.setattr(hs_mod, "DB_PATH", str(db))
    return TestClient(app), db


def test_evaluate_cooldown_meta_default_from_memory():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        """ + table_sql("game_config_meta") + """
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            last_rollup_narrative_turn_count INTEGER
        );
        INSERT INTO campaigns (id) VALUES (1);
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            user_text TEXT NOT NULL,
            route TEXT NOT NULL,
            assistant_text TEXT,
            turn_number INTEGER NOT NULL
        );
        """
    )
    assert get_summary_rollup_cooldown_turns(conn) == 20
    conn.execute(
        "INSERT INTO game_config_meta (key, value) VALUES (?, ?)",
        (META_KEY_SUMMARY_ROLLUP_COOLDOWN, "5"),
    )
    conn.commit()
    assert get_summary_rollup_cooldown_turns(conn) == 5
    allowed, n, la, cur = evaluate_summary_rollup_cooldown(conn, 1)
    assert allowed is True
    assert la is None
    conn.close()


@patch.object(ch_mod, "generate_campaign_summary", side_effect=lambda **kw: _fake_summary())
def test_post_summary_second_call_429_when_same_turn_count(mock_gen, client_and_db):
    client, _db = client_and_db
    r1 = client.post("/api/campaigns/1/history/summary?user_id=10")
    assert r1.status_code == 200
    r2 = client.post("/api/campaigns/1/history/summary?user_id=10")
    assert r2.status_code == 429
    body = r2.json()
    assert body["detail"]["error"] == "summary_rollup_cooldown"
    assert body["detail"]["turns_until_allowed"] >= 1


@patch.object(ch_mod, "generate_campaign_summary", side_effect=lambda **kw: _fake_summary())
def test_post_summary_allowed_after_enough_narrative_turns(mock_gen, client_and_db):
    client, db = client_and_db
    r1 = client.post("/api/campaigns/1/history/summary?user_id=10")
    assert r1.status_code == 200
    _add_narrative_turns(db, 3, start_turn=1)
    r2 = client.post("/api/campaigns/1/history/summary?user_id=10")
    assert r2.status_code == 200


def test_ensure_returns_cooldown_when_stale_but_blocked(client_and_db):
    """Stale vs saved included_turn, but rollup cooldown blocks LLM — must return cache."""
    client, db = client_and_db
    _add_narrative_turns(db, 7, start_turn=1)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE campaigns SET last_rollup_narrative_turn_count = 5 WHERE id = 1"
    )
    conn.execute(
        """
        INSERT INTO campaign_ai_summaries (
            campaign_id, summary_text, model_used, included_turn_count, audience
        )
        VALUES (1, 'cached', 'm', 6, 'player')
        """
    )
    conn.commit()
    conn.close()

    def banned(**kw):
        raise AssertionError("generate_campaign_summary should not run under cooldown")

    with patch.object(ses_mod, "generate_campaign_summary", side_effect=banned):
        r = client.post(
            "/api/campaigns/1/history/summary/ensure?user_id=10&stale_after_turns=1"
        )
    assert r.status_code == 200
    data = r.json()
    assert data.get("cooldown_active") is True
    assert data.get("refreshed") is False
    assert data.get("summary") == "cached"
