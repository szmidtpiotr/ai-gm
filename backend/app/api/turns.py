from pathlib import Path
import json
import sqlite3

from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel

from app.core.turn_engine import runnarrativeturn

router = APIRouter()
DBPATH = Path("data/ai-gm.db")


class TurnCreate(BaseModel):
    characterid: int
    text: str
    system: str | None = None
    engine: str | None = None
    gameid: int | None = None


def getdb():
    conn = sqlite3.connect(DBPATH)
    conn.row_factory = sqlite3.Row
    return conn


def getcampaignor404(conn: sqlite3.Connection, campaignid: int):
    campaign = conn.execute(
        "SELECT * FROM campaigns WHERE id = ?",
        (campaignid,),
    ).fetchone()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def getcharacteror404(conn: sqlite3.Connection, campaignid: int, characterid: int):
    character = conn.execute(
        "SELECT * FROM characters WHERE id = ? AND campaignid = ?",
        (characterid, campaignid),
    ).fetchone()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character


def createturnlog(
    conn: sqlite3.Connection,
    campaignid: int,
    characterid: int | None,
    usertext: str,
    assistanttext: str | None,
    route: str,
):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO campaignturns (campaignid, characterid, usertext, assistanttext, route) VALUES (?, ?, ?, ?, ?)",
        (campaignid, characterid, usertext, assistanttext, route),
    )
    turnid = cur.lastrowid
    row = cur.execute(
        "SELECT id, createdat FROM campaignturns WHERE id = ?",
        (turnid,),
    ).fetchone()
    conn.commit()
    return {
        "turnnumber": row["id"],
        "createdat": row["createdat"],
    }


@router.get("/campaigns/{campaignid}/turns")
def listcampaignturns(campaignid: int, limit: int = Query(default=30, ge=1, le=100)):
    conn = getdb()
    try:
        getcampaignor404(conn, campaignid)
        rows = conn.execute(
            """
            SELECT
                t.id,
                t.campaignid,
                t.characterid,
                t.usertext,
                t.assistanttext,
                t.route,
                t.createdat,
                c.name AS charactername
            FROM campaignturns t
            LEFT JOIN characters c ON c.id = t.characterid
            WHERE t.campaignid = ?
            ORDER BY t.id DESC
            LIMIT ?
            """,
            (campaignid, limit),
        ).fetchall()

        turns = []
        for row in rows:
            turns.append(
                {
                    "id": row["id"],
                    "turnnumber": row["id"],
                    "campaignid": row["campaignid"],
                    "characterid": row["characterid"],
                    "charactername": row["charactername"],
                    "usertext": row["usertext"],
                    "assistanttext": row["assistanttext"],
                    "route": row["route"],
                    "createdat": row["createdat"],
                }
            )

        turns.reverse()
        return {
            "campaignid": campaignid,
            "turns": turns,
            "count": len(turns),
        }
    finally:
        conn.close()


@router.post("/campaigns/{campaignid}/turns")
def createturn(
    campaignid: int,
    payload: TurnCreate,
    x_ollama_base_url: str | None = Header(default=None),
):
    conn = getdb()
    try:
        campaign = getcampaignor404(conn, campaignid)
        character = getcharacteror404(conn, campaignid, payload.characterid)
        text = (payload.text or "").strip()

        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        if text.startswith("/"):
            route = "command"

            if text.startswith("/name"):
                newname = text[5:].strip()
                if not newname:
                    raise HTTPException(status_code=400, detail="Character name is required")

                conn.execute(
                    "UPDATE characters SET name = ? WHERE id = ? AND campaignid = ?",
                    (newname, payload.characterid, campaignid),
                )
                conn.commit()

                result = {
                    "command": "name",
                    "charactername": newname,
                }
                log = createturnlog(
                    conn=conn,
                    campaignid=campaignid,
                    characterid=payload.characterid,
                    usertext=text,
                    assistanttext=json.dumps(result, ensure_ascii=False),
                    route=route,
                )
                return {
                    "turnnumber": log["turnnumber"],
                    "createdat": log["createdat"],
                    "route": "command",
                    "result": result,
                }

            if text == "/sheet":
                result = {
                    "command": "sheet",
                    "character": {
                        "id": character["id"],
                        "name": character["name"],
                        "campaignid": character["campaignid"],
                        "userid": character["userid"],
                        "systemid": character["systemid"],
                        "sheetjson": character["sheetjson"],
                        "location": character["location"],
                        "isactive": character["isactive"],
                        "createdat": character["createdat"],
                    },
                }
                log = createturnlog(
                    conn=conn,
                    campaignid=campaignid,
                    characterid=payload.characterid,
                    usertext=text,
                    assistanttext=json.dumps(result, ensure_ascii=False),
                    route=route,
                )
                return {
                    "turnnumber": log["turnnumber"],
                    "createdat": log["createdat"],
                    "route": "command",
                    "result": result,
                }

            result = {
                "command": text.split(" ", 1)[0],
                "message": "Unknown command",
            }
            log = createturnlog(
                conn=conn,
                campaignid=campaignid,
                characterid=payload.characterid,
                usertext=text,
                assistanttext=json.dumps(result, ensure_ascii=False),
                route=route,
            )
            return {
                "turnnumber": log["turnnumber"],
                "createdat": log["createdat"],
                "route": "command",
                "result": result,
            }

        route = "narrative"
        model = payload.engine or campaign["modelid"] or "gemma3:1b"

        result = runnarrativeturn(
            conn=conn,
            campaign=campaign,
            character=character,
            usertext=text,
            model=model,
            ollamabaseurl=x_ollama_base_url,
        )

        assistanttext = (result.get("message") or "").strip()
        if not assistanttext:
            raise HTTPException(status_code=500, detail="Empty narrative response")

        log = createturnlog(
            conn=conn,
            campaignid=campaignid,
            characterid=payload.characterid,
            usertext=text,
            assistanttext=assistanttext,
            route=route,
        )

        return {
            "turnnumber": log["turnnumber"],
            "createdat": log["createdat"],
            "route": "narrative",
            "result": result,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        conn.close()