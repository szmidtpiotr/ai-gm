"""TDD: Issue #629 (HI6) — Inspektor: „Wymuś edycję" (force) gdy live-lock.

HI6 to feature frontendowy (toggle force w modalu), ale opiera się na własności
backendu: `force=true` na ścieżce inspektora MUSI (a) ominąć blokadę 409 live-lock,
ORAZ (b) i tak zapisać audyt — wymuszona edycja ma być w pełni śledzona.

Ten test pilnuje tej własności na realnej ścieżce equip (`/inventory/{id}/equip`)
przez `inspector_guard`. Gdyby force zaczął gubić audyt albo gdyby blokada bez force
przestała działać, link force z UI cicho złamałby bezpieczeństwo.

Test samowystarczalny (własny schemat w tmp DB, patch `resolve_db_path`).
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services import inspector_guard


def _seed_schema(db_path: str, *, combat: bool = False) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER, user_id INTEGER, name TEXT,
              sheet_json TEXT, status TEXT,
              is_active INTEGER NOT NULL DEFAULT 1, gold_gp INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE character_inventory (
              id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
              item_key TEXT, weapon_key TEXT, consumable_key TEXT,
              quantity INTEGER NOT NULL DEFAULT 1, equipped INTEGER NOT NULL DEFAULT 0, slot TEXT
            );
            CREATE TABLE active_combat (
              id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'active', ended_reason TEXT
            );
            CREATE TABLE game_sessions (id TEXT PRIMARY KEY, campaign_id INTEGER, session_flags TEXT);
            CREATE TABLE admin_audit_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT, table_name TEXT NOT NULL, row_key TEXT,
              operation TEXT NOT NULL, old_values TEXT, new_values TEXT,
              performed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO characters(id, campaign_id, user_id, name, sheet_json, status, gold_gp)
            VALUES (1, 101, 1, 'Bohater Demo', '{"archetype":"warrior","level":3}', 'active', 100);
            INSERT INTO character_inventory(id, character_id, weapon_key) VALUES (7, 1, 'sword_short');
            """
        )
        if combat:
            conn.execute("INSERT INTO active_combat(campaign_id, status) VALUES (101, 'active')")
        conn.commit()
    finally:
        conn.close()


def _audit_rows(db_path: str) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT table_name, row_key, operation FROM admin_audit_log").fetchall()
    finally:
        conn.close()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    p = str(tmp_path / "test_hi6.db")
    monkeypatch.setattr(inspector_guard, "resolve_db_path", lambda: p)
    return p


@pytest.fixture
def equip_client(db_path, monkeypatch):
    from app.api import inventory
    from app.services import loot_service

    monkeypatch.setattr(loot_service, "equip_item", lambda cid, iid, slot: {"equipped": True, "slot": slot})
    monkeypatch.setattr(loot_service, "unequip_item", lambda cid, iid: {"equipped": False})
    app = FastAPI()
    app.include_router(inventory.router, prefix="/api")
    with TestClient(app) as c:
        yield c, db_path


# ─── (a) force omija blokadę live-lock ────────────────────────────────────────

def test_force_bypasses_live_lock_during_combat(equip_client, db_path):
    """inspector:true + force:true w trakcie walki → 200 (nie 409)."""
    c, _ = equip_client
    _seed_schema(db_path, combat=True)
    r = c.post("/api/inventory/1/equip",
               json={"inventory_id": 7, "slot": "main_hand", "inspector": True, "force": True})
    assert r.status_code == 200


# ─── (b) wymuszona mutacja NADAL pisze audyt (śledzenie) ──────────────────────

def test_force_still_writes_audit(equip_client, db_path):
    """Wymuszona edycja musi zostawić ślad w admin_audit_log."""
    c, _ = equip_client
    _seed_schema(db_path, combat=True)
    c.post("/api/inventory/1/equip",
           json={"inventory_id": 7, "slot": "main_hand", "inspector": True, "force": True})
    assert any("equip" in row[2] for row in _audit_rows(db_path)), "wymuszona edycja nie zapisała audytu"


# ─── Regresja: bez force blokada nadal działa ─────────────────────────────────

def test_without_force_still_blocked_during_combat(equip_client, db_path):
    """inspector:true bez force w walce → 409 (lock nie może zniknąć)."""
    c, _ = equip_client
    _seed_schema(db_path, combat=True)
    r = c.post("/api/inventory/1/equip",
               json={"inventory_id": 7, "slot": "main_hand", "inspector": True})
    assert r.status_code == 409
    assert r.json()["detail"]["reason"] == "live_locked"
