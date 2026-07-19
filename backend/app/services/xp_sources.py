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

import datetime
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
# #1469: environmental/scripted death — bare or `[DEATH_TRIGGER: reason]`.
_DEATH_TRIGGER_RE = re.compile(r"\[DEATH_TRIGGER(?::\s*([^\]]*))?\]", re.I)

SESSION_GAP_MINUTES = 30
XP_GRANT_SESSION_CAP = 50  # XS12 cap per session
SKILL_DC_XP_DAILY_CAP = 5  # AUDIT #1445 — max skill-DC XP grants per real day (starting value)


# ── Core helper ───────────────────────────────────────────────────────────────

def _grant(conn: sqlite3.Connection, character_id: int, campaign_id: int,
           reward_key: str, reason: str, turn_number: int | None,
           override_amount: int | None = None, source_key: str = "") -> int:
    """Look up reward amount, grant to pending_xp; return amount or 0."""
    amount = override_amount if override_amount is not None else get_xp_reward_amount(conn, reward_key)
    if not amount or amount <= 0:
        return 0
    grant_pending_xp(
        conn, character_id, campaign_id, amount,
        reason=reason, source=reward_key, source_key=source_key, turn_number=turn_number,
    )
    logger.info("xp_source_granted", reward_key=reward_key, amount=amount,
                character_id=character_id, turn_number=turn_number)
    return amount


def _already_granted(conn: sqlite3.Connection, character_id: int, source: str, source_key: str) -> bool:
    """AUDIT #1445 — dedup guard (mirror of grant_first_npc_talk): a (source, source_key)
    pair grants XP at most once per character. Used for discovery/dungeon-clear tags that
    otherwise re-granted on every repeat (same tag in two turns, or twice in one response
    via finditer)."""
    if not source_key:
        return False
    row = conn.execute(
        "SELECT 1 FROM character_xp_grants "
        "WHERE character_id = ? AND source = ? AND source_key = ? LIMIT 1",
        (character_id, source, source_key),
    ).fetchone()
    return row is not None


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
    # AUDIT #1445: dedup by source_key — the same [DUNGEON_CLEAR:key] in two turns (or
    # twice in one response via finditer) used to re-grant unbounded.
    if _already_granted(conn, character_id, "campaign.dungeon_cleared", dungeon_key):
        return 0
    return _grant(conn, character_id, campaign_id, "campaign.dungeon_cleared",
                  f"Loch oczyszczony: {dungeon_key}", turn_number, source_key=dungeon_key)


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

def _norm_npc(s: Any) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(s or "").strip().lower())
        if not unicodedata.combining(c)
    )


def _is_known_npc(conn: sqlite3.Connection, campaign_id: int, npc_key: str) -> bool:
    """AUDIT #1445 — walidacja nazwy NPC względem rzeczywistej obsady sceny/kampanii.
    `DIALOGUE:<any>` leci na TEKŚCIE GRACZA, więc bez tego `DIALOGUE:aaa`, `DIALOGUE:bbb`
    farmiło XP „pierwszej rozmowy" dla zmyślonych NPC. Porównanie znormalizowane (bez
    polskich znaków — gracze mobilni piszą bez ogonków, feedback_pl_diacritics_intent)."""
    key = _norm_npc(npc_key)
    if not key:
        return False
    import json as _j
    try:
        row = conn.execute(
            "SELECT scene_npcs FROM game_sessions WHERE campaign_id = ? LIMIT 1", (campaign_id,)
        ).fetchone()
        if row and row["scene_npcs"]:
            for n in _j.loads(row["scene_npcs"] or "[]"):
                if key in (_norm_npc(n.get("key")), _norm_npc(n.get("name")), _norm_npc(n.get("label"))):
                    return True
    except Exception:
        pass
    try:
        rows = conn.execute(
            "SELECT npc_id, npc_name FROM campaign_known_npcs WHERE campaign_id = ?", (campaign_id,)
        ).fetchall()
        for r in rows:
            if key in (_norm_npc(r["npc_id"]), _norm_npc(r["npc_name"])):
                return True
    except Exception:
        pass
    return False


