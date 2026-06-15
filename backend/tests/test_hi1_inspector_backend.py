"""TDD: Issue #623 (HI1) — Inspektor Bohatera backend.

Czysty odczyt `/admin/characters/{id}/full` (agregat + is_live_locked) + 3 luki zapisu
w admin_cheat (set skill / set mana / add+remove condition) + audyt każdej mutacji
inspektora + guard live_locked (409 gdy aktywna walka / tura w toku; override force=true).

REUSE: wszystko w admin_cheat.py. Testy są samowystarczalne (własny schemat w tmp DB).
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
              item_key TEXT,
              weapon_key TEXT,
              consumable_key TEXT,
              quantity INTEGER NOT NULL DEFAULT 1,
              equipped INTEGER NOT NULL DEFAULT 0,
              slot TEXT
            );

            CREATE TABLE active_combat (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'active',
              ended_reason TEXT
            );

            CREATE TABLE game_sessions (
              id TEXT PRIMARY KEY,
              campaign_id INTEGER,
              session_flags TEXT
            );

            CREATE TABLE admin_audit_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              table_name TEXT NOT NULL,
              row_key TEXT,
              operation TEXT NOT NULL,
              old_values TEXT,
              new_values TEXT,
              performed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE game_config_conditions (
              key TEXT PRIMARY KEY,
              label TEXT NOT NULL DEFAULT '',
              description TEXT,
              is_active INTEGER NOT NULL DEFAULT 1
            );

            INSERT INTO game_config_conditions(key, label, is_active) VALUES
              ('blessed', 'Błogosławiony', 1),
              ('poisoned', 'Zatruty', 1);

            INSERT INTO characters(id, campaign_id, user_id, name, location, sheet_json, status, gold_gp)
            VALUES (
              1,
              101,
              1,
              'Testowy Bohater',
              'start_village',
              '{"archetype":"scholar","current_hp":5,"max_hp":10,"current_mana":2,"max_mana":8,"level":2,"stats":{"STR":12,"INT":16},"skills":{"arcana":1},"conditions":[],"xp":120,"quests_active":["quest_intro"],"quests_completed":[]}',
              'active',
              50
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
            conn.execute(
                "INSERT INTO active_combat(campaign_id, status) VALUES (101, 'active')"
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def test_db_path(tmp_path):
    return str(tmp_path / "test_hi1_inspector.db")


@pytest.fixture
def client(test_db_path):
    old_db_path = admin_cheat.DB_PATH
    admin_cheat.DB_PATH = test_db_path
    _seed_schema(test_db_path)

    app = FastAPI()
    app.include_router(admin_cheat.router, prefix="/api")
    app.dependency_overrides[require_admin_token] = lambda: None
    try:
        with TestClient(app) as c:
            yield c, test_db_path
    finally:
        app.dependency_overrides.clear()
        admin_cheat.DB_PATH = old_db_path


def _post(client: TestClient, cmd: str, **kwargs):
    payload = {"cmd": cmd}
    payload.update(kwargs)
    return client.post("/api/admin/cheat/1", json=payload)


def _sheet(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = 1").fetchone()
    finally:
        conn.close()
    return json.loads(row[0] or "{}")


# ─── /full aggregate ─────────────────────────────────────────────────────────

def test_full_endpoint_returns_aggregate(client):
    c, _ = client
    r = c.get("/api/admin/characters/1/full")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "id", "name", "gold_gp", "archetype", "level", "stats", "stat_modifiers",
        "skills", "hp", "max_hp", "mana", "max_mana", "conditions",
        "inventory", "spells", "xp", "quests_active", "quests_completed",
        "is_live_locked",
    ):
        assert key in body, f"missing key {key}"
    assert body["level"] == 2
    assert body["mana"] == 2
    assert body["max_mana"] == 8
    # INT 16 → modifier +3
    assert body["stat_modifiers"]["INT"] == 3


def test_full_reports_live_locked_during_combat(client):
    c, db = client
    _set_combat_active(db, True)
    r = c.get("/api/admin/characters/1/full")
    assert r.status_code == 200
    assert r.json()["is_live_locked"] is True


# ─── Set skill rank ──────────────────────────────────────────────────────────

def test_set_skill_updates_sheet(client):
    c, db = client
    r = _post(c, "set skill", key="stealth", value=2)
    assert r.status_code == 200
    assert _sheet(db)["skills"]["stealth"] == 2


def test_set_skill_rejects_out_of_range_rank(client):
    c, _ = client
    r = _post(c, "set skill", key="stealth", value=99)
    assert r.status_code == 422


# ─── Set / add mana ──────────────────────────────────────────────────────────

def test_set_mana_clamped_to_max(client):
    c, db = client
    r = _post(c, "set mana", value=999)
    assert r.status_code == 200
    assert r.json()["result"]["current_mana"] == 8
    assert _sheet(db)["current_mana"] == 8


def test_set_mana_exact_value(client):
    c, db = client
    r = _post(c, "set mana", value=3)
    assert r.status_code == 200
    assert _sheet(db)["current_mana"] == 3


def test_add_mana_increases_current(client):
    c, db = client
    r = _post(c, "add mana", value=4)
    assert r.status_code == 200
    # started at 2, +4 = 6
    assert _sheet(db)["current_mana"] == 6


# ─── Add / remove condition ──────────────────────────────────────────────────

def test_add_condition_appends_from_catalog(client):
    c, db = client
    r = _post(c, "add condition", key="blessed")
    assert r.status_code == 200
    conds = _sheet(db)["conditions"]
    assert any(isinstance(x, dict) and x.get("key") == "blessed" for x in conds)


def test_add_condition_rejects_unknown(client):
    c, _ = client
    r = _post(c, "add condition", key="not_a_real_condition")
    assert r.status_code == 422


def test_remove_condition_removes(client):
    c, db = client
    _post(c, "add condition", key="poisoned")
    r = _post(c, "remove condition", key="poisoned")
    assert r.status_code == 200
    conds = _sheet(db)["conditions"]
    assert not any(isinstance(x, dict) and x.get("key") == "poisoned" for x in conds)


# ─── Audit ───────────────────────────────────────────────────────────────────

def test_mutation_writes_audit_log(client):
    c, db = client
    _post(c, "set skill", key="arcana", value=3)
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT table_name, row_key, operation FROM admin_audit_log"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) >= 1
    assert any(
        r[0] == "characters" and r[1] == "1" and "set skill" in r[2] for r in rows
    )


# ─── Guard live_locked ───────────────────────────────────────────────────────

def test_inspector_mutation_blocked_during_combat(client):
    c, db = client
    _set_combat_active(db, True)
    r = _post(c, "set skill", key="stealth", value=2)
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["reason"] == "live_locked"


def test_force_overrides_live_lock(client):
    c, db = client
    _set_combat_active(db, True)
    r = _post(c, "set skill", key="stealth", value=2, force=True)
    assert r.status_code == 200
    assert _sheet(db)["skills"]["stealth"] == 2


def test_live_lock_when_pending_skill_test(client):
    c, db = client
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO game_sessions(id, campaign_id, session_flags) VALUES (?,?,?)",
            ("101", 101, json.dumps({"pending_skill_test": {"skill_test_id": "abc"}})),
        )
        conn.commit()
    finally:
        conn.close()
    r = _post(c, "set mana", value=5)
    assert r.status_code == 409
    assert r.json()["detail"]["reason"] == "live_locked"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_existing_cheat_without_inspector_flag_works_during_combat(client):
    """Stare wywołania cheat (bez flagi inspector) NIE są guardowane — brak regresji."""
    c, db = client
    _set_combat_active(db, True)
    r = _post(c, "add gold", value=10)
    assert r.status_code == 200
    assert r.json()["result"]["gold_gp"] == 60


def test_inspector_flag_guards_existing_cheat_cmd(client):
    """Inspektor reużywający starego cmd (inspector=true) dostaje guard + audyt."""
    c, db = client
    _set_combat_active(db, True)
    r = _post(c, "add gold", value=10, inspector=True)
    assert r.status_code == 409
    assert r.json()["detail"]["reason"] == "live_locked"
