"""Player-facing dungeon run API — Task 41 V2."""
from __future__ import annotations
import json
import sqlite3
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.jwt_auth import assert_campaign_owner, assert_character_owner
from app.core.db_runtime import resolve_db_path

router = APIRouter()
DB_PATH = resolve_db_path()


def _guard_dungeon_req(character_id: int, campaign_id: int, authorization: str | None) -> None:
    """#1424 — a dungeon action must come from the owner of BOTH the campaign and
    the hero named in the request body."""
    uid = assert_campaign_owner(campaign_id, authorization)
    assert_character_owner(character_id, authorization, uid)


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _is_dungeon_enabled() -> bool:
    """Read dungeon_enabled from game_mode_flags in game_config_meta. Default True."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = 'game_mode_flags'"
        ).fetchone()
        if row and row[0]:
            return bool(json.loads(row[0]).get("dungeon_enabled", True))
        return True
    except Exception:
        return True
    finally:
        conn.close()


def _get_hero_level(character_id: int) -> int:
    conn = _get_db()
    try:
        char = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (character_id,)).fetchone()
        if not char:
            return 1
        sheet = json.loads(char["sheet_json"] or "{}")
        # Canonical level is derived from lifetime XP (matches frontend display +
        # xp_service). Fall back to a stored sheet.level only when XP is absent.
        if sheet.get("xp_lifetime_earned") is not None:
            from app.services.xp_service import get_xp_level_thresholds, level_from_xp
            thresholds = get_xp_level_thresholds(conn)
            return level_from_xp(int(sheet.get("xp_lifetime_earned") or 0), thresholds)
        return int(sheet.get("level", 1) or 1)
    finally:
        conn.close()


# ── List + detail ─────────────────────────────────────────────────────────────

@router.get("/dungeons")
def list_dungeons_for_character(character_id: int | None = None):
    from app.services.dungeon_service import list_dungeons
    return {"dungeons": list_dungeons(character_id)}


@router.get("/dungeons/active-run")
def get_active_dungeon_run_for_character(character_id: int):
    """E22: Return the active (incomplete) dungeon run for a character, if any.

    Searches campaigns with mode='dungeon' and status='active' where the character
    is assigned, then looks for a non-completed dungeon_run in session_flags.
    Returns {active_run: {campaign_id, dungeon_key, current_room, ...} | null}.
    """
    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT c.id AS campaign_id
               FROM campaigns c
               JOIN characters ch ON ch.campaign_id = c.id
               WHERE ch.id = ? AND c.status = 'active'
               ORDER BY c.id DESC""",
            (character_id,),
        ).fetchall()
        for row in rows:
            cid = row["campaign_id"]
            gs = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (cid,),
            ).fetchone()
            if not gs:
                continue
            flags = json.loads(gs["session_flags"] or "{}")
            run = flags.get("dungeon_run")
            if run and not run.get("completed") and not run.get("failed"):
                return {"active_run": {**run, "campaign_id": cid}}
        return {"active_run": None}
    finally:
        conn.close()


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
            "SELECT sheet_json, gold_gp FROM characters WHERE id = ?",  # #1181: legacy `gold` retired
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
        "current_mana": sheet.get("current_mana"),  # L7: for mana restore on death
        "gold_gp": char["gold_gp"],  # #1181: gold_gp is the sole gold column
        "inventory": inventory,
        "xp_lifetime_earned": int(sheet.get("xp_lifetime_earned") or 0),  # L7: XP rollback
        "xp_available": int(sheet.get("xp_available") or 0),
    }
    save_snapshot(campaign_id, turn_number, state_dict, source="dungeon_enter")


# ── Enter ─────────────────────────────────────────────────────────────────────

class DungeonEnterReq(BaseModel):
    character_id: int
    campaign_id: int
    previous_campaign_id: int | None = None  # set when entering mid-campaign


