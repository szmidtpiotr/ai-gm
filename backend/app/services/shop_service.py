"""Phase 9A-4 — NPC shop service (buy/sell)."""

from __future__ import annotations

import json
import math
import sqlite3
import zlib
from typing import Any

from app.services.dice import parse_character_sheet
from app.services.loot_service import (
    LOOT_DB_PATH,
    apply_character_gold_delta,
    get_character_gold,
    grant_loot_to_character,
)
from app.services import haggle_service
from app.services import night_economy_service as night_econ
from app.services import npc_memory_service
from app.services import npc_placement_service
from app.services import smuggling_service

SELL_RATIO = 0.5

# #1196 E6 — black-market treasure-map fragment (STARTING price, Sandbox-tunable).
# The carrier's catalog value_gp stays 0 so it never appears in normal stock;
# the black market surfaces it with this fixed price instead.
TREASURE_FRAGMENT_KEY = "fragment_mapy_skarbow"
TREASURE_FRAGMENT_BM_PRICE = 50

# #973 R4: Kowalskie oko — krasnolud discount (STARTING value, tunable via Sandbox)
DWARF_SHOP_DISCOUNT = 0.15
DWARF_REPAIR_COST_GP = 20  # złoto za akcję Reperuj (startowo)
# #1475: Piętno społeczne — Piętnowany płaci WIĘCEJ (obcy się go boją). Odwrotność
# kowalskiego oka: +10% narzutu na cenach kupna. Mechaniczna przeciwwaga bonusów
# rasy (łagodniejszy miscast, magia krwi). STARTING value — tunable via Sandbox.
PIETNOWANI_SHOP_MARKUP = 0.10

# Type aliases: catalog may return sub-types that map to canonical stored types.
# "gear" appears in game_config_items.item_type and is returned by catalog for
# general equipment (torch, rope, etc.), but shop_inventory_json stores them as "item".
_ITEM_TYPE_ALIASES: dict[str, str] = {"gear": "item"}


def _norm_item_type(t: str) -> str:
    """Canonical form of item_type for comparison (e.g. 'gear' → 'item')."""
    return _ITEM_TYPE_ALIASES.get(str(t or "").strip().lower(), str(t or "").strip().lower())


def _event_price_category(item_type: str) -> str:
    """#1193: item_type → kategoria cenowa dla mnożnika wydarzenia regionalnego."""
    t = _norm_item_type(item_type)
    if t in ("weapon", "consumable", "armor"):
        return t
    return "item"


def _event_price_multiplier(conn: sqlite3.Connection, character_id: int, item_type: str) -> float:
    """#1193: mnożnik ceny z aktywnego wydarzenia regionalnego (jarmark/zaraza/susza).

    1.0 gdy brak eventu / brak kampanii / błąd. Defensywny."""
    try:
        cid = _campaign_id_for_character(conn, character_id)
        if cid is None:
            return 1.0
        from app.services import world_event_service, reputation_service
        region = reputation_service.resolve_region(conn, int(cid))
        return world_event_service.price_multiplier(conn, region, _event_price_category(item_type))
    except Exception:
        return 1.0


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


def _current_hour_for_character(conn: sqlite3.Connection, character_id: int) -> int | None:
    """#1127: current in-game hour (0–23) from the campaign clock, or None when
    the clock is unknown (no campaign / no session_flags) → night gate disabled."""
    cid = _campaign_id_for_character(conn, character_id)
    if cid is None:
        return None
    flags = _load_session_flags(conn, cid)
    if "ingame_hours" not in flags:
        return None
    try:
        return int(flags["ingame_hours"]) % 24
    except (TypeError, ValueError):
        return None


