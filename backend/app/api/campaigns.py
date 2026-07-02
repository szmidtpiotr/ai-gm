import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict

from app.core.config import DEFAULT_CAMPAIGN_LANGUAGE
from app.core.jwt_auth import resolve_authed_user_id
from app.core.logging import get_logger
from app.services.history_summary_service import generate_dual_summary_preview
from app.services.solo_death_service import death_summary_payload, end_summary_payload
from app.services.gm_plan_generation_service import retry_initial_gm_plan_for_campaign
from app.services.gm_plan_schema import merge_gm_plan_patch, normalize_gm_plan
from app.services.summary_settings_service import get_dual_summary_preview_mode

DB_PATH = "/data/ai_gm.db"
logger = get_logger(__name__)

router = APIRouter()


def _maybe_add_pending_advantage_gate(row_dict: dict, sf: dict, scene_enemies_raw: str = "[]") -> None:
    """#1045: surface pending_advantage_gate when pending_zaskoczony is set AND enemies are in scene.
    Mirrors the pending_skill_test restore pattern so F5 re-renders the advantage gate card.
    #1046: also checks scene_enemies so a stale flag (after movement) never re-shows the gate.
    """
    if not (isinstance(sf, dict) and sf.get("pending_zaskoczony")):
        return
    try:
        if not json.loads(scene_enemies_raw or "[]"):
            return
    except Exception:
        return
    try:
        from app.services.combat_service import build_advantage_gate
        gate = build_advantage_gate("stealth")
        if gate:
            row_dict["pending_advantage_gate"] = gate
    except Exception:
        pass


def _migrate_template_plan_to_w1(raw: str | None) -> str:
    """Migrate template gm_plan_json from list-arcs format to W1 dict-arcs + acts list.

    Templates store: {"arcs": [{"id": "...", "key_beats": [...], "status": "active"}]}
    W1 engine expects: {"arcs": {"arc_id": {"scene_goals": [...], ...}}}
    V2 runtime expects: {"acts": [{"id": "...", "key_beats": [...]}]}
    """
    try:
        plan = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return "{}"
    arcs = plan.get("arcs")
    if not isinstance(arcs, list) or not arcs:
        return raw or "{}"
    # Populate "acts" for V2 runtime beat tracking
    if not plan.get("acts"):
        plan["acts"] = arcs
    # Convert arcs list → W1 dict keyed by arc.id
    arcs_dict: dict = {}
    active_id: str | None = None
    for i, arc in enumerate(arcs):
        if not isinstance(arc, dict):
            continue
        arc_id = str(arc.get("id", f"arc_{i}"))
        arc_copy = dict(arc)
        if "key_beats" in arc_copy and "scene_goals" not in arc_copy:
            arc_copy["scene_goals"] = [
                b.get("label") or b.get("beat_key", "")
                for b in arc_copy.get("key_beats", [])
                if isinstance(b, dict) and (b.get("label") or b.get("beat_key"))
            ]
        arcs_dict[arc_id] = arc_copy
        if arc.get("status") == "active" and active_id is None:
            active_id = arc_id
    plan["arcs"] = arcs_dict
    if not plan.get("active_arc_id") and active_id:
        plan["active_arc_id"] = active_id
    return json.dumps(plan, ensure_ascii=False)


@router.get("/campaign-modes")
def get_campaign_modes():
    """D9 (#384) — 5 trybów huba kampanii (Nowa/Gotowa/Loch/Loch-kafelki/Multiplayer)
    z flagą `available` zależną od danych, by UI nie prowadził w broken state."""
    from app.services.campaign_modes_service import get_available_modes
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return {"modes": get_available_modes(conn)}
    finally:
        conn.close()


