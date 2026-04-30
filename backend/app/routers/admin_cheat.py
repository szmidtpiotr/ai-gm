import json
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Path
from fastapi.params import Depends
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path
from app.routers.admin import require_admin_token

router = APIRouter(tags=["admin-cheat"])
DB_PATH = resolve_db_path()


def _sqlite_table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _resolve_inventory_add_key(
    conn: sqlite3.Connection, raw_key: str, preferred_kind: str | None = None
) -> tuple[str, str]:
    """
    Map raw cheat key to (canonical_catalog_key, column_name).

    column_name is one of weapon_key | consumable_key | item_key.

    When game_config_* tables exist, match catalog rows (including legacy
    ``weapon_<catalog_key>`` aliases). Otherwise fall back to prefix heuristics
    so minimal test DBs without catalogs keep working.
    """
    k = str(raw_key or "").strip()
    if not k:
        raise ValueError("empty key")

    def w(canonical: str) -> tuple[str, str]:
        return canonical, "weapon_key"

    def c(canonical: str) -> tuple[str, str]:
        return canonical, "consumable_key"

    def i(canonical: str) -> tuple[str, str]:
        return canonical, "item_key"

    has_w = _sqlite_table_exists(conn, "game_config_weapons")
    has_c = _sqlite_table_exists(conn, "game_config_consumables")
    has_i = _sqlite_table_exists(conn, "game_config_items")
    pref = str(preferred_kind or "").strip().lower()

    # Explicit command intent ("/admin add weapon|consumable ...") has priority.
    if pref == "weapon":
        if has_w:
            row = conn.execute(
                "SELECT key FROM game_config_weapons WHERE key = ? LIMIT 1",
                (k,),
            ).fetchone()
            if row:
                return w(str(row["key"]))
            if k.startswith("weapon_"):
                alt = k[7:]
                row = conn.execute(
                    "SELECT key FROM game_config_weapons WHERE key = ? LIMIT 1",
                    (alt,),
                ).fetchone()
                if row:
                    return w(str(row["key"]))
        return w(k[7:] if k.startswith("weapon_") else k)

    if pref == "consumable":
        if has_c:
            row = conn.execute(
                "SELECT key FROM game_config_consumables WHERE key = ? LIMIT 1",
                (k,),
            ).fetchone()
            if row:
                return c(str(row["key"]))
            if k.startswith("consumable_"):
                alt = k[11:]
                row = conn.execute(
                    "SELECT key FROM game_config_consumables WHERE key = ? LIMIT 1",
                    (alt,),
                ).fetchone()
                if row:
                    return c(str(row["key"]))
        return c(k[11:] if k.startswith("consumable_") else k)

    if has_w:
        row = conn.execute(
            "SELECT key FROM game_config_weapons WHERE key = ? LIMIT 1",
            (k,),
        ).fetchone()
        if row:
            return w(str(row["key"]))
        if k.startswith("weapon_"):
            alt = k[7:]
            row = conn.execute(
                "SELECT key FROM game_config_weapons WHERE key = ? LIMIT 1",
                (alt,),
            ).fetchone()
            if row:
                return w(str(row["key"]))

    if has_c:
        row = conn.execute(
            "SELECT key FROM game_config_consumables WHERE key = ? LIMIT 1",
            (k,),
        ).fetchone()
        if row:
            return c(str(row["key"]))
        if k.startswith("consumable_"):
            alt = k[11:]
            row = conn.execute(
                "SELECT key FROM game_config_consumables WHERE key = ? LIMIT 1",
                (alt,),
            ).fetchone()
            if row:
                return c(str(row["key"]))

    if has_i:
        row = conn.execute(
            "SELECT key, item_type FROM game_config_items WHERE key = ? LIMIT 1",
            (k,),
        ).fetchone()
        if row:
            ik = str(row["key"])
            it = str(row["item_type"] or "").strip().lower() or "item"
            # Mikstury / konsumable z efektami są w game_config_consumables; sam wiersz
            # w items z item_type=consumable (np. import) musi trafiać do consumable_key,
            # żeby ten sam kształt co grant_loot / sklep / silnik.
            if it == "consumable" and has_c:
                crow = conn.execute(
                    "SELECT key FROM game_config_consumables WHERE key = ? LIMIT 1",
                    (ik,),
                ).fetchone()
                if crow:
                    return c(str(crow["key"]))
            # Broń w katalogu broni — preferuj weapon_key zamiast item_key.
            if it == "weapon" and has_w:
                wrow = conn.execute(
                    "SELECT key FROM game_config_weapons WHERE key = ? LIMIT 1",
                    (ik,),
                ).fetchone()
                if wrow:
                    return w(str(wrow["key"]))
            return i(ik)

    if k.startswith("weapon_"):
        return w(k)
    if k.startswith("consumable_"):
        return c(k)
    return i(k)