def grant_first_npc_talk(conn: sqlite3.Connection, character_id: int, campaign_id: int,
                         npc_key: str, turn_number: int) -> int:
    """Grant once per unique npc_key per character (tracked in character_xp_grants)."""
    if not npc_key:
        return 0
    # AUDIT #1445: reject XP for NPCs the campaign has never surfaced (anti-farm on
    # `DIALOGUE:<fabricated>` player text).
    if not _is_known_npc(conn, campaign_id, npc_key):
        logger.info("dialogue_xp_unknown_npc_skipped", character_id=character_id, npc_key=npc_key)
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
    # AUDIT #1445: dedup by source_key so a repeated [DISCOVERY:key] can't farm XP.
    source = "exploration.hidden_room" if discovery_key == "secret_location" else "exploration.secret"
    if _already_granted(conn, character_id, source, discovery_key):
        return 0
    if discovery_key == "secret_location":
        return _grant(conn, character_id, campaign_id, "exploration.hidden_room",
                      f"Odkrycie ukrytej lokacji: {discovery_key}", turn_number, source_key=discovery_key)
    return _grant(conn, character_id, campaign_id, "exploration.secret",
                  f"Odkrycie lore: {discovery_key}", turn_number, source_key=discovery_key)


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
    # AUDIT #1445: daily cap on skill-DC XP. Every successful DC≥12 test used to grant
    # unbounded pending XP — spamming "wspinam się na mur" each turn = infinite XP. Cap the
    # number of skill-DC grants per real day (starting value, Sandbox-tunable).
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM character_xp_grants "
            "WHERE character_id = ? AND source LIKE 'skills.skill_dc%' "
            "AND date(created_at) = date('now')",
            (character_id,),
        ).fetchone()[0]
    except Exception:
        cnt = 0
    if cnt >= SKILL_DC_XP_DAILY_CAP:
        logger.info("skill_dc_xp_daily_cap_hit", character_id=character_id, cap=SKILL_DC_XP_DAILY_CAP)
        return 0
    return _grant(conn, character_id, campaign_id, key, f"Sukces DC {dc}", turn_number, source_key=key)


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


# ── #1469: environmental / scripted death mechanic ───────────────────────────

