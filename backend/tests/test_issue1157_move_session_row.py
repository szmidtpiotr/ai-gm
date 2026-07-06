"""TDD: Issue #1157 — /move pisał do złego wiersza game_sessions.

`UPDATE game_sessions ... WHERE id = ?` bindował `campaign_id` do kolumny PK `id`,
ale `game_sessions.id != campaign_id`. Zapis trafiał w nieistniejący wiersz i /move
cicho nic nie zmieniał. Fix: keyować po `campaign_id`.
"""
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.turn import turn_commands


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE game_sessions (id INTEGER PRIMARY KEY, campaign_id INTEGER,
            current_location_id INTEGER);
        CREATE TABLE game_locations (id INTEGER PRIMARY KEY, label TEXT);
        INSERT INTO game_locations (id, label) VALUES (99, 'Tawerna');
        """
    )
    return conn


def _stub_log(**kw):
    return {"turn_id": 1}


def _stub_trace(d, tid):
    return d


def _patch_move(monkeypatch, *, resolved_id=99):
    monkeypatch.setattr(turn_commands, "get_bool_flag", lambda *a, **k: True)
    monkeypatch.setattr(
        turn_commands, "validate_move",
        lambda cid, intent: SimpleNamespace(
            allowed=True, resolved_location_id=resolved_id,
            is_new_location=False, block_reason=None,
        ),
    )


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_move_updates_row_keyed_by_campaign_id(monkeypatch):
    """Sesja ma id=5 != campaign_id=1 → /move musi trafić w wiersz campaign_id=1."""
    conn = _db()
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id) VALUES (5, 1, NULL)"
    )
    conn.commit()
    _patch_move(monkeypatch)

    turn_commands.handle(
        conn=conn, campaign_id=1, character_id=1, text="/move Tawerna",
        cmd="/move", turn_id=1, create_turn_log=_stub_log, _with_turn_trace=_stub_trace,
    )

    got = conn.execute(
        "SELECT current_location_id FROM game_sessions WHERE campaign_id = 1"
    ).fetchone()[0]
    assert got == 99, f"lokalizacja nie zapisana w wierszu campaign_id=1 (got {got})"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_move_still_works_when_id_equals_campaign_id(monkeypatch):
    """Gdy przypadkiem id == campaign_id, zapis nadal działa."""
    conn = _db()
    conn.execute(
        "INSERT INTO game_sessions (id, campaign_id, current_location_id) VALUES (1, 1, NULL)"
    )
    conn.commit()
    _patch_move(monkeypatch)

    turn_commands.handle(
        conn=conn, campaign_id=1, character_id=1, text="/move Tawerna",
        cmd="/move", turn_id=1, create_turn_log=_stub_log, _with_turn_trace=_stub_trace,
    )

    got = conn.execute(
        "SELECT current_location_id FROM game_sessions WHERE campaign_id = 1"
    ).fetchone()[0]
    assert got == 99
