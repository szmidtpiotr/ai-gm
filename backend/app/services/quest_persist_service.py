"""HF-2 (#524): Quest persistence to character_quests table.

Two public functions called from turns.py QUEST_SUGGEST and kill-quest handlers:
  persist_quest_to_character_quests()  — INSERT on QUEST_SUGGEST parse
  complete_quest_in_character_quests() — UPDATE on kill/location auto-complete

#756: added objective-level dedup (Jaccard word similarity) + build_quest_context_block().
#991: check_and_set_quest_suggest_needed() + build_quest_suggest_directive() — quest-dead guard.
"""
from __future__ import annotations

import re
import sqlite3
import structlog

logger = structlog.get_logger(__name__)

_SIMILARITY_THRESHOLD = 0.65

# #1011: hard cap on concurrent active quests. The narrator can emit a fresh
# [QUEST_SUGGEST] almost every turn; title + Jaccard-objective dedup misses
# re-worded near-duplicates (smoke 999972 spawned 5 variants of "find Iwo").
# Beyond this many active main quests, new suggestions are dropped until the
# player closes one. STARTING VALUE — tunable.
MAX_ACTIVE_QUESTS = 3


def count_active_quests(
    conn: sqlite3.Connection, campaign_id: int, character_id: int | None = None
) -> int:
    """Count active *main* quests for a campaign (optionally scoped to a character)."""
    if character_id is not None:
        row = conn.execute(
            "SELECT COUNT(*) FROM character_quests "
            "WHERE campaign_id=? AND character_id=? AND status='active' "
            "AND COALESCE(quest_type,'main')='main'",
            (campaign_id, character_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) FROM character_quests "
            "WHERE campaign_id=? AND status='active' "
            "AND COALESCE(quest_type,'main')='main'",
            (campaign_id,),
        ).fetchone()
    return int(row[0]) if row else 0


