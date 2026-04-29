"""Phase 9A-4 — NPC shop service (buy/sell)."""

from __future__ import annotations

import json
import math
import sqlite3
from typing import Any

from app.services.loot_service import (
    LOOT_DB_PATH,
    apply_character_gold_delta,
    get_character_gold,
    grant_loot_to_character,
)

SELL_RATIO = 0.5


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(LOOT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_shop_npc(conn: sqlite3.Connection, npc_id: int) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT id, key, label, npc_type, is_shop, is_active, shop_inventory_json
        FROM npcs
        WHERE id = ?
        """,
        (int(npc_id),),
    ).fetchone()
    if not row:
        raise ValueError("npc_not_found")
    if int(row["is_active"] or 0) != 1 or int(row["is_shop"] or 0) != 1:
        raise ValueError("npc_not_shop")
    return row


def _load_shop_npc_by_key(conn: sqlite3.Connection, npc_key: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT id, key, label, npc_type, is_shop, is_active, shop_inventory_json
        FROM npcs
        WHERE key = ?
        """,
        (str(npc_key or "").strip(),),
    ).fetchone()
    if not row:
        raise ValueError("npc_not_found")
    if int(row["is_active"] or 0) != 1 or int(row["is_shop"] or 0) != 1:
        raise ValueError("npc_not_shop")
    return row


def _catalog_item(conn: sqlite3.Connection, item_type: str, item_key: str) -> dict[str, Any] | None:
    t = str(item_type or "").strip().lower()
    k = str(item_key or "").strip()
    if not k:
        return None

    if t == "weapon":
        row = conn.execute(
            """
            SELECT key, label, description, COALESCE(value_gp, 0) AS price_gp
            FROM game_config_weapons
            WHERE key = ? AND COALESCE(is_active, 1) = 1
            """,
            (k,),
        ).fetchone()
        if not row:
            return None
        return {
            "type": "weapon",
            "key": row["key"],
            "label": row["label"] or row["key"],
            "description": row["description"] or "",
            "value_gp": int(row["price_gp"] or 0),
        }

    if t == "consumable":
        row = conn.execute(
            """
            SELECT key, label, description, COALESCE(base_price, 0) AS price_gp
            FROM game_config_consumables
            WHERE key = ? AND COALESCE(is_active, 1) = 1
            """,
            (k,),
        ).fetchone()
        if not row:
            return None
        return {
            "type": "consumable",
            "key": row["key"],
            "label": row["label"] or row["key"],
            "description": row["description"] or "",
            "value_gp": int(row["price_gp"] or 0),
        }

    # item / armor / misc / quest (stored in game_config_items)
    row = conn.execute(
        """
        SELECT key, label, description, COALESCE(value_gp, 0) AS price_gp
        FROM game_config_items
        WHERE key = ? AND COALESCE(is_active, 1) = 1
        """,
        (k,),
    ).fetchone()
    if not row:
        return None
    return {
        "type": t or "item",
        "key": row["key"],
        "label": row["label"] or row["key"],
        "description": row["description"] or "",
        "value_gp": int(row["price_gp"] or 0),
    }


def _parse_shop_inventory(raw_json: str) -> list[dict[str, str]]:
    try:
        parsed = json.loads(raw_json or "[]")
    except Exception:
        parsed = []
    out: list[dict[str, str]] = []
    if not isinstance(parsed, list):
        return out
    for e in parsed:
        if not isinstance(e, dict):
            continue
        t = str(e.get("type") or "").strip().lower()
        k = str(e.get("key") or "").strip()
        if not t or not k:
            continue
        out.append({"type": t, "key": k})
    return out


