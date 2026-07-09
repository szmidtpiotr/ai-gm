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


def _get_service_label(conn: sqlite3.Connection, service_key: str) -> str:
    """Return human label for a service key, or the key itself if unavailable."""
    try:
        row = conn.execute(
            "SELECT label FROM game_config_services WHERE key = ? AND is_active = 1 LIMIT 1",
            (service_key,),
        ).fetchone()
    except Exception:
        return service_key
    if row is None or row["label"] is None:
        return service_key
    return str(row["label"])


def apply_spend_gold_to_narrative(
    text: Optional[str],
    conn: sqlite3.Connection,
    character_id: int,
    collect_events: Optional[list] = None,
) -> str:
    """Process all [SPEND_GOLD:key] tags in text.

    For each tag:
    - If character can afford: deduct gold (caller must commit), replace tag with "".
    - If insufficient: replace tag with Polish refusal text.
    - Unknown key: strip tag silently.

    #1101: if `collect_events` is a list, append one visible record per SUCCESSFUL
    charge — {delta, label, source, service_key} — so the turn pipeline can surface
    a 💰 bubble in chat. Refusals/unknown keys add nothing (no money moved).

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
            if collect_events is not None:
                collect_events.append({
                    "delta": -cost,
                    "label": _get_service_label(conn, key),
                    "source": "service",
                    "service_key": key,
                })
            result = result.replace(tag_str, "", 1)
        else:
            refusal = build_refusal_text(conn, character_id, key)
            logger.info("spend_gold_insufficient", character_id=character_id,
                        service_key=key, have=current, need=cost)
            result = result.replace(tag_str, refusal, 1)

    return result.strip()


# ── #1292: food/drink purchase safety-net ────────────────────────────────────
# The narrator is meant to emit [SPEND_GOLD:tavern_meal|tavern_drink] when the
# hero buys food/drink in a tavern (system_prompt rule), but it frequently forgets
# — the meal is served free and no 💰 bubble appears. This deterministic net
# mirrors skill_check_safety_net: on an *explicit* purchase phrase, when the hero
# can afford it and the narrator did NOT already charge this turn, deduct the price.

# Explicit purchase verbs (imperative / present — avoids subjunctive "chciałbym").
_FOOD_ORDER_VERB_RE = re.compile(
    r"\b(zamawiam|zamówi[ćeęą]\w*|kupuj[ęe]|kupi[ćeęą]\w*|płac[ęe]|zapłac\w*|"
    r"proszę o|biorę|bierz[ee])\b",
    re.IGNORECASE,
)
_FOOD_NOUN_RE = re.compile(
    r"\b(straw[aęy]\w*|jedzeni\w*|posił\w*|obiad\w*|kolacj\w*|śniadani\w*|"
    r"gulasz\w*|zup[aęy]\w*|chleb\w*|miski\w*|miskę)\b",
    re.IGNORECASE,
)
_DRINK_NOUN_RE = re.compile(
    r"\b(piw[aoęy]\w*|kufel\w*|kufl\w*|napój\w*|napoj\w*|wina?\b|winem|"
    r"miód\w*|miod\w*|gorzał\w*|trunk\w*|kielisz\w*)\b",
    re.IGNORECASE,
)


def food_purchase_safety_net(
    player_text: Optional[str],
    conn: sqlite3.Connection,
    character_id: int,
    already_charged: bool,
    collect_events: Optional[list] = None,
) -> bool:
    """Auto-charge a tavern meal/drink the narrator forgot to bill.

    Fires only when ALL hold:
      • the narrator did NOT already emit a SPEND_GOLD charge this turn,
      • the player text has an explicit purchase verb + a food/drink noun,
      • the hero can afford the resolved service (tavern_meal if any food noun,
        else tavern_drink).

    Returns True when a charge was applied (caller must commit). Appends a gold_event
    to `collect_events` for the 💰 bubble. Never raises — a miss just returns False.
    """
    if already_charged or not player_text:
        return False
    try:
        if not _FOOD_ORDER_VERB_RE.search(player_text):
            return False
        has_food = bool(_FOOD_NOUN_RE.search(player_text))
        has_drink = bool(_DRINK_NOUN_RE.search(player_text))
        if not (has_food or has_drink):
            return False
        # Food (with or without drink) → meal; drink only → drink.
        key = "tavern_meal" if has_food else "tavern_drink"
        cost = _get_service_cost(conn, key)
        if cost is None:
            return False
        row = conn.execute(
            "SELECT gold_gp FROM characters WHERE id = ? LIMIT 1", (character_id,)
        ).fetchone()
        if not row or int(row["gold_gp"] or 0) < cost:
            return False  # can't afford → leave to narrator, no forced refusal
        from app.services.economy_service import change_gold
        new_gold = change_gold(
            conn, character_id, -cost, "service",
            meta={"service_key": key, "source": "food_safety_net"},
        )
        logger.info("food_purchase_safety_net_charged", character_id=character_id,
                    service_key=key, cost=cost, new_gold=new_gold)
        if collect_events is not None:
            collect_events.append({
                "delta": -cost,
                "label": _get_service_label(conn, key),
                "source": "service",
                "service_key": key,
            })
        return True
    except Exception as exc:
        logger.warning("food_purchase_safety_net_error", error=str(exc))
        return False
