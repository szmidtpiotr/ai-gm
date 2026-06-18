"""#762 — Rejestr decyzji silnika per tura (turn_decisions).

Helper `record_turn_decision(...)` wpinany na żywej ścieżce narracyjnej. Każdy wpis:
co parser rozpoznał (action_type + confidence), jaką trasą poszło (route), czy gate
zablokował i DLACZEGO, jaki handler odpalił, czy nałożono korektę narracji. Odpowiada
„czemu silnik zrobił X zamiast Y" bez replayu. Żywy następca martwego action_log.
Best-effort: błąd logowania NIGDY nie wywraca tury. Tabela bez FK CASCADE.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

DECISION_LOG_DB_PATH = "/data/ai_gm.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DECISION_LOG_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _as_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps(str(value), ensure_ascii=False)


def record_turn_decision(
    campaign_id: int,
    *,
    character_id: Optional[int] = None,
    turn_number: Optional[float] = None,
    user_text: Optional[str] = None,
    action_type: Optional[str] = None,
    confidence: Optional[float] = None,
    route: Optional[str] = None,
    gate_blocked: Optional[bool] = None,
    gate_reason: Optional[str] = None,
    handler: Optional[str] = None,
    correction_applied: Optional[bool] = None,
    raw_intent: Optional[str] = None,
    meta: Any = None,
    conn: Optional[sqlite3.Connection] = None,
) -> Optional[int]:
    """Zapisz decyzję silnika dla tury. Zwraca id lub None. NIGDY nie rzuca."""
    own_conn = conn is None
    try:
        c = conn or _conn()
        try:
            cur = c.execute(
                """
                INSERT INTO turn_decisions
                    (campaign_id, character_id, turn_number, user_text, action_type,
                     confidence, route, gate_blocked, gate_reason, handler,
                     correction_applied, raw_intent, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(campaign_id),
                    int(character_id) if character_id is not None else None,
                    float(turn_number) if turn_number is not None else None,
                    (str(user_text)[:500] if user_text is not None else None),
                    str(action_type) if action_type is not None else None,
                    float(confidence) if confidence is not None else None,
                    str(route) if route is not None else None,
                    (1 if gate_blocked else 0) if gate_blocked is not None else None,
                    str(gate_reason) if gate_reason is not None else None,
                    str(handler) if handler is not None else None,
                    (1 if correction_applied else 0) if correction_applied is not None else None,
                    str(raw_intent) if raw_intent is not None else None,
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
        logger.warning("turn_decision_record_failed", error=str(e), campaign_id=campaign_id)
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
        "turn_number": row["turn_number"], "user_text": row["user_text"],
        "action_type": row["action_type"], "confidence": row["confidence"], "route": row["route"],
        "gate_blocked": bool(row["gate_blocked"]) if row["gate_blocked"] is not None else None,
        "gate_reason": row["gate_reason"], "handler": row["handler"],
        "correction_applied": bool(row["correction_applied"]) if row["correction_applied"] is not None else None,
        "raw_intent": row["raw_intent"], "meta": meta, "created_at": row["created_at"],
    }


def query_turn_decisions(
    campaign_id: int,
    *,
    from_turn: Optional[float] = None,
    to_turn: Optional[float] = None,
    limit: int = 100,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict[str, Any]]:
    """Zwróć decyzje silnika kampanii (najnowsze pierwsze), z rozparsowanym meta."""
    own_conn = conn is None
    c = conn or _conn()
    try:
        where = ["campaign_id = ?"]
        params: list[Any] = [int(campaign_id)]
        if from_turn is not None:
            where.append("turn_number >= ?"); params.append(float(from_turn))
        if to_turn is not None:
            where.append("turn_number <= ?"); params.append(float(to_turn))
        lim = max(1, min(int(limit or 100), 1000))
        sql = "SELECT * FROM turn_decisions WHERE " + " AND ".join(where) + " ORDER BY id DESC LIMIT ?"
        params.append(lim)
        return [_row_to_dict(r) for r in c.execute(sql, params).fetchall()]
    except Exception as e:  # noqa: BLE001
        logger.warning("turn_decision_query_failed", error=str(e), campaign_id=campaign_id)
        return []
    finally:
        if own_conn:
            c.close()
