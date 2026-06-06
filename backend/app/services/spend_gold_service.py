"""C12: [SPEND_GOLD:service_key] tag parser + deterministic gold deduction.

parse_spend_gold_tags(text, conn) → [(key, cost_gp), ...]
can_afford_service(conn, character_id, service_key) → bool
spend_gold_on_service(conn, character_id, service_key) → (success, new_gold | None)

Prices come from game_config_services table — never from LLM.
"""
from __future__ import annotations
import re
import sqlite3
from typing import Optional

import structlog

logger = structlog.get_logger()

_RE = re.compile(r'\[SPEND_GOLD:\s*([a-zA-Z0-9_]+)\s*\]')


def _get_service_cost(conn: sqlite3.Connection, service_key: str) -> int | None:
    """Return cost_gp for active service key, or None if not found."""
    row = conn.execute(
        "SELECT cost_gp FROM game_config_services WHERE key = ? AND is_active = 1 LIMIT 1",
        (service_key,),
    ).fetchone()
    if row is None:
        return None
    return int(row["cost_gp"])


def parse_spend_gold_tags(
    text: Optional[str],
    conn: sqlite3.Connection,
) -> list[tuple[str, int]]:
    """Extract [SPEND_GOLD:key] tags from text and resolve cost_gp from DB.

    Unknown / inactive service keys are silently ignored.
    Returns list of (service_key, cost_gp) in order of appearance.
    """
    if not text:
        return []

    result = []
    for m in _RE.finditer(text):
        key = m.group(1).strip()
        cost = _get_service_cost(conn, key)
        if cost is not None:
            result.append((key, cost))
    return result


def can_afford_service(
    conn: sqlite3.Connection,
    character_id: int,
    service_key: str,
) -> bool:
    """Return True if character has enough gold for the service."""
    cost = _get_service_cost(conn, service_key)
    if cost is None:
        return False

    row = conn.execute(
        "SELECT gold_gp FROM characters WHERE id = ? LIMIT 1",
        (character_id,),
    ).fetchone()
    if row is None:
        return False

    return int(row["gold_gp"] or 0) >= cost


def spend_gold_on_service(
    conn: sqlite3.Connection,
    character_id: int,
    service_key: str,
) -> tuple[bool, int | None]:
    """Deduct cost_gp from character.gold_gp if affordable.

    Returns (True, new_gold) on success, (False, None) on failure.
    Does NOT commit — caller owns the transaction.
    """
    cost = _get_service_cost(conn, service_key)
    if cost is None:
        logger.warning("spend_gold_unknown_service", service_key=service_key)
        return False, None

    row = conn.execute(
        "SELECT gold_gp FROM characters WHERE id = ? LIMIT 1",
        (character_id,),
    ).fetchone()
    if row is None:
        return False, None

    current = int(row["gold_gp"] or 0)
    if current < cost:
        logger.info("spend_gold_insufficient", character_id=character_id,
                    service_key=service_key, have=current, need=cost)
        return False, None

    new_gold = current - cost
    conn.execute(
        "UPDATE characters SET gold_gp = ? WHERE id = ?",
        (new_gold, character_id),
    )
    logger.info("spend_gold_success", character_id=character_id,
                service_key=service_key, cost=cost, new_gold=new_gold)
    return True, new_gold