def _trigger_environmental_death(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    narrative: str,
) -> bool:
    """Run the death mechanic for a [DEATH_TRIGGER] tag. Returns True if fired.

    Gated so it fires exactly once and never kills a test hero during a smoke run:
      - campaign must still be active (status guard blocks re-fire on later turns)
      - autopilot [TEST] heroes are skipped (see `feedback_smoke_test_db_cheat`)
    Reuses the same `end_solo_campaign_on_death` flow as death_save / combat death,
    so no new player-facing death behaviour is introduced — only a new trigger.
    """
    camp = conn.execute(
        "SELECT status FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    if camp is not None:
        status = str(camp["status"] or "").strip().lower()
        if status not in ("", "active"):
            return False  # already ended/completed — never re-fire

    char_row = conn.execute(
        "SELECT * FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if char_row is None:
        return False

    try:
        from app.services.playthrough_service import is_autopilot_active, is_test_hero
        if is_autopilot_active() and is_test_hero(char_row):
            logger.info("death_trigger_test_hero_skipped",
                        campaign_id=campaign_id, character_id=character_id)
            return False
    except Exception:
        pass

    m = _DEATH_TRIGGER_RE.search(narrative or "")
    reason = (m.group(1) or "").strip() if (m and m.lastindex) else ""
    death_reason = reason or "Śmierć w wyniku wydarzeń w świecie gry"

    from app.services.solo_death_service import end_solo_campaign_on_death
    end_solo_campaign_on_death(
        conn,
        campaign_id=campaign_id,
        character_row=char_row,
        death_reason=death_reason,
    )
    logger.error("death_trigger_fired", campaign_id=campaign_id,
                 character_id=character_id, reason=death_reason)
    return True


# ── Narrative tag bulk processor ─────────────────────────────────────────────

def process_narrative_xp_tags(
    narrative: str,
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    turn_number: int,
    session_free_grant_total: int | None = None,
) -> dict[str, Any]:
    """Parse XS2-XS4, XS7-XS8, XS12 tags from GM narrative. Returns total granted.

    AUDIT #1445: when the caller doesn't pass an explicit running total (default), the
    [XP_GRANT] free-grant total is loaded from and persisted back to session_flags. Every
    caller previously used the default 0 and discarded the returned total, so
    XP_GRANT_SESSION_CAP reset every turn (50 XP/turn, unbounded per session).
    """
    import json as _pjson
    total = 0

    _persist = session_free_grant_total is None
    _sf_row = None
    _sf: dict[str, Any] = {}
    if _persist:
        _sf_row = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if _sf_row and _sf_row["session_flags"]:
            try:
                _sf = _pjson.loads(_sf_row["session_flags"] or "{}")
            except Exception:
                _sf = {}
        session_free_grant_total = int(_sf.get("xp_free_grant_session_total", 0) or 0)

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
        _ending_id_from_tag = m.group(1).strip()
        total += grant_campaign_end(conn, character_id, campaign_id, _ending_id_from_tag, turn_number)
        # T38 (#1009): a narrator [CAMPAIGN_END] tag also closes the campaign,
        # not just grants XP (completes the half-built victory path).
        # #1058: also store ended_at + selected_ending_id so victory screen picks
        # the correct ending instead of always using endings[0].
        try:
            _ended_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute(
                "UPDATE campaigns SET status = 'completed', ended_at = ? "
                "WHERE id = ? AND lower(coalesce(status, '')) = 'active'",
                (_ended_at, campaign_id),
            )
            conn.commit()
        except Exception as _ce_err:
            logger.warning("campaign_end_status_error", error=str(_ce_err))
        try:
            from app.services.solo_death_service import _store_selected_ending
            _store_selected_ending(conn, campaign_id, _ending_id_from_tag)
        except Exception as _se_err:
            logger.warning("campaign_end_store_ending_error", error=str(_se_err))

    # #1469: [DEATH_TRIGGER] — scripted/environmental death (lava, fall, drown).
    # The system-prompt RESTRICT block allows narrative death ONLY via this tag
    # (or death_save fail / combat HP<=0). Honour that contract: run the real
    # death mechanic (end campaign + epitaph) instead of leaving a dead promise.
    if _DEATH_TRIGGER_RE.search(narrative):
        try:
            _trigger_environmental_death(conn, character_id, campaign_id, narrative)
        except Exception as _dt_err:  # never crash a turn on a death-trigger hiccup
            logger.warning("death_trigger_error", error=str(_dt_err),
                           campaign_id=campaign_id, character_id=character_id)

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

    # T38/#1097 (#1009): deterministic finale-gate spinacz — runs after every turn's
    # tags. Opens (sticky) only when all acts/scenes are traversed AND no active
    # quests remain; the player triggers the actual completion via POST /finish.
    finale_opened = False
    try:
        from app.services.campaign_plan_runtime import maybe_complete_campaign
        finale_opened = maybe_complete_campaign(campaign_id, character_id, turn_number, conn)
    except Exception as _vc_err:
        logger.warning("campaign_victory_check_error", error=str(_vc_err))

    # AUDIT #1445: persist the running free-grant total so the session cap survives turns.
    if _persist and _sf_row is not None:
        try:
            _sf["xp_free_grant_session_total"] = int(session_free_grant_total or 0)
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                (_pjson.dumps(_sf, ensure_ascii=False), _sf_row["id"]),
            )
            conn.commit()
        except Exception as _persist_err:
            logger.warning("xp_grant_session_total_persist_error", error=str(_persist_err))

    return {
        "total_granted": total,
        "session_free_grant_total": session_free_grant_total,
        "finale_available_transition": finale_opened,
    }
