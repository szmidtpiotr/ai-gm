"""
Economy Service — V2 Phase 06 Tasks 20-26

Handles:
- TASK_20: Inventory & equipment (V2 slot system)
- TASK_22: Loot generation + claiming
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

# ── Wound Labels (TASK_24) ─────────────────────────────────────────────────

WOUND_LABELS = [
    (76,  None,       "#4caf50", None),        # Healthy — no label
    (51,  "Ranny",    "#ffc107", "minor_pain"),
    (26,  "Ciężko Ranny", "#ff9800", "impaired"),
    (11,  "Poważnie Ranny", "#f44336", "desperate"),
    (1,   "Na Skraju Śmierci", "#7f0000", "near_death"),
]


def get_wound_label(current_hp: int, max_hp: int) -> dict:
    """
    Returns wound label info for a given HP pair.
    """
    if max_hp <= 0:
        return {"label": None, "color": "#4caf50", "pct": 0}
    pct = (current_hp / max_hp) * 100
    for threshold, label, color, cue in WOUND_LABELS:
        if pct >= threshold:
            return {"label": label, "color": color, "pct": round(pct, 1), "cue": cue}
    return {"label": "Na Skraju Śmierci", "color": "#7f0000", "pct": 0, "cue": "near_death"}


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


# ── Loot System (TASK_22) ──────────────────────────────────────────────────

def generate_combat_loot(
    campaign_id: int,
    character_id: int,
    enemy_keys: list[str],
    location_key: str | None,
    conn: sqlite3.Connection,
) -> dict:
    """
    Generate loot after combat victory. Creates a combat_loot record.
    Returns {"loot_id": int, "items": list[dict]}
    """
    all_items = []
    total_gold = 0

    for enemy_key in enemy_keys:
        # Get base enemy key (strip instance suffix like "goblin_1" → "goblin")
        base_key = enemy_key.split("_")[0] if "_" in enemy_key else enemy_key
        erow = conn.execute(
            "SELECT loot_table_key, drop_chance, tier FROM game_config_enemies WHERE key = ?",
            (base_key,)
        ).fetchone()
        if not erow:
            continue

        # Check drop chance
        if random.random() > float(erow["drop_chance"] or 1.0):
            continue

        loot_table_key = erow["loot_table_key"]
        if not loot_table_key:
            # Fallback: gold by tier
            tier_gold = {"weak": 3, "standard": 8, "elite": 20, "boss": 60}
            gold = tier_gold.get(erow["tier"] or "standard", 5)
            total_gold += random.randint(1, gold)
            continue

        # Load loot table
        lrow = conn.execute(
            "SELECT gold_min, gold_max FROM game_config_loot_tables WHERE key = ?",
            (loot_table_key,)
        ).fetchone()
        if lrow:
            gold_min = int(lrow["gold_min"] or 0)
            gold_max = int(lrow["gold_max"] or 0)
            if gold_max > 0:
                total_gold += random.randint(gold_min, gold_max)

        # Load loot entries
        entry_rows = conn.execute(
            """SELECT item_key, weapon_key, consumable_key, weight, qty_min, qty_max
               FROM game_config_loot_entries WHERE loot_table_key = ?""",
            (loot_table_key,)
        ).fetchall()

        for entry in entry_rows:
            roll = random.randint(1, 100)
            if roll > int(entry["weight"] or 100):
                continue
            qty = random.randint(
                int(entry["qty_min"] or 1),
                int(entry["qty_max"] or 1)
            )
            item_key = entry["item_key"] or entry["weapon_key"] or entry["consumable_key"]
            if item_key:
                all_items.append({"item_key": item_key, "quantity": qty, "claimed": False})

    # Add gold as item if any
    if total_gold > 0:
        all_items.append({"item_key": "gold_coins", "quantity": total_gold,
                          "claimed": False, "is_gold": True})

    # Find location ID
    loc_id = None
    if location_key:
        loc_row = conn.execute(
            "SELECT id FROM game_locations WHERE key = ?", (location_key,)
        ).fetchone()
        if loc_row:
            loc_id = loc_row[0]

    # Create combat_loot record
    try:
        cursor = conn.execute(
            """INSERT INTO combat_loot
               (campaign_id, character_id, combat_location_id, loot_items, status)
               VALUES (?, ?, ?, ?, 'available')""",
            (campaign_id, character_id, loc_id,
             json.dumps(all_items, ensure_ascii=False))
        )
        conn.commit()
        loot_id = cursor.lastrowid
        logger.info("combat_loot_generated", campaign_id=campaign_id, items=len(all_items))
        return {"loot_id": loot_id, "items": all_items}
    except Exception as e:
        logger.warning("loot_generate_failed", error=str(e))
        return {"loot_id": None, "items": []}


def claim_loot(
    character_id: int,
    loot_id: int,
    item_keys_to_claim: list[str],
    current_location_key: str | None,
    conn: sqlite3.Connection,
) -> dict:
    """
    Claim selected items from a loot record.
    Returns {"ok": bool, "claimed": list, "gold": int, "message": str}
    """
    row = conn.execute(
        "SELECT * FROM combat_loot WHERE id = ? AND character_id = ?",
        (loot_id, character_id)
    ).fetchone()
    if not row:
        return {"ok": False, "message": "Loot not found"}

    status = row["status"]
    if status in ("claimed", "expired", "discarded"):
        return {"ok": False, "message": f"Loot is {status}"}

    # Validate player is at the right location
    if row["combat_location_id"] and current_location_key:
        loc_row = conn.execute(
            "SELECT id FROM game_locations WHERE key = ?", (current_location_key,)
        ).fetchone()
        if loc_row and loc_row[0] != row["combat_location_id"]:
            return {"ok": False, "message": "Nie jesteś już przy miejscu walki."}

    items = json.loads(row["loot_items"] or "[]")
    claimed = []
    total_gold = 0

    for item in items:
        if item.get("claimed"):
            continue
        item_key = item.get("item_key", "")
        if item_keys_to_claim and item_key not in item_keys_to_claim:
            continue

        # Gold handling
        if item.get("is_gold") or item_key == "gold_coins":
            qty = int(item.get("quantity", 0))
            total_gold += qty
            item["claimed"] = True
            claimed.append({"type": "gold", "amount": qty})
            continue

        # Regular item
        qty = int(item.get("quantity", 1))
        item["claimed"] = True
        # Determine item type
        wrow = conn.execute(
            "SELECT key FROM game_config_weapons WHERE key = ?", (item_key,)
        ).fetchone()
        itype = "weapon" if wrow else "item"
        add_to_inventory(character_id, item_key, qty, "loot", conn, itype)
        claimed.append({"type": "item", "item_key": item_key, "quantity": qty})

    # Add gold to character
    if total_gold > 0:
        char_row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        if char_row:
            sheet = json.loads(char_row[0] or "{}")
            sheet["gold"] = int(sheet.get("gold", 0)) + total_gold
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet), character_id)
            )

    # Update loot status
    all_claimed = all(item.get("claimed") for item in items)
    new_status = "claimed" if all_claimed else "partial"
    conn.execute(
        "UPDATE combat_loot SET loot_items = ?, status = ? WHERE id = ?",
        (json.dumps(items), new_status, loot_id)
    )
    conn.commit()

    return {
        "ok": True,
        "claimed": claimed,
        "gold": total_gold,
        "status": new_status,
        "message": f"Odebrano {len(claimed)} {'przedmiotów' if len(claimed) != 1 else 'przedmiot'}.",
    }


def expire_loot_on_location_change(
    character_id: int,
    old_macro_key: str,
    new_macro_key: str,
    long_rest_count: int,
    conn: sqlite3.Connection,
) -> None:
    """Expire partial loot when player moves to different macro or rests."""
    if old_macro_key == new_macro_key:
        return
    conn.execute(
        """UPDATE combat_loot SET status = 'expired'
           WHERE character_id = ? AND status IN ('available','partial')""",
        (character_id,)
    )
    conn.commit()


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
