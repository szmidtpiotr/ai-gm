"""
T10 — co N tur narracyjnych (konfigurowalne) uruchom w tle
`run_ensure_campaign_history_summary` (respektuje T08 cooldown; best-effort).
"""

from __future__ import annotations

import threading

from app.core.logging import get_logger
from app.services.history_summary_service import (
    count_narrative_turns,
    generate_and_persist_dual_summary,
    get_summary_auto_ensure_every_n_narrative_turns,
    touch_rollup_cooldown_anchor,
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
    """T36: use dual summary (one LLM call → player + gm persisted in campaign_ai_summaries)."""
    try:
        out = generate_and_persist_dual_summary(
            campaign_id=campaign_id,
            user_id=owner_user_id,
        )
        # Stamp the shared rollup cooldown anchor so the next auto-ensure doesn't fire too soon.
        conn = _get_db()
        try:
            touch_rollup_cooldown_anchor(conn, campaign_id)
        finally:
            conn.close()
    except Exception as e:
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
        player_saved=bool(out.get("player_saved")),
        gm_saved=bool(out.get("gm_saved")),
        included_turn_count=out.get("included_turn_count"),
        warning=out.get("warning"),
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
