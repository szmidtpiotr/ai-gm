"""Admin endpoints for the dungeon tile card system (issue #224).

Manages tile categories, tile content (doors / enemies / items / states / exit
conditions), and triggers image generation against the local FLUX service on
192.168.1.170:8765.

All endpoints require an admin bearer token.
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.admin import require_admin_token
from app.services.dungeon_tile_service import (
    DIRECTIONS,
    draw_tile_sequence,
    resolve_tile_content,
)

DB_PATH = Path("/data/ai_gm.db")
TILES_DIR = Path("/app/tiles")  # bind-mounted to frontend/images/tiles
TILES_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_GEN_URL = os.getenv("DUNGEON_IMAGE_GEN_URL", "http://192.168.1.170:8765/generate")
IMAGE_GEN_MODEL = os.getenv("DUNGEON_IMAGE_GEN_MODEL", "flux1-schnell-Q5_K_S.gguf")
IMAGE_GEN_TIMEOUT = int(os.getenv("DUNGEON_IMAGE_GEN_TIMEOUT", "180"))

BASE_PROMPT = (
    "Gloomhaven dungeon tile art style, top down view, flat 2D illustration, "
    "stone floor, thick dark stone walls forming square border, fantasy board game tile, "
    "overhead perspective, square tile format, painted game art, cartoonish style"
)

DIRECTION_WORDS = {"N": "north", "S": "south", "E": "east", "W": "west"}


router = APIRouter(prefix="/admin", tags=["admin-dungeon-tiles"])


# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _tile_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for k in ("doors_json", "enemies_json", "items_json",
              "active_states_json", "exit_conditions_json"):
        try:
            d[k.replace("_json", "")] = json.loads(d.get(k) or "[]")
        except Exception:
            d[k.replace("_json", "")] = []
    d["is_boss_tile"] = bool(d.get("is_boss_tile") or 0)
    d["is_active"] = bool(d.get("is_active") or 0)
    return d


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/dungeon-tile-categories",
            dependencies=[Depends(require_admin_token)])
def list_categories() -> dict:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM dungeon_tile_categories WHERE is_active = 1 ORDER BY sort_order, key"
        ).fetchall()
    return {"categories": [dict(r) for r in rows]}


@router.post("/dungeon-tile-categories",
             dependencies=[Depends(require_admin_token)])
def create_category(payload: dict = Body(...)) -> dict:
    key = (payload.get("key") or "").strip().lower()
    label = (payload.get("label") or "").strip()
    if not key or not label:
        raise HTTPException(status_code=400, detail="key and label required")
    with _conn() as c:
        try:
            c.execute(
                """INSERT INTO dungeon_tile_categories
                   (key, label, description, style_modifier, sort_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (key, label,
                 payload.get("description", ""),
                 payload.get("style_modifier", ""),
                 int(payload.get("sort_order") or 0)),
            )
            c.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Category key already exists")
    return {"ok": True, "key": key}


@router.patch("/dungeon-tile-categories/{key}",
              dependencies=[Depends(require_admin_token)])
def update_category(key: str, payload: dict = Body(...)) -> dict:
    fields = []
    params: list[Any] = []
    for k in ("label", "description", "style_modifier", "sort_order", "is_active"):
        if k in payload:
            fields.append(f"{k} = ?")
            params.append(payload[k])
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    params.append(key)
    with _conn() as c:
        c.execute(f"UPDATE dungeon_tile_categories SET {', '.join(fields)} WHERE key = ?", params)
        c.commit()
    return {"ok": True}


# ── Tiles ─────────────────────────────────────────────────────────────────────

@router.get("/dungeon-tiles", dependencies=[Depends(require_admin_token)])
def list_tiles(category_key: str | None = None,
               include_inactive: bool = False) -> dict:
    sql = "SELECT * FROM dungeon_tiles WHERE 1=1"
    params: list[Any] = []
    if category_key:
        sql += " AND category_key = ?"
        params.append(category_key)
    if not include_inactive:
        sql += " AND is_active = 1"
    sql += " ORDER BY category_key, is_boss_tile DESC, label"
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return {"tiles": [_tile_to_dict(r) for r in rows]}


@router.get("/dungeon-tiles/{tile_id}",
            dependencies=[Depends(require_admin_token)])