def _occupied_equipment_slots(conn: sqlite3.Connection, character_id: int) -> dict[str, bool]:
    o = {"main_hand": False, "off_hand": False, "armor": False}
    rows = conn.execute(
        """
        SELECT slot FROM character_inventory
        WHERE character_id = ? AND equipped = 1 AND slot IS NOT NULL AND slot != ''
        """,
        (int(character_id),),
    ).fetchall()
    for r in rows:
        s = str(r["slot"] or "").lower()
        if s in o:
            o[s] = True
    return o


def _pick_weapon_equip_slot(
    conn: sqlite3.Connection, character_id: int, weapon_catalog_key: str
) -> str:
    """Match frontend inventory.js pickEquipSlot: shields → off_hand when free, else hands."""
    occupied = _occupied_equipment_slots(conn, character_id)
    key_lower = weapon_catalog_key.lower()
    lab = ""
    row = conn.execute(
        "SELECT label FROM game_config_weapons WHERE key = ? LIMIT 1",
        (weapon_catalog_key,),
    ).fetchone()
    if row and row["label"] is not None:
        lab = str(row["label"]).lower()
    if "shield" in key_lower or "tarcz" in lab or "shield" in lab:
        if not occupied["off_hand"]:
            return "off_hand"
        if not occupied["main_hand"]:
            return "main_hand"
        return "off_hand"
    if not occupied["main_hand"]:
        return "main_hand"
    if not occupied["off_hand"]:
        return "off_hand"
    return "main_hand"


def _auto_equip_new_inventory_row(
    conn: sqlite3.Connection,
    character_id: int,
    inventory_id: int,
    col: str,
    canonical_key: str,
) -> str | None:
    """
    After cheat INSERT, assign equipped + slot for weapons and armor items.
    Returns slot name if equipped, else None.
    """
    cid = int(character_id)
    iid = int(inventory_id)
    slot: str | None = None
    if col == "weapon_key":
        slot = _pick_weapon_equip_slot(conn, cid, canonical_key)
    elif col == "item_key":
        row = conn.execute(
            "SELECT item_type FROM game_config_items WHERE key = ? LIMIT 1",
            (canonical_key,),
        ).fetchone()
        it = str(row["item_type"] or "").lower() if row else ""
        if it == "armor":
            slot = "armor"
    else:
        return None

    if not slot:
        return None

    conn.execute(
        "UPDATE character_inventory SET equipped = 0, slot = NULL WHERE character_id = ? AND slot = ?",
        (cid, slot),
    )
    conn.execute(
        "UPDATE character_inventory SET equipped = 1, slot = ? WHERE id = ?",
        (slot, iid),
    )
    return slot


def _inventory_key_remove_variants(raw_key: str) -> list[str]:
    """Aliases so remove matches bare keys and legacy weapon_/consumable_ typos."""
    k = str(raw_key or "").strip()
    if not k:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        if x and x not in seen:
            seen.add(x)
            out.append(x)

    add(k)
    if k.startswith("weapon_"):
        add(k[7:])
    else:
        add("weapon_" + k)
    if k.startswith("consumable_"):
        add(k[11:])
    else:
        add("consumable_" + k)
    return out


