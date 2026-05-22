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
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if gs and gs["session_flags"]:
            sf = json.loads(gs["session_flags"])
            if isinstance(sf, dict) and sf.get("pending_skill_test"):
                row_dict["pending_skill_test"] = sf["pending_skill_test"]
                row_dict["state_machine"] = sf.get("state") or "SKILL_TEST_PENDING"
    except Exception:
        pass
    return row_dict


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
            (SELECT ch.id FROM characters ch WHERE ch.campaign_id = c.id AND ch.is_active = 1 LIMIT 1) AS character_id
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
        out.append(item)

    return {"campaigns": out}


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
            raise HTTPException(status_code=404, detail="Campaign not found")

        return _apply_gm_plan_visibility(conn, dict(row), campaign_id, effective_uid)
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


@router.post("/campaigns/{campaign_id}/gm-plan/advance-scene")
def advance_campaign_scene(
    campaign_id: int,
    user_id: int | None = Query(None, description="Legacy fallback — prefer Authorization: Bearer."),
    note: str = Query("", max_length=2000, description="Optional note for the scene log."),
    authorization: str | None = Header(default=None),
):
    """
    Increment `current_scene_ordinal` and append `scene_log` entry (**[S11a]** / **[S10c]** boundary).
    """
    user_id = resolve_authed_user_id(authorization, user_id)
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

        tr = conn.execute(
            """
            SELECT MAX(turn_number) AS m
            FROM campaign_turns
            WHERE campaign_id = ? AND route = 'narrative'
            """,
            (campaign_id,),
        ).fetchone()
        through_turn = int(tr["m"] or 0) if tr else 0

        plan = _parse_gm_plan(row["gm_plan_json"])
        arcs: dict = plan.get("arcs") if isinstance(plan.get("arcs"), dict) else {}
        active = plan.get("active_arc_id")
        if isinstance(active, str) and active.strip() and active in arcs:
            key = active
        elif arcs:
            key = next(iter(arcs.keys()))
        else:
            key = "default"
            arcs["default"] = {
                "id": "default",
                "title": "",
                "status": "active",
                "scene_goals": [],
                "hooks": {},
            }
        arc = arcs.get(key) if isinstance(arcs.get(key), dict) else {}
        ordn = int(arc.get("current_scene_ordinal") or plan.get("current_scene_ordinal") or 0) + 1
        arc["current_scene_ordinal"] = ordn
        log = arc.get("scene_log")
        if not isinstance(log, list):
            log = []
        entry = {
            "ordinal": ordn,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "through_turn": through_turn,
        }
        nt = (note or "").strip()
        if nt:
            entry["note"] = nt
        log.append(entry)
        arc["scene_log"] = log
        arcs[key] = arc
        plan["arcs"] = arcs
        plan["active_arc_id"] = key
        plan = normalize_gm_plan(json.dumps(plan, ensure_ascii=False))

        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
            (json.dumps(plan, ensure_ascii=False), campaign_id),
        )
        conn.commit()
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "gm_plan_json": plan,
        }
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

    cur.execute(
        """
        INSERT INTO campaigns (title, system_id, model_id, owner_user_id, language, mode, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            req.title,
            req.system_id,
            req.model_id,
            req.owner_user_id,
            req.language,
            req.mode,
            req.status,
        ),
    )
    conn.commit()

    campaign_id = cur.lastrowid

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
            raise HTTPException(status_code=400, detail=msg)

        # Re-read flags (build_camp commits, but doesn't touch session_flags)
        flags["camp_encounter_boost"] = 0.20
        flags["current_location_key"] = location["key"]
        conn.execute(
            "UPDATE game_sessions SET session_flags = ?, current_location_id = (SELECT id FROM game_locations WHERE key = ?) WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), location["key"], session_row["id"]),
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

        conn.execute("BEGIN")

        # Stage 6 write hook — record an `abandoned` history row for each hero
        # in this campaign before unlinking. Idempotent: skip if a non-active
        # history row already exists for (character, campaign).
        heroes_in = conn.execute(
            """
            SELECT c.id, c.sheet_json,
                   (SELECT COUNT(*) FROM campaign_turns t WHERE t.campaign_id = ?) AS turns_count,
                   COALESCE(c.gold_gp, 0) AS gold_at_end
            FROM characters c WHERE c.campaign_id = ?
            """,
            (campaign_id, campaign_id),
        ).fetchall()
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
            conn.execute(
                """
                INSERT INTO character_campaign_history
                  (character_id, campaign_id, outcome, xp_earned, gold_at_end, turns_count, completed_at)
                VALUES (?, ?, 'abandoned', ?, ?, ?, datetime('now'))
                """,
                (int(h["id"]), campaign_id, xp_lifetime, int(h["gold_at_end"]), int(h["turns_count"])),
            )

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
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete campaign: {str(e)}")
    finally:
        conn.close()
