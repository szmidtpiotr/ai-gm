"""TDD: Issue #626 (HI3) — Inspektor: zakładka Arkusz.

HI3 jest frontend-only, ale opiera się o kontrakt backendu, którego zakładka Arkusz
używa do edycji liczb bohatera. Ten test pilnuje, że WSZYSTKIE pola edytowane w Arkuszu
przez istniejące komendy cheat (`add stat`, `set health`, `set level`, `set gold`) — gdy
wywołane z flagą `inspector:true` jak robi to inspektor — są:
  1. zapisywane (round-trip widoczny w GET /admin/characters/{id}/full),
  2. guardowane live_locked (409 przy aktywnej walce),
  3. audytowane (admin_audit_log),
oraz że /full eksponuje `owner_id` i `campaign_id` (baner #1013 + bramka XP we froncie).

REUSE: cały backend już istnieje (HI1 #623). Test = regression guard kontraktu HI3.
Samowystarczalny (własny schemat w tmp DB, monkeypatch DB_PATH).
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import admin_cheat
from app.routers.admin import require_admin_token


def _seed_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER,
              user_id INTEGER,
              name TEXT,
              location TEXT,
              sheet_json TEXT,
              status TEXT,
              is_active INTEGER NOT NULL DEFAULT 1,
              gold_gp INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE character_inventory (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              character_id INTEGER NOT NULL,
              item_key TEXT, weapon_key TEXT, consumable_key TEXT,
              quantity INTEGER NOT NULL DEFAULT 1,
              equipped INTEGER NOT NULL DEFAULT 0, slot TEXT
            );
            CREATE TABLE active_combat (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'active', ended_reason TEXT
            );
            CREATE TABLE game_sessions (
              id TEXT PRIMARY KEY, campaign_id INTEGER, session_flags TEXT
            );
            CREATE TABLE admin_audit_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              table_name TEXT NOT NULL, row_key TEXT, operation TEXT NOT NULL,
              old_values TEXT, new_values TEXT,
              performed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            INSERT INTO characters(id, campaign_id, user_id, name, location, sheet_json, status, gold_gp)
            VALUES (
              1, 101, 1, 'Demo Bohater', 'start_village',
              '{"archetype":"warrior","current_hp":12,"max_hp":30,"level":3,"stats":{"STR":14,"CON":13,"LCK":9},"skills":{"athletics":1},"conditions":[],"xp":200,"quests_active":[],"quests_completed":[]}',
              'active', 75
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _set_combat_active(db_path: str, active: bool) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM active_combat WHERE campaign_id = 101")
        if active:
            conn.execute("INSERT INTO active_combat(campaign_id, status) VALUES (101, 'active')")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test_hi3_sheet.db")
    old = admin_cheat.DB_PATH
    admin_cheat.DB_PATH = db_path
    _seed_schema(db_path)
    app = FastAPI()
    app.include_router(admin_cheat.router, prefix="/api")
    app.dependency_overrides[require_admin_token] = lambda: None
    try:
        with TestClient(app) as c:
            yield c, db_path
    finally:
        app.dependency_overrides.clear()
        admin_cheat.DB_PATH = old


def _post(c, cmd, **kw):
    return c.post("/api/admin/cheat/1", json={"cmd": cmd, "inspector": True, **kw})


def _full(c) -> dict:
    r = c.get("/api/admin/characters/1/full")
    assert r.status_code == 200
    return r.json()


# ─── /full eksponuje pola wymagane przez Arkusz (HI3) ──────────────────────────

def test_full_exposes_owner_and_campaign_for_frontend(client):
    """Front używa owner_id (baner #1013) i campaign_id (bramka XP)."""
    c, _ = client
    body = _full(c)
    assert body["owner_id"] == 1
    assert body["campaign_id"] == 101
    assert body["stats"]["LCK"] == 9  # LCK obecne (front pokazuje read-only)


# ─── Edytowalne liczby Arkusza round-trip przez inspector:true ─────────────────

def test_inspector_set_gold_roundtrips(client):
    c, _ = client
    assert _post(c, "set gold", value=999).status_code == 200
    assert _full(c)["gold_gp"] == 999


def test_inspector_set_health_roundtrips(client):
    c, _ = client
    assert _post(c, "set health", value=20).status_code == 200
    assert _full(c)["hp"] == 20


def test_inspector_add_stat_roundtrips(client):
    c, _ = client
    assert _post(c, "add stat", stat="STR", value=2).status_code == 200
    assert _full(c)["stats"]["STR"] == 16


def test_inspector_set_level_roundtrips(client):
    c, _ = client
    assert _post(c, "set level", value=5).status_code == 200
    assert _full(c)["level"] == 5


# ─── Guard live_locked obejmuje istniejące cmd-y użyte przez Arkusz ────────────

@pytest.mark.parametrize(
    "cmd,kw",
    [
        ("set gold", {"value": 1}),
        ("set health", {"value": 1}),
        ("add stat", {"stat": "STR", "value": 1}),
        ("set level", {"value": 2}),
    ],
)
def test_inspector_edit_blocked_during_combat(client, cmd, kw):
    c, db = client
    _set_combat_active(db, True)
    r = _post(c, cmd, **kw)
    assert r.status_code == 409
    assert r.json()["detail"]["reason"] == "live_locked"


# ─── Audyt każdej mutacji Arkusza ──────────────────────────────────────────────

def test_inspector_edit_writes_audit(client):
    c, db = client
    _post(c, "set gold", value=123)
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT operation FROM admin_audit_log WHERE table_name='characters' AND row_key='1'"
        ).fetchall()
    finally:
        conn.close()
    assert any("set gold" in r[0] for r in rows)


# ─── Backward compat: bez flagi inspector stare cmd-y nie są guardowane ────────

def test_existing_cmd_without_inspector_not_blocked_in_combat(client):
    c, db = client
    _set_combat_active(db, True)
    r = c.post("/api/admin/cheat/1", json={"cmd": "set gold", "value": 10})
    assert r.status_code == 200
    assert _full(c)["gold_gp"] == 10
