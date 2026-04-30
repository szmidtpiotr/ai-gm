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
            item_key = str(req.key or "").strip()
            if not item_key:
                raise HTTPException(status_code=422, detail="item_key_required")
            if item_key.startswith("weapon_"):
                conn.execute(
                    "INSERT INTO character_inventory (character_id, weapon_key) VALUES (?, ?)",
                    (character_id, item_key),
                )
            elif item_key.startswith("consumable_"):
                conn.execute(
                    "INSERT INTO character_inventory (character_id, consumable_key) VALUES (?, ?)",
                    (character_id, item_key),
                )
            else:
                conn.execute(
                    "INSERT INTO character_inventory (character_id, item_key) VALUES (?, ?)",
                    (character_id, item_key),
                )
            result = {"added": item_key}

        elif cmd == "remove item":
            item_key = str(req.key or "").strip()
            if not item_key:
                raise HTTPException(status_code=422, detail="item_key_required")
            conn.execute(
                "DELETE FROM character_inventory "
                "WHERE character_id = ? AND (item_key = ? OR weapon_key = ? OR consumable_key = ?)",
                (character_id, item_key, item_key, item_key),
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
