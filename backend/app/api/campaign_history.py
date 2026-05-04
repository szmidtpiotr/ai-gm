"""AI-generated campaign history summaries (prompt z pliku + SQLite jako kanon treści)."""

from fastapi import APIRouter, HTTPException, Query

from app.api.turns import get_campaign_or_404, get_db
from app.services.history_summary_service import (
    SUMMARY_AUDIENCE_PLAYER,
    evaluate_summary_rollup_cooldown,
    generate_campaign_summary,
    persist_summary,
    touch_rollup_cooldown_anchor,
    turns_until_summary_rollup_allowed,
)
from app.services.summary_ensure_service import (
    SummaryEnsureHttpError,
    run_ensure_campaign_history_summary,
)

router = APIRouter()


def _finalize_rollup_cooldown(campaign_id: int) -> None:
    """T08: bump per-campaign anchor after any successful LLM rollup call."""
    conn = get_db()
    try:
        touch_rollup_cooldown_anchor(conn, campaign_id)
    finally:
        conn.close()


@router.post("/campaigns/{campaign_id}/history/summary")
def create_campaign_history_summary(
    campaign_id: int,
    user_id: int = Query(..., description="Must match campaign owner; used for per-user LLM settings."),
    max_turns: int = Query(200, ge=5, le=2000),
    persist: bool = Query(True, description="Zapisz wynik w tabeli campaign_ai_summaries (kanon poza Loki)."),
    audience: str = Query(
        SUMMARY_AUDIENCE_PLAYER,
        pattern="^(player|gm)$",
        description="[T02] Który stos rollupu zapisać (player vs gm).",
    ),
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
        allowed, cooldown_n, last_anchor, cur_n = evaluate_summary_rollup_cooldown(
            conn, campaign_id
        )
        if not allowed:
            need = turns_until_summary_rollup_allowed(cooldown_n, last_anchor, cur_n)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "summary_rollup_cooldown",
                    "message": (
                        "Odświeżenie skrótu fabularnego było zbyt niedawno dla tej kampanii. "
                        f"Pozostało ok. {need} tur narracyjnych do następnego rollupu."
                    ),
                    "cooldown_turns": cooldown_n,
                    "turns_until_allowed": need,
                    "narrative_turn_count": cur_n,
                    "last_rollup_narrative_turn_count": last_anchor,
                },
            )
    finally:
        conn.close()

    try:
        result = generate_campaign_summary(
            campaign_id=campaign_id,
            user_id=user_id,
            max_turns=max_turns,
            audience=audience,
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
                audience=audience,
            )
        finally:
            conn.close()

    _finalize_rollup_cooldown(campaign_id)

    return {
        "campaign_id": campaign_id,
        "summary": result.get("summary", ""),
        "model_used": result.get("model_used"),
        "included_turn_count": result.get("included_turn_count", 0),
        "warning": result.get("warning"),
        "persisted": bool(summary_id),
        "summary_id": summary_id,
        "audience": audience,
    }


@router.post("/campaigns/{campaign_id}/history/summary/ensure")
def ensure_campaign_history_summary(
    campaign_id: int,
    user_id: int = Query(..., description="Must match campaign owner; LLM settings."),
    max_turns: int = Query(200, ge=5, le=2000),
    persist: bool = Query(True, description="Zapisz nowe podsumowanie w campaign_ai_summaries."),
    audience: str = Query(
        SUMMARY_AUDIENCE_PLAYER,
        pattern="^(player|gm)$",
        description="[T02] Który stos rollupu sprawdzać / odświeżać.",
    ),
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
    try:
        return run_ensure_campaign_history_summary(
            campaign_id=campaign_id,
            user_id=user_id,
            max_turns=max_turns,
            persist=persist,
            audience=audience,
            stale_after_turns=stale_after_turns,
        )
    except SummaryEnsureHttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/campaigns/{campaign_id}/history/summary")
def get_latest_campaign_history_summary(
    campaign_id: int,
    audience: str = Query(
        SUMMARY_AUDIENCE_PLAYER,
        pattern="^(player|gm)$",
        description="[T02] Który stos rollupu zwrócić.",
    ),
):
    """Ostatnio zapisane podsumowanie (jeśli było POST z persist=true)."""
    conn = get_db()
    try:
        get_campaign_or_404(conn, campaign_id)
        row = fetch_latest_saved_summary(conn, campaign_id, audience=audience)
        if not row:
            return {"campaign_id": campaign_id, "summary": None, "audience": audience}
        return {
            "campaign_id": campaign_id,
            "summary_id": row["id"],
            "summary": row["summary_text"],
            "model_used": row["model_used"],
            "included_turn_count": row["included_turn_count"],
            "created_at": row["created_at"],
            "audience": row.get("audience", audience),
        }
    finally:
        conn.close()
