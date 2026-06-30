"""Solo campaign death: death save tracking, campaign end, epitaph LLM."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import sqlite3

from app.core.logging import get_logger
from app.services.event_logger import write_game_event
from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full

logger = get_logger(__name__)

DEATH_SAVE_FAILURE_THRESHOLD = 3

# V2: Escalating DC ladder — pure d20, no CON modifier
# Each time player reaches 0 HP in same combat, DC increases.
_V2_DC_LADDER = [10, 13, 16, 19]


# ── #1058 — Victory ending helpers ───────────────────────────────────────────


def _find_ending_by_id(endings, ending_id: str) -> dict | None:
    """Find ending by id in list or dict form of endings."""
    if isinstance(endings, dict):
        return endings.get(ending_id)
    if isinstance(endings, list):
        for e in endings:
            if isinstance(e, dict) and str(e.get("id") or "") == ending_id:
                return e
    return None


def _find_primary_type_ending(endings) -> dict | None:
    """First ending with type=='primary', or first ending if none has that type."""
    if isinstance(endings, dict):
        endings_list = list(endings.values())
    elif isinstance(endings, list):
        endings_list = endings
    else:
        return None
    for e in endings_list:
        if isinstance(e, dict) and e.get("type") == "primary":
            return e
    return endings_list[0] if endings_list else None


def _store_selected_ending(
    conn: sqlite3.Connection,
    campaign_id: int,
    ending_id: str,
) -> None:
    """Persist selected_ending_id inside gm_plan_json for future reads."""
    try:
        row = conn.execute(
            "SELECT gm_plan_json FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        if not row:
            return
        plan = json.loads(row["gm_plan_json"] if isinstance(row, sqlite3.Row) else row[0] or "{}")
        plan["selected_ending_id"] = ending_id
        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
            (json.dumps(plan, ensure_ascii=False), campaign_id),
        )
        conn.commit()
    except Exception as _err:
        logger.warning("store_selected_ending_failed", error=str(_err))


def _select_ending_id_llm(
    conn: sqlite3.Connection,
    campaign_id: int,
    plan: dict,
    camp,
) -> str | None:
    """Ask LLM to pick the best ending_id based on the last 15 turns.

    Returns None on any error so callers can fall back gracefully.
    """
    endings = plan.get("endings")
    if not endings:
        return None
    endings_list = list(endings.values()) if isinstance(endings, dict) else (
        endings if isinstance(endings, list) else []
    )
    if len(endings_list) <= 1:
        e = endings_list[0] if endings_list else None
        return str(e.get("id")) if isinstance(e, dict) and e.get("id") else None

    try:
        rows = conn.execute(
            "SELECT user_text, assistant_text FROM campaign_turns "
            "WHERE campaign_id = ? ORDER BY turn_number DESC LIMIT 15",
            (campaign_id,),
        ).fetchall()
    except Exception:
        return None
    rows = list(reversed(rows))
    turns_text = "\n".join(
        f"Gracz: {(r['user_text'] or '')[:200]}\nNarrator: {(r['assistant_text'] or '')[:200]}"
        for r in rows
    )
    endings_desc = "\n".join(
        f"- {e.get('id')}: \"{e.get('title')}\" — wymagania: {'; '.join(e.get('requirements', []))}"
        for e in endings_list if isinstance(e, dict)
    )
    prompt = (
        f"Ostatnie tury gry (chronologicznie):\n{turns_text}\n\n"
        f"Dostępne zakończenia kampanii:\n{endings_desc}\n\n"
        "Na podstawie faktycznych wydarzeń z ostatnich tur wybierz JEDNO zakończenie, "
        "które najlepiej pasuje do tego, co naprawdę się wydarzyło. "
        "Zwróć TYLKO id zakończenia, np. `ending_alternate`. Bez żadnego innego tekstu."
    )
    owner_id = int(camp["owner_user_id"]) if camp else 1
    model = str(camp["model_id"] or "").strip() if camp else ""
    llm_config = get_user_llm_settings_full(owner_id)
    model_resolved = (llm_config.get("model") or model or "").strip() or model
    messages = [
        {
            "role": "system",
            "content": "You are a game master assistant. Return only the ending_id string, nothing else.",
        },
        {"role": "user", "content": prompt},
    ]
    try:
        text = (generate_chat(messages=messages, model=model_resolved, llm_config=llm_config) or "").strip()
        valid_ids = {str(e.get("id")) for e in endings_list if isinstance(e, dict) and e.get("id")}
        for vid in valid_ids:
            if vid in text:
                return vid
    except Exception as e:
        logger.warning("ending_selection_llm_failed", error=str(e))
    return None


def generate_victory_epitaph_llm(
    *,
    name: str,
    arch: str,
    ending_title: str,
    ending_summary: str,
    recent_turns: str,
    model: str,
    llm_config: dict,
) -> str:
    """Generate a short (2-3 sentence) victory summary based on last turns + chosen ending."""
    prompt = (
        f"Napisz krótkie podsumowanie zakończenia (2–3 zdania) dla bohatera imieniem {name} ({arch}).\n"
        f"Tytuł zakończenia: {ending_title}\n"
        f"Opis zakończenia: {ending_summary}\n"
        f"Ostatnie zdarzenia:\n{recent_turns}\n\n"
        "Pisz po polsku, bez markdown. Klimat ciemnego fantasy. "
        "Opisz co faktycznie zaszło, nie tylko powtarzaj tytuł."
    )
    messages = [
        {
            "role": "system",
            "content": "Piszesz krótkie klimatyczne podsumowania zakończeń kampanii RPG. Zwykły tekst, bez markdown.",
        },
        {"role": "user", "content": prompt},
    ]
    try:
        text = (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip()
    except Exception as e:
        logger.warning("victory_epitaph_llm_failed", error=str(e))
        text = ""
    return text or f"{name} osiągnął kres swej przygody — {ending_title}."


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
    write_game_event(
        "player_death",
        int(campaign_id),
        int(character_row["id"]),
        int(character_row["user_id"] or 0) or None,
        {
            "cause": death_reason,
            "death_save_count": int((sheet or {}).get("death_save_count") or 0),
        },
        severity="warning",
    )
    return epitaph


def campaign_run_stats(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
) -> dict[str, int]:
    """E3/E4 (#418/#419) — summary stats for the end/death screen.

    Counts narrative turns, current gold, distinct NPCs met and completed
    quests. Each count is defensive — a missing table yields 0, never raises.
    """
    def _scalar(sql: str, args: tuple) -> int:
        try:
            row = conn.execute(sql, args).fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except Exception:
            return 0

    return {
        "turn_count": _scalar(
            "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ?", (campaign_id,)
        ),
        "gold": _scalar(
            "SELECT gold_gp FROM characters WHERE id = ?", (character_id,)
        ),
        "npcs_met": _scalar(
            "SELECT COUNT(*) FROM campaign_known_npcs WHERE campaign_id = ?", (campaign_id,)
        ),
        "quests_completed": _scalar(
            "SELECT COUNT(*) FROM character_quests WHERE campaign_id = ? AND completed_turn IS NOT NULL",
            (campaign_id,),
        ),
        # #1016 — side-quest breakdown for the end screen (X/Y zrobione).
        # X = side completed; Y = ALL side (completed + skipped + active);
        # skipped counts toward Y but never toward X (legal optional skip, #1011).
        "side_quests_completed": _scalar(
            "SELECT COUNT(*) FROM character_quests "
            "WHERE campaign_id = ? AND quest_type = 'side' AND status = 'completed'",
            (campaign_id,),
        ),
        "side_quests_total": _scalar(
            "SELECT COUNT(*) FROM character_quests "
            "WHERE campaign_id = ? AND quest_type = 'side'",
            (campaign_id,),
        ),
        "side_quests_skipped": _scalar(
            "SELECT COUNT(*) FROM character_quests "
            "WHERE campaign_id = ? AND quest_type = 'side' AND status = 'skipped'",
            (campaign_id,),
        ),
    }


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
        SELECT id, status, death_reason, ended_at, epitaph, gm_plan_json,
               model_id, owner_user_id
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

    arch = str(sheet.get("archetype") or sheet.get("class") or "adventurer").strip()
    level = sheet.get("level")
    if level is None and sheet.get("xp_lifetime_earned") is not None:
        from app.services.xp_service import get_xp_level_thresholds, level_from_xp
        try:
            thresholds = get_xp_level_thresholds(conn)
        except Exception:
            thresholds = None
        level = max(1, min(10, level_from_xp(int(sheet["xp_lifetime_earned"]), thresholds)))
    xp_lifetime = int(sheet.get("xp_lifetime_earned") or 0)

    # Pull ending title + summary from gm_plan_json for victory.
    # #1058: use selected_ending_id (stored on CAMPAIGN_END tag or from LLM selection)
    # instead of always picking endings[0].
    ending_title = ""
    ending_summary = ""
    ending_type = "primary"
    if outcome == "victory":
        try:
            plan = json.loads(camp["gm_plan_json"] or "{}")
        except Exception:
            plan = {}
        endings = plan.get("endings")
        ending_obj = None

        # 1. Use pre-stored ending_id if available (from [CAMPAIGN_END:id] tag)
        sel_id = plan.get("selected_ending_id")
        if sel_id:
            ending_obj = _find_ending_by_id(endings, sel_id)

        # 2. LLM-based selection — lazy, cached in gm_plan_json after first run
        if not ending_obj:
            selected_id = _select_ending_id_llm(conn, int(camp["id"]), plan, camp)
            if selected_id:
                ending_obj = _find_ending_by_id(endings, selected_id)
                if ending_obj:
                    _store_selected_ending(conn, int(camp["id"]), selected_id)

        # 3. Fall back to first primary-type ending (not just endings[0])
        if not ending_obj:
            ending_obj = _find_primary_type_ending(endings)

        if isinstance(ending_obj, dict):
            ending_title = str(ending_obj.get("title") or "")
            ending_summary = str(ending_obj.get("summary") or ending_obj.get("description") or "")
            ending_type = str(ending_obj.get("type") or "primary")

        # Generate victory epitaph on first load, cache in DB
        if not str(camp["epitaph"] or "").strip() and ending_title:
            try:
                rows = conn.execute(
                    "SELECT user_text, assistant_text FROM campaign_turns "
                    "WHERE campaign_id = ? ORDER BY turn_number DESC LIMIT 10",
                    (int(camp["id"]),),
                ).fetchall()
                recent_turns = "\n".join(
                    f"Gracz: {(r['user_text'] or '')[:150]}\nNarrator: {(r['assistant_text'] or '')[:150]}"
                    for r in reversed(rows)
                )
                owner_id = int(camp["owner_user_id"] or 1)
                model = str(camp["model_id"] or "").strip()
                llm_cfg = get_user_llm_settings_full(owner_id)
                model_resolved = (llm_cfg.get("model") or model or "").strip() or model
                victory_epitaph = generate_victory_epitaph_llm(
                    name=str(ch["name"] or "Bohater"),
                    arch=arch,
                    ending_title=ending_title,
                    ending_summary=ending_summary,
                    recent_turns=recent_turns,
                    model=model_resolved,
                    llm_config=llm_cfg,
                )
                if victory_epitaph:
                    conn.execute(
                        "UPDATE campaigns SET epitaph = ? WHERE id = ?",
                        (victory_epitaph, int(camp["id"])),
                    )
                    conn.commit()
            except Exception as _ep_err:
                logger.warning("victory_epitaph_generation_error", error=str(_ep_err))

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
        "ending_type": ending_type,  # #1058: 'primary'|'alternate' for tone label
        "secret": str(ident.get("secret") or ""),
        "bonds": bonds_out,
        # E3/E4 (#418/#419) — campaign run stats for the summary screen.
        "stats": campaign_run_stats(conn, int(camp["id"]), int(ch["id"])),
    }
