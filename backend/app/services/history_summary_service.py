"""Build campaign transcript from SQLite and call LLM for summary text."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.history_summary_prompt_loader import HISTORY_SUMMARY_PROMPT_TEXT
from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full


DB_PATH = "/data/ai_gm.db"


def _fetch_campaign(conn: sqlite3.Connection, campaign_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, title, system_id, model_id, owner_user_id, language, mode, status, created_at
        FROM campaigns WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()
    return dict(row) if row else None


def count_narrative_turns(conn: sqlite3.Connection, campaign_id: int) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM campaign_turns
        WHERE campaign_id = ? AND route = 'narrative'
        """,
        (campaign_id,),
    ).fetchone()
    return int(row["n"] or 0) if row else 0


def fetch_narrative_turns(
    conn: sqlite3.Connection, campaign_id: int, max_turns: int
) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT turn_number, user_text, assistant_text, created_at
        FROM campaign_turns
        WHERE campaign_id = ? AND route = 'narrative'
        ORDER BY turn_number DESC
        LIMIT ?
        """,
        (campaign_id, max_turns),
    ).fetchall()
    return list(reversed(rows))


def format_transcript(turns: list[sqlite3.Row], campaign_title: str, language: str) -> str:
    lines = [
        f"Kampania: {campaign_title}",
        f"Język (meta): {language}",
        "",
        "--- Transkrypt (tylko tury narracyjne) ---",
        "",
    ]
    for t in turns:
        un = (t["user_text"] or "").strip()
        an = (t["assistant_text"] or "").strip()
        lines.append(f"[Tura {t['turn_number']}] ({t['created_at']})")
        lines.append(f"Gracz: {un}")
        lines.append(f"MG: {an}")
        lines.append("")
    return "\n".join(lines)


def generate_campaign_summary(
    *,
    campaign_id: int,
    user_id: int,
    max_turns: int = 200,
) -> dict[str, Any]:
    """
    user_id must match campaigns.owner_user_id (caller enforced in router).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        camp = _fetch_campaign(conn, campaign_id)
        if not camp:
            raise ValueError("campaign_not_found")
        turns = fetch_narrative_turns(conn, campaign_id, max_turns)
        if not turns:
            return {
                "summary": "",
                "model_used": "",
                "included_turn_count": 0,
                "warning": "Brak tur narracyjnych do podsumowania.",
            }

        transcript = format_transcript(turns, camp["title"] or f"Kampania {campaign_id}", camp["language"] or "pl")
        llm_config = get_user_llm_settings_full(user_id)
        model = (camp.get("model_id") or "").strip() or None

        messages = [
            {"role": "system", "content": HISTORY_SUMMARY_PROMPT_TEXT},
            {
                "role": "user",
                "content": transcript,
            },
        ]
        summary = generate_chat(messages, model=model, llm_config=llm_config).strip()
        return {
            "summary": summary,
            "model_used": model or llm_config.get("model", ""),
            "included_turn_count": len(turns),
        }
    finally:
        conn.close()


def persist_summary(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    summary_text: str,
    model_used: str | None,
    included_turn_count: int,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO campaign_ai_summaries (campaign_id, summary_text, model_used, included_turn_count)
        VALUES (?, ?, ?, ?)
        """,
        (campaign_id, summary_text, model_used or "", included_turn_count),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def fetch_latest_saved_summary(conn: sqlite3.Connection, campaign_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, campaign_id, summary_text, model_used, included_turn_count, created_at
        FROM campaign_ai_summaries
        WHERE campaign_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (campaign_id,),
    ).fetchone()
    return dict(row) if row else None
