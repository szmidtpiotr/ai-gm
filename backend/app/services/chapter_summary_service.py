"""J2 — Chapter summary generator for character_campaign_history.

On campaign close (death / victory / abandonment) this service:
  1. Ensures a character_campaign_history row exists for the outcome.
  2. Generates a 2-paragraph, first-person, Polish chapter summary via LLM.
  3. Stores the result in character_campaign_history.chapter_summary.

The LLM call runs in a daemon thread so it never blocks the turn response.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Literal

import structlog

from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full

logger = structlog.get_logger()

DB_PATH = "/data/ai_gm.db"

Outcome = Literal["death", "victory", "abandoned"]

_OUTCOME_LABEL = {
    "death": "śmierć",
    "victory": "zwycięstwo",
    "abandoned": "porzucona",
}


# ── Internal helpers ───────────────────────────────────────────────────────────

def _open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_last_turns(conn: sqlite3.Connection, campaign_id: int, limit: int = 25) -> str:
    """Return the last N narrative turns as a compact transcript."""
    rows = conn.execute(
        """
        SELECT user_text, assistant_text, turn_number
        FROM campaign_turns
        WHERE campaign_id = ? AND route IN ('narrative', 'skill_check', 'combat')
        ORDER BY turn_number DESC
        LIMIT ?
        """,
        (campaign_id, limit),
    ).fetchall()
    rows = list(reversed(rows))
    if not rows:
        return "(brak tur)"
    parts: list[str] = []
    for r in rows:
        user = (r["user_text"] or "").strip()[:120]
        gm   = (r["assistant_text"] or "").strip()[:250]
        if user or gm:
            parts.append(f"Gracz: {user}\nGM: {gm}")
    return "\n---\n".join(parts)


def _fetch_character_info(conn: sqlite3.Connection, character_id: int) -> dict:
    row = conn.execute(
        "SELECT name, sheet_json FROM characters WHERE id = ?",
        (character_id,),
    ).fetchone()
    if not row:
        return {"name": "Bohater", "archetype": "poszukiwacz przygód"}
    try:
        sheet = json.loads(row["sheet_json"] or "{}")
    except Exception:
        sheet = {}
    arch = str(sheet.get("archetype") or sheet.get("class") or "poszukiwacz przygód").strip()
    return {"name": str(row["name"] or "Bohater"), "archetype": arch}


def _build_prompt(name: str, archetype: str, outcome: Outcome, transcript: str) -> str:
    outcome_pl = _OUTCOME_LABEL.get(outcome, outcome)
    return (
        f"Jesteś pisarzem kroniki drużyny RPG. Napisz podsumowanie rozdziału dla postaci.\n\n"
        f"Bohater: {name} ({archetype})\n"
        f"Zakończenie: {outcome_pl}\n\n"
        f"Fragment przygody (ostatnie tury):\n{transcript}\n\n"
        f"Napisz 2 akapity w pierwszej osobie, w czasie przeszłym, PO POLSKU. "
        f"Bohater wspomina co się wydarzyło — kluczowe momenty, emocje, decyzje. "
        f"Łącznie 130–200 słów. Styl: mroczne fantasy, osobisty pamiętnik. "
        f"Zacznij od imienia lub emocji — nie od słowa 'Ja'. Żadnych nagłówków ani markdown."
    )


def _call_llm(name: str, archetype: str, outcome: Outcome,
              campaign_id: int, user_id: int) -> str:
    conn = _open_db()
    try:
        transcript = _fetch_last_turns(conn, campaign_id)
    finally:
        conn.close()

    prompt = _build_prompt(name, archetype, outcome, transcript)
    messages = [
        {"role": "system", "content": "Piszesz pamiętniki bohaterów gry RPG. Tylko czysty tekst, bez nagłówków."},
        {"role": "user", "content": prompt},
    ]
    llm_config = get_user_llm_settings_full(user_id)
    try:
        text = (generate_chat(messages=messages, llm_config=llm_config) or "").strip()
    except Exception as e:
        logger.warning("chapter_summary_llm_failed", error=str(e), campaign_id=campaign_id)
        text = ""
    return text


# ── Public API ─────────────────────────────────────────────────────────────────

def ensure_history_row(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
    outcome: Outcome,
    xp_earned: int = 0,
    gold_at_end: int = 0,
    turns_count: int = 0,
) -> int:
    """Insert or return existing character_campaign_history row id."""
    existing = conn.execute(
        "SELECT id FROM character_campaign_history WHERE character_id = ? AND campaign_id = ?",
        (character_id, campaign_id),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE character_campaign_history
            SET outcome = ?, xp_earned = ?, gold_at_end = ?, turns_count = ?,
                completed_at = COALESCE(completed_at, datetime('now'))
            WHERE id = ?
            """,
            (outcome, xp_earned, gold_at_end, turns_count, int(existing["id"])),
        )
        conn.commit()
        return int(existing["id"])

    cur = conn.execute(
        """
        INSERT INTO character_campaign_history
          (character_id, campaign_id, outcome, xp_earned, gold_at_end, turns_count, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (character_id, campaign_id, outcome, xp_earned, gold_at_end, turns_count),
    )
    conn.commit()
    return int(cur.lastrowid)


def _update_chapter_summary(history_id: int, summary: str) -> None:
    conn = _open_db()
    try:
        conn.execute(
            "UPDATE character_campaign_history SET chapter_summary = ? WHERE id = ?",
            (summary, history_id),
        )
        conn.commit()
        logger.info("chapter_summary_saved", history_id=history_id, length=len(summary))
    except Exception as e:
        logger.warning("chapter_summary_save_failed", history_id=history_id, error=str(e))
    finally:
        conn.close()


def schedule_chapter_summary(
    *,
    history_id: int,
    campaign_id: int,
    character_id: int,
    outcome: Outcome,
    user_id: int,
) -> None:
    """Fire-and-forget: generate chapter summary in a daemon thread."""
    def _worker():
        conn = _open_db()
        try:
            info = _fetch_character_info(conn, character_id)
        finally:
            conn.close()

        summary = _call_llm(
            name=info["name"],
            archetype=info["archetype"],
            outcome=outcome,
            campaign_id=campaign_id,
            user_id=user_id,
        )
        if summary:
            _update_chapter_summary(history_id, summary)

    t = threading.Thread(target=_worker, daemon=True, name=f"chapter-summary-{campaign_id}")
    t.start()


def get_hero_chronicle(
    conn: sqlite3.Connection,
    character_id: int,
    *,
    limit: int = 3,
) -> str:
    """#1096 — Read hero's campaign history as a formatted chronicle block.

    Returns a Polish text block with the last `limit` campaign summaries,
    or empty string if no completed campaigns exist for this character.
    """
    try:
        rows = conn.execute(
            """
            SELECT cch.outcome, cch.chapter_summary, cch.turns_count,
                   cch.completed_at, c.title
            FROM character_campaign_history cch
            LEFT JOIN campaigns c ON c.id = cch.campaign_id
            WHERE cch.character_id = ?
              AND cch.outcome IN ('victory', 'death', 'abandoned')
              AND cch.chapter_summary IS NOT NULL
              AND cch.chapter_summary != ''
            ORDER BY cch.completed_at DESC
            LIMIT ?
            """,
            (character_id, limit),
        ).fetchall()
    except Exception:
        # campaigns table may not exist in test DBs without it
        try:
            rows = conn.execute(
                """
                SELECT cch.outcome, cch.chapter_summary, cch.turns_count,
                       cch.completed_at, NULL as title
                FROM character_campaign_history cch
                WHERE cch.character_id = ?
                  AND cch.outcome IN ('victory', 'death', 'abandoned')
                  AND cch.chapter_summary IS NOT NULL
                  AND cch.chapter_summary != ''
                ORDER BY cch.completed_at DESC
                LIMIT ?
                """,
                (character_id, limit),
            ).fetchall()
        except Exception:
            return ""

    if not rows:
        return ""

    _outcome_pl = {"victory": "zwycięstwo", "death": "śmierć", "abandoned": "porzucona"}
    parts: list[str] = []
    for i, r in enumerate(reversed(list(rows)), start=1):
        outcome_pl = _outcome_pl.get(str(r["outcome"] or ""), str(r["outcome"] or ""))
        title = str(r["title"] or "Poprzednia kampania").strip()
        summary = str(r["chapter_summary"] or "").strip()
        parts.append(f"Rozdział {i} — {title} [{outcome_pl}]:\n{summary}")

    return (
        "=== KRONIKA BOHATERA (poprzednie kampanie) ===\n"
        + "\n\n".join(parts)
        + "\n=== KONIEC KRONIKI ==="
    )


def close_campaign_with_summary(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
    outcome: Outcome,
    user_id: int,
    xp_earned: int = 0,
    gold_at_end: int = 0,
    turns_count: int = 0,
) -> None:
    """Ensure history row exists and queue async chapter summary generation.

    Call this immediately after marking a campaign ended/completed/abandoned.
    Safe to call multiple times (idempotent on the history row).
    """
    history_id = ensure_history_row(
        conn,
        campaign_id=campaign_id,
        character_id=character_id,
        outcome=outcome,
        xp_earned=xp_earned,
        gold_at_end=gold_at_end,
        turns_count=turns_count,
    )
    schedule_chapter_summary(
        history_id=history_id,
        campaign_id=campaign_id,
        character_id=character_id,
        outcome=outcome,
        user_id=user_id,
    )
    logger.info(
        "chapter_summary_scheduled",
        campaign_id=campaign_id,
        character_id=character_id,
        outcome=outcome,
        history_id=history_id,
    )
