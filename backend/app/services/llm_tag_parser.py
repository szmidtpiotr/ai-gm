"""U5 (#528): Central LLM tag parser registry.

All LLM-emitted [TAG:...] patterns registered here. Single point for:
- pattern definitions (all tag regexes in one place)
- error logging to llm_tag_errors table
- unknown tag detection

Parse result status values:
  ok                — tag parsed and action applied
  invalid_schema    — tag syntax wrong (bad fields, missing required)
  invalid_reference — key doesn't exist in DB
  rejected_by_gate  — gate mechanism blocked the action
  dc_clamped        — DC value clamped to nearest allowed value (U7)
  unknown_tag       — tag name not in registry

The existing individual parsers (quest_suggest_parser, spend_gold_service, etc.)
remain authoritative for their logic. This module centralises:
1. The regex definitions (single source of truth)
2. The error logging function
3. Unknown-tag detection
"""
from __future__ import annotations

import re
import sqlite3
from typing import Optional

import structlog

logger = structlog.get_logger()

# ── Tag registry: name → compiled regex ──────────────────────────────────────
# Patterns copied from their authoritative service files; kept in sync here.

TAG_REGISTRY: dict[str, re.Pattern] = {
    # C10: quests
    "QUEST_SUGGEST": re.compile(
        r'\[QUEST_SUGGEST:\s*([^|\]]+?)\s*\|\s*([^|\]]+?)\s*\|\s*([^|\]]+?)\s*\]',
        re.IGNORECASE,
    ),
    "QUEST_COMPLETE": re.compile(
        r'\[QUEST_COMPLETE:\s*([^\]]+?)\s*\]',
        re.IGNORECASE,
    ),
    # C12: gold sink
    "SPEND_GOLD": re.compile(
        r'\[SPEND_GOLD:\s*([a-zA-Z0-9_]+)\s*\]',
    ),
    # Skill tests (B4 / U7)
    "SKILL_TEST": re.compile(
        r'\[SKILL_TEST:\s*([^:\]]+?)\s*:\s*(\d+|OPPOSED:\d+)\s*\]',
        re.IGNORECASE,
    ),
    "SKILL_CHECK": re.compile(
        r'\[SKILL_CHECK:\s*([^:\]]+?)\s*:\s*(\d+|OPPOSED:\d+)\s*\]',
        re.IGNORECASE,
    ),
    "TRAP": re.compile(
        r'\[TRAP:\s*([^:\]]+?)\s*:\s*(\d+)\s*:\s*([^:\]]+?)\s*:\s*([^\]]+?)\s*\]',
        re.IGNORECASE,
    ),
    # D3: NPC memory
    "NPC_MEMORY": re.compile(
        r'\[NPC_MEMORY:\s*([^|\]]+?)\s*\|\s*([^\]]+?)\s*\]',
        re.IGNORECASE,
    ),
    # D6: narrative state
    "NARRATIVE_EVENT": re.compile(
        r"\[NARRATIVE_EVENT:\s*key=([^,\]]+?)\s*,\s*note=([^\]]+?)\s*\]",
        re.IGNORECASE,
    ),
    "NARRATIVE_SEED": re.compile(
        r"\[NARRATIVE_SEED:\s*key=([^,\]]+?)\s*,\s*hint=([^\]]+?)\s*\]",
        re.IGNORECASE,
    ),
    # E6/E9: GM plan
    "BEAT_COMPLETE": re.compile(
        r'\[BEAT_COMPLETE:\s*([^\]]+?)\s*\]',
        re.IGNORECASE,
    ),
    "ARC_ADVANCE": re.compile(
        r'\[ARC_ADVANCE:\s*([^\]]+?)\s*\]',
        re.IGNORECASE,
    ),
    # Combat
    "COMBAT_START": re.compile(
        r'\[COMBAT_START:\s*([^\]]+?)\s*\]',
        re.IGNORECASE,
    ),
    "APPLY_CONDITION": re.compile(
        r'\[APPLY_CONDITION:\s*([^:\]]+?)\s*:\s*([^\]]+?)\s*\]',
        re.IGNORECASE,
    ),
    # World creation (world_service)
    "CREATE_LOCATION": re.compile(
        r"\[CREATE_LOCATION:\s*(.*?)\]",
        re.IGNORECASE | re.DOTALL,
    ),
    "CREATE_NPC": re.compile(
        r"\[CREATE_NPC:\s*(.*?)\]",
        re.IGNORECASE | re.DOTALL,
    ),
    "CREATE_ENEMY": re.compile(
        r"\[CREATE_ENEMY:\s*(.*?)\]",
        re.IGNORECASE | re.DOTALL,
    ),
    "NPC_KILLED": re.compile(
        r"\[NPC_KILLED:\s*key\s*=\s*([^\]\s,]+)\]",
        re.IGNORECASE,
    ),
    "SET_SAFE_FOR_REST": re.compile(
        r"\[SET_SAFE_FOR_REST:\s*([^\]\s:,]+)\s*:\s*(on|off|true|false|1|0)\s*\]",
        re.IGNORECASE,
    ),
    # XP sources
    "DISCOVERY": re.compile(
        r'\[DISCOVERY:\s*([^|\]]+?)\s*\|\s*([^\]]+?)\s*\]',
        re.IGNORECASE,
    ),
    "XP_GRANT": re.compile(
        r'\[XP_GRANT:\s*([^:\]]+?)\s*:\s*(\d+)\s*\]',
        re.IGNORECASE,
    ),
    "CAMPAIGN_END": re.compile(
        r'\[CAMPAIGN_END:\s*([^\]]+?)\s*\]',
        re.IGNORECASE,
    ),
    # Dungeons
    "DUNGEON_CLEAR": re.compile(
        r'\[DUNGEON_CLEAR:\s*([^\]]+?)\s*\]',
        re.IGNORECASE,
    ),
}

# Detects any [CAPS_WORD:...] pattern — for unknown-tag scanning
_ANY_TAG_RE = re.compile(r'\[([A-Z][A-Z0-9_]+):([^\]]*)\]')


# ── Unknown tag detection ─────────────────────────────────────────────────────

def find_unknown_tags(text: Optional[str]) -> list[str]:
    """Return raw tag strings found in text whose name is NOT in TAG_REGISTRY."""
    if not text:
        return []
    result = []
    for m in _ANY_TAG_RE.finditer(text):
        tag_name = m.group(1).upper()
        if tag_name not in TAG_REGISTRY:
            result.append(m.group(0))
    return result


# ── Error logging ─────────────────────────────────────────────────────────────

def log_tag_error(
    conn: sqlite3.Connection,
    campaign_id: int,
    turn_number: int,
    tag_raw: str,
    error_type: str,
) -> None:
    """Insert a row into llm_tag_errors. Never raises — logging must not crash a turn.

    error_type values: invalid_schema / invalid_reference / rejected_by_gate /
                       dc_clamped / unknown_tag
    """
    try:
        conn.execute(
            """
            INSERT INTO llm_tag_errors (campaign_id, turn_number, tag_raw, error_type, ts)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (campaign_id, turn_number, (tag_raw or "")[:500], error_type),
        )
        conn.commit()
        logger.info(
            "llm_tag_error_logged",
            campaign_id=campaign_id,
            turn=turn_number,
            error_type=error_type,
        )
    except Exception as exc:
        logger.warning("llm_tag_error_log_failed", exc=str(exc))


def get_tag_error_count(conn: sqlite3.Connection, campaign_id: int) -> int:
    """Return total number of tag errors recorded for a campaign."""
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM llm_tag_errors WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0
