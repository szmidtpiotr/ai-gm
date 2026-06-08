"""Phase 8C / T18 — loot, inventory and consumable runtime."""

from __future__ import annotations

import json
import random
import re
import sqlite3
from typing import Any

from app.core.logging import get_logger
from app.services.dice import parse_character_sheet
from app.services.effect_json_migration import legacy_effect_fields_from_json

LOOT_DB_PATH = "/data/ai_gm.db"

logger = get_logger(__name__)

_SLOT_VALUES = {
    "head",
    "torso",
    "l_arm",
    "r_arm",
    "l_leg",
    "r_leg",
    "main_hand",
    "off_hand",
}

# Stage 5 E1/E2/E4: armor_coverage enum → which slots a single equipped row
# claims. 'full' anchors to torso but locks all four limbs simultaneously.
_ARMOR_COVERAGE_TO_SLOTS = {
    "head": ("head",),
    "torso": ("torso",),
    "limb_arm": ("l_arm", "r_arm"),  # caller picks one at equip time
    "limb_leg": ("l_leg", "r_leg"),  # caller picks one at equip time
    "full": ("torso", "l_arm", "r_arm", "l_leg", "r_leg"),
}
_VALID_ARMOR_COVERAGE = frozenset(_ARMOR_COVERAGE_TO_SLOTS.keys())

# Stage 5 follow-up: weapon_slot enum → which slots a weapon can occupy.
# 'two_handed' anchors at main_hand but locks off_hand too.
_VALID_WEAPON_SLOT = frozenset({"main_hand", "two_handed", "off_hand_only", "either"})

# When game_config_items.item_type is wrong (e.g. quest) but effect_* matches consumable mechanics (8H).
_CONSUMABLE_EFFECT_SIGNAL = frozenset(
    {"heal_hp", "restore_mana", "remove_condition", "add_condition", "stat_buff"}
)
_SUPPORTED_ITEM_USE_EFFECTS = {"heal_hp", "apply_condition", "remove_condition", "narrative_only"}


