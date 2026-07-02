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


_OUTCOME_PL_FULL = {"victory": "zwycięstwo", "death": "śmierć", "abandoned": "porzucona"}

# #1096 — Hero Legend: cap the flattened whole-life digest so token cost stays
# constant no matter how many campaigns a hero survives. Starting value.
LEGEND_DIGEST_TARGET_WORDS = 300

# #1096 (1B) — abandonment scar: only campaigns played for at least this many
# narrative turns leave an "unfinished business" note. Below it (misclick / test
# campaign) nothing is written. Starting value, tunable.
ABANDON_MIN_TURNS = 5
# Short scar — a faint reputation mark, not a full chapter. Starting value.
ABANDON_NOTE_TARGET_WORDS = 70


def _row_get(row, key):
    """Safe column access — returns None when the column is absent (older schema)."""
    try:
        return row[key]
    except Exception:
        return None


def should_generate_abandonment_note(narrative_turns: int) -> bool:
    """#1096 (1B) — gate: only campaigns with enough play leave a scar."""
    try:
        return int(narrative_turns) >= ABANDON_MIN_TURNS
    except Exception:
        return False


def _build_abandonment_prompt(name: str, campaign_title: str, transcript: str) -> str:
    """LLM prompt for a short 'unfinished business' scar (reputation mark)."""
    return (
        f"Jesteś kronikarzem legend. Bohater {name} PORZUCIŁ przygodę "
        f"„{campaign_title}” — odszedł, nie kończąc zadań.\n\n"
        f"Fragment tego, co zdążyło się wydarzyć:\n{transcript}\n\n"
        f"Napisz KRÓTKĄ notkę (~{ABANDON_NOTE_TARGET_WORDS} słów, PO POLSKU, "
        f"trzecia osoba) o tym, co bohater zostawił NIEDOKOŃCZONE i kogo tym ZAWIÓDŁ "
        f"— porzucone zadania, złamane obietnice, NPC/miejsca, które zapamiętają jego "
        f"odejście. To rysa na reputacji, nie triumf. Bez nagłówków ani markdown."
    )


def _generate_abandonment_note_text(
    name: str, campaign_title: str, transcript: str, user_id: int
) -> str:
    """Call the LLM to produce the abandonment scar note (empty string on failure)."""
    prompt = _build_abandonment_prompt(name, campaign_title, transcript)
    messages = [
        {"role": "system", "content": "Piszesz kroniki bohaterów gry RPG. Tylko czysty tekst, bez nagłówków."},
        {"role": "user", "content": prompt},
    ]
    llm_config = get_user_llm_settings_full(user_id)
    try:
        return (generate_chat(messages=messages, llm_config=llm_config) or "").strip()
    except Exception as e:
        logger.warning("abandonment_note_llm_failed", error=str(e))
        return ""


def _update_abandonment_note(history_id: int, note: str) -> None:
    conn = _open_db()
    try:
        conn.execute(
            "UPDATE character_campaign_history SET abandonment_note = ? WHERE id = ?",
            (note, history_id),
        )
        conn.commit()
        logger.info("abandonment_note_saved", history_id=history_id, length=len(note))
    except Exception as e:
        logger.warning("abandonment_note_save_failed", history_id=history_id, error=str(e))
    finally:
        conn.close()


def schedule_abandonment_note(
    *,
    history_id: int,
    name: str,
    campaign_title: str,
    transcript: str,
    user_id: int,
) -> None:
    """Fire-and-forget: generate the abandonment scar in a daemon thread.

    The transcript is captured BY THE CALLER before campaign_turns are deleted,
    so this is self-contained and does not read the (soon-gone) turns table.
    """
    def _worker():
        note = _generate_abandonment_note_text(name, campaign_title, transcript, user_id)
        if note:
            _update_abandonment_note(history_id, note)

    t = threading.Thread(target=_worker, daemon=True, name=f"abandon-note-{history_id}")
    t.start()