AVAILABLE_CMDS = [
    "add gold",
    "set gold",
    "add health",
    "set health",
    "add stat",
    "set level",
    "set location",
    "add item",
    "remove item",
    "clear inventory",
    "combat end",
    "quest add",
    "quest complete",
    "show state",
]


class CheatRequest(BaseModel):
    cmd: str
    value: int | str | None = None
    key: str | None = None
    stat: str | None = None
    kind: str | None = None


@router.post("/admin/cheat/{character_id}")
def admin_cheat(
    character_id: int = Path(...),
    req: CheatRequest = ...,
    _: None = Depends(require_admin_token),
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        char = conn.execute(
            "SELECT id, campaign_id, location, sheet_json, COALESCE(gold_gp, 0) AS gold_gp "
            "FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        if not char:
            raise HTTPException(status_code=404, detail="character_not_found")

        sheet: dict[str, Any] = json.loads(char["sheet_json"] or "{}")
        campaign_id = int(char["campaign_id"] or 0)
        result: dict[str, Any] = {}
        cmd = req.cmd.strip().lower()

        if cmd == "add gold":
            amount = int(req.value or 0)
            conn.execute(
                "UPDATE characters SET gold_gp = gold_gp + ? WHERE id = ?",
                (amount, character_id),
            )
            new_gold = conn.execute(
                "SELECT COALESCE(gold_gp,0) FROM characters WHERE id = ?",
                (character_id,),
            ).fetchone()[0]
            result = {"gold_gp": new_gold}

        elif cmd == "set gold":
            amount = max(0, int(req.value or 0))
            conn.execute(
                "UPDATE characters SET gold_gp = ? WHERE id = ?",
                (amount, character_id),
            )
            result = {"gold_gp": amount}

        elif cmd in ("add health", "set health"):
            max_hp = int(sheet.get("max_hp", sheet.get("current_hp", 1)) or 1)
            cur_hp = int(sheet.get("current_hp", max_hp) or max_hp)

            if str(req.value).strip().lower() == "max":
                sheet["current_hp"] = max_hp
            elif cmd == "add health":
                sheet["current_hp"] = max(0, min(max_hp, cur_hp + int(req.value or 0)))
            else:
                sheet["current_hp"] = max(0, min(max_hp, int(req.value or 0)))

            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"current_hp": sheet["current_hp"], "max_hp": max_hp}

        elif cmd == "add stat":
            stat_key = (req.stat or "").upper()
            if stat_key not in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
                raise HTTPException(status_code=422, detail="invalid_stat")
            stats: dict[str, Any] = sheet.get("stats") or {}
            stats[stat_key] = int(stats.get(stat_key, 0)) + int(req.value or 0)
            sheet["stats"] = stats
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"stat": stat_key, "new_value": stats[stat_key]}

        elif cmd == "set level":
            sheet["level"] = max(1, int(req.value or 1))
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"level": sheet["level"]}

        elif cmd == "set location":
            loc = str(req.key or "").strip()
            if not loc:
                raise HTTPException(status_code=422, detail="location_key_required")
            conn.execute(
                "UPDATE characters SET location = ? WHERE id = ?",
                (loc, character_id),
            )
            result = {"location": loc}

        elif cmd == "add item":
            raw = str(req.key or "").strip()
            if not raw:
                raise HTTPException(status_code=422, detail="item_key_required")
            try:
                canonical, col = _resolve_inventory_add_key(conn, raw, req.kind)
            except ValueError:
                raise HTTPException(status_code=422, detail="item_key_required") from None
            conn.execute(
                f"INSERT INTO character_inventory (character_id, {col}) VALUES (?, ?)",
                (character_id, canonical),
            )
            inv_row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
            inv_id = int(inv_row["id"]) if inv_row and inv_row["id"] is not None else 0
            equipped_slot: str | None = None
            if inv_id > 0:
                try:
                    equipped_slot = _auto_equip_new_inventory_row(
                        conn, character_id, inv_id, col, canonical
                    )
                except sqlite3.OperationalError:
                    equipped_slot = None
            result = {"added": canonical}
            if equipped_slot:
                result["equipped_slot"] = equipped_slot

        elif cmd == "remove item":
            item_key = str(req.key or "").strip()
            if not item_key:
                raise HTTPException(status_code=422, detail="item_key_required")
            variants = _inventory_key_remove_variants(item_key)
            if not variants:
                raise HTTPException(status_code=422, detail="item_key_required")
            placeholders = ",".join("?" * len(variants))
            conn.execute(
                f"""
                DELETE FROM character_inventory
                WHERE character_id = ?
                  AND (
                    item_key IN ({placeholders})
                    OR weapon_key IN ({placeholders})
                    OR consumable_key IN ({placeholders})
                  )
                """,
                (character_id, *variants, *variants, *variants),
            )
            result = {"removed": item_key}

        elif cmd == "clear inventory":
            conn.execute(
                "DELETE FROM character_inventory WHERE character_id = ?",
                (character_id,),
            )
            result = {"cleared": True}

        elif cmd == "combat end":
            conn.execute(
                "UPDATE active_combat "
                "SET status = 'ended', ended_reason = 'admin_cheat' "
                "WHERE campaign_id = ? AND status = 'active'",
                (campaign_id,),
            )
            result = {"combat_ended": True, "campaign_id": campaign_id}

        elif cmd == "quest add":
            key = str(req.key or "").strip()
            if not key:
                raise HTTPException(status_code=422, detail="quest_key_required")
            quests_active: list[str] = sheet.get("quests_active") or []
            if key not in quests_active:
                quests_active.append(key)
            sheet["quests_active"] = quests_active
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"quest_added": key, "quests_active": quests_active}

        elif cmd == "quest complete":
            key = str(req.key or "").strip()
            if not key:
                raise HTTPException(status_code=422, detail="quest_key_required")
            active: list[str] = list(sheet.get("quests_active") or [])
            completed: list[str] = list(sheet.get("quests_completed") or [])
            if key in active:
                active.remove(key)
            if key not in completed:
                completed.append(key)
            sheet["quests_active"] = active
            sheet["quests_completed"] = completed
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {
                "quest_completed": key,
                "quests_active": active,
                "quests_completed": completed,
            }

        elif cmd == "show state":
            gold = int(
                conn.execute(
                    "SELECT COALESCE(gold_gp,0) FROM characters WHERE id = ?",
                    (character_id,),
                ).fetchone()[0]
                or 0
            )
            location = str(
                conn.execute(
                    "SELECT location FROM characters WHERE id = ?",
                    (character_id,),
                ).fetchone()[0]
                or ""
            )
            try:
                inv_rows = conn.execute(
                    "SELECT item_key, weapon_key, consumable_key FROM character_inventory "
                    "WHERE character_id = ? ORDER BY id ASC",
                    (character_id,),
                ).fetchall()
                inventory = [
                    str(r["item_key"] or r["weapon_key"] or r["consumable_key"])
                    for r in inv_rows
                    if (r["item_key"] or r["weapon_key"] or r["consumable_key"])
                ]
            except sqlite3.OperationalError:
                inventory = []

            result = {
                "current_hp": sheet.get("current_hp"),
                "max_hp": sheet.get("max_hp"),
                "gold_gp": gold,
                "level": sheet.get("level"),
                "location": location,
                "stats": sheet.get("stats"),
                "quests_active": sheet.get("quests_active") or [],
                "quests_completed": sheet.get("quests_completed") or [],
                "inventory": inventory,
            }

        else:
            raise HTTPException(
                status_code=422,
                detail={"error": "unknown_cmd", "available": AVAILABLE_CMDS},
            )

        conn.commit()
        return {"ok": True, "cmd": req.cmd, "result": result}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from None
    finally:
        conn.close()