def _normalize_words(text: str) -> set[str]:
    """Lowercase + strip punctuation → set of words for Jaccard comparison."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return set(text.split())


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _is_duplicate_objective(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    new_objective: str,
) -> bool:
    """Return True if any active quest has high word-overlap with new_objective."""
    rows = conn.execute(
        "SELECT narrative FROM character_quests WHERE character_id=? AND campaign_id=? AND status='active'",
        (character_id, campaign_id),
    ).fetchall()
    new_words = _normalize_words(new_objective)
    for row in rows:
        stored = row[0] or ""
        if stored and _jaccard(new_words, _normalize_words(stored)) >= _SIMILARITY_THRESHOLD:
            return True
    return False


def persist_quest_to_character_quests(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    quest: dict,
    turn_number: int | None = None,
    beat_key: str | None = None,
) -> bool:
    """Insert quest into character_quests if not already present.

    Returns True if inserted, False if duplicate (exact title OR similar objective).

    #1015: `beat_key` pins the quest to the scene that spawned it so the #1011
    skip-cancel loop can fire (skipped beat → skipped quest). It may also be read
    from the quest dict (`quest["beat_key"]`) for template/Forge spawn paths;
    the explicit argument wins. None = unlinked quest (legacy behavior).
    """
    title = quest.get("title", "").strip()
    if not title:
        return False

    existing = conn.execute(
        "SELECT id FROM character_quests WHERE character_id=? AND campaign_id=? AND title=?",
        (character_id, campaign_id, title),
    ).fetchone()
    if existing:
        return False

    narrative = quest.get("objective", quest.get("narrative", ""))

    # #756: reject near-duplicate objectives even when the title differs
    if narrative and _is_duplicate_objective(conn, character_id, campaign_id, narrative):
        logger.info(
            "quest_rejected_duplicate_objective",
            character_id=character_id,
            campaign_id=campaign_id,
            title=title,
        )
        return False

    # #1011: cap concurrent active quests — backstop against runaway narrator spam
    # that re-wording slips past the dedup. Beyond the cap, drop the new quest.
    if count_active_quests(conn, campaign_id, character_id) >= MAX_ACTIVE_QUESTS:
        logger.info(
            "quest_rejected_at_cap",
            character_id=character_id,
            campaign_id=campaign_id,
            title=title,
            cap=MAX_ACTIVE_QUESTS,
        )
        return False

    if turn_number is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
            (campaign_id,),
        ).fetchone()
        turn_number = row[0] if row else 1

    # #1015: explicit arg wins; fall back to a beat_key carried on the quest dict
    # (template/Forge spawn). Empty string normalizes to NULL (= unlinked).
    link = beat_key if beat_key is not None else quest.get("beat_key")
    link = (str(link).strip() or None) if link else None

    try:
        conn.execute(
            """INSERT INTO character_quests
                   (character_id, campaign_id, quest_type, title, narrative, status,
                    created_turn, beat_key)
               VALUES (?,?,?,?,?,?,?,?)""",
            (character_id, campaign_id, "main", title, narrative, "active", turn_number, link),
        )
    except sqlite3.OperationalError:
        # beat_key column not migrated yet → insert without the link (legacy schema).
        conn.execute(
            """INSERT INTO character_quests
                   (character_id, campaign_id, quest_type, title, narrative, status, created_turn)
               VALUES (?,?,?,?,?,?,?)""",
            (character_id, campaign_id, "main", title, narrative, "active", turn_number),
        )
    conn.commit()
    logger.info(
        "quest_persisted_to_db",
        character_id=character_id,
        campaign_id=campaign_id,
        title=title,
        created_turn=turn_number,
        beat_key=link,
    )
    return True


def build_quest_context_block(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
) -> str:
    """Build a QUESTY context block for LLM prompt injection.

    Lists active quests so LLM knows what already exists and avoids re-proposing them.
    Returns '' on any error or when no active quests.
    """
    try:
        rows = conn.execute(
            """SELECT title, narrative FROM character_quests
               WHERE character_id=? AND campaign_id=? AND status='active'
               ORDER BY created_turn""",
            (character_id, campaign_id),
        ).fetchall()
    except Exception as e:
        logger.warning("quest_context_block_failed", error=str(e))
        return ""

    if not rows:
        return ""

    lines = ["=== QUESTY (aktywne zadania bohatera) ==="]
    for row in rows:
        title = row[0] or "?"
        objective = row[1] or ""
        if objective:
            lines.append(f"• {title}: {objective}")
        else:
            lines.append(f"• {title}")
    return "\n".join(lines)


def get_active_quests_for_bar(
    conn: sqlite3.Connection,
    campaign_id: int,
) -> list[dict]:
    """#999 — Active quests for the HUD quest bar, read from character_quests.

    Single source of truth: character_quests WHERE status='active'. Replaces the
    old world_state.active_quests read, which drifted (completed quests never
    pruned, new ones never added). Maps `narrative` → `objective` for the HUD
    (renderQuestBar reads q.title / q.objective / q.reward); `reward` is not
    stored on character_quests so it is returned empty.
    """
    try:
        rows = conn.execute(
            """SELECT title, narrative FROM character_quests
               WHERE campaign_id=? AND status='active'
               ORDER BY created_turn, id""",
            (campaign_id,),
        ).fetchall()
    except Exception as e:
        logger.warning("quest_bar_query_failed", campaign_id=campaign_id, error=str(e))
        return []

    out: list[dict] = []
    for row in rows:
        d = dict(row) if hasattr(row, "keys") else {"title": row[0], "narrative": row[1]}
        out.append({
            "title": d.get("title") or "",
            "objective": d.get("narrative") or "",
            "reward": "",
        })
    return out


def complete_quest_in_character_quests(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    title: str,
    completed_turn: int | None = None,
) -> bool:
    """Mark quest as completed in character_quests.

    Returns True if a row was updated, False if quest not found or already done.
    """
    if completed_turn is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(turn_number),1) FROM campaign_turns WHERE campaign_id=?",
            (campaign_id,),
        ).fetchone()
        completed_turn = row[0] if row else 1

    # T38 (#1009): match title case/whitespace-insensitively. The narrator often
    # restates a quest title with a different case or stray spaces; an exact `title=?`
    # match silently no-ops, leaving the quest active forever and blocking the
    # campaign-victory check ("0 active quests"). Matching is done in Python with
    # str.casefold() — SQLite's lower() is ASCII-only and would mis-handle Polish
    # diacritics (e.g. 'Ł' stays 'Ł', never folds to 'ł').
    want = (title or "").strip().casefold()
    rows = conn.execute(
        "SELECT id, title FROM character_quests "
        "WHERE character_id=? AND campaign_id=? AND status='active'",
        (character_id, campaign_id),
    ).fetchall()
    match_id = None
    for r in rows:
        r_title = r["title"] if isinstance(r, sqlite3.Row) else r[1]
        if (r_title or "").strip().casefold() == want:
            match_id = r["id"] if isinstance(r, sqlite3.Row) else r[0]
            break
    if match_id is None:
        return False
    cur = conn.execute(
        """UPDATE character_quests
           SET status='completed', completed_turn=?, updated_at=datetime('now')
           WHERE id=? AND status='active'""",
        (completed_turn, match_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    if updated:
        logger.info(
            "quest_completed_in_db",
            character_id=character_id,
            campaign_id=campaign_id,
            title=title,
            completed_turn=completed_turn,
        )
    return updated


# ── #1011: Auto-complete quests by game event (no [QUEST_COMPLETE] tag) ──────
#
# The narrator closes a quest only when it remembers to emit [QUEST_COMPLETE:title].
# If it forgets (but the quest is fabularnie done), the quest hangs status='active'
# forever and blocks the campaign-victory check ("0 active quests", #1009).
# This mirrors the beat model (auto_complete_beats_by_event): a quest with a
# structured objective_type/objective_value closes itself on the matching event;
# a quest with no structured objective falls back to keyword-matching its narrative
# against the event target. Campaign-scoped, idempotent.

_QUEST_OBJECTIVE_TYPES = frozenset(
    {"kill_enemy", "visit_location", "talk_to_npc", "find_item"}
)


def auto_complete_quests_by_event(
    conn: sqlite3.Connection,
    campaign_id: int,
    event_type: str,
    target_name: str,
    turn_number: int,
) -> list[str]:
    """Auto-complete active quests whose condition matches a game event.

    Matching, per active quest in the campaign:
      • structured: objective_type == event_type AND (objective_value empty = wildcard,
        OR objective_value keyword-matches target_name);
      • fallback (no objective_type): the quest narrative/title keyword-matches
        target_name AND event_type is one of the known objective types.

    On match: flips status→completed and fires the same side-effects as the tag path
    (XP grant, #991 quest-dead guard) best-effort. Returns the list of completed titles.
    """
    if event_type not in _QUEST_OBJECTIVE_TYPES or not target_name:
        return []

    from app.services.quest_checker import _keyword_match

    try:
        rows = conn.execute(
            "SELECT id, character_id, title, narrative, objective_type, objective_value "
            "FROM character_quests WHERE campaign_id=? AND status='active'",
            (campaign_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        # objective_type/objective_value columns not migrated yet → fall back to a
        # structureless query so the keyword path still works.
        rows = conn.execute(
            "SELECT id, character_id, title, narrative, "
            "NULL AS objective_type, NULL AS objective_value "
            "FROM character_quests WHERE campaign_id=? AND status='active'",
            (campaign_id,),
        ).fetchall()

    completed: list[str] = []
    for r in rows:
        obj_type = r["objective_type"]
        obj_value = (r["objective_value"] or "") if obj_type else ""
        if obj_type:
            if obj_type != event_type:
                continue
            # wildcard (empty objective_value) matches any target of the right type
            if obj_value and not _keyword_match(obj_value, target_name):
                continue
        else:
            # no structured objective → keyword fallback on narrative + title
            haystack = f"{r['narrative'] or ''} {r['title'] or ''}".strip()
            if not haystack or not _keyword_match(haystack, target_name):
                continue

        cur = conn.execute(
            "UPDATE character_quests "
            "SET status='completed', completed_turn=?, updated_at=datetime('now') "
            "WHERE id=? AND status='active'",
            (turn_number, r["id"]),
        )
        if cur.rowcount <= 0:
            continue
        title = r["title"]
        character_id = r["character_id"]
        completed.append(title)
        logger.info(
            "quest_auto_completed",
            campaign_id=campaign_id,
            character_id=character_id,
            title=title,
            event_type=event_type,
            target=target_name,
        )
        # Parity with the tag path: grant XP, log event, fire #991 guard. Best-effort —
        # never let a reward failure leave the flip half-done.
        try:
            from app.services.xp_sources import grant_quest_complete
            grant_quest_complete(conn, character_id, campaign_id, title, turn_number)
        except Exception as _xp_err:
            logger.warning("quest_auto_complete_xp_error", title=title, error=str(_xp_err))
        try:
            from app.services.event_logger import write_game_event
            write_game_event(
                "quest_complete", campaign_id, character_id, None,
                {"quest_title": title, "turn": turn_number, "auto": True},
                conn=conn,
            )
        except Exception as _ev_err:
            logger.warning("quest_auto_complete_event_error", title=title, error=str(_ev_err))

    if completed:
        conn.commit()
        # #991 quest-dead guard: set flag once if no active quests remain.
        try:
            last = completed[-1]
            # character_id of the last completed quest drives the guard scope.
            for r in rows:
                if r["title"] == last:
                    check_and_set_quest_suggest_needed(
                        conn, r["character_id"], campaign_id, last
                    )
                    break
        except Exception as _g_err:
            logger.warning("quest_auto_complete_guard_error", error=str(_g_err))

    return completed


# ── #1011 refinement: cancel quests pinned to skipped beats ──────────────────


def cancel_quests_for_skipped_beats(
    conn: sqlite3.Connection,
    campaign_id: int,
    beat_keys: list[str],
) -> list[str]:
    """Cancel active quests pinned (via `beat_key`) to beats skipped on act close.

    When an optional beat is skipped (critical-path act completion, #1010), any
    side-quest attached to it would otherwise hang `status='active'` forever and
    block the #1009 victory check. Flip such quests to `status='skipped'` so the
    player legally dropping a side thread does not strand the campaign.

    Returns the titles of cancelled quests. Idempotent; tolerant of an un-migrated
    `beat_key` column (returns [] without raising).
    """
    if not beat_keys:
        return []
    placeholders = ",".join("?" * len(beat_keys))
    try:
        rows = conn.execute(
            f"SELECT id, title FROM character_quests "
            f"WHERE campaign_id=? AND status='active' AND beat_key IN ({placeholders})",
            (campaign_id, *beat_keys),
        ).fetchall()
    except sqlite3.OperationalError:
        # beat_key column not migrated yet → nothing to cancel by link.
        return []

    cancelled: list[str] = []
    for r in rows:
        cur = conn.execute(
            "UPDATE character_quests "
            "SET status='skipped', updated_at=datetime('now') "
            "WHERE id=? AND status='active'",
            (r["id"],),
        )
        if cur.rowcount > 0:
            cancelled.append(r["title"])
    if cancelled:
        conn.commit()
        logger.info(
            "quests_cancelled_skipped_beats",
            campaign_id=campaign_id,
            beat_keys=beat_keys,
            titles=cancelled,
        )
    return cancelled


# ── #1011: Fallback reminder when the narrator forgets [QUEST_COMPLETE] ───────

# Starting value (Numbers Policy): a quest active this many turns without closing
# triggers a narrator nudge. Sandbox-tunable.
QUEST_COMPLETE_REMINDER_THRESHOLD = 8


def build_quest_complete_reminder(
    conn: sqlite3.Connection,
    campaign_id: int,
    current_turn: int,
    threshold: int = QUEST_COMPLETE_REMINDER_THRESHOLD,
) -> str:
    """Build a directive nudging the narrator to close long-lived quests.

    Lists active quests older than `threshold` turns and instructs the narrator to
    emit [QUEST_COMPLETE:dokładny tytuł] if any is fabularnie done. Returns '' when
    no quest is stale (or on error).
    """
    try:
        rows = conn.execute(
            "SELECT title, COALESCE(created_turn, 0) AS created_turn "
            "FROM character_quests WHERE campaign_id=? AND status='active' "
            "ORDER BY created_turn, id",
            (campaign_id,),
        ).fetchall()
    except Exception as e:
        logger.warning("quest_complete_reminder_failed", campaign_id=campaign_id, error=str(e))
        return ""

    stale = [r["title"] for r in rows if (current_turn - int(r["created_turn"])) >= threshold]
    if not stale:
        return ""

    listing = ", ".join(f'"{t}"' for t in stale)
    return (
        f"[QUEST_COMPLETE_REMINDER: Aktywne od dawna zadania: {listing}. "
        "Jeśli któreś zostało FABULARNIE wykonane, OSADŹ w narracji tag "
        "[QUEST_COMPLETE:dokładny tytuł] (skopiuj tytuł 1:1 z powyższej listy). "
        "Nie zamykaj zadania, które nadal trwa.]"
    )


# ── #991: Quest-dead guard ───────────────────────────────────────────────────

QUEST_SUGGEST_URGENCY_THRESHOLD = 3  # turns before directive escalates


def check_and_set_quest_suggest_needed(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    completed_quest_title: str,
) -> bool:
    """After quest completes, set session_flags[quest_suggest_needed] if no active quests remain.

    Returns True if flag was set (no active quests), False if active quests still exist.
    """
    import json

    active_count = conn.execute(
        "SELECT COUNT(*) FROM character_quests WHERE character_id=? AND campaign_id=? AND status='active'",
        (character_id, campaign_id),
    ).fetchone()[0]
    if active_count > 0:
        return False

    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not row:
        return False

    sf = json.loads(row["session_flags"] or "{}")
    sf["quest_suggest_needed"] = {
        "last_completed": completed_quest_title,
        "turns_waiting": 0,
    }
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=?",
        (json.dumps(sf, ensure_ascii=False), campaign_id),
    )
    conn.commit()
    logger.info(
        "quest_suggest_needed_set",
        campaign_id=campaign_id,
        character_id=character_id,
        quest=completed_quest_title,
    )
    return True


def clear_quest_suggest_needed(conn: sqlite3.Connection, campaign_id: int) -> None:
    """Remove quest_suggest_needed flag once a new quest is proposed."""
    import json

    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not row:
        return
    sf = json.loads(row["session_flags"] or "{}")
    if "quest_suggest_needed" in sf:
        del sf["quest_suggest_needed"]
        conn.execute(
            "UPDATE game_sessions SET session_flags=? WHERE campaign_id=?",
            (json.dumps(sf, ensure_ascii=False), campaign_id),
        )
        conn.commit()


def build_quest_suggest_directive(last_completed: str = "", turns_waiting: int = 0) -> str:
    """Build a system directive injected into LLM context to nudge new quest proposal.

    Escalates urgency after QUEST_SUGGEST_URGENCY_THRESHOLD turns without a quest.
    """
    urgency = "PILNE! " if turns_waiting >= QUEST_SUGGEST_URGENCY_THRESHOLD else ""
    completed_part = f' (ukończony quest: "{last_completed}")' if last_completed else ""
    wait_part = f" od {turns_waiting} tur" if turns_waiting > 0 else ""
    return (
        f"[QUEST_SUGGEST_NEEDED: {urgency}Bohater nie ma aktywnego zadania{wait_part}"
        f"{completed_part}. "
        "GM MUSI zaproponować nowy cel używając tagu [QUEST_SUGGEST:tytuł|cel|nagroda] "
        "— wynikający z bieżących odkryć, NPC i lokacji z ostatnich tur. "
        "Nie twórz generycznego questu — użyj konkretnych wątków z historii kampanii.]"
    )
