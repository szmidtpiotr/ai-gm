"""#1292 — deterministic services-at-location resolver + purchase, bypassing the LLM.

game_config_services (inn_night, tavern_meal, blacksmith_repair, healer_light, ...) has
no location/NPC association in the data model — it's a flat global price list. And
game_locations.location_subtype is freeform LLM-authored text (145+ distinct values
observed in prod data, no enum), so "which services does this location offer" cannot be
looked up directly. This module infers availability via keyword matching against the
location's label/subtype. Unmatched/unusual locations simply offer nothing — prices
always come from game_config_services (same source the narrator's [SPEND_GOLD] tag
path uses), so a wrong keyword match can under-offer but never mis-price.
"""
from __future__ import annotations

import re
import sqlite3

# Words indicating the player means a SERVICE (nocleg/jedzenie/naprawa/uzdrowienie/
# przewodnik/posłaniec/stajnia), not an unrelated item purchase ("kupuję miecz").
# A generic trade verb (kupuję/zamawiam/proszę o/...) alone is NOT enough to open
# the modal — it must co-occur with one of these, else e.g. "chcę kupić miecz" while
# standing in a tavern would wrongly open Usługi instead of going to the narrator.
SERVICE_NOUN_RE = re.compile(
    r"\b("
    r"nocleg\w*|pok[oó]j\w*|łóżk\w*|lozk\w*|prześpi\w*|przespi\w*|spa[ćc]\w*"
    r"|straw[aęy]\w*|jedzeni\w*|posił\w*|posil\w*|obiad\w*|kolacj\w*|śniadani\w*|sniadani\w*|gulasz\w*"
    r"|piw[aoęy]\w*|kufel\w*|kufl\w*|nap[oó]j\w*|napo\w*|win[aoęy]\w*|trunk\w*"
    r"|napraw\w*|kowal\w*"
    r"|uzdrowi\w*|lecz\w*|ran\w*"
    r"|błogosław\w*|blogoslaw\w*|święc\w*|swiec\w*|odklęc\w*|odklec\w*|odklin\w*|klątw\w*|klatw\w*|kląt\w*"
    r"|stajni\w*|ko[nń]\w*|wierzchowc\w*"
    r"|przewodnik\w*"
    r"|posła[nń]c\w*|poslan\w*|wiadomo[śs][ćc]\w*"
    r")\b",
    re.IGNORECASE,
)

_LODGING_KEYWORDS = ("inn", "tavern", "gospoda", "karczma", "zajazd", "oberza", "oberża")
_LODGING_SERVICES = ("inn_night", "inn_night_fine", "tavern_meal", "tavern_drink")

_SMITH_KEYWORDS = ("smithy", "blacksmith", "kowal", "forge", "kuznia", "kuźnia")
_SMITH_SERVICES = ("blacksmith_repair",)

# Światło shrines: temples/shrines/monasteries offer healing + blessing + curse removal.
# "klasztor"/"kaplica"/"katedra" added (KN-6 #1500) so monastery & cathedral hubs qualify.
_HEALER_KEYWORDS = ("temple", "shrine", "healer", "swiatynia", "świątynia", "uzdrowic",
                    "klinika", "medyk", "klasztor", "kaplica", "katedra", "sanktuarium")
_HEALER_SERVICES = ("healer_light", "healer_heavy", "blessing_light", "curse_removal")

_STABLE_KEYWORDS = ("stable", "stajni", "stajnia")
_STABLE_SERVICES = ("stable_night",)

# Guide/messenger are not tied to one building — offered by any settled/safe place.
_SETTLEMENT_SERVICES = ("guide_day", "messenger")


def get_available_service_keys(conn: sqlite3.Connection, location_key: str | None) -> list[str]:
    """Return service keys (game_config_services) inferred as offered at location_key.

    Order is stable (lodging, smith, healer, stable, settlement-wide) and de-duplicated.
    Empty list on missing/inactive location or no keyword match.
    """
    if not location_key:
        return []
    row = conn.execute(
        "SELECT label, location_subtype, safe_for_rest FROM game_locations "
        "WHERE key = ? AND is_active = 1 LIMIT 1",
        (location_key,),
    ).fetchone()
    if not row:
        return []

    haystack = f"{row['label'] or ''} {row['location_subtype'] or ''}".lower()
    found: list[str] = []

    def _add(keywords: tuple[str, ...], services: tuple[str, ...]) -> None:
        if any(k in haystack for k in keywords):
            for s in services:
                if s not in found:
                    found.append(s)

    _add(_LODGING_KEYWORDS, _LODGING_SERVICES)
    _add(_SMITH_KEYWORDS, _SMITH_SERVICES)
    _add(_HEALER_KEYWORDS, _HEALER_SERVICES)
    _add(_STABLE_KEYWORDS, _STABLE_SERVICES)
    # Lodging locations always have somewhere to stable a mount too.
    if any(k in haystack for k in _LODGING_KEYWORDS) and "stable_night" not in found:
        found.append("stable_night")
    # Any place safe enough to rest counts as "civilised" for travel services.
    if bool(row["safe_for_rest"]) or any(k in haystack for k in _LODGING_KEYWORDS):
        for s in _SETTLEMENT_SERVICES:
            if s not in found:
                found.append(s)

    return found