def _shop_open_state(conn: sqlite3.Connection, npc: sqlite3.Row, character_id: int) -> dict:
    """#1127: night-economy open/closed + black-market flag for this NPC & clock."""
    npc_type = npc["npc_type"] if "npc_type" in npc.keys() else ""
    kind = night_econ.classify_shop(npc["key"], npc["label"], npc_type)
    hour = _current_hour_for_character(conn, character_id)
    return night_econ.shop_open_state(kind, hour)


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
    # AUDIT #1438: block on a concurrent writer rather than raising immediately, so
    # the CAS decrement in sell_item resolves to rowcount 0 instead of a lock error.
    conn.execute("PRAGMA busy_timeout = 5000")
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
        entry: dict[str, Any] = {"type": t, "key": k}
        # MP-7 (#1494): opcjonalny narzut per-sklep. Sól z Pustkowi u Helgi (Granie)
        # jest droższa niż u źródła — bez tego pola cena = katalogowa (bez zmian).
        try:
            price_ov = e.get("price")
            if isinstance(price_ov, (int, float)) and int(price_ov) > 0:
                entry["price"] = int(price_ov)
        except (TypeError, ValueError):
            pass
        out.append(entry)
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
# SG-5c: an innkeeper is not a general trader — a tavern back room holds travel
# sundries and hangover cures, never swords.
_TAVERN_KEYWORDS = (
    "karczmarz", "karczmark", "szynkarz", "oberżyst", "oberzyst", "gospodarz gospody",
    "innkeep", "barkeep", "tavern", "karczma", "szynk",
)

# SG-5c: role → how many catalog picks of each kind. Replaces the old flat
# "4 weapons + 3 armor / 6 consumables / 3+3+1" split.
_STOCK_PROFILES: dict[str, tuple[tuple[str, int], ...]] = {
    "smith": (("weapon", 6), ("armor", 5), ("item", 2)),
    # Kept consumable-only on purpose: the healer contract from #579 (a herbalist
    # never sells hardware) is part of the game's shop vocabulary.
    "healer": (("consumable", 8),),
    "tavern": (("consumable", 4), ("item", 4)),
    "general": (("item", 5), ("consumable", 4), ("weapon", 2), ("armor", 2)),
}

# SG-5c: price ceiling per settlement tier. A hamlet does not stock plate armour;
# a tier-3 city does. STARTING values, Sandbox-tunable.
_TIER_PRICE_CAP: dict[int, int] = {1: 30, 2: 120, 3: 400, 4: 1200}
_TIER_PRICE_CAP_DEFAULT = 30

# Catalog rows that must never reach a shop window regardless of price/kind.
_STOCK_KEY_BLOCKLIST_PREFIXES = ("test_", "[test]", "debug_")
# `game_items.item_data.item_type` values that are story/loot payloads, not
# merchandise: quest tokens (Złoty bożek, Czaszka demona) and relics (#1302,
# passive-effect gear that is meant to be FOUND). A default merchant must not
# put them on the shelf; an admin can still list one explicitly.
_STOCK_ITEM_TYPE_BLOCKLIST = ("quest", "relic")
# Ammunition is a consumable in the catalog, so a herbalist/innkeeper drawing the
# cheapest consumables ended up selling arrows. Armourers and general traders may.
_AMMO_KEYS = ("arrows", "bolts", "strzaly", "belty")
_PROFILE_KEY_BLOCKLIST: dict[str, tuple[str, ...]] = {
    "healer": _AMMO_KEYS,
    "tavern": _AMMO_KEYS,
}


def _stable_offset(seed: str, modulo: int) -> int:
    """Deterministic 0..modulo-1 from a string.

    zlib.crc32, NOT hash() — Python randomises string hashing per process, which
    would make a shop's stock change on every backend restart (and, worse, differ
    between the shop-view request and the buy request → 'item_not_in_shop').
    """
    if modulo <= 1:
        return 0
    return zlib.crc32(seed.encode("utf-8")) % modulo


def _npc_home_tier(conn: sqlite3.Connection, npc: sqlite3.Row) -> int:
    """Settlement tier of where this merchant stands (1 when unknown).

    Deliberately keyed off the MERCHANT's own location, not the shopper's: stock is
    a property of the shop, so the view path and the buy path (which never receives
    a location argument) always compute the exact same list.
    """
    # #1524: obsada lokacji ma jedno źródło prawdy — tabelę przypisań.
    return npc_placement_service.max_tier_for_npc_key(conn, str(npc["key"] or ""))


