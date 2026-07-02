"""TDD: Issue #1098 — GET /characters/{id}/chronicle endpoint."""
import sqlite3
import sys
import os

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_db():
    """In-memory SQLite with minimal schema matching DEV migrations."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL DEFAULT 'Hero',
            is_active INTEGER NOT NULL DEFAULT 1,
            legend_digest TEXT
        );

        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'Kampania'
        );

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
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            abandonment_note TEXT,
            key_decisions_json TEXT
        );
    """)
    return conn


# ─── Test główny: struktura odpowiedzi ───────────────────────────────────────

def test_chronicle_returns_legend_chapters_scars():
    """Endpoint zwraca {legend, chapters, scars} dla bohatera z pełną historią."""
    conn = _make_db()
    conn.execute("INSERT INTO characters(id, legend_digest) VALUES (1, 'Wielki wojownik z Kresy.')")
    conn.execute("INSERT INTO campaigns(id, title) VALUES (10, 'Wyprawa na Północ')")
    conn.execute("""
        INSERT INTO character_campaign_history
          (character_id, campaign_id, outcome, chapter_summary, xp_earned, turns_count)
        VALUES (1, 10, 'victory', 'Bohater pokonał smoka.', 500, 12)
    """)
    conn.commit()

    from app.api.characters import _get_chronicle_data
    result = _get_chronicle_data(conn, character_id=1)

    assert result["legend"] == "Wielki wojownik z Kresy."
    assert len(result["chapters"]) == 1
    assert result["chapters"][0]["campaign_title"] == "Wyprawa na Północ"
    assert result["chapters"][0]["outcome"] == "victory"
    assert result["chapters"][0]["chapter_summary"] == "Bohater pokonał smoka."
    assert result["chapters"][0]["xp_earned"] == 500
    assert result["scars"] == []


# ─── Test: bohater bez historii → pusty stan ─────────────────────────────────

def test_chronicle_empty_hero():
    """Bohater bez historii zwraca pustą kronikę (nie 404, nie błąd)."""
    conn = _make_db()
    conn.execute("INSERT INTO characters(id, legend_digest) VALUES (2, NULL)")
    conn.commit()

    from app.api.characters import _get_chronicle_data
    result = _get_chronicle_data(conn, character_id=2)

    assert result["legend"] is None
    assert result["chapters"] == []
    assert result["scars"] == []


# ─── Test: rozdziały oddzielone od blizn ─────────────────────────────────────

def test_chronicle_separates_chapters_from_scars():
    """chapter_summary → chapters[], abandonment_note → scars[] (osobne listy)."""
    conn = _make_db()
    conn.execute("INSERT INTO characters(id) VALUES (3)")
    conn.execute("INSERT INTO campaigns(id, title) VALUES (20, 'Ukończona'), (21, 'Porzucona')")
    conn.execute("""
        INSERT INTO character_campaign_history
          (character_id, campaign_id, outcome, chapter_summary)
        VALUES (3, 20, 'victory', 'Misja wykonana.')
    """)
    conn.execute("""
        INSERT INTO character_campaign_history
          (character_id, campaign_id, outcome, abandonment_note)
        VALUES (3, 21, 'abandoned', 'Zniknął bez słowa przed bitwą o Wachstein.')
    """)
    conn.commit()

    from app.api.characters import _get_chronicle_data
    result = _get_chronicle_data(conn, character_id=3)

    assert len(result["chapters"]) == 1
    assert result["chapters"][0]["chapter_summary"] == "Misja wykonana."
    assert len(result["scars"]) == 1
    assert result["scars"][0]["abandonment_note"] == "Zniknął bez słowa przed bitwą o Wachstein."
    assert result["scars"][0]["campaign_title"] == "Porzucona"


# ─── Backward compat: /history nadal działa ──────────────────────────────────

def test_existing_history_endpoint_still_accessible():
    """GET /characters/{id}/history (istniejący endpoint) nadal dostępny po dodaniu /chronicle."""
    # Import sprawdza że router nie jest zepsuty przez nowy endpoint
    from app.api.characters import router
    routes = [r.path for r in router.routes]
    assert any("/history" in r for r in routes), "Endpoint /history zniknął z routera"
    assert any("/chronicle" in r for r in routes), "Endpoint /chronicle nie istnieje w routerze"
