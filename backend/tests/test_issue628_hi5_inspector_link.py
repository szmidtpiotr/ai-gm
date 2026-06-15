"""TDD: Issue #628 (HI5) — link „Otwórz inspektora" z monitora kampanii.

HI5 nie dodaje backendu: otwiera TEN SAM modal Inspektora (HI2) z drugiego miejsca
(karta bohatera w monitorze kampanii). Cała mutacja z tego modalu idzie tą samą,
guardowaną ścieżką co z sekcji „Bohaterowie" (`inspector:true` →
`inspector_guard.guard_or_raise` 409 + `inspector_guard.audit` wpis).

Ten test domyka „weryfikację audytu/live-lock end-to-end" z opisu HI5: dowodzi, że
ścieżka, którą reużywa link, NADAL blokuje edycję w trakcie walki i pisze audyt.
Gdyby któryś z tych bezpieczników zniknął, link z kampanii cicho ominąłby ochronę.

Test samowystarczalny (własny schemat w tmp DB, patch `resolve_db_path`).
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi import HTTPException

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
            -- Bohater przypisany do kampanii 101 (jak na karcie monitora kampanii).
            INSERT INTO characters(id, campaign_id, user_id, name, sheet_json, status, gold_gp)
            VALUES (1, 101, 1, 'Bohater Demo',
              '{"archetype":"warrior","level":3}', 'active', 100);
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
    p = str(tmp_path / "test_hi5.db")
    monkeypatch.setattr(inspector_guard, "resolve_db_path", lambda: p)
    return p


# ─── Live-lock dziedziczony: edycja z modalu otwartego z kampanii jest blokowana ──

def test_link_target_blocked_during_combat(db_path):
    """Bohater w walce → mutacja inspektora (z modalu kampanii) musi dać 409 live_locked."""
    _seed_schema(db_path, combat=True)
    with pytest.raises(HTTPException) as exc:
        inspector_guard.guard_or_raise(1, force=False)
    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "live_locked"


def test_link_target_blocked_during_pending_turn(db_path):
    """Tura w toku (pending_skill_test) → też 409 (anty-desync)."""
    _seed_schema(db_path, pending=True)
    with pytest.raises(HTTPException) as exc:
        inspector_guard.guard_or_raise(1, force=False)
    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "live_locked"


# ─── Audyt dziedziczony: udana mutacja z linku pisze wpis ─────────────────────

def test_link_target_writes_audit_when_idle(db_path):
    """Bohater wolny → mutacja przechodzi i zostawia ślad w admin_audit_log."""
    _seed_schema(db_path, combat=False)
    inspector_guard.guard_or_raise(1, force=False)  # brak wyjątku
    inspector_guard.audit(1, "inspector:set gold", {"gold_gp": 100}, {"gold_gp": 250})
    rows = _audit_rows(db_path)
    assert any(r[0] == "characters" and r[1] == "1" and "gold" in r[2] for r in rows)


# ─── Backward compat: zwykła gra (bez inspektora) nie jest blokowana z tej ścieżki ─

def test_force_override_still_works(db_path):
    """Świadomy override force=True przepuszcza mutację nawet w walce (bez regresji)."""
    _seed_schema(db_path, combat=True)
    inspector_guard.guard_or_raise(1, force=True)  # nie podnosi wyjątku
