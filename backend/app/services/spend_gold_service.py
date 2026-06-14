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

    # U26: mutate + journal through the central chokepoint (caller owns commit).
    from app.services.economy_service import change_gold
    new_gold = change_gold(
        conn, character_id, -cost, "service", meta={"service_key": service_key},
    )
    logger.info("spend_gold_success", character_id=character_id,
                service_key=service_key, cost=cost, new_gold=new_gold)
    return True, new_gold


def build_refusal_text(
    conn: sqlite3.Connection,
    character_id: int,
    service_key: str,
) -> str:
    """Return a Polish refusal string when character cannot afford service_key.

    Empty string if service_key is unknown (nothing to refuse).
    """
    cost = _get_service_cost(conn, service_key)
    if cost is None:
        return ""

    row = conn.execute(
        "SELECT gold_gp FROM characters WHERE id = ? LIMIT 1",
        (character_id,),
    ).fetchone()
    current = int(row["gold_gp"] or 0) if row else 0

    return (
        f"*(Nie masz wystarczająco złota — potrzebujesz {cost} zł, "
        f"masz {current} zł. Transakcja nieudana.)*"
    )


def apply_spend_gold_to_narrative(
    text: Optional[str],
    conn: sqlite3.Connection,
    character_id: int,
) -> str:
    """Process all [SPEND_GOLD:key] tags in text.

    For each tag:
    - If character can afford: deduct gold (caller must commit), replace tag with "".
    - If insufficient: replace tag with Polish refusal text.
    - Unknown key: strip tag silently.

    Returns modified text. Does NOT commit the transaction.
    """
    if not text:
        return text or ""

    result = text
    for m in _RE.finditer(text):
        key = m.group(1).strip()
        cost = _get_service_cost(conn, key)
        tag_str = m.group(0)

        if cost is None:
            # Unknown service — strip silently
            result = result.replace(tag_str, "", 1)
            continue

        row = conn.execute(
            "SELECT gold_gp FROM characters WHERE id = ? LIMIT 1",
            (character_id,),
        ).fetchone()
        current = int(row["gold_gp"] or 0) if row else 0

        if current >= cost:
            # U26: mutate + journal through the central chokepoint.
            from app.services.economy_service import change_gold
            new_gold = change_gold(
                conn, character_id, -cost, "service", meta={"service_key": key},
            )
            logger.info("spend_gold_applied", character_id=character_id,
                        service_key=key, cost=cost, new_gold=new_gold)
            result = result.replace(tag_str, "", 1)
        else:
            refusal = build_refusal_text(conn, character_id, key)
            logger.info("spend_gold_insufficient", character_id=character_id,
                        service_key=key, have=current, need=cost)
            result = result.replace(tag_str, refusal, 1)

    return result.strip()