def _shop_profile_for_npc(npc: sqlite3.Row) -> str:
    key = str(npc["key"] or "").lower()
    label = str(npc["label"] or "").lower()
    npc_type = str(npc["npc_type"] or "").lower() if "npc_type" in npc.keys() else ""
    crafter_type = str(npc["crafter_type"] or "").lower() if "crafter_type" in npc.keys() else ""
    hay = f"{key} {label} {npc_type} {crafter_type}"
    if ("is_crafter" in npc.keys() and int(npc["is_crafter"] or 0) == 1) or "smith" in hay:
        return "smith"
    if any(w in hay for w in _HEALER_KEYWORDS):
        return "healer"
    if any(w in hay for w in _TAVERN_KEYWORDS):
        return "tavern"
    return "general"


def _pick_catalog_keys(
    conn: sqlite3.Connection,
    kind: str,
    limit: int,
    *,
    price_cap: int | None = None,
    seed: str = "",
    exclude_keys: tuple[str, ...] = (),
) -> list[str]:
    """`limit` catalog keys of a kind, SPREAD across the affordable price range.

    The old version took the `limit` CHEAPEST rows, which is why every smith in the
    game offered a staff, a quarterstaff, a wooden shield and a dagger — the four
    cheapest weapons in the catalog — and every general trader the same three 1 gp
    trinkets. Picking evenly spaced entries from the price-sorted, tier-capped list
    gives each shop a low/mid/high spread instead, and a per-NPC offset keeps two
    smiths in the same town from being carbon copies.
    """
    params = (kind, int(price_cap if price_cap is not None else 10**9))
    base_sql = (
        "SELECT key FROM game_items "
        "WHERE kind = ? AND is_active = 1 AND COALESCE(price_gp, 0) > 0 "
        "AND COALESCE(price_gp, 0) <= ? "
    )
    try:
        rows = conn.execute(
            base_sql
            + "AND COALESCE(json_extract(item_data, '$.item_type'), '') NOT IN "
            + "(" + ",".join("?" * len(_STOCK_ITEM_TYPE_BLOCKLIST)) + ") "
            + "ORDER BY price_gp ASC, key ASC",
            params + _STOCK_ITEM_TYPE_BLOCKLIST,
        ).fetchall()
    except sqlite3.OperationalError:
        # Minimal/legacy catalog without item_data — price/kind filtering only.
        rows = conn.execute(base_sql + "ORDER BY price_gp ASC, key ASC", params).fetchall()
    blocked = {str(k).lower() for k in exclude_keys}
    pool = []
    for r in rows:
        k = str((r["key"] if isinstance(r, sqlite3.Row) else r[0]) or "")
        if k.lower().startswith(_STOCK_KEY_BLOCKLIST_PREFIXES) or k.lower() in blocked:
            continue
        pool.append(k)
    n = int(limit)
    if n <= 0 or not pool:
        return []
    if len(pool) <= n:
        return pool
    step = len(pool) / n
    offset = _stable_offset(f"{seed}|{kind}", max(1, int(step)))
    picked: list[str] = []
    for i in range(n):
        idx = min(len(pool) - 1, int(i * step) + offset)
        k = pool[idx]
        if k not in picked:
            picked.append(k)
    # Offset collisions can shrink the list; backfill from the untouched pool so a
    # shop always shows the promised number of goods.
    for k in pool:
        if len(picked) >= n:
            break
        if k not in picked:
            picked.append(k)
    return picked


def _default_stock_for_npc(conn: sqlite3.Connection, npc: sqlite3.Row) -> list[dict[str, str]]:
    """Role- AND tier-based default stock when an NPC has no explicit inventory.

    Explicit `shop_inventory_json` still wins (see `_effective_shop_entries`); this
    is what the other ~29 of 31 merchants fall back on.
    """
    profile = _shop_profile_for_npc(npc)
    cap = _TIER_PRICE_CAP.get(_npc_home_tier(conn, npc), _TIER_PRICE_CAP_DEFAULT)
    seed = str(npc["key"] or npc["label"] or "shop")
    entries: list[dict[str, str]] = []
    excluded = _PROFILE_KEY_BLOCKLIST.get(profile, ())
    for kind, count in _STOCK_PROFILES[profile]:
        entries += [
            {"type": kind, "key": k}
            for k in _pick_catalog_keys(
                conn, kind, count, price_cap=cap, seed=seed, exclude_keys=excluded
            )
        ]
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


