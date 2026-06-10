"""Phase 9A-4 — NPC shop service (buy/sell)."""

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


def _get_character_level(conn: sqlite3.Connection, character_id: int) -> int:
    """Return character level from sheet_json; defaults to 1."""
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1",
            (int(character_id),),
        ).fetchone()
        if not row:
            return 1
        sheet = parse_character_sheet(row["sheet_json"] if isinstance(row, sqlite3.Row) else row[0])
        return int(sheet.get("level", 1) or 1)
    except Exception:
        return 1


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
            SELECT key, label, description,
                   COALESCE(price_gp, value_gp, 0) AS effective_price,
                   COALESCE(min_level, 1) AS min_level, location_tags
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
            "value_gp": int(row["effective_price"] or 0),
            "min_level": int(row["min_level"] or 1),
            "location_tags": row["location_tags"],
        }

    if t == "consumable":
        try:
            row = conn.execute(
                """
                SELECT key, label, description,
                       COALESCE(price_gp, value_gp, 0) AS effective_price, item_type,
                       COALESCE(min_level, 1) AS min_level, location_tags
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
                "value_gp": int(row["effective_price"] or 0),
                "min_level": int(row["min_level"] or 1),
                "location_tags": row["location_tags"],
            }
        row = conn.execute(
            """
            SELECT key, label, description,
                   COALESCE(price_gp, base_price, 0) AS effective_price,
                   COALESCE(min_level, 1) AS min_level, location_tags
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
            "value_gp": int(row["effective_price"] or 0),
            "min_level": int(row["min_level"] or 1),
            "location_tags": row["location_tags"],
        }

    # item / armor / misc / quest (stored in game_config_items)
    try:
        row = conn.execute(
            """
            SELECT key, label, description,
                   COALESCE(price_gp, value_gp, 0) AS effective_price, item_type,
                   COALESCE(min_level, 1) AS min_level, location_tags
            FROM game_config_items
            WHERE key = ? AND COALESCE(is_active, 1) = 1
            """,
            (k,),
        ).fetchone()
        item_type_from_row = str(row["item_type"] or "").strip().lower() if row else ""
    except sqlite3.OperationalError:
        row = conn.execute(
            """
            SELECT key, label, description, COALESCE(price_gp, value_gp, 0) AS effective_price
            FROM game_config_items
            WHERE key = ? AND COALESCE(is_active, 1) = 1
            """,
            (k,),
        ).fetchone()
        item_type_from_row = ""
    if not row:
        return None
    min_level_val = 1
    location_tags_val = None
    try:
        min_level_val = int(row["min_level"] or 1)
        location_tags_val = row["location_tags"]
    except (IndexError, KeyError):
        pass
    return {
        "type": (item_type_from_row or t or "item"),
        "key": row["key"],
        "label": row["label"] or row["key"],
        "description": row["description"] or "",
        "value_gp": int(row["effective_price"] or 0),
        "min_level": min_level_val,
        "location_tags": location_tags_val,
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


def _cha_buy_multiplier(cha: int) -> float:
    """F10 (#470): buy-price multiplier from CHA, symmetric to sell.

    Formula: 1 - CHA_mod * 0.05, where CHA_mod = (CHA - 10) // 2.
    High CHA → discount (<1.0), low CHA → markup (>1.0).
    Clamped to a 50% floor so prices never drop below half base.
    """
    cha_mod = (int(cha) - 10) // 2
    mult = 1.0 - cha_mod * 0.05
    return round(max(0.5, min(2.0, mult)), 4)


def _buy_price(base_price: int, cha: int) -> int:
    """Apply CHA buy multiplier to a base price; priced items never round to 0."""
    base = int(base_price or 0)
    if base <= 0:
        return base
    return max(1, int(math.floor(base * _cha_buy_multiplier(cha))))


# F11 (#471): tier bonuses for affixed item instances
_AFFIX_TIER_BONUS: dict[int, int] = {1: 25, 2: 75, 3: 200}


def _affix_price_bonus(conn: sqlite3.Connection, affix_keys: list[str]) -> int:
    """Sum of price bonuses for each affix key based on its tier.

    T1 = +25 gp, T2 = +75 gp, T3 = +200 gp. Unknown keys contribute 0.
    """
    if not affix_keys:
        return 0
    total = 0
    for key in affix_keys:
        try:
            row = conn.execute(
                "SELECT tier FROM game_config_affixes WHERE key = ?", (str(key),)
            ).fetchone()
            if row:
                total += _AFFIX_TIER_BONUS.get(int(row[0] or row["tier"] or 0), 0)
        except Exception:
            pass
    return total


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


def _item_passes_filters(cat: dict[str, Any], char_level: int, location_key: str | None) -> bool:
    """Return True if item should be shown given character level and current location."""
    min_level = int(cat.get("min_level") or 1)
    if char_level < min_level:
        return False
    raw_tags = cat.get("location_tags")
    if raw_tags is None:
        # NULL location_tags = available everywhere
        return True
    try:
        tags = json.loads(raw_tags) if isinstance(raw_tags, str) else list(raw_tags)
    except Exception:
        return True
    if not tags:
        return True
    if location_key is None:
        # No location provided → hide location-restricted items
        return False
    return str(location_key).strip().lower() in [str(t).strip().lower() for t in tags]


def get_shop_inventory(npc_id: int, character_id: int, location_key: str | None = None) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc(conn, npc_id)
        cha = _get_character_cha(conn, character_id)
        char_level = _get_character_level(conn, character_id)
        ratio = _cha_sell_ratio(cha)
        entries = _parse_shop_inventory(str(npc["shop_inventory_json"] or "[]"))
        items = []
        for e in entries:
            cat = _catalog_item(conn, e["type"], e["key"])
            if not cat or int(cat.get("value_gp") or 0) <= 0:
                continue
            if not _item_passes_filters(cat, char_level, location_key):
                continue
            cat["buy_price_gp"] = _buy_price(int(cat.get("value_gp") or 0), cha)
            items.append(cat)
        sell_items = _character_sellables(conn, character_id, ratio)
    return {
        "npc": {"id": int(npc["id"]), "key": npc["key"], "label": npc["label"]},
        "items": items,
        "sell_items": sell_items,
        "character_gold": int(get_character_gold(character_id)),
        "sell_ratio": ratio,
        "buy_multiplier": _cha_buy_multiplier(cha),
        "cha": cha,
        "char_level": char_level,
        "location_key": location_key,
    }


def get_shop_inventory_by_key(npc_key: str, character_id: int, location_key: str | None = None) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc_by_key(conn, npc_key)
    return get_shop_inventory(int(npc["id"]), character_id, location_key=location_key)


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
        base_price = int(cat["value_gp"] or 0)
        if base_price <= 0:
            raise ValueError("price_or_catalog_missing")
        # F10 (#470): CHA modifies actual buy price (discount/markup, symmetric to sell).
        cha = _get_character_cha(conn, character_id)
        price = _buy_price(base_price, cha)

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
        "paid_gp": int(price),
        "cha": int(cha),
        "buy_multiplier": _cha_buy_multiplier(cha),
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
        item_type = str(cat.get("type") or item_type)

        base_price = int(cat["value_gp"] or 0)
        cha = _get_character_cha(conn, character_id)
        ratio = _cha_sell_ratio(cha)
        cha_sell_price = max(1, int(math.floor(base_price * ratio))) if base_price > 0 else 0

        # F12 (#472): anti-farm decay for repeated sales of the same item_key
        try:
            from app.services.anti_farm_service import get_anti_farm_multiplier, apply_anti_farm
            af_mult = get_anti_farm_multiplier(conn, character_id, item_key)
            earned = apply_anti_farm(cha_sell_price, af_mult)
        except Exception:
            af_mult = 1.0
            earned = cha_sell_price

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
    # Tag the most recent shop_sell log row with item_key for anti-farm tracking
    try:
        with _conn() as _c:
            _c.execute(
                """UPDATE character_gold_log SET meta_json = ?
                   WHERE character_id = ? AND source = 'shop_sell'
                     AND id = (SELECT MAX(id) FROM character_gold_log
                               WHERE character_id = ? AND source = 'shop_sell')""",
                (json.dumps({"item_key": item_key}), int(character_id), int(character_id)),
            )
            _c.commit()
    except Exception:
        pass
    return {
        "gold_gp": int(new_gold),
        "earned_gp": int(earned),
        "sell_ratio": ratio,
        "anti_farm_multiplier": af_mult,
        "cha": int(cha),
        "sold_item": {
            "type": item_type,
            "key": item_key,
            "label": cat["label"],
        },
    }
