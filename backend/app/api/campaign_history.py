"""AI-generated campaign history summaries (prompt z pliku + SQLite jako kanon treści)."""

from fastapi import APIRouter, HTTPException, Query

from app.api.turns import get_campaign_or_404, get_db
from app.services.history_summary_service import (
    count_narrative_turns,
    fetch_latest_saved_summary,
    generate_campaign_summary,
    persist_summary,
)

router = APIRouter()


@router.post("/campaigns/{campaign_id}/history/summary")
def create_campaign_history_summary(
    campaign_id: int,
    user_id: int = Query(..., description="Must match campaign owner; used for per-user LLM settings."),
    max_turns: int = Query(200, ge=5, le=2000),
    persist: bool = Query(True, description="Zapisz wynik w tabeli campaign_ai_summaries (kanon poza Loki)."),
):
    """
    Generuje podsumowanie z tur narracyjnych w SQLite (nie z logów Loki).
    Prompt reguł: backend/prompts/history_summary_prompt.txt
    """
    conn = get_db()
    try:
        campaign = get_campaign_or_404(conn, campaign_id)
        if int(campaign["owner_user_id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="user_id must match campaign owner")
    finally:
        conn.close()

    try:
        result = generate_campaign_summary(
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

    summary_id = None
    if persist and (result.get("summary") or "").strip():
        conn = get_db()
        try:
            summary_id = persist_summary(
                conn,
                campaign_id=campaign_id,
                summary_text=result["summary"],
                model_used=str(result.get("model_used") or ""),
                included_turn_count=int(result.get("included_turn_count") or 0),
            )
        finally:
            conn.close()

    return {
        "campaign_id": campaign_id,
        "summary": result.get("summary", ""),
        "model_used": result.get("model_used"),
        "included_turn_count": result.get("included_turn_count", 0),
        "warning": result.get("warning"),
        "persisted": bool(summary_id),
        "summary_id": summary_id,
    }


@router.post("/campaigns/{campaign_id}/history/summary/ensure")
def ensure_campaign_history_summary(
    campaign_id: int,
    user_id: int = Query(..., description="Must match campaign owner; LLM settings."),
    max_turns: int = Query(200, ge=5, le=2000),
    persist: bool = Query(True, description="Zapisz nowe podsumowanie w campaign_ai_summaries."),
    stale_after_turns: int = Query(
        5,
        ge=1,
        le=500,
        description="Regeneruj, gdy przybyło co najmniej tyle nowych tur narracyjnych od zapisu.",
    ),
):
    """
    Dla UI „Historia”: zwraca zapisane podsumowanie, jeśli jest świeże;
    w przeciwnym razie generuje (jak POST …/history/summary) i zapisuje.
    Świeżość: regeneracja, gdy od zapisu doszło co najmniej ``stale_after_turns`` nowych tur narracyjnych
    (porównanie: aktualny COUNT tur narracyjnych minus ``included_turn_count`` z ostatniego wiersza).
    """
    conn = get_db()
    try:
        campaign = get_campaign_or_404(conn, campaign_id)
        if int(campaign["owner_user_id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="user_id must match campaign owner")
        narrative_n = count_narrative_turns(conn, campaign_id)
        saved = fetch_latest_saved_summary(conn, campaign_id)
    finally:
        conn.close()

    def _payload_from_row(row: dict, *, refreshed: bool) -> dict:
        return {
            "campaign_id": campaign_id,
            "summary_id": row["id"],
            "summary": row["summary_text"],
            "model_used": row["model_used"],
            "included_turn_count": row["included_turn_count"],
            "created_at": row["created_at"],
            "narrative_turn_count": narrative_n,
            "refreshed": refreshed,
        }

    if saved:
        included = int(saved.get("included_turn_count") or 0)
        new_turns = narrative_n - included
        if new_turns < stale_after_turns:
            return _payload_from_row(saved, refreshed=False)

    try:
        result = generate_campaign_summary(
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

    text = (result.get("summary") or "").strip()
    if not text:
        return {
            "campaign_id": campaign_id,
            "summary": None,
            "summary_id": None,
            "model_used": None,
            "included_turn_count": int(result.get("included_turn_count") or 0),
            "created_at": None,
            "narrative_turn_count": narrative_n,
            "refreshed": False,
            "warning": result.get("warning"),
        }

    if not persist:
        return {
            "campaign_id": campaign_id,
            "summary": text,
            "summary_id": None,
            "model_used": result.get("model_used"),
            "included_turn_count": int(result.get("included_turn_count") or 0),
            "created_at": None,
            "narrative_turn_count": narrative_n,
            "refreshed": True,
            "warning": result.get("warning"),
        }

    conn = get_db()
    try:
        persist_summary(
            conn,
            campaign_id=campaign_id,
            summary_text=result["summary"],
            model_used=str(result.get("model_used") or ""),
            included_turn_count=int(result.get("included_turn_count") or 0),
        )
        row = fetch_latest_saved_summary(conn, campaign_id)
    finally:
        conn.close()

    if not row:
        raise HTTPException(
            status_code=500,
            detail="Summary generated but could not be reloaded from campaign_ai_summaries",
        )

    return _payload_from_row(row, refreshed=True)


@router.get("/campaigns/{campaign_id}/history/summary")
def get_latest_campaign_history_summary(campaign_id: int):
    """Ostatnio zapisane podsumowanie (jeśli było POST z persist=true)."""
    conn = get_db()
    try:
        get_campaign_or_404(conn, campaign_id)
        row = fetch_latest_saved_summary(conn, campaign_id)
        if not row:
            return {"campaign_id": campaign_id, "summary": None}
        return {
            "campaign_id": campaign_id,
            "summary_id": row["id"],
            "summary": row["summary_text"],
            "model_used": row["model_used"],
            "included_turn_count": row["included_turn_count"],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()
