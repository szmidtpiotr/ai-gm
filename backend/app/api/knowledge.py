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
        rows = conn.execute(
            "SELECT tip_key, category, title, body, icon, related_command, sort_order "
            "FROM knowledge_book WHERE is_active = 1 ORDER BY sort_order, tip_key"
        ).fetchall()
        return {"tips": [dict(r) for r in rows]}
    except Exception:
        # icon/related_command columns may not exist yet on first request before migration
        rows = conn.execute(
            "SELECT tip_key, category, title, body, sort_order "
            "FROM knowledge_book WHERE is_active = 1 ORDER BY sort_order, tip_key"
        ).fetchall()
        return {"tips": [dict(r) for r in rows]}
    finally:
        conn.close()