def _is_guild_npc(conn: sqlite3.Connection, npc_id: int) -> bool:
    """#1342: czy NPC to placówka Gildii Kupieckiej (osobna kolumna, nie w _load_shop_npc)."""
    try:
        row = conn.execute(
            "SELECT COALESCE(is_guild_merchant, 0) AS g FROM npcs WHERE id = ?", (int(npc_id),)
        ).fetchone()
        return bool(row and int(row["g"] or 0) == 1)
    except sqlite3.OperationalError:
        return False


def get_shop_inventory(npc_id: int, character_id: int, location_key: str | None = None) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc(conn, npc_id)
        # #1342: placówka gildii → istniejący widok sklepu, ale asortyment komponentów
        # z asymetrią cen i rotacją per dzień (delegacja; lazy import — cykl modułów).
        if _is_guild_npc(conn, int(npc["id"])):
            from app.services import guild_shop_service
            return guild_shop_service.get_guild_shop(int(npc["id"]), character_id)
        cha = _get_character_cha(conn, character_id)
        char_level = _get_character_level(conn, character_id)
        # S6 (#586): podgląd jednorazowego rabatu z targowania (bez konsumpcji).
        haggle_discount = _peek_haggle_for_character(conn, character_id)
        cha_buy_mult = _cha_buy_multiplier(cha)
        eff_buy_mult = haggle_service.effective_buy_multiplier(cha_buy_mult, haggle_discount)
        # G8 #1472: krasnolud (kowalskie oko, −15%) widzi cenę PO rabacie także w
        # podglądzie — wcześniej okno sklepu pokazywało cenę wyższą niż faktycznie
        # pobierana przy kupnie (combined_buy_multiplier). Klamer jak na torze kupna.
        _shopper_race = _get_character_race(conn, character_id)
        if _shopper_race == "dwarf":
            eff_buy_mult = round(max(0.4, min(2.0, eff_buy_mult * (1.0 - DWARF_SHOP_DISCOUNT))), 4)
        elif _shopper_race == "pietnowani":
            # #1475 / MP-8: piętno społeczne — obcy podnoszą cenę (+10%), ale we
            # własnej enklawie (Solny Próg) swoi NIE dokładają narzutu.
            eff_buy_mult = round(max(0.4, min(2.0, eff_buy_mult * _pietnowani_markup(conn, character_id, location_key))), 4)
        # KN-8 (#1500): glejt kupiecki → cena cechowa na targach Nizin (podgląd = kupno).
        _glejt_mult = smuggling_service.glejt_market_multiplier(conn, character_id)
        if _glejt_mult != 1.0:
            eff_buy_mult = round(max(0.4, min(2.0, eff_buy_mult * _glejt_mult)), 4)
        ratio = haggle_service.effective_sell_ratio(_cha_sell_ratio(cha), haggle_discount)
        # #1127: night economy — reflect open state + black-market pricing in the UI.
        night_state = _shop_open_state(conn, npc, character_id)
        if night_state["is_black_market"] and night_state["open"]:
            eff_buy_mult = round(eff_buy_mult * night_econ.BLACK_MARKET_BUY_MULT, 4)
            ratio = round(ratio * night_econ.BLACK_MARKET_SELL_MULT, 4)
        entries = _effective_shop_entries(conn, npc)
        items = []
        for e in entries:
            cat = _catalog_item(conn, e["type"], e["key"])
            if not cat or int(cat.get("value_gp") or 0) <= 0:
                continue
            if not _item_passes_filters(cat, char_level, location_key):
                continue
            # MP-7 (#1494): narzut per-sklep (shop_inventory_json entry.price) bije cenę katalogową.
            base = int(e.get("price") or cat.get("value_gp") or 0)
            # #1193: wydarzenie regionalne (jarmark −20%, zaraza mikstury +50%) —
            # mnożnik per kategoria, składany multiplikatywnie z CHA/haggle/noc.
            ev_mult = _event_price_multiplier(conn, character_id, e["type"])
            cat["buy_price_gp"] = max(1, int(math.floor(base * eff_buy_mult * ev_mult))) if base > 0 else base
            items.append(cat)
        # #1196 E6 — black market at night offers a treasure-map fragment (kept out
        # of the normal catalog so it never leaks into daytime/regular stock).
        if night_state["is_black_market"] and night_state["open"]:
            _frag = {"type": "item", "key": TREASURE_FRAGMENT_KEY,
                     "label": "Fragment mapy skarbów", "value_gp": TREASURE_FRAGMENT_BM_PRICE,
                     "description": "Podejrzany typ zniża głos: „Kawałek mapy… resztę znajdziesz sam."}
            _frag["buy_price_gp"] = max(1, int(math.floor(TREASURE_FRAGMENT_BM_PRICE * eff_buy_mult)))
            items.append(_frag)
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
        # #1127: night economy — UI shows open/closed banner + black-market flag.
        "shop_open": bool(night_state["open"]),
        "shop_closed_reason": night_state["reason"],
        "shop_closed_message": night_state["message"],
        "is_black_market": bool(night_state["is_black_market"]),
    }


