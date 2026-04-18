"""Solo campaign death: death save tracking, campaign end, epitaph LLM."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import sqlite3

from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full

logger = logging.getLogger(__name__)

DEATH_SAVE_FAILURE_THRESHOLD = 3


def apply_death_save_outcome(sheet: dict, roll_result: dict) -> tuple[dict, bool]:
    """
    Update death_save_failures on sheet for a resolved death_save roll.
    Returns (updated_sheet, died) where died is True if failures >= threshold.
    """
    if roll_result.get("test") != "death_save":
        return sheet, False

    out = dict(sheet) if isinstance(sheet, dict) else {}
    prev = int(out.get("death_save_failures") or 0)
    total = int(roll_result.get("total") or 0)
    is_nat20 = bool(roll_result.get("is_nat20"))
    is_nat1 = bool(roll_result.get("is_nat1"))

    if total >= 10 or is_nat20:
        new_failures = 0
    else:
        inc = 2 if is_nat1 else 1
        new_failures = prev + inc

    out["death_save_failures"] = new_failures
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
        logger.warning("[epitaph] LLM failed: %s", e)
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
    return epitaph


def death_summary_payload(
    conn: sqlite3.Connection,
    campaign_id: int,
) -> dict[str, Any] | None:
    """Build death-summary JSON or None if not ended."""
    camp = conn.execute(
        """
        SELECT id, status, death_reason, ended_at, epitaph
        FROM campaigns WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()
    if not camp or str(camp["status"] or "").lower() != "ended":
        return None

    ch = conn.execute(
        """
        SELECT name, sheet_json FROM characters
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
                bonds_out.append(
                    {
                        "text": str(b.get("text") or ""),
                        "strength": str(b.get("strength") or "strong"),
                        "origin": str(b.get("origin") or "creation"),
                    }
                )

    arch = str(sheet.get("archetype") or sheet.get("class") or "adventurer").strip()

    return {
        "character_name": str(ch["name"] or ""),
        "character_class": arch,
        "death_reason": str(camp["death_reason"] or ""),
        "ended_at": str(camp["ended_at"] or ""),
        "epitaph": str(camp["epitaph"] or ""),
        "secret": str(ident.get("secret") or ""),
        "bonds": bonds_out,
    }