@router.post("/dungeons/{dungeon_key}/enter")
def enter_dungeon(dungeon_key: str, req: DungeonEnterReq, authorization: str | None = Header(None)):
    _guard_dungeon_req(req.character_id, req.campaign_id, authorization)
    if not _is_dungeon_enabled():
        raise HTTPException(
            status_code=403,
            detail={"error": "dungeon_disabled", "message": "Lochy są obecnie wyłączone przez administratora."},
        )

    # AUDIT #1443: entering a dungeon mutates position/session_flags like travel does,
    # so it must honour the same gates — a dead hero can't dive, and you can't leave an
    # active fight by entering a dungeon.
    _dconn = _get_db()
    try:
        _dchar = _dconn.execute(
            "SELECT status, sheet_json FROM characters WHERE id = ?", (req.character_id,)
        ).fetchone()
    finally:
        _dconn.close()
    if _dchar is not None:
        _dsheet = json.loads(_dchar["sheet_json"] or "{}")
        _dhp = _dsheet.get("current_hp")
        if (
            ("status" in _dchar.keys() and _dchar["status"] == "dead")
            or _dsheet.get("status") == "dead"
            or (isinstance(_dhp, (int, float)) and _dhp <= 0)
        ):
            raise HTTPException(status_code=409, detail={"error": "hero_dead", "message": "Bohater nie żyje — nie może wejść do lochu."})
    from app.services.combat_service import get_active_combat as _dget_combat
    if _dget_combat(req.campaign_id):
        raise HTTPException(status_code=409, detail={"error": "in_combat", "message": "Nie można wejść do lochu w trakcie walki."})

    from app.services.dungeon_service import get_dungeon
    from app.services.dungeon_tile_service import enter_dungeon_tiles

    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        raise HTTPException(status_code=404, detail="Dungeon not found")

    hero_level = _get_hero_level(req.character_id)

    # #739: gate by min_level — block heroes below the dungeon's required level.
    min_level = int(dungeon.get("min_level") or 1)
    if hero_level < min_level:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "level_too_low",
                "message": f"Wymagany Poz. {min_level}+ — Twój bohater ma Poz. {hero_level}.",
                "min_level": min_level,
                "hero_level": hero_level,
            },
        )

    # WL-7: bramka pływowa (synergia z WL-5). Cmentarzysko Wraków leży na pasie raf
    # odsłanianym tylko przy odpływie — przy przypływie dojście zalane → 423.
    from app.services import tide_service
    _tide_block = tide_service.dungeon_blocked_by_tide(req.campaign_id, dungeon_key)
    if _tide_block is not None:
        raise HTTPException(
            status_code=423,
            detail={
                "error": "tide_high",
                "message": (
                    "Przypływ zakrył dojście do „"
                    + str(dungeon.get("label", dungeon_key))
                    + f"” — wróć przy odpływie (za ~{_tide_block['hours_to_change']} h)."
                ),
                "hours_to_change": _tide_block["hours_to_change"],
            },
        )

    try:
        instance = enter_dungeon_tiles(
            req.campaign_id, req.character_id, dungeon_key, hero_level,
            previous_campaign_id=req.previous_campaign_id
        )
    except PermissionError as e:
        parts = str(e).split("|")
        detail: dict = {"error": "dungeon_on_cooldown"}
        if len(parts) >= 3:
            detail["cooldown_until"] = parts[1]
            try:
                detail["hours_remaining"] = float(parts[2])
            except (ValueError, IndexError):
                pass
        raise HTTPException(status_code=423, detail=detail)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    _save_dungeon_entry_snapshot(req.campaign_id, req.character_id)

    # #865: resolve bare riddle string keys to dicts before returning, so the fresh-entry
    # path matches the resume endpoint (GET /dungeon-run). Without this the frontend gets
    # content.riddle = "riddle_silence" and renders the bare key instead of the riddle text.
    _conn = _get_db()
    try:
        _resolve_run_riddles(_conn, instance)
    finally:
        _conn.close()

    # Build entry narrative from tile description (Decision 3: DB desc + LLM colorizes)
    label = instance["dungeon_label"]
    graph = instance.get("graph") or {}
    nodes = graph.get("nodes") or {}
    entry_node_id = graph.get("entry_node", "")
    entry_node = nodes.get(entry_node_id) or {}
    entry_content = entry_node.get("content") or {}
    entry_desc = entry_content.get("room_description") or ""

    narrative = f"Wkraczasz do *{label}*."
    if entry_desc:
        narrative += f" {entry_desc}"

    # L12b: teach dungeon mechanics (doors / chest / riddle / death) on first entry.
    onboarding_cards: list[dict] = []
    try:
        from app.services.onboarding_service import get_unseen_cards_for_mechanics
        conn = _get_db()
        try:
            row = conn.execute(
                "SELECT user_id FROM characters WHERE id = ?", (req.character_id,)
            ).fetchone()
            if row and row["user_id"] is not None:
                onboarding_cards = get_unseen_cards_for_mechanics(
                    conn, int(row["user_id"]), ["dungeon_tiles"]
                )
        finally:
            conn.close()
    except Exception:
        onboarding_cards = []

    return {
        "ok": True,
        "dungeon_run": instance,
        "room_narrative": narrative,
        "onboarding_cards": onboarding_cards,
    }