def get_shop_inventory_by_key(npc_key: str, character_id: int, location_key: str | None = None) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc_by_key(conn, npc_key)
    return get_shop_inventory(int(npc["id"]), character_id, location_key=location_key)


def _reputation_buy_multiplier(conn, character_id: int, npc_id: int | None = None) -> float:
    """#1099/#1103 — buy-price multiplier combining region + faction reputation.

    Uses combined_buy_multiplier: best-deal of region rep and (if NPC belongs to
    a faction) faction rep. 1.0 when no campaign / neutral standing / error.
    """
    try:
        from app.services import reputation_service as rep
        row = conn.execute(
            "SELECT campaign_id FROM characters WHERE id = ?", (int(character_id),)
        ).fetchone()
        campaign_id = row["campaign_id"] if row else None
        if not campaign_id:
            return 1.0
        region = rep.resolve_region(conn, int(campaign_id))
        # #1103: check if this NPC belongs to a faction
        faction_key = None
        if npc_id is not None:
            try:
                npc_row = conn.execute(
                    "SELECT faction_key FROM npcs WHERE id = ?", (int(npc_id),)
                ).fetchone()
                faction_key = npc_row["faction_key"] if npc_row else None
            except Exception:
                pass
        return rep.combined_buy_multiplier(conn, int(character_id), region, faction_key)
    except Exception:
        return 1.0


def combined_buy_multiplier(
    conn: sqlite3.Connection,
    character_id: int,
    npc_id: int | None,
    item_type: str,
    *,
    is_black_market: bool = False,
    haggle_discount: float = 0.0,
) -> float:
    """AUDIT #1439 — assemble EVERY buy-price multiplier into one product and clamp
    ONCE at the end to [0.4, 2.0].

    The old buy path clamped CHA×haggle early (`effective_buy_multiplier`) and THEN
    multiplied dwarf ×0.85, reputation, black-market and regional event on top, so
    the true floor silently sank to ~0.27 — well under the intended 0.40 — opening a
    buy-cheap / sell-dear arbitrage. Building the raw product and clamping a single
    time closes that. Also the single source of truth for the sell-side arbitrage
    cap, so buy and sell always agree on the item's fair market multiplier.
    """
    cha = _get_character_cha(conn, character_id)
    raw = _cha_buy_multiplier(cha) * (1.0 - float(haggle_discount or 0.0))
    _buyer_race = _get_character_race(conn, character_id)
    if _buyer_race == "dwarf":
        raw *= (1.0 - DWARF_SHOP_DISCOUNT)
    elif _buyer_race == "pietnowani":
        raw *= _pietnowani_markup(conn, character_id)  # #1475/MP-8: piętno tylko poza enklawą
    rep_mult = _reputation_buy_multiplier(conn, character_id, npc_id=npc_id)
    if rep_mult != 1.0:
        raw *= rep_mult
    # KN-8 (#1500): glejt kupiecki → cena cechowa na targach Nizin (−10%).
    glejt_mult = smuggling_service.glejt_market_multiplier(conn, character_id)
    if glejt_mult != 1.0:
        raw *= glejt_mult
    if is_black_market:
        raw *= night_econ.BLACK_MARKET_BUY_MULT
    ev_mult = _event_price_multiplier(conn, character_id, item_type)
    if ev_mult != 1.0:
        raw *= ev_mult
    return round(max(0.4, min(2.0, raw)), 4)


