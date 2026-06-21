"""TDD #797 — G11: Catch-up po powrocie (missed rounds + absence warnings reset)."""
import importlib
import json
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ── Minimal schema ────────────────────────────────────────────────────────────

def _make_test_db(tmp_path):
    db_path = str(tmp_path / "test_797.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'test',
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            model_id TEXT NOT NULL DEFAULT 'gpt-4',
            owner_user_id INTEGER NOT NULL DEFAULT 1,
            mode TEXT NOT NULL DEFAULT 'multiplayer',
            status TEXT NOT NULL DEFAULT 'active',
            round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
            round_timer_hours INTEGER NOT NULL DEFAULT 24,
            max_players INTEGER NOT NULL DEFAULT 4,
            host_user_id INTEGER,
            lobby_status TEXT NOT NULL DEFAULT 'open'
        );
        CREATE TABLE IF NOT EXISTS campaign_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'player',
            status TEXT NOT NULL DEFAULT 'accepted',
            character_id INTEGER,
            joined_at TEXT NOT NULL DEFAULT (datetime('now')),
            absence_warnings INTEGER NOT NULL DEFAULT 0,
            UNIQUE(campaign_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS campaign_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'collecting',
            deadline TEXT,
            closed_at TEXT,
            narrative_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS campaign_round_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            character_id INTEGER,
            character_name TEXT NOT NULL DEFAULT 'Bohater',
            action_text TEXT NOT NULL,
            submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
            initiative_roll INTEGER NOT NULL DEFAULT 0,
            UNIQUE(round_id, user_id)
        );
    """)
    conn.commit()
    return db_path, conn


def _load_svc(monkeypatch, db_path: str):
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import app.services.multiplayer_round_service as svc
    importlib.reload(svc)
    monkeypatch.setattr(svc, "trigger_narration", lambda round_id: None)
    return svc


def _add_campaign(conn, cid, uid):
    conn.execute(
        "INSERT INTO campaigns (id, owner_user_id, host_user_id) VALUES (?, ?, ?)",
        (cid, uid, uid),
    )
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, role, status, absence_warnings) "
        "VALUES (?, ?, 'host', 'accepted', 0)",
        (cid, uid),
    )
    conn.commit()


def _add_member(conn, cid, uid, absence_warnings=0):
    conn.execute(
        "INSERT OR REPLACE INTO campaign_members "
        "(campaign_id, user_id, role, status, absence_warnings) VALUES (?, ?, 'player', 'accepted', ?)",
        (cid, uid, absence_warnings),
    )
    conn.commit()


def _add_done_round(conn, cid, round_id, round_number):
    narrative = json.dumps({"narrative": f"Runda {round_number}: drużyna walczyła."})
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status, narrative_json) "
        "VALUES (?, ?, ?, 'done', ?)",
        (round_id, cid, round_number, narrative),
    )
    conn.commit()


def _add_action(conn, round_id, cid, uid, action="Atakuję!"):
    conn.execute(
        "INSERT OR REPLACE INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, action_text) VALUES (?, ?, ?, ?)",
        (round_id, cid, uid, action),
    )
    conn.commit()


# ─── Test 1: Gracz był we WSZYSTKICH rundach → brak missed ───────────────────

def test_no_missed_rounds_when_always_present(tmp_path, monkeypatch):
    """Jeśli gracz uczestniczył we wszystkich rundach → missed_rounds = []."""
    db_path, conn = _make_test_db(tmp_path)
    CID, UID = 7970, 9701
    _add_campaign(conn, CID, UID)
    _add_member(conn, CID, UID, absence_warnings=0)
    for i in range(1, 4):
        _add_done_round(conn, CID, 7970 + i, i)
        _add_action(conn, 7970 + i, CID, UID, "Atakuję!")
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.get_catchup(CID, UID)

    assert result["missed_rounds"] == [], f"Expected no missed rounds, got {result['missed_rounds']}"
    assert result["summary_line"] == ""


# ─── Test 2: Gracz pominął OSTATNIE N rund (tail) ────────────────────────────

def test_missed_tail_rounds_returned(tmp_path, monkeypatch):
    """Gracz obecny w rundach 1-2, pominął 3-5 → missed_rounds=[3,4,5], summary niepuste."""
    db_path, conn = _make_test_db(tmp_path)
    CID, UID = 7971, 9702
    _add_campaign(conn, CID, UID)
    _add_member(conn, CID, UID, absence_warnings=3)
    # present in 1-2
    for i in range(1, 3):
        _add_done_round(conn, CID, 7971 + i, i)
        _add_action(conn, 7971 + i, CID, UID, "Atakuję!")
    # missed 3-5
    for i in range(3, 6):
        _add_done_round(conn, CID, 7971 + i, i)
        _add_action(conn, 7971 + i, CID, UID, "[BRAK AKCJI]")
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.get_catchup(CID, UID)

    assert len(result["missed_rounds"]) == 3, f"Expected 3 missed, got {result['missed_rounds']}"
    missed_nums = [r["round_number"] for r in result["missed_rounds"]]
    assert missed_nums == [3, 4, 5], f"Expected [3,4,5], got {missed_nums}"
    assert result["summary_line"] != "", "summary_line should be non-empty"
    assert "3" in result["summary_line"]


# ─── Test 3: Pominął środkowe, był w ostatniej → tail pusta ─────────────────

def test_no_tail_when_present_in_last_round(tmp_path, monkeypatch):
    """Pominął rundę 2, ale był w rundzie 3 → missed_rounds = [] (tail = [])."""
    db_path, conn = _make_test_db(tmp_path)
    CID, UID = 7972, 9703
    _add_campaign(conn, CID, UID)
    _add_member(conn, CID, UID, absence_warnings=1)
    _add_done_round(conn, CID, 79721, 1)
    _add_action(conn, 79721, CID, UID, "Atakuję!")
    _add_done_round(conn, CID, 79722, 2)
    _add_action(conn, 79722, CID, UID, "[BRAK AKCJI]")
    _add_done_round(conn, CID, 79723, 3)
    _add_action(conn, 79723, CID, UID, "Leczę!")
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.get_catchup(CID, UID)

    assert result["missed_rounds"] == [], f"Tail should be empty, got {result['missed_rounds']}"
    assert result["summary_line"] == ""


# ─── Test 4: absence_warnings reset po get_catchup ───────────────────────────

def test_absence_warnings_reset_on_catchup(tmp_path, monkeypatch):
    """Po wywołaniu get_catchup absence_warnings = 0 dla tego gracza."""
    db_path, conn = _make_test_db(tmp_path)
    CID, UID = 7973, 9704
    _add_campaign(conn, CID, UID)
    _add_member(conn, CID, UID, absence_warnings=5)
    _add_done_round(conn, CID, 79731, 1)
    _add_action(conn, 79731, CID, UID, "[BRAK AKCJI]")
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.get_catchup(CID, UID)

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    row = check.execute(
        "SELECT absence_warnings FROM campaign_members WHERE campaign_id=? AND user_id=?",
        (CID, UID),
    ).fetchone()
    check.close()

    assert row is not None
    assert int(row["absence_warnings"]) == 0, f"Expected 0, got {row['absence_warnings']}"


# ─── Test 5: 0 rund done → missed_rounds = [] ────────────────────────────────

def test_no_done_rounds_returns_empty(tmp_path, monkeypatch):
    """Gdy nie ma żadnej rundy done → missed_rounds = [], summary_line = ''."""
    db_path, conn = _make_test_db(tmp_path)
    CID, UID = 7974, 9705
    _add_campaign(conn, CID, UID)
    _add_member(conn, CID, UID, absence_warnings=0)
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    result = svc.get_catchup(CID, UID)

    assert result["missed_rounds"] == []
    assert result["summary_line"] == ""