def _character_sellables(conn: sqlite3.Connection, character_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, item_key, weapon_key, consumable_key, quantity, source
        FROM character_inventory
        WHERE character_id = ?
        ORDER BY id ASC
        """,
        (int(character_id),),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item_type = ""
        item_key = ""
        if row["weapon_key"]:
            item_type = "weapon"
            item_key = str(row["weapon_key"])
        elif row["consumable_key"]:
            item_type = "consumable"
            item_key = str(row["consumable_key"])
        elif row["item_key"]:
            item_type = "item"
            item_key = str(row["item_key"])
        if not item_type or not item_key:
            continue
        cat = _catalog_item(conn, item_type, item_key)
        if not cat:
            continue
        out.append(
            {
                "inventory_id": int(row["id"]),
                "item_type": item_type,
                "key": item_key,
                "label": cat["label"],
                "quantity": int(row["quantity"] or 1),
                "value_gp": int(cat["value_gp"] or 0),
                "sell_price_gp": int(math.floor(int(cat["value_gp"] or 0) * SELL_RATIO)),
                "source": row["source"] or "",
            }
        )
    return out


def get_shop_inventory(npc_id: int, character_id: int) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc(conn, npc_id)
        entries = _parse_shop_inventory(str(npc["shop_inventory_json"] or "[]"))
        items = []
        for e in entries:
            cat = _catalog_item(conn, e["type"], e["key"])
            if cat:
                items.append(cat)
        sell_items = _character_sellables(conn, character_id)
    return {
        "npc": {"id": int(npc["id"]), "key": npc["key"], "label": npc["label"]},
        "items": items,
        "sell_items": sell_items,
        "character_gold": int(get_character_gold(character_id)),
    }


def get_shop_inventory_by_key(npc_key: str, character_id: int) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc_by_key(conn, npc_key)
    return get_shop_inventory(int(npc["id"]), character_id)


def buy_item(character_id: int, npc_id: int, item_type: str, item_key: str) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc(conn, npc_id)
        entries = _parse_shop_inventory(str(npc["shop_inventory_json"] or "[]"))
        allowed = any(
            e["type"] == str(item_type).strip().lower() and e["key"] == str(item_key).strip()
            for e in entries
        )
        if not allowed:
            raise ValueError("item_not_in_shop")
        cat = _catalog_item(conn, item_type, item_key)
        if not cat:
            raise ValueError("price_or_catalog_missing")
        price = int(cat["value_gp"] or 0)
        if price <= 0:
            raise ValueError("price_or_catalog_missing")

    # Validate gold first for cleaner error mapping.
    cur_gold = int(get_character_gold(character_id))
    if cur_gold < price:
        raise ValueError("insufficient_gold")

    # Use existing economy and loot services.
    new_gold = apply_character_gold_delta(character_id, -price, "shop_purchase")
    loot_payload: dict[str, Any]
    t = str(item_type).strip().lower()
    if t == "weapon":
        loot_payload = {"weapon_key": str(item_key).strip(), "quantity": 1}
    elif t == "consumable":
        loot_payload = {"consumable_key": str(item_key).strip(), "quantity": 1}
    else:
        loot_payload = {"item_key": str(item_key).strip(), "quantity": 1}

    try:
        grant_loot_to_character(character_id, [loot_payload], source="purchase")
    except Exception:
        # Best effort rollback of deducted gold.
        apply_character_gold_delta(character_id, price, "shop_purchase_refund")
        raise

    return {
        "gold_gp": int(new_gold),
        "item": {
            "type": cat["type"],
            "key": cat["key"],
            "label": cat["label"],
            "value_gp": int(cat["value_gp"] or 0),
        },
    }


def sell_item(character_id: int, inventory_id: int) -> dict[str, Any]:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, character_id, item_key, weapon_key, consumable_key, quantity
            FROM character_inventory
            WHERE id = ? AND character_id = ?
            LIMIT 1
            """,
            (int(inventory_id), int(character_id)),
        ).fetchone()
        if not row:
            raise ValueError("inventory_not_found")

        item_type = ""
        item_key = ""
        if row["weapon_key"]:
            item_type = "weapon"
            item_key = str(row["weapon_key"])
        elif row["consumable_key"]:
            item_type = "consumable"
            item_key = str(row["consumable_key"])
        elif row["item_key"]:
            item_type = "item"
            item_key = str(row["item_key"])
        if not item_type or not item_key:
            raise ValueError("inventory_not_sellable")

        cat = _catalog_item(conn, item_type, item_key)
        if not cat:
            raise ValueError("price_or_catalog_missing")

        base_price = int(cat["value_gp"] or 0)
        earned = int(math.floor(base_price * SELL_RATIO))
        if earned < 0:
            earned = 0

        qty = int(row["quantity"] or 1)
        if qty > 1:
            conn.execute(
                "UPDATE character_inventory SET quantity = ? WHERE id = ?",
                (qty - 1, int(row["id"])),
            )
        else:
            conn.execute("DELETE FROM character_inventory WHERE id = ?", (int(row["id"]),))
        conn.commit()

    new_gold = apply_character_gold_delta(character_id, earned, "shop_sell")
    return {
        "gold_gp": int(new_gold),
        "earned_gp": int(earned),
        "sold_item": {
            "type": item_type,
            "key": item_key,
            "label": cat["label"],
        },
    }
