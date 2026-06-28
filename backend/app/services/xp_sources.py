"""Stage 2D — XP source wiring (XS1-XS15).

All functions grant to pending_xp (flushed to xp_available on long rest).
Call sites:
  XS1  turn_pipeline._process_beat_signals
  XS2  turn_pipeline._process_narrative_xp_tags  ([QUEST_COMPLETE:key])
  XS3  turn_pipeline._process_narrative_xp_tags  ([DUNGEON_CLEAR:key])
  XS4  turn_pipeline._process_narrative_xp_tags  ([CAMPAIGN_END:id])
  XS5  turns.py location change hook
  XS6  turn_pipeline._process_npc_first_talk
  XS7  turn_pipeline._process_narrative_xp_tags  ([DISCOVERY:lore_key])
  XS8  turn_pipeline._process_narrative_xp_tags  ([DISCOVERY:secret_location])
  XS9-11 turns.py skill roll resolution
  XS12 turn_pipeline._process_narrative_xp_tags  ([XP_GRANT:reason:amount])
  XS13 combat_service end-combat hook
  XS14 turns.py death-save survived
  XS15 turns.py first-turn session gap detection
"""
from __future__ import annotations

import re
import sqlite3
from typing import Any

import structlog

from app.services.xp_service import grant_pending_xp, get_xp_reward_amount
from app.services.quest_persist_service import complete_quest_in_character_quests

logger = structlog.get_logger()

# ── Regex patterns for LLM narrative tags ────────────────────────────────────

# [^\]]+ allows spaces in quest titles (e.g. "Nocna przesyłka")
_QUEST_RE   = re.compile(r"\[QUEST_COMPLETE:\s*([^\]]+?)\s*\]", re.I)
_DUNGEON_RE = re.compile(r"\[DUNGEON_CLEAR:\s*([^\]\s]+)\s*\]", re.I)
_CAMPAIGN_RE= re.compile(r"\[CAMPAIGN_END:\s*([^\]\s]+)\s*\]", re.I)
_DISC_RE    = re.compile(r"\[DISCOVERY:\s*([^\]\s]+)\s*\]", re.I)
_XP_GRANT_RE= re.compile(r"\[XP_GRANT:\s*([^:\]]+):\s*(\d+)\s*\]", re.I)

SESSION_GAP_MINUTES = 30
XP_GRANT_SESSION_CAP = 50  # XS12 cap per session


# ── Core helper ───────────────────────────────────────────────────────────────

def _grant(conn: sqlite3.Connection, character_id: int, campaign_id: int,
           reward_key: str, reason: str, turn_number: int | None,
           override_amount: int | None = None) -> int:
    """Look up reward amount, grant to pending_xp; return amount or 0."""
    amount = override_amount if override_amount is not None else get_xp_reward_amount(conn, reward_key)
    if not amount or amount <= 0:
        return 0
    grant_pending_xp(
        conn, character_id, campaign_id, amount,
        reason=reason, source=reward_key, turn_number=turn_number,
    )
    logger.info("xp_source_granted", reward_key=reward_key, amount=amount,
                character_id=character_id, turn_number=turn_number)
    return amount


# ── XS1: Beat complete ────────────────────────────────────────────────────────

def grant_beat_complete(conn: sqlite3.Connection, character_id: int, campaign_id: int,
                        beat_key: str, turn_number: int) -> int:
    return _grant(conn, character_id, campaign_id, "campaign.beat_complete",
                  f"Bit ukończony: {beat_key}", turn_number)


# ── XS2: Quest complete ───────────────────────────────────────────────────────

def grant_quest_complete(conn: sqlite3.Connection, character_id: int, campaign_id: int,
                         quest_key: str, turn_number: int) -> int:
    return _grant(conn, character_id, campaign_id, "campaign.side_quest",
                  f"Quest ukończony: {quest_key}", turn_number)


# ── XS3: Dungeon clear ────────────────────────────────────────────────────────

def grant_dungeon_clear(conn: sqlite3.Connection, character_id: int, campaign_id: int,
                        dungeon_key: str, turn_number: int) -> int:
    return _grant(conn, character_id, campaign_id, "campaign.dungeon_cleared",
                  f"Loch oczyszczony: {dungeon_key}", turn_number)


# ── XS4: Campaign end ─────────────────────────────────────────────────────────

def grant_campaign_end(conn: sqlite3.Connection, character_id: int, campaign_id: int,
                       ending_id: str, turn_number: int) -> int:
    return _grant(conn, character_id, campaign_id, "campaign.campaign_ending",
                  f"Koniec kampanii: {ending_id}", turn_number)


# ── XS5: First location visit ─────────────────────────────────────────────────

