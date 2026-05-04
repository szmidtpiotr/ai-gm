"""
T10 — co N tur narracyjnych (konfigurowalne) uruchom w tle
`run_ensure_campaign_history_summary` (respektuje T08 cooldown; best-effort).
"""

from __future__ import annotations

import threading

from app.core.logging import get_logger
from app.services.history_summary_service import (
    count_narrative_turns,
    get_summary_auto_ensure_every_n_narrative_turns,
)
from app.services.summary_ensure_service import (
    SummaryEnsureHttpError,
    run_ensure_campaign_history_summary,
)

logger = get_logger(__name__)


def _get_db():
    from app.api.turns import get_db

    return get_db()


def _run_ensure_bg(campaign_id: int, owner_user_id: int) -> None:
    try:
        out = run_ensure_campaign_history_summary(
            campaign_id=campaign_id,
            user_id=owner_user_id,
        )
    except SummaryEnsureHttpError as e:
        logger.warning(
            "summary_auto_ensure_result",
            campaign_id=campaign_id,
            ok=False,
            status_code=e.status_code,
            detail=e.detail,
        )
        return
    except Exception as e:  # pragma: no cover - defensive
        logger.exception(
            "summary_auto_ensure_result",
            campaign_id=campaign_id,
            ok=False,
            error=str(e),
        )
        return

    logger.info(
        "summary_auto_ensure_result",
        campaign_id=campaign_id,
        ok=True,
        refreshed=bool(out.get("refreshed")),
        cooldown_active=bool(out.get("cooldown_active")),
        summary_id=out.get("summary_id"),
    )


def schedule_after_narrative_turn_committed(campaign_id: int) -> None:
    """Wywołaj po zapisie wiersza campaign_turns z route='narrative' (po commit)."""
    conn = _get_db()
    try:
        interval = get_summary_auto_ensure_every_n_narrative_turns(conn)
        if interval <= 0:
            return
        n = count_narrative_turns(conn, campaign_id)
        if n <= 0 or (n % interval) != 0:
            return
        row = conn.execute(
            "SELECT owner_user_id FROM campaigns WHERE id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row:
            return
        owner_user_id = int(row["owner_user_id"])
    finally:
        conn.close()

    t = threading.Thread(
        target=_run_ensure_bg,
        args=(campaign_id, owner_user_id),
        daemon=True,
        name=f"summary-auto-ensure-{campaign_id}",
    )
    t.start()