def _count_completed_chapters(conn: sqlite3.Connection, character_id: int) -> int:
    """Number of finished campaigns with a chapter summary for this hero."""
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM character_campaign_history
            WHERE character_id = ?
              AND outcome IN ('victory', 'death', 'abandoned')
              AND chapter_summary IS NOT NULL
              AND chapter_summary != ''
            """,
            (character_id,),
        ).fetchone()
        return int(row["n"] if row else 0)
    except Exception:
        return 0


def _fetch_recent_chapters(
    conn: sqlite3.Connection, character_id: int, limit: int
) -> list[sqlite3.Row]:
    """Last `limit` finished chapters (newest first). Handles DBs without `campaigns`."""
    try:
        return conn.execute(
            """
            SELECT cch.outcome, cch.chapter_summary, cch.completed_at, c.title
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
        try:
            return conn.execute(
                """
                SELECT cch.outcome, cch.chapter_summary, cch.completed_at,
                       NULL AS title
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
            return []


def _read_legend_digest(conn: sqlite3.Connection, character_id: int) -> str:
    """Cached whole-life legend digest, or '' when absent / column missing."""
    try:
        row = conn.execute(
            "SELECT legend_digest FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        return str((row["legend_digest"] if row else "") or "").strip()
    except Exception:
        return ""


def _count_legend_sources(conn: sqlite3.Connection, character_id: int) -> int:
    """#1096 (1B) — chapters (victory/death) PLUS abandonment scars that feed the
    legend. Used for lazy staleness so a new scar also triggers a re-fold."""
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM character_campaign_history
            WHERE character_id = ?
              AND outcome IN ('victory', 'death', 'abandoned')
              AND ( (chapter_summary  IS NOT NULL AND chapter_summary  != '')
                 OR (abandonment_note IS NOT NULL AND abandonment_note != '') )
            """,
            (character_id,),
        ).fetchone()
        return int(row["n"] if row else 0)
    except Exception:
        # older schema without abandonment_note
        return _count_completed_chapters(conn, character_id)


def _fetch_legend_sources(conn: sqlite3.Connection, character_id: int) -> list[sqlite3.Row]:
    """All legend inputs (chapters + abandonment scars), oldest → newest."""
    try:
        return conn.execute(
            """
            SELECT outcome, chapter_summary, abandonment_note, completed_at
            FROM character_campaign_history
            WHERE character_id = ?
              AND outcome IN ('victory', 'death', 'abandoned')
              AND ( (chapter_summary  IS NOT NULL AND chapter_summary  != '')
                 OR (abandonment_note IS NOT NULL AND abandonment_note != '') )
            ORDER BY completed_at ASC
            """,
            (character_id,),
        ).fetchall()
    except Exception:
        # older schema — fall back to chapter summaries only (oldest → newest)
        return list(reversed(_fetch_recent_chapters(conn, character_id, limit=9999)))


def _build_legend_prompt(name: str, sources: list[sqlite3.Row]) -> str:
    """LLM prompt that folds ALL chapters + abandonment scars into one bounded legend."""
    lines: list[str] = []
    for i, r in enumerate(sources, start=1):
        outcome_pl = _OUTCOME_PL_FULL.get(str(r["outcome"] or ""), str(r["outcome"] or ""))
        summary = str(_row_get(r, "chapter_summary") or "").strip()
        note = str(_row_get(r, "abandonment_note") or "").strip()
        if summary:
            lines.append(f"Kampania {i} [{outcome_pl}]: {summary}")
        elif note:
            lines.append(f"Kampania {i} [PORZUCONA — niedokończone]: {note}")
    transcript = "\n\n".join(lines)
    return (
        f"Jesteś kronikarzem legend. Oto kroniki WSZYSTKICH przygód bohatera {name} "
        f"(od najstarszej do najnowszej). Kampanie oznaczone [PORZUCONA] to zadania, "
        f"od których bohater odszedł — potraktuj je jako RYSY na reputacji.\n\n"
        f"{transcript}\n\n"
        f"Napisz zwięzłą LEGENDĘ tego bohatera — spłaszczone streszczenie CAŁEGO życia. "
        f"NIE gub wczesnych wydarzeń: zachowaj reputację (także złą), powracających NPC, "
        f"wrogów, sojuszników, kluczowe łuki, konsekwencje decyzji ORAZ niedokończone "
        f"sprawy z porzuconych wypraw. Pomiń drobiazgi. "
        f"Maksymalnie ~{LEGEND_DIGEST_TARGET_WORDS} słów, PO POLSKU, proza w trzeciej osobie. "
        f"Bez nagłówków ani markdown."
    )