def get_services_catalog(
    conn: sqlite3.Connection, location_key: str | None, character_id: int
) -> dict:
    """Full payload for the Services modal: available services (with price/label) + gold."""
    keys = get_available_service_keys(conn, location_key)
    items: list[dict] = []
    if keys:
        placeholders = ",".join("?" * len(keys))
        rows = conn.execute(
            f"SELECT key, label, cost_gp, description FROM game_config_services "
            f"WHERE key IN ({placeholders}) AND is_active = 1",
            keys,
        ).fetchall()
        by_key = {r["key"]: r for r in rows}
        # Preserve the resolver's stable ordering, not the SQL result order.
        for k in keys:
            r = by_key.get(k)
            if r:
                items.append({
                    "key": r["key"], "label": r["label"],
                    "cost_gp": int(r["cost_gp"]), "description": r["description"],
                })

    gold_row = conn.execute(
        "SELECT gold_gp FROM characters WHERE id = ? LIMIT 1", (character_id,)
    ).fetchone()
    gold = int(gold_row["gold_gp"] or 0) if gold_row else 0
    return {"location_key": location_key, "items": items, "character_gold": gold}


def buy_service(conn: sqlite3.Connection, character_id: int, service_key: str) -> dict:
    """Deduct cost_gp for service_key. Raises ValueError with a mapped code on failure.

    Purely mechanical — no LLM, no narrative, no turn logged. Uses the same
    game_config_services price + character_gold_log ledger as the narrator-driven
    [SPEND_GOLD] tag path (spend_gold_service.py), so accounting/audit stays unified.
    """
    row = conn.execute(
        "SELECT key, label, cost_gp FROM game_config_services WHERE key = ? AND is_active = 1 LIMIT 1",
        (service_key,),
    ).fetchone()
    if not row:
        raise ValueError("service_not_found")
    cost = int(row["cost_gp"])

    gold_row = conn.execute(
        "SELECT gold_gp FROM characters WHERE id = ? LIMIT 1", (character_id,)
    ).fetchone()
    if not gold_row:
        raise ValueError("character_not_found")
    current = int(gold_row["gold_gp"] or 0)
    if current < cost:
        raise ValueError("insufficient_gold")

    from app.services.economy_service import change_gold
    new_gold = change_gold(
        conn, character_id, -cost, "service",
        meta={"service_key": service_key, "source": "services_modal"},
    )
    conn.commit()
    return {"gold_gp": new_gold, "paid_gp": cost, "label": row["label"], "service_key": service_key}


def buy_services_batch(conn: sqlite3.Connection, character_id: int, service_keys: list[str]) -> dict:
    """Multi-select cart checkout: verify the FULL cart is affordable up front (atomic —
    never charge a partial cart), then deduct each item individually (own ledger row,
    same accounting as buy_service). Raises ValueError on any missing key or
    insufficient total gold — no state changed in either case.
    """
    if not service_keys:
        raise ValueError("empty_cart")

    placeholders = ",".join("?" * len(service_keys))
    rows = conn.execute(
        f"SELECT key, label, cost_gp FROM game_config_services "
        f"WHERE key IN ({placeholders}) AND is_active = 1",
        service_keys,
    ).fetchall()
    by_key = {r["key"]: r for r in rows}
    missing = [k for k in service_keys if k not in by_key]
    if missing:
        raise ValueError("service_not_found")

    total_cost = sum(int(by_key[k]["cost_gp"]) for k in service_keys)

    gold_row = conn.execute(
        "SELECT gold_gp FROM characters WHERE id = ? LIMIT 1", (character_id,)
    ).fetchone()
    if not gold_row:
        raise ValueError("character_not_found")
    if int(gold_row["gold_gp"] or 0) < total_cost:
        raise ValueError("insufficient_gold")

    from app.services.economy_service import change_gold
    items: list[dict] = []
    new_gold = int(gold_row["gold_gp"] or 0)
    for k in service_keys:
        row = by_key[k]
        cost = int(row["cost_gp"])
        new_gold = change_gold(
            conn, character_id, -cost, "service",
            meta={"service_key": k, "source": "services_modal_batch"},
        )
        items.append({"key": k, "label": row["label"], "cost_gp": cost})
    conn.commit()
    return {"items": items, "total_paid_gp": total_cost, "gold_gp": new_gold}