def get_tile(tile_id: int) -> dict:
    with _conn() as c:
        row = c.execute("SELECT * FROM dungeon_tiles WHERE id = ?", (tile_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Tile not found")
    return {"tile": _tile_to_dict(row)}


def _normalize_doors(doors: Any) -> list[str]:
    if not isinstance(doors, list):
        return []
    out: list[str] = []
    for d in doors:
        s = str(d).strip().upper()
        if s in DIRECTIONS and s not in out:
            out.append(s)
    return out


@router.post("/dungeon-tiles", dependencies=[Depends(require_admin_token)])
def create_tile(payload: dict = Body(...)) -> dict:
    category_key = (payload.get("category_key") or "").strip()
    label = (payload.get("label") or "").strip()
    if not category_key or not label:
        raise HTTPException(status_code=400, detail="category_key and label required")

    # Validate category exists
    with _conn() as c:
        cat = c.execute(
            "SELECT 1 FROM dungeon_tile_categories WHERE key = ?", (category_key,)
        ).fetchone()
        if not cat:
            raise HTTPException(status_code=400, detail=f"Unknown category_key: {category_key}")

        doors = _normalize_doors(payload.get("doors") or payload.get("doors_json"))
        cur = c.execute(
            """INSERT INTO dungeon_tiles
               (category_key, label, image_url, image_gen_prompt, doors_json,
                room_description, enemies_json, items_json, active_states_json,
                riddle_key, exit_conditions_json, is_boss_tile, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                category_key,
                label,
                payload.get("image_url"),
                payload.get("image_gen_prompt"),
                json.dumps(doors),
                payload.get("room_description") or "",
                json.dumps(payload.get("enemies") or []),
                json.dumps(payload.get("items") or []),
                json.dumps(payload.get("active_states") or []),
                payload.get("riddle_key"),
                json.dumps(payload.get("exit_conditions") or []),
                1 if payload.get("is_boss_tile") else 0,
                1 if payload.get("is_active", True) else 0,
            ),
        )
        tile_id = cur.lastrowid
        c.commit()
    return {"ok": True, "id": tile_id}


@router.patch("/dungeon-tiles/{tile_id}",
              dependencies=[Depends(require_admin_token)])
def update_tile(tile_id: int, payload: dict = Body(...)) -> dict:
    field_map = {
        "label": ("label", lambda v: v),
        "category_key": ("category_key", lambda v: v),
        "image_url": ("image_url", lambda v: v),
        "image_gen_prompt": ("image_gen_prompt", lambda v: v),
        "doors": ("doors_json", lambda v: json.dumps(_normalize_doors(v))),
        "room_description": ("room_description", lambda v: v),
        "enemies": ("enemies_json", lambda v: json.dumps(v or [])),
        "items": ("items_json", lambda v: json.dumps(v or [])),
        "active_states": ("active_states_json", lambda v: json.dumps(v or [])),
        "riddle_key": ("riddle_key", lambda v: v),
        "exit_conditions": ("exit_conditions_json", lambda v: json.dumps(v or [])),
        "is_boss_tile": ("is_boss_tile", lambda v: 1 if v else 0),
        "is_active": ("is_active", lambda v: 1 if v else 0),
    }
    sets = []
    params: list[Any] = []
    for k, val in payload.items():
        if k in field_map:
            col, transform = field_map[k]
            sets.append(f"{col} = ?")
            params.append(transform(val))
    if not sets:
        raise HTTPException(status_code=400, detail="no fields to update")
    sets.append("updated_at = datetime('now')")
    params.append(tile_id)
    with _conn() as c:
        c.execute(f"UPDATE dungeon_tiles SET {', '.join(sets)} WHERE id = ?", params)
        c.commit()
    return {"ok": True}


@router.delete("/dungeon-tiles/{tile_id}",
               dependencies=[Depends(require_admin_token)])
def delete_tile(tile_id: int) -> dict:
    with _conn() as c:
        c.execute("UPDATE dungeon_tiles SET is_active = 0 WHERE id = ?", (tile_id,))
        c.commit()
    return {"ok": True}


# ── Image generation ──────────────────────────────────────────────────────────

def _build_prompt(tile: dict, category_style: str) -> str:
    """Compose final prompt from base + category style + tile content + doors."""
    parts = [BASE_PROMPT]
    if category_style:
        parts.append(category_style)
    room_desc = (tile.get("room_description") or "").strip()
    if room_desc:
        parts.append(room_desc)
    doors = _normalize_doors(tile.get("doors") or json.loads(tile.get("doors_json") or "[]"))
    if doors:
        words = [DIRECTION_WORDS[d] for d in doors]
        if len(words) == 1:
            parts.append(f"gap opening in {words[0]} wall")
        elif len(words) == 4:
            parts.append("gap openings in all four walls north south east west")
        else:
            parts.append("gap openings in " + " and ".join(f"{w} wall" for w in words))
    return ", ".join(parts)


@router.post("/dungeon-tiles/{tile_id}/generate-image",
             dependencies=[Depends(require_admin_token)])
def generate_tile_image(tile_id: int, payload: dict = Body(default={})) -> dict:
    """Call FLUX image gen service, save PNG, update tile.image_url."""
    with _conn() as c:
        tile = c.execute("SELECT * FROM dungeon_tiles WHERE id = ?", (tile_id,)).fetchone()
        if not tile:
            raise HTTPException(status_code=404, detail="Tile not found")
        cat = c.execute(
            "SELECT style_modifier FROM dungeon_tile_categories WHERE key = ?",
            (tile["category_key"],),
        ).fetchone()
    cat_style = cat["style_modifier"] if cat else ""

    # Build prompt (admin override possible)
    override_prompt = (payload or {}).get("prompt")
    if override_prompt:
        prompt = str(override_prompt).strip()
    else:
        prompt = _build_prompt(_tile_to_dict(tile), cat_style)

    steps = int((payload or {}).get("steps") or 8)
    model = str((payload or {}).get("model") or IMAGE_GEN_MODEL)

    try:
        resp = requests.post(
            IMAGE_GEN_URL,
            json={"prompt": prompt, "width": 512, "height": 512, "steps": steps, "model": model},
            timeout=IMAGE_GEN_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502,
                            detail=f"Image gen service unreachable: {exc}") from None
    if resp.status_code != 200:
        raise HTTPException(status_code=502,
                            detail=f"Image gen failed: HTTP {resp.status_code} — {resp.text[:200]}")
    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Image gen returned non-JSON response") from None
    if "b64" not in data:
        raise HTTPException(status_code=502,
                            detail=f"Image gen missing b64: {data.get('error', 'unknown error')}")

    # Save to bind-mounted dir; bust browser cache with timestamp
    ts = int(time.time())
    fname = f"dungeon_tile_{tile_id}_{ts}.png"
    out_path = TILES_DIR / fname
    try:
        out_path.write_bytes(base64.b64decode(data["b64"]))
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=500,
                            detail=f"Failed to save image: {exc}") from None

    public_url = f"/images/tiles/{fname}"
    with _conn() as c:
        c.execute(
            "UPDATE dungeon_tiles SET image_url = ?, image_gen_prompt = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (public_url, prompt, tile_id),
        )
        c.commit()

    return {"ok": True, "image_url": public_url, "prompt": prompt, "filename": fname}


# ── Path preview (admin testing) ──────────────────────────────────────────────

@router.get("/dungeon-tiles/preview-path/{category_key}",
            dependencies=[Depends(require_admin_token)])
def preview_path(category_key: str, count: int = 4,
                 boss_tile_id: int | None = None) -> dict:
    """Try to build a valid path of `count` tiles. Returns sequence with positions."""
    if count < 2:
        raise HTTPException(status_code=400, detail="count must be >= 2")
    try:
        seq = draw_tile_sequence(category_key, count, boss_tile_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    # Resolve labels for each step
    with _conn() as c:
        tile_ids = [s["tile_id"] for s in seq]
        placeholders = ",".join("?" * len(tile_ids))
        rows = c.execute(
            f"SELECT id, label, image_url, doors_json, is_boss_tile FROM dungeon_tiles "
            f"WHERE id IN ({placeholders})",
            tile_ids,
        ).fetchall()
    by_id = {r["id"]: dict(r) for r in rows}

    enriched = []
    for s in seq:
        t = by_id.get(s["tile_id"]) or {}
        enriched.append({
            **s,
            "label": t.get("label"),
            "image_url": t.get("image_url"),
            "doors": json.loads(t.get("doors_json") or "[]"),
            "is_boss_tile": bool(t.get("is_boss_tile") or 0),
        })
    return {"ok": True, "sequence": enriched, "count": len(enriched)}
