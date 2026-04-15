import json
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

DB_PATH = "/data/ai_gm.db"

router = APIRouter()


class CharacterCreateRequest(BaseModel):
    user_id: int
    name: str
    system_id: str
    sheet_json: dict = {}
    location: str | None = None
    is_active: int = 1


class CharacterSheetPatchRequest(BaseModel):
    sheet_json: dict


def _deep_merge_dicts(base: dict, incoming: dict) -> dict:
    merged = dict(base)
    for key, value in incoming.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


@router.get("/campaigns/{campaign_id}/characters")
def list_characters(campaign_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    campaign = conn.execute(
        "SELECT id FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()

    if not campaign:
        conn.close()
        raise HTTPException(status_code=404, detail="Campaign not found")

    rows = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at
        FROM characters
        WHERE campaign_id = ?
        ORDER BY id ASC
        """,
        (campaign_id,),
    ).fetchall()

    conn.close()

    characters = []
    for row in rows:
        item = dict(row)
        try:
            item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
        except Exception:
            item["sheet_json"] = {}
        characters.append(item)

    return {"characters": characters}


@router.get("/characters/{character_id}")
def get_character(character_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Character not found")

    item = dict(row)
    try:
        item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
    except Exception:
        item["sheet_json"] = {}

    return item


@router.get("/characters/{character_id}/sheet")
def get_character_sheet(character_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT sheet_json
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        sheet_json = json.loads(row["sheet_json"]) if row["sheet_json"] else {}
    except Exception:
        sheet_json = {}

    return {"sheet_json": sheet_json}


@router.patch("/characters/{character_id}/sheet")
def patch_character_sheet(character_id: int, req: CharacterSheetPatchRequest):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT id, sheet_json
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        existing_sheet_json = json.loads(row["sheet_json"]) if row["sheet_json"] else {}
    except Exception:
        existing_sheet_json = {}

    merged_sheet_json = _deep_merge_dicts(existing_sheet_json, req.sheet_json)

    conn.execute(
        """
        UPDATE characters
        SET sheet_json = ?
        WHERE id = ?
        """,
        (json.dumps(merged_sheet_json, ensure_ascii=False), character_id),
    )
    conn.commit()

    updated_row = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not updated_row:
        raise HTTPException(status_code=500, detail="Character updated but could not be loaded")

    item = dict(updated_row)
    try:
        item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
    except Exception:
        item["sheet_json"] = {}

    return item


@router.post("/campaigns/{campaign_id}/characters")
def create_character(campaign_id: int, req: CharacterCreateRequest):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    campaign = conn.execute(
        """
        SELECT id, system_id
        FROM campaigns
        WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()

    if not campaign:
        conn.close()
        raise HTTPException(status_code=404, detail="Campaign not found")

    if req.system_id != campaign["system_id"]:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"system_id mismatch: campaign uses '{campaign['system_id']}'"
        )

    cur.execute(
        """
        INSERT INTO characters (campaign_id, user_id, name, system_id, sheet_json, location, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            campaign_id,
            req.user_id,
            req.name,
            req.system_id,
            json.dumps(req.sheet_json, ensure_ascii=False),
            req.location,
            req.is_active,
        ),
    )
    conn.commit()

    character_id = cur.lastrowid

    row = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=500, detail="Character created but could not be loaded")

    item = dict(row)
    try:
        item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
    except Exception:
        item["sheet_json"] = {}

    return item