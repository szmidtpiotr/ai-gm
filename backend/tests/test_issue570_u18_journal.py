"""TDD: Issue #570 (U18) — Dziennik gracza (Zadania / Wątki / Kronika).

The journal endpoint composes three sources into one read-only payload:
  - Zadania  ← character_quests (active + completed)
  - Wątki    ← narrative_state.seeds filtered by player_visible
  - Kronika  ← narrative_state.events + completed beats (reverse chronological)
Mechanics-only: the journal never writes state, it only reads it.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.journal_service import build_journal  # noqa: E402
from app.services.narrative_state_service import (  # noqa: E402
    apply_narrative_tags,
    seed_narrative_state_from_plan,
)


def _mk_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT);
        CREATE TABLE game_sessions (id TEXT, campaign_id INTEGER, session_flags TEXT);
        CREATE TABLE character_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, campaign_id INTEGER, quest_type TEXT,
            title TEXT, narrative TEXT, status TEXT,
            created_turn INTEGER, completed_turn INTEGER
        );
        """
    )
    return conn


def _seed_campaign(conn: sqlite3.Connection, campaign_id: int = 1) -> None:
    gm_plan = {
        "active_act": 1,
        "acts": [
            {
                "id": "act1",
                "key_beats": [
                    {"beat_key": "rescue", "description": "Uratuj Martę z lochu",
                     "visited": True, "visited_at_turn": 5},
                    {"beat_key": "secret", "description": "Sekret GM (nieodwiedzony)",
                     "visited": False},
                ],
            }
        ],
    }
    conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (?, ?)",
                 (campaign_id, json.dumps(gm_plan)))
    # quests
    conn.execute(
        "INSERT INTO character_quests (character_id, campaign_id, quest_type, title, narrative, status, created_turn) "
        "VALUES (?,?,?,?,?,?,?)",
        (10, campaign_id, "main", "Znajdź klucz", "Zdobądź klucz do bramy", "active", 2),
    )
    conn.execute(
        "INSERT INTO character_quests (character_id, campaign_id, quest_type, title, narrative, status, created_turn, completed_turn) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (10, campaign_id, "main", "Pokonaj goblina", "Zabij goblina", "completed", 1, 4),
    )
    # narrative_state: one visible promise + one GM secret, one event
    ns = apply_narrative_tags(None, events=[("zawalony_most", "Most się zawalił")], turn=3)
    ns = apply_narrative_tags(ns, seeds=[("obietnica_marta", "Obiecałeś pomóc Marcie")],
                              turn=3, player_visible=True)
    ns = apply_narrative_tags(ns, seeds=[("sekret_zdrajca", "Zdrajca w wiosce")],
                              turn=3, player_visible=False)
    flags = {"narrative_state": ns}
    conn.execute("INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (?,?,?)",
                 (str(campaign_id), campaign_id, json.dumps(flags)))
    conn.commit()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_journal_composes_three_sections():
    """Dziennik składa Zadania, Wątki (tylko player_visible) i Kronikę."""
    conn = _mk_db()
    _seed_campaign(conn)
    j = build_journal(1, conn)

    titles = {q["title"] for q in j["quests"]}
    assert titles == {"Znajdź klucz", "Pokonaj goblina"}
    statuses = {q["title"]: q["status"] for q in j["quests"]}
    assert statuses["Znajdź klucz"] == "active"
    assert statuses["Pokonaj goblina"] == "completed"


def test_journal_threads_hide_gm_secrets():
    """Wątki pokazują obietnicę gracza, ale NIE sekret GM (player_visible=False)."""
    conn = _mk_db()
    _seed_campaign(conn)
    j = build_journal(1, conn)
    hints = {t["hint"] for t in j["threads"]}
    assert "Obiecałeś pomóc Marcie" in hints
    assert "Zdrajca w wiosce" not in hints


def test_journal_chronicle_has_events_and_beats_reverse_chrono():
    """Kronika łączy eventy + ukończone beaty, odwrotna chronologia, z numerem tury."""
    conn = _mk_db()
    _seed_campaign(conn)
    j = build_journal(1, conn)
    turns = [e["turn"] for e in j["chronicle"]]
    assert turns == sorted(turns, reverse=True)  # reverse chronological
    texts = " | ".join(e["text"] for e in j["chronicle"])
    assert "Most się zawalił" in texts          # NARRATIVE_EVENT
    assert "Uratuj Martę" in texts              # completed beat
    assert "Sekret GM" not in texts             # un-visited beat excluded


# ─── player_visible na seeds ────────────────────────────────────────────────

def test_apply_narrative_tags_player_visible_defaults_true():
    """Seedy z akcji gracza domyślnie player_visible=True."""
    st = apply_narrative_tags(None, seeds=[("k", "hint")], turn=1)
    assert st["seeds"][0]["player_visible"] is True


def test_apply_narrative_tags_player_visible_false_for_secrets():
    """Seedy oznaczone jako sekret mają player_visible=False."""
    st = apply_narrative_tags(None, seeds=[("k", "hint")], turn=1, player_visible=False)
    assert st["seeds"][0]["player_visible"] is False


def test_seed_from_plan_marks_secrets_hidden():
    """seed_narrative_state_from_plan oznacza wątki GM Planu jako ukryte."""
    conn = _mk_db()
    conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (1, '{}')")
    conn.commit()
    plan = {"narrative_hooks": [{"key": "h1", "hint": "Sekretny wątek planu"}]}
    assert seed_narrative_state_from_plan(1, plan, conn) is True
    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    ns = json.loads(row["session_flags"])["narrative_state"]
    assert ns["seeds"][0]["player_visible"] is False


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_apply_narrative_tags_backward_compat():
    """Stare wywołanie bez player_visible nadal działa (default True)."""
    st = apply_narrative_tags(None, events=[("e", "n")], seeds=[("s", "h")], turn=2)
    assert st["events"][0]["note"] == "n"
    assert st["seeds"][0]["hint"] == "h"
    assert st["seeds"][0]["status"] == "active"
