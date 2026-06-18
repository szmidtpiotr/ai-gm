"""HF-2 (#524): Quest persistence to character_quests table.

Two public functions called from turns.py QUEST_SUGGEST and kill-quest handlers:
  persist_quest_to_character_quests()  — INSERT on QUEST_SUGGEST parse
  complete_quest_in_character_quests() — UPDATE on kill/location auto-complete

#756: added objective-level dedup (Jaccard word similarity) + build_quest_context_block().
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

    cur = conn.execute(
        """UPDATE character_quests
           SET status='completed', completed_turn=?, updated_at=datetime('now')
           WHERE character_id=? AND campaign_id=? AND title=? AND status='active'""",
        (completed_turn, character_id, campaign_id, title),
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
