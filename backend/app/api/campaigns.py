import sqlite3

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.core.config import DEFAULT_CAMPAIGN_LANGUAGE
from app.core.logging import get_logger
from app.services.solo_death_service import death_summary_payload
from app.services.location_integrity_service import update_campaign_location_by_key

DB_PATH = "/data/ai_gm.db"
logger = get_logger(__name__)

router = APIRouter()


class CampaignCreateRequest(BaseModel):
    title: str
    system_id: str
    model_id: str
    owner_user_id: int
    language: str = DEFAULT_CAMPAIGN_LANGUAGE
    mode: str = "solo"
    status: str = "active"


class CampaignLocationPatchRequest(BaseModel):
    location_key: str


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
        SELECT id, title, system_id, model_id, owner_user_id, language, mode, status, created_at
        FROM campaigns
        WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return dict(row)


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
        SELECT id, title, system_id, model_id, owner_user_id, language, mode, status, created_at
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


@router.patch("/campaigns/{campaign_id}/location")
def patch_campaign_location(campaign_id: int, req: CampaignLocationPatchRequest):
    key = (req.location_key or "").strip()
    if not key:
        raise HTTPException(status_code=422, detail="location_key is required")
    try:
        return update_campaign_location_by_key(campaign_id, key)
    except LookupError as e:
        if str(e) == "campaign_not_found":
            raise HTTPException(status_code=404, detail="Campaign not found") from None
        if str(e) == "location_not_found":
            raise HTTPException(status_code=404, detail="Location not found") from None
        raise


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