def _current_location_key_for_character(conn: sqlite3.Connection, character_id: int) -> str | None:
    """AUDIT #1439 — the character's current world-location key, or None when it
    cannot be resolved (no campaign / lightweight test fixture)."""
    try:
        cid = _campaign_id_for_character(conn, character_id)
        if not cid:
            return None
        from app.services.location_state_service import get_current_location_key
        return get_current_location_key(conn, int(cid)) or None
    except Exception:
        return None


#: MP-8 (#1475/#1494 §8) — enklawa Piętnowanych = Solny Próg (hub + wszystkie
#: suby: gospoda, dom starszych, cicha sala, targ, magazyny). We własnej enklawie
#: piętno społeczne NIE działa (swoi nie boją się Piętna); poza nią (Obóz Gorączki,
#: Misja Światła, reszta świata) obcy dokładają narzut.
PIETNOWANI_ENCLAVE_PREFIX = "solny_prog"


def _pietnowani_in_home_enclave(
    conn: sqlite3.Connection, character_id: int, location_key: str | None = None
) -> bool:
    """True, gdy Piętnowany handluje we własnej enklawie (Solny Próg) — wtedy
    piętno społeczne nie podnosi ceny. Nieznana lokacja → traktuj jak teren obcy
    (zachowuje domyślny narzut rasy, tak jak przed MP-8)."""
    loc = location_key or _current_location_key_for_character(conn, character_id)
    return bool(loc) and str(loc).startswith(PIETNOWANI_ENCLAVE_PREFIX)


def _pietnowani_markup(
    conn: sqlite3.Connection, character_id: int, location_key: str | None = None
) -> float:
    """MP-8 (#1475): mnożnik piętna społecznego dla Piętnowanego. Poza enklawą
    1.0 + PIETNOWANI_SHOP_MARKUP (obcy boją się Piętna → +10%); u swoich w Solnym
    Progu 1.0 (bez narzutu). Wołany tylko gdy rasa == 'pietnowani'."""
    if _pietnowani_in_home_enclave(conn, character_id, location_key):
        return 1.0
    return 1.0 + PIETNOWANI_SHOP_MARKUP


def _npc_serves_location(conn: sqlite3.Connection, npc: sqlite3.Row, location_key: str | None) -> bool:
    """AUDIT #1439 — True if this shop NPC is present at ``location_key``.

    An NPC with NO location assignments at all is treated as global (present
    everywhere) so seed/test merchants are never falsely rejected; one WITH
    assignments must list the player's current location, otherwise the buyer is
    trying to shop at a merchant in another region by raw id → npc_not_here.
    """
    # #1524: jedno źródło prawdy — location_npc_assignments (legacy npc_locations martwe).
    return npc_placement_service.npc_is_at_location(conn, str(npc["key"] or ""), location_key)


