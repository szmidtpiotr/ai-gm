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
from app.services.tile_compositor import composite_tile, default_overlays_for

DB_PATH = Path("/data/ai_gm.db")
TILES_DIR = Path("/app/tiles")  # bind-mounted to frontend/images/tiles
TILES_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_GEN_URL = os.getenv("DUNGEON_IMAGE_GEN_URL", "http://192.168.1.170:8765/generate")
IMAGE_GEN_MODEL = os.getenv("DUNGEON_IMAGE_GEN_MODEL", "flux1-schnell-Q5_K_S.gguf")
IMAGE_GEN_TIMEOUT = int(os.getenv("DUNGEON_IMAGE_GEN_TIMEOUT", "180"))

BASE_PROMPT = (
    "Gloomhaven dungeon tile art style, top down view, flat 2D illustration, "
    "stone floor with room interior decor and furniture, fantasy board game tile, "
    "overhead perspective, square tile format, painted game art, cartoonish style, "
    "NO walls, NO doors, NO doorways, NO archways, NO openings — only floor and interior content"
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
    # door_overlays is a dict (per-side positions), not a list
    try:
        d["door_overlays"] = json.loads(d.get("door_overlays_json") or "{}")
    except Exception:
        d["door_overlays"] = {}
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
                   (key, label, description, style_modifier, system_prompt, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (key, label,
                 payload.get("description", ""),
                 payload.get("style_modifier", ""),
                 payload.get("system_prompt", ""),
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
    for k in ("label", "description", "style_modifier", "system_prompt", "sort_order", "is_active"):
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


@router.post("/dungeon-tile-categories/{key}/generate-system-prompt",
             dependencies=[Depends(require_admin_token)])
def generate_category_system_prompt(key: str) -> dict:
    """Use LLM to generate a GM system prompt for this tile category."""
    with _conn() as c:
        row = c.execute(
            "SELECT key, label, description, style_modifier FROM dungeon_tile_categories WHERE key = ?",
            (key,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Category not found")

    from app.services.llm_service import generate_chat

    cat = dict(row)
    messages = [
        {
            "role": "system",
            "content": (
                "Jesteś ekspertem od projektowania gier fabularnych. Tworzysz instrukcje dla Mistrza Gry "
                "do gry RPG w stylu dark fantasy. Odpowiadasz wyłącznie po polsku."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Stwórz system prompt dla Mistrza Gry dla kategorii kafelkowego lochu o nazwie '{cat['label']}'.\n"
                f"Opis kategorii: {cat['description'] or '(brak)'}\n"
                f"Styl wizualny: {cat['style_modifier'] or '(brak)'}\n\n"
                "System prompt powinien:\n"
                "1. Ustawić klimat i atmosferę (3-5 zdań)\n"
                "2. Wskazać MG jak opisywać komnaty, dźwięki, zapachy, nastrój\n"
                "3. Określić poziom mroku i niebezpieczeństwa\n"
                "4. Być napisany po POLSKU, w trybie rozkazującym (instrukcje dla MG)\n"
                "5. Mieć max 200 słów — zwięzły, konkretny\n\n"
                "Zwróć TYLKO sam tekst promptu, bez nagłówków ani komentarzy."
            ),
        },
    ]

    try:
        result = generate_chat(messages, call_type="admin_gen")
        return {"ok": True, "system_prompt": result.strip()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM error: {exc}")


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
        "door_overlays": ("door_overlays_json", lambda v: json.dumps(v or {})),
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
    """Compose final prompt — interior decor only. Walls + doors are composited
    mechanically by `tile_compositor.py`, so the prompt explicitly forbids them.
    """
    parts = [BASE_PROMPT]
    if category_style:
        parts.append(category_style)
    # Use image_gen_prompt (English) not room_description (Polish — FLUX won't understand)
    img_prompt = (tile.get("image_gen_prompt") or "").strip()
    if img_prompt:
        parts.append(img_prompt)
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

    # Build prompt — admin can override full prompt OR just the image_gen_prompt part
    override_prompt = (payload or {}).get("prompt")
    override_img_prompt = (payload or {}).get("image_gen_prompt")
    if override_prompt:
        prompt = str(override_prompt).strip()
    elif override_img_prompt:
        tile_dict = _tile_to_dict(tile)
        tile_dict["image_gen_prompt"] = str(override_img_prompt).strip()
        prompt = _build_prompt(tile_dict, cat_style)
    else:
        prompt = _build_prompt(_tile_to_dict(tile), cat_style)

    # Read global image quality config from visual_config (set via #system/imagegen).
    # Per-request overrides from payload still take precedence.
    try:
        from app.routers.admin_images import _get_image_config as _img_cfg
        _gcfg = _img_cfg()
    except Exception:
        _gcfg = {}
    _global_steps = int(_gcfg.get("image_gen.steps") or 4)
    _global_model = str(_gcfg.get("image_gen.checkpoint") or "").strip() or IMAGE_GEN_MODEL

    steps = int((payload or {}).get("steps") or _global_steps)
    model = str((payload or {}).get("model") or _global_model)

    _gen_url = str(_gcfg.get("image_gen.url") or IMAGE_GEN_URL).strip().rstrip("/") + "/generate"
    if not _gen_url.startswith("http"):
        _gen_url = IMAGE_GEN_URL

    try:
        resp = requests.post(
            _gen_url,
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

    # Save raw AI output (kept on disk for re-compositing if door overlays change)
    ts = int(time.time())
    raw_fname = f"dungeon_tile_{tile_id}_raw_{ts}.png"
    raw_path = TILES_DIR / raw_fname
    try:
        raw_bytes = base64.b64decode(data["b64"])
        raw_path.write_bytes(raw_bytes)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=500,
                            detail=f"Failed to save raw image: {exc}") from None
    raw_url = f"/images/tiles/{raw_fname}"

    # Composite: raw + procedural wall frame + door arches at active sides
    tile_dict = _tile_to_dict(tile)
    doors = _normalize_doors(tile_dict.get("doors") or [])
    overlays = tile_dict.get("door_overlays") or {}
    try:
        final_bytes = composite_tile(raw_bytes, doors, overlays)
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Compositor failed: {exc}") from None

    final_fname = f"dungeon_tile_{tile_id}_{ts}.png"
    final_path = TILES_DIR / final_fname
    try:
        final_path.write_bytes(final_bytes)
    except OSError as exc:
        raise HTTPException(status_code=500,
                            detail=f"Failed to save composited image: {exc}") from None
    final_url = f"/images/tiles/{final_fname}"

    # Backfill overlays with defaults for any active door missing a custom position
    if doors:
        merged_overlays = dict(overlays or {})
        for side in doors:
            if side not in merged_overlays:
                merged_overlays.update(default_overlays_for([side]))
    else:
        merged_overlays = overlays

    with _conn() as c:
        c.execute(
            "UPDATE dungeon_tiles SET image_url = ?, image_url_raw = ?, "
            "door_overlays_json = ?, updated_at = datetime('now') WHERE id = ?",
            (final_url, raw_url, json.dumps(merged_overlays), tile_id),
        )
        c.commit()

    return {
        "ok": True,
        "image_url": final_url,
        "image_url_raw": raw_url,
        "prompt": prompt,
        "filename": final_fname,
        "door_overlays": merged_overlays,
    }


@router.post("/dungeon-tiles/{tile_id}/recomposite",
             dependencies=[Depends(require_admin_token)])
def recomposite_tile_image(tile_id: int) -> dict:
    """Re-run the wall+door compositor on the stored raw image.

    Use after editing door_overlays_json or active doors — no AI gen call needed.
    Returns 400 if no raw image is stored for this tile.
    """
    with _conn() as c:
        tile = c.execute("SELECT * FROM dungeon_tiles WHERE id = ?", (tile_id,)).fetchone()
        if not tile:
            raise HTTPException(status_code=404, detail="Tile not found")
    tile_dict = _tile_to_dict(tile)
    raw_url = tile_dict.get("image_url_raw")
    if not raw_url:
        raise HTTPException(
            status_code=400,
            detail="No raw image stored — regenerate first to capture raw AI output.",
        )
    raw_fname = raw_url.rsplit("/", 1)[-1]
    raw_path = TILES_DIR / raw_fname
    if not raw_path.exists():
        raise HTTPException(status_code=400, detail=f"Raw image missing on disk: {raw_fname}")
    raw_bytes = raw_path.read_bytes()
    doors = _normalize_doors(tile_dict.get("doors") or [])
    overlays = tile_dict.get("door_overlays") or {}
    try:
        final_bytes = composite_tile(raw_bytes, doors, overlays)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Compositor failed: {exc}") from None

    ts = int(time.time())
    final_fname = f"dungeon_tile_{tile_id}_{ts}.png"
    (TILES_DIR / final_fname).write_bytes(final_bytes)
    final_url = f"/images/tiles/{final_fname}"
    with _conn() as c:
        c.execute(
            "UPDATE dungeon_tiles SET image_url = ?, updated_at = datetime('now') WHERE id = ?",
            (final_url, tile_id),
        )
        c.commit()
    return {"ok": True, "image_url": final_url, "filename": final_fname}


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
