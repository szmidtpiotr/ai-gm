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
    "SKILL_CHECK_AUTO_SUCCESS": re.compile(
        r'\[SKILL_CHECK:\s*auto_success\s*\]',
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


# ── Generic mechanic-tag strip ────────────────────────────────────────────────

_STRIP_TAG_RE = re.compile(r'\s*\[[A-Z][A-Z0-9_]+:[^\]]*\]')


def strip_all_mechanic_tags(text: Optional[str]) -> str:
    """Remove every [ALLCAPS_TAG: ...] from text.

    Covers all known (and future) mechanic tags emitted by the LLM.
    Mirrors the JS stripMechanicTags() in frontend/front/js/app.js.
    """
    if not text:
        return ''
    return _STRIP_TAG_RE.sub('', str(text)).strip()


# ── Leaked JSON-envelope field lines ──────────────────────────────────────────
# Some models (observed on gpt-5.4) duplicate a top-level envelope field INSIDE
# the `narrative` string as a bare `key: value` line, e.g. a narrative ending with
# a literal "location_intent: null" line. These are snake_case identifiers that a
# Polish narration never legitimately starts a line with, so stripping bare lines
# whose sole content is `<known_field>: ...` is safe and does not touch prose. The
# field is still parsed from its real top-level position — only the visible echo is
# removed. Bare `Roll <skill> d20` cues stay untouched here (they drive the dice
# popup in turns.py before display).
_LEAKED_FIELD_NAMES = (
    "location_intent", "roll_cue", "advance_to_time_of_day", "time_of_day",
    "grant_item", "grant_items", "combat_start", "npc_action", "location_action",
    "suggested_actions", "target_label", "target_key", "parent_key",
)
_LEAKED_FIELD_RE = re.compile(
    r'(?im)^[ \t>*\-]*"?(?:' + "|".join(_LEAKED_FIELD_NAMES) + r')"?\s*:.*$'
)
# Collapse 3+ newlines left behind after a mid-text line removal down to a blank line.
_MULTI_BLANK_RE = re.compile(r'\n{3,}')


def strip_leaked_json_fields(text: Optional[str]) -> str:
    """Remove bare `<envelope_field>: value` lines the LLM leaked into narrative prose.

    Only whole lines whose content is a known snake_case envelope key + colon are
    removed; ordinary prose containing colons is never affected.
    """
    if not text:
        return ''
    cleaned = _LEAKED_FIELD_RE.sub('', str(text))
    cleaned = _MULTI_BLANK_RE.sub('\n\n', cleaned)
    return cleaned.strip()


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


# ── Rejection corrections (U6) ────────────────────────────────────────────────
# Templates appended to turn narration when a tag/event is rejected by the engine.
# None = no narration correction (quest exists narratively without XP; skill DC clamped in U7).
import json as _json

REJECTION_CORRECTIONS: dict[str, "str | None"] = {
    # Decision 2026-06-12 (Piotr): pending items DO reach the inventory (D1 flow kept),
    # so the correction must not claim otherwise — neutral "looks worthless" wording.
    "GRANT_ITEM":  "*(Przedmiot wygląda na bezwartościowy — zwykły drobiazg.)*",
    "ITEM_CREATE": "*(Przedmiot wygląda na bezwartościowy — zwykły drobiazg.)*",
    "QUEST_SUGGEST": None,
    "SKILL_CHECK": None,  # DC clamped in U7, no narration correction
    "COMBAT_START": None,  # correction injected by _maybe_start_combat_from_gm_tag (HF-7)
    # S8 (#603): klucz kondycji spoza katalogu game_config_conditions → tag odrzucony.
    "APPLY_CONDITION": "*(Nic trwałego się nie dzieje.)*",
}


def get_rejection_correction(tag_type: str) -> "str | None":
    """Return Polish correction text for rejected tag, or None if no correction needed."""
    return REJECTION_CORRECTIONS.get(tag_type.upper())


def save_rejected_tags(conn: sqlite3.Connection, campaign_id: int, tags: list) -> None:
    """Store rejected tag names in session_flags.last_rejected_tags for next-turn LLM context."""
    if not tags:
        return
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if row is None:
            return
        sf = _json.loads(row["session_flags"] or "{}")
        sf["last_rejected_tags"] = list(tags)
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (_json.dumps(sf, ensure_ascii=False), campaign_id),
        )
        conn.commit()
    except Exception as exc:
        logger.warning("save_rejected_tags_failed", exc=str(exc))


