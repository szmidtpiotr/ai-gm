"""TDD #803 — G22: Drabina nieobecności: autopilot opt-in + auto-handoff hosta."""
import importlib
import sqlite3
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_test_db(tmp_path):
    """Minimal schema for G22 tests including autopilot_consent column."""
    db_path = str(tmp_path / "test_803.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            model_id TEXT NOT NULL DEFAULT 'gpt-4',
            owner_user_id INTEGER NOT NULL DEFAULT 1,
            mode TEXT NOT NULL DEFAULT 'multiplayer',
            status TEXT NOT NULL DEFAULT 'active',
            round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
            round_timer_hours INTEGER NOT NULL DEFAULT 24,
            max_players INTEGER NOT NULL DEFAULT 4,
            host_user_id INTEGER,
            lobby_status TEXT NOT NULL DEFAULT 'open',
            host_note TEXT,
            template_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS campaign_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'player',
            status TEXT NOT NULL DEFAULT 'accepted',
            character_id INTEGER,
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            absence_warnings INTEGER NOT NULL DEFAULT 0,
            autopilot_consent INTEGER NOT NULL DEFAULT 0,
            last_seen TEXT,
            pending_intro INTEGER NOT NULL DEFAULT 0,
            UNIQUE(campaign_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            sheet_json TEXT NOT NULL DEFAULT '{}'
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
            character_name TEXT NOT NULL,
            action_text TEXT NOT NULL,
            submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
            initiative_roll INTEGER NOT NULL DEFAULT 0,
            UNIQUE(round_id, user_id)
        );
    """)
    conn.commit()
    return db_path, conn


def _setup_2player_campaign(conn, camp_id=1, host_id=101, other_id=102, host_consent=0):
    conn.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?,?)", (host_id, f"host{host_id}"))
    conn.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?,?)", (other_id, f"user{other_id}"))
    conn.execute(
        "INSERT OR IGNORE INTO campaigns (id, title, host_user_id, owner_user_id) VALUES (?,?,?,?)",
        (camp_id, "G22Camp", host_id, host_id),
    )
    conn.execute(
        "INSERT OR IGNORE INTO campaign_members (campaign_id, user_id, status, absence_warnings, autopilot_consent) "
        "VALUES (?,?,?,?,?)",
        (camp_id, host_id, "accepted", 0, host_consent),
    )
    conn.execute(
        "INSERT OR IGNORE INTO campaign_members (campaign_id, user_id, status, absence_warnings, autopilot_consent) "
        "VALUES (?,?,?,?,?)",
        (camp_id, other_id, "accepted", 0, 0),
    )
    conn.execute(
        "INSERT OR IGNORE INTO characters (id, campaign_id, user_id, name) VALUES (?,?,?,?)",
        (host_id * 10, camp_id, host_id, f"HeroOf{host_id}"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO characters (id, campaign_id, user_id, name) VALUES (?,?,?,?)",
        (other_id * 10, camp_id, other_id, f"HeroOf{other_id}"),
    )
    conn.commit()


def _add_expired_round(conn, camp_id=1, round_id=1, round_num=1):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT OR IGNORE INTO campaign_rounds (id, campaign_id, round_number, status, deadline) "
        "VALUES (?,?,?,'collecting',?)",
        (round_id, camp_id, round_num, past),
    )
    conn.commit()


def _load_svc(monkeypatch, db_path: str):
    monkeypatch.setenv("AI_TEST_DB_PATH", db_path)
    import app.services.multiplayer_round_service as svc
    importlib.reload(svc)
    monkeypatch.setattr(svc, "trigger_narration", lambda round_id: None)
    return svc


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_no_consent_gets_brak_akcji(tmp_path, monkeypatch):
    """Gracz bez zgody (autopilot_consent=0) → akcja = [BRAK AKCJI]."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2player_campaign(conn, camp_id=1, host_id=101, other_id=102, host_consent=0)
    _add_expired_round(conn, camp_id=1, round_id=1)
    # other_id submits, host_id does NOT
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1,1,102,1020,'HeroOf102','Atakuję!')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.sweep_expired_rounds()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    action = check.execute(
        "SELECT action_text FROM campaign_round_actions WHERE round_id=1 AND user_id=101"
    ).fetchone()
    assert action is not None, "Host should have an action inserted"
    assert action["action_text"] == "[BRAK AKCJI]", (
        f"Expected [BRAK AKCJI], got {action['action_text']!r}"
    )
    check.close()


