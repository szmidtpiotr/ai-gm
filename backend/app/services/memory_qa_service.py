"""Answer /mem questions using campaign_ai_summaries — J4: cross-campaign search."""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Any

from app.memory_qa_prompt_loader import MEMORY_QA_PROMPT_TEXT
from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full

DB_PATH = "/data/ai_gm.db"

_GM_DOES_NOT_REMEMBER = (
    "Nie przypominam sobie tego szczegółu — w zapisanym podsumowaniu nic takiego nie mam. "
    "Jeśli to było w grze, minęło mi przez głowę bez śladu."
)

_OUTCOME_LABEL = {"death": "Śmierć", "victory": "Zwycięstwo", "abandoned": "Porzucona", "active": "Aktywna"}


def _fetch_summary_corpus(conn: sqlite3.Connection, campaign_id: int) -> str:
    """Single-campaign corpus (legacy path, kept for direct callers)."""
    rows = conn.execute(
        """
        SELECT id, summary_text, created_at
        FROM campaign_ai_summaries
        WHERE campaign_id = ? AND IFNULL(audience, 'player') = 'player'
        ORDER BY id ASC
        """,
        (campaign_id,),
    ).fetchall()
    if not rows:
        return ""
    parts = []
    max_chars = int(os.getenv("MEM_QA_MAX_SUMMARY_CHARS", "48000") or "48000")
    total = 0
    for r in rows:
        chunk = f"--- Podsumowanie #{r['id']} ({r['created_at']}) ---\n{r['summary_text'] or ''}\n"
        if total + len(chunk) > max_chars:
            remain = max_chars - total
            if remain > 200:
                parts.append(chunk[:remain] + "\n…[ucięte MEM_QA_MAX_SUMMARY_CHARS]")
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n".join(parts).strip()


def _fetch_cross_campaign_corpus(
    conn: sqlite3.Connection, character_id: int, current_campaign_id: int
) -> str:
    """J4 — Corpus spanning ALL campaigns this character participated in.

    Order: oldest completed campaigns first, active current campaign last.
    Each campaign block is labeled so the LLM can cite which campaign a fact is from.
    """
    # All campaign_ids this character has history rows for
    history_rows = conn.execute(
        """
        SELECT h.campaign_id, h.outcome, c.title
        FROM character_campaign_history h
        LEFT JOIN campaigns c ON c.id = h.campaign_id
        WHERE h.character_id = ?
        ORDER BY h.id ASC
        """,
        (character_id,),
    ).fetchall()

    # Build ordered list: past campaigns from history, then current if not already in list
    seen_ids: list[int] = []
    campaign_meta: dict[int, dict] = {}
    for row in history_rows:
        cid = int(row["campaign_id"])
        if cid not in campaign_meta:
            seen_ids.append(cid)
        campaign_meta[cid] = {
            "title": row["title"] or f"Kampania #{cid}",
            "outcome": _OUTCOME_LABEL.get(str(row["outcome"] or ""), str(row["outcome"] or "")),
        }
    if current_campaign_id not in campaign_meta:
        seen_ids.append(current_campaign_id)
        c_row = conn.execute("SELECT title FROM campaigns WHERE id = ?", (current_campaign_id,)).fetchone()
        campaign_meta[current_campaign_id] = {
            "title": (c_row["title"] if c_row else None) or f"Kampania #{current_campaign_id}",
            "outcome": "Aktywna",
        }

    max_chars = int(os.getenv("MEM_QA_MAX_SUMMARY_CHARS", "48000") or "48000")
    parts: list[str] = []
    total = 0

    for cid in seen_ids:
        meta = campaign_meta[cid]
        header = f"=== {meta['title']} ({meta['outcome']}) ===\n"
        sum_rows = conn.execute(
            """
            SELECT id, summary_text, created_at
            FROM campaign_ai_summaries
            WHERE campaign_id = ? AND IFNULL(audience, 'player') = 'player'
            ORDER BY id ASC
            """,
            (cid,),
        ).fetchall()
        if not sum_rows:
            continue
        block_parts = [header]
        for r in sum_rows:
            chunk = f"--- Podsumowanie #{r['id']} ({r['created_at']}) ---\n{r['summary_text'] or ''}\n"
            if total + len(header) + len(chunk) > max_chars:
                remain = max_chars - total - len(header)
                if remain > 200:
                    block_parts.append(chunk[:remain] + "\n…[ucięte]")
                    total = max_chars
                break
            block_parts.append(chunk)
            total += len(chunk)
        parts.append("".join(block_parts))
        if total >= max_chars:
            break

    return "\n".join(parts).strip()


def answer_from_summaries(
    *,
    campaign_id: int,
    user_id: int,
    question: str,
    model: str | None = None,
    character_id: int | None = None,
) -> dict[str, Any]:
    """J4: when character_id is provided, corpus spans all campaigns for that character."""
    q = (question or "").strip()
    if not q:
        return {"answer": _GM_DOES_NOT_REMEMBER, "source": "empty_question", "used_llm": False}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if character_id:
            corpus = _fetch_cross_campaign_corpus(conn, character_id, campaign_id)
            source_label = "cross_campaign"
        else:
            corpus = _fetch_summary_corpus(conn, campaign_id)
            source_label = "single_campaign"
    finally:
        conn.close()

    if not corpus.strip():
        return {
            "answer": _GM_DOES_NOT_REMEMBER,
            "source": "no_summaries",
            "used_llm": False,
        }

    llm_config = get_user_llm_settings_full(user_id)
    user_block = (
        f"PODSUMOWANIA / ZAPISY (jedyne źródło faktów):\n\n{corpus}\n\n"
        f"PYTANIE GRACZA:\n{q}"
    )
    messages = [
        {"role": "system", "content": MEMORY_QA_PROMPT_TEXT},
        {"role": "user", "content": user_block},
    ]
    raw = generate_chat(messages=messages, model=model, llm_config=llm_config).strip()
    compact = re.sub(r"\s+", " ", raw).strip()
    cu = compact.upper()
    if cu in ("NIE PAMIĘTAM", "NIE PAMIĘTAM.") or cu.startswith("NIE PAMIĘTAM"):
        return {"answer": _GM_DOES_NOT_REMEMBER, "source": "llm_unknown", "used_llm": True}
    return {"answer": raw, "source": source_label, "used_llm": True}