def _inventory_rows_sql(effect_json_col_sql: str, effect_type_col_sql: str, effect_dice_col_sql: str) -> str:
    """Select unified inventory rows; new schema uses effect_json, old schema may still use effect_*."""
    return f"""
            SELECT ci.id, ci.slot, ci.equipped, ci.quantity, ci.source, ci.acquired_at,
                   ci.item_key, ci.weapon_key, ci.consumable_key,
                   ci.label AS narrative_label, ci.meta_json AS ci_meta_json,
                   gi.label AS item_label, gi.item_type AS item_kind,
                   gi.armor_coverage AS gi_armor_coverage,
                   {effect_json_col_sql}, {effect_type_col_sql}, {effect_dice_col_sql},
                   gw.label AS weapon_label,
                   gw.weapon_slot AS gw_weapon_slot,
                   gc.label AS consumable_label,
                   gc_item.key AS consumable_catalog_item_key,
                   gc_item.label AS consumable_by_item_key_label
            FROM character_inventory ci
            LEFT JOIN game_config_items gi ON gi.key = ci.item_key
            LEFT JOIN game_config_weapons gw ON gw.key = ci.weapon_key
                OR (
                    ci.weapon_key LIKE 'weapon_%'
                    AND gw.key = SUBSTR(ci.weapon_key, 8)
                )
            LEFT JOIN game_config_consumables gc ON gc.key = ci.consumable_key
                OR (
                    ci.consumable_key LIKE 'consumable_%'
                    AND gc.key = SUBSTR(ci.consumable_key, 12)
                )
            LEFT JOIN game_config_consumables gc_item ON gc_item.key = ci.item_key
                AND ci.weapon_key IS NULL
                AND (ci.consumable_key IS NULL OR ci.consumable_key = '')
            WHERE ci.character_id = ?
            ORDER BY ci.id ASC
            """


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(LOOT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _roll_dice_value(expr: str) -> int:
    raw = str(expr or "").strip().lower()
    # Supports: "2d6", "d8", "2d6+4", "1d4-1"
    m = re.match(r"^(\d*)d(\d+)([+-]\d+)?$", raw)
    if not m:
        raise ValueError("invalid_effect_value")
    n = int(m.group(1) or 1)
    sides = int(m.group(2))
    bonus = int(m.group(3) or 0)
    return sum(random.randint(1, sides) for _ in range(max(1, n))) + bonus


def _normalize_sheet_conditions(sheet: dict[str, Any]) -> list[dict[str, Any]]:
    raw = sheet.get("conditions")
    if not isinstance(raw, list):
        raw = []
    out: list[dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, dict):
            key = str(entry.get("key") or "").strip().lower()
            if not key:
                continue
            out.append(
                {
                    "key": key,
                    "label": str(entry.get("label") or key).strip() or key,
                    "effect_json": entry.get("effect_json"),
                    "source_item_key": entry.get("source_item_key"),
                    "applied_at": entry.get("applied_at"),
                }
            )
        elif isinstance(entry, str) and entry.strip():
            key = entry.strip().lower()
            out.append({"key": key, "label": key, "effect_json": None, "source_item_key": None, "applied_at": None})
    sheet["conditions"] = out
    return out


def _decode_effect_json(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _effect_payloads_from_item_row(row: sqlite3.Row) -> list[dict[str, Any]]:
    parsed = _decode_effect_json(row["effect_json"] if "effect_json" in row.keys() else None)
    if parsed and isinstance(parsed.get("effects"), list):
        return [e for e in parsed["effects"] if isinstance(e, dict)]

    effect_type = str(row["effect_type"] if "effect_type" in row.keys() and row["effect_type"] is not None else "").strip().lower()
    if not effect_type:
        return []
    effect_bonus = int(row["effect_bonus"] if "effect_bonus" in row.keys() and row["effect_bonus"] is not None else 0)
    effect_dice = str(row["effect_dice"] if "effect_dice" in row.keys() and row["effect_dice"] is not None else "").strip()
    effect_value: int | str | None = None
    if effect_dice:
        effect_value = effect_dice
    elif effect_bonus:
        effect_value = effect_bonus

    if effect_type == "heal_hp":
        return [{"type": "heal_hp", "value": effect_value if effect_value is not None else 0}]
    if effect_type == "restore_mana":
        return [{"type": "restore_mana", "value": effect_value if effect_value is not None else 0}]
    if effect_type == "remove_condition":
        condition_key = str(row["effect_target"] if "effect_target" in row.keys() and row["effect_target"] is not None else "").strip().lower()
        return [{"type": "remove_condition", "condition_key": condition_key}] if condition_key else []
    if effect_type == "add_condition":
        condition_key = str(row["effect_target"] if "effect_target" in row.keys() and row["effect_target"] is not None else "").strip().lower()
        return [{"type": "apply_condition", "condition_key": condition_key}] if condition_key else []
    return []


def _condition_catalog_row(conn: sqlite3.Connection, condition_key: str) -> sqlite3.Row | None:
    try:
        return conn.execute(
            """
            SELECT key, label, effect_json, stackable
            FROM game_config_conditions
            WHERE key = ? AND COALESCE(is_active, 1) = 1
            LIMIT 1
            """,
            (str(condition_key or "").strip().lower(),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None


def _sync_player_state_to_active_combat(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
    current_hp: int,
    conditions: list[dict[str, Any]],
) -> None:
    try:
        row = conn.execute(
            """
            SELECT combatants
            FROM active_combat
            WHERE campaign_id = ? AND character_id = ?
            LIMIT 1
            """,
            (int(campaign_id), int(character_id)),
        ).fetchone()
    except sqlite3.OperationalError:
        return
    if not row:
        return
    try:
        combatants = json.loads(row["combatants"] or "[]")
    except Exception:
        return
    if not isinstance(combatants, list):
        return
    changed = False
    for combatant in combatants:
        if not isinstance(combatant, dict) or str(combatant.get("id")) != "player":
            continue
        combatant["hp_current"] = int(current_hp)
        combatant["conditions"] = conditions
        changed = True
        break
    if changed:
        conn.execute(
            "UPDATE active_combat SET combatants = ?, updated_at = datetime('now') WHERE campaign_id = ? AND character_id = ?",
            (json.dumps(combatants, ensure_ascii=False), int(campaign_id), int(character_id)),
        )


def _row_to_loot_entry(row: sqlite3.Row) -> dict[str, Any]:
    # `weight` is used as direct per-entry drop percent in range 1..100.
    weight = max(1, min(100, int(row["weight"] or 0)))
    chance = float(weight / 100.0)
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
        try:
            row = conn.execute(
                """
                SELECT key, label, item_type FROM game_config_items
                WHERE key = ? AND is_active = 1 AND COALESCE(approved, 1) = 1
                """,
                (key,),
            ).fetchone()
        except sqlite3.OperationalError:
            row = conn.execute(
                """
                SELECT key, label, item_type FROM game_config_items
                WHERE key = ? AND is_active = 1
                """,
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
    return [_row_to_loot_entry(r) for r in rows]


def roll_loot(enemy_key: str) -> list[dict]:
    """
    Roll each loot-table entry independently for enemy_key.
    Returns [] when enemy or loot table is missing, or no entry roll succeeds.
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

    entries = get_loot_table(ek)
    if not entries:
        return []

    rolled: list[dict] = []
    for entry in entries:
        if random.random() > float(entry.get("chance") or 0.0):
            continue
        qmin = max(1, int(entry.get("quantity_min") or 1))
        qmax = max(qmin, int(entry.get("quantity_max") or qmin))
        qty = random.randint(qmin, qmax)
        rolled.append(
            {
                "item_key": entry.get("item_key"),
                "weapon_key": entry.get("weapon_key"),
                "consumable_key": entry.get("consumable_key"),
                "quantity": qty,
            }
        )
    return rolled


def roll_gold_drop(enemy_key: str) -> int:
    """
    Roll gold reward for an enemy from its loot table range.
    Returns 0 when enemy/table missing or range is empty.
    """
    ek = str(enemy_key or "").strip()
    if not ek:
        return 0
    try:
        with _conn() as conn:
            row = conn.execute(
                """
                SELECT t.gold_min, t.gold_max
                FROM game_config_enemies e
                JOIN game_config_loot_tables t ON t.key = e.loot_table_key
                WHERE e.key = ? AND t.is_active = 1
                LIMIT 1
                """,
                (ek,),
            ).fetchone()
    except sqlite3.Error:
        # Backward compatibility with DBs created before gold columns existed.
        return 0
    if not row:
        return 0
    gmin = max(0, int(row["gold_min"] or 0))
    gmax = max(0, int(row["gold_max"] or 0))
    if gmax <= 0:
        return 0
    if gmax < gmin:
        gmax = gmin
    return random.randint(gmin, gmax)


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
            else:
                # 8H: wszystkie wiersze z game_config_items (w tym consumable) stackują po item_key
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


def preview_loot_items(loot_items: list[dict], source: str = "loot") -> list[dict]:
    """
    Validate/normalize loot payload against catalogs without writing inventory.
    Returns the same display contract as grant_loot_to_character.
    """
    if not isinstance(loot_items, list):
        return []
    src = str(source or "loot").strip() or "loot"
    out: list[dict] = []
    with _conn() as conn:
        for raw in loot_items:
            if not isinstance(raw, dict):
                continue
            qty = max(1, int(raw.get("quantity") or 1))
            cat = _catalog_entry(conn, raw)
            if not cat:
                continue
            key, label, item_type = cat
            out.append({"label": label, "item_type": item_type, "quantity": qty, "source": src, "key": key})
    return out


def get_character_inventory(character_id: int) -> list[dict]:
    """Return unified inventory rows for a character."""
    cid = int(character_id)
    with _conn() as conn:
        ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not ch:
            raise ValueError("character not found")
        try:
            rows = conn.execute(
                _inventory_rows_sql(
                    "gi.effect_json AS gi_effect_json",
                    "gi.effect_type AS gi_effect_type",
                    "gi.effect_dice AS gi_effect_dice",
                ),
                (cid,),
            ).fetchall()
        except sqlite3.OperationalError:
            try:
                rows = conn.execute(
                    _inventory_rows_sql(
                        "NULL AS gi_effect_json",
                        "gi.effect_type AS gi_effect_type",
                        "gi.effect_dice AS gi_effect_dice",
                    ),
                    (cid,),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    _inventory_rows_sql(
                        "NULL AS gi_effect_json",
                        "NULL AS gi_effect_type",
                        "NULL AS gi_effect_dice",
                    ),
                    (cid,),
                ).fetchall()

    out: list[dict] = []
    for r in rows:
        # T46: Narrative item — label stored directly, no catalog key.
        # item_key may be '__narrative__' sentinel (satisfies inv_xor CHECK constraint).
        narrative_label = r["narrative_label"] if "narrative_label" in r.keys() else None
        if narrative_label and r["item_key"] in (None, "__narrative__") and not r["weapon_key"] and not r["consumable_key"]:
            try:
                meta = json.loads(r["ci_meta_json"] or "{}") if "ci_meta_json" in r.keys() else {}
            except Exception:
                meta = {}
            item_type = str(meta.get("item_type") or "narrative").strip().lower() or "narrative"
            out.append({
                "id": int(r["id"]),
                "slot": None,
                "equipped": 0,
                "quantity": int(r["quantity"] or 1),
                "source": r["source"],
                "acquired_at": r["acquired_at"],
                "label": narrative_label,
                "item_type": item_type,
                "key": None,
                "can_use": False,
                "description": meta.get("description"),
                "is_narrative": True,
            })
            continue
        if r["weapon_key"]:
            label = str(r["weapon_label"] or r["weapon_key"])
            item_type = "weapon"
            key = r["weapon_key"]
        elif r["consumable_key"]:
            label = str(r["consumable_label"] or r["consumable_key"])
            item_type = "consumable"
            key = r["consumable_catalog_item_key"] or r["consumable_key"]
        else:
            raw_kind = str(r["item_kind"] or "item").strip().lower()
            label = str(r["item_label"] or r["item_key"])
            key = r["item_key"]
            # Legacy consumables table OR catalog effect_type → consumable (fixes wrong item_type on unified catalog rows).
            legacy = legacy_effect_fields_from_json(r["gi_effect_json"]) or {}
            et = str(legacy.get("effect_type") or r["gi_effect_type"] or "").strip().lower()
            dice = str(legacy.get("effect_dice") or r["gi_effect_dice"] or "").strip()
            if r["consumable_catalog_item_key"]:
                item_type = "consumable"
                clab = r["consumable_by_item_key_label"]
                if clab:
                    label = str(clab)
            elif et in _CONSUMABLE_EFFECT_SIGNAL:
                item_type = "consumable"
            elif raw_kind == "quest" and dice:
                # Mis-tagged elixirs/potions still stored as quest; dice + consumable-like row → treat as consumable.
                item_type = "consumable"
            else:
                item_type = raw_kind or "item"
        # Stage 5 E4: surface armor_coverage + the list of slots a full-coverage
        # anchor row is locking, so the frontend can render limb cards as "covered".
        armor_coverage_raw = None
        weapon_slot_raw = None
        try:
            armor_coverage_raw = r["gi_armor_coverage"]
        except (KeyError, IndexError):
            pass
        try:
            weapon_slot_raw = r["gw_weapon_slot"]
        except (KeyError, IndexError):
            pass
        coverage = (armor_coverage_raw or "").lower() if item_type == "armor" else None
        wslot = (weapon_slot_raw or "").lower() if item_type == "weapon" else None
        covered_slots: list[str] = []
        if item_type == "armor" and int(r["equipped"] or 0) == 1 and coverage == "full":
            covered_slots = list(_ARMOR_COVERAGE_TO_SLOTS["full"])
        # Two-handed weapon: anchor at main_hand but also lock off_hand visually.
        if item_type == "weapon" and int(r["equipped"] or 0) == 1 and wslot == "two_handed":
            covered_slots = ["main_hand", "off_hand"]
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
                "can_use": item_type == "consumable",
                "armor_coverage": coverage,
                "weapon_slot": wslot,
                "covered_slots": covered_slots,
            }
        )
    return out


def _rget(row: sqlite3.Row, col: str, default: Any = None) -> Any:
    try:
        return row[col] if col in row.keys() else default
    except (KeyError, IndexError):
        return default


def get_inventory_item_detail(character_id: int, inventory_id: int) -> dict:
    """D5 (#380) — full detail for one inventory entry, for the item-view modal.

    Resolves the character_inventory row to its catalog (weapon/consumable/item)
    and returns common fields (name, description, type, value, quantity, equipped)
    plus kind-specific blocks: weapon{damage_die,linked_stat,...},
    armor{ac_bonus,coverage}, consumable{effect_*}. Narrative items fall back to
    the stored label + meta description. Raises ValueError if not found.
    """
    cid = int(character_id)
    iid = int(inventory_id)
    with _conn() as conn:
        ci = conn.execute(
            "SELECT * FROM character_inventory WHERE id = ? AND character_id = ?",
            (iid, cid),
        ).fetchone()
        if not ci:
            raise ValueError("inventory item not found")
        base = {
            "id": iid,
            "quantity": int(_rget(ci, "quantity", 1) or 1),
            "equipped": int(_rget(ci, "equipped", 0) or 0),
        }

        # Weapon
        if _rget(ci, "weapon_key"):
            wkey = ci["weapon_key"]
            w = conn.execute(
                "SELECT * FROM game_config_weapons WHERE key = ?", (wkey,)
            ).fetchone()
            if w:
                return {
                    **base, "kind": "weapon", "item_type": "weapon",
                    "name": _rget(w, "label") or wkey,
                    "description": _rget(w, "description"),
                    "value_gp": int(_rget(w, "value_gp", 0) or 0),
                    "note": _rget(w, "note"),
                    "weapon": {
                        "damage_die": _rget(w, "damage_die"),
                        "linked_stat": _rget(w, "linked_stat"),
                        "weapon_type": _rget(w, "weapon_type"),
                        "attack_bonus": int(_rget(w, "attack_bonus", 0) or 0),
                    },
                }
            return {
                **base, "kind": "weapon", "item_type": "weapon",
                "name": _rget(ci, "label") or wkey, "description": None, "weapon": {},
            }

        # Consumable
        if _rget(ci, "consumable_key"):
            ckey = ci["consumable_key"]
            c = conn.execute(
                "SELECT * FROM game_config_consumables WHERE key = ?", (ckey,)
            ).fetchone()
            if c:
                return {
                    **base, "kind": "consumable", "item_type": "consumable",
                    "name": _rget(c, "label") or ckey,
                    "description": _rget(c, "description"),
                    "value_gp": int(_rget(c, "base_price", 0) or 0),
                    "note": _rget(c, "note"),
                    "consumable": {
                        "effect_type": _rget(c, "effect_type"),
                        "effect_dice": _rget(c, "effect_dice"),
                        "effect_bonus": int(_rget(c, "effect_bonus", 0) or 0),
                        "effect_target": _rget(c, "effect_target"),
                    },
                }

        # Catalog item (incl. armor)
        ikey = _rget(ci, "item_key")
        if ikey and ikey != "__narrative__":
            it = conn.execute(
                "SELECT * FROM game_config_items WHERE key = ?", (ikey,)
            ).fetchone()
            if it:
                item_type = str(_rget(it, "item_type") or "item").strip().lower() or "item"
                detail = {
                    **base, "kind": item_type, "item_type": item_type,
                    "name": _rget(it, "label") or ikey,
                    "description": _rget(it, "description"),
                    "value_gp": int(_rget(it, "value_gp", 0) or 0),
                    "note": _rget(it, "note"),
                }
                if item_type == "armor":
                    detail["armor"] = {
                        "ac_bonus": int(_rget(it, "ac_bonus", 0) or 0),
                        "coverage": _rget(it, "armor_coverage"),
                    }
                if _rget(it, "effect_type"):
                    detail["consumable"] = {
                        "effect_type": _rget(it, "effect_type"),
                        "effect_dice": _rget(it, "effect_dice"),
                        "effect_bonus": int(_rget(it, "effect_bonus", 0) or 0),
                        "effect_target": _rget(it, "effect_target"),
                    }
                return detail

        # Narrative fallback
        try:
            meta = json.loads(_rget(ci, "meta_json") or "{}")
        except Exception:
            meta = {}
        return {
            **base, "kind": "narrative",
            "item_type": str(meta.get("item_type") or "narrative"),
            "name": _rget(ci, "label") or "Przedmiot",
            "description": meta.get("description"),
            "is_narrative": True,
        }


def use_inventory_item(character_id: int, inventory_id: int) -> dict[str, Any]:
    """Consume one inventory stack and apply supported effects to the character sheet."""
    cid = int(character_id)
    iid = int(inventory_id)
    with _conn() as conn:
        try:
            row = conn.execute(
                """
                SELECT c.id AS character_id,
                       c.campaign_id,
                       c.sheet_json,
                       ci.id AS inventory_id,
                       ci.item_key,
                       ci.weapon_key,
                       ci.consumable_key,
                       ci.quantity,
                       gi.key AS catalog_item_key,
                       gi.label AS item_label,
                       gi.item_type,
                       gi.effect_json,
                       gi.effect_type,
                       gi.effect_dice,
                       gi.effect_bonus,
                       gi.effect_target,
                       gc.key AS legacy_consumable_key,
                       gc.label AS legacy_consumable_label,
                       gc.effect_type AS legacy_effect_type,
                       gc.effect_dice AS legacy_effect_dice,
                       gc.effect_bonus AS legacy_effect_bonus,
                       gc.effect_target AS legacy_effect_target
                FROM characters c
                JOIN character_inventory ci ON ci.character_id = c.id
                LEFT JOIN game_config_items gi ON gi.key = ci.item_key
                LEFT JOIN game_config_consumables gc
                  ON gc.key = ci.consumable_key
                     OR (ci.item_key IS NOT NULL AND gc.key = ci.item_key)
                WHERE c.id = ? AND ci.id = ?
                LIMIT 1
                """,
                (cid, iid),
            ).fetchone()
        except sqlite3.OperationalError:
            row = conn.execute(
                """
                SELECT c.id AS character_id,
                       c.campaign_id,
                       c.sheet_json,
                       ci.id AS inventory_id,
                       ci.item_key,
                       ci.weapon_key,
                       ci.consumable_key,
                       ci.quantity,
                       gi.key AS catalog_item_key,
                       gi.label AS item_label,
                       gi.item_type,
                       gi.effect_json,
                       NULL AS effect_type,
                       NULL AS effect_dice,
                       NULL AS effect_bonus,
                       NULL AS effect_target,
                       gc.key AS legacy_consumable_key,
                       gc.label AS legacy_consumable_label,
                       gc.effect_type AS legacy_effect_type,
                       gc.effect_dice AS legacy_effect_dice,
                       gc.effect_bonus AS legacy_effect_bonus,
                       gc.effect_target AS legacy_effect_target
                FROM characters c
                JOIN character_inventory ci ON ci.character_id = c.id
                LEFT JOIN game_config_items gi ON gi.key = ci.item_key
                LEFT JOIN game_config_consumables gc
                  ON gc.key = ci.consumable_key
                     OR (ci.item_key IS NOT NULL AND gc.key = ci.item_key)
                WHERE c.id = ? AND ci.id = ?
                LIMIT 1
                """,
                (cid, iid),
            ).fetchone()
        if not row:
            ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
            if not ch:
                raise ValueError("character not found")
            raise ValueError("inventory entry not found")

        if row["weapon_key"]:
            raise ValueError("inventory item is not usable")

        catalog_key = str(row["catalog_item_key"] or row["legacy_consumable_key"] or row["item_key"] or row["consumable_key"] or "").strip()
        item_label = str(row["item_label"] or row["legacy_consumable_label"] or catalog_key or "item").strip() or "item"
        raw_item_type = str(row["item_type"] or "").strip().lower()
        if raw_item_type == "consumable" or row["legacy_consumable_key"]:
            item_type = "consumable"
        else:
            item_legacy = legacy_effect_fields_from_json(row["effect_json"]) or {}
            item_effect_type = str(item_legacy.get("effect_type") or "").strip().lower()
            legacy_effect_type = str(row["legacy_effect_type"] or "").strip().lower()
            signal = item_effect_type or legacy_effect_type
            item_type = "consumable" if signal in _CONSUMABLE_EFFECT_SIGNAL else (raw_item_type or "item")
        if item_type != "consumable":
            raise ValueError("inventory item is not usable")

        sheet = parse_character_sheet(row["sheet_json"] if "sheet_json" in row.keys() else None)
        if not isinstance(sheet, dict):
            sheet = {}
        current_hp = int(sheet.get("current_hp", 0) or 0)
        max_hp = max(1, int(sheet.get("max_hp", current_hp or 1) or (current_hp or 1)))
        current_mana = int(sheet.get("current_mana", 0) or 0)
        max_mana = max(0, int(sheet.get("max_mana", current_mana) or current_mana))
        conditions = _normalize_sheet_conditions(sheet)

        item_row: dict[str, Any] = dict(row)
        if not item_row.get("effect_json") and item_row.get("effect_type"):
            pass
        elif item_row.get("legacy_consumable_key"):
            item_row["effect_type"] = item_row.get("legacy_effect_type")
            item_row["effect_dice"] = item_row.get("legacy_effect_dice")
            item_row["effect_bonus"] = item_row.get("legacy_effect_bonus")
            item_row["effect_target"] = item_row.get("legacy_effect_target")
        effects = _effect_payloads_from_item_row(item_row) if catalog_key else []
        if not effects:
            raise ValueError("inventory item has no usable effects")

        results: list[dict[str, Any]] = []
        for effect in effects:
            effect_type = str(effect.get("type") or "").strip().lower()
            if effect_type not in _SUPPORTED_ITEM_USE_EFFECTS and effect_type != "restore_mana":
                raise ValueError("unsupported_item_effect")

            if effect_type == "heal_hp":
                value = effect.get("value", 0)
                rolled = _roll_dice_value(value) if isinstance(value, str) and value.strip() else int(value or 0)
                before = current_hp
                current_hp = max(0, min(max_hp, current_hp + int(rolled)))
                results.append({"type": "heal_hp", "amount": int(current_hp - before)})
                continue

            if effect_type == "restore_mana":
                value = effect.get("value", 0)
                rolled = _roll_dice_value(value) if isinstance(value, str) and value.strip() else int(value or 0)
                before = current_mana
                current_mana = max(0, min(max_mana, current_mana + int(rolled)))
                results.append({"type": "restore_mana", "amount": int(current_mana - before)})
                continue

            if effect_type == "remove_condition":
                condition_key = str(effect.get("condition_key") or "").strip().lower()
                if not condition_key:
                    raise ValueError("unsupported_item_effect")
                before_count = len(conditions)
                conditions = [c for c in conditions if str(c.get("key") or "").strip().lower() != condition_key]
                sheet["conditions"] = conditions
                results.append({"type": "remove_condition", "condition_key": condition_key, "removed": before_count - len(conditions)})
                continue

            if effect_type == "apply_condition":
                condition_key = str(effect.get("condition_key") or "").strip().lower()
                if not condition_key:
                    raise ValueError("unsupported_item_effect")
                cond_row = _condition_catalog_row(conn, condition_key)
                if not cond_row:
                    raise ValueError("condition_not_found")
                stackable = bool(int(cond_row["stackable"] or 0)) if "stackable" in cond_row.keys() else False
                already_has = any(str(c.get("key") or "").strip().lower() == condition_key for c in conditions)
                if already_has and not stackable:
                    results.append({"type": "apply_condition", "condition_key": condition_key, "applied": False, "reason": "already_present"})
                    continue
                conditions.append(
                    {
                        "key": str(cond_row["key"]),
                        "label": str(cond_row["label"] or cond_row["key"]),
                        "effect_json": cond_row["effect_json"],
                        "source_item_key": catalog_key,
                        "applied_at": "inventory_use",
                    }
                )
                sheet["conditions"] = conditions
                results.append({"type": "apply_condition", "condition_key": condition_key, "applied": True})
                continue

            if effect_type == "narrative_only":
                results.append({"type": "narrative_only"})
                continue

        sheet["current_hp"] = current_hp
        sheet["max_hp"] = max_hp
        sheet["current_mana"] = current_mana
        sheet["max_mana"] = max_mana
        sheet["conditions"] = conditions

        next_qty = int(row["quantity"] or 1) - 1
        if next_qty > 0:
            conn.execute("UPDATE character_inventory SET quantity = ? WHERE id = ?", (next_qty, iid))
        else:
            conn.execute("DELETE FROM character_inventory WHERE id = ?", (iid,))

        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), cid),
        )
        _sync_player_state_to_active_combat(
            conn,
            campaign_id=int(row["campaign_id"] or 0),
            character_id=cid,
            current_hp=current_hp,
            conditions=conditions,
        )
        conn.commit()

    return {
        "inventory_id": iid,
        "character_id": cid,
        "item": {"key": catalog_key, "label": item_label, "item_type": item_type},
        "remaining_quantity": max(0, next_qty),
        "effects_applied": results,
        "character_state": {
            "current_hp": current_hp,
            "max_hp": max_hp,
            "current_mana": current_mana,
            "max_mana": max_mana,
            "conditions": conditions,
        },
    }


def equip_item(character_id: int, inventory_id: int, slot: str) -> dict:
    """
    Equip an inventory entry on a slot, freeing whatever previously occupied
    that slot (and, for full-coverage armor, all 4 limb slots in one go).

    Coverage rules (Stage 5 E4):
    - Weapons → main_hand or off_hand (no coverage check).
    - Armor with `armor_coverage='head'` → only `slot='head'`.
    - Armor with `armor_coverage='torso'` → only `slot='torso'`.
    - Armor with `armor_coverage='limb_arm'` → caller must pass `l_arm` or `r_arm`.
    - Armor with `armor_coverage='limb_leg'` → caller must pass `l_leg` or `r_leg`.
    - Armor with `armor_coverage='full'` → row is anchored at `slot='torso'`,
      but the equip transaction also frees existing `l_arm`/`r_arm`/`l_leg`/`r_leg`
      rows. Hydration in `get_character_inventory` later reports the full row as
      occupying all 5 slots so the UI can render limb cards as "covered by full".
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
            """
            SELECT ci.id, ci.weapon_key, ci.item_key,
                   gi.item_type, gi.armor_coverage,
                   gw.weapon_slot AS weapon_slot
            FROM character_inventory ci
            LEFT JOIN game_config_items gi ON gi.key = ci.item_key
            LEFT JOIN game_config_weapons gw ON gw.key = ci.weapon_key
            WHERE ci.id = ? AND ci.character_id = ?
            """,
            (iid, cid),
        ).fetchone()
        if not row:
            raise ValueError("inventory entry not found")

        item_type = (row["item_type"] or "").lower()
        coverage = (row["armor_coverage"] or "").lower()
        weapon_slot_kind = (row["weapon_slot"] or "main_hand").lower()
        is_weapon = bool(row["weapon_key"]) or item_type == "weapon"
        is_armor = item_type == "armor"

        slots_to_free: list[str] = [s]
        anchor_slot = s

        if is_armor:
            if coverage and coverage not in _VALID_ARMOR_COVERAGE:
                raise ValueError(f"invalid armor_coverage '{coverage}'")
            if coverage == "head" and s != "head":
                raise ValueError("head armor can only equip to slot 'head'")
            if coverage == "torso" and s != "torso":
                raise ValueError("torso armor can only equip to slot 'torso'")
            if coverage == "limb_arm" and s not in ("l_arm", "r_arm"):
                raise ValueError("arm armor must equip to 'l_arm' or 'r_arm'")
            if coverage == "limb_leg" and s not in ("l_leg", "r_leg"):
                raise ValueError("leg armor must equip to 'l_leg' or 'r_leg'")
            if coverage == "full":
                anchor_slot = "torso"
                slots_to_free = list(_ARMOR_COVERAGE_TO_SLOTS["full"])
        elif is_weapon:
            if s not in ("main_hand", "off_hand"):
                raise ValueError("weapons can only equip to 'main_hand' or 'off_hand'")
            # Stage 5 follow-up: weapon_slot enforcement.
            if weapon_slot_kind and weapon_slot_kind not in _VALID_WEAPON_SLOT:
                raise ValueError(f"invalid weapon_slot '{weapon_slot_kind}'")
            if weapon_slot_kind == "main_hand" and s != "main_hand":
                raise ValueError("this weapon can only be equipped in main_hand")
            if weapon_slot_kind == "off_hand_only" and s != "off_hand":
                raise ValueError("this off-hand item can only be equipped in off_hand")
            if weapon_slot_kind == "two_handed":
                if s != "main_hand":
                    raise ValueError("two-handed weapons must be equipped to main_hand (they lock off_hand too)")
                # Two-handed weapons anchor to main_hand and occupy both.
                anchor_slot = "main_hand"
                slots_to_free = ["main_hand", "off_hand"]

        # Free whatever sits in any slot this equip is about to claim.
        placeholders = ",".join(["?"] * len(slots_to_free))
        params = [cid, *slots_to_free]
        conn.execute(
            f"UPDATE character_inventory SET equipped = 0, slot = NULL "
            f"WHERE character_id = ? AND slot IN ({placeholders})",
            params,
        )
        # ALSO free any existing full-coverage anchor whose locked limbs overlap
        # the target — prevents leaving phantom limbs occupied by an unequipped
        # full plate (rare, but cheap to guard).
        if is_armor and any(slot_x in slots_to_free for slot_x in ("l_arm", "r_arm", "l_leg", "r_leg", "torso")):
            conn.execute(
                """
                UPDATE character_inventory SET equipped = 0, slot = NULL
                WHERE character_id = ? AND equipped = 1 AND slot = 'torso'
                  AND id IN (
                    SELECT ci2.id FROM character_inventory ci2
                    JOIN game_config_items gi2 ON gi2.key = ci2.item_key
                    WHERE ci2.character_id = ? AND gi2.armor_coverage = 'full'
                  )
                """,
                (cid, cid),
            )

        conn.execute(
            "UPDATE character_inventory SET equipped = 1, slot = ? WHERE id = ?",
            (anchor_slot, iid),
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


def apply_character_gold_delta(
    character_id: int,
    delta: int,
    reason: str | None = None,
    *,
    campaign_id: int | None = None,
) -> int:
    """
    Atomically adjust gold_gp by delta (must not go below 0).
    Stage 11 R6 — `reason` is now persisted to `character_gold_log` so the
    `gold_recent_days` resurrection mode can sum recent gains. `campaign_id`
    is used to derive the in-game day; without it, day defaults to 1 and the
    row won't be matched by a windowed lookup.
    """
    if int(delta) == 0:
        raise ValueError("delta must be non-zero")
    cid = int(character_id)
    d = int(delta)
    with _conn() as conn:
        row = conn.execute("SELECT gold_gp, campaign_id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise ValueError("character not found")
        cur = int(row["gold_gp"] or 0)
        new_g = cur + d
        if new_g < 0:
            raise ValueError("gold_gp would be negative")
        conn.execute("UPDATE characters SET gold_gp = ? WHERE id = ?", (new_g, cid))
        # Resolve campaign for clock lookup (fall back to character's own campaign_id)
        cid_for_clock = campaign_id if campaign_id is not None else row["campaign_id"]
        try:
            from app.services.economy_service import journal_gold_delta
            journal_gold_delta(
                conn, cid, d, reason or "unknown",
                campaign_id=cid_for_clock,
            )
        except Exception as _e:
            pass  # journaling must never block the gold mutation
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
