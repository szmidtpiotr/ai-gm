from pathlib import Path
import json
import sqlite3

from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel

from app.core.turn_engine import runnarrativeturn

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


def get_campaign_or_404(conn: sqlite3.Connection, campaign_id: int):
    campaign = conn.execute(
        "SELECT * FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def get_character_or_404(conn: sqlite3.Connection, campaign_id: int, character_id: int):
    character = conn.execute(
        "SELECT * FROM characters WHERE id = ? AND campaign_id = ?",
        (character_id, campaign_id),
    ).fetchone()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character


def create_turn_log(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int | None,
    user_text: str,
    assistant_text: str | None,
    route: str,
):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO campaign_turns (campaign_id, character_id, user_text, assistant_text, route) VALUES (?, ?, ?, ?, ?)",
        (campaign_id, character_id, user_text, assistant_text, route),
    )
    turn_id = cur.lastrowid
    row = cur.execute(
        "SELECT id, created_at FROM campaign_turns WHERE id = ?",
        (turn_id,),
    ).fetchone()
    conn.commit()
    return {
        "turn_number": row["id"],
        "created_at": row["created_at"],
    }


@router.get("/campaigns/{campaign_id}/turns")
def list_campaign_turns(campaign_id: int, limit: int = Query(default=30, ge=1, le=100)):
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
                t.assistant_text,
                t.route,
                t.created_at,
                c.name AS character_name
            FROM campaign_turns t
            LEFT JOIN characters c ON c.id = t.character_id
            WHERE t.campaign_id = ?
            ORDER BY t.id DESC
            LIMIT ?
            """,
            (campaign_id, limit),
        ).fetchall()

        turns = []
        for row in rows:
            turns.append(
                {
                    "id": row["id"],
                    "turn_number": row["id"],
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
                    raise HTTPException(status_code=400, detail="Character name is required")

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
                "turn_number": log["turn_number"],
                "created_at": log["created_at"],
                "route": "command",
                "result": result,
            }

        route = "narrative"
        model = payload.engine or campaign["model_id"] or "gemma3:4b"

        result = runnarrativeturn(
            conn=conn,
            campaign=campaign,
            character=character,
            usertext=text,
            model=model,
            ollamabaseurl=x_ollama_base_url,
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
            "turn_number": log["turn_number"],
            "created_at": log["created_at"],
            "route": "narrative",
            "result": result,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        conn.close()
        
        