def _is_global_admin(conn: sqlite3.Connection, user_id: int | None) -> bool:
    if user_id is None:
        return False
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False
    try:
        urow = conn.execute(
            "SELECT COALESCE(is_admin, 0) AS ia FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
        return bool(urow and int(urow["ia"] or 0) == 1)
    except sqlite3.OperationalError:
        return False


def _may_view_gm_plan_json(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    owner_user_id: int,
    viewer_user_id: int | None,
) -> bool:
    """T07 / [S11b]: only owner, global admin, or campaign gm/admin role sees `gm_plan_json` in HTTP JSON."""
    if viewer_user_id is None:
        return False
    try:
        vid = int(viewer_user_id)
        oid = int(owner_user_id)
    except (TypeError, ValueError):
        return False
    if vid == oid:
        return True
    if _is_global_admin(conn, vid):
        return True
    try:
        mrow = conn.execute(
            """
            SELECT role FROM campaign_members
            WHERE campaign_id = ? AND user_id = ?
            """,
            (campaign_id, vid),
        ).fetchone()
        if mrow:
            role = str(mrow["role"] or "").strip().lower()
            if role in ("gm", "admin"):
                return True
    except sqlite3.OperationalError:
        pass
    return False


def _apply_gm_plan_visibility(
    conn: sqlite3.Connection,
    row_dict: dict,
    campaign_id: int,
    viewer_user_id: int | None,
) -> dict:
    owner_user_id = int(row_dict.get("owner_user_id") or 0)
    if _may_view_gm_plan_json(
        conn,
        campaign_id=campaign_id,
        owner_user_id=owner_user_id,
        viewer_user_id=viewer_user_id,
    ):
        row_dict = dict(row_dict)
    else:
        row_dict = dict(row_dict)
        row_dict.pop("gm_plan_json", None)
    # Stage 10-C+ — surface any pending skill test so a refreshed client
    # can re-mount the popup. The d20 is server-committed (see
    # _commit_pending_skill_test in turns.py) so F5 cannot reroll.
    try:
        gs = conn.execute(
            "SELECT session_flags, scene_enemies FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if gs and gs["session_flags"]:
            sf = json.loads(gs["session_flags"])
            if isinstance(sf, dict) and sf.get("pending_skill_test"):
                row_dict["pending_skill_test"] = sf["pending_skill_test"]
                row_dict["state_machine"] = sf.get("state") or "SKILL_TEST_PENDING"
            # #1045/#1046: restore advantage gate — only when enemies still in scene
            _maybe_add_pending_advantage_gate(row_dict, sf, gs["scene_enemies"] if gs else "[]")
    except Exception:
        pass
    return row_dict


def _check_hero_dead(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
) -> bool:
    """E5 (#420) — check if hero is dead (hero_status='dead')."""
    try:
        row = conn.execute(
            "SELECT status FROM characters WHERE id = ? AND campaign_id = ?",
            (character_id, campaign_id),
        ).fetchone()
        return bool(row and row["status"] == "dead")
    except sqlite3.OperationalError:
        return False


def _get_campaign_with_hero_state(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
) -> dict | None:
    """E5 (#420) — get campaign with hero_blocked and hero_status fields.

    Returns None if campaign not found.
    Adds hero_blocked=True if attached hero has status='dead'.
    """
    try:
        # Fetch campaign
        c_row = conn.execute(
            """
            SELECT id, title, system_id, model_id, owner_user_id,
                   language, mode, status, created_at, gm_plan_json,
                   finale_available, host_user_id
            FROM campaigns
            WHERE id = ?
            """,
            (campaign_id,),
        ).fetchone()
        if not c_row:
            return None

        campaign_dict = dict(c_row)
        campaign_dict["finale_available"] = bool(campaign_dict.get("finale_available"))

        # Fetch attached hero status if any
        hero_status = None
        try:
            ch_row = conn.execute(
                """
                SELECT ch.status
                FROM characters ch
                WHERE ch.campaign_id = ? AND ch.status IN ('dead', 'in_campaign')
                LIMIT 1
                """,
                (campaign_id,),
            ).fetchone()
            if ch_row:
                hero_status = ch_row["status"]
        except sqlite3.OperationalError:
            pass

        campaign_dict["hero_status"] = hero_status
        campaign_dict["hero_blocked"] = hero_status == "dead"
        return campaign_dict
    except sqlite3.OperationalError:
        return None


def _parse_gm_plan(raw: str | None) -> dict:
    return normalize_gm_plan(raw)


class CampaignCreateRequest(BaseModel):
    title: str
    system_id: str
    model_id: str
    owner_user_id: int
    language: str = DEFAULT_CAMPAIGN_LANGUAGE
    mode: str = "solo"
    status: str = "active"
    # E8 (#423) — launch a ready campaign from a published template.
    template_id: int | None = None
    # E28 (#443) — tutorial campaign flag.
    is_tutorial: bool = False


class GmPlanPatchRequest(BaseModel):
    """Merge into `gm_plan_json` (W1: `arcs` / `engine_private` — deep merge; legacy flat keys → aktywny łuk)."""

    model_config = ConfigDict(extra="forbid")
    gm_plan_json: dict


@router.get("/campaigns")
def list_campaigns():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            c.id,
            c.title,
            c.system_id,
            c.model_id,
            c.owner_user_id,
            c.language,
            c.mode,
            c.status,
            c.created_at,
            c.gm_plan_json,
            (SELECT COUNT(*) FROM characters ch WHERE ch.campaign_id = c.id) AS character_count,
            (SELECT ch.id FROM characters ch WHERE ch.campaign_id = c.id AND ch.is_active = 1 LIMIT 1) AS character_id,
            (SELECT ch.status FROM characters ch WHERE ch.campaign_id = c.id AND ch.status IN ('dead', 'in_campaign') LIMIT 1) AS hero_status
        FROM campaigns c
        WHERE NOT (
            c.status = 'active'
            AND (SELECT COUNT(*) FROM characters ch WHERE ch.campaign_id = c.id) = 0
            AND c.created_at IS NOT NULL
            AND c.created_at < datetime('now', '-1 hour')
        )
        ORDER BY c.id ASC
        """
    ).fetchall()

    conn.close()

    # Stage 9 follow-up: surface the GM-plan's premise/roadmap as the campaign
    # description, and a `plan_ready` boolean so the UI can show a spinner /
    # placeholder until the plan finishes generating.
    out = []
    for row in rows:
        item = dict(row)
        raw_plan = item.pop("gm_plan_json", None) or ""
        plan_ready = False
        description = ""
        if raw_plan and raw_plan.strip() and raw_plan.strip() != "{}":
            try:
                plan = json.loads(raw_plan)
            except Exception:
                plan = {}
            if isinstance(plan, dict):
                # Try W1 schema first: top-level title/premise/roadmap.
                title = str(plan.get("title") or "").strip()
                premise = str(plan.get("premise") or "").strip()
                roadmap = str(plan.get("roadmap") or "").strip()
                # V2 schema: arcs.default.title / arcs.default.roadmap (or the active arc).
                if not (title or premise or roadmap):
                    arcs = plan.get("arcs") or {}
                    if isinstance(arcs, dict):
                        # Prefer the active arc, else first one.
                        active_arc = next((a for a in arcs.values()
                                           if isinstance(a, dict) and str(a.get("status") or "").lower() == "active"),
                                          None)
                        if active_arc is None and arcs:
                            active_arc = next(iter(arcs.values()))
                        if isinstance(active_arc, dict):
                            title = str(active_arc.get("title") or "").strip()
                            roadmap = str(active_arc.get("roadmap") or "").strip()
                description = (premise or roadmap)[:240]
                plan_ready = bool(title or premise or roadmap)
        item["description"] = description
        item["plan_ready"] = plan_ready
        # E5 (#420) — mark campaigns with dead heroes as blocked
        hero_status = item.get("hero_status")
        item["hero_blocked"] = hero_status == "dead"
        out.append(item)

    return {"campaigns": out}


@router.get("/campaigns/{campaign_id}/dice-rolls")
def get_campaign_dice_rolls(
    campaign_id: int,
    roll_type: str | None = Query(None, description="Filtr typu rzutu (np. skill_test, attack_player)."),
    from_turn: float | None = Query(None, description="Dolny zakres turn_number (włącznie)."),
    to_turn: float | None = Query(None, description="Górny zakres turn_number (włącznie)."),
    limit: int = Query(100, ge=1, le=1000),
):
    """#754: strukturalny rejestr rzutów kampanii (najnowsze pierwsze)."""
    from app.services.dice_log_service import query_dice_rolls
    rolls = query_dice_rolls(
        campaign_id, roll_type=roll_type, from_turn=from_turn, to_turn=to_turn, limit=limit
    )
    return {"campaign_id": campaign_id, "count": len(rolls), "dice_rolls": rolls}


@router.get("/campaigns/{campaign_id}/state-changes")
def get_campaign_state_changes(
    campaign_id: int,
    resource: str | None = Query(None, description="Filtr zasobu: hp|mana|condition|zone."),
    from_turn: float | None = Query(None),
    to_turn: float | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """#761: rejestr zmian zasobów/kondycji gracza (before→after+cause+tura)."""
    from app.services.state_log_service import query_state_changes
    changes = query_state_changes(
        campaign_id, resource=resource, from_turn=from_turn, to_turn=to_turn, limit=limit
    )
    return {"campaign_id": campaign_id, "count": len(changes), "state_changes": changes}


@router.get("/campaigns/{campaign_id}/turn-decisions")
def get_campaign_turn_decisions(
    campaign_id: int,
    from_turn: float | None = Query(None),
    to_turn: float | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """#762: rejestr decyzji silnika per tura (intent/route/gate)."""
    from app.services.decision_log_service import query_turn_decisions
    decisions = query_turn_decisions(
        campaign_id, from_turn=from_turn, to_turn=to_turn, limit=limit
    )
    return {"campaign_id": campaign_id, "count": len(decisions), "turn_decisions": decisions}


@router.get("/campaigns/{campaign_id}/game-events")
def get_campaign_game_events(
    campaign_id: int,
    event_type: str | None = Query(None, description="Filtr typu zdarzenia."),
    severity: str | None = Query(None, description="Filtr severity: info|warning|error."),
    limit: int = Query(200, ge=1, le=1000),
):
    """#781: rejestr zdarzeń narracyjnych+walki per kampania (game_events, najnowsze pierwsze)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        where = ["campaign_id = ?"]
        params: list = [campaign_id]
        if event_type:
            where.append("event_type = ?"); params.append(event_type)
        if severity:
            where.append("severity = ?"); params.append(severity)
        params.append(limit)
        rows = conn.execute(
            "SELECT id, event_type, severity, character_id, user_id, event_data, created_at "
            "FROM game_events WHERE " + " AND ".join(where)
            + " ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()
        out = []
        for r in rows:
            try:
                data = json.loads(r["event_data"] or "{}")
            except (TypeError, ValueError):
                data = {}
            out.append({
                "id": r["id"],
                "event_type": r["event_type"],
                "severity": r["severity"],
                "character_id": r["character_id"],
                "user_id": r["user_id"],
                "data": data,
                "created_at": r["created_at"],
            })
        return {"campaign_id": campaign_id, "count": len(out), "game_events": out}
    finally:
        conn.close()


@router.get("/campaigns/{campaign_id}/world-snapshots")
def get_campaign_world_snapshots(
    campaign_id: int,
    from_turn: int | None = Query(None),
    to_turn: int | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
):
    """#760: przycięty stan świata per tura (debug bez replayu)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        where = ["campaign_id = ?"]
        params: list = [campaign_id]
        if from_turn is not None:
            where.append("turn_number >= ?"); params.append(from_turn)
        if to_turn is not None:
            where.append("turn_number <= ?"); params.append(to_turn)
        params.append(limit)
        rows = conn.execute(
            "SELECT turn_number, snapshot_json, snapshot_source, created_at "
            "FROM world_state_snapshots WHERE " + " AND ".join(where)
            + " ORDER BY turn_number DESC LIMIT ?",
            params,
        ).fetchall()
        out = []
        for r in rows:
            try:
                snap = json.loads(r["snapshot_json"] or "{}")
            except (TypeError, ValueError):
                snap = {}
            enemies = snap.get("scene_enemies") or []
            out.append({
                "turn_number": r["turn_number"],
                "scene_cleared": snap.get("scene_cleared"),
                "enemies": [
                    {"key": e.get("key") or e.get("enemy_key"), "name": e.get("name"), "hp": e.get("hp")}
                    for e in enemies if isinstance(e, dict)
                ],
                "enemy_count": len(enemies),
                "npcs": [n.get("name") or n.get("key") for n in (snap.get("scene_npcs") or []) if isinstance(n, dict)],
                "quests": [(q if isinstance(q, str) else (q.get("title") or q.get("key"))) for q in (snap.get("active_quests") or [])],
                "conditions": [(c if isinstance(c, str) else c.get("key")) for c in (snap.get("player_conditions") or [])],
                "source": r["snapshot_source"],
                "created_at": r["created_at"],
            })
        return {"campaign_id": campaign_id, "count": len(out), "snapshots": out}
    finally:
        conn.close()


@router.get("/admin/campaigns/{campaign_id}/llm-calls")
def get_campaign_llm_calls(
    campaign_id: int,
    call_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
):
    """#760: telemetria wywołań LLM per kampania (typ/model/tokeny/latencja/cache/error)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        where = ["campaign_id = ?"]
        params: list = [campaign_id]
        if call_type:
            where.append("call_type = ?"); params.append(call_type)
        params.append(limit)
        rows = conn.execute(
            "SELECT call_type, model, prompt_tokens, completion_tokens, latency_ms, "
            "cache_hit, error, created_at FROM llm_call_log WHERE " + " AND ".join(where)
            + " ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()
        calls = [dict(r) for r in rows]
        return {"campaign_id": campaign_id, "count": len(calls), "llm_calls": calls}
    finally:
        conn.close()


@router.get("/campaigns/{campaign_id}")
def get_campaign(
    campaign_id: int,
    user_id: int | None = Query(
        None,
        description="Viewer user id (legacy fallback); prefer Authorization: Bearer.",
    ),
    authorization: str | None = Header(default=None),
):
    # JWT-aware viewer resolution. Best-effort — visibility falls back to
    # "no plan visible" when neither auth source is present, which is the
    # safest default for this endpoint.
    effective_uid = user_id
    if authorization:
        try:
            effective_uid = resolve_authed_user_id(authorization, user_id)
        except HTTPException:
            effective_uid = user_id
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # E5 (#420) — include hero status + hero_blocked flag
        campaign_dict = _get_campaign_with_hero_state(conn, campaign_id=campaign_id)
        if not campaign_dict:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return _apply_gm_plan_visibility(conn, campaign_dict, campaign_id, effective_uid)
    finally:
        conn.close()


@router.get("/campaigns/{campaign_id}/turns-history")
def get_campaign_turns_player(
    campaign_id: int,
    user_id: int | None = Query(None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
):
    """#900/#1065: Read-only turn history for archived campaign viewer (player-facing).

    Works for campaigns with any status — owner check via user_id/JWT.
    Returns turns oldest-first for chronological reading.
    Supports offset pagination; response includes total_count.
    """
    effective_uid = resolve_authed_user_id(authorization, user_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        camp = conn.execute(
            "SELECT id, owner_user_id, title, status FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if effective_uid and int(camp["owner_user_id"]) != int(effective_uid):
            raise HTTPException(status_code=403, detail="Not your campaign")

        total_count = conn.execute(
            "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()[0]
        rows = conn.execute(
            """SELECT turn_number, user_text, assistant_text, created_at
               FROM campaign_turns
               WHERE campaign_id = ?
               ORDER BY turn_number ASC, id ASC
               LIMIT ? OFFSET ?""",
            (campaign_id, limit, offset),
        ).fetchall()
        return {
            "campaign_id": campaign_id,
            "title": camp["title"],
            "status": camp["status"],
            "total_count": total_count,
            "turns": [dict(r) for r in rows],
        }
    finally:
        conn.close()


@router.patch("/campaigns/{campaign_id}/gm-plan")
def patch_campaign_gm_plan(
    campaign_id: int,
    req: GmPlanPatchRequest,
    user_id: int | None = Query(None, description="Legacy fallback — prefer Authorization: Bearer."),
    authorization: str | None = Header(default=None),
):
    user_id = resolve_authed_user_id(authorization, user_id)
    """
    Owner-only merge into `gm_plan_json` (**[S11a]** / T06 W1).
    Prefer body: `arcs`, `active_arc_id`, `engine_private`. Stare, płaskie klucze
    (`roadmap`, `scene_goals`, …) trafiają do **aktywnego łuku**, o ile nie podano `arcs` w tym samym żądaniu.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, owner_user_id, gm_plan_json FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if int(row["owner_user_id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="user_id must match campaign owner")
        base = _parse_gm_plan(row["gm_plan_json"])
        merged = merge_gm_plan_patch(base, req.gm_plan_json)
        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
            (json.dumps(merged, ensure_ascii=False), campaign_id),
        )
        conn.commit()
        out = conn.execute(
            "SELECT id, title, system_id, model_id, owner_user_id, language, mode, status, created_at, gm_plan_json FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        return dict(out) if out else {}
    except sqlite3.OperationalError as e:
        if "no such column" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail="gm_plan_json column missing — apply migrations and restart API",
            ) from None
        raise HTTPException(status_code=500, detail=str(e)) from None
    finally:
        conn.close()


@router.post("/campaigns/{campaign_id}/gm-plan/generate-initial")
def post_generate_initial_gm_plan(
    campaign_id: int,
    user_id: int | None = Query(None, description="Legacy fallback — prefer Authorization: Bearer."),
    authorization: str | None = Header(default=None),
):
    """
    T05: ponów generację początkowego planu MG (owner), np. gdy LLM padł przy tworzeniu postaci.
    """
    user_id = resolve_authed_user_id(authorization, user_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ok, err = retry_initial_gm_plan_for_campaign(
            conn, campaign_id=campaign_id, owner_user_id=int(user_id)
        )
        if not ok:
            if err == "campaign_not_found":
                raise HTTPException(status_code=404, detail="Campaign not found")
            if err == "forbidden":
                raise HTTPException(status_code=403, detail="user_id must match campaign owner")
            raise HTTPException(
                status_code=502,
                detail=err or "Nie udało się wygenerować planu MG",
            )
        row = conn.execute(
            "SELECT id, gm_plan_json FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        plan_raw = (row["gm_plan_json"] if row else None) or "{}"
        try:
            plan_dict = json.loads(plan_raw) if isinstance(plan_raw, str) else {}
        except json.JSONDecodeError:
            plan_dict = {}
        return {"ok": True, "campaign_id": campaign_id, "gm_plan_json": plan_dict}
    except HTTPException:
        raise
    except sqlite3.OperationalError as e:
        if "no such column" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail="gm_plan_json column missing — apply migrations and restart API",
            ) from None
        raise HTTPException(status_code=500, detail=str(e)) from None
    finally:
        conn.close()


@router.get("/campaigns/{campaign_id}/death-summary")
def get_campaign_death_summary(campaign_id: int):
    """Solo tombstone payload — only when campaign.status == ended."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        payload = death_summary_payload(conn, campaign_id)
    finally:
        conn.close()
    if payload is None:
        raise HTTPException(status_code=404, detail="Campaign not ended or not found")
    return payload


@router.get("/campaigns/{campaign_id}/quests")
def get_campaign_quests(campaign_id: int):
    """E1 (#416) — Player-facing active quests for the HUD quest bar.

    #999: reads character_quests (status='active') — the single source of truth —
    instead of world_state.active_quests, which drifted (completed quests never
    pruned, new ones never added). Keeps the bar in sync with the quest lifecycle.
    """
    from app.services.quest_persist_service import get_active_quests_for_bar
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")
        active = get_active_quests_for_bar(conn, campaign_id)
    finally:
        conn.close()
    return {"active_quests": active}


@router.get("/campaigns/{campaign_id}/journal")
def get_campaign_journal(campaign_id: int):
    """U18 (#570) — Player journal: Zadania / Wątki / Kronika.

    Read-only composition of character_quests + narrative_state seeds/events +
    completed beats. GM-plan secret seeds (player_visible=False) are filtered out.
    """
    from app.services.journal_service import build_journal
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return build_journal(campaign_id, conn)
    finally:
        conn.close()


@router.get("/campaigns/{campaign_id}/recap")
def get_campaign_recap(campaign_id: int):
    """U19 (#571) — "Poprzednio w Twojej przygodzie…" recap.

    Read-only. The >24h trigger (`should_show`) is decided by the backend from
    campaign_turns.created_at; the card reuses the saved player summary + last
    turns + active quests and never calls the LLM (Zasady 1–5).
    """
    from app.services.journal_service import build_recap
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return build_recap(campaign_id, conn)
    finally:
        conn.close()


@router.get("/campaigns/{campaign_id}/end-summary")
def get_campaign_end_summary(campaign_id: int):
    """Stage 9 P5+P6 — unified summary for both death AND victory screens.

    Returns:
      outcome='death'   when campaigns.status == 'ended'
      outcome='victory' when campaigns.status == 'completed'
      404 otherwise
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        payload = end_summary_payload(conn, campaign_id)
    finally:
        conn.close()
    if payload is None:
        raise HTTPException(status_code=404, detail="Campaign not ended yet")
    return payload


@router.post("/campaigns")
def create_campaign(req: CampaignCreateRequest):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # E8 (#423) — when launching from a template, copy its GM plan into the new
    # campaign and bump the template play_count.
    tpl_plan = "{}"
    if req.template_id is not None:
        tpl = conn.execute(
            "SELECT gm_plan_json FROM campaign_templates WHERE id = ? AND status = 'published'",
            (req.template_id,),
        ).fetchone()
        if not tpl:
            conn.close()
            raise HTTPException(status_code=404, detail="Published template not found")
        tpl_plan = _migrate_template_plan_to_w1(tpl["gm_plan_json"] or "{}")

    cur.execute(
        """
        INSERT INTO campaigns (title, system_id, model_id, owner_user_id, language, mode, status, gm_plan_json, is_tutorial)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            req.title,
            req.system_id,
            req.model_id,
            req.owner_user_id,
            req.language,
            req.mode,
            req.status,
            tpl_plan,
            1 if req.is_tutorial else 0,
        ),
    )
    conn.commit()

    campaign_id = cur.lastrowid

    if req.template_id is not None:
        conn.execute(
            "UPDATE campaign_templates SET play_count = play_count + 1 WHERE id = ?",
            (req.template_id,),
        )
        # U8 #532: store source_template_id to detect Gotowa Kampania for Story Gravity L3
        try:
            conn.execute(
                "UPDATE campaigns SET source_template_id = ? WHERE id = ?",
                (req.template_id, campaign_id),
            )
        except Exception:
            pass  # column may not exist yet — migration will add it on next restart
        conn.commit()
        # E11 (#426) — pre-seed NarrativeState from the template's narrative_hooks.
        try:
            from app.services.narrative_state_service import seed_narrative_state_from_plan
            seed_narrative_state_from_plan(campaign_id, json.loads(tpl_plan or "{}"), conn)
        except Exception:
            pass

    row = conn.execute(
        """
        SELECT id, title, system_id, model_id, owner_user_id, language, mode, status, created_at,
               gm_plan_json
        FROM campaigns
        WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=500, detail="Campaign created but could not be loaded")

    out = _apply_gm_plan_visibility(conn, dict(row), campaign_id, req.owner_user_id)
    conn.close()

    # NOTE: Chat history lives in the frontend — switching to a new campaign
    # clears the UI automatically because the campaign_id changes.
    # The backend does not maintain an in-memory chat state.
    return out


@router.post("/campaigns/{campaign_id}/reset")
def reset_campaign_progress(campaign_id: int):
    """
    Dev / playtest: clear chat turns, combat state, AI summaries; reopen ended campaign.
    Does not delete the campaign row or characters.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, status FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")

        conn.execute("BEGIN")
        conn.execute("DELETE FROM combat_turns WHERE campaign_id = ?", (campaign_id,))
        conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
        conn.execute("DELETE FROM campaign_turns WHERE campaign_id = ?", (campaign_id,))
        try:
            conn.execute("DELETE FROM campaign_ai_summaries WHERE campaign_id = ?", (campaign_id,))
        except sqlite3.OperationalError:
            pass
        conn.execute(
            """
            UPDATE campaigns
            SET status = 'active',
                death_reason = NULL,
                ended_at = NULL,
                epitaph = NULL
            WHERE id = ?
            """,
            (campaign_id,),
        )
        conn.commit()
        logger.info(
            "campaign_progress_reset",
            campaign_id=campaign_id,
            previous_status=str(row["status"] or ""),
        )
        return {"ok": True, "campaign_id": campaign_id}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Campaign reset failed: {e}") from None
    finally:
        conn.close()


@router.post("/campaigns/{campaign_id}/finish")
def finish_campaign_endpoint(
    campaign_id: int,
    user_id: int | None = Query(None, description="Legacy fallback — prefer Authorization: Bearer."),
    authorization: str | None = Header(default=None),
):
    """#1097 — player-triggered finale. Requires the #1009 gate to be open
    (`finale_available=1`, set by `maybe_complete_campaign` after every turn).
    Host-only in multiplayer (owner_user_id / host_user_id); solo campaigns
    always pass that check since the owner is the only possible caller.

    Flips `status='completed'` + `ended_at`, logs `campaign_complete`
    (trigger=`player_finish`), then best-effort schedules the chapter summary
    with outcome=`victory` (mirrors the death-flow in api/turns.py — the async
    summary job must never block this response).
    """
    resolved_user_id = resolve_authed_user_id(authorization, user_id)
    from app.services.campaign_plan_runtime import finish_campaign

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        char_row = conn.execute(
            "SELECT id, user_id, sheet_json FROM characters "
            "WHERE campaign_id = ? AND is_active = 1 LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not char_row:
            raise HTTPException(status_code=404, detail="Brak aktywnego bohatera w tej kampanii.")
        turn_number = conn.execute(
            "SELECT COALESCE(MAX(turn_number), 1) FROM campaign_turns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()[0]

        result = finish_campaign(
            campaign_id, int(char_row["id"]), resolved_user_id, int(turn_number), conn
        )
        if not result["ok"]:
            code = 404 if result["error"] == "not_found" else (
                403 if result["error"] == "not_host" else 409
            )
            raise HTTPException(status_code=code, detail=result["error"])

        if not result["already_completed"]:
            try:
                from app.services.chapter_summary_service import close_campaign_with_summary
                sheet = json.loads(char_row["sheet_json"] or "{}")
                turns_count = conn.execute(
                    "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ? AND route = 'narrative'",
                    (campaign_id,),
                ).fetchone()[0]
                close_campaign_with_summary(
                    conn,
                    campaign_id=campaign_id,
                    character_id=int(char_row["id"]),
                    outcome="victory",
                    user_id=int(char_row["user_id"]),
                    xp_earned=int(sheet.get("xp_lifetime_earned") or 0),
                    gold_at_end=int(sheet.get("gold_gp") or sheet.get("gold") or 0),
                    turns_count=int(turns_count or 0),
                )
            except Exception as _cs_err:
                logger.warning("finish_campaign_chapter_summary_error", error=str(_cs_err))

        return {"ok": True, "campaign_id": campaign_id, "ended_at": result.get("ended_at")}
    finally:
        conn.close()


@router.post("/campaigns/{campaign_id}/dual-summary-preview")
def dual_summary_preview(
    campaign_id: int,
    user_id: int | None = Query(None, description="Legacy fallback — prefer Authorization: Bearer."),
    max_turns: int = Query(200, ge=5, le=2000),
    authorization: str | None = Header(default=None),
):
    """
    [T01] One LLM call → JSON player_summary + gm_notes. Does NOT persist to campaign_ai_summaries.
    Mounted on campaigns router (same prefix /api) so the path is always registered with core campaign API.
    """
    user_id = resolve_authed_user_id(authorization, user_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if int(row["owner_user_id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="user_id must match campaign owner")
        preview_mode = get_dual_summary_preview_mode(conn)
        if preview_mode == "off":
            raise HTTPException(status_code=403, detail="Dual summary preview is disabled.")
        if preview_mode == "owner_admin" and not _is_global_admin(conn, user_id):
            raise HTTPException(
                status_code=403,
                detail="Dual summary preview requires campaign owner with global admin role.",
            )
    finally:
        conn.close()

    try:
        result = generate_dual_summary_preview(
            campaign_id=campaign_id,
            user_id=user_id,
            max_turns=max_turns,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    except ValueError as e:
        if str(e) == "campaign_not_found":
            raise HTTPException(status_code=404, detail="Campaign not found") from None
        raise

    return {
        "campaign_id": campaign_id,
        "player_summary": result.get("player_summary", ""),
        "gm_notes": result.get("gm_notes", ""),
        "leaked_plan_tokens": result.get("leaked_plan_tokens") or [],
        "model_used": result.get("model_used"),
        "included_turn_count": int(result.get("included_turn_count") or 0),
        "warning": result.get("warning"),
        "parse_error": result.get("parse_error"),
        "raw_preview": result.get("raw_preview"),
        "persisted": False,
    }


@router.post("/campaigns/{campaign_id}/build-camp")
def build_camp(campaign_id: int):
    """Stage 2B R4 — player action "Rozbij obóz".

    Creates a temporary `temp_camp_*` sub-location on the player's current hex
    with `safe_for_rest=1`, advances clock +1h, and sets
    `session_flags.camp_encounter_boost = 0.20` (consumed by the next /rest call).

    Gates:
      - 404 if no active session
      - 409 if hero is in combat
      - 409 if current hex is already `safe_for_rest=1`
      - 404 if current hex unknown / session has no `current_hex`
    """
    from app.services import world_service
    from app.services.clock_service import advance_clock
    from app.services.combat_service import get_active_combat

    if get_active_combat(campaign_id):
        raise HTTPException(status_code=409, detail="Nie można rozbić obozu w trakcie walki.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        session_row = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not session_row:
            raise HTTPException(status_code=404, detail="Brak aktywnej sesji dla kampanii.")

        flags = json.loads(session_row["session_flags"] or "{}")
        current_hex = flags.get("current_hex") or {}
        q = current_hex.get("q")
        r = current_hex.get("r")
        if q is None or r is None:
            raise HTTPException(status_code=404, detail="Sesja nie ma zapisanej pozycji hex.")

        try:
            location = world_service.build_camp(conn, campaign_id, int(q), int(r))
        except ValueError as e:
            msg = str(e)
            if msg == "hex_already_safe":
                raise HTTPException(status_code=409, detail="Ten hex jest już bezpieczny do odpoczynku — obóz zbędny.")
            if msg == "no_hex_record":
                raise HTTPException(status_code=404, detail="Bieżący hex nie istnieje w bazie.")
            if msg.startswith("settlement_has_rest"):
                parts = msg.split("|", 2)
                suggested_key = parts[1] if len(parts) > 1 else None
                suggested_label = parts[2] if len(parts) > 2 else None
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "W tej osadzie jest miejsce odpoczynku — obóz zbędny.",
                        "suggested_rest_location": {"key": suggested_key, "label": suggested_label} if suggested_key else None,
                    },
                )
            raise HTTPException(status_code=400, detail=msg)

        # Re-read flags (build_camp commits, but doesn't touch session_flags)
        flags["camp_encounter_boost"] = 0.20
        flags["current_location_key"] = location["key"]
        conn.execute(
            "UPDATE game_sessions SET session_flags = ?, current_location_id = (SELECT id FROM game_locations WHERE key = ?) WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), location["key"], session_row["id"]),
        )
        # #825: clear scene_enemies when moving to camp — prior encounter enemies
        # (pre-spawn, no hp) must not persist into the new temp_camp sublocation.
        conn.execute(
            "UPDATE game_sessions SET scene_enemies = '[]', scene_npcs = '[]' WHERE campaign_id = ?",
            (campaign_id,),
        )
        conn.commit()

        clock = advance_clock(campaign_id, 1, reason="camp_setup")
        return {
            "ok": True,
            "location": location,
            "current_clock": clock,
            "encounter_boost": 0.20,
        }
    finally:
        conn.close()


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(campaign_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute(
            "SELECT id FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # #1096 (1B) — capture context BEFORE turns are deleted, so we can
        # generate an "unfinished business" scar for campaigns played long enough.
        _camp_title = ""
        _abandon_transcript = ""
        _narrative_turns = 0
        try:
            _ct_row = conn.execute(
                "SELECT title FROM campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
            _camp_title = str((_ct_row["title"] if _ct_row else "") or "Bezimienna wyprawa")
            _narrative_turns = int(conn.execute(
                "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ? AND route = 'narrative'",
                (campaign_id,),
            ).fetchone()[0] or 0)
            from app.services.chapter_summary_service import (
                _fetch_last_turns,
                should_generate_abandonment_note,
            )
            if should_generate_abandonment_note(_narrative_turns):
                _abandon_transcript = _fetch_last_turns(conn, campaign_id)
        except Exception as _pre_err:
            logger.warning("abandon_precapture_failed", error=str(_pre_err))

        conn.execute("BEGIN")

        # Stage 6 write hook — record an `abandoned` history row for each hero
        # in this campaign before unlinking. Idempotent: skip if a non-active
        # history row already exists for (character, campaign).
        heroes_in = conn.execute(
            """
            SELECT c.id, c.name, c.user_id, c.sheet_json,
                   (SELECT COUNT(*) FROM campaign_turns t WHERE t.campaign_id = ?) AS turns_count,
                   COALESCE(c.gold_gp, 0) AS gold_at_end
            FROM characters c WHERE c.campaign_id = ?
            """,
            (campaign_id, campaign_id),
        ).fetchall()
        _pending_scars: list[dict] = []  # scheduled after commit
        for h in heroes_in:
            try:
                sheet = json.loads(h["sheet_json"] or "{}")
            except Exception:
                sheet = {}
            xp_lifetime = int(sheet.get("xp_lifetime_earned") or 0)
            already = conn.execute(
                """
                SELECT 1 FROM character_campaign_history
                WHERE character_id = ? AND campaign_id = ? AND outcome != 'active'
                LIMIT 1
                """,
                (int(h["id"]), campaign_id),
            ).fetchone()
            if already:
                continue
            cur = conn.execute(
                """
                INSERT INTO character_campaign_history
                  (character_id, campaign_id, outcome, xp_earned, gold_at_end, turns_count, completed_at)
                VALUES (?, ?, 'abandoned', ?, ?, ?, datetime('now'))
                """,
                (int(h["id"]), campaign_id, xp_lifetime, int(h["gold_at_end"]), int(h["turns_count"])),
            )
            # #1096 (1B) — queue an abandonment scar when the run had real play.
            # Loot/XP still persist (Hero-First) — this is a narrative mark only.
            if _abandon_transcript:
                _pending_scars.append({
                    "history_id": int(cur.lastrowid),
                    "name": str(h["name"] or "Bohater"),
                    "user_id": int(h["user_id"] or 0),
                })
                # #1099 — anti-farm: farm-and-bail lowers regional reputation (the
                # narrative scar becomes a mechanical dent). Real play only.
                try:
                    from app.services import reputation_service as rep
                    rep.apply_campaign_outcome(conn, int(h["id"]), campaign_id, "abandoned")
                except Exception as _rep_err:
                    logger.warning("reputation_abandon_failed", error=str(_rep_err))

        conn.execute(
            "DELETE FROM campaign_turns WHERE campaign_id = ?",
            (campaign_id,),
        )

        # Free heroes — keep them, just unlink from this campaign
        conn.execute(
            "UPDATE characters SET campaign_id = NULL, status = 'idle' WHERE campaign_id = ?",
            (campaign_id,),
        )

        conn.execute(
            "DELETE FROM campaigns WHERE id = ?",
            (campaign_id,),
        )

        conn.commit()

        # After commit: fire-and-forget scar generation (daemon thread, own DB).
        if _pending_scars:
            try:
                from app.services.chapter_summary_service import schedule_abandonment_note
                for _scar in _pending_scars:
                    schedule_abandonment_note(
                        history_id=_scar["history_id"],
                        name=_scar["name"],
                        campaign_title=_camp_title,
                        transcript=_abandon_transcript,
                        user_id=_scar["user_id"],
                    )
            except Exception as _scar_err:
                logger.warning("abandon_scar_schedule_failed", error=str(_scar_err))

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete campaign: {str(e)}")
    finally:
        conn.close()
