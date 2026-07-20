"""#761 — Rejestr zmian zasobów/kondycji gracza (state_changes).

Helper `record_state_change(...)` wpinany tam, gdzie zmienia się HP/mana/kondycja/strefa.
Każdy wpis: before→after + delta + przyczyna + tura. Odpowiada „czemu HP/mana/kondycja
jest teraz X" bez replayu sesji. Best-effort: błąd logowania NIGDY nie wywraca tury.
Tabela bez FK CASCADE — przeżywa wyjście z lochu (jak dice_rolls #754).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

import structlog
from app.core.db_runtime import resolve_db_path

logger = structlog.get_logger(__name__)

STATE_LOG_DB_PATH = resolve_db_path()

RESOURCES = {"hp", "mana", "condition", "zone"}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(STATE_LOG_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _as_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps(str(value), ensure_ascii=False)


def record_state_change(
    campaign_id: int,
    resource: str,
    *,
    character_id: Optional[int] = None,
    turn_number: Optional[float] = None,
    combat_id: Optional[int] = None,
    before_val: Any = None,
    after_val: Any = None,
    delta: Optional[int] = None,
    cause: Optional[str] = None,
    meta: Any = None,
    conn: Optional[sqlite3.Connection] = None,
) -> Optional[int]:
    """Zapisz zmianę zasobu/kondycji. Zwraca id lub None. NIGDY nie rzuca.

    before_val/after_val mogą być liczbą (hp/mana), stringiem (zone) lub kluczem kondycji.
    `delta` liczone automatycznie z before/after gdy oba liczbowe i delta nie podane.
    """
    own_conn = conn is None
    try:
        if delta is None:
            try:
                if before_val is not None and after_val is not None:
                    delta = int(after_val) - int(before_val)
            except (TypeError, ValueError):
                delta = None
        c = conn or _conn()
        try:
            cur = c.execute(
                """
                INSERT INTO state_changes
                    (campaign_id, character_id, turn_number, combat_id, resource,
                     before_val, after_val, delta, cause, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(campaign_id),
                    int(character_id) if character_id is not None else None,
                    float(turn_number) if turn_number is not None else None,
                    int(combat_id) if combat_id is not None else None,
                    str(resource),
                    str(before_val) if before_val is not None else None,
                    str(after_val) if after_val is not None else None,
                    int(delta) if delta is not None else None,
                    str(cause) if cause is not None else None,
                    _as_json(meta),
                ),
            )
            if own_conn:
                c.commit()
            return int(cur.lastrowid)
        finally:
            if own_conn:
                c.close()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "state_change_record_failed", error=str(e),
            campaign_id=campaign_id, resource=resource,
        )
        return None


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    meta = row["meta"]
    if meta is not None:
        try:
            meta = json.loads(meta)
        except (TypeError, ValueError):
            pass
    return {
        "id": row["id"], "campaign_id": row["campaign_id"], "character_id": row["character_id"],
        "turn_number": row["turn_number"], "combat_id": row["combat_id"], "resource": row["resource"],
        "before_val": row["before_val"], "after_val": row["after_val"], "delta": row["delta"],
        "cause": row["cause"], "meta": meta, "created_at": row["created_at"],
    }


def query_state_changes(
    campaign_id: int,
    *,
    resource: Optional[str] = None,
    from_turn: Optional[float] = None,
    to_turn: Optional[float] = None,
    limit: int = 100,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict[str, Any]]:
    """Zwróć zmiany stanu kampanii (najnowsze pierwsze), z rozparsowanym meta."""
    own_conn = conn is None
    c = conn or _conn()
    try:
        where = ["campaign_id = ?"]
        params: list[Any] = [int(campaign_id)]
        if resource:
            where.append("resource = ?"); params.append(str(resource))
        if from_turn is not None:
            where.append("turn_number >= ?"); params.append(float(from_turn))
        if to_turn is not None:
            where.append("turn_number <= ?"); params.append(float(to_turn))
        lim = max(1, min(int(limit or 100), 1000))
        sql = "SELECT * FROM state_changes WHERE " + " AND ".join(where) + " ORDER BY id DESC LIMIT ?"
        params.append(lim)
        return [_row_to_dict(r) for r in c.execute(sql, params).fetchall()]
    except Exception as e:  # noqa: BLE001
        logger.warning("state_change_query_failed", error=str(e), campaign_id=campaign_id)
        return []
    finally:
        if own_conn:
            c.close()
