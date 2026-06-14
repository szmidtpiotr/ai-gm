"""
Economy Service — V2 Phase 06 Tasks 20-26

Handles:
- TASK_20: Inventory & equipment (V2 slot system)
- TASK_23: Healing items, rest recovery
- TASK_24: Wound labels (HP threshold → Polish label + color)
- TASK_25V2: XP grants (reads from game_config_xp_awards)
- TASK_26: XP log access
"""

from __future__ import annotations

import json
import random
import sqlite3
import structlog
from typing import Any

logger = structlog.get_logger()

DB_PATH = "/data/ai_gm.db"

# ── Wound Labels (TASK_24 → U15) ───────────────────────────────────────────
# U15: labels now derive from the single source of truth in wound_utils.WOUND_TIERS
# so a tier's label and its mechanical roll penalty can never drift apart.
from app.services.wound_utils import wound_tier


def get_wound_label(current_hp: int, max_hp: int) -> dict:
    """
    Returns wound label info for a given HP pair.
    Delegates to wound_utils.wound_tier() (single source of truth).
    """
    t = wound_tier(current_hp, max_hp)
    return {"label": t["label"], "color": t["color"], "pct": t["pct"], "cue": t["cue"]}


# ── XP System (TASK_25V2 + TASK_26) ───────────────────────────────────────

def get_xp_award_amount(source_key: str, conn: sqlite3.Connection) -> int:
    """Read XP award amount from game_config_xp_awards. Returns 0 if not found/inactive."""
    row = conn.execute(
        "SELECT xp_amount, is_active FROM game_config_xp_awards WHERE source_key = ?",
        (source_key,)
    ).fetchone()
    if not row or not row["is_active"]:
        return 0
    return int(row["xp_amount"] or 0)


def grant_xp(
    character_id: int,
    campaign_id: int,
    source_key: str,
    conn: sqlite3.Connection,
    detail: str = "",
    turn_number: int | None = None,
) -> int:
    """
    Grant XP to a character. Reads amount from game_config_xp_awards.
    Returns amount granted (0 if source inactive or not found).
    """
    amount = get_xp_award_amount(source_key, conn)
    if amount <= 0:
        return 0

    try:
        conn.execute(
            """INSERT INTO character_xp_grants
               (character_id, campaign_id, amount, source_key, detail, turn_number)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (character_id, campaign_id, amount, source_key, detail, turn_number)
        )
        conn.commit()
        logger.info("xp_granted", character_id=character_id, source=source_key, amount=amount)
    except Exception as e:
        logger.warning("xp_grant_failed", error=str(e))
        return 0

    return amount


def get_total_xp(character_id: int, conn: sqlite3.Connection) -> int:
    """Sum all XP grants for a character."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM character_xp_grants WHERE character_id = ?",
        (character_id,)
    ).fetchone()
    return int(row[0]) if row else 0


