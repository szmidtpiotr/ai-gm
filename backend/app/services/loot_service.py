"""Phase 8C — loot and inventory service."""

from __future__ import annotations

import random
import sqlite3
from typing import Any

from app.core.logging import get_logger

LOOT_DB_PATH = "/data/ai_gm.db"

logger = get_logger(__name__)

_SLOT_VALUES = {"main_hand", "off_hand", "armor"}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(LOOT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_loot_entry(row: sqlite3.Row, total_weight: int) -> dict[str, Any]:
    weight = max(1, int(row["weight"] or 0))
    chance = float(weight / total_weight) if total_weight > 0 else 0.0
    return {
        "item_key": row["item_key"],
        "weapon_key": row["weapon_key"],
        "consumable_key": row["consumable_key"],
        "chance": chance,
        "quantity_min": max(1, int(row["qty_min"] or 1)),
        "quantity_max": max(1, int(row["qty_max"] or 1)),
        "weight": weight,
    }


def _catalog_entry(conn: sqlite3.Connection, loot: dict[str, Any]) -> tuple[str, str, str] | None:
    if loot.get("item_key"):
        key = str(loot["item_key"]).strip()
        row = conn.execute(
            "SELECT key, label, item_type FROM game_config_items WHERE key = ? AND is_active = 1",
            (key,),
        ).fetchone()
        if not row:
            return None
        item_type = str(row["item_type"] or "item").strip().lower() or "item"
        return str(row["key"]), str(row["label"] or row["key"]), item_type

    if loot.get("weapon_key"):
        key = str(loot["weapon_key"]).strip()
        row = conn.execute(
            "SELECT key, label FROM game_config_weapons WHERE key = ? AND is_active = 1",
            (key,),
        ).fetchone()
        if not row:
            return None
        return str(row["key"]), str(row["label"] or row["key"]), "weapon"

    if loot.get("consumable_key"):
        key = str(loot["consumable_key"]).strip()
        row = conn.execute(
            "SELECT key, label FROM game_config_consumables WHERE key = ? AND is_active = 1",
            (key,),
        ).fetchone()
        if not row:
            return None
        return str(row["key"]), str(row["label"] or row["key"]), "consumable"

    return None


def get_loot_table(enemy_key: str) -> list[dict]:
    """
    Resolve enemy loot table into weighted entries.
    Returns [] when enemy or loot table is missing.
    """
    ek = str(enemy_key or "").strip()
    if not ek:
        return []

    with _conn() as conn:
        enemy = conn.execute(
            "SELECT loot_table_key FROM game_config_enemies WHERE key = ?",
            (ek,),
        ).fetchone()
        if not enemy or not enemy["loot_table_key"]:
            return []
        table_key = str(enemy["loot_table_key"])
        rows = conn.execute(
            """
            SELECT e.item_key, e.weapon_key, e.consumable_key, e.weight, e.qty_min, e.qty_max
            FROM game_config_loot_entries e
            JOIN game_config_loot_tables t ON t.key = e.loot_table_key
            WHERE e.loot_table_key = ? AND t.is_active = 1
            ORDER BY e.id ASC
            """,
            (table_key,),
        ).fetchall()
    if not rows:
        return []
    total_weight = sum(max(1, int(r["weight"] or 0)) for r in rows)
    return [_row_to_loot_entry(r, total_weight) for r in rows]


def roll_loot(enemy_key: str) -> list[dict]:
    """
    Roll one weighted loot entry for enemy_key.
    Returns [] if enemy has no loot table or drop chance fails.
    """
    ek = str(enemy_key or "").strip()
    if not ek:
        return []
    with _conn() as conn:
        enemy = conn.execute(
            "SELECT loot_table_key, drop_chance FROM game_config_enemies WHERE key = ?",
            (ek,),
        ).fetchone()
    if not enemy or not enemy["loot_table_key"]:
        return []

    drop_chance = float(enemy["drop_chance"] if enemy["drop_chance"] is not None else 1.0)
    if random.random() > drop_chance:
        return []

    entries = get_loot_table(ek)
    if not entries:
        return []

    r = random.random()
    acc = 0.0
    chosen = entries[-1]
    for entry in entries:
        acc += float(entry.get("chance") or 0.0)
        if r <= acc:
            chosen = entry
            break
    qmin = max(1, int(chosen.get("quantity_min") or 1))
    qmax = max(qmin, int(chosen.get("quantity_max") or qmin))
    qty = random.randint(qmin, qmax)
    return [
        {
            "item_key": chosen.get("item_key"),
            "weapon_key": chosen.get("weapon_key"),
            "consumable_key": chosen.get("consumable_key"),
            "quantity": qty,
        }
    ]


def grant_loot_to_character(character_id: int, loot_items: list[dict], source: str = "loot") -> list[dict]:
    """
    Grant rolled loot to character inventory with catalog validation.
    Item/consumable stack by key; weapons are always inserted as separate rows.
    """
    cid = int(character_id)
    if not isinstance(loot_items, list):
        return []

    src = str(source or "loot").strip() or "loot"
    granted: list[dict] = []
    with _conn() as conn:
        ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not ch:
            raise ValueError("character not found")

        for raw in loot_items:
            if not isinstance(raw, dict):
                continue
            qty = max(1, int(raw.get("quantity") or 1))
            cat = _catalog_entry(conn, raw)
            if not cat:
                logger.warning("loot_catalog_key_missing", character_id=cid, loot_item=raw)
                continue
            key, label, item_type = cat
            if item_type == "weapon":
                conn.execute(
                    """
                    INSERT INTO character_inventory
                    (character_id, item_key, weapon_key, consumable_key, quantity, equipped, slot, source, meta_json)
                    VALUES (?, NULL, ?, NULL, ?, 0, NULL, ?, NULL)
                    """,
                    (cid, key, qty, src),
                )
            elif item_type == "consumable":
                existing = conn.execute(
                    """
                    SELECT id, quantity FROM character_inventory
                    WHERE character_id = ? AND consumable_key = ? AND weapon_key IS NULL AND item_key IS NULL
                    ORDER BY id ASC LIMIT 1
                    """,
                    (cid, key),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE character_inventory SET quantity = ? WHERE id = ?",
                        (int(existing["quantity"] or 0) + qty, int(existing["id"])),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO character_inventory
                        (character_id, item_key, weapon_key, consumable_key, quantity, equipped, slot, source, meta_json)
                        VALUES (?, NULL, NULL, ?, ?, 0, NULL, ?, NULL)
                        """,
                        (cid, key, qty, src),
                    )
            else:
                existing = conn.execute(
                    """
                    SELECT id, quantity FROM character_inventory
                    WHERE character_id = ? AND item_key = ? AND weapon_key IS NULL AND consumable_key IS NULL
                    ORDER BY id ASC LIMIT 1
                    """,
                    (cid, key),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE character_inventory SET quantity = ? WHERE id = ?",
                        (int(existing["quantity"] or 0) + qty, int(existing["id"])),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO character_inventory
                        (character_id, item_key, weapon_key, consumable_key, quantity, equipped, slot, source, meta_json)
                        VALUES (?, ?, NULL, NULL, ?, 0, NULL, ?, NULL)
                        """,
                        (cid, key, qty, src),
                    )

            granted.append({"label": label, "item_type": item_type, "quantity": qty, "source": src, "key": key})

        conn.commit()
    return granted


def get_character_inventory(character_id: int) -> list[dict]:
    """Return unified inventory rows for a character."""
    cid = int(character_id)
    with _conn() as conn:
        ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not ch:
            raise ValueError("character not found")
        rows = conn.execute(
            """
            SELECT ci.id, ci.slot, ci.equipped, ci.quantity, ci.source, ci.acquired_at,
                   ci.item_key, ci.weapon_key, ci.consumable_key,
                   gi.label AS item_label, gi.item_type AS item_kind,
                   gw.label AS weapon_label,
                   gc.label AS consumable_label
            FROM character_inventory ci
            LEFT JOIN game_config_items gi ON gi.key = ci.item_key
            LEFT JOIN game_config_weapons gw ON gw.key = ci.weapon_key
            LEFT JOIN game_config_consumables gc ON gc.key = ci.consumable_key
            WHERE ci.character_id = ?
            ORDER BY ci.id ASC
            """,
            (cid,),
        ).fetchall()

    out: list[dict] = []
    for r in rows:
        if r["weapon_key"]:
            label = str(r["weapon_label"] or r["weapon_key"])
            item_type = "weapon"
            key = r["weapon_key"]
        elif r["consumable_key"]:
            label = str(r["consumable_label"] or r["consumable_key"])
            item_type = "consumable"
            key = r["consumable_key"]
        else:
            label = str(r["item_label"] or r["item_key"])
            item_type = str(r["item_kind"] or "item")
            key = r["item_key"]
        out.append(
            {
                "id": int(r["id"]),
                "slot": r["slot"],
                "equipped": int(r["equipped"] or 0),
                "quantity": int(r["quantity"] or 0),
                "source": r["source"],
                "acquired_at": r["acquired_at"],
                "label": label,
                "item_type": item_type,
                "key": key,
            }
        )
    return out


def equip_item(character_id: int, inventory_id: int, slot: str) -> dict:
    """
    Equip an inventory entry on a slot and un-equip previous entry in same slot.
    """
    cid = int(character_id)
    iid = int(inventory_id)
    s = str(slot or "").strip().lower()
    if s not in _SLOT_VALUES:
        raise ValueError("invalid slot")

    with _conn() as conn:
        ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not ch:
            raise ValueError("character not found")

        row = conn.execute(
            "SELECT id FROM character_inventory WHERE id = ? AND character_id = ?",
            (iid, cid),
        ).fetchone()
        if not row:
            raise ValueError("inventory entry not found")

        conn.execute(
            "UPDATE character_inventory SET equipped = 0, slot = NULL WHERE character_id = ? AND slot = ?",
            (cid, s),
        )
        conn.execute(
            "UPDATE character_inventory SET equipped = 1, slot = ? WHERE id = ?",
            (s, iid),
        )
        conn.commit()

    updated = [x for x in get_character_inventory(cid) if int(x["id"]) == iid]
    if not updated:
        raise ValueError("inventory entry not found")
    return updated[0]


def unequip_item(character_id: int, inventory_id: int) -> dict:
    """Clear equipped flag and slot for one inventory row (8E-3)."""
    cid = int(character_id)
    iid = int(inventory_id)
    with _conn() as conn:
        ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not ch:
            raise ValueError("character not found")

        row = conn.execute(
            "SELECT id FROM character_inventory WHERE id = ? AND character_id = ?",
            (iid, cid),
        ).fetchone()
        if not row:
            raise ValueError("inventory entry not found")

        conn.execute(
            "UPDATE character_inventory SET equipped = 0, slot = NULL WHERE id = ? AND character_id = ?",
            (iid, cid),
        )
        conn.commit()

    updated = [x for x in get_character_inventory(cid) if int(x["id"]) == iid]
    if not updated:
        raise ValueError("inventory entry not found")
    return updated[0]


def delete_inventory_item(character_id: int, inventory_id: int, *, force: bool = False) -> dict:
    """Delete a character inventory entry (guard equipped unless force=True)."""
    cid = int(character_id)
    iid = int(inventory_id)
    with _conn() as conn:
        ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not ch:
            raise ValueError("character not found")
        row = conn.execute(
            """
            SELECT id, character_id, item_key, weapon_key, consumable_key, quantity, equipped, slot, source, acquired_at
            FROM character_inventory
            WHERE id = ? AND character_id = ?
            """,
            (iid, cid),
        ).fetchone()
        if not row:
            raise ValueError("inventory entry not found")
        if int(row["equipped"] or 0) == 1 and not force:
            raise ValueError("equipped item requires force")
        conn.execute("DELETE FROM character_inventory WHERE id = ? AND character_id = ?", (iid, cid))
        conn.commit()
    return {
        "id": int(row["id"]),
        "character_id": int(row["character_id"]),
        "item_key": row["item_key"],
        "weapon_key": row["weapon_key"],
        "consumable_key": row["consumable_key"],
        "quantity": int(row["quantity"] or 0),
        "equipped": int(row["equipped"] or 0),
        "slot": row["slot"],
        "source": row["source"],
        "acquired_at": row["acquired_at"],
    }


def list_config_items(item_type: str | None = None) -> list[dict]:
    """List game_config_items, optionally filtered by item_type."""
    t = str(item_type or "").strip().lower()
    with _conn() as conn:
        if t:
            rows = conn.execute(
                """
                SELECT key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active
                FROM game_config_items
                WHERE item_type = ?
                ORDER BY label COLLATE NOCASE ASC, key ASC
                """,
                (t,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active
                FROM game_config_items
                ORDER BY label COLLATE NOCASE ASC, key ASC
                """
            ).fetchall()
    return [
        {
            "key": r["key"],
            "label": r["label"],
            "item_type": r["item_type"],
            "description": r["description"],
            "value_gp": int(r["value_gp"] or 0),
            "weight": float(r["weight"] or 0.0),
            "weight_kg": float(r["weight_kg"] or 0.0),
            "effect_json": r["effect_json"],
            "is_active": bool(r["is_active"]),
        }
        for r in rows
    ]


def get_character_gold(character_id: int) -> int:
    """Return current gold_gp for a character (0 if column missing treated as 0)."""
    cid = int(character_id)
    with _conn() as conn:
        row = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise ValueError("character not found")
        return int(row["gold_gp"] or 0)


def apply_character_gold_delta(character_id: int, delta: int, reason: str | None = None) -> int:
    """
    Atomically adjust gold_gp by delta (must not go below 0).
    ``reason`` is accepted for API compatibility; not persisted in this phase.
    """
    _ = reason
    if int(delta) == 0:
        raise ValueError("delta must be non-zero")
    cid = int(character_id)
    d = int(delta)
    with _conn() as conn:
        row = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise ValueError("character not found")
        cur = int(row["gold_gp"] or 0)
        new_g = cur + d
        if new_g < 0:
            raise ValueError("gold_gp would be negative")
        conn.execute("UPDATE characters SET gold_gp = ? WHERE id = ?", (new_g, cid))
    return new_g


def get_config_item(key: str) -> dict | None:
    """Get one game_config_item by key."""
    k = str(key or "").strip()
    if not k:
        return None
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active
            FROM game_config_items
            WHERE key = ?
            """,
            (k,),
        ).fetchone()
    if not row:
        return None
    return {
        "key": row["key"],
        "label": row["label"],
        "item_type": row["item_type"],
        "description": row["description"],
        "value_gp": int(row["value_gp"] or 0),
        "weight": float(row["weight"] or 0.0),
        "weight_kg": float(row["weight_kg"] or 0.0),
        "effect_json": row["effect_json"],
        "is_active": bool(row["is_active"]),
    }
