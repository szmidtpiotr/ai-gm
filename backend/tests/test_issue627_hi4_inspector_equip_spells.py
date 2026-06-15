"""TDD: Issue #627 (HI4) — Inspektor: zakładki Ekwipunek + Zaklęcia + Questy.

Backend tej części to CIENKI guard+audyt inspektora dla ścieżek, które wcześniej go
nie miały: equip (`/inventory/{id}/equip`) i zaklęcia (`/admin/characters/{id}/spells/
learn|upgrade`). Logika żyje w nowym module `app.services.inspector_guard` (jedno źródło);
`admin_cheat.character_inspector_live_lock` do niego deleguje.

Operacje przedmiotów/questów (add/remove item, quest add/complete) idą przez admin_cheat
z `inspector:true` i są pokryte testem HI1 — tu testujemy tylko nowe luki.

Testy samowystarczalne (własny schemat w tmp DB, patch `resolve_db_path`).
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.services import inspector_guard


def _seed_schema(db_path: str, *, combat: bool = False, pending: bool = False) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER,
              user_id INTEGER,
              name TEXT,
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
            INSERT INTO characters(id, campaign_id, user_id, name, sheet_json, status, gold_gp)
            VALUES (1, 101, 1, 'Testowy Bohater',
              '{"archetype":"scholar","level":2}', 'active', 50);
            INSERT INTO character_inventory(id, character_id, weapon_key) VALUES (7, 1, 'sword_short');
            """
        )
        if combat:
            conn.execute("INSERT INTO active_combat(campaign_id, status) VALUES (101, 'active')")
        if pending:
            conn.execute(
                "INSERT INTO game_sessions(id, campaign_id, session_flags) VALUES (?,?,?)",
                ("101", 101, json.dumps({"pending_skill_test": {"id": "x"}})),
            )
        conn.commit()
    finally:
        conn.close()


def _audit_rows(db_path: str) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT table_name, row_key, operation FROM admin_audit_log"
        ).fetchall()
    finally:
        conn.close()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    p = str(tmp_path / "test_hi4.db")
    monkeypatch.setattr(inspector_guard, "resolve_db_path", lambda: p)
    return p


# ─── inspector_guard — jednostkowo (nowe jedno źródło logiki) ─────────────────

