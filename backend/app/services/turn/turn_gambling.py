import sqlite3

from app.core.logging import get_logger

logger = get_logger(__name__)


def apply_gamble_outcome_in_skill_resolution(
    *,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    pending: dict,
    session_flags: dict,
    result: dict,
) -> dict | None:
    """S7 (#601) — gamble → gold flow according to test outcome (S1).

    Applies the gamble outcome when the resolved skill test is a gamble:
    calls apply_gamble_outcome, moves gold via change_gold, and logs the
    result.  Must run BEFORE the skill scanner (root cause #616).

    Returns the gamble_summary dict, or None when this turn was not a gamble.
    Errors are swallowed — caller continues normally.
    """
    if str(pending.get("skill_key", "")).lower() != "gamble":
        return None

    try:
        from app.services import gamble_service as _gbl
        from app.services.economy_service import change_gold as _chg
        from app.services.world_service import get_current_location_info
        _stake = int((pending.get("gamble") or {}).get("stake", 0) or 0)
        _loc_key = ""
        try:
            _loc = get_current_location_info(conn, campaign_id)
            _loc_key = str((_loc or {}).get("key") or "")
        except Exception:
            _loc_key = ""
        _gamble_summary = _gbl.apply_gamble_outcome(
            session_flags, result.get("outcome", "FAILURE"), _stake, _loc_key
        )
        _delta = int(_gamble_summary.get("delta", 0) or 0)
        if _delta:
            try:
                _chg(conn, character_id, _delta, "gamble",
                     campaign_id=campaign_id,
                     meta={"stake": _stake, "outcome": result.get("outcome")},
                     allow_negative=False)
            except ValueError:
                # #1161: przegrana większa niż saldo — ogranicz stratę do bieżącego
                # złota (przegrywasz co masz), zamiast połykać cały wynik hazardu.
                if _delta < 0:
                    from app.services.economy_service import get_character_gold
                    _cur = int(get_character_gold(conn, character_id))
                    _capped = -_cur
                    _gamble_summary["delta"] = _capped
                    _delta = _capped
                    if _capped:
                        _chg(conn, character_id, _capped, "gamble",
                             campaign_id=campaign_id,
                             meta={"stake": _stake, "outcome": result.get("outcome"),
                                   "capped_to_balance": True},
                             allow_negative=False)
                else:
                    raise
        logger.info("gamble_outcome_applied", campaign_id=campaign_id,
                    stake=_stake, delta=_delta,
                    cheat=_gamble_summary.get("cheat_accused"))
        return _gamble_summary
    except Exception as _gbl_err:
        logger.warning("gamble_outcome_error", error=str(_gbl_err))
        return None


def build_gamble_narrator_ctx(gamble_summary: dict | None) -> str:
    """S7 (#601): build gamble context string for narrator.

    Returns text to append to skill_ctx so the narrator knows about the gold
    flow (mechanika already moved the gold via change_gold).
    Crit-fail → cheating accusation in the returned text.
    Returns empty string when gamble_summary is None.
    """
    if gamble_summary is None:
        return ""
    _stake_g = int(gamble_summary.get("stake", 0) or 0)
    _delta_g = int(gamble_summary.get("delta", 0) or 0)
    if _delta_g > 0:
        ctx = f"\n[HAZARD] Gracz wygrał {_delta_g} zł (stawka {_stake_g} zł). Opisz triumf przy stole — BEZ podawania liczb."
    else:
        ctx = f"\n[HAZARD] Gracz przegrał {abs(_delta_g)} zł (stawka {_stake_g} zł). Opisz przegraną — BEZ podawania liczb."
    if gamble_summary.get("cheat_accused"):
        ctx += "\n[HAZARD] Padło oskarżenie o oszustwo — inni gracze/karczmarz patrzą na bohatera podejrzliwie; wprowadź to napięcie do narracji."
    return ctx
