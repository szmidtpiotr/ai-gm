"""AI-generated campaign history summaries (prompt z pliku + SQLite jako kanon treści)."""

from fastapi import APIRouter, HTTPException, Query

from app.api.turns import get_campaign_or_404, get_db
from app.services.history_summary_service import (
    SUMMARY_AUDIENCE_PLAYER,
    count_narrative_turns,
    evaluate_summary_rollup_cooldown,
    fetch_latest_saved_summary,
    generate_campaign_summary,
    persist_summary,
    touch_rollup_cooldown_anchor,
    turns_until_summary_rollup_allowed,
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
    conn = get_db()
    try:
        campaign = get_campaign_or_404(conn, campaign_id)
        if int(campaign["owner_user_id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="user_id must match campaign owner")
        narrative_n = count_narrative_turns(conn, campaign_id)
        saved = fetch_latest_saved_summary(conn, campaign_id, audience=audience)
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
            "audience": row.get("audience", SUMMARY_AUDIENCE_PLAYER),
            "narrative_turn_count": narrative_n,
            "refreshed": refreshed,
        }

    if saved:
        included = int(saved.get("included_turn_count") or 0)
        new_turns = narrative_n - included
        if new_turns < stale_after_turns:
            return _payload_from_row(saved, refreshed=False)

    conn_cd = get_db()
    try:
        allowed, cooldown_n, last_anchor, cur_n = evaluate_summary_rollup_cooldown(
            conn_cd, campaign_id
        )
        if not allowed:
            need = turns_until_summary_rollup_allowed(cooldown_n, last_anchor, cur_n)
            if saved:
                out = _payload_from_row(saved, refreshed=False)
                out["cooldown_active"] = True
                out["turns_until_summary_rollup_allowed"] = need
                return out
            return {
                "campaign_id": campaign_id,
                "summary": None,
                "summary_id": None,
                "model_used": None,
                "included_turn_count": 0,
                "created_at": None,
                "audience": audience,
                "narrative_turn_count": narrative_n,
                "refreshed": False,
                "cooldown_active": True,
                "turns_until_summary_rollup_allowed": need,
                "warning": None,
            }
    finally:
        conn_cd.close()

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

    text = (result.get("summary") or "").strip()
    if not text:
        _finalize_rollup_cooldown(campaign_id)
        return {
            "campaign_id": campaign_id,
            "summary": None,
            "summary_id": None,
            "model_used": None,
            "included_turn_count": int(result.get("included_turn_count") or 0),
            "created_at": None,
            "audience": audience,
            "narrative_turn_count": narrative_n,
            "refreshed": False,
            "warning": result.get("warning"),
        }

    if not persist:
        _finalize_rollup_cooldown(campaign_id)
        return {
            "campaign_id": campaign_id,
            "summary": text,
            "summary_id": None,
            "model_used": result.get("model_used"),
            "included_turn_count": int(result.get("included_turn_count") or 0),
            "created_at": None,
            "audience": audience,
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
            audience=audience,
        )
        row = fetch_latest_saved_summary(conn, campaign_id, audience=audience)
    finally:
        conn.close()

    if not row:
        raise HTTPException(
            status_code=500,
            detail="Summary generated but could not be reloaded from campaign_ai_summaries",
        )

    _finalize_rollup_cooldown(campaign_id)

    return _payload_from_row(row, refreshed=True)


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
