import json
import sqlite3

from app.core.logging import get_logger
from app.services.turn.turn_skill_router import _commit_pending_skill_test

logger = get_logger(__name__)

_COMBAT_CLASS_SKILLS = frozenset({
    "attack", "ranged_attack", "two_handed", "melee_attack", "spell_attack",
    "initiative",
})


def is_combat_class_skill(skill_key: str | None) -> bool:
    return str(skill_key or "").strip().lower() in _COMBAT_CLASS_SKILLS


def intercept_narrator_skill_tags(
    assistant_text: str,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    character_sheet: dict,
) -> tuple[str, "dict | None"]:
    """Intercept [SKILL_TEST:] / [TRAP:] tags from narrator text.

    Drops the pending test if the narrator hallucinated a combat-class
    skill outside actual combat (e.g. user typed "uderzam toporem", LLM
    picked two_handed, but no enemy exists). Returns (cleaned_text, pending | None).
    """
    _skill_pending_narrator = None
    try:
        from app.services.skill_service import intercept_skill_test_tag, intercept_trap_tag
        assistant_text, _skill_pending_narrator = intercept_skill_test_tag(
            assistant_text, conn, campaign_id, character_id
        )
        if not _skill_pending_narrator:
            assistant_text, _skill_pending_narrator = intercept_trap_tag(
                assistant_text, conn, campaign_id, character_id, character_sheet
            )
        # Drop the pending test if the narrator hallucinated a combat-class
        # skill outside actual combat. Same guard as the keyword scans above.
        if _skill_pending_narrator and is_combat_class_skill(_skill_pending_narrator.get("skill_key")):
            logger.info("combat_class_skill_test_suppressed",
                        skill=_skill_pending_narrator.get("skill_key"),
                        source="narrator_tag")
            _skill_pending_narrator = None
        if _skill_pending_narrator:
            gs_row2 = conn.execute(
                "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if gs_row2:
                _sf2 = json.loads(gs_row2["session_flags"] or "{}")
                _sf2 = _commit_pending_skill_test(_skill_pending_narrator, _sf2)
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                    (json.dumps(_sf2, ensure_ascii=False), campaign_id),
                )
                conn.commit()
    except Exception as _se:
        logger.warning("skill_tag_intercept_error: %s", str(_se))
    return assistant_text, _skill_pending_narrator


def persist_narrative_turn(
    *,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    user_text: str,
    assistant_text: str,
    route: str,
    create_turn_log_fn,
    log_narrative_fn,
) -> dict:
    """Persist a narrative turn to DB and emit structured log.

    Wraps create_turn_log + log_narrative_turn_structured as a pair.
    Shared by create_turn (sync) and create_turn_stream (R1.5).
    Returns the log dict from create_turn_log_fn.
    """
    log = create_turn_log_fn(
        conn=conn,
        campaign_id=campaign_id,
        character_id=character_id,
        user_text=user_text,
        assistant_text=assistant_text,
        route=route,
    )
    log_narrative_fn(
        route=route,
        campaign_id=campaign_id,
        character_id=character_id,
        turn_row=log,
        user_text=user_text,
        assistant_text=assistant_text,
    )
    return log
