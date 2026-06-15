"""HI4 (#627): współdzielony guard live-lock + audyt mutacji Inspektora Bohatera.

Jedno źródło logiki dla ścieżek zapisu inspektora, które żyją POZA `admin_cheat`
(equip w `api/inventory.py`, zaklęcia w `routers/admin.py`). `admin_cheat`
deleguje tu swoją funkcję `character_inspector_live_lock`, więc logika blokady
żywego bohatera istnieje w dokładnie jednym miejscu.

Zasada (decyzja Piotra 2026-06-15): każda mutacja bohatera przez inspektora MUSI
pisać audyt do `admin_audit_log` i respektować blokadę live-lock (409 gdy aktywna
walka / tura w toku; `force=True` świadomie omija).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.core.db_runtime import resolve_db_path


def live_lock_by_campaign(
    conn: sqlite3.Connection, campaign_id: int
) -> tuple[bool, str | None]:
    """Czy kampania jest w „żywym" stanie blokującym edycję inspektora.

    Locked gdy kampania ma aktywną walkę (`active_combat status='active'`) LUB turę
    w toku (`game_sessions.session_flags.pending_skill_test`). Brak campaign_id /
    tabel = brak blokady.
    """
    if not campaign_id:
        return (False, None)
    try:
        row = conn.execute(
            "SELECT 1 FROM active_combat WHERE campaign_id = ? AND status = 'active' LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
        if row:
            return (True, "active_combat")
    except sqlite3.OperationalError:
        pass
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
        if row and row[0]:
            flags = json.loads(row[0] or "{}")
            if isinstance(flags, dict) and flags.get("pending_skill_test"):
                return (True, "pending_skill_test")
    except (sqlite3.OperationalError, json.JSONDecodeError, TypeError):
        pass
    return (False, None)


def live_lock_by_character(
    conn: sqlite3.Connection, character_id: int
) -> tuple[bool, str | None]:
    """Jak `live_lock_by_campaign`, ale rozwiązuje kampanię z bohatera."""
    try:
        row = conn.execute(
            "SELECT campaign_id FROM characters WHERE id = ?", (int(character_id),)
        ).fetchone()
    except sqlite3.OperationalError:
        return (False, None)
    campaign_id = int(row[0] or 0) if row and row[0] is not None else 0
    return live_lock_by_campaign(conn, campaign_id)


def guard_or_raise(character_id: int, force: bool = False) -> None:
    """Podnieś 409 `live_locked` gdy bohater w trakcie walki/tury. `force` omija.

    Otwiera własne połączenie (`resolve_db_path`), więc nadaje się do wołania
    z endpointów, które same nie trzymają kursora do game DB.
    """
    if force:
        return
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    try:
        locked, reason = live_lock_by_character(conn, character_id)
    finally:
        conn.close()
    if locked:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=409,
            detail={"reason": "live_locked", "lock_reason": reason},
        )


def write_audit(
    conn: sqlite3.Connection,
    character_id: int,
    operation: str,
    old_values: Any,
    new_values: Any,
) -> None:
    """Wpisz mutację inspektora do `admin_audit_log` na podanym połączeniu."""
    try:
        conn.execute(
            "INSERT INTO admin_audit_log (table_name, row_key, operation, old_values, new_values) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "characters",
                str(character_id),
                operation,
                json.dumps(old_values, ensure_ascii=False),
                json.dumps(new_values, ensure_ascii=False),
            ),
        )
    except sqlite3.OperationalError:
        pass


def audit(character_id: int, operation: str, old_values: Any, new_values: Any) -> None:
    """Jak `write_audit`, ale otwiera i commituje własne połączenie."""
    conn = sqlite3.connect(resolve_db_path())
    try:
        write_audit(conn, character_id, operation, old_values, new_values)
        conn.commit()
    finally:
        conn.close()