# ── Legacy endpoints (L9: removed) ───────────────────────────────────────────

@router.post("/dungeons/advance-room")
def advance_dungeon_room_gone():
    raise HTTPException(status_code=410, detail="Procedural dungeon system removed. Use /dungeons/move instead.")


@router.post("/dungeons/resolve-room")
def resolve_dungeon_room_gone():
    raise HTTPException(status_code=410, detail="Procedural dungeon system removed. Use /dungeons/resolve-tile instead.")


# ── L6: Resolve tile action ───────────────────────────────────────────────────

class DungeonResolveTileReq(BaseModel):
    character_id: int
    campaign_id: int
    action: str  # open_chest | answer_riddle | riddle_hint | rest
    payload: dict | None = None  # e.g. {"answer": "..."} for answer_riddle


@router.post("/dungeons/resolve-tile")
def resolve_dungeon_tile(req: DungeonResolveTileReq, authorization: str | None = Header(None)):
    """L6: Resolve non-combat tile action.

    Returns action result. 409 when no active v2 dungeon run.
    U22 fallback: missing node returns ok=True, fallback=True (pusty korytarz).
    """
    _guard_dungeon_req(req.character_id, req.campaign_id, authorization)
    from app.services.dungeon_tile_service import resolve_tile_action
    from app.services.dungeon_service import grant_dungeon_loot, get_active_dungeon_run

    try:
        result = resolve_tile_action(req.campaign_id, req.character_id, req.action, req.payload)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if result.get("loot"):
        run = get_active_dungeon_run(req.campaign_id)
        granted = grant_dungeon_loot(
            req.character_id, req.campaign_id, result["loot"],
            loot_tier=(run or {}).get("loot_tier"),
        )
        result["loot"] = granted

    return {"ok": True, **result}


# ── L4: Move through door ─────────────────────────────────────────────────────

class DungeonMoveReq(BaseModel):
    character_id: int
    campaign_id: int
    direction: str  # N / S / E / W


@router.post("/dungeons/move")
def dungeon_move(req: DungeonMoveReq, authorization: str | None = Header(None)):
    """L4: Move through a door in the given direction.

    Returns {ok, node, content, room_description, fog_discovered, is_cleared, combat, narrative}
    on success, or {ok: false, blocked: true, reason: str} when blocked.
    409 when no active v2 dungeon run.
    """
    _guard_dungeon_req(req.character_id, req.campaign_id, authorization)
    from app.services.dungeon_tile_service import move_through_door
    try:
        result = move_through_door(req.campaign_id, req.character_id, req.direction)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return result


# ── L8: Boss choice ───────────────────────────────────────────────────────────

class DungeonBossChoiceReq(BaseModel):
    character_id: int
    campaign_id: int
    choice: str  # "exit" | "go_deeper"


