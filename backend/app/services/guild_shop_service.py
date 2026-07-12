"""#1342 BL-D3 — Gildia kupiecka: handel komponentami z asymetrią cen.

Design — OCHRONA PĘTLI FARMIENIA. Gdyby komponenty dało się tanio kupować,
farmienie (bestiariusz #1191 + rzemiosło #1199) traci sens. Dlatego gildia:
  • **sprzedaje** komponenty graczowi drogo — ``GUILD_BUY_MULT`` = 150% bazy,
  • **skupuje** komponenty od gracza tanio — ``GUILD_SELL_RATIO`` = 40% bazy,
  • wystawia **ograniczony, rotowany** asortyment (deterministycznie per DZIEŃ
    gry — te same komponenty przez cały dzień, inne nazajutrz),
  • **NIE** handluje komponentami rzadkimi/bossowymi (``no_trade=1`` — bind-on-drop,
    tylko z farmienia).

Ceny reagują na Targowanie (reuse ``haggle_service``) i reputację regionu/frakcji
(reuse ``shop_service._reputation_buy_multiplier``). Kształt odpowiedzi jest
zgodny z ``shop_service.get_shop_inventory`` (``items``/``sell_items``/…), więc
ŻAR renderuje gildię istniejącym widokiem sklepu z dodatkową sekcją komponentów.

Wszystkie liczby to WARTOŚCI STARTOWE (Numbers Policy) — tuning po smoke ekonomii.
"""
from __future__ import annotations

import hashlib
import math
import sqlite3
from typing import Any

from app.services import haggle_service
from app.services import shop_service
from app.services.loot_service import (
    apply_character_gold_delta,
    get_character_gold,
    grant_loot_to_character,
)

# Asymetria cen gildii (Numbers Policy — startowe).
GUILD_BUY_MULT = 1.5      # gracz KUPUJE komponent od gildii za 150% bazy
GUILD_SELL_RATIO = 0.4    # gracz SPRZEDAJE komponent gildii za 40% bazy

