"""TDD: Issue #721 — GET /campaigns/{id}/dungeon-run musi zwracać zresolvowane riddle.

Bug: Po akcji tile (riddle_hint) frontend wywołuje GET /dungeon-run i nadpisuje
_activeDungeonRun surowym grafem gdzie content.riddle = "riddle_shadow" (string key).
Frontend wyświetla wtedy goły klucz zamiast treści pytania.

Fix: endpoint (lub helper _resolve_run_riddles) musi resolvować string riddle keys
na dict {text, answer, hints, ...} przed zwróceniem run danych.

Weryfikuje:
- _resolve_run_riddles zamienia goły string key na dict w bieżącym node
- _resolve_run_riddles zamienia we WSZYSTKICH odwiedzonych nodes (nie tylko current)
- riddle już dict → bez zmian
- riddle = None → bez zmian
- nieznany klucz → riddle = None
"""
from __future__ import annotations

import json
import sqlite3

import pytest


SCHEMA = """
CREATE TABLE game_config_riddles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    text TEXT NOT NULL,
    answer TEXT NOT NULL,
    answer_alts TEXT DEFAULT '[]',
    hints TEXT DEFAULT '["Wskazówka pierwsza"]',
    difficulty TEXT DEFAULT 'medium',
    theme TEXT DEFAULT 'general',
    is_active INTEGER DEFAULT 1
);
"""


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO game_config_riddles (key, text, answer, hints, is_active) VALUES (?, ?, ?, ?, 1)",
        ("riddle_shadow", "Podążam za tobą w dzień. Czym jestem?", "cień", '["Szukaj przy świetle"]'),
    )
    conn.commit()
    return conn


def _make_run(riddle_value="riddle_shadow") -> dict:
    """Simulate run as stored in session_flags (riddle as raw string key)."""
    return {
        "system": "tiles_v2",
        "positions": {"1": "node_riddle"},
        "graph": {
            "entry_node": "node_entry",
            "nodes": {
                "node_entry": {
                    "visited": True,
                    "cleared": True,
                    "content": {"riddle": None, "enemies": [], "label": "Wejście"},
                },
                "node_riddle": {
                    "visited": True,
                    "cleared": False,
                    "content": {
                        "riddle": riddle_value,  # bare string key — the bug
                        "enemies": [],
                        "label": "Komnata Zagadek",
                    },
                },
            },
        },
    }


# ─── RED: testy które muszą failować bez implementacji _resolve_run_riddles ──

def test_resolve_run_riddles_resolves_current_node_riddle():
    """_resolve_run_riddles musi zamieniać string riddle na dict w bieżącym node.

    BEZ tego fixa frontend dostaje 'riddle_shadow' i wyświetla goły klucz.
    """
    from app.api.dungeons import _resolve_run_riddles

    conn = _make_conn()
    run = _make_run("riddle_shadow")

    # Before: riddle is bare string key
    current_content = run["graph"]["nodes"]["node_riddle"]["content"]
    assert isinstance(current_content["riddle"], str), "Setup error: riddle should be string"

    _resolve_run_riddles(conn, run)

    riddle = current_content["riddle"]
    assert isinstance(riddle, dict), (
        f"#721: content.riddle musi być dict po resolve, jest: {type(riddle).__name__} = {riddle!r}. "
        "Frontend dostaje goły klucz zamiast {{text: '...'}}"
    )
    assert riddle.get("text") == "Podążam za tobą w dzień. Czym jestem?", f"Brak 'text': {riddle}"
    assert riddle.get("answer") == "cień", f"Brak 'answer': {riddle}"
    assert isinstance(riddle.get("hints"), list), f"Brak 'hints': {riddle}"
    conn.close()


def test_resolve_run_riddles_resolves_all_visited_nodes():
    """Wszystkie odwiedzone nody z string riddle muszą być zresolvowane (nie tylko current)."""
    from app.api.dungeons import _resolve_run_riddles

    conn = _make_conn()
    run = {
        "system": "tiles_v2",
        "positions": {"1": "node_b"},
        "graph": {
            "nodes": {
                "node_a": {
                    "visited": True,
                    "content": {"riddle": "riddle_shadow", "enemies": []},
                },
                "node_b": {
                    "visited": True,
                    "content": {"riddle": "riddle_shadow", "enemies": []},
                },
                "node_c": {
                    "visited": False,  # not visited — may have stale data, irrelevant
                    "content": {"riddle": "riddle_shadow", "enemies": []},
                },
            }
        },
    }

    _resolve_run_riddles(conn, run)

    # Both visited nodes resolved
    for node_id in ("node_a", "node_b"):
        riddle = run["graph"]["nodes"][node_id]["content"]["riddle"]
        assert isinstance(riddle, dict), f"node {node_id} riddle nie zresolvowany: {riddle!r}"

    # Non-visited node also resolved (no harm in resolving all)
    # — or we can assert it too; the implementation may resolve all string riddles
    conn.close()


def test_resolve_run_riddles_unknown_key_sets_none():
    """Nieznany klucz riddle → content['riddle'] = None, nie goły string."""
    from app.api.dungeons import _resolve_run_riddles

    conn = _make_conn()
    run = _make_run("riddle_nonexistent")

    _resolve_run_riddles(conn, run)

    riddle = run["graph"]["nodes"]["node_riddle"]["content"]["riddle"]
    assert riddle is None, f"Nieznany klucz powinien dać None, dostano: {riddle!r}"
    conn.close()


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_resolve_run_riddles_noop_when_riddle_already_dict():
    """Riddle już jako dict → bez zmian."""
    from app.api.dungeons import _resolve_run_riddles

    conn = _make_conn()
    existing_dict = {"key": "riddle_shadow", "text": "Już rozwiązane", "solved": True}
    run = _make_run(existing_dict.copy())

    _resolve_run_riddles(conn, run)

    riddle = run["graph"]["nodes"]["node_riddle"]["content"]["riddle"]
    assert isinstance(riddle, dict), f"Dict powinien zostać dict: {riddle!r}"
    assert riddle.get("text") == "Już rozwiązane", "Istniejący dict nie może być nadpisany"
    conn.close()


def test_resolve_run_riddles_noop_when_riddle_none():
    """Node bez riddle (riddle=None) → bez zmian, brak crashu."""
    from app.api.dungeons import _resolve_run_riddles

    conn = _make_conn()
    run = _make_run(None)

    _resolve_run_riddles(conn, run)

    riddle = run["graph"]["nodes"]["node_riddle"]["content"]["riddle"]
    assert riddle is None
    conn.close()


def test_resolve_run_riddles_noop_when_no_graph():
    """Run bez grafu (stary v1 format) → brak crashu."""
    from app.api.dungeons import _resolve_run_riddles

    conn = _make_conn()
    run = {"system": "tiles_v1", "rooms": []}  # no graph key

    _resolve_run_riddles(conn, run)  # must not crash
    conn.close()


def test_resolve_run_riddles_noop_when_run_none():
    """run=None → brak crashu."""
    from app.api.dungeons import _resolve_run_riddles

    conn = _make_conn()
    _resolve_run_riddles(conn, None)  # must not crash
    conn.close()
