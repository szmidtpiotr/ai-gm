"""HF-2 (#524): Quest persistence to character_quests table.

Two public functions called from turns.py QUEST_SUGGEST and kill-quest handlers:
  persist_quest_to_character_quests()  — INSERT on QUEST_SUGGEST parse
  complete_quest_in_character_quests() — UPDATE on kill/location auto-complete
"""
from __future__ import annotations

import sqlite3
import structlog

logger = structlog.get_logger(__name__)


def persist_quest_to_character_quests(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    quest: dict,
    turn_number: int | None = None,
) -> bool:
    """Insert quest into character_quests if not already present.

    Returns True if inserted, False if duplicate (same title+character+campaign).
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

    if turn_number is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
            (campaign_id,),
        ).fetchone()
        turn_number = row[0] if row else 1

    narrative = quest.get("objective", quest.get("narrative", ""))
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
