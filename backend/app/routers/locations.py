import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.admin_auth import verify_admin_token

DB_PATH = "/data/ai_gm.db"

router = APIRouter()


class LocationCreateRequest(BaseModel):
    key: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    description: str | None = None
    parent_id: int | None = None
    location_type: str = Field(default="macro", pattern="^(macro|sub)$")
    rules: dict[str, Any] | list[Any] | str | None = None
    enemy_keys: list[str] = Field(default_factory=list)
    npc_keys: list[str] = Field(default_factory=list)


class LocationPatchRequest(BaseModel):
    key: str | None = None
    label: str | None = None
    description: str | None = None
    parent_id: int | None = None
    location_type: str | None = Field(default=None, pattern="^(macro|sub)$")
    rules: dict[str, Any] | list[Any] | str | None = None
    enemy_keys: list[str] | None = None
    npc_keys: list[str] | None = None


def _db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, uri=DB_PATH.startswith("file:"))
    conn.row_factory = sqlite3.Row
    return conn


def _parse_json_list(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    txt = str(raw).strip()
    if not txt:
        return []
    try:
        parsed = json.loads(txt)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _parse_json_obj(raw: Any) -> dict[str, Any] | list[Any] | None:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    txt = str(raw).strip()
    if not txt:
        return None
    try:
        parsed = json.loads(txt)
        if isinstance(parsed, (dict, list)):
            return parsed
    except json.JSONDecodeError:
        pass
    return txt


def _to_json_text(value: dict[str, Any] | list[Any] | str | None, *, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _row_to_location(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "key": str(row["key"]),
        "label": str(row["label"]),
        "description": row["description"],
        "parent_id": row["parent_id"],
        "location_type": str(row["location_type"] or "macro"),
        "rules": _parse_json_obj(row["rules"]),
        "enemy_keys": _parse_json_list(row["enemy_keys"]),
        "npc_keys": _parse_json_list(row["npc_keys"]),
        "is_active": int(row["is_active"] or 0),
        "children": [],
    }


def _build_tree(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {int(item["id"]): item for item in items}
    roots: list[dict[str, Any]] = []
    for item in items:
        parent_id = item.get("parent_id")
        if parent_id is None:
            roots.append(item)
            continue
        parent = by_id.get(int(parent_id))
        if parent is None:
            roots.append(item)
            continue
        parent["children"].append(item)
    return roots


def _require_internal_gm_or_admin(
    authorization: str | None = Header(default=None),
    x_internal_role: str | None = Header(default=None),
) -> None:
    role = (x_internal_role or "").strip().lower()
    if role in {"gm", "admin"}:
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing auth (use Bearer admin token or X-Internal-Role: gm/admin)",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.get("/locations")
def list_locations(
    type: str = Query("all", pattern="^(macro|sub|all)$"),
    parent_id: int | None = Query(default=None),
    active_only: int = Query(default=1, ge=0, le=1),
):
    conn = _db_connect()
    try:
        where: list[str] = []
        params: list[Any] = []
        if active_only == 1:
            where.append("is_active = 1")
        if type in {"macro", "sub"}:
            where.append("location_type = ?")
            params.append(type)
        sql = """
            SELECT id, key, label, description, parent_id, location_type, rules, enemy_keys, npc_keys, is_active
            FROM game_locations
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id ASC"
        rows = conn.execute(sql, tuple(params)).fetchall()
    finally:
        conn.close()

    items = [_row_to_location(r) for r in rows]
    tree = _build_tree(items)
    if parent_id is not None:
        node = next((n for n in items if int(n["id"]) == int(parent_id)), None)
        return [] if node is None else [node]
    return tree


@router.post("/locations", status_code=status.HTTP_201_CREATED)
def create_location(req: LocationCreateRequest, _: None = Depends(_require_internal_gm_or_admin)):
    conn = _db_connect()
    try:
        key = req.key.strip()
        label = req.label.strip()
        if not key or not label:
            raise HTTPException(status_code=422, detail="key and label are required")

        existing = conn.execute(
            "SELECT id FROM game_locations WHERE key = ? LIMIT 1",
            (key,),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=422, detail="Location key already exists")

        if req.parent_id is not None:
            parent = conn.execute(
                "SELECT id FROM game_locations WHERE id = ? LIMIT 1",
                (req.parent_id,),
            ).fetchone()
            if not parent:
                raise HTTPException(status_code=404, detail="Parent location not found")

        cur = conn.execute(
            """
            INSERT INTO game_locations (
                key, label, description, parent_id, location_type, rules, enemy_keys, npc_keys, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                key,
                label,
                req.description,
                req.parent_id,
                req.location_type,
                _to_json_text(req.rules, fallback="{}"),
                json.dumps(req.enemy_keys or [], ensure_ascii=False),
                json.dumps(req.npc_keys or [], ensure_ascii=False),
            ),
        )
        conn.commit()
        created = conn.execute(
            """
            SELECT id, key, label, description, parent_id, location_type, rules, enemy_keys, npc_keys, is_active
            FROM game_locations
            WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
        if not created:
            raise HTTPException(status_code=500, detail="Location created but could not be loaded")
        return _row_to_location(created)
    finally:
        conn.close()


@router.get("/locations/{key}")
def get_location_detail(
    key: str,
    active_only: int = Query(default=1, ge=0, le=1),
):
    conn = _db_connect()
    try:
        where = "key = ?"
        params: list[Any] = [key]
        if active_only == 1:
            where += " AND is_active = 1"
        row = conn.execute(
            f"""
            SELECT id, key, label, description, parent_id, location_type, rules, enemy_keys, npc_keys, is_active
            FROM game_locations
            WHERE {where}
            LIMIT 1
            """,
            tuple(params),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Location not found")

        location = _row_to_location(row)
        location_id = int(location["id"])
        children_rows = conn.execute(
            """
            SELECT id, key, label, description, parent_id, location_type, rules, enemy_keys, npc_keys, is_active
            FROM game_locations
            WHERE parent_id = ?
            ORDER BY id ASC
            """,
            (location_id,),
        ).fetchall()
        if active_only == 1:
            location["children"] = [
                _row_to_location(r) for r in children_rows if int(r["is_active"] or 0) == 1
            ]
        else:
            location["children"] = [_row_to_location(r) for r in children_rows]

        parent = None
        if location["parent_id"] is not None:
            parent_row = conn.execute(
                "SELECT key, label FROM game_locations WHERE id = ? LIMIT 1",
                (location["parent_id"],),
            ).fetchone()
            if parent_row:
                parent = {"key": parent_row["key"], "label": parent_row["label"]}
        location["parent"] = parent
        return location
    finally:
        conn.close()


@router.patch("/locations/{key}")
def patch_location(
    key: str,
    req: LocationPatchRequest,
    _: None = Depends(_require_internal_gm_or_admin),
):
    conn = _db_connect()
    try:
        row = conn.execute(
            "SELECT id, key FROM game_locations WHERE key = ? LIMIT 1",
            (key,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Location not found")
        current_id = int(row["id"])

        updates: list[str] = []
        params: list[Any] = []

        if req.key is not None:
            new_key = req.key.strip()
            if not new_key:
                raise HTTPException(status_code=422, detail="key cannot be empty")
            exists = conn.execute(
                "SELECT id FROM game_locations WHERE key = ? AND id != ? LIMIT 1",
                (new_key, current_id),
            ).fetchone()
            if exists:
                raise HTTPException(status_code=422, detail="Location key already exists")
            updates.append("key = ?")
            params.append(new_key)
        if req.label is not None:
            lbl = req.label.strip()
            if not lbl:
                raise HTTPException(status_code=422, detail="label cannot be empty")
            updates.append("label = ?")
            params.append(lbl)
        if req.description is not None:
            updates.append("description = ?")
            params.append(req.description)
        if req.location_type is not None:
            updates.append("location_type = ?")
            params.append(req.location_type)
        if req.parent_id is not None:
            parent = conn.execute("SELECT id FROM game_locations WHERE id = ? LIMIT 1", (req.parent_id,)).fetchone()
            if not parent:
                raise HTTPException(status_code=404, detail="Parent location not found")
            updates.append("parent_id = ?")
            params.append(req.parent_id)
        if req.rules is not None:
            updates.append("rules = ?")
            params.append(_to_json_text(req.rules, fallback="{}"))
        if req.enemy_keys is not None:
            updates.append("enemy_keys = ?")
            params.append(json.dumps(req.enemy_keys, ensure_ascii=False))
        if req.npc_keys is not None:
            updates.append("npc_keys = ?")
            params.append(json.dumps(req.npc_keys, ensure_ascii=False))

        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(current_id)
            conn.execute(
                f"UPDATE game_locations SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            conn.commit()

        updated = conn.execute(
            """
            SELECT id, key, label, description, parent_id, location_type, rules, enemy_keys, npc_keys, is_active
            FROM game_locations
            WHERE id = ?
            """,
            (current_id,),
        ).fetchone()
        if not updated:
            raise HTTPException(status_code=500, detail="Location updated but could not be loaded")
        return _row_to_location(updated)
    finally:
        conn.close()


@router.delete("/locations/{key}")
def delete_location(
    key: str,
    _: None = Depends(_require_internal_gm_or_admin),
):
    conn = _db_connect()
    try:
        row = conn.execute(
            "SELECT id FROM game_locations WHERE key = ? LIMIT 1",
            (key,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Location not found")
        conn.execute(
            "UPDATE game_locations SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
            (int(row["id"]),),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
