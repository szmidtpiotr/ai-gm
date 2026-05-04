"""
Core logic for POST /campaigns/{id}/history/summary/ensure (T02 + T08).
Extracted for reuse by API router and T10 background automation.
"""

from __future__ import annotations

from app.services.history_summary_service import (
    SUMMARY_AUDIENCE_PLAYER,
    SummaryAudience,
    count_narrative_turns,
    evaluate_summary_rollup_cooldown,
    fetch_latest_saved_summary,
    generate_campaign_summary,
    persist_summary,
    touch_rollup_cooldown_anchor,
    turns_until_summary_rollup_allowed,
)


def _get_db():
    """Lazy import — avoid circular import with `turns` at app startup."""
    from app.api.turns import get_db as _open

    return _open()


class SummaryEnsureHttpError(Exception):
    """Maps to FastAPI HTTPException in the HTTP layer."""

    def __init__(self, status_code: int, detail: str | dict) -> None:
        self.status_code = int(status_code)
        self.detail = detail
        super().__init__(str(detail))


def _finalize_rollup_cooldown(campaign_id: int) -> None:
    conn = _get_db()
    try:
        touch_rollup_cooldown_anchor(conn, campaign_id)
    finally:
        conn.close()


def run_ensure_campaign_history_summary(
    *,
    campaign_id: int,
    user_id: int,
    max_turns: int = 200,
    persist: bool = True,
    audience: SummaryAudience = SUMMARY_AUDIENCE_PLAYER,
    stale_after_turns: int = 5,
) -> dict:
    """
    Same contract as the ensure HTTP handler: success dict, or SummaryEnsureHttpError.
    """
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not row:
            raise SummaryEnsureHttpError(404, "Campaign not found")
        campaign = row
        if int(campaign["owner_user_id"]) != int(user_id):
            raise SummaryEnsureHttpError(403, "user_id must match campaign owner")
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

    conn_cd = _get_db()
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
        raise SummaryEnsureHttpError(502, str(e)) from None
    except ValueError as e:
        if str(e) == "campaign_not_found":
            raise SummaryEnsureHttpError(404, "Campaign not found") from None
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

    conn = _get_db()
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
        raise SummaryEnsureHttpError(
            500,
            "Summary generated but could not be reloaded from campaign_ai_summaries",
        )

    _finalize_rollup_cooldown(campaign_id)

    return _payload_from_row(row, refreshed=True)