def buy_item(character_id: int, npc_id: int, item_type: str, item_key: str) -> dict[str, Any]:
    with _conn() as conn:
        npc = _load_shop_npc(conn, npc_id)
        # #1342: zakup u gildii → silnik komponentów (asymetria + rotacja + no_trade).
        if _is_guild_npc(conn, int(npc["id"])):
            from app.services import guild_shop_service
            return guild_shop_service.buy_component(character_id, int(npc["id"]), item_key)
        # #1183: remember which campaign this purchase belongs to, so the merchant
        # NPC's purchase_count can be bumped after the sale succeeds.
        buy_campaign_id = _campaign_id_for_character(conn, character_id)
        # #1127: night economy — refuse closed shops; flag the black market.
        night_state = _shop_open_state(conn, npc, character_id)
        if not night_state["open"]:
            raise ValueError(night_state["reason"] or "shop_closed_night")
        # #1196 E6 — a treasure-map fragment is offered only at black markets at night.
        _is_bm_frag = bool(night_state["is_black_market"]
                           and str(item_key).strip() == TREASURE_FRAGMENT_KEY)
        entries = _effective_shop_entries(conn, npc)
        req_type_norm = _norm_item_type(item_type)
        allowed = _is_bm_frag or any(
            _norm_item_type(e["type"]) == req_type_norm and e["key"] == str(item_key).strip()
            for e in entries
        )
        if not allowed:
            raise ValueError("item_not_in_shop")
        if _is_bm_frag:
            cat = {"type": "item", "key": TREASURE_FRAGMENT_KEY,
                   "label": "Fragment mapy skarbów", "value_gp": TREASURE_FRAGMENT_BM_PRICE}
            base_price = TREASURE_FRAGMENT_BM_PRICE
        else:
            cat = _catalog_item(conn, item_type, item_key)
            if not cat:
                raise ValueError("price_or_catalog_missing")
            base_price = int(cat["value_gp"] or 0)
            # MP-7 (#1494): jeśli sklep ustawił narzut per-wpis, on wygrywa nad ceną katalogową.
            _price_ov = next(
                (int(e["price"]) for e in entries
                 if _norm_item_type(e["type"]) == req_type_norm
                 and e["key"] == str(item_key).strip() and e.get("price")),
                None,
            )
            if _price_ov:
                base_price = _price_ov
            if base_price <= 0:
                raise ValueError("price_or_catalog_missing")
        # AUDIT #1439 (P1): a direct POST /buy bypassed the availability filters the
        # shop VIEW enforces (`_item_passes_filters`) — a level-1 hero could buy a
        # min_level-10 item, and any NPC id from another region was buyable remotely.
        # Enforce both here. min_level is always checked; the location-tag filter and
        # NPC-presence check apply only when we can resolve the player's location
        # (campaignless test characters keep working). BM fragment is synthetic (no
        # catalog row) and skips the item filter.
        char_level = _get_character_level(conn, character_id)
        server_location = _current_location_key_for_character(conn, character_id)
        if not _is_bm_frag:
            if char_level < int(cat.get("min_level") or 1):
                raise ValueError("item_not_available")
            if server_location and not _item_passes_filters(cat, char_level, server_location):
                raise ValueError("item_not_available")
        if server_location and not _npc_serves_location(conn, npc, server_location):
            raise ValueError("npc_not_here")
        # F10 (#470): CHA modifies actual buy price (discount/markup, symmetric to sell).
        # S6 (#586): jednorazowy rabat z targowania stackuje multiplikatywnie z CHA.
        # AUDIT #1439: PEEK the haggle discount for pricing; it is CONSUMED only after
        # the gold check succeeds (a failed purchase must not burn the discount), and
        # ALL multipliers are assembled + clamped ONCE inside combined_buy_multiplier
        # (no more early-clamp-then-multiply arbitrage below the 0.40 floor).
        cha = _get_character_cha(conn, character_id)
        haggle_discount = _peek_haggle_for_character(conn, character_id)
        eff_buy_mult = combined_buy_multiplier(
            conn, character_id, npc_id, item_type,
            is_black_market=bool(night_state["is_black_market"]),
            haggle_discount=haggle_discount,
        )
        price = max(1, int(math.floor(base_price * eff_buy_mult))) if base_price > 0 else base_price

    # Validate gold first for cleaner error mapping.
    cur_gold = int(get_character_gold(character_id))
    if cur_gold < price:
        raise ValueError("insufficient_gold")

    # AUDIT #1439: gold check passed → NOW consume the one-shot haggle discount.
    with _conn() as _c2:
        _consume_haggle_for_character(_c2, character_id)
        _c2.commit()

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

    # #1183: sale confirmed — bump this merchant NPC's purchase_count so the GM can
    # greet a returning customer (rendered via format_known_npcs_block). Best-effort:
    # a memory-bump failure must never undo a completed purchase.
    if buy_campaign_id is not None:
        try:
            npc_memory_service.increment_npc_purchase_count(
                campaign_id=buy_campaign_id,
                npc_id=int(npc_id),
                npc_name=(str(npc["label"]).strip() or None) if npc["label"] else None,
            )
        except Exception:
            pass

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


