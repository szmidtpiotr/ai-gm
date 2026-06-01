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
    from app.services.xp_service import get_hero_level
    conn = _get_db()
    try:
        char = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (character_id,)).fetchone()
        if not char:
            return 1
        return get_hero_level(json.loads(char["sheet_json"] or "{}"))
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
        parts = str(e).split("|")
        detail: dict = {"error": "dungeon_on_cooldown"}
        if len(parts) >= 3:
            detail["cooldown_until"] = parts[1]
            detail["hours_remaining"] = float(parts[2])
        raise HTTPException(status_code=423, detail=detail)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    label = instance["dungeon_label"]
    atm = instance.get("atmosphere") or dungeon.get("atmosphere") or ""

    if instance.get("system") == "tiles":
        first_tile = (instance.get("tiles") or [None])[0] or {}
        narrative = f"Wkraczasz do *{label}*."
        if atm:
            narrative += f" {atm}"
        if first_tile.get("room_description"):
            narrative += f" {first_tile['room_description'][:120]}"
        elif first_tile.get("enemies"):
            enemy = first_tile["enemies"][0]
            narrative += f" {enemy.get('label','Wróg')} staje na twej drodze."
    else:
        rooms = instance.get("rooms") or []
        first_room = rooms[0] if rooms else {}
        room_type = first_room.get("room_type", "combat")
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

class DungeonAdvanceReq(BaseModel):
    character_id: int
    campaign_id: int
    door_chosen: str | None = None  # tile system: N/S/E/W


@router.post("/dungeons/advance-room")
def advance_dungeon_room(req: DungeonAdvanceReq):
    from app.services.dungeon_service import (
        advance_room, get_active_dungeon_run, complete_dungeon,
        get_current_room, roll_boss_loot, grant_dungeon_loot
    )

    run = get_active_dungeon_run(req.campaign_id)
    if not run:
        raise HTTPException(status_code=409, detail="No active dungeon run")

    advance_result = advance_room(req.campaign_id, req.character_id, req.door_chosen)

    # Tile system returns {"ok", "run", ...}; legacy returns run dict directly
    if isinstance(advance_result, dict) and "ok" in advance_result and "run" in advance_result:
        if not advance_result.get("ok"):
            raise HTTPException(status_code=409, detail=advance_result.get("reason", "Blocked"))
        updated_run = advance_result["run"]
    else:
        updated_run = advance_result

    # Dungeon completed
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

    # Tile system narrative
    if updated_run.get("system") == "tiles":
        cur_idx = updated_run.get("current_index", 0)
        total = updated_run.get("total_tiles", 1)
        tile = (updated_run.get("tiles") or [])[cur_idx] if cur_idx < len(updated_run.get("tiles") or []) else {}
        label = tile.get("label", "komnata")
        if tile.get("is_boss_tile"):
            narrative = f"💀 BOSS {cur_idx+1}/{total} — {label}! Przygotuj się na walkę!"
        elif tile.get("room_description"):
            narrative = tile["room_description"]
        else:
            narrative = f"Komnata {cur_idx+1}/{total} — {label}."
        return {"ok": True, "dungeon_run": updated_run, "completed": False, "narrative": narrative}

    # Legacy narrative
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
