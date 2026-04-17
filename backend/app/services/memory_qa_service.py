"""Answer /mem questions using only campaign_ai_summaries text (phase 1)."""

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


def _fetch_summary_corpus(conn: sqlite3.Connection, campaign_id: int) -> str:
    rows = conn.execute(
        """
        SELECT id, summary_text, created_at
        FROM campaign_ai_summaries
        WHERE campaign_id = ?
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


def answer_from_summaries(
    *,
    campaign_id: int,
    user_id: int,
    question: str,
    model: str | None = None,
) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        return {"answer": _GM_DOES_NOT_REMEMBER, "source": "empty_question", "used_llm": False}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        corpus = _fetch_summary_corpus(conn, campaign_id)
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
    return {"answer": raw, "source": "llm_summary", "used_llm": True}
