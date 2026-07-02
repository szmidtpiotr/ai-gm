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
from app.services import haggle_service

SELL_RATIO = 0.5

# #973 R4: Kowalskie oko — krasnolud discount (STARTING value, tunable via Sandbox)
DWARF_SHOP_DISCOUNT = 0.15
DWARF_REPAIR_COST_GP = 20  # złoto za akcję Reperuj (startowo)

# Type aliases: catalog may return sub-types that map to canonical stored types.
# "gear" appears in game_config_items.item_type and is returned by catalog for
# general equipment (torch, rope, etc.), but shop_inventory_json stores them as "item".
_ITEM_TYPE_ALIASES: dict[str, str] = {"gear": "item"}


def _norm_item_type(t: str) -> str:
    """Canonical form of item_type for comparison (e.g. 'gear' → 'item')."""
    return _ITEM_TYPE_ALIASES.get(str(t or "").strip().lower(), str(t or "").strip().lower())


def _campaign_id_for_character(conn: sqlite3.Connection, character_id: int) -> int | None:
    """S6: bohater wie, w jakiej kampanii gra → tam żyją session_flags z rabatem."""
    try:
        row = conn.execute(
            "SELECT campaign_id FROM characters WHERE id = ? LIMIT 1",
            (int(character_id),),
        ).fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except sqlite3.OperationalError:
        pass
    return None


def _load_session_flags(conn: sqlite3.Connection, campaign_id: int) -> dict:
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
        if row and row[0]:
            return json.loads(row[0])
    except (sqlite3.OperationalError, ValueError, TypeError):
        pass
    return {}


def _save_session_flags(conn: sqlite3.Connection, campaign_id: int, flags: dict) -> None:
    try:
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(flags, ensure_ascii=False), int(campaign_id)),
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass


def _peek_haggle_for_character(conn: sqlite3.Connection, character_id: int) -> float:
    """Podgląd rabatu z targowania BEZ konsumpcji (dla wyświetlanych cen)."""
    cid = _campaign_id_for_character(conn, character_id)
    if cid is None:
        return 0.0
    return haggle_service.peek_haggle_discount(_load_session_flags(conn, cid))


def _consume_haggle_for_character(conn: sqlite3.Connection, character_id: int) -> float:
    """Pobierz rabat z targowania i wyczyść go (jednorazowy — ta transakcja)."""
    cid = _campaign_id_for_character(conn, character_id)
    if cid is None:
        return 0.0
    flags = _load_session_flags(conn, cid)
    discount = haggle_service.consume_haggle_discount(flags)
    if discount:
        _save_session_flags(conn, cid, flags)
    return discount


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
        SELECT id, key, label, npc_type, is_shop, is_active, is_crafter, shop_inventory_json
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
        SELECT id, key, label, npc_type, is_shop, is_active, is_crafter, shop_inventory_json
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
    """U11b (#557): czyta z game_items zamiast starych tabel.

    item_type ('weapon'/'consumable'/'item'/'armor') używany jako hint — szukamy po kluczu.
    """
    t = str(item_type or "").strip().lower()
    k = str(item_key or "").strip()
    if not k:
        return None

    # Mapowanie item_type → kind w game_items
    _KIND_MAP = {
        "weapon": "weapon",
        "consumable": "consumable",
        "armor": "armor",
        "item": "item",
    }
    kind_hint = _KIND_MAP.get(t)

    row = conn.execute(
        """
        SELECT key, label, description,
               COALESCE(price_gp, 0) AS effective_price,
               COALESCE(min_level, 1) AS min_level,
               location_tags, kind,
               json_extract(item_data, '$.item_type') AS item_type_raw
        FROM game_items
        WHERE key = ? AND is_active = 1
        """,
        (k,),
    ).fetchone()

    if row:
        kind = str(row["kind"] or t or "item")
        item_type_raw = str(row["item_type_raw"] or kind or "item")
        resolved_type = kind if kind in ("weapon", "consumable", "armor") else (item_type_raw or t or "item")
        return {
            "type": resolved_type,
            "key": row["key"],
            "label": row["label"] or row["key"],
            "description": row["description"] or "",
            "value_gp": int(row["effective_price"] or 0),
            "min_level": int(row["min_level"] or 1),
            "location_tags": row["location_tags"],
        }

    # Fallback: stara tabela (dla itemów stworzonych przez LLM/admin nie backfillowanych — U11c naprawi)
    if t == "weapon":
        old = conn.execute(
            """SELECT key, label, description, COALESCE(price_gp, value_gp, 0) AS effective_price,
                      COALESCE(min_level, 1) AS min_level, location_tags
               FROM game_config_weapons WHERE key = ? AND COALESCE(is_active, 1) = 1""",
            (k,),
        ).fetchone()
        if old:
            return {
                "type": "weapon", "key": old["key"], "label": old["label"] or old["key"],
                "description": old["description"] or "",
                "value_gp": int(old["effective_price"] or 0),
                "min_level": int(old["min_level"] or 1), "location_tags": old["location_tags"],
            }
    if t == "consumable":
        old = conn.execute(
            """SELECT key, label, description, COALESCE(price_gp, base_price, 0) AS effective_price,
                      COALESCE(min_level, 1) AS min_level, location_tags
               FROM game_config_consumables WHERE key = ? AND COALESCE(is_active, 1) = 1""",
            (k,),
        ).fetchone()
        if old:
            return {
                "type": "consumable", "key": old["key"], "label": old["label"] or old["key"],
                "description": old["description"] or "",
                "value_gp": int(old["effective_price"] or 0),
                "min_level": int(old["min_level"] or 1), "location_tags": old["location_tags"],
            }
    try:
        old = conn.execute(
            """SELECT key, label, description, COALESCE(price_gp, value_gp, 0) AS effective_price,
                      item_type, COALESCE(min_level, 1) AS min_level, location_tags
               FROM game_config_items WHERE key = ? AND COALESCE(is_active, 1) = 1""",
            (k,),
        ).fetchone()
    except sqlite3.OperationalError:
        old = None
    if old:
        item_type_from_row = str(old["item_type"] or "").strip().lower()
        return {
            "type": item_type_from_row or t or "item", "key": old["key"],
            "label": old["label"] or old["key"],
            "description": old["description"] or "",
            "value_gp": int(old["effective_price"] or 0),
            "min_level": int(old["min_level"] or 1), "location_tags": old["location_tags"],
        }
    return None


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


