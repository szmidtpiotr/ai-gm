"""Player-facing dungeon run API — Task 41 V2."""
from __future__ import annotations
import json
import sqlite3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
DB_PATH = "/data/ai_gm.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_hero_level(character_id: int) -> int:
    conn = _get_db()
    try:
        char = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (character_id,)).fetchone()
        if not char:
            return 1
        sheet = json.loads(char["sheet_json"] or "{}")
        return int(sheet.get("level", 1) or 1)
    finally:
        conn.close()


# ── List + detail ─────────────────────────────────────────────────────────────

@router.get("/dungeons")
def list_dungeons_for_character(character_id: int | None = None):
    from app.services.dungeon_service import list_dungeons
    return {"dungeons": list_dungeons(character_id)}


@router.get("/dungeons/{dungeon_key}")
def get_dungeon_detail(dungeon_key: str, character_id: int | None = None):
    from app.services.dungeon_service import check_cooldown, get_dungeon
    d = get_dungeon(dungeon_key)
    if not d:
        raise HTTPException(status_code=404, detail="Dungeon not found")
    if character_id:
        d["cooldown"] = check_cooldown(character_id, dungeon_key)
    return d


# ── Dungeon entry snapshot ────────────────────────────────────────────────────

def _save_dungeon_entry_snapshot(campaign_id: int, character_id: int) -> None:
    """Save a world_state_snapshots row capturing HP, gold, and inventory at dungeon entry."""
    from app.services.world_state_service import save_snapshot
    conn = _get_db()
    try:
        char = conn.execute(
            "SELECT sheet_json, gold, gold_gp FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        if not char:
            return
        sheet = json.loads(char["sheet_json"] or "{}")
        inv_rows = conn.execute(
            """SELECT item_key, weapon_key, consumable_key, quantity, equipped
               FROM character_inventory WHERE character_id = ?""",
            (character_id,),
        ).fetchall()
        inventory = [dict(r) for r in inv_rows]
        turn_row = conn.execute(
            "SELECT MAX(turn_number) AS t FROM campaign_turns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        turn_number = (turn_row["t"] or 0) if turn_row else 0
    finally:
        conn.close()

    state_dict = {
        "current_hp": sheet.get("current_hp"),
        "max_hp": sheet.get("max_hp"),
        "gold": char["gold"],
        "gold_gp": char["gold_gp"],
        "inventory": inventory,
        "dungeon_key": None,  # populated by caller context, available via session_flags
    }
    save_snapshot(campaign_id, turn_number, state_dict, source="dungeon_enter")


# ── Enter ─────────────────────────────────────────────────────────────────────

class DungeonEnterReq(BaseModel):
    character_id: int
    campaign_id: int
    previous_campaign_id: int | None = None  # set when entering mid-campaign


@router.post("/dungeons/{dungeon_key}/enter")
def enter_dungeon(dungeon_key: str, req: DungeonEnterReq):
    from app.services.dungeon_service import enter_dungeon as _enter, get_dungeon

    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        raise HTTPException(status_code=404, detail="Dungeon not found")

    hero_level = _get_hero_level(req.character_id)

    try:
        instance = _enter(
            req.campaign_id, req.character_id, dungeon_key, hero_level,
            previous_campaign_id=req.previous_campaign_id
        )
    except PermissionError as e:
        parts = str(e).split(":")
        detail: dict = {"error": "dungeon_on_cooldown"}
        if len(parts) >= 3:
            detail["cooldown_until"] = parts[1]
            detail["hours_remaining"] = float(parts[2])
        raise HTTPException(status_code=423, detail=detail)

    _save_dungeon_entry_snapshot(req.campaign_id, req.character_id)

    first_room = instance["rooms"][0] if instance["rooms"] else {}
    room_type = first_room.get("room_type", "combat")
    atm = instance.get("atmosphere", "")
    label = instance["dungeon_label"]

    narrative = f"Wkraczasz do *{label}*. {atm}"
    if room_type == "combat":
        enemy_label = first_room.get("enemy_label") or first_room.get("enemy_key") or "wroga"
        narrative += f" Pierwsza komnata — {enemy_label} staje na twej drodze."
    elif room_type == "riddle":
        narrative += " Drzwi zabezpieczone zagadką. Musisz odpowiedzieć poprawnie."
    elif room_type == "trap":
        narrative += " Wchodząc, czujesz że powietrze jest inne. Ostrożnie."
    elif room_type == "chest":
        narrative += " Glimmer of gold catches your eye — a chest in the corner."
    elif room_type == "rest":
        narrative += " " + first_room.get("rest_description", "Spokojne miejsce.")

    return {"ok": True, "dungeon_run": instance, "room_narrative": narrative}


# ── Advance room ──────────────────────────────────────────────────────────────

@router.post("/dungeons/advance-room")
def advance_dungeon_room(req: DungeonEnterReq):
    from app.services.dungeon_service import (
        advance_room, get_active_dungeon_run, complete_dungeon,
        get_current_room, roll_boss_loot, grant_dungeon_loot
    )

    run = get_active_dungeon_run(req.campaign_id)
    if not run:
        raise HTTPException(status_code=409, detail="No active dungeon run")

    updated_run = advance_room(req.campaign_id)

    # If dungeon completed, record clear + roll boss loot
    if updated_run.get("completed"):
        boss_loot: list[dict] = []
        try:
            boss_loot = roll_boss_loot(updated_run["dungeon_key"])
            if boss_loot:
                granted = grant_dungeon_loot(req.character_id, req.campaign_id, boss_loot)
                updated_run.setdefault("loot_collected", []).extend(granted)
        except Exception:
            pass
        try:
            complete_dungeon(req.character_id, updated_run["dungeon_key"])
        except Exception:
            pass
        return {
            "ok": True,
            "dungeon_run": updated_run,
            "completed": True,
            "loot": boss_loot,
            "narrative": f"Pokonałeś *{updated_run['dungeon_label']}*! Zdobyłeś łupy i możesz wyjść.",
        }

    next_room = get_current_room(updated_run)
    if not next_room:
        raise HTTPException(status_code=409, detail="Room not found")

    room_type = next_room.get("room_type", "combat")
    room_num = updated_run["current_room"]
    total = updated_run["total_rooms"]

    narratives = {
        "combat": f"Komnata {room_num}/{total} — {next_room.get('enemy_label') or next_room.get('enemy_key', 'wróg')} czeka.",
        "boss": f"KOMNATA BOSSA {room_num}/{total} — {next_room.get('enemy_label') or next_room.get('enemy_key', 'boss')} strzeże wyjścia!",
        "riddle": f"Komnata {room_num}/{total} — zagadka. Odgadnij aby przejść.",
        "trap": f"Komnata {room_num}/{total} — {next_room.get('trap', {}).get('description', 'Pułapka!')}",
        "chest": f"Komnata {room_num}/{total} — skrzynia skarbów.",
        "rest": f"Komnata {room_num}/{total} — {next_room.get('rest_description', 'Chwila odpoczynku.')}",
    }

    return {
        "ok": True,
        "dungeon_run": updated_run,
        "completed": False,
        "next_room": next_room,
        "narrative": narratives.get(room_type, f"Komnata {room_num}/{total}."),
    }


# ── Resolve non-combat room ───────────────────────────────────────────────────

class DungeonResolveReq(BaseModel):
    character_id: int
    campaign_id: int
    player_input: str | None = None  # riddle answer or empty for hint request


@router.post("/dungeons/resolve-room")
def resolve_dungeon_room(req: DungeonResolveReq):
    from app.services.dungeon_service import resolve_room, grant_dungeon_loot

    try:
        result = resolve_room(req.campaign_id, req.character_id, req.player_input)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Grant any chest loot to inventory
    if result.get("loot"):
        granted = grant_dungeon_loot(req.character_id, req.campaign_id, result["loot"])
        result["loot"] = granted

    return {"ok": True, **result}


# ── Death handling ────────────────────────────────────────────────────────────

@router.post("/dungeons/death")
def dungeon_death(req: DungeonEnterReq):
    from app.services.dungeon_service import handle_dungeon_death
    result = handle_dungeon_death(req.campaign_id, req.character_id)
    return {"ok": True, **result}


# ── Exit dungeon ──────────────────────────────────────────────────────────────

@router.post("/dungeons/exit")
def exit_dungeon(req: DungeonEnterReq):
    """Exit dungeon: clear run from session, return previous_campaign_id if set."""
    from app.services.dungeon_service import get_active_dungeon_run, clear_dungeon_run
    import sqlite3 as _sl

    run = get_active_dungeon_run(req.campaign_id)
    previous_campaign_id = None

    # Get previous_campaign_id from session flags
    conn = _sl.connect(DB_PATH)
    conn.row_factory = _sl.Row
    try:
        row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1", (req.campaign_id,)).fetchone()
        if row:
            flags = json.loads(row["session_flags"] or "{}")
            previous_campaign_id = flags.get("dungeon_previous_campaign_id")
    finally:
        conn.close()

    clear_dungeon_run(req.campaign_id)

    return {
        "ok": True,
        "previous_campaign_id": previous_campaign_id,
        "was_completed": run.get("completed", False) if run else False,
        "was_failed": run.get("failed", False) if run else False,
    }


# ── Active run ────────────────────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/dungeon-run")
def get_current_dungeon_run(campaign_id: int):
    from app.services.dungeon_service import get_active_dungeon_run
    run = get_active_dungeon_run(campaign_id)
    return {"dungeon_run": run}


@router.get("/characters/{character_id}/dungeon-history")
def character_dungeon_history(character_id: int):
    from app.services.dungeon_service import get_run_history
    return {"history": get_run_history(character_id)}
