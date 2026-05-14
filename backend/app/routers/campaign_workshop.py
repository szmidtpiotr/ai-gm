"""
Campaign Workshop Router — Phase 08 Task 31

Admin endpoints for an AI-assisted campaign improvement workshop.
The agent analyzes the current campaign plan + recent turns and proposes changes.
"""

import json
import re
import sqlite3
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.admin_auth import verify_admin_token
from app.services.llm_service import generate_chat

DB_PATH = "/data/ai_gm.db"

router = APIRouter(prefix="/api/admin/campaigns", tags=["admin-campaign-workshop"])

# ── In-memory session store ─────────────────────────────────────────────────

_sessions: dict[str, dict] = {}
SESSION_TTL_SECONDS = 3600  # 60 minutes


def _purge_expired() -> None:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["last_active"] > SESSION_TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]


def _get_or_create_session(session_id: str, campaign_id: int) -> dict:
    _purge_expired()
    if session_id not in _sessions:
        _sessions[session_id] = {
            "history": [],
            "proposed_changes": None,
            "campaign_id": campaign_id,
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

CAMPAIGN_WORKSHOP_SYSTEM_PROMPT = """Jesteś ekspertem od narracji RPG. Analizujesz bieżącą kampanię i pomagasz ją poprawić.
Masz dostęp do pełnego planu kampanii i ostatnich 10 tur.
Możesz proponować konkretne zmiany do planu — jako JSON diff obiekty: {"field": "...", "old_value": "...", "new_value": "...", "reason": "..."}.
Gdy proponujesz zmiany, umieść je w bloku ```json\n[{"field":..., "new_value":...}]\n```."""


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_campaign_context(campaign_id: int) -> dict:
    """Load campaign plan and last 10 turns for the given campaign."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT id, title, status, gm_plan_json FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")

        campaign_data = {
            "id": row["id"],
            "title": row["title"],
            "status": row["status"],
            "gm_plan": json.loads(row["gm_plan_json"] or "{}"),
        }

        turns = conn.execute(
            """
            SELECT turn_number, user_text, assistant_text, created_at
            FROM campaign_turns
            WHERE campaign_id = ?
            ORDER BY turn_number DESC
            LIMIT 10
            """,
            (campaign_id,),
        ).fetchall()

        campaign_data["recent_turns"] = [
            {
                "turn_number": t["turn_number"],
                "role": "player",
                "content": (t["user_text"] or "")[:400],
                "gm": (t["assistant_text"] or "")[:400],
                "created_at": t["created_at"],
            }
            for t in reversed(turns)
        ]

        return campaign_data
    finally:
        conn.close()


def _extract_proposed_changes(text: str) -> Optional[list]:
    """Extract a JSON array of proposed changes from a ```json ... ``` block."""
    code_block = re.search(r"```json\s*\n(\[.*?\])\s*\n```", text, re.DOTALL)
    if code_block:
        try:
            changes = json.loads(code_block.group(1))
            if isinstance(changes, list):
                return changes
        except json.JSONDecodeError:
            pass
    return None


def _apply_change_to_plan(plan: dict, change: dict) -> dict:
    """Apply a single change dict to the plan dict by field path."""
    field = change.get("field", "")
    new_value = change.get("new_value")

    # Support dot-notation field paths (e.g. "acts.0.title")
    parts = field.split(".")
    obj = plan
    for part in parts[:-1]:
        if isinstance(obj, dict):
            obj = obj.setdefault(part, {})
        elif isinstance(obj, list):
            try:
                obj = obj[int(part)]
            except (IndexError, ValueError):
                return plan
        else:
            return plan

    last = parts[-1]
    if isinstance(obj, dict):
        obj[last] = new_value
    elif isinstance(obj, list):
        try:
            obj[int(last)] = new_value
        except (IndexError, ValueError):
            pass

    return plan


# ── Request/response models ───────────────────────────────────────────────────

class WorkshopMessageReq(BaseModel):
    session_id: str
    message: str


class ApplyChangeReq(BaseModel):
    session_id: str
    change_index: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{campaign_id}/workshop/message")
def campaign_workshop_message(
    campaign_id: int,
    req: WorkshopMessageReq,
    _: None = Depends(_require_admin),
):
    session = _get_or_create_session(req.session_id, campaign_id)

    # Load campaign context for first message or refresh
    ctx = _load_campaign_context(campaign_id)
    context_block = (
        f"## Campaign: {ctx['title']} (status: {ctx['status']})\n\n"
        f"### GM Plan:\n{json.dumps(ctx['gm_plan'], ensure_ascii=False, indent=2)}\n\n"
        f"### Last 10 turns:\n"
        + "\n".join(
            f"[Turn {t['turn_number']}] Player: {t['content'][:200]} | GM: {t['gm'][:200]}"
            for t in ctx["recent_turns"]
        )
    )

    # Build messages: system + context injection + history + user message
    system_msg = {"role": "system", "content": CAMPAIGN_WORKSHOP_SYSTEM_PROMPT}
    context_msg = {"role": "user", "content": f"[KONTEKST KAMPANII]\n{context_block}"}
    context_ack = {"role": "assistant", "content": "Rozumiem. Mam dostęp do planu kampanii i ostatnich tur. Jak mogę pomóc?"}

    session["history"].append({"role": "user", "content": req.message})

    messages = [system_msg, context_msg, context_ack] + session["history"]

    try:
        reply = generate_chat(messages=messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    session["history"].append({"role": "assistant", "content": reply})

    proposed_changes = _extract_proposed_changes(reply)
    if proposed_changes is not None:
        session["proposed_changes"] = proposed_changes

    return {
        "session_id": req.session_id,
        "reply": reply,
        "proposed_changes": session.get("proposed_changes"),
    }


@router.post("/{campaign_id}/workshop/apply")
def campaign_workshop_apply(
    campaign_id: int,
    req: ApplyChangeReq,
    _: None = Depends(_require_admin),
):
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    changes = session.get("proposed_changes")
    if not changes:
        raise HTTPException(status_code=400, detail="No proposed changes in session")

    if req.change_index < 0 or req.change_index >= len(changes):
        raise HTTPException(status_code=400, detail=f"change_index out of range (0–{len(changes) - 1})")

    change = changes[req.change_index]

    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT gm_plan_json FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")

        plan = json.loads(row["gm_plan_json"] or "{}")
        plan = _apply_change_to_plan(plan, change)

        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
            (json.dumps(plan, ensure_ascii=False), campaign_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "applied_change": change}