def get_last_rejected_tags(conn: sqlite3.Connection, campaign_id: int) -> list:
    """Return list of rejected tag names from previous turn (for LLM context injection)."""
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if row is None:
            return []
        sf = _json.loads(row["session_flags"] or "{}")
        return list(sf.get("last_rejected_tags", []))
    except Exception:
        return []


def clear_rejected_tags(conn: sqlite3.Connection, campaign_id: int) -> None:
    """Clear last_rejected_tags from session_flags (call at start of new successful turn)."""
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if row is None:
            return
        sf = _json.loads(row["session_flags"] or "{}")
        sf.pop("last_rejected_tags", None)
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (_json.dumps(sf, ensure_ascii=False), campaign_id),
        )
        conn.commit()
    except Exception as exc:
        logger.warning("clear_rejected_tags_failed", exc=str(exc))


# ── U7: DC lock + SKILL_CHECK parser + safety net ────────────────────────────

_DC_SCALE = [8, 12, 16, 20, 24]

# Matches [SKILL_CHECK: auto_success] (checked before the key:dc variant)
_SKILL_CHECK_AUTO_RE = re.compile(r'\[SKILL_CHECK:\s*auto_success\s*\]', re.IGNORECASE)
# Matches [SKILL_CHECK: key: dc]
_SKILL_CHECK_RE = re.compile(
    r'\[SKILL_CHECK:\s*([^:\]]+?)\s*:\s*(\d+)\s*\]', re.IGNORECASE
)
# Presence check — is any [SKILL_CHECK...] in the LLM response?
_SKILL_CHECK_ANY_RE = re.compile(r'\[SKILL_CHECK:', re.IGNORECASE)


def clamp_dc_to_scale(dc: int) -> tuple:
    """Clamp dc to nearest value in _DC_SCALE. Returns (clamped_dc, was_clamped)."""
    nearest = min(_DC_SCALE, key=lambda v: (abs(v - dc), v))
    return (nearest, nearest != dc)


def parse_skill_check_tag(
    tag_text: str,
    conn: sqlite3.Connection,
    campaign_id: int,
    turn_number: int,
) -> "dict | None":
    """Parse a [SKILL_CHECK:...] tag string. Returns dict or None if no match.

    Returns:
        {"auto_success": True}  — for [SKILL_CHECK: auto_success]
        {"skill_key": str, "dc": int, "clamped": bool}  — for [SKILL_CHECK: key: dc]
        None  — if tag_text doesn't match any pattern
    """
    if _SKILL_CHECK_AUTO_RE.search(tag_text):
        return {"auto_success": True}

    m = _SKILL_CHECK_RE.search(tag_text)
    if not m:
        return None

    skill_key = m.group(1).strip()
    raw_dc = int(m.group(2))
    clamped_dc, was_clamped = clamp_dc_to_scale(raw_dc)

    if was_clamped:
        log_tag_error(
            conn=conn,
            campaign_id=campaign_id,
            turn_number=turn_number,
            tag_raw=tag_text[:200],
            error_type="dc_clamped",
        )
        logger.info(
            "skill_check_dc_clamped",
            campaign_id=campaign_id,
            original_dc=raw_dc,
            clamped_dc=clamped_dc,
            skill=skill_key,
        )

    return {"skill_key": skill_key, "dc": clamped_dc, "clamped": was_clamped}


def skill_check_safety_net(
    llm_response: str,
    risky_intent: "dict | None",
    existing_pending: "dict | None",
    conn: sqlite3.Connection,
    campaign_id: int,
) -> "dict | None":
    """Post-LLM safety net: if risky intent detected and LLM omitted [SKILL_CHECK] → force test.

    Returns pending_skill_test dict if test should be forced, None otherwise.
    """
    if not risky_intent:
        return None
    if existing_pending:
        return None
    if _SKILL_CHECK_ANY_RE.search(llm_response or ""):
        return None

    skill_key = risky_intent["skill_key"]
    dc = risky_intent["default_dc"]
    category = risky_intent["category_key"]

    log_tag_error(
        conn=conn,
        campaign_id=campaign_id,
        turn_number=0,
        tag_raw=f"skill_check_forced|category={category}|skill={skill_key}|dc={dc}",
        error_type="skill_check_forced",
    )
    logger.info(
        "skill_check_forced",
        campaign_id=campaign_id,
        skill=skill_key,
        category=category,
        dc=dc,
    )

    return {"skill_key": skill_key, "dc": dc, "source": "safety_net", "category": category}
