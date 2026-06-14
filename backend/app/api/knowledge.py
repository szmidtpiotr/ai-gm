"""KW3 — Player-facing knowledge tips endpoint."""
from __future__ import annotations
import sqlite3
from fastapi import APIRouter

router = APIRouter()
DB_PATH = "/data/ai_gm.db"

CATEGORY_ORDER = ["combat", "magic", "exploration", "mechanics", "general"]

@router.get("/knowledge-tips")
def list_knowledge_tips():
    """Return all active tips, ordered by category then sort_order."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(knowledge_book)").fetchall()}
        base = ["tip_key", "category", "title", "body", "sort_order"]
        for opt in ("icon", "related_command"):
            if opt in cols:
                base.append(opt)
        where = "is_active = 1"
        # #594: only player knowledge tips — exclude onboarding_card rows
        if "kind" in cols:
            where += " AND kind = 'knowledge_tip'"
        rows = conn.execute(
            f"SELECT {', '.join(base)} FROM knowledge_book WHERE {where} "
            "ORDER BY sort_order, tip_key"
        ).fetchall()
        return {"tips": [dict(r) for r in rows]}
    finally:
        conn.close()
