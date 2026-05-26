"""Solo campaign death: death save tracking, campaign end, epitaph LLM."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import sqlite3

from app.core.logging import get_logger
from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full

logger = get_logger(__name__)

DEATH_SAVE_FAILURE_THRESHOLD = 3

# V2: Escalating DC ladder — pure d20, no CON modifier
# Each time player reaches 0 HP in same combat, DC increases.
_V2_DC_LADDER = [10, 13, 16, 19]


def get_v2_death_save_dc(death_save_count: int) -> int:
    """Return the DC for the Nth 0-HP event in this combat (1-indexed)."""
    idx = min(max(0, death_save_count - 1), len(_V2_DC_LADDER) - 1)
    return _V2_DC_LADDER[idx]


def apply_death_save_outcome(sheet: dict, roll_result: dict) -> tuple[dict, bool]:
    """
    Update death_save_failures on sheet for a resolved death_save roll.
    Returns (updated_sheet, died) where died is True if failures >= threshold.

    V2: Uses escalating DC via death_save_count field on sheet.
    Falls back to fixed DC 10 for V1 compatibility.
    """
    if roll_result.get("test") != "death_save":
        return sheet, False

    out = dict(sheet) if isinstance(sheet, dict) else {}
    prev = int(out.get("death_save_failures") or 0)
    total = int(roll_result.get("total") or 0)
    is_nat20 = bool(roll_result.get("is_nat20"))
    is_nat1 = bool(roll_result.get("is_nat1"))

    # V2: use escalating DC if death_save_count is tracked
    death_save_count = int(out.get("death_save_count") or 1)
    dc = get_v2_death_save_dc(death_save_count)

    if total >= dc or is_nat20:
        # Success: clear failures (but NOT death_save_count — it persists per combat)
        new_failures = prev  # V2: failures do NOT reset on success (ladder is per-combat)
    else:
        inc = 2 if is_nat1 else 1
        new_failures = prev + inc

    out["death_save_failures"] = new_failures
    # Increment count for next 0-HP event
    out["death_save_count"] = death_save_count + (1 if not (total >= dc or is_nat20) else 0)
    died = new_failures >= DEATH_SAVE_FAILURE_THRESHOLD
    return out, died


def _identity_bits(sheet: dict) -> dict[str, str]:
    ident = sheet.get("identity") if isinstance(sheet.get("identity"), dict) else {}
    bonds = ident.get("bonds")
    bond_text = ""
    if isinstance(bonds, list) and bonds:
        b0 = bonds[0] if isinstance(bonds[0], dict) else {}
        bond_text = str(b0.get("text") or "")
    return {
        "personality": str(ident.get("personality") or ""),
        "flaw": str(ident.get("flaw") or ""),
        "bond": bond_text,
        "secret": str(ident.get("secret") or ""),
    }


def generate_epitaph_llm(
    *,
    name: str,
    class_label: str,
    death_reason: str,
    sheet: dict,
    user_id: int,
    model: str,
) -> str:
    bits = _identity_bits(sheet)
    prompt = (
        "Write a short epitaph (2-3 sentences) for a fallen RPG character.\n"
        f"Name: {name}\n"
        f"Class: {class_label}\n"
        f"Died: {death_reason}\n"
        f"Personality: {bits['personality']}\n"
        f"Flaw: {bits['flaw']}\n"
        f"Bond: {bits['bond']}\n"
        f"Secret (weave in subtly if fitting): {bits['secret']}\n\n"
        "Write in the same language as the personality text. Dark fantasy tone. No markdown."
    )
    messages = [
        {"role": "system", "content": "You write brief, atmospheric RPG epitaphs. Plain text only."},
        {"role": "user", "content": prompt},
    ]
    llm_config = get_user_llm_settings_full(user_id)
    try:
        text = (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip()
    except Exception as e:
        logger.warning("epitaph_llm_failed", error_message=str(e))
        text = ""
    if not text:
        return f"Here lies {name}, {class_label}, claimed by fate."
    return text


def end_solo_campaign_on_death(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_row: sqlite3.Row,
    death_reason: str,
) -> str:
    """
    Sets campaign to ended, fills ended_at, death_reason, epitaph.
    Returns epitaph text.
    """
    sheet = {}
    try:
        sheet = json.loads(character_row["sheet_json"] or "{}")
    except Exception:
        sheet = {}
    if not isinstance(sheet, dict):
        sheet = {}

    name = (character_row["name"] or "Hero").strip()
    arch = str(sheet.get("archetype") or sheet.get("class") or "adventurer").strip()
    user_id = int(character_row["user_id"] or 1)

    camp = conn.execute(
        "SELECT model_id, owner_user_id FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()
    model = str(camp["model_id"] or "").strip() if camp else "gemma3:1b"
    owner_id = int(camp["owner_user_id"]) if camp else user_id
    llm_config = get_user_llm_settings_full(owner_id)
    model_resolved = (llm_config.get("model") or model or "").strip() or model

    epitaph = generate_epitaph_llm(
        name=name,
        class_label=arch,
        death_reason=death_reason,
        sheet=sheet,
        user_id=owner_id,
        model=model_resolved,
    )

    ended_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        UPDATE campaigns
        SET status = 'ended',
            death_reason = ?,
            ended_at = ?,
            epitaph = ?
        WHERE id = ?
        """,
        (death_reason, ended_at, epitaph, campaign_id),
    )
    conn.commit()
    logger.error(
        "player_death",
        cause=death_reason,
        campaign_id=campaign_id,
        character_name=name,
    )
    # O1 — log player_death event (best-effort)
    try:
        from app.services.event_logger import write_game_event
        write_game_event(
            "player_death",
            campaign_id,
            int(character_row["id"]),
            user_id,
            {"cause": death_reason},
            severity="warning",
            conn=conn,
        )
        conn.commit()
    except Exception:
        pass
    # T42: flush pending_xp on death — between campaigns counts as long rest
    try:
        character_id = int(character_row["id"])
        from app.services.rest_service import flush_pending_xp_on_campaign_end
        flush_pending_xp_on_campaign_end(conn, character_id, campaign_id)
    except Exception as _flush_err:
        logger.warning("pending_xp_flush_failed_death", error=str(_flush_err))
    return epitaph