@router.post("/dungeons/boss-choice")
def dungeon_boss_choice(req: DungeonBossChoiceReq, authorization: str | None = Header(None)):
    """L8: After boss defeated (boss_choice_pending=True), player chooses exit or go_deeper.

    exit: complete_dungeon() + 100% cooldown + return to previous campaign.
    go_deeper: extend_dungeon_for_endless() → new graph segment, cycle+=1.
    409 when no active v2 run or boss_choice_pending is False.
    """
    _guard_dungeon_req(req.character_id, req.campaign_id, authorization)
    from app.services.dungeon_service import (
        get_active_dungeon_run, complete_dungeon, clear_dungeon_run,
    )
    from app.services.dungeon_tile_service import extend_dungeon_for_endless
    import sqlite3 as _sl

    run = get_active_dungeon_run(req.campaign_id)
    if not run:
        raise HTTPException(status_code=409, detail="Brak aktywnego runu lochu.")
    if not run.get("boss_choice_pending"):
        raise HTTPException(status_code=409, detail="Nie ma oczekującego wyboru po bossie.")

    if req.choice == "exit":
        dungeon_key = run.get("dungeon_key", "")
        try:
            complete_dungeon(req.character_id, dungeon_key)
        except Exception:
            pass

        previous_campaign_id = None
        conn2 = _sl.connect(DB_PATH)
        conn2.row_factory = _sl.Row
        try:
            row = conn2.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (req.campaign_id,)
            ).fetchone()
            if row:
                _flags = json.loads(row["session_flags"] or "{}")
                previous_campaign_id = _flags.get("dungeon_previous_campaign_id")
        finally:
            conn2.close()

        clear_dungeon_run(req.campaign_id)
        return {
            "ok": True,
            "choice": "exit",
            "previous_campaign_id": previous_campaign_id,
            "narrative": "Wychodzisz z lochu z łupami. Dobrze zrobione.",
        }

    elif req.choice == "go_deeper":
        try:
            result = extend_dungeon_for_endless(req.campaign_id, req.character_id)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return {
            "ok": True,
            "choice": "go_deeper",
            "new_cycle": result["new_cycle"],
            "new_segment_tile_count": result["new_segment_tile_count"],
            "new_entry_node": result["new_entry_node"],
            "new_boss_node": result["new_boss_node"],
            "narrative": f"Schodzisz głębiej. Cykl {result['new_cycle']} — wrogowie są silniejsi.",
        }

    else:
        raise HTTPException(status_code=400, detail="choice musi być 'exit' lub 'go_deeper'.")


# ── Death handling ────────────────────────────────────────────────────────────

@router.post("/dungeons/death")
def dungeon_death(req: DungeonEnterReq, authorization: str | None = Header(None)):
    _guard_dungeon_req(req.character_id, req.campaign_id, authorization)
    from app.services.dungeon_service import handle_dungeon_death
    result = handle_dungeon_death(req.campaign_id, req.character_id)
    return {"ok": True, **result}


# ── Exit dungeon ──────────────────────────────────────────────────────────────

@router.post("/dungeons/exit")
def exit_dungeon(req: DungeonEnterReq, authorization: str | None = Header(None)):
    """L7: Abandon dungeon or exit on win.

    Mid-segment: restore from last checkpoint + 50% cooldown.
    At checkpoint (boss defeated): full reward + 100% cooldown.
    Completed run (win): no restore, no extra cooldown (complete_dungeon already called).
    """
    _guard_dungeon_req(req.character_id, req.campaign_id, authorization)
    from app.services.dungeon_service import (
        get_active_dungeon_run, clear_dungeon_run, handle_dungeon_abandon
    )
    import sqlite3 as _sl

    run = get_active_dungeon_run(req.campaign_id)

    previous_campaign_id = None
    conn = _sl.connect(DB_PATH)
    conn.row_factory = _sl.Row
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (req.campaign_id,)
        ).fetchone()
        if row:
            flags = json.loads(row["session_flags"] or "{}")
            previous_campaign_id = flags.get("dungeon_previous_campaign_id")
    finally:
        conn.close()

    # #752: re-link the hero to the campaign they came from BEFORE returning, so the
    # original campaign is continuable regardless of frontend cache/navigation. The
    # frontend then deletes the disposable dungeon campaign; because the hero already
    # points at the previous campaign, that DELETE no longer idles them.
    relinked_campaign_id = _relink_hero_to_previous(req.character_id, previous_campaign_id)

    if run and run.get("completed"):
        # Win path: complete_dungeon already called; just clear the run
        clear_dungeon_run(req.campaign_id)
        return {
            "ok": True,
            "previous_campaign_id": previous_campaign_id,
            "relinked_campaign_id": relinked_campaign_id,
            "was_completed": True,
            "was_failed": False,
            "restored": False,
            "at_checkpoint": False,
        }

    # Abandon path: L7 logic (mid-segment or at checkpoint)
    abandon_result = handle_dungeon_abandon(req.campaign_id, req.character_id)
    clear_dungeon_run(req.campaign_id)

    return {
        "ok": True,
        "previous_campaign_id": previous_campaign_id,
        "relinked_campaign_id": relinked_campaign_id,
        "was_completed": abandon_result.get("at_checkpoint", False),
        "was_failed": not abandon_result.get("at_checkpoint", False),
        "restored": abandon_result.get("restored", False),
        "at_checkpoint": abandon_result.get("at_checkpoint", False),
        "cooldown_until": abandon_result.get("cooldown_until"),
    }