def get_level_display(character_id: int, conn: sqlite3.Connection) -> int:
    """Level is display-only: floor(total_xp / 100), capped at 10."""
    total = get_total_xp(character_id, conn)
    return min(10, total // 100)


# ── Gold journaling (Stage 11 R6 — issue #64) ─────────────────────────────


def journal_gold_delta(
    conn: sqlite3.Connection,
    character_id: int,
    delta: int,
    source: str,
    *,
    campaign_id: int | None = None,
    meta: dict | None = None,
    set_absolute: int | None = None,
) -> None:
    """Write a row to character_gold_log. Mutating gold_gp itself is the
    caller's responsibility — this only journals.

    `delta` is the SIGNED change (positive = gain, negative = spend).
    `set_absolute` lets callers that overwrite (e.g. admin "set gold to N")
    record the resulting value in meta_json — pass it for traceability.
    Resurrection's gold_recent_days mode only sums positive deltas, so
    spends do not affect that calculation.
    """
    if delta == 0:
        return
    game_day = 1
    if campaign_id is not None:
        try:
            from app.services.clock_service import get_clock_state
            game_day = int(get_clock_state(int(campaign_id), conn=conn)["day"])
        except Exception:
            pass
    payload = dict(meta or {})
    if set_absolute is not None:
        payload["set_absolute"] = int(set_absolute)
    meta_str = json.dumps(payload, ensure_ascii=False) if payload else None
    try:
        # U26: campaign_id is now a first-class column (migration adds it).
        conn.execute(
            """
            INSERT INTO character_gold_log
                (character_id, delta, source, campaign_id, game_clock_day, meta_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (character_id, int(delta), source, campaign_id, game_day, meta_str),
        )
    except sqlite3.OperationalError:
        # Pre-U26 schema without campaign_id column — fall back gracefully.
        try:
            conn.execute(
                """
                INSERT INTO character_gold_log
                    (character_id, delta, source, game_clock_day, meta_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (character_id, int(delta), source, game_day, meta_str),
            )
        except sqlite3.OperationalError as e:
            logger.warning("gold_log_insert_failed", error=str(e))


# ── U26: central gold mutation chokepoint + telemetry ─────────────────────


# Map raw source strings (scattered across services) → canonical ENUM buckets
# for the admin economy tile. Stored source strings stay unchanged (anti-farm
# and resurrection windows depend on them); categorize only for reporting.
_SOURCE_BUCKETS = {
    "loot": "loot",
    "gold_drop": "loot",
    "shop_sell": "sell",
    "sell": "sell",
    "shop_purchase": "buy",
    "shop_purchase_refund": "buy",
    "buy": "buy",
    "service": "service",
    "spend_gold": "service",
    "robbery": "robbery",
    "resurrection_gold": "resurrection",
    "resurrection": "resurrection",
    "repair_durability": "repair",
    "repair": "repair",
    "craft": "craft",
    "crafter_repair": "repair",
    "crafter_affix": "craft",
    "quest_reward": "quest_reward",
    "starter_gold": "starter_gold",
    "admin_cheat_add": "admin_cheat",
    "admin_cheat": "admin_cheat",
    "gamble": "gamble",
}

# Allowed canonical buckets (spec U26 ENUM, extended with starter/admin/gamble/other).
ECONOMY_SOURCE_BUCKETS = (
    "loot", "sell", "buy", "service", "robbery", "resurrection",
    "repair", "craft", "quest_reward", "starter_gold", "admin_cheat", "gamble", "other",
)


def categorize_source(source: str | None) -> str:
    """Map a raw gold-log source string to a canonical reporting bucket.

    Falls back to prefix heuristics, then 'other'. Read-side only — stored
    source strings are never rewritten.
    """
    s = (source or "").strip().lower()
    if s in _SOURCE_BUCKETS:
        return _SOURCE_BUCKETS[s]
    if s.startswith("shop_purchase") or s.startswith("buy"):
        return "buy"
    if s.startswith("shop_sell") or s.startswith("sell"):
        return "sell"
    if s.startswith("repair"):
        return "repair"
    if s.startswith("craft"):
        return "craft"
    if s.startswith("resurrection"):
        return "resurrection"
    if s.startswith("admin_cheat"):
        return "admin_cheat"
    if s.startswith("starter"):
        return "starter_gold"
    if s.startswith("quest"):
        return "quest_reward"
    if s.startswith("service") or s.startswith("spend_gold"):
        return "service"
    if s.startswith("gamble"):
        return "gamble"
    return "other"


def change_gold(
    conn: sqlite3.Connection,
    character_id: int,
    delta: int,
    source: str,
    *,
    campaign_id: int | None = None,
    meta: dict | None = None,
    allow_negative: bool = False,
) -> int:
    """U26 — single chokepoint for every gold mutation.

    Atomically adjusts `characters.gold_gp` by signed `delta` AND journals the
    change to `character_gold_log` (via journal_gold_delta). Operates on the
    caller-owned `conn` and does NOT commit — the caller owns the transaction.

    Returns the new balance. Raises ValueError if the character is missing or
    the result would go below 0 (unless `allow_negative=True`). A zero delta is
    a no-op that returns the current balance without writing a log row.
    """
    cid = int(character_id)
    d = int(delta)
    row = conn.execute(
        "SELECT gold_gp FROM characters WHERE id = ?", (cid,)
    ).fetchone()
    if not row:
        raise ValueError("character not found")
    cur = int(row["gold_gp"] or 0)
    if d == 0:
        return cur
    new_g = cur + d
    if new_g < 0 and not allow_negative:
        raise ValueError("gold_gp would be negative")
    conn.execute("UPDATE characters SET gold_gp = ? WHERE id = ?", (new_g, cid))
    # Resolve campaign for the journal: explicit arg wins, else fall back to the
    # character's own campaign_id (column may be absent in minimal test fixtures).
    cid_for_clock = campaign_id
    if cid_for_clock is None:
        try:
            cr = conn.execute(
                "SELECT campaign_id FROM characters WHERE id = ?", (cid,)
            ).fetchone()
            cid_for_clock = cr["campaign_id"] if cr else None
        except sqlite3.OperationalError:
            cid_for_clock = None
    journal_gold_delta(conn, cid, d, source, campaign_id=cid_for_clock, meta=meta)
    return new_g


def get_economy_7d(conn: sqlite3.Connection, days: int = 7) -> dict:
    """U26 — admin telemetry: gold income/expense per source bucket over a window.

    Reads character_gold_log within the last `days` (wall_clock_at), groups by
    the canonical bucket from categorize_source(). Income = sum of positive
    deltas, expense = sum of |negative deltas|.
    """
    rows = conn.execute(
        """
        SELECT source, delta FROM character_gold_log
        WHERE wall_clock_at >= datetime('now', ?)
          AND COALESCE(reverted_at, '') = ''
        """,
        (f"-{int(days)} days",),
    ).fetchall()
    buckets: dict[str, dict] = {}
    for r in rows:
        b = categorize_source(r["source"])
        slot = buckets.setdefault(b, {"source": b, "income": 0, "expense": 0, "count": 0})
        d = int(r["delta"] or 0)
        if d >= 0:
            slot["income"] += d
        else:
            slot["expense"] += -d
        slot["count"] += 1
    out_rows = []
    total_income = total_expense = 0
    for b in sorted(buckets, key=lambda k: -(buckets[k]["income"] + buckets[k]["expense"])):
        slot = buckets[b]
        slot["net"] = slot["income"] - slot["expense"]
        out_rows.append(slot)
        total_income += slot["income"]
        total_expense += slot["expense"]
    return {
        "days": int(days),
        "rows": out_rows,
        "total_income": total_income,
        "total_expense": total_expense,
        "net": total_income - total_expense,
    }


def get_xp_log(
    character_id: int,
    conn: sqlite3.Connection,
    campaign_id: int | None = None,
    limit: int = 20,
) -> list[dict]:
    """Get XP grant history for a character."""
    query = """SELECT xg.amount, xg.source_key, xg.detail, xg.turn_number,
                      xg.campaign_id, xa.label as source_label, xg.created_at
               FROM character_xp_grants xg
               LEFT JOIN game_config_xp_awards xa ON xa.source_key = xg.source_key
               WHERE xg.character_id = ?"""
    params: list = [character_id]
    if campaign_id:
        query += " AND xg.campaign_id = ?"
        params.append(campaign_id)
    query += " ORDER BY xg.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_pending_xp(character_id: int, conn: sqlite3.Connection) -> int:
    """XP earned but not yet 'spent' at next long rest."""
    # In V2, XP is always available; this helper exists for UI display
    return get_total_xp(character_id, conn)


# ── Inventory & Equipment (TASK_20) ───────────────────────────────────────

VALID_SLOTS = {"main_hand", "off_hand", "body", "head", "hands"}


def equip_item(
    character_id: int,
    inventory_id: int,
    slot: str,
    conn: sqlite3.Connection,
) -> dict:
    """
    Equip an item from inventory to a slot.
    Unequips any existing item in that slot first.
    Returns {"ok": bool, "message": str, "unequipped_key": str|None}
    """
    if slot not in VALID_SLOTS:
        return {"ok": False, "message": f"Invalid slot: {slot}"}

    # Check item exists in inventory
    item_row = conn.execute(
        "SELECT id, item_key, weapon_key FROM character_inventory WHERE id = ? AND character_id = ?",
        (inventory_id, character_id)
    ).fetchone()
    if not item_row:
        return {"ok": False, "message": "Item not found in inventory"}

    item_key = item_row["item_key"] or item_row["weapon_key"]

    # Validate slot compatibility
    if not _slot_compatible(item_key, slot, conn):
        return {"ok": False, "message": f"Item cannot be equipped in slot: {slot}"}

    # Unequip current item in this slot
    unequipped_key = None
    current = conn.execute(
        "SELECT id, item_key, weapon_key FROM character_inventory WHERE character_id = ? AND slot = ? AND equipped = 1",
        (character_id, slot)
    ).fetchone()
    if current:
        conn.execute("UPDATE character_inventory SET equipped = 0, slot = NULL WHERE id = ?", (current["id"],))
        unequipped_key = current["item_key"] or current["weapon_key"]

    # Equip new item
    conn.execute(
        "UPDATE character_inventory SET equipped = 1, slot = ? WHERE id = ?",
        (slot, inventory_id)
    )
    conn.commit()

    logger.info("item_equipped", character_id=character_id, item=item_key, slot=slot)
    return {"ok": True, "message": f"Equipped {item_key} in {slot}", "unequipped_key": unequipped_key}


def unequip_item(
    character_id: int,
    slot: str,
    conn: sqlite3.Connection,
) -> dict:
    """Remove item from a slot (moves back to unequipped inventory)."""
    row = conn.execute(
        "SELECT id, item_key, weapon_key FROM character_inventory WHERE character_id = ? AND slot = ? AND equipped = 1",
        (character_id, slot)
    ).fetchone()
    if not row:
        return {"ok": False, "message": "No item in slot"}

    conn.execute("UPDATE character_inventory SET equipped = 0, slot = NULL WHERE id = ?", (row["id"],))
    conn.commit()
    item_key = row["item_key"] or row["weapon_key"]
    return {"ok": True, "message": f"Unequipped {item_key} from {slot}"}


def get_equipped_items(character_id: int, conn: sqlite3.Connection) -> dict[str, str]:
    """Returns {slot: item_key} for all equipped items."""
    rows = conn.execute(
        "SELECT slot, item_key, weapon_key FROM character_inventory WHERE character_id = ? AND equipped = 1",
        (character_id,)
    ).fetchall()
    result = {}
    for r in rows:
        if r["slot"]:
            result[r["slot"]] = r["item_key"] or r["weapon_key"] or ""
    return result


def get_inventory(character_id: int, conn: sqlite3.Connection) -> list[dict]:
    """Returns all inventory items with equipped status."""
    rows = conn.execute(
        """SELECT ci.id, ci.item_key, ci.weapon_key, ci.quantity,
                  ci.equipped, ci.slot, ci.source,
                  COALESCE(gi.label, gw.label, gc.label) as label,
                  COALESCE(gi.item_type, 'weapon') as item_type,
                  COALESCE(gi.value_gp, gw.value_gp, gc.base_price, 0) as value_gp
           FROM character_inventory ci
           LEFT JOIN game_config_items gi ON gi.key = ci.item_key
           LEFT JOIN game_config_weapons gw ON gw.key = ci.weapon_key
           LEFT JOIN game_config_consumables gc ON gc.key = ci.item_key
           WHERE ci.character_id = ?
           ORDER BY ci.equipped DESC, ci.acquired_at DESC""",
        (character_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def add_to_inventory(
    character_id: int,
    item_key: str,
    quantity: int = 1,
    source: str = "unknown",
    conn: sqlite3.Connection = None,
    item_type: str = "item",  # "item", "weapon", "consumable"
) -> bool:
    """Add an item to character inventory."""
    try:
        if item_type == "weapon":
            conn.execute(
                "INSERT INTO character_inventory (character_id, weapon_key, quantity, source) VALUES (?, ?, ?, ?)",
                (character_id, item_key, quantity, source)
            )
        else:
            conn.execute(
                "INSERT INTO character_inventory (character_id, item_key, quantity, source) VALUES (?, ?, ?, ?)",
                (character_id, item_key, quantity, source)
            )
        conn.commit()
        return True
    except Exception as e:
        logger.warning("add_to_inventory_failed", error=str(e))
        return False


def _slot_compatible(item_key: str, slot: str, conn: sqlite3.Connection) -> bool:
    """Check if an item can go in a given slot."""
    # Check weapons
    wrow = conn.execute(
        "SELECT weapon_type FROM game_config_weapons WHERE key = ?", (item_key,)
    ).fetchone()
    if wrow:
        weapon_type = wrow["weapon_type"]
        if slot in ("main_hand", "off_hand"):
            return True  # any weapon can go in main/off hand
        return False

    # Check armor/items
    irow = conn.execute(
        "SELECT item_type FROM game_config_items WHERE key = ?", (item_key,)
    ).fetchone()
    if irow:
        item_type = irow["item_type"]
        if item_type == "armor":
            return slot in ("body", "head", "hands", "off_hand")
    return False



# ── Healing System (TASK_23) ───────────────────────────────────────────────

def apply_healing_item(
    character_id: int,
    item_key: str,
    conn: sqlite3.Connection,
) -> dict:
    """
    Apply a healing consumable from inventory.
    Returns {"ok": bool, "hp_before": int, "hp_after": int, "message": str}
    """
    # Load character
    char_row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if not char_row:
        return {"ok": False, "message": "Character not found"}

    sheet = json.loads(char_row[0] or "{}")
    current_hp = int(sheet.get("current_hp", 0))
    max_hp = int(sheet.get("max_hp", 10))
    stats = sheet.get("stats") or {}

    # Check inventory (consumables or items)
    inv_row = conn.execute(
        """SELECT id FROM character_inventory
           WHERE character_id = ? AND (item_key = ? OR consumable_key = ?) LIMIT 1""",
        (character_id, item_key, item_key)
    ).fetchone()
    if not inv_row:
        return {"ok": False, "message": f"Nie masz {item_key} w ekwipunku."}

    # Load item effects
    heal_amount = 0
    con_mod = (int(stats.get("CON", 10)) - 10) // 2

    # Check consumables first
    crow = conn.execute(
        "SELECT effect_type, effect_dice, effect_bonus FROM game_config_consumables WHERE key = ?",
        (item_key,)
    ).fetchone()
    if crow and crow["effect_type"] == "heal_hp":
        dice_str = crow["effect_dice"] or "1d6"
        bonus = int(crow["effect_bonus"] or 0)
        from app.services.mechanic_resolver import parse_dice
        heal_amount = parse_dice(dice_str) + bonus + con_mod

    else:
        # Check game_config_items effect_json
        irow = conn.execute(
            "SELECT effect_json FROM game_config_items WHERE key = ?", (item_key,)
        ).fetchone()
        if irow and irow[0]:
            try:
                effect = json.loads(irow[0])
                heal_str = effect.get("heal", "")
                if heal_str:
                    from app.services.mechanic_resolver import parse_dice
                    heal_amount = parse_dice(str(heal_str)) + con_mod
            except Exception:
                pass

    if heal_amount <= 0:
        return {"ok": False, "message": f"Przedmiot {item_key} nie leczy."}

    new_hp = min(max_hp, current_hp + heal_amount)
    sheet["current_hp"] = new_hp
    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet), character_id)
    )

    # Remove one unit from inventory
    qty = conn.execute(
        "SELECT quantity FROM character_inventory WHERE id = ?", (inv_row[0],)
    ).fetchone()
    if qty and int(qty[0]) > 1:
        conn.execute("UPDATE character_inventory SET quantity = quantity - 1 WHERE id = ?", (inv_row[0],))
    else:
        conn.execute("DELETE FROM character_inventory WHERE id = ?", (inv_row[0],))
    conn.commit()

    return {
        "ok": True,
        "hp_before": current_hp,
        "hp_after": new_hp,
        "healed": new_hp - current_hp,
        "message": f"Wyleczono {new_hp - current_hp} HP.",
    }


def apply_rest(
    character_id: int,
    rest_type: str,
    conn: sqlite3.Connection,
    short_rest_count: int = 0,
) -> dict:
    """
    Apply short or long rest healing.
    Returns {"ok": bool, "hp_before": ..., "hp_after": ..., "mana_before": ..., "mana_after": ...}
    """
    char_row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if not char_row:
        return {"ok": False, "message": "Character not found"}

    sheet = json.loads(char_row[0] or "{}")
    stats = sheet.get("stats") or {}
    archetype = str(sheet.get("archetype", "warrior")).lower()

    current_hp = int(sheet.get("current_hp", 0))
    max_hp = int(sheet.get("max_hp", 10))
    current_mana = int(sheet.get("current_mana", 0))
    max_mana = int(sheet.get("max_mana", 0))

    con_mod = (int(stats.get("CON", 10)) - 10) // 2
    int_mod = (int(stats.get("INT", 10)) - 10) // 2

    if rest_type == "long":
        new_hp = max_hp
        new_mana = max_mana
    else:  # short
        heal = max(1, random.randint(1, 6) + con_mod)
        new_hp = min(max_hp, current_hp + heal)
        mana_recover = int_mod if archetype == "scholar" else 0
        new_mana = min(max_mana, current_mana + max(0, mana_recover))

    sheet["current_hp"] = new_hp
    sheet["current_mana"] = new_mana
    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet), character_id)
    )
    conn.commit()

    return {
        "ok": True,
        "rest_type": rest_type,
        "hp_before": current_hp,
        "hp_after": new_hp,
        "mana_before": current_mana,
        "mana_after": new_mana,
    }
