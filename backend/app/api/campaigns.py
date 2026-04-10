import sqlite3

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.core.config import DEFAULT_CAMPAIGN_LANGUAGE

DB_PATH = "/data/ai_gm.db"

router = APIRouter()


class CampaignCreateRequest(BaseModel):
    title: str
    system_id: str
    model_id: str
    owner_user_id: int
    language: str = DEFAULT_CAMPAIGN_LANGUAGE
    mode: str = "solo"
    status: str = "active"


@router.get("/campaigns")
def list_campaigns():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT id, title, system_id, model_id, owner_user_id, language, mode, status, created_at
        FROM campaigns
        ORDER BY id ASC
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

    return dict(row)


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