def sell_item(character_id: int, inventory_id: int, npc_id: int | None = None) -> dict[str, Any]:
    with _conn() as conn:
        # #1127: night economy — gate the sale by shop hours when we know the NPC.
        # npc_id omitted (legacy callers) → no gating, old behaviour preserved.
        night_state = {"open": True, "is_black_market": False}
        if npc_id is not None:
            try:
                npc = _load_shop_npc(conn, int(npc_id))
                # #1342: sprzedaż gildii → skup komponentów 40% (no_trade odrzucone).
                if _is_guild_npc(conn, int(npc["id"])):
                    from app.services import guild_shop_service
                    return guild_shop_service.sell_component(character_id, int(npc["id"]), int(inventory_id))
                night_state = _shop_open_state(conn, npc, character_id)
                if not night_state["open"]:
                    raise ValueError(night_state["reason"] or "shop_closed_night")
            except ValueError as e:
                if "npc_not" in str(e).lower():
                    night_state = {"open": True, "is_black_market": False}
                else:
                    raise
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
        # #1127: the black-market fence pays less (×0.6).
        if night_state.get("is_black_market") and cha_sell_price > 0:
            cha_sell_price = max(1, int(math.floor(cha_sell_price * night_econ.BLACK_MARKET_SELL_MULT)))

        # WL-8 (#1504): towar handlowy krainy (sól morska / kontrabanda) ma cenę
        # SPRZEDAŻY zależną od regionu — arbitraż międzykrainowy jest tu sensem gry
        # (przemyt), więc CELOWO omija cap arbitrażu z AUDIT #1439 (ten cap chroni
        # przed round-tripem w JEDNYM sklepie, nie przed handlem Wybrzeże↔Niziny).
        _tg_sell = smuggling_service.trade_good_sell_price(conn, character_id, item_key)
        if _tg_sell is not None:
            earned = int(_tg_sell)
            cha_sell_price = int(_tg_sell)
            af_mult = 1.0
            recent_sell_count = 0
        else:
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

            # AUDIT #1439 (P1): kill buy-low / sell-high arbitrage. Cap the payout
            # strictly BELOW what it would cost to buy the SAME item back from this NPC
            # right now, so a round-trip can never net gold no matter how CHA / dwarf /
            # reputation / event multipliers drift apart between the two sides.
            buy_mult = combined_buy_multiplier(
                conn, character_id, npc_id, item_type,
                is_black_market=bool(night_state.get("is_black_market")),
            )
            buy_price_back = max(1, int(math.floor(base_price * buy_mult))) if base_price > 0 else 0
            if buy_price_back > 0:
                earned = max(0, min(int(earned), buy_price_back - 1))

        # AUDIT #1438 (P1): double-sell race. The old SELECT → unconditional
        # DELETE → credit let two concurrent requests on the same inventory_id both
        # pass the SELECT, both credit gold, while the second DELETE was a silent
        # no-op → double payout for one physical item. Compare-and-swap on the read
        # quantity: only one racer's decrement lands; the loser sees rowcount 0 and
        # is rejected BEFORE any gold is credited.
        qty = int(row["quantity"] or 1)
        if qty > 1:
            mut = conn.execute(
                "UPDATE character_inventory SET quantity = quantity - 1 "
                "WHERE id = ? AND quantity = ?",
                (int(row["id"]), qty),
            )
        else:
            mut = conn.execute(
                "DELETE FROM character_inventory WHERE id = ? AND quantity = ?",
                (int(row["id"]), qty),
            )
        if mut.rowcount == 0:
            raise ValueError("inventory_not_found")
        # #1158: kredyt złota + tag anti-farm w TEJ SAMEJ transakcji co usunięcie
        # przedmiotu — jedno połączenie, jeden commit. Wcześniej DELETE commitował się
        # (linia 729), a wypłata szła osobnym połączeniem: awaria między nimi niszczyła
        # przedmiot bez złota i bez kompensacji. change_gold journaluje z meta, więc
        # item_key trafia w ten sam wiersz logu atomowo (koniec kruchego MAX(id)-taga).
        from app.services.economy_service import change_gold
        new_gold = change_gold(
            conn, int(character_id), int(earned), "shop_sell",
            meta={"item_key": item_key},
        )
        conn.commit()

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