def test_live_lock_by_campaign_true_during_combat(db_path):
    _seed_schema(db_path, combat=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        locked, reason = inspector_guard.live_lock_by_campaign(conn, 101)
    finally:
        conn.close()
    assert locked is True
    assert reason == "active_combat"


def test_live_lock_by_campaign_false_when_idle(db_path):
    _seed_schema(db_path, combat=False)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        locked, reason = inspector_guard.live_lock_by_campaign(conn, 101)
    finally:
        conn.close()
    assert locked is False
    assert reason is None


def test_live_lock_by_character_resolves_campaign(db_path):
    _seed_schema(db_path, pending=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        locked, reason = inspector_guard.live_lock_by_character(conn, 1)
    finally:
        conn.close()
    assert locked is True
    assert reason == "pending_skill_test"


def test_guard_or_raise_409_during_combat(db_path):
    _seed_schema(db_path, combat=True)
    with pytest.raises(HTTPException) as exc:
        inspector_guard.guard_or_raise(1, force=False)
    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "live_locked"


def test_guard_or_raise_force_overrides(db_path):
    _seed_schema(db_path, combat=True)
    # force=True → brak wyjątku
    inspector_guard.guard_or_raise(1, force=True)


def test_audit_writes_row(db_path):
    _seed_schema(db_path)
    inspector_guard.audit(1, "inspector:equip", {"inventory_id": 7}, {"equipped": True})
    rows = _audit_rows(db_path)
    assert any(r[0] == "characters" and r[1] == "1" and "equip" in r[2] for r in rows)


# ─── admin_cheat deleguje do inspector_guard (jedno źródło) ───────────────────

def test_admin_cheat_live_lock_delegates(db_path):
    """character_inspector_live_lock musi zwracać to samo co inspector_guard."""
    _seed_schema(db_path, combat=True)
    from app.routers import admin_cheat
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        locked, reason = admin_cheat.character_inspector_live_lock(conn, 101)
    finally:
        conn.close()
    assert locked is True
    assert reason == "active_combat"


# ─── Equip endpoint — guard + audyt gdy inspector:true ───────────────────────

@pytest.fixture
def equip_client(db_path, monkeypatch):
    from app.api import inventory
    from app.services import loot_service

    monkeypatch.setattr(
        loot_service, "equip_item", lambda cid, iid, slot: {"equipped": True, "slot": slot}
    )
    monkeypatch.setattr(
        loot_service, "unequip_item", lambda cid, iid: {"equipped": False}
    )
    app = FastAPI()
    app.include_router(inventory.router, prefix="/api")
    with TestClient(app) as c:
        yield c, db_path


def test_equip_inspector_blocked_during_combat(equip_client, db_path):
    c, _ = equip_client
    _seed_schema(db_path, combat=True)
    r = c.post("/api/inventory/1/equip", json={"inventory_id": 7, "slot": "main_hand", "inspector": True})
    assert r.status_code == 409
    assert r.json()["detail"]["reason"] == "live_locked"


def test_equip_inspector_writes_audit(equip_client, db_path):
    c, _ = equip_client
    _seed_schema(db_path, combat=False)
    r = c.post("/api/inventory/1/equip", json={"inventory_id": 7, "slot": "main_hand", "inspector": True})
    assert r.status_code == 200
    assert any("equip" in row[2] for row in _audit_rows(db_path))


def test_unequip_inspector_writes_audit(equip_client, db_path):
    c, _ = equip_client
    _seed_schema(db_path, combat=False)
    r = c.post("/api/inventory/1/equip", json={"inventory_id": 7, "inspector": True})
    assert r.status_code == 200
    assert any("equip" in row[2] for row in _audit_rows(db_path))


def test_equip_without_inspector_not_guarded_and_no_audit(equip_client, db_path):
    """Backward compat: zwykłe wywołanie equip (gra) NIE jest guardowane ani audytowane."""
    c, _ = equip_client
    _seed_schema(db_path, combat=True)
    r = c.post("/api/inventory/1/equip", json={"inventory_id": 7, "slot": "main_hand"})
    assert r.status_code == 200
    assert _audit_rows(db_path) == []


# ─── Spells learn/upgrade — guard + audyt gdy inspector:true ──────────────────

@pytest.fixture
def spell_funcs(db_path, monkeypatch):
    import app.services.spell_service as spell_service
    from app.routers import admin as admin_router

    monkeypatch.setattr(spell_service, "learn_spell", lambda cid, key: {"spell_key": key, "rank": 1})
    monkeypatch.setattr(spell_service, "upgrade_spell", lambda cid, key: {"spell_key": key, "rank": 2})
    return admin_router


def test_learn_spell_inspector_blocked_during_combat(spell_funcs, db_path):
    _seed_schema(db_path, combat=True)
    with pytest.raises(HTTPException) as exc:
        spell_funcs.admin_learn_spell(1, {"spell_key": "magic_bolt", "inspector": True}, None)
    assert exc.value.status_code == 409


def test_learn_spell_inspector_writes_audit(spell_funcs, db_path):
    _seed_schema(db_path, combat=False)
    res = spell_funcs.admin_learn_spell(1, {"spell_key": "magic_bolt", "inspector": True}, None)
    assert res["ok"] is True
    assert any("learn" in row[2] for row in _audit_rows(db_path))


def test_upgrade_spell_inspector_writes_audit(spell_funcs, db_path):
    _seed_schema(db_path, combat=False)
    res = spell_funcs.admin_upgrade_spell(1, {"spell_key": "magic_bolt", "inspector": True}, None)
    assert res["ok"] is True
    assert any("upgrade" in row[2] for row in _audit_rows(db_path))


def test_learn_spell_without_inspector_not_guarded(spell_funcs, db_path):
    """Backward compat: nauka spella spoza inspektora (np. skrypt) nie jest guardowana."""
    _seed_schema(db_path, combat=True)
    res = spell_funcs.admin_learn_spell(1, {"spell_key": "magic_bolt"}, None)
    assert res["ok"] is True
    assert _audit_rows(db_path) == []
