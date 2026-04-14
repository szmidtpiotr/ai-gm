import json
import os
import sqlite3

import requests
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.turn_engine import buildmessages, loadrecentturns, runnarrativeturn
from app.services.ollama_service import generatechat_stream

router = APIRouter()
DB_PATH = "/data/ai_gm.db"


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


def get_ollama_base_url(override: str | None = None) -> str:
    return (override or os.getenv("OLLAMA_BASE_URL") or "http://ollama:11434").rstrip("/")


def get_available_model_names(ollama_base_url: str) -> list[str]:
    try:
        response = requests.get(f"{ollama_base_url}/api/tags", timeout=10)
        response.raise_for_status()
        data = response.json()
        models = data.get("models") or []
        return [m.get("name") for m in models if m.get("name")]
    except requests.RequestException as e:
        raise RuntimeError(f"Could not fetch Ollama models from {ollama_base_url}: {e}")


def resolve_model_name(
    requested_model: str | None,
    campaign_model: str | None,
    ollama_base_url: str,
) -> str:
    available = get_available_model_names(ollama_base_url)

    if not available:
        raise RuntimeError("No Ollama models are installed")

    if requested_model and requested_model in available:
        return requested_model

    if campaign_model and campaign_model in available:
        return campaign_model

    preferred = [
        "gemma4:e4b",
        "gemma3:4b",
        "gemma3:1b",
    ]

    for model_name in preferred:
        if model_name in available:
            return model_name

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
        text = (payload.text or "").strip()

        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        if text.startswith("/"):
            route = "command"

            if text.startswith("/name"):
                new_name = text[5:].strip()
                if not new_name:
                    raise HTTPException(
                        status_code=400, detail="Character name is required"
                    )

                conn.execute(
                    "UPDATE characters SET name = ? WHERE id = ? AND campaign_id = ?",
                    (new_name, payload.character_id, campaign_id),
                )
                conn.commit()

                result = {
                    "command": "name",
                    "character_name": new_name,
                }

                log = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=text,
                    assistant_text=json.dumps(result, ensure_ascii=False),
                    route=route,
                )

                return {
                    "id": log["id"],
                    "campaign_id": log["campaign_id"],
                    "turn_number": log["turn_number"],
                    "created_at": log["created_at"],
                    "route": "command",
                    "result": result,
                }

            if text == "/sheet":
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
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=text,
                    assistant_text=json.dumps(result, ensure_ascii=False),
                    route=route,
                )

                return {
                    "id": log["id"],
                    "campaign_id": log["campaign_id"],
                    "turn_number": log["turn_number"],
                    "created_at": log["created_at"],
                    "route": "command",
                    "result": result,
                }

            result = {
                "command": text.split(" ", 1)[0],
                "message": "Unknown command",
            }

            log = create_turn_log(
                conn=conn,
                campaign_id=campaign_id,
                character_id=payload.character_id,
                user_text=text,
                assistant_text=json.dumps(result, ensure_ascii=False),
                route=route,
            )

            return {
                "id": log["id"],
                "campaign_id": log["campaign_id"],
                "turn_number": log["turn_number"],
                "created_at": log["created_at"],
                "route": "command",
                "result": result,
            }

        route = "narrative"
        ollama_base_url = get_ollama_base_url(x_ollama_base_url)

        model = resolve_model_name(
            requested_model=payload.engine,
            campaign_model=campaign["model_id"],
            ollama_base_url=ollama_base_url,
        )

        result = runnarrativeturn(
            conn=conn,
            campaign=campaign,
            character=character,
            usertext=text,
            model=model,
            ollamabaseurl=ollama_base_url,
        )

        assistant_text = (result.get("message") or "").strip()
        if not assistant_text:
            raise HTTPException(status_code=500, detail="Empty narrative response")

        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            user_text=text,
            assistant_text=assistant_text,
            route=route,
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

    The full assembled text is also saved to campaign_turns after streaming completes.
    NOTE: Since we need to collect the full text to save it, we buffer internally
    and yield tokens as they arrive.
    """
    conn = get_db()
    try:
        campaign = get_campaign_or_404(conn, campaign_id)
        character = get_character_or_404(conn, campaign_id, payload.character_id)
        text = (payload.text or "").strip()

        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        # Commands are not streamed — return immediately as JSON-in-SSE
        if text.startswith("/"):
            def command_stream():
                yield f"data: [CMD] {text}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(command_stream(), media_type="text/event-stream")

        ollama_base_url = get_ollama_base_url(x_ollama_base_url)
        model = resolve_model_name(
            requested_model=payload.engine,
            campaign_model=campaign["model_id"],
            ollama_base_url=ollama_base_url,
        )

        recent_turns = loadrecentturns(conn, campaign_id, limit=8)
        messages = buildmessages(
            campaign=campaign,
            character=character,
            recentturns=recent_turns,
            usertext=text,
        )

        # We need a fresh connection for the post-stream DB write
        # because the generator runs after this function returns
        campaign_id_val = campaign_id
        character_id_val = payload.character_id
        user_text_val = text

        def token_generator():
            collected = []
            for chunk in generatechat_stream(model=model, messages=messages, base_url=ollama_base_url):
                if chunk.startswith("data: [DONE]"):
                    # Save the full text to DB
                    full_text = "".join(collected).replace("\\n", "\n")
                    if full_text.strip():
                        save_conn = get_db()
                        try:
                            create_turn_log(
                                conn=save_conn,
                                campaign_id=campaign_id_val,
                                character_id=character_id_val,
                                user_text=user_text_val,
                                assistant_text=full_text.strip(),
                                route="narrative",
                            )
                        finally:
                            save_conn.close()
                    yield chunk
                elif chunk.startswith("data: [ERROR]"):
                    yield chunk
                else:
                    # Extract the token from 'data: <token>\n\n'
                    token = chunk[6:].rstrip("\n")
                    collected.append(token)
                    yield chunk

        return StreamingResponse(
            token_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        conn.close()
