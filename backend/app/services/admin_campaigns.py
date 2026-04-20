"""Admin: list campaigns by owner and regenerate AI history summaries."""

from __future__ import annotations

import sqlite3

from app.services.history_summary_service import (
    generate_campaign_summary,
    persist_summary,
)

DB_PATH = "/data/ai_gm.db"


def list_campaigns_by_owner(owner_user_id: int) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.title,
                c.status,
                c.created_at,
                (SELECT COUNT(*) FROM campaign_turns ct WHERE ct.campaign_id = c.id) AS turn_count,
                (SELECT MAX(ct2.created_at) FROM campaign_turns ct2 WHERE ct2.campaign_id = c.id)
                    AS last_turn_at
            FROM campaigns c
            WHERE c.owner_user_id = ?
            ORDER BY c.id DESC
            """,
            (owner_user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def regenerate_campaign_summary_admin(campaign_id: int) -> dict:
    """
    Regenerate stored AI summary for a campaign (admin).
    Uses campaign owner for per-user LLM settings.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, owner_user_id FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise KeyError("campaign_not_found")
        owner_id = int(row["owner_user_id"])
    finally:
        conn.close()

    try:
        result = generate_campaign_summary(
            campaign_id=campaign_id,
            user_id=owner_id,
            max_turns=200,
        )
    except ValueError as e:
        if str(e) == "campaign_not_found":
            raise KeyError("campaign_not_found") from e
        raise

    summary_id = None
    text = (result.get("summary") or "").strip()
    if text:
        conn2 = sqlite3.connect(DB_PATH)
        try:
            summary_id = persist_summary(
                conn2,
                campaign_id=campaign_id,
                summary_text=result["summary"],
                model_used=str(result.get("model_used") or ""),
                included_turn_count=int(result.get("included_turn_count") or 0),
            )
        finally:
            conn2.close()

    return {
        "ok": True,
        "campaign_id": campaign_id,
        "persisted": bool(summary_id),
        "warning": result.get("warning"),
    }
