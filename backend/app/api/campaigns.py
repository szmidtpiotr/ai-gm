import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict

from app.core.config import DEFAULT_CAMPAIGN_LANGUAGE
from app.core.logging import get_logger
from app.services.history_summary_service import generate_dual_summary_preview
from app.services.solo_death_service import death_summary_payload
from app.services.gm_plan_generation_service import retry_initial_gm_plan_for_campaign
from app.services.gm_plan_schema import merge_gm_plan_patch, normalize_gm_plan

DB_PATH = "/data/ai_gm.db"
logger = get_logger(__name__)

router = APIRouter()


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
            (SELECT COUNT(*) FROM characters ch WHERE ch.campaign_id = c.id) AS character_count
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

    return {
        "campaigns": [dict(row) for row in rows]
    }


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT id, title, system_id, model_id, owner_user_id, language, mode, status, created_at,
               gm_plan_json
        FROM campaigns
        WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return dict(row)


@router.patch("/campaigns/{campaign_id}/gm-plan")
def patch_campaign_gm_plan(campaign_id: int, req: GmPlanPatchRequest, user_id: int = Query(...)):
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
def post_generate_initial_gm_plan(campaign_id: int, user_id: int = Query(...)):
    """
    T05: ponów generację początkowego planu MG (owner), np. gdy LLM padł przy tworzeniu postaci.
    """
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
    user_id: int = Query(...),
    note: str = Query("", max_length=2000, description="Optional note for the scene log."),
):
    """
    Increment `current_scene_ordinal` and append `scene_log` entry (**[S11a]** / **[S10c]** boundary).
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

    conn.close()

    if not row:
        raise HTTPException(status_code=500, detail="Campaign created but could not be loaded")

    # NOTE: Chat history lives in the frontend — switching to a new campaign
    # clears the UI automatically because the campaign_id changes.
    # The backend does not maintain an in-memory chat state.
    return dict(row)


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
    user_id: int = Query(..., description="Must match campaign owner."),
    max_turns: int = Query(200, ge=5, le=2000),
):
    """
    [T01] One LLM call → JSON player_summary + gm_notes. Does NOT persist to campaign_ai_summaries.
    Mounted on campaigns router (same prefix /api) so the path is always registered with core campaign API.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if int(row["owner_user_id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="user_id must match campaign owner")
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


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(campaign_id: int):
    conn = sqlite3.connect(DB_PATH)

    try:
        row = conn.execute(
            "SELECT id FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")

        conn.execute("BEGIN")

        conn.execute(
            "DELETE FROM campaign_turns WHERE campaign_id = ?",
            (campaign_id,),
        )

        conn.execute(
            "DELETE FROM characters WHERE campaign_id = ?",
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