def death_summary_payload(
    conn: sqlite3.Connection,
    campaign_id: int,
) -> dict[str, Any] | None:
    """Build death-summary JSON or None if not ended."""
    return _end_summary_payload(conn, campaign_id, expected_outcome="death")


def end_summary_payload(
    conn: sqlite3.Connection,
    campaign_id: int,
) -> dict[str, Any] | None:
    """Stage 9 P5+P6 — unified payload for both death AND victory screens.

    Reads `campaigns.status`:
      'ended'     → outcome='death',   epitaph + death_reason
      'completed' → outcome='victory', ending title + summary from gm_plan_json
    Returns None if campaign is still active.
    """
    return _end_summary_payload(conn, campaign_id, expected_outcome=None)


def _end_summary_payload(
    conn: sqlite3.Connection,
    campaign_id: int,
    expected_outcome: str | None,
) -> dict[str, Any] | None:
    camp = conn.execute(
        """
        SELECT id, status, death_reason, ended_at, epitaph, gm_plan_json
        FROM campaigns WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()
    if not camp:
        return None
    status = str(camp["status"] or "").strip().lower()
    if status == "ended":
        outcome = "death"
    elif status == "completed":
        outcome = "victory"
    else:
        return None
    if expected_outcome and outcome != expected_outcome:
        return None

    ch = conn.execute(
        """
        SELECT id, name, sheet_json FROM characters
        WHERE campaign_id = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (campaign_id,),
    ).fetchone()
    if not ch:
        return None

    sheet = {}
    try:
        sheet = json.loads(ch["sheet_json"] or "{}")
    except Exception:
        sheet = {}
    ident = sheet.get("identity") if isinstance(sheet.get("identity"), dict) else {}
    bonds_raw = ident.get("bonds")
    bonds_out: list[dict[str, str]] = []
    if isinstance(bonds_raw, list):
        for b in bonds_raw:
            if isinstance(b, dict):
                # Support BOTH V2 (description) and V1 (text) key shapes.
                bonds_out.append(
                    {
                        "text": str(b.get("description") or b.get("text") or ""),
                        "strength": str(b.get("strength") or "strong"),
                        "origin": str(b.get("origin") or "creation"),
                    }
                )

    from app.services.xp_service import get_hero_level
    arch = str(sheet.get("archetype") or sheet.get("class") or "adventurer").strip()
    level = get_hero_level(sheet)
    xp_lifetime = int(sheet.get("xp_lifetime_earned") or 0)

    # Pull ending title + summary from gm_plan_json for victory.
    ending_title = ""
    ending_summary = ""
    if outcome == "victory":
        try:
            plan = json.loads(camp["gm_plan_json"] or "{}")
        except Exception:
            plan = {}
        endings = plan.get("endings")
        # endings may be a dict keyed by ending_id, or a list. Pick the first
        # non-empty one for MVP — when CAMPAIGN_END tag lands the id will be
        # propagated explicitly.
        ending_obj = None
        if isinstance(endings, dict) and endings:
            ending_obj = next(iter(endings.values()))
        elif isinstance(endings, list) and endings:
            ending_obj = endings[0]
        if isinstance(ending_obj, dict):
            ending_title = str(ending_obj.get("title") or "")
            ending_summary = str(ending_obj.get("summary") or ending_obj.get("description") or "")

    return {
        "outcome": outcome,  # 'death' | 'victory'
        "campaign_id": int(camp["id"]),
        "character_id": int(ch["id"]),
        "character_name": str(ch["name"] or ""),
        "character_class": arch,
        "level": level or 1,
        "xp_lifetime_earned": xp_lifetime,
        "death_reason": str(camp["death_reason"] or ""),
        "ended_at": str(camp["ended_at"] or ""),
        "epitaph": str(camp["epitaph"] or ""),
        "ending_title": ending_title,
        "ending_summary": ending_summary,
        "secret": str(ident.get("secret") or ""),
        "bonds": bonds_out,
        "xp_unlocked": _get_end_flush_xp(conn, int(ch["id"]), int(camp["id"])),
    }


def _get_end_flush_xp(conn: sqlite3.Connection, character_id: int, campaign_id: int) -> int:
    """Return pending_xp flushed at campaign end (source='campaign_end_flush')."""
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM character_xp_grants "
            "WHERE character_id = ? AND campaign_id = ? AND source = 'campaign_end_flush'",
            (character_id, campaign_id),
        ).fetchone()
        return int(row[0] or 0)
    except Exception:
        return 0
