"""Phase 9A-4 — NPC shop service (buy/sell/rent/trade-in)."""

from __future__ import annotations

import json
import math
import sqlite3
from typing import Any

from app.services.dice import parse_character_sheet
from app.services.loot_service import (
    LOOT_DB_PATH,
    apply_character_gold_delta,
    get_character_gold,
    grant_loot_to_character,
)

SELL_RATIO = 0.5
RENTAL_FEE_RATIO = 0.10  # 10% of item value per turn


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
        try:
            row = conn.execute(
                """
                SELECT key, label, description, COALESCE(value_gp, 0) AS price_gp, item_type
                FROM game_config_items
                WHERE key = ? AND COALESCE(is_active, 1) = 1
                LIMIT 1
                """,
                (k,),
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
        if row and str(row["item_type"] or "").strip().lower() == "consumable":
            return {
                "type": "consumable",
                "key": row["key"],
                "label": row["label"] or row["key"],
                "description": row["description"] or "",
                "value_gp": int(row["price_gp"] or 0),
            }
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
    try:
        row = conn.execute(
            """
            SELECT key, label, description, COALESCE(value_gp, 0) AS price_gp, item_type
            FROM game_config_items
            WHERE key = ? AND COALESCE(is_active, 1) = 1
            """,
            (k,),
        ).fetchone()
        item_type_from_row = str(row["item_type"] or "").strip().lower() if row else ""
    except sqlite3.OperationalError:
        row = conn.execute(
            """
            SELECT key, label, description, COALESCE(value_gp, 0) AS price_gp
            FROM game_config_items
            WHERE key = ? AND COALESCE(is_active, 1) = 1
            """,
            (k,),
        ).fetchone()
        item_type_from_row = ""
    if not row:
        return None
    return {
        "type": (item_type_from_row or t or "item"),
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


def _get_character_cha(conn: sqlite3.Connection, character_id: int) -> int:
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1",
            (int(character_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        # Backward compatibility for lightweight/test DBs without sheet_json column.
        return 10
    if not row:
        return 10
    try:
        sheet = parse_character_sheet(row["sheet_json"] if isinstance(row, sqlite3.Row) else row[0])
        stats = sheet.get("stats", {}) if isinstance(sheet, dict) else {}
        return int(stats.get("CHA", 10))
    except Exception:
        return 10


def _cha_sell_ratio(cha: int) -> float:
    ratio = SELL_RATIO + (int(cha) - 10) * 0.02
    return round(max(0.10, min(0.70, ratio)), 4)


def _character_sellables(
    conn: sqlite3.Connection, character_id: int, ratio: float
) -> list[dict[str, Any]]:
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
        effective_type = str(cat.get("type") or item_type)
        out.append(
            {
                "inventory_id": int(row["id"]),
                "item_type": effective_type,
                "key": item_key,
                "label": cat["label"],
                "quantity": int(row["quantity"] or 1),
                "value_gp": int(cat["value_gp"] or 0),
                "sell_price_gp": (
                    max(1, int(math.floor(int(cat["value_gp"] or 0) * ratio)))
                    if int(cat["value_gp"] or 0) > 0
                    else 0
                ),
                "source": row["source"] or "",
            }
        )
    return out


def _get_character_campaign_id(conn: sqlite3.Connection, character_id: int) -> int | None:
    row = conn.execute(
        "SELECT campaign_id FROM characters WHERE id = ? LIMIT 1",
        (int(character_id),),
    ).fetchone()
    return int(row["campaign_id"]) if row and row["campaign_id"] else None


def _get_campaign_current_turn(conn: sqlite3.Connection, campaign_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(turn_number), 0) AS t FROM campaign_turns WHERE campaign_id = ?",
        (int(campaign_id),),
    ).fetchone()
    return int(row["t"]) if row else 0


def _expire_stale_rentals(conn: sqlite3.Connection, character_id: int, npc_id: int, current_turn: int) -> int:
    """Remove items for expired rentals. Returns count of expired rows."""
    expired = conn.execute(
        """
        SELECT id, inventory_id FROM character_rentals
        WHERE character_id = ? AND npc_id = ? AND status = 'active' AND expires_at_turn <= ?
        """,
        (int(character_id), int(npc_id), current_turn),
    ).fetchall()
    for row in expired:
        if row["inventory_id"]:
            conn.execute(
                "DELETE FROM character_inventory WHERE id = ? AND character_id = ?",
                (int(row["inventory_id"]), int(character_id)),
            )
        conn.execute(
            "UPDATE character_rentals SET status = 'expired', updated_at = datetime('now') WHERE id = ?",
            (int(row["id"]),),
        )
    if expired:
        conn.commit()
    return len(expired)


def get_shop_inventory(npc_id: int, character_id: int) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc(conn, npc_id)
        cha = _get_character_cha(conn, character_id)
        ratio = _cha_sell_ratio(cha)
        entries = _parse_shop_inventory(str(npc["shop_inventory_json"] or "[]"))

        campaign_id = _get_character_campaign_id(conn, character_id)
        current_turn = _get_campaign_current_turn(conn, campaign_id) if campaign_id else 0

        # Lazy expiry: clear overdue rentals when player visits shop
        _expire_stale_rentals(conn, character_id, int(npc["id"]), current_turn)

        items = []
        for e in entries:
            cat = _catalog_item(conn, e["type"], e["key"])
            if cat and int(cat.get("value_gp") or 0) > 0:
                rental_fee = max(1, int(math.floor(int(cat["value_gp"]) * RENTAL_FEE_RATIO)))
                items.append({**cat, "rental_fee_gp": rental_fee})

        sell_items = _character_sellables(conn, character_id, ratio)

        active_rentals = conn.execute(
            """
            SELECT id, item_type, item_key, label, rental_fee_gp, total_paid_gp,
                   duration_turns, rented_at_turn, expires_at_turn, status
            FROM character_rentals
            WHERE character_id = ? AND npc_id = ? AND status = 'active'
            ORDER BY expires_at_turn ASC
            """,
            (int(character_id), int(npc["id"])),
        ).fetchall()

    return {
        "npc": {"id": int(npc["id"]), "key": npc["key"], "label": npc["label"]},
        "items": items,
        "sell_items": sell_items,
        "active_rentals": [
            {**dict(r), "turns_remaining": max(0, int(r["expires_at_turn"]) - current_turn)}
            for r in active_rentals
        ],
        "character_gold": int(get_character_gold(character_id)),
        "sell_ratio": ratio,
        "cha": cha,
        "rental_fee_ratio": RENTAL_FEE_RATIO,
    }


def get_shop_inventory_by_key(npc_key: str, character_id: int) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc_by_key(conn, npc_key)
    return get_shop_inventory(int(npc["id"]), character_id)


def buy_item(
    character_id: int,
    npc_id: int,
    item_type: str,
    item_key: str,
    trade_in_inventory_id: int | None = None,
) -> dict[str, Any]:
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

        # Trade-in: validate and calculate discount
        trade_in_info: dict[str, Any] | None = None
        trade_discount = 0
        if trade_in_inventory_id is not None:
            ti_row = conn.execute(
                """
                SELECT id, item_key, weapon_key, consumable_key
                FROM character_inventory
                WHERE id = ? AND character_id = ?
                LIMIT 1
                """,
                (int(trade_in_inventory_id), int(character_id)),
            ).fetchone()
            if not ti_row:
                raise ValueError("trade_in_not_found")
            ti_type = ""
            ti_key = ""
            if ti_row["weapon_key"]:
                ti_type = "weapon"
                ti_key = str(ti_row["weapon_key"])
            elif ti_row["consumable_key"]:
                ti_type = "consumable"
                ti_key = str(ti_row["consumable_key"])
            elif ti_row["item_key"]:
                ti_type = "item"
                ti_key = str(ti_row["item_key"])
            if not ti_type or not ti_key:
                raise ValueError("trade_in_not_sellable")
            ti_cat = _catalog_item(conn, ti_type, ti_key)
            if ti_cat:
                cha = _get_character_cha(conn, character_id)
                ratio = _cha_sell_ratio(cha)
                ti_base = int(ti_cat["value_gp"] or 0)
                trade_discount = max(1, int(math.floor(ti_base * ratio))) if ti_base > 0 else 0
                trade_in_info = {
                    "inventory_id": int(ti_row["id"]),
                    "type": str(ti_cat.get("type") or ti_type),
                    "key": ti_key,
                    "label": ti_cat["label"],
                    "value_gp": ti_base,
                    "discount_gp": trade_discount,
                }

    effective_price = max(0, price - trade_discount)

    cur_gold = int(get_character_gold(character_id))
    if cur_gold < effective_price:
        raise ValueError("insufficient_gold")

    # Remove trade-in item before paying (trade-in submitted = item leaves inventory)
    if trade_in_info:
        with _conn() as conn2:
            conn2.execute(
                "DELETE FROM character_inventory WHERE id = ? AND character_id = ?",
                (trade_in_info["inventory_id"], int(character_id)),
            )
            conn2.commit()

    new_gold = apply_character_gold_delta(character_id, -effective_price, "shop_purchase")
    t = str(item_type).strip().lower()
    if t == "weapon":
        loot_payload: dict[str, Any] = {"weapon_key": str(item_key).strip(), "quantity": 1}
    else:
        loot_payload = {"item_key": str(item_key).strip(), "quantity": 1}

    try:
        grant_loot_to_character(character_id, [loot_payload], source="purchase")
    except Exception:
        apply_character_gold_delta(character_id, effective_price, "shop_purchase_refund")
        raise

    # Reputation tracking
    try:
        from app.services.npc_memory_service import increment_npc_purchase_count
        with _conn() as rep_conn:
            char_row = rep_conn.execute(
                "SELECT campaign_id FROM characters WHERE id = ? LIMIT 1",
                (int(character_id),),
            ).fetchone()
            if char_row and char_row["campaign_id"]:
                increment_npc_purchase_count(
                    campaign_id=int(char_row["campaign_id"]),
                    npc_id=int(npc_id),
                    npc_name=str(npc["label"]) if npc["label"] else None,
                )
    except Exception:
        pass  # Non-critical; never fail a purchase over reputation tracking

    result: dict[str, Any] = {
        "gold_gp": int(new_gold),
        "price_paid_gp": effective_price,
        "item": {
            "type": cat["type"],
            "key": cat["key"],
            "label": cat["label"],
            "value_gp": int(cat["value_gp"] or 0),
        },
    }
    if trade_in_info:
        result["trade_in"] = {
            "type": trade_in_info["type"],
            "key": trade_in_info["key"],
            "label": trade_in_info["label"],
            "discount_gp": trade_discount,
        }
    return result


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
        item_type = str(cat.get("type") or item_type)

        base_price = int(cat["value_gp"] or 0)
        cha = _get_character_cha(conn, character_id)
        ratio = _cha_sell_ratio(cha)
        earned = max(1, int(math.floor(base_price * ratio))) if base_price > 0 else 0

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
        "sell_ratio": ratio,
        "cha": int(cha),
        "sold_item": {
            "type": item_type,
            "key": item_key,
            "label": cat["label"],
        },
    }


def rent_item(
    character_id: int,
    npc_id: int,
    item_type: str,
    item_key: str,
    duration_turns: int,
) -> dict[str, Any]:
    if int(duration_turns) < 1:
        raise ValueError("invalid_duration")

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
        if not cat or int(cat["value_gp"] or 0) <= 0:
            raise ValueError("price_or_catalog_missing")

        campaign_id = _get_character_campaign_id(conn, character_id)
        current_turn = _get_campaign_current_turn(conn, campaign_id) if campaign_id else 0

    rental_fee = max(1, int(math.floor(int(cat["value_gp"]) * RENTAL_FEE_RATIO)))
    total_cost = rental_fee * int(duration_turns)
    expires_at_turn = current_turn + int(duration_turns)

    cur_gold = int(get_character_gold(character_id))
    if cur_gold < total_cost:
        raise ValueError("insufficient_gold")

    new_gold = apply_character_gold_delta(character_id, -total_cost, "shop_rental")

    t = str(item_type).strip().lower()
    loot_payload: dict[str, Any]
    if t == "weapon":
        loot_payload = {"weapon_key": str(item_key).strip(), "quantity": 1}
    else:
        loot_payload = {"item_key": str(item_key).strip(), "quantity": 1}

    inventory_id: int | None = None
    try:
        grant_loot_to_character(character_id, [loot_payload], source="rental")
        # Retrieve inventory_id of the just-granted item to track it for expiry removal
        with _conn() as conn2:
            if t == "weapon":
                inv_row = conn2.execute(
                    "SELECT id FROM character_inventory WHERE character_id = ? AND weapon_key = ? ORDER BY id DESC LIMIT 1",
                    (int(character_id), str(item_key).strip()),
                ).fetchone()
            else:
                inv_row = conn2.execute(
                    "SELECT id FROM character_inventory WHERE character_id = ? AND item_key = ? ORDER BY id DESC LIMIT 1",
                    (int(character_id), str(item_key).strip()),
                ).fetchone()
            inventory_id = int(inv_row["id"]) if inv_row else None
    except Exception:
        apply_character_gold_delta(character_id, total_cost, "shop_rental_refund")
        raise

    with _conn() as conn3:
        cur = conn3.execute(
            """
            INSERT INTO character_rentals
                (character_id, campaign_id, npc_id, item_type, item_key, label,
                 rental_fee_gp, total_paid_gp, duration_turns,
                 rented_at_turn, expires_at_turn, inventory_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(character_id),
                campaign_id,
                int(npc_id),
                str(item_type).strip().lower(),
                str(item_key).strip(),
                cat["label"],
                rental_fee,
                total_cost,
                int(duration_turns),
                current_turn,
                expires_at_turn,
                inventory_id,
            ),
        )
        conn3.commit()
        rental_id = cur.lastrowid

    return {
        "rental_id": rental_id,
        "gold_gp": int(new_gold),
        "rental_fee_gp": rental_fee,
        "total_paid_gp": total_cost,
        "duration_turns": int(duration_turns),
        "rented_at_turn": current_turn,
        "expires_at_turn": expires_at_turn,
        "item": {
            "type": cat["type"],
            "key": cat["key"],
            "label": cat["label"],
            "value_gp": int(cat["value_gp"] or 0),
        },
    }


def return_rental(character_id: int, rental_id: int) -> dict[str, Any]:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, item_type, item_key, label, inventory_id, status
            FROM character_rentals
            WHERE id = ? AND character_id = ?
            LIMIT 1
            """,
            (int(rental_id), int(character_id)),
        ).fetchone()
        if not row:
            raise ValueError("rental_not_found")
        if str(row["status"]) != "active":
            raise ValueError("rental_not_active")

        if row["inventory_id"]:
            conn.execute(
                "DELETE FROM character_inventory WHERE id = ? AND character_id = ?",
                (int(row["inventory_id"]), int(character_id)),
            )
        conn.execute(
            "UPDATE character_rentals SET status = 'returned', updated_at = datetime('now') WHERE id = ?",
            (int(row["id"]),),
        )
        conn.commit()

    return {
        "ok": True,
        "returned_item": {
            "type": str(row["item_type"]),
            "key": str(row["item_key"]),
            "label": str(row["label"] or row["item_key"]),
        },
    }