def _get_character_race(conn: sqlite3.Connection, character_id: int) -> str:
    """Return character race ('human'/'dwarf'). Fallback 'human' on any error."""
    try:
        row = conn.execute(
            "SELECT race FROM characters WHERE id = ? LIMIT 1",
            (int(character_id),),
        ).fetchone()
        if row:
            val = row["race"] if isinstance(row, sqlite3.Row) else row[0]
            return str(val or "human").strip().lower()
    except Exception:
        pass
    return "human"


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


# #579: village shops are mostly seeded with an empty shop_inventory_json, so smiths/
# healers/merchants showed nothing to buy. When a shop has no explicit stock, fall back
# to a role-appropriate default drawn from the live catalog (game_items). Admins keep full
# control by setting shop_inventory_json explicitly (that always wins).
_HEALER_KEYWORDS = (
    "uzdrowiciel", "zielarka", "aptek", "chirurg", "medyk", "znachor",
    "apothecary", "healer", "herbalist", "alchem",
)


def _pick_catalog_keys(conn: sqlite3.Connection, kind: str, limit: int) -> list[str]:
    """Cheapest `limit` active catalog keys of a given kind (deterministic order)."""
    rows = conn.execute(
        "SELECT key FROM game_items "
        "WHERE kind = ? AND is_active = 1 AND COALESCE(price_gp, 0) > 0 "
        "ORDER BY price_gp ASC, key ASC LIMIT ?",
        (kind, int(limit)),
    ).fetchall()
    return [(r["key"] if isinstance(r, sqlite3.Row) else r[0]) for r in rows]


def _default_stock_for_npc(conn: sqlite3.Connection, npc: sqlite3.Row) -> list[dict[str, str]]:
    """Role-based default shop stock when an NPC has no explicit shop_inventory_json."""
    key = str(npc["key"] or "").lower()
    label = str(npc["label"] or "").lower()
    is_crafter = "is_crafter" in npc.keys() and int(npc["is_crafter"] or 0) == 1
    is_healer = any(w in key or w in label for w in _HEALER_KEYWORDS)

    entries: list[dict[str, str]] = []
    if is_crafter:  # smith — basic weapons + armor
        entries += [{"type": "weapon", "key": k} for k in _pick_catalog_keys(conn, "weapon", 4)]
        entries += [{"type": "armor", "key": k} for k in _pick_catalog_keys(conn, "armor", 3)]
    elif is_healer:  # apothecary/herbalist — consumables
        entries += [{"type": "consumable", "key": k} for k in _pick_catalog_keys(conn, "consumable", 6)]
    else:  # general merchant — a bit of everything
        entries += [{"type": "consumable", "key": k} for k in _pick_catalog_keys(conn, "consumable", 3)]
        entries += [{"type": "item", "key": k} for k in _pick_catalog_keys(conn, "item", 3)]
        entries += [{"type": "weapon", "key": k} for k in _pick_catalog_keys(conn, "weapon", 1)]
    return entries


def _effective_shop_entries(conn: sqlite3.Connection, npc: sqlite3.Row) -> list[dict[str, str]]:
    """Explicit shop_inventory_json wins; empty → role-based default stock (#579)."""
    entries = _parse_shop_inventory(str(npc["shop_inventory_json"] or "[]"))
    if entries:
        return entries
    try:
        return _default_stock_for_npc(conn, npc)
    except Exception:  # default stock must never break a shop
        return []