def _relink_hero_to_previous(character_id: int, previous_campaign_id: int | None) -> int | None:
    """#752: After leaving a dungeon, point the hero back at the campaign they came
    from so it stays continuable. Only re-links to a still-active, non-dungeon
    campaign owned by the hero. Returns the campaign id re-linked to, else None."""
    if not previous_campaign_id:
        return None
    import sqlite3 as _sl
    conn = _sl.connect(DB_PATH)
    conn.row_factory = _sl.Row
    try:
        hero = conn.execute(
            "SELECT user_id FROM characters WHERE id = ? AND is_active = 1",
            (character_id,),
        ).fetchone()
        if not hero:
            return None
        camp = conn.execute(
            "SELECT id, status, mode FROM campaigns WHERE id = ?",
            (int(previous_campaign_id),),
        ).fetchone()
        if not camp or camp["status"] not in ("active", "pending") or camp["mode"] == "dungeon":
            return None
        # #767: a campaign belongs to exactly ONE hero. NEVER evict another hero on
        # relink (this was the recurrence vector — a stale dungeon snapshot pointing
        # at another hero's campaign). Only relink if the target is genuinely this
        # hero's: no OTHER active hero parked there, and no foreign play-history.
        other = conn.execute(
            "SELECT id FROM characters WHERE campaign_id = ? AND is_active = 1 AND id != ?",
            (int(previous_campaign_id), character_id),
        ).fetchone()
        if other:
            return None
        foreign_turn = conn.execute(
            "SELECT 1 FROM campaign_turns WHERE campaign_id = ? "
            "AND character_id IS NOT NULL AND character_id != ? LIMIT 1",
            (int(previous_campaign_id), character_id),
        ).fetchone()
        if foreign_turn:
            return None
        conn.execute(
            "UPDATE characters SET campaign_id = ?, status = 'in_campaign' WHERE id = ?",
            (int(previous_campaign_id), character_id),
        )
        conn.commit()
        return int(previous_campaign_id)
    except Exception:
        return None
    finally:
        conn.close()


# ── Active run ────────────────────────────────────────────────────────────────


def _resolve_run_riddles(conn: sqlite3.Connection, run: dict | None) -> None:
    """Resolve all bare string riddle keys to dicts in-place for all graph nodes.

    The graph generator stores riddle as a bare key string (e.g. "riddle_shadow").
    The frontend needs the full dict {text, answer, hints, solved, ...}.
    Called on resume and post-action paths that re-fetch the full run from DB.
    No-op when run is None or has no graph. (#721)
    """
    if not run:
        return
    from app.services.dungeon_tile_service import _resolve_riddle_in_content
    nodes = (run.get("graph") or {}).get("nodes") or {}
    for node in nodes.values():
        content = (node or {}).get("content")
        if content and isinstance(content.get("riddle"), str):
            try:
                _resolve_riddle_in_content(conn, content)
            except Exception:
                pass


@router.get("/campaigns/{campaign_id}/dungeon-run")
def get_current_dungeon_run(campaign_id: int):
    from app.services.dungeon_service import get_active_dungeon_run
    run = get_active_dungeon_run(campaign_id)

    onboarding_cards: list[dict] = []
    if run:
        conn = _get_db()
        try:
            # #721: resolve bare riddle string keys to dicts for resume/post-action paths
            _resolve_run_riddles(conn, run)

            # L12b: surface the unseen dungeon mechanics codex card so resume/restore paths
            # (not just fresh enter) can teach it. Frontend shows it at most once per load.
            try:
                from app.services.onboarding_service import get_unseen_cards_for_mechanics
                char_id = next(iter((run.get("positions") or {}).keys()), None)
                if char_id is not None:
                    row = conn.execute(
                        "SELECT user_id FROM characters WHERE id = ?", (int(char_id),)
                    ).fetchone()
                    if row and row["user_id"] is not None:
                        onboarding_cards = get_unseen_cards_for_mechanics(
                            conn, int(row["user_id"]), ["dungeon_tiles"]
                        )
            except Exception:
                onboarding_cards = []
        finally:
            conn.close()

    return {"dungeon_run": run, "onboarding_cards": onboarding_cards}


@router.get("/characters/{character_id}/dungeon-history")
def character_dungeon_history(character_id: int):
    from app.services.dungeon_service import get_run_history
    return {"history": get_run_history(character_id)}