def test_with_consent_gets_autopilot(tmp_path, monkeypatch):
    """Gracz ze zgodą (autopilot_consent=1) → akcja = [AUTOPILOT — postać trzyma pozycję]."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2player_campaign(conn, camp_id=1, host_id=101, other_id=102, host_consent=1)
    _add_expired_round(conn, camp_id=1, round_id=1)
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1,1,102,1020,'HeroOf102','Atakuję!')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.sweep_expired_rounds()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    action = check.execute(
        "SELECT action_text FROM campaign_round_actions WHERE round_id=1 AND user_id=101"
    ).fetchone()
    assert action is not None, "Host should have an action inserted"
    assert action["action_text"] == "[AUTOPILOT — postać trzyma pozycję]", (
        f"Expected autopilot action, got {action['action_text']!r}"
    )
    check.close()


def test_both_consent_levels_increment_warnings(tmp_path, monkeypatch):
    """Zarówno brak akcji jak i autopilot podbijają absence_warnings o 1."""
    db_path, conn = _make_test_db(tmp_path)
    # host_id=101 consent=0, other_id=102 consent=1 — both miss the round
    _setup_2player_campaign(conn, camp_id=1, host_id=101, other_id=102, host_consent=0)
    conn.execute("UPDATE campaign_members SET autopilot_consent=1 WHERE campaign_id=1 AND user_id=102")
    _add_expired_round(conn, camp_id=1, round_id=1)
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.sweep_expired_rounds()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    for uid in [101, 102]:
        row = check.execute(
            "SELECT absence_warnings FROM campaign_members WHERE campaign_id=1 AND user_id=?",
            (uid,),
        ).fetchone()
        assert row is not None
        assert int(row["absence_warnings"]) == 1, (
            f"user {uid} should have 1 absence_warning after missing round"
        )
    check.close()


def test_promote_next_host_helper_is_importable():
    """_promote_next_host helper istnieje i jest callable (jeden punkt prawdy)."""
    from app.services.multiplayer_round_service import _promote_next_host
    assert callable(_promote_next_host), "_promote_next_host must be a callable"


def test_absent_host_triggers_auto_handoff(tmp_path, monkeypatch):
    """Nieobecny host z absence_warnings>=1 → po kolejnej nieobecności host przeniesiony."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2player_campaign(conn, camp_id=1, host_id=101, other_id=102, host_consent=0)
    # Pre-set absence_warnings=1 for host — next miss crosses threshold (>=2)
    conn.execute("UPDATE campaign_members SET absence_warnings=1 WHERE campaign_id=1 AND user_id=101")
    _add_expired_round(conn, camp_id=1, round_id=1)
    # other_id submits, host_id does NOT
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1,1,102,1020,'HeroOf102','Atakuję!')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.sweep_expired_rounds()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    camp = check.execute("SELECT host_user_id, host_note FROM campaigns WHERE id=1").fetchone()
    assert camp is not None
    assert int(camp["host_user_id"]) == 102, (
        f"Host should be transferred to user 102, got {camp['host_user_id']}"
    )
    assert camp["host_note"] is not None and len(camp["host_note"]) > 0, (
        "New host should receive a host_note"
    )
    check.close()


def test_single_absence_does_not_trigger_handoff(tmp_path, monkeypatch):
    """Pojedyncza nieobecność hosta (absence_warnings=0→1) NIE odbiera mu roli."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_2player_campaign(conn, camp_id=1, host_id=101, other_id=102, host_consent=0)
    _add_expired_round(conn, camp_id=1, round_id=1)
    conn.execute(
        "INSERT INTO campaign_round_actions "
        "(round_id, campaign_id, user_id, character_id, character_name, action_text) "
        "VALUES (1,1,102,1020,'HeroOf102','Atakuję!')"
    )
    conn.commit()
    conn.close()

    svc = _load_svc(monkeypatch, db_path)
    svc.sweep_expired_rounds()

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    camp = check.execute("SELECT host_user_id FROM campaigns WHERE id=1").fetchone()
    assert int(camp["host_user_id"]) == 101, (
        "First miss should NOT transfer host (threshold is 2 consecutive misses)"
    )
    check.close()
