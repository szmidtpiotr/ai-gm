"""Phase 9A-2 — NPC CRUD API."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

DB_PATH = "/data/ai_gm.db"

router = APIRouter(tags=["npcs"])
_NPC_TYPES = {"neutral", "merchant", "quest_giver", "ally"}


class NpcCreateReq(BaseModel):
    key: str
    label: str
    npc_type: str = "neutral"
    description: str | None = None
    personality_json: str = "{}"
    is_shop: int = 0
    is_quest_giver: int = 0
    is_ally: int = 0
    shop_inventory_json: str = "[]"
    is_active: int = 1
    location_keys: list[str] = Field(default_factory=list)


class NpcPatchReq(BaseModel):
    label: str | None = None
    npc_type: str | None = None
    description: str | None = None
    personality_json: str | None = None
    is_shop: int | None = None
    is_quest_giver: int | None = None
    is_ally: int | None = None
    shop_inventory_json: str | None = None
    is_active: int | None = None
    location_keys: list[str] | None = None


def _derive_primary_npc_type(is_shop: int, is_quest_giver: int, is_ally: int) -> str:
    """Priority: merchant > quest_giver > ally > neutral. Matches
    backend/app/routers/world_review.py — keep in sync."""
    if int(is_shop or 0):        return "merchant"
    if int(is_quest_giver or 0): return "quest_giver"
    if int(is_ally or 0):        return "ally"
    return "neutral"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _validate_json_fields(fields: dict[str, str | None]) -> None:
    for f in ("personality_json", "shop_inventory_json"):
        if f in fields and fields[f] is not None:
            try:
                json.loads(str(fields[f]))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid JSON in {f}") from exc


def _validate_npc_type(value: str | None) -> None:
    if value is None:
        return
    if str(value).strip() not in _NPC_TYPES:
        raise HTTPException(status_code=400, detail="Invalid npc_type")


def _set_npc_locations(conn: sqlite3.Connection, npc_id: int, location_keys: list[str]) -> None:
    conn.execute("DELETE FROM npc_locations WHERE npc_id = ?", (int(npc_id),))
    for loc_key in location_keys:
        lk = str(loc_key or "").strip()
        if not lk:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO npc_locations (npc_id, location_key) VALUES (?, ?)",
            (int(npc_id), lk),
        )


def _get_location_keys(conn: sqlite3.Connection, npc_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT location_key FROM npc_locations WHERE npc_id = ? ORDER BY location_key",
        (int(npc_id),),
    ).fetchall()
    return [str(r["location_key"]) for r in rows]


def _load_npc(conn: sqlite3.Connection, npc_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM npcs WHERE id = ?", (int(npc_id),)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="NPC not found")
    return row


@router.get("/npcs")
def list_npcs(active_only: bool = Query(False)):
    with _conn() as conn:
        q = "SELECT * FROM npcs"
        params: tuple = ()
        if active_only:
            q += " WHERE is_active = 1"
        rows = conn.execute(q + " ORDER BY npc_type, label COLLATE NOCASE", params).fetchall()
        data = []
        for r in rows:
            npc = dict(r)
            npc["location_keys"] = _get_location_keys(conn, int(npc["id"]))
            data.append(npc)
    return {"ok": True, "data": data}


@router.get("/npcs/{npc_id}")
def get_npc(npc_id: int):
    with _conn() as conn:
        row = _load_npc(conn, npc_id)
        npc = dict(row)
        npc["location_keys"] = _get_location_keys(conn, npc_id)
    return {"ok": True, "data": npc}


@router.post("/npcs")
def create_npc(body: NpcCreateReq):
    # When ANY role flag is set, derive npc_type from the flags (admin checked
    # the new role checkboxes); otherwise honour an explicit npc_type field.
    is_shop = int(body.is_shop or 0)
    is_quest_giver = int(body.is_quest_giver or 0)
    is_ally = int(body.is_ally or 0)
    if is_shop or is_quest_giver or is_ally:
        npc_type = _derive_primary_npc_type(is_shop, is_quest_giver, is_ally)
    else:
        npc_type = body.npc_type
    _validate_npc_type(npc_type)
    _validate_json_fields(
        {
            "personality_json": body.personality_json,
            "shop_inventory_json": body.shop_inventory_json,
        }
    )
    with _conn() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO npcs
                (key, label, npc_type, description, personality_json, is_shop,
                 is_quest_giver, is_ally, shop_inventory_json, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    body.key.strip(),
                    body.label.strip(),
                    npc_type.strip(),
                    body.description,
                    body.personality_json,
                    is_shop,
                    is_quest_giver,
                    is_ally,
                    body.shop_inventory_json,
                    int(body.is_active),
                ),
            )
            npc_id = int(cur.lastrowid)
            _set_npc_locations(conn, npc_id, body.location_keys)
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="NPC key already exists") from exc
    return {"ok": True, "id": npc_id}


@router.patch("/npcs/{npc_id}")
def patch_npc(npc_id: int, body: NpcPatchReq):
    data = body.model_dump(exclude_unset=True)
    location_keys = data.pop("location_keys", None)

    # If any role flag was sent, also re-derive npc_type from the merged state
    # (sent flags + current DB values for unsent flags). Same pattern as
    # world_review.patch_pending_npc.
    role_keys = {"is_shop", "is_quest_giver", "is_ally"}
    sent_roles = role_keys & data.keys()
    if sent_roles:
        with _conn() as conn:
            row = _load_npc(conn, npc_id)
            cur_flags = {k: int(row[k] or 0) for k in role_keys}
        merged = {**cur_flags, **{k: int(data[k] or 0) for k in sent_roles}}
        data["npc_type"] = _derive_primary_npc_type(
            merged["is_shop"], merged["is_quest_giver"], merged["is_ally"]
        )

    _validate_npc_type(data.get("npc_type"))
    _validate_json_fields(data)

    with _conn() as conn:
        _load_npc(conn, npc_id)
        if data:
            set_clause = ", ".join(f"{k} = ?" for k in data.keys())
            vals = list(data.values()) + [int(npc_id)]
            conn.execute(
                f"UPDATE npcs SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                tuple(vals),
            )
        if location_keys is not None:
            _set_npc_locations(conn, npc_id, location_keys)
        conn.commit()
    return {"ok": True}


@router.delete("/npcs/{npc_id}")
def delete_npc(npc_id: int):
    with _conn() as conn:
        _load_npc(conn, npc_id)
        conn.execute("DELETE FROM npc_locations WHERE npc_id = ?", (int(npc_id),))
        conn.execute("DELETE FROM npcs WHERE id = ?", (int(npc_id),))
        conn.commit()
    return {"ok": True}
