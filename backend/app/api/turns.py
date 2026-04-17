import json
import logging
import os
import re
import sqlite3

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.dice import (
    format_roll_result_message,
    parse_character_sheet,
    parse_roll_command,
    resolve_test_name,
    resolve_roll,
)
from app.services.game_engine import build_narrative_messages, run_narrative_turn
from app.services.llm_service import generate_chat_stream, get_effective_config, get_health
from app.services.user_llm_settings import get_user_llm_settings_full

router = APIRouter()
DB_PATH = "/data/ai_gm.db"
logger = logging.getLogger(__name__)


def _truncate_for_story_log(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + "…[truncated]"


def log_narrative_turn_structured(
    *,
    route: str,
    campaign_id: int,
    character_id: int | None,
    turn_row: dict,
    user_text: str,
    assistant_text: str,
) -> None:
    """
    Emit one JSON log line (via root JsonFormatter) for Loki/Grafana — near-live story
    without syncing SQLite to the observability VM. Disable with NARRATIVE_STORY_LOG=0.

    Optional: NARRATIVE_LOG_MAX_CHARS caps user_text / assistant_text size (0 = no cap).
    """
    if route != "narrative":
        return
    if os.getenv("NARRATIVE_STORY_LOG", "1").strip().lower() in ("0", "false", "no"):
        return
    try:
        max_chars = int(os.getenv("NARRATIVE_LOG_MAX_CHARS", "0") or "0")
    except ValueError:
        max_chars = 0
    try:
        logger.info(
            "narrative_turn",
            extra={
                "extra_fields": {
                    "event": "narrative_turn",
                    "campaign_id": campaign_id,
                    "character_id": character_id,
                    "turn_id": turn_row.get("id"),
                    "turn_number": turn_row.get("turn_number"),
                    "created_at": turn_row.get("created_at"),
                    "user_text": _truncate_for_story_log(user_text or "", max_chars),
                    "assistant_text": _truncate_for_story_log(assistant_text or "", max_chars),
                }
            },
        )
    except Exception:
        # Never fail a turn because logging broke
        pass


def log_memory_turn_structured(
    *,
    campaign_id: int,
    character_id: int | None,
    turn_row: dict,
    user_text: str,
    assistant_text: str,
) -> None:
    """Emit JSON log line for /mem turns (Loki: event=memory_turn). Same opt-out as narrative."""
    if os.getenv("NARRATIVE_STORY_LOG", "1").strip().lower() in ("0", "false", "no"):
        return
    try:
        max_chars = int(os.getenv("NARRATIVE_LOG_MAX_CHARS", "0") or "0")
    except ValueError:
        max_chars = 0
    try:
        logger.info(
            "memory_turn",
            extra={
                "extra_fields": {
                    "event": "memory_turn",
                    "campaign_id": campaign_id,
                    "character_id": character_id,
                    "turn_id": turn_row.get("id"),
                    "turn_number": turn_row.get("turn_number"),
                    "created_at": turn_row.get("created_at"),
                    "user_text": _truncate_for_story_log(user_text or "", max_chars),
                    "assistant_text": _truncate_for_story_log(assistant_text or "", max_chars),
                }
            },
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Command registry — used by /help and the command dispatcher
# ---------------------------------------------------------------------------
COMMAND_REGISTRY = {
    "/help": "Show this list of available commands",
    "/sheet": "Display your full character sheet",
    "/roll": "Roll d20 + modifier for the last GM-requested roll",
    "/name <new name>": "Rename your character",
    "/history": "Show the last 10 turns of the session",
    "/mem [pytanie]": "Pytanie o przeszłość z podsumowań — bez wpływu na narrację (żółte dymki)",
    "/export": "Export the full session to a text file on the server (/data/exports/)",
}


class TurnCreate(BaseModel):
    character_id: int
    text: str
    system: str | None = None
    engine: str | None = None
    game_id: int | None = None


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def validate_roll_cue_name(assistant_text: str) -> str | None:
    lines = (assistant_text or "").splitlines()
    if not lines:
        return None
    last_line = (lines[-1] or "").strip()
    cue_match = re.match(r"^Roll (.+?) (d\d+)$", last_line, re.I)
    if not cue_match:
        return None
    raw_test_name = (cue_match.group(1) or "").strip()
    canonical = resolve_test_name(raw_test_name)
    if canonical is None:
        logger.warning("Unknown LLM roll cue test name ignored: %s", raw_test_name)
    return canonical


def resolve_model_name(
    requested_model: str | None,
    campaign_model: str | None,
    llm_config: dict[str, str] | None = None,
) -> str:
    effective = get_effective_config(llm_config)
    if effective["provider"] == "openai":
        return (requested_model or campaign_model or effective["model"]).strip()

    health = get_health(llm_config)
    available = health.get("models") or []
    if not available:
        return (requested_model or campaign_model or effective["model"]).strip()
    if requested_model and requested_model in available:
        return requested_model
    if campaign_model and campaign_model in available:
        return campaign_model
    if effective["model"] in available:
        return effective["model"]
    return available[0]


def get_campaign_or_404(conn: sqlite3.Connection, campaign_id: int):
    campaign = conn.execute(
        "SELECT * FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def get_character_or_404(
    conn: sqlite3.Connection, campaign_id: int, character_id: int
):
    character = conn.execute(
        "SELECT * FROM characters WHERE id = ? AND campaign_id = ?",
        (character_id, campaign_id),
    ).fetchone()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character


def get_next_turn_number(conn: sqlite3.Connection, campaign_id: int) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(turn_number), 0) AS max_turn
        FROM campaign_turns
        WHERE campaign_id = ?
        """,
        (campaign_id,),
    ).fetchone()
    return int(row["max_turn"] or 0) + 1


def create_turn_log(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int | None,
    user_text: str,
    assistant_text: str | None,
    route: str,
):
    cur = conn.cursor()
    turn_number = get_next_turn_number(conn, campaign_id)

    cur.execute(
        """
        INSERT INTO campaign_turns (
            campaign_id,
            character_id,
            user_text,
            route,
            assistant_text,
            turn_number
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (campaign_id, character_id, user_text, route, assistant_text, turn_number),
    )

    turn_id = cur.lastrowid

    row = cur.execute(
        """
        SELECT id, campaign_id, turn_number, created_at
        FROM campaign_turns
        WHERE id = ?
        """,
        (turn_id,),
    ).fetchone()

    conn.commit()

    return {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "turn_number": row["turn_number"],
        "created_at": row["created_at"],
    }


# ---------------------------------------------------------------------------
# Helper: export session to text file
# ---------------------------------------------------------------------------

def _export_session_to_file(conn: sqlite3.Connection, campaign_id: int) -> str:
    """Writes all turns for campaign_id to /data/exports/campaign_<id>_<ts>.txt"""
    import time

    rows = conn.execute(
        """
        SELECT turn_number, user_text, assistant_text, created_at
        FROM campaign_turns
        WHERE campaign_id = ?
        ORDER BY turn_number ASC
        """,
        (campaign_id,),
    ).fetchall()

    campaign = conn.execute(
        "SELECT title, system_id FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()

    export_dir = "/data/exports"
    os.makedirs(export_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    filename = f"{export_dir}/campaign_{campaign_id}_{ts}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        title = campaign["title"] if campaign else f"Campaign {campaign_id}"
        system = campaign["system_id"] if campaign else "unknown"
        f.write(f"=== {title} [{system}] ===\n")
        f.write(f"Exported: {ts}\n")
        f.write("=" * 60 + "\n\n")

        for row in rows:
            f.write(f"[Turn {row['turn_number']}] {row['created_at']}\n")
            f.write(f"PLAYER: {row['user_text']}\n")
            if row["assistant_text"]:
                f.write(f"GM:     {row['assistant_text']}\n")
            f.write("\n")

    return filename


# ---------------------------------------------------------------------------
# GET turns list
# ---------------------------------------------------------------------------

@router.get("/campaigns/{campaign_id}/turns")
def list_campaign_turns(
    campaign_id: int, limit: int = Query(default=30, ge=1, le=100)
):
    conn = get_db()
    try:
        get_campaign_or_404(conn, campaign_id)

        rows = conn.execute(
            """
            SELECT
                t.id,
                t.campaign_id,
                t.character_id,
                t.user_text,
                t.route,
                t.assistant_text,
                t.created_at,
                t.turn_number,
                c.name AS character_name
                ,c.user_id AS character_user_id
            FROM campaign_turns t
            LEFT JOIN characters c ON c.id = t.character_id
            WHERE t.campaign_id = ?
            ORDER BY t.turn_number DESC
            LIMIT ?
            """,
            (campaign_id, limit),
        ).fetchall()

        turns = []
        for row in rows:
            turns.append(
                {
                    "id": row["id"],
                    "turn_number": row["turn_number"],
                    "campaign_id": row["campaign_id"],
                    "character_id": row["character_id"],
                    "character_name": row["character_name"],
                    "character_user_id": row["character_user_id"],
                    "user_text": row["user_text"],
                    "assistant_text": row["assistant_text"],
                    "route": row["route"],
                    "created_at": row["created_at"],
                }
            )

        turns.reverse()

        return {
            "campaign_id": campaign_id,
            "turns": turns,
            "count": len(turns),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Export session endpoint
# ---------------------------------------------------------------------------

@router.post("/campaigns/{campaign_id}/export")
def export_session(campaign_id: int):
    """Exports the full session to a .txt file under /data/exports/"""
    conn = get_db()
    try:
        get_campaign_or_404(conn, campaign_id)
        filepath = _export_session_to_file(conn, campaign_id)
        return {"status": "ok", "file": filepath}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# POST turn (non-streaming)
# ---------------------------------------------------------------------------

@router.post("/campaigns/{campaign_id}/turns")
def create_turn(
    campaign_id: int,
    payload: TurnCreate,
    x_ollama_base_url: str | None = Header(default=None),
):
    conn = get_db()
    try:
        campaign = get_campaign_or_404(conn, campaign_id)
        character = get_character_or_404(conn, campaign_id, payload.character_id)
        llm_config = get_user_llm_settings_full(character["user_id"])
        text = (payload.text or "").strip()

        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        roll_request = parse_roll_command(text)
        roll_result_message = None
        roll_result_data = None
        if roll_request:
            character_sheet = parse_character_sheet(character["sheet_json"])
            roll_result = resolve_roll(
                character_sheet=character_sheet,
                test_name=roll_request["skill"],
                raw_roll=roll_request.get("raw_roll"),
            )
            roll_result_data = roll_result
            roll_result_message = format_roll_result_message(roll_result)

        if text.startswith("/") and not roll_request:
            route = "command"
            cmd = text.split(" ", 1)[0].lower()

            # /help
            if cmd == "/help":
                result = {
                    "command": "help",
                    "commands": COMMAND_REGISTRY,
                }
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return {**log, "route": "command", "result": result}

            # /name
            if cmd == "/name":
                new_name = text[5:].strip()
                if not new_name:
                    raise HTTPException(status_code=400, detail="Character name is required")
                conn.execute(
                    "UPDATE characters SET name = ? WHERE id = ? AND campaign_id = ?",
                    (new_name, payload.character_id, campaign_id),
                )
                conn.commit()
                result = {"command": "name", "character_name": new_name}
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return {**log, "route": "command", "result": result}

            # /sheet
            if cmd == "/sheet":
                result = {
                    "command": "sheet",
                    "character": {
                        "id": character["id"],
                        "name": character["name"],
                        "campaign_id": character["campaign_id"],
                        "user_id": character["user_id"],
                        "system_id": character["system_id"],
                        "sheet_json": character["sheet_json"],
                        "location": character["location"],
                        "is_active": character["is_active"],
                        "created_at": character["created_at"],
                    },
                }
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return {**log, "route": "command", "result": result}

            # /history
            if cmd == "/history":
                rows = conn.execute(
                    """
                    SELECT turn_number, user_text, assistant_text, created_at
                    FROM campaign_turns
                    WHERE campaign_id = ?
                    ORDER BY turn_number DESC
                    LIMIT 10
                    """,
                    (campaign_id,),
                ).fetchall()
                history = [
                    {
                        "turn": r["turn_number"],
                        "player": r["user_text"],
                        "gm": r["assistant_text"],
                        "at": r["created_at"],
                    }
                    for r in reversed(rows)
                ]
                result = {"command": "history", "turns": history}
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return {**log, "route": "command", "result": result}

            # /export
            if cmd == "/export":
                filepath = _export_session_to_file(conn, campaign_id)
                result = {"command": "export", "file": filepath}
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return {**log, "route": "command", "result": result}

            # Unknown command
            result = {"command": cmd, "message": f"Unknown command '{cmd}'. Type /help for a list."}
            log = create_turn_log(
                conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
            )
            return {**log, "route": "command", "result": result}

        route = "narrative"
        model = resolve_model_name(
            requested_model=payload.engine,
            campaign_model=campaign["model_id"],
            llm_config=llm_config,
        )

        result = run_narrative_turn(
            conn=conn,
            campaign=campaign,
            character=character,
            user_text=text,
            model=model,
            ollama_base_url=x_ollama_base_url,
            llm_config=llm_config,
            roll_result_message=roll_result_message,
            roll_result_data=roll_result_data,
        )

        assistant_text = (result.get("message") or "").strip()
        if not assistant_text:
            raise HTTPException(status_code=500, detail="Empty narrative response")
        validate_roll_cue_name(assistant_text)

        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            user_text=roll_result_message or text,
            assistant_text=assistant_text,
            route=route,
        )
        log_narrative_turn_structured(
            route=route,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            turn_row=log,
            user_text=roll_result_message or text,
            assistant_text=assistant_text,
        )

        return {
            "id": log["id"],
            "campaign_id": log["campaign_id"],
            "turn_number": log["turn_number"],
            "created_at": log["created_at"],
            "route": "narrative",
            "result": result,
        }

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# POST turn streaming (SSE)
# ---------------------------------------------------------------------------

@router.post("/campaigns/{campaign_id}/turns/stream")
def create_turn_stream(
    campaign_id: int,
    payload: TurnCreate,
    x_ollama_base_url: str | None = Header(default=None),
):
    """
    Streaming version of the turn endpoint.
    Returns a text/event-stream (SSE) response.
    Each chunk: 'data: <token>\\n\\n'
    Final chunk: 'data: [DONE]\\n\\n'
    The full assembled text is saved to campaign_turns after streaming completes.
    """
    conn = get_db()
    try:
        campaign = get_campaign_or_404(conn, campaign_id)
        character = get_character_or_404(conn, campaign_id, payload.character_id)
        llm_config = get_user_llm_settings_full(character["user_id"])
        text = (payload.text or "").strip()

        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        roll_request = parse_roll_command(text)
        roll_result_message = None
        roll_result_data = None
        if roll_request:
            character_sheet = parse_character_sheet(character["sheet_json"])
            roll_result = resolve_roll(
                character_sheet=character_sheet,
                test_name=roll_request["skill"],
                raw_roll=roll_request.get("raw_roll"),
            )
            roll_result_data = roll_result
            roll_result_message = format_roll_result_message(roll_result)

        # Commands are not streamed (except /roll, which is turned into a narrative input)
        if text.startswith("/") and not roll_request:
            def command_stream():
                yield f"data: [CMD] {text}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(command_stream(), media_type="text/event-stream")

        model = resolve_model_name(
            requested_model=payload.engine,
            campaign_model=campaign["model_id"],
            llm_config=llm_config,
        )

        llm_user_text = roll_result_message or text
        messages = build_narrative_messages(
            conn=conn,
            campaign=campaign,
            character=character,
            user_text=text,
            roll_result_message=roll_result_message,
            roll_result_data=roll_result_data,
        )

        campaign_id_val = campaign_id
        character_id_val = payload.character_id
        user_text_val = llm_user_text

        def token_generator():
            collected = []
            for chunk in generate_chat_stream(
                messages=messages,
                model=model,
                llm_config=llm_config,
            ):
                if chunk.startswith("data: [DONE]"):
                    full_text = "".join(collected).replace("\\n", "\n")
                    if full_text.strip():
                        validate_roll_cue_name(full_text.strip())
                        save_conn = get_db()
                        try:
                            stream_log = create_turn_log(
                                conn=save_conn,
                                campaign_id=campaign_id_val,
                                character_id=character_id_val,
                                user_text=user_text_val,
                                assistant_text=full_text.strip(),
                                route="narrative",
                            )
                            log_narrative_turn_structured(
                                route="narrative",
                                campaign_id=campaign_id_val,
                                character_id=character_id_val,
                                turn_row=stream_log,
                                user_text=user_text_val,
                                assistant_text=full_text.strip(),
                            )
                        finally:
                            save_conn.close()
                    yield chunk
                elif chunk.startswith("data: [ERROR]"):
                    yield chunk
                else:
                    token = chunk[6:].rstrip("\n")
                    collected.append(token)
                    yield chunk

        return StreamingResponse(
            token_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        conn.close()
