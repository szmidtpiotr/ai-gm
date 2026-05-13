"""
Ideas Workshop Router — Phase 08 Task 30

Admin endpoints for an AI-assisted campaign idea creation workshop.
The agent helps the admin build structured ideas and saves them to campaign_ideas.
"""

import json
import re
import sqlite3
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.services.admin_auth import verify_admin_token
from app.services.llm_service import generate_chat

DB_PATH = "/data/ai_gm.db"

router = APIRouter(prefix="/api/admin/ideas", tags=["admin-ideas-workshop"])

# ── In-memory session store ─────────────────────────────────────────────────

_sessions: dict[str, dict] = {}
SESSION_TTL_SECONDS = 3600  # 60 minutes


def _purge_expired() -> None:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["last_active"] > SESSION_TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]


def _get_or_create_session(session_id: str) -> dict:
    _purge_expired()
    if session_id not in _sessions:
        _sessions[session_id] = {
            "history": [],
            "draft": None,
            "category": None,
            "last_active": time.time(),
        }
    else:
        _sessions[session_id]["last_active"] = time.time()
    return _sessions[session_id]


# ── Auth ─────────────────────────────────────────────────────────────────────

def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


# ── Agent system prompt ───────────────────────────────────────────────────────

WORKSHOP_SYSTEM_PROMPT = """Jesteś kreatywnym asystentem projektowania kampanii do mrocznego fantasy RPG (WFRP-inspired).
Pomagasz administratorowi zbudować ustrukturyzowany pomysł do bazy danych gry.

TWOJE ZADANIE:
1. Zrozum pomysł admina (zadaj max 3 pytania, nie za dużo)
2. Wykryj kategorię: seed | scene_module | npc_concept | location | plot_twist | encounter
3. Zaproponuj ustrukturyzowany szkic w formacie JSON gdy już masz dość informacji
4. Dostosuj szkic na podstawie feedbacku
5. Gdy admin powie "zapisz" lub "zatwierdź" lub "save" — zwróć JSON z kluczem "READY_TO_SAVE": true i pełnym szkicem

TON: Kreatywny, entuzjastyczny, traktuj admina jak współautora.
ŚWIAT: Mroczna fantasy (WFRP-inspired) — grim, niebezpieczny, moralnie niejednoznaczny.

Format odpowiedzi:
- Zwykła rozmowa: po prostu odpowiedz naturalnie
- Gdy proponujesz szkic: zwróć ```json\n{...}\n``` blok z polami: category, title, premise/setup, i pozostałe pola zależne od kategorii
- Gdy gotowy do zapisu: zwróć {"READY_TO_SAVE": true, "draft": {...}}"""


# ── Draft extraction ──────────────────────────────────────────────────────────

def _extract_draft(text: str) -> tuple[Optional[dict], bool]:
    """
    Returns (draft_dict_or_None, ready_to_save).
    Tries to find JSON in ```json ... ``` block first,
    then tries to parse the whole text as JSON (for READY_TO_SAVE signal).
    """
    # Check for READY_TO_SAVE JSON object (may appear anywhere)
    ready_pattern = re.search(r'\{[^{}]*"READY_TO_SAVE"\s*:\s*true[^{}]*\}', text, re.DOTALL)
    if ready_pattern:
        try:
            obj = json.loads(ready_pattern.group(0))
            draft = obj.get("draft")
            return draft, True
        except json.JSONDecodeError:
            pass

    # Also try parsing as pure JSON (when whole reply IS the READY_TO_SAVE object)
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            obj = json.loads(stripped)
            if obj.get("READY_TO_SAVE"):
                return obj.get("draft"), True
        except json.JSONDecodeError:
            pass

    # Check for ```json ... ``` block
    code_block = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if code_block:
        try:
            obj = json.loads(code_block.group(1))
            if "category" in obj:
                return obj, False
        except json.JSONDecodeError:
            pass

    return None, False


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _idea_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "category": row["category"],
        "title": row["title"],
        "description": row["description"],
        "structured_data": json.loads(row["structured_data"] or "{}"),
        "tags": json.loads(row["tags"] or "[]"),
        "quality_rating": row["quality_rating"],
        "times_used": row["times_used"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "review_status": row["review_status"],
        "cooldown_hours": row["cooldown_hours"],
        "is_active": row["is_active"],
    }


# ── Request/response models ───────────────────────────────────────────────────

class WorkshopMessageReq(BaseModel):
    session_id: str
    message: str


class SaveIdeaReq(BaseModel):
    session_id: Optional[str] = None
    idea_data: Optional[dict] = None