def grant_first_location_visit(conn: sqlite3.Connection, character_id: int,
                                campaign_id: int, location_key: str, turn_number: int) -> int:
    """Grant if this is the character's first visit to this macro-location.
    Tracks visited keys in characters.visited_location_keys (JSON list)."""
    import json
    row = conn.execute(
        "SELECT visited_location_keys FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if not row:
        return 0
    raw = row["visited_location_keys"]
    try:
        visited: list[str] = json.loads(raw) if raw else []
    except Exception:
        visited = []
    if location_key in visited:
        return 0
    # Only fire for macro locations
    loc = conn.execute(
        "SELECT location_type FROM game_locations WHERE key = ? AND is_active = 1", (location_key,)
    ).fetchone()
    if not loc or loc["location_type"] != "macro":
        return 0
    visited.append(location_key)
    conn.execute(
        "UPDATE characters SET visited_location_keys = ? WHERE id = ?",
        (json.dumps(visited, ensure_ascii=False), character_id),
    )
    xp = _grant(conn, character_id, campaign_id, "exploration.location_new",
                f"Pierwsza wizyta: {location_key}", turn_number)
    from app.services.event_logger import write_game_event
    write_game_event(
        "location_new", campaign_id, character_id, None,
        {"location_key": location_key, "xp": xp, "turn": turn_number},
        conn=conn,
    )
    return xp


# ── XS6: First NPC talk ───────────────────────────────────────────────────────

def grant_first_npc_talk(conn: sqlite3.Connection, character_id: int, campaign_id: int,
                         npc_key: str, turn_number: int) -> int:
    """Grant once per unique npc_key per character (tracked in character_xp_grants)."""
    if not npc_key:
        return 0
    existing = conn.execute(
        "SELECT id FROM character_xp_grants "
        "WHERE character_id = ? AND source = 'exploration.npc_first_talk' AND source_key = ? LIMIT 1",
        (character_id, npc_key),
    ).fetchone()
    if existing:
        return 0
    return _grant(conn, character_id, campaign_id, "exploration.npc_first_talk",
                  f"Pierwsza rozmowa: {npc_key}", turn_number,
                  override_amount=None)  # let the reward table drive


# ── XS7/XS8: Discovery tags ───────────────────────────────────────────────────

def grant_discovery(conn: sqlite3.Connection, character_id: int, campaign_id: int,
                    discovery_key: str, turn_number: int) -> int:
    if discovery_key == "secret_location":
        return _grant(conn, character_id, campaign_id, "exploration.hidden_room",
                      f"Odkrycie ukrytej lokacji: {discovery_key}", turn_number)
    return _grant(conn, character_id, campaign_id, "exploration.secret",
                  f"Odkrycie lore: {discovery_key}", turn_number)


# ── XS9/XS10/XS11: Skill DC success ─────────────────────────────────────────

def grant_skill_dc_success(conn: sqlite3.Connection, character_id: int, campaign_id: int,
                            dc: int, turn_number: int) -> int:
    if dc >= 20:
        key = "skills.skill_dc_20"
    elif dc >= 16:
        key = "skills.skill_dc_16"
    elif dc >= 12:
        key = "skills.skill_dc_12"
    else:
        return 0
    return _grant(conn, character_id, campaign_id, key, f"Sukces DC {dc}", turn_number)


# ── XS12: Narrative free grant ────────────────────────────────────────────────

def grant_narrative_free(conn: sqlite3.Connection, character_id: int, campaign_id: int,
                         reason: str, amount: int, turn_number: int,
                         session_total_so_far: int) -> tuple[int, int]:
    """Grant [XP_GRANT:reason:amount] up to XP_GRANT_SESSION_CAP per session.
    Returns (granted, new_session_total)."""
    amount = max(0, min(amount, XP_GRANT_SESSION_CAP))
    remaining_cap = max(0, XP_GRANT_SESSION_CAP - session_total_so_far)
    actual = min(amount, remaining_cap)
    if actual <= 0:
        return 0, session_total_so_far
    granted = _grant(conn, character_id, campaign_id, "narrative.free_grant",
                     f"Nagroda narracyjna: {reason}", turn_number, override_amount=actual)
    return granted, session_total_so_far + granted


# ── XS13: Outnumbered victory ────────────────────────────────────────────────

def grant_outnumbered_victory(conn: sqlite3.Connection, character_id: int,
                               campaign_id: int, enemy_count: int, turn_number: int) -> int:
    if enemy_count < 3:
        return 0
    return _grant(conn, character_id, campaign_id, "combat.outnumbered_victory",
                  f"Zwycięstwo w przewadze ({enemy_count} wrogów)", turn_number)


# ── XS14: Death save survived ────────────────────────────────────────────────

def grant_death_save_survived(conn: sqlite3.Connection, character_id: int,
                               campaign_id: int, turn_number: int) -> int:
    return _grant(conn, character_id, campaign_id, "combat.death_save_survived",
                  "Przeżycie rzutu na śmierć", turn_number)


# ── XS15: Session start bonus ────────────────────────────────────────────────

def grant_session_start(conn: sqlite3.Connection, character_id: int,
                        campaign_id: int, turn_number: int) -> int:
    """Grant once if ≥SESSION_GAP_MINUTES have passed since the last turn."""
    import datetime
    row = conn.execute(
        "SELECT created_at FROM campaign_turns WHERE campaign_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not row:
        return 0  # first ever turn — no gap to measure
    try:
        last_ts = datetime.datetime.fromisoformat(str(row["created_at"]).replace(" ", "T"))
        gap = (datetime.datetime.utcnow() - last_ts).total_seconds() / 60
    except Exception:
        return 0
    if gap < SESSION_GAP_MINUTES:
        return 0
    return _grant(conn, character_id, campaign_id, "session.start_bonus",
                  f"Powrót do sesji ({gap:.0f} min przerwy)", turn_number)


# ── Narrative tag bulk processor ─────────────────────────────────────────────

def process_narrative_xp_tags(
    narrative: str,
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    turn_number: int,
    session_free_grant_total: int = 0,
) -> dict[str, Any]:
    """Parse XS2-XS4, XS7-XS8, XS12 tags from GM narrative. Returns total granted."""
    total = 0

    from app.services.event_logger import write_game_event

    for m in _QUEST_RE.finditer(narrative):
        quest_title = m.group(1).strip()
        flipped = complete_quest_in_character_quests(
            conn, character_id, campaign_id, quest_title, completed_turn=turn_number
        )
        if flipped:
            xp = grant_quest_complete(conn, character_id, campaign_id, quest_title, turn_number)
            total += xp
            write_game_event(
                "quest_complete", campaign_id, character_id, None,
                {"quest_title": quest_title, "xp": xp, "turn": turn_number},
                conn=conn,
            )
            # #991: flag quest_suggest_needed when no active quests remain
            try:
                from app.services.quest_persist_service import check_and_set_quest_suggest_needed
                check_and_set_quest_suggest_needed(conn, character_id, campaign_id, quest_title)
            except Exception as _qsn_err:
                logger.warning("quest_suggest_needed_error", error=str(_qsn_err))
            # #991: auto-advance GM plan arc out of tutorial when quest completes
            try:
                import json as _json
                from app.services.gm_plan_schema import advance_gm_plan_arc as _advance_arc
                _camp_row = conn.execute(
                    "SELECT gm_plan_json FROM campaigns WHERE id=?", (campaign_id,)
                ).fetchone()
                if _camp_row:
                    _new_plan, _did_advance = _advance_arc(_camp_row["gm_plan_json"])
                    if _did_advance:
                        conn.execute(
                            "UPDATE campaigns SET gm_plan_json=? WHERE id=?",
                            (_json.dumps(_new_plan, ensure_ascii=False), campaign_id),
                        )
                        conn.commit()
                        logger.info(
                            "gm_plan_arc_auto_advanced",
                            campaign_id=campaign_id,
                            new_arc=_new_plan.get("active_arc_id"),
                        )
            except Exception as _arc_err:
                logger.warning("arc_advance_error", error=str(_arc_err))

    for m in _DUNGEON_RE.finditer(narrative):
        total += grant_dungeon_clear(conn, character_id, campaign_id, m.group(1), turn_number)

    for m in _CAMPAIGN_RE.finditer(narrative):
        total += grant_campaign_end(conn, character_id, campaign_id, m.group(1), turn_number)
        # T38 (#1009): a narrator [CAMPAIGN_END] tag also closes the campaign,
        # not just grants XP (completes the half-built victory path).
        try:
            conn.execute(
                "UPDATE campaigns SET status = 'completed' "
                "WHERE id = ? AND lower(coalesce(status, '')) = 'active'",
                (campaign_id,),
            )
            conn.commit()
        except Exception as _ce_err:
            logger.warning("campaign_end_status_error", error=str(_ce_err))

    for m in _DISC_RE.finditer(narrative):
        total += grant_discovery(conn, character_id, campaign_id, m.group(1), turn_number)

    for m in _XP_GRANT_RE.finditer(narrative):
        reason_str = m.group(1).strip()
        try:
            amount = int(m.group(2))
        except ValueError:
            continue
        granted, session_free_grant_total = grant_narrative_free(
            conn, character_id, campaign_id, reason_str, amount,
            turn_number, session_free_grant_total,
        )
        total += granted
        if granted:
            write_game_event(
                "xp_grant", campaign_id, character_id, None,
                {"reason": reason_str, "amount": granted, "turn": turn_number},
                conn=conn,
            )

    # T38 (#1009): deterministic victory spinacz — runs after every turn's tags.
    # Fires only when all acts/scenes are traversed AND no active quests remain.
    try:
        from app.services.campaign_plan_runtime import maybe_complete_campaign
        maybe_complete_campaign(campaign_id, character_id, turn_number, conn)
    except Exception as _vc_err:
        logger.warning("campaign_victory_check_error", error=str(_vc_err))

    return {"total_granted": total, "session_free_grant_total": session_free_grant_total}