def get_shop_inventory(npc_id: int, character_id: int, location_key: str | None = None) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc(conn, npc_id)
        cha = _get_character_cha(conn, character_id)
        char_level = _get_character_level(conn, character_id)
        # S6 (#586): podgląd jednorazowego rabatu z targowania (bez konsumpcji).
        haggle_discount = _peek_haggle_for_character(conn, character_id)
        cha_buy_mult = _cha_buy_multiplier(cha)
        eff_buy_mult = haggle_service.effective_buy_multiplier(cha_buy_mult, haggle_discount)
        ratio = haggle_service.effective_sell_ratio(_cha_sell_ratio(cha), haggle_discount)
        entries = _effective_shop_entries(conn, npc)
        items = []
        for e in entries:
            cat = _catalog_item(conn, e["type"], e["key"])
            if not cat or int(cat.get("value_gp") or 0) <= 0:
                continue
            if not _item_passes_filters(cat, char_level, location_key):
                continue
            base = int(cat.get("value_gp") or 0)
            cat["buy_price_gp"] = max(1, int(math.floor(base * eff_buy_mult))) if base > 0 else base
            items.append(cat)
        sell_items = _character_sellables(conn, character_id, ratio)
    return {
        "npc": {"id": int(npc["id"]), "key": npc["key"], "label": npc["label"]},
        "items": items,
        "sell_items": sell_items,
        "character_gold": int(get_character_gold(character_id)),
        "sell_ratio": ratio,
        "buy_multiplier": eff_buy_mult,
        "cha": cha,
        "char_level": char_level,
        "location_key": location_key,
        # S6: ujemny rabat (crit-fail) = narzut; UI renderuje badge przy cenie.
        "haggle_discount": round(haggle_discount, 4),
    }


def get_shop_inventory_by_key(npc_key: str, character_id: int, location_key: str | None = None) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc_by_key(conn, npc_key)
    return get_shop_inventory(int(npc["id"]), character_id, location_key=location_key)


def _reputation_buy_multiplier(conn, character_id: int) -> float:
    """#1099 — regional-reputation buy-price multiplier for a character. 1.0 when
    the character has no campaign / neutral standing or anything goes wrong."""
    try:
        from app.services import reputation_service as rep
        row = conn.execute(
            "SELECT campaign_id FROM characters WHERE id = ?", (int(character_id),)
        ).fetchone()
        campaign_id = row["campaign_id"] if row else None
        if not campaign_id:
            return 1.0
        region = rep.resolve_region(conn, int(campaign_id))
        value = rep.get_reputation(conn, int(character_id), region)
        return rep.shop_price_multiplier(value)
    except Exception:
        return 1.0


def buy_item(character_id: int, npc_id: int, item_type: str, item_key: str) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc(conn, npc_id)
        entries = _effective_shop_entries(conn, npc)
        req_type_norm = _norm_item_type(item_type)
        allowed = any(
            _norm_item_type(e["type"]) == req_type_norm and e["key"] == str(item_key).strip()
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
        # S6 (#586): jednorazowy rabat z targowania stackuje multiplikatywnie z CHA.
        cha = _get_character_cha(conn, character_id)
        haggle_discount = _consume_haggle_for_character(conn, character_id)
        eff_buy_mult = haggle_service.effective_buy_multiplier(_cha_buy_multiplier(cha), haggle_discount)
        # #973 R4: Kowalskie oko — krasnolud płaci mniej u kowala (15% startowo)
        race = _get_character_race(conn, character_id)
        if race == "dwarf":
            eff_buy_mult = round(eff_buy_mult * (1.0 - DWARF_SHOP_DISCOUNT), 4)
        # #1099: regional reputation shifts prices (high standing = discount, low = markup).
        rep_mult = _reputation_buy_multiplier(conn, character_id)
        if rep_mult != 1.0:
            eff_buy_mult = round(eff_buy_mult * rep_mult, 4)
        price = max(1, int(math.floor(base_price * eff_buy_mult))) if base_price > 0 else base_price

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
        "buy_multiplier": eff_buy_mult,
        "haggle_discount": round(haggle_discount, 4),
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
        # S6 (#586): jednorazowy rabat z targowania podnosi cenę sprzedaży.
        haggle_discount = _consume_haggle_for_character(conn, character_id)
        ratio = haggle_service.effective_sell_ratio(_cha_sell_ratio(cha), haggle_discount)
        cha_sell_price = max(1, int(math.floor(base_price * ratio))) if base_price > 0 else 0

        # F12 (#472): anti-farm decay for repeated sales of the same item_key
        # U16 (#564): także liczba sprzedaży w oknie + flaga oversupply dla komunikatu gracza
        recent_sell_count = 0
        try:
            from app.services.anti_farm_service import (
                get_anti_farm_multiplier, apply_anti_farm, _recent_sell_count,
            )
            af_mult = get_anti_farm_multiplier(conn, character_id, item_key)
            earned = apply_anti_farm(cha_sell_price, af_mult)
            recent_sell_count = _recent_sell_count(conn, character_id, item_key)
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
        "base_sell_gp": int(cha_sell_price),
        "sell_ratio": ratio,
        "anti_farm_multiplier": af_mult,
        "recent_sell_count": int(recent_sell_count),
        "oversupply": bool(af_mult < 1.0),
        "haggle_discount": round(haggle_discount, 4),
        "cha": int(cha),
        "sold_item": {
            "type": item_type,
            "key": item_key,
            "label": cat["label"],
        },
    }
