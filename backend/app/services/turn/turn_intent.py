import json
import sqlite3
import uuid as _uuid

from app.core.logging import get_logger

logger = get_logger(__name__)


def detect_risky_intent(conn: sqlite3.Connection, narrative_text: str, roll_request: bool) -> dict | None:
    """U7: detect risky player intent before LLM call.

    Returns the risky-intent match dict, or None when not applicable.
    Errors are swallowed — caller continues normally.
    """
    if roll_request:
        return None
    try:
        from app.services.game_engine import _detect_risky_intent as _u7_detect
        return _u7_detect(conn, narrative_text)
    except Exception as _ri_err:
        logger.warning("risky_intent_detect_error", error=str(_ri_err))
        return None


def snapshot_hex(conn: sqlite3.Connection, campaign_id: int) -> dict | None:
    """Read current_hex from session_flags before location intent processing.

    Used to detect hex changes for hex_enter encounter trigger.
    Returns the hex dict (with q/r) or None on error.
    """
    try:
        _gs_pre_enc = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1", (campaign_id,)
        ).fetchone()
        if _gs_pre_enc:
            _sf_pre_enc = json.loads(_gs_pre_enc["session_flags"] or "{}")
            return _sf_pre_enc.get("current_hex")
    except Exception:
        pass
    return None


def check_hex_enter_trigger(conn: sqlite3.Connection, campaign_id: int, hex_before: dict | None) -> None:
    """Hex-enter encounter trigger: fire when current_hex changed after location intent.

    Reads the post-intent session_flags and compares with hex_before.  If the
    hex changed, calls maybe_inject_encounter so random encounters can fire on
    map movement.  Errors are swallowed — caller continues normally.
    """
    try:
        _gs_post_enc = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1", (campaign_id,)
        ).fetchone()
        if _gs_post_enc:
            _sf_post_enc = json.loads(_gs_post_enc["session_flags"] or "{}")
            _hex_after_enc = _sf_post_enc.get("current_hex")
            if _hex_after_enc and _hex_after_enc != hex_before:
                from app.services.encounter_service import maybe_inject_encounter as _mie
                _mie(
                    conn, campaign_id, "hex_enter",
                    q=int(_hex_after_enc.get("q", 0)),
                    r=int(_hex_after_enc.get("r", 0)),
                )
    except Exception as _enc_trigger_err:
        logger.warning("hex_enter_encounter_trigger_error", error=str(_enc_trigger_err))


def apply_u7_safety_net(
    *,
    conn: sqlite3.Connection,
    campaign_id: int,
    character: dict,
    assistant_text: str,
    risky_intent_match: dict | None,
    skill_pending_narrator: dict | None,
    commit_pending_skill_test_fn,
) -> dict | None:
    """U7: safety net — force skill test if risky intent + LLM omitted tag.

    If the LLM response already contains a skill test tag (_skill_pending_narrator
    is set), this is a no-op.  When a risky intent was detected but the narrator
    didn't emit [SKILL_TEST:], we force one here.

    Returns the new pending skill test dict, or None if nothing was forced.
    Errors are swallowed — caller continues normally.
    """
    if not risky_intent_match or skill_pending_narrator:
        return None

    try:
        from app.services.llm_tag_parser import skill_check_safety_net as _u7_sn
        from app.services.skill_service import calc_skill_modifier_info, _skill_label, _get_counter
        _gs_u7 = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        _existing_pending_u7 = None
        if _gs_u7:
            _existing_pending_u7 = json.loads(_gs_u7["session_flags"] or "{}").get("pending_skill_test")
        _forced = _u7_sn(
            llm_response=assistant_text,
            risky_intent=risky_intent_match,
            existing_pending=_existing_pending_u7,
            conn=conn,
            campaign_id=campaign_id,
        )
        if _forced:
            _char_sh_u7 = json.loads(character["sheet_json"] or "{}")
            _skill_key_u7 = _forced["skill_key"]
            _pending_u7 = {
                "skill_test_id": f"st-{_uuid.uuid4().hex[:8]}",
                "skill_key": _skill_key_u7,
                "skill_label": _skill_label(_skill_key_u7),
                "counter": _get_counter(conn, _skill_key_u7),
                "modifier_breakdown": calc_skill_modifier_info(_char_sh_u7, _skill_key_u7),
                "dc": _forced["dc"],
                "source": "safety_net",
            }
            if _gs_u7:
                _sf_u7 = json.loads(_gs_u7["session_flags"] or "{}")
                _sf_u7 = commit_pending_skill_test_fn(_pending_u7, _sf_u7)
                conn.execute(
                    "UPDATE game_sessions SET session_flags=? WHERE campaign_id=?",
                    (json.dumps(_sf_u7, ensure_ascii=False), campaign_id),
                )
                conn.commit()
            return _pending_u7
    except Exception as _u7_err:
        logger.warning("u7_safety_net_error", error=str(_u7_err))
    return None
