"""POST /mem — odpowiedzi z campaign_ai_summaries bez wpływu na narrację (route=memory)."""

import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.turns import (
    create_turn_log,
    get_campaign_or_404,
    get_db,
    log_memory_turn_structured,
)
from app.services.client_ui_config import is_slash_command_enabled
from app.services.history_summary_service import count_narrative_turns
from app.services.memory_qa_service import answer_from_summaries

router = APIRouter()

# Stage 9 P3 — Historia cooldown: /mem usable once per N narrative turns per campaign.
# Counter lives in game_sessions.session_flags["historia_last_turn"] (number of
# narrative turns at last successful /mem call). Admin users bypass.
HISTORIA_COOLDOWN_TURNS = 20


def _is_admin(conn, user_id: int) -> bool:
    try:
        r = conn.execute("SELECT is_admin FROM users WHERE id = ?", (int(user_id),)).fetchone()
        return bool(r and int(r[0] or 0) == 1)
    except Exception:
        return False


def _load_session_flags(conn, campaign_id: int) -> tuple[dict, str]:
    """Return (flags, session_id_str). Session row keyed on str(campaign_id)."""
    sid = str(campaign_id)
    row = conn.execute("SELECT session_flags FROM game_sessions WHERE id = ?", (sid,)).fetchone()
    if not row:
        return {}, sid
    try:
        return (json.loads(row["session_flags"] or "{}") or {}), sid
    except Exception:
        return {}, sid


def _save_session_flags(conn, sid: str, flags: dict) -> None:
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
        (json.dumps(flags, ensure_ascii=False), sid),
    )
    conn.commit()


class MemoryAskBody(BaseModel):
    character_id: int = Field(..., ge=1)
    question: str = Field(..., min_length=1)
    """Treść pytania (bez prefiksu /mem)."""
    user_line: str | None = Field(
        default=None,
        description="Pełna linia z czatu (np. '/mem Kto był w karczmie?') do zapisu w turze.",
    )


@router.post("/campaigns/{campaign_id}/memory/ask")
def post_memory_ask(
    campaign_id: int,
    body: MemoryAskBody,
    user_id: int = Query(..., description="Właściciel kampanii — spójnie z LLM."),
):
    if not is_slash_command_enabled("/mem [pytanie]"):
        raise HTTPException(
            status_code=403,
            detail="Komenda /mem jest wyłączona przez administratora.",
        )

    conn = get_db()
    try:
        camp = get_campaign_or_404(conn, campaign_id)
        if int(camp["owner_user_id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="user_id must match campaign owner")
        # Stage 9 P3 — historia cooldown. Admin bypasses.
        if not _is_admin(conn, user_id):
            narrative_n = count_narrative_turns(conn, campaign_id)
            flags, sid = _load_session_flags(conn, campaign_id)
            last = int(flags.get("historia_last_turn") or 0)
            turns_since = max(0, narrative_n - last)
            if last > 0 and turns_since < HISTORIA_COOLDOWN_TURNS:
                remaining = HISTORIA_COOLDOWN_TURNS - turns_since
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "historia_cooldown",
                        "message": f"Pamięć potrzebuje czasu. Spróbuj za {remaining} tur.",
                        "turns_remaining": remaining,
                        "turns_since_last": turns_since,
                        "cooldown_turns": HISTORIA_COOLDOWN_TURNS,
                    },
                )
    finally:
        conn.close()

    try:
        out = answer_from_summaries(
            campaign_id=campaign_id,
            user_id=user_id,
            question=body.question.strip(),
            model=str(camp["model_id"] or "").strip() or None,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    except Exception as e:
        # JSON decode, bugs, etc. — always return JSON detail (avoids generic HTTP 500 + empty body)
        raise HTTPException(status_code=502, detail=f"Memory QA failed: {e}") from None

    user_text = (body.user_line or "").strip() or f"/mem {body.question.strip()}"

    conn = get_db()
    try:
        # Sprawdź, że postać należy do kampanii
        ch = conn.execute(
            "SELECT id FROM characters WHERE id = ? AND campaign_id = ?",
            (body.character_id, campaign_id),
        ).fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail="Character not found in this campaign")

        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=body.character_id,
            user_text=user_text,
            assistant_text=out["answer"],
            route="memory",
        )
        log_memory_turn_structured(
            campaign_id=campaign_id,
            character_id=body.character_id,
            turn_row=log,
            user_text=user_text,
            assistant_text=out["answer"],
        )
        # Stage 9 P3 — stamp the cooldown anchor. Skip for admin so they keep
        # bypassing on subsequent calls (consistent with the gate check above).
        if not _is_admin(conn, user_id):
            flags, sid = _load_session_flags(conn, campaign_id)
            flags["historia_last_turn"] = count_narrative_turns(conn, campaign_id)
            _save_session_flags(conn, sid, flags)
    finally:
        conn.close()

    return {
        "answer": out["answer"],
        "source": out.get("source"),
        "used_llm": out.get("used_llm", False),
        "id": log["id"],
        "campaign_id": campaign_id,
        "turn_number": log["turn_number"],
        "created_at": log["created_at"],
        "route": "memory",
    }