# Rozmiar rotowanego asortymentu (ile komponentów wystawionych naraz danego dnia).
ASSORTMENT_SIZE = 8


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_guild_npc(conn: sqlite3.Connection, npc_id: int) -> sqlite3.Row:
    """Załaduj NPC (walidacja is_shop/is_active) i potwierdź flagę gildii.

    ``shop_service._load_shop_npc`` nie selectuje ``is_guild_merchant``, więc flagę
    dobieramy osobnym zapytaniem.
    """
    npc = shop_service._load_shop_npc(conn, int(npc_id))
    try:
        row = conn.execute(
            "SELECT COALESCE(is_guild_merchant, 0) AS g FROM npcs WHERE id = ?",
            (int(npc["id"]),),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if not row or int(row["g"] or 0) != 1:
        raise ValueError("npc_not_guild")
    return npc


def _load_guild_npc_by_key(conn: sqlite3.Connection, npc_key: str) -> sqlite3.Row:
    npc = shop_service._load_shop_npc_by_key(conn, str(npc_key))
    return _load_guild_npc(conn, int(npc["id"]))


def _game_day(conn: sqlite3.Connection, character_id: int) -> int:
    """Dzień gry (0-indeksowany) z zegara kampanii — sterownik rotacji asortymentu."""
    cid = shop_service._campaign_id_for_character(conn, int(character_id))
    if cid is None:
        return 0
    flags = shop_service._load_session_flags(conn, cid)
    try:
        return int(flags.get("ingame_hours", 0) or 0) // 24
    except (TypeError, ValueError):
        return 0


def _tradeable_components(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Wszystkie handlowalne komponenty: is_component=1 AND no_trade=0, aktywne, wycenione."""
    try:
        return conn.execute(
            """
            SELECT key, label, description, component_type,
                   COALESCE(price_gp, value_gp, 0) AS value_gp
            FROM game_config_items
            WHERE is_component = 1
              AND COALESCE(no_trade, 0) = 0
              AND COALESCE(is_active, 1) = 1
              AND COALESCE(price_gp, value_gp, 0) > 0
            ORDER BY key
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return []


def _daily_assortment(rows: list[sqlite3.Row], day: int, size: int = ASSORTMENT_SIZE) -> list[sqlite3.Row]:
    """Deterministyczna rotacja: stabilny hash(key:day) → sort → pierwsze ``size``.

    Python ``hash()`` jest solony per-proces (niedeterministyczny między restartami),
    więc używamy md5 — ta sama pula i dzień zawsze dają ten sam asortyment.
    """
    def _rank(r: sqlite3.Row) -> str:
        return hashlib.md5(f"{r['key']}:{int(day)}".encode("utf-8")).hexdigest()
    return sorted(rows, key=_rank)[: max(0, int(size))]


def _is_no_trade(conn: sqlite3.Connection, item_key: str) -> bool:
    """Czy komponent jest bind-on-drop (no_trade=1) — nie do handlu w gildii."""
    try:
        row = conn.execute(
            "SELECT COALESCE(no_trade, 0) AS nt, COALESCE(is_component, 0) AS ic "
            "FROM game_config_items WHERE key = ? LIMIT 1",
            (str(item_key).strip(),),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if not row:
        return False
    return int(row["nt"] or 0) == 1 or int(row["ic"] or 0) != 1


# ── read ─────────────────────────────────────────────────────────────────────

def get_guild_shop(npc_id: int, character_id: int) -> dict[str, Any]:
    """Wystaw sklep gildii: rotowany asortyment komponentów + skup z plecaka gracza."""
    with shop_service._conn() as conn:
        npc = _load_guild_npc(conn, npc_id)
        char_level = shop_service._get_character_level(conn, character_id)
        haggle_discount = shop_service._peek_haggle_for_character(conn, character_id)
        rep_mult = shop_service._reputation_buy_multiplier(conn, character_id, npc_id=int(npc["id"]))

        # Mnożnik kupna: 150% × reputacja × targowanie (klamp z haggle_service).
        eff_buy_mult = haggle_service.effective_buy_multiplier(GUILD_BUY_MULT * rep_mult, haggle_discount)
        # Współczynnik sprzedaży: 40% × targowanie (klamp).
        sell_ratio = haggle_service.effective_sell_ratio(GUILD_SELL_RATIO, haggle_discount)

        day = _game_day(conn, character_id)
        assortment = _daily_assortment(_tradeable_components(conn), day)

        items: list[dict[str, Any]] = []
        for r in assortment:
            base = int(r["value_gp"] or 0)
            if base <= 0:
                continue
            items.append({
                "type": "item",
                "key": r["key"],
                "label": r["label"] or r["key"],
                "description": r["description"] or "",
                "value_gp": base,
                "buy_price_gp": max(1, int(math.floor(base * eff_buy_mult))),
                "min_level": 1,
                "is_component": True,
                "component_type": r["component_type"],
            })

        sell_items = _guild_sellables(conn, character_id, sell_ratio)

    return {
        "npc": {"id": int(npc["id"]), "key": npc["key"], "label": npc["label"]},
        "items": items,
        "sell_items": sell_items,
        "character_gold": int(get_character_gold(character_id)),
        "sell_ratio": round(sell_ratio, 4),
        "buy_multiplier": round(eff_buy_mult, 4),
        "char_level": char_level,
        "haggle_discount": round(haggle_discount, 4),
        "game_day": int(day),
        "is_guild": True,
        # Gildia handluje o każdej porze — bez bramki nocnej (parytet pól z UI sklepu).
        "shop_open": True,
        "shop_closed_reason": None,
        "shop_closed_message": None,
        "is_black_market": False,
    }


def get_guild_shop_by_key(npc_key: str, character_id: int) -> dict[str, Any]:
    with shop_service._conn() as conn:
        npc = _load_guild_npc_by_key(conn, npc_key)
    return get_guild_shop(int(npc["id"]), character_id)


def _guild_sellables(conn: sqlite3.Connection, character_id: int, sell_ratio: float) -> list[dict[str, Any]]:
    """Komponenty z plecaka gracza, które gildia skupi (is_component=1, no_trade=0)."""
    try:
        rows = conn.execute(
            """
            SELECT ci.id AS inv_id, ci.item_key AS key, ci.quantity AS qty,
                   gci.label AS label, gci.component_type AS component_type,
                   COALESCE(gci.price_gp, gci.value_gp, 0) AS value_gp
            FROM character_inventory ci
            JOIN game_config_items gci ON gci.key = ci.item_key
            WHERE ci.character_id = ?
              AND gci.is_component = 1
              AND COALESCE(gci.no_trade, 0) = 0
              AND COALESCE(gci.is_active, 1) = 1
              AND COALESCE(gci.price_gp, gci.value_gp, 0) > 0
            ORDER BY gci.label
            """,
            (int(character_id),),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        base = int(r["value_gp"] or 0)
        out.append({
            "inventory_id": int(r["inv_id"]),
            "item_type": "item",
            "key": r["key"],
            "label": r["label"] or r["key"],
            "quantity": int(r["qty"] or 1),
            "value_gp": base,
            "sell_price_gp": max(1, int(math.floor(base * sell_ratio))) if base > 0 else 0,
            "component_type": r["component_type"],
            "is_component": True,
        })
    return out


# ── buy ──────────────────────────────────────────────────────────────────────

def buy_component(character_id: int, npc_id: int, item_key: str) -> dict[str, Any]:
    """Kup komponent z dzisiejszego asortymentu gildii (cena 150% × rep × targowanie)."""
    item_key = str(item_key).strip()
    with shop_service._conn() as conn:
        npc = _load_guild_npc(conn, npc_id)
        if _is_no_trade(conn, item_key):
            raise ValueError("component_no_trade")
        day = _game_day(conn, character_id)
        assortment_keys = {r["key"] for r in _daily_assortment(_tradeable_components(conn), day)}
        if item_key not in assortment_keys:
            raise ValueError("item_not_in_shop")

        cat = shop_service._catalog_item(conn, "item", item_key)
        if not cat or int(cat.get("value_gp") or 0) <= 0:
            raise ValueError("price_or_catalog_missing")
        base = int(cat["value_gp"] or 0)

        haggle_discount = shop_service._consume_haggle_for_character(conn, character_id)
        rep_mult = shop_service._reputation_buy_multiplier(conn, character_id, npc_id=int(npc["id"]))
        eff_buy_mult = haggle_service.effective_buy_multiplier(GUILD_BUY_MULT * rep_mult, haggle_discount)
        price = max(1, int(math.floor(base * eff_buy_mult)))

    if int(get_character_gold(character_id)) < price:
        raise ValueError("insufficient_gold")

    new_gold = apply_character_gold_delta(character_id, -price, "guild_purchase")
    try:
        grant_loot_to_character(character_id, [{"item_key": item_key, "quantity": 1}], source="guild_purchase")
    except Exception:
        apply_character_gold_delta(character_id, price, "guild_purchase_refund")
        raise

    return {
        "gold_gp": int(new_gold),
        "paid_gp": int(price),
        "buy_multiplier": round(eff_buy_mult, 4),
        "haggle_discount": round(haggle_discount, 4),
        "item": {"type": "item", "key": item_key, "label": cat["label"], "value_gp": base},
    }


# ── sell ─────────────────────────────────────────────────────────────────────

def sell_component(character_id: int, npc_id: int, inventory_id: int) -> dict[str, Any]:
    """Sprzedaj komponent gildii (cena 40% × targowanie). no_trade → odmowa."""
    with shop_service._conn() as conn:
        _load_guild_npc(conn, npc_id)
        row = conn.execute(
            "SELECT id, character_id, item_key, quantity FROM character_inventory "
            "WHERE id = ? AND character_id = ? LIMIT 1",
            (int(inventory_id), int(character_id)),
        ).fetchone()
        if not row or not row["item_key"]:
            raise ValueError("inventory_not_found")
        item_key = str(row["item_key"])
        if _is_no_trade(conn, item_key):
            raise ValueError("component_no_trade")

        cat = shop_service._catalog_item(conn, "item", item_key)
        if not cat:
            raise ValueError("price_or_catalog_missing")
        base = int(cat["value_gp"] or 0)

        haggle_discount = shop_service._consume_haggle_for_character(conn, character_id)
        sell_ratio = haggle_service.effective_sell_ratio(GUILD_SELL_RATIO, haggle_discount)
        earned = max(1, int(math.floor(base * sell_ratio))) if base > 0 else 0

        qty = int(row["quantity"] or 1)
        if qty > 1:
            conn.execute("UPDATE character_inventory SET quantity = ? WHERE id = ?", (qty - 1, int(row["id"])))
        else:
            conn.execute("DELETE FROM character_inventory WHERE id = ?", (int(row["id"]),))
        from app.services.economy_service import change_gold
        new_gold = change_gold(conn, int(character_id), int(earned), "guild_sell", meta={"item_key": item_key})
        conn.commit()

    return {
        "gold_gp": int(new_gold),
        "earned_gp": int(earned),
        "sell_ratio": round(sell_ratio, 4),
        "haggle_discount": round(haggle_discount, 4),
        "sold_item": {"type": "item", "key": item_key, "label": cat["label"]},
    }
