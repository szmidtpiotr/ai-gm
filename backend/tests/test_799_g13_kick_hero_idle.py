"""TDD #799 — G13: Host kick → hero freed to idle, XP/gold/items/spells preserved."""
import importlib
import json
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── DB helpers ────────────────────────────────────────────────────────────────

def _make_test_db(tmp_path):
    db_path = str(tmp_path / "test_799.db")
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
            owner_user_id INTEGER NOT NULL,
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
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            absence_warnings INTEGER NOT NULL DEFAULT 0,
            pending_intro INTEGER NOT NULL DEFAULT 0,
            UNIQUE(campaign_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            sheet_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'idle'
        );
        CREATE TABLE IF NOT EXISTS character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            item_key TEXT,
            qty INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS character_spells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            spell_key TEXT NOT NULL,
            rank INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS campaign_kick_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            target_user_id INTEGER NOT NULL,
            voter_user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(campaign_id, target_user_id, voter_user_id)
        );
    """)
    conn.commit()
    return db_path, conn


def _conn(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def _setup_lobby(conn, lobby_status="open"):
    """host=10, player=11 with hero (id=21) carrying XP/gold/item/spell."""
    sheet = json.dumps({"xp": 150, "gold": 75, "level": 3})
    for uid, name in [(10, "host"), (11, "player1")]:
        conn.execute("INSERT INTO users (id, username) VALUES (?, ?)", (uid, name))
    conn.execute(
        "INSERT INTO campaigns (id, title, owner_user_id, host_user_id, mode, lobby_status) "
        "VALUES (1, 'TestCamp', 10, 10, 'multiplayer', ?)",
        (lobby_status,),
    )
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, status, character_id) "
        "VALUES (1, 10, 'accepted', NULL)"
    )
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, status, character_id) "
        "VALUES (1, 11, 'accepted', 21)"
    )
    conn.execute(
        "INSERT INTO characters (id, campaign_id, user_id, name, sheet_json, status) "
        "VALUES (21, 1, 11, 'Aria', ?, 'active')",
        (sheet,),
    )
    conn.execute(
        "INSERT INTO character_inventory (character_id, item_key, qty) VALUES (21, 'sword', 1)"
    )
    conn.execute(
        "INSERT INTO character_spells (character_id, spell_key, rank) VALUES (21, 'magic_bolt', 2)"
    )
    conn.commit()


def _make_client(monkeypatch, db_path: str):
    import app.api.multiplayer as mp
    importlib.reload(mp)

    def _test_db():
        return _conn(db_path)

    monkeypatch.setattr(mp, "_db", _test_db)
    app_inst = FastAPI()
    app_inst.include_router(mp.router)
    return TestClient(app_inst, raise_server_exceptions=False)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_kick_before_start_frees_hero(tmp_path, monkeypatch):
    """Host kicks player in open lobby → hero becomes idle with campaign_id=NULL."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_lobby(conn, lobby_status="open")
    conn.close()

    client = _make_client(monkeypatch, db_path)
    r = client.delete("/multiplayer/campaigns/1/players/11?user_id=10")
    assert r.status_code == 200, r.text

    check = _conn(db_path)
    member = check.execute(
        "SELECT status FROM campaign_members WHERE campaign_id=1 AND user_id=11"
    ).fetchone()
    assert member["status"] == "kicked", f"Expected 'kicked', got '{member['status']}'"

    hero = check.execute(
        "SELECT campaign_id, status FROM characters WHERE id=21"
    ).fetchone()
    assert hero["campaign_id"] is None, "Hero campaign_id must be NULL after kick"
    assert hero["status"] == "idle", "Hero status must be idle after kick"
    check.close()


def test_kick_after_start_allowed(tmp_path, monkeypatch):
    """Host can kick player AFTER game started (lobby_status='started')."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_lobby(conn, lobby_status="started")
    conn.close()

    client = _make_client(monkeypatch, db_path)
    r = client.delete("/multiplayer/campaigns/1/players/11?user_id=10")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    check = _conn(db_path)
    hero = check.execute(
        "SELECT campaign_id, status FROM characters WHERE id=21"
    ).fetchone()
    assert hero["campaign_id"] is None
    assert hero["status"] == "idle"
    check.close()


def test_kick_preserves_xp_and_gold(tmp_path, monkeypatch):
    """After kick: sheet_json (XP, gold, level) unchanged."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_lobby(conn, lobby_status="started")
    conn.close()

    client = _make_client(monkeypatch, db_path)
    client.delete("/multiplayer/campaigns/1/players/11?user_id=10")

    check = _conn(db_path)
    hero = check.execute("SELECT sheet_json FROM characters WHERE id=21").fetchone()
    sheet = json.loads(hero["sheet_json"])
    assert sheet["xp"] == 150, "XP must not change after kick"
    assert sheet["gold"] == 75, "Gold must not change after kick"
    assert sheet["level"] == 3, "Level must not change after kick"
    check.close()


def test_kick_preserves_inventory(tmp_path, monkeypatch):
    """After kick: character_inventory rows unchanged."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_lobby(conn, lobby_status="started")
    conn.close()

    client = _make_client(monkeypatch, db_path)
    client.delete("/multiplayer/campaigns/1/players/11?user_id=10")

    check = _conn(db_path)
    items = check.execute(
        "SELECT item_key, qty FROM character_inventory WHERE character_id=21"
    ).fetchall()
    assert len(items) == 1, "Inventory must not be deleted after kick"
    assert items[0]["item_key"] == "sword"
    assert items[0]["qty"] == 1
    check.close()


def test_kick_preserves_spells(tmp_path, monkeypatch):
    """After kick: character_spells rows unchanged."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_lobby(conn, lobby_status="started")
    conn.close()

    client = _make_client(monkeypatch, db_path)
    client.delete("/multiplayer/campaigns/1/players/11?user_id=10")

    check = _conn(db_path)
    spells = check.execute(
        "SELECT spell_key, rank FROM character_spells WHERE character_id=21"
    ).fetchall()
    assert len(spells) == 1, "Spells must not be deleted after kick"
    assert spells[0]["spell_key"] == "magic_bolt"
    assert spells[0]["rank"] == 2
    check.close()


def test_slot_freed_after_kick(tmp_path, monkeypatch):
    """After kick: campaign_members.status='kicked' (slot clearly available for replacement)."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_lobby(conn, lobby_status="open")
    conn.close()

    client = _make_client(monkeypatch, db_path)
    r = client.delete("/multiplayer/campaigns/1/players/11?user_id=10")
    assert r.status_code == 200

    check = _conn(db_path)
    member = check.execute(
        "SELECT status FROM campaign_members WHERE campaign_id=1 AND user_id=11"
    ).fetchone()
    assert member["status"] == "kicked"
    check.close()


def test_non_host_cannot_kick(tmp_path, monkeypatch):
    """Only host can kick — non-host gets 403."""
    db_path, conn = _make_test_db(tmp_path)
    _setup_lobby(conn, lobby_status="open")
    conn.close()

    client = _make_client(monkeypatch, db_path)
    r = client.delete("/multiplayer/campaigns/1/players/10?user_id=11")
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