class PatchIdeaReq(BaseModel):
    quality_rating: Optional[int] = None
    is_active: Optional[bool] = None
    title: Optional[str] = None
    review_status: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/workshop/message")
def workshop_message(
    req: WorkshopMessageReq,
    _: None = Depends(_require_admin),
):
    session = _get_or_create_session(req.session_id)

    # Append user message to history
    session["history"].append({"role": "user", "content": req.message})

    # Build full message list for LLM
    messages = [{"role": "system", "content": WORKSHOP_SYSTEM_PROMPT}] + session["history"]

    try:
        reply = generate_chat(messages=messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    # Append assistant reply to history
    session["history"].append({"role": "assistant", "content": reply})

    # Extract draft if present
    draft, ready_to_save = _extract_draft(reply)
    if draft and "category" in draft:
        session["draft"] = draft
        session["category"] = draft.get("category")

    return {
        "session_id": req.session_id,
        "reply": reply,
        "draft": session["draft"],
        "ready_to_save": ready_to_save,
    }


@router.post("/save")
def save_idea(
    req: SaveIdeaReq,
    _: None = Depends(_require_admin),
):
    # Determine idea_data: either directly provided or from session draft
    idea_data = req.idea_data
    if idea_data is None:
        if not req.session_id:
            raise HTTPException(status_code=400, detail="Provide session_id or idea_data")
        session = _sessions.get(req.session_id)
        if not session or not session.get("draft"):
            raise HTTPException(status_code=400, detail="No draft found for this session")
        idea_data = session["draft"]

    category = idea_data.get("category")
    title = idea_data.get("title")
    if not category:
        raise HTTPException(status_code=422, detail="idea_data must have 'category'")
    if not title:
        raise HTTPException(status_code=422, detail="idea_data must have 'title'")

    description = idea_data.get("description") or idea_data.get("premise") or idea_data.get("setup") or ""
    structured_data = json.dumps(idea_data)
    tags = json.dumps(idea_data.get("tags", []))

    conn = _get_db()
    try:
        cur = conn.execute(
            """
            INSERT INTO campaign_ideas
                (category, title, description, structured_data, tags, quality_rating,
                 review_status, created_by, is_active)
            VALUES (?, ?, ?, ?, ?, 0, 'draft', 'workshop', 1)
            """,
            (category, title, description, structured_data, tags),
        )
        conn.commit()
        idea_id = cur.lastrowid
    finally:
        conn.close()

    return {"ok": True, "id": idea_id}


@router.get("")
def list_ideas(
    category: Optional[str] = Query(default=None),
    min_rating: int = Query(default=0),
    active_only: bool = Query(default=True),
    _: None = Depends(_require_admin),
):
    conn = _get_db()
    try:
        conditions = ["quality_rating >= ?"]
        params: list = [min_rating]

        if active_only:
            conditions.append("is_active = 1")
        if category:
            conditions.append("category = ?")
            params.append(category)

        where = " AND ".join(conditions)
        rows = conn.execute(
            f"SELECT * FROM campaign_ideas WHERE {where} ORDER BY created_at DESC",
            params,
        ).fetchall()
        return {"items": [_idea_row_to_dict(r) for r in rows]}
    finally:
        conn.close()


@router.patch("/{idea_id}")
def patch_idea(
    idea_id: int,
    req: PatchIdeaReq,
    _: None = Depends(_require_admin),
):
    conn = _get_db()
    try:
        row = conn.execute("SELECT id FROM campaign_ideas WHERE id = ?", (idea_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Idea not found")

        updates: list[str] = []
        params: list = []

        if req.quality_rating is not None:
            updates.append("quality_rating = ?")
            params.append(req.quality_rating)
        if req.is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if req.is_active else 0)
        if req.title is not None:
            updates.append("title = ?")
            params.append(req.title)
        if req.review_status is not None:
            updates.append("review_status = ?")
            params.append(req.review_status)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(idea_id)
        conn.execute(
            f"UPDATE campaign_ideas SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM campaign_ideas WHERE id = ?", (idea_id,)).fetchone()
        return _idea_row_to_dict(updated)
    finally:
        conn.close()


@router.delete("/{idea_id}")
def delete_idea(
    idea_id: int,
    _: None = Depends(_require_admin),
):
    conn = _get_db()
    try:
        row = conn.execute("SELECT id FROM campaign_ideas WHERE id = ?", (idea_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Idea not found")
        conn.execute("UPDATE campaign_ideas SET is_active = 0 WHERE id = ?", (idea_id,))
        conn.commit()
        return {"ok": True, "id": idea_id}
    finally:
        conn.close()
