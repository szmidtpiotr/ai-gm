"""TDD: Issue #571 (U19) — Recap "Poprzednio w Twojej przygodzie…".

The recap card must appear ONLY when the player returns after a >24h real gap,
must stay hidden for fresh/empty campaigns, and must compose the saved player
summary + last turns + active quests WITHOUT calling the LLM.
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.journal_service import build_recap  # noqa: E402


def _mkdb() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_text TEXT,
            route TEXT NOT NULL DEFAULT 'narrative',
            assistant_text TEXT,
            turn_number INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE character_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            title TEXT,
            narrative TEXT,
            status TEXT,
            quest_type TEXT,
            created_turn INTEGER,
            completed_turn INTEGER
        );
        CREATE TABLE campaign_ai_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            summary_text TEXT,
            model_used TEXT,
            included_turn_count INTEGER,
            audience TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    return conn


def _add_turn(conn, cid, n, *, user, gm, age_days=0.0, route="narrative"):
    conn.execute(
        """INSERT INTO campaign_turns
             (campaign_id, user_text, route, assistant_text, turn_number, created_at)
           VALUES (?, ?, ?, ?, ?, datetime('now', ?))""",
        (cid, user, route, gm, n, f"-{age_days} days"),
    )
    conn.commit()


# ─── Test główny: trigger po >24h ────────────────────────────────────────────

def test_recap_triggers_after_24h_gap():
    """Ostatnia tura sprzed 2 dni → karta recap się pokazuje."""
    conn = _mkdb()
    _add_turn(conn, 1, 1, user="Idę do lasu", gm="Wchodzisz w gęsty las.", age_days=2.0)
    r = build_recap(1, conn)
    assert r["should_show"] is True
    assert r["hours_since_last"] > 24
    assert r["turn_count"] == 1


# ─── Trigger NIE odpala dla świeżej gry ──────────────────────────────────────

def test_recap_not_triggered_when_recent():
    """Tura sprzed chwili → karta się NIE pokazuje."""
    conn = _mkdb()
    _add_turn(conn, 1, 1, user="Atakuję", gm="Trafiasz goblina.", age_days=0.0)
    r = build_recap(1, conn)
    assert r["should_show"] is False


def test_recap_not_triggered_when_no_turns():
    """Nowa kampania (0 tur) → karta się NIE pokazuje."""
    conn = _mkdb()
    r = build_recap(1, conn)
    assert r["should_show"] is False
    assert r["turn_count"] == 0


# ─── Kompozycja: summary + ostatnie tury + aktywne questy ─────────────────────

def test_recap_composition():
    """Karta zawiera zapisane summary, ostatnie 2 tury i aktywne questy."""
    conn = _mkdb()
    _add_turn(conn, 1, 1, user="Pierwsza", gm="GM 1", age_days=3.0)
    _add_turn(conn, 1, 2, user="Druga", gm="GM 2", age_days=2.5)
    _add_turn(conn, 1, 3, user="Trzecia", gm="GM 3", age_days=2.0)
    conn.execute(
        "INSERT INTO campaign_ai_summaries (campaign_id, summary_text, audience) VALUES (1, ?, 'player')",
        ("Dotychczas bohater zwiedził las i poznał Martę.",),
    )
    conn.execute(
        """INSERT INTO character_quests (campaign_id, title, narrative, status, created_turn)
           VALUES (1, 'Znajdź miecz', 'Marta poprosiła o miecz', 'active', 1)""",
    )
    conn.execute(
        """INSERT INTO character_quests (campaign_id, title, narrative, status, created_turn)
           VALUES (1, 'Stary quest', 'zrobiony', 'completed', 0)""",
    )
    conn.commit()

    r = build_recap(1, conn)
    assert r["should_show"] is True
    assert "Mart" in r["summary"]
    assert len(r["recent_turns"]) == 2          # RECAP_RECENT_TURNS
    assert r["recent_turns"][0]["turn_number"] == 3   # newest first
    titles = [q["title"] for q in r["active_quests"]]
    assert "Znajdź miecz" in titles
    assert "Stary quest" not in titles          # completed filtered out


# ─── Marker wewnętrzny ukryty przed graczem ──────────────────────────────────

def test_recap_hides_internal_markers():
    """user_text typu __AI_GM_OPEN nie wycieka do karty."""
    conn = _mkdb()
    _add_turn(conn, 1, 1, user="__AI_GM_OPEN", gm="Twoja przygoda się zaczyna.", age_days=2.0)
    r = build_recap(1, conn)
    assert r["recent_turns"][0]["player"] == ""
    assert "przygoda" in r["recent_turns"][0]["gm"]


def test_recap_strips_json_envelope():
    """assistant_text w formacie {"narrative": ...} → karta pokazuje czystą prozę."""
    conn = _mkdb()
    _add_turn(conn, 1, 1, user="Idę",
              gm='{"narrative": "Wchodzisz do mrocznej jaskini."}', age_days=2.0)
    r = build_recap(1, conn)
    gm = r["recent_turns"][0]["gm"]
    assert "Wchodzisz do mrocznej jaskini." in gm
    assert "{" not in gm and "narrative" not in gm