def refresh_hero_legend(
    conn: sqlite3.Connection,
    character_id: int,
    user_id: int,
) -> str:
    """#1096 — Lazily (re)generate the hero's flattened whole-life legend digest.

    Cheap-guarded: only calls the LLM when the stored digest is stale
    (legend_digest_count != number of finished chapters). Returns the digest
    (possibly the existing cached one). Safe when the character has no history.
    """
    sources_count = _count_legend_sources(conn, character_id)
    if sources_count == 0:
        return ""

    try:
        row = conn.execute(
            "SELECT name, legend_digest, legend_digest_count FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
    except Exception:
        return ""
    if not row:
        return ""

    cur_digest = str((row["legend_digest"] or "")).strip()
    try:
        cur_count = int(row["legend_digest_count"] or 0)
    except Exception:
        cur_count = 0

    # Fresh — nothing changed since last fold.
    if cur_digest and cur_count == sources_count:
        return cur_digest

    name = str(row["name"] or "Bohater")
    sources = _fetch_legend_sources(conn, character_id)  # oldest → newest
    if not sources:
        return cur_digest

    prompt = _build_legend_prompt(name, sources)
    messages = [
        {"role": "system", "content": "Piszesz legendy bohaterów gry RPG. Tylko czysty tekst, bez nagłówków."},
        {"role": "user", "content": prompt},
    ]
    llm_config = get_user_llm_settings_full(user_id)
    try:
        digest = (generate_chat(messages=messages, llm_config=llm_config) or "").strip()
    except Exception as e:
        logger.warning("hero_legend_llm_failed", error=str(e), character_id=character_id)
        return cur_digest

    if not digest:
        return cur_digest

    try:
        conn.execute(
            "UPDATE characters SET legend_digest = ?, legend_digest_count = ? WHERE id = ?",
            (digest, sources_count, character_id),
        )
        conn.commit()
        logger.info("hero_legend_refreshed", character_id=character_id, chapters=sources_count)
    except Exception as e:
        logger.warning("hero_legend_save_failed", error=str(e), character_id=character_id)
    return digest


def get_hero_chronicle(
    conn: sqlite3.Connection,
    character_id: int,
    *,
    limit: int = 2,
    user_id: int | None = None,
    regenerate: bool = False,
) -> str:
    """#1096 — Two-tier hero chronicle for cross-campaign continuity.

    Tier 1 (LEGENDA): cached, flattened whole-life digest — keeps early
    campaigns alive no matter how many a hero survives (bounded tokens).
    Tier 2 (OSTATNIE ROZDZIAŁY): the last `limit` chapter summaries verbatim.

    READ-ONLY by default (no LLM) — safe to call every narrator turn.
    Plan-generation paths pass `regenerate=True` + `user_id` to lazily refresh
    the digest first. Returns '' when the hero has no history.
    """
    if regenerate and user_id is not None:
        try:
            refresh_hero_legend(conn, character_id, user_id)
        except Exception as e:
            logger.warning("hero_chronicle_regen_failed", error=str(e), character_id=character_id)

    digest = _read_legend_digest(conn, character_id)
    recent = _fetch_recent_chapters(conn, character_id, limit)

    if not digest and not recent:
        return ""

    parts: list[str] = []
    if digest:
        parts.append("=== LEGENDA BOHATERA (całe życie) ===\n" + digest)

    if recent:
        verbatim: list[str] = []
        for i, r in enumerate(reversed(list(recent)), start=1):
            outcome_pl = _OUTCOME_PL_FULL.get(str(r["outcome"] or ""), str(r["outcome"] or ""))
            title = str(r["title"] or "Poprzednia kampania").strip()
            summary = str(r["chapter_summary"] or "").strip()
            verbatim.append(f"Rozdział {i} — {title} [{outcome_pl}]:\n{summary}")
        parts.append("=== OSTATNIE ROZDZIAŁY (szczegóły) ===\n" + "\n\n".join(verbatim))

    return "\n\n".join(parts) + "\n=== KONIEC KRONIKI ==="


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
    # #1099 — apply the regional reputation delta for this outcome (victory raises,
    # death dents). Abandonment is handled at delete_campaign. Best-effort.
    try:
        from app.services import reputation_service as rep
        rep.apply_campaign_outcome(conn, character_id, campaign_id, outcome)
    except Exception as _rep_err:
        logger.warning("reputation_outcome_failed", error=str(_rep_err))
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
