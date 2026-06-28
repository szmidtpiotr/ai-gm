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
) -> bool:
    """Insert quest into character_quests if not already present.

    Returns True if inserted, False if duplicate (exact title OR similar objective).
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

    if turn_number is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
            (campaign_id,),
        ).fetchone()
        turn_number = row[0] if row else 1

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
