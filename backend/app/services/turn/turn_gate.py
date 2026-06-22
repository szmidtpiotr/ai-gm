import sqlite3

from app.core.logging import get_logger

logger = get_logger(__name__)


def check_gate_and_record(
    *,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    narrative_text: str,
    roll_request: bool,
    turn_id: str,
    record_turn_decision_fn,
    with_turn_trace_fn,
) -> dict | None:
    """B3: Gate Mechanic — validate against World State before LLM.

    Returns a blocked-response dict (caller should return it immediately) if the
    gate blocks the action, otherwise None (proceed to LLM).  Also records the
    narrative-route turn decision when the gate passes.

    Gate errors never break the game — exceptions fall through to LLM.
    """
    if roll_request:
        return None

    # ── B3: Gate Mechanic — validate against World State before LLM ─────
    try:
        from app.services.gate_service import validate_action as _gate_validate
        _gate_result = _gate_validate(campaign_id, narrative_text)
        if not _gate_result.allowed:
            logger.info(
                "gate_blocked",
                campaign_id=campaign_id,
                reason=_gate_result.reason,
                action_preview=narrative_text[:60],
            )
            record_turn_decision_fn(
                campaign_id, character_id, narrative_text,
                route="blocked", gate_blocked=True, gate_reason=_gate_result.reason,
                handler="gate", conn=conn,
            )
            return with_turn_trace_fn(
                {
                    "blocked": True,
                    "feedback": _gate_result.feedback,
                    "reason": _gate_result.reason,
                },
                turn_id,
            )
    except Exception as _gate_err:
        logger.warning("gate_check_error", error=str(_gate_err))
        # Gate errors must never break the game — fall through to LLM

    # #762: decyzja silnika — tura przepuszczona przez gate (intent + route narracyjny)
    record_turn_decision_fn(
        campaign_id, character_id, narrative_text,
        route="narrative", gate_blocked=False, gate_reason=None,
        handler="narrative", conn=conn,
    )
    return None
