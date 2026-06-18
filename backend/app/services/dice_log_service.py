"""#754 — Strukturalny rejestr rzutów kostką (dice_rolls).

Jeden helper `record_dice_roll(...)` wpinany w KAŻDĄ ścieżkę rzutu (atak gracza/wroga,
unik, blok, test skilla, obrażenia NdX, save, loot, gold). Zapis jest:

  • strukturalny — surowy d20/kości, rozbicie modyfikatorów, DC, outcome, powiązanie z turą;
  • queryowalny — `query_dice_rolls(...)` zwraca dane dla API i narzędzia MCP;
  • odporny — błąd logowania NIGDY nie wywraca rozgrywki (loguj-i-jedź dalej);
  • trwały — tabela `dice_rolls` nie ma FK CASCADE, więc rzuty przeżywają wyjście z lochu
    (lochy kasują kampanię, a rzuty muszą zostać do debugowania post-mortem).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

# Ta sama baza co reszta backendu (bind-mount /data/ai_gm.db w kontenerze).
DICE_LOG_DB_PATH = "/data/ai_gm.db"

# Dozwolone typy rzutu — informacyjne (DB nie wymusza CHECK, żeby nie blokować
# przyszłych typów). Trzymane tu jako kontrakt/dokumentacja.
ROLL_TYPES = {
    "attack_player",
    "attack_enemy",
    "skill_test",
    "dodge",
    "shield_block",
    "damage",
    "save",
    "loot",
    "gold",
}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DICE_LOG_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _as_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps(str(value), ensure_ascii=False)


def record_dice_roll(
    campaign_id: int,
    roll_type: str,
    *,
    character_id: Optional[int] = None,
    turn_number: Optional[float] = None,
    combat_id: Optional[int] = None,
    actor: Optional[str] = None,
    notation: Optional[str] = None,
    raw_rolls: Any = None,
    modifiers: Any = None,
    total: Optional[int] = None,
    dc: Optional[int] = None,
    outcome: Optional[str] = None,
    meta: Any = None,
    conn: Optional[sqlite3.Connection] = None,
) -> Optional[int]:
    """Zapisz pojedynczy rzut do `dice_rolls`. Zwraca id wiersza lub None przy błędzie.

    NIGDY nie podnosi wyjątku w górę — logowanie rzutu nie może zepsuć tury.
    `raw_rolls`/`modifiers`/`meta` są serializowane do JSON automatycznie.
    Jeśli podasz `conn`, użyje go (i NIE zamknie); w przeciwnym razie otwiera własne.
    """
    own_conn = conn is None
    try:
        c = conn or _conn()
        try:
            cur = c.execute(
                """
                INSERT INTO dice_rolls
                    (campaign_id, character_id, turn_number, combat_id, roll_type,
                     actor, notation, raw_rolls, modifiers, total, dc, outcome, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(campaign_id),
                    int(character_id) if character_id is not None else None,
                    float(turn_number) if turn_number is not None else None,
                    int(combat_id) if combat_id is not None else None,
                    str(roll_type),
                    str(actor) if actor is not None else None,
                    str(notation) if notation is not None else None,
                    _as_json(raw_rolls),
                    _as_json(modifiers),
                    int(total) if total is not None else None,
                    int(dc) if dc is not None else None,
                    str(outcome) if outcome is not None else None,
                    _as_json(meta),
                ),
            )
            if own_conn:
                c.commit()
            return int(cur.lastrowid)
        finally:
            if own_conn:
                c.close()
    except Exception as e:  # noqa: BLE001 — logowanie nie może wywrócić tury
        logger.warning(
            "dice_roll_record_failed",
            error=str(e),
            campaign_id=campaign_id,
            roll_type=roll_type,
        )
        return None


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    def _load(val: Any) -> Any:
        if val is None:
            return None
        try:
            return json.loads(val)
        except (TypeError, ValueError):
            return val

    return {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "character_id": row["character_id"],
        "turn_number": row["turn_number"],
        "combat_id": row["combat_id"],
        "roll_type": row["roll_type"],
        "actor": row["actor"],
        "notation": row["notation"],
        "raw_rolls": _load(row["raw_rolls"]),
        "modifiers": _load(row["modifiers"]),
        "total": row["total"],
        "dc": row["dc"],
        "outcome": row["outcome"],
        "meta": _load(row["meta"]),
        "created_at": row["created_at"],
    }


def query_dice_rolls(
    campaign_id: int,
    *,
    roll_type: Optional[str] = None,
    from_turn: Optional[float] = None,
    to_turn: Optional[float] = None,
    limit: int = 100,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict[str, Any]]:
    """Zwróć strukturalne rzuty kampanii (najnowsze pierwsze), z rozparsowanym JSON.

    Filtruje po `roll_type` i zakresie `turn_number` (włącznie). `limit` przycięty do 1..1000.
    """
    own_conn = conn is None
    c = conn or _conn()
    try:
        where = ["campaign_id = ?"]
        params: list[Any] = [int(campaign_id)]
        if roll_type:
            where.append("roll_type = ?")
            params.append(str(roll_type))
        if from_turn is not None:
            where.append("turn_number >= ?")
            params.append(float(from_turn))
        if to_turn is not None:
            where.append("turn_number <= ?")
            params.append(float(to_turn))
        lim = max(1, min(int(limit or 100), 1000))
        sql = (
            "SELECT * FROM dice_rolls WHERE "
            + " AND ".join(where)
            + " ORDER BY id DESC LIMIT ?"
        )
        params.append(lim)
        rows = c.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:  # noqa: BLE001
        logger.warning("dice_roll_query_failed", error=str(e), campaign_id=campaign_id)
        return []
    finally:
        if own_conn:
            c.close()
