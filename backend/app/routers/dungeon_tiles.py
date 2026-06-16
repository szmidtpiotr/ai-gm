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
from app.services.tile_compositor import TILE_SIZE, composite_tile, default_overlays_for

DB_PATH = Path("/data/ai_gm.db")
TILES_DIR = Path("/app/tiles")  # bind-mounted to frontend/images/tiles
TILES_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_GEN_URL = os.getenv("DUNGEON_IMAGE_GEN_URL", "http://192.168.1.170:8765/generate")
IMAGE_GEN_MODEL = os.getenv("DUNGEON_IMAGE_GEN_MODEL", "flux1-schnell-Q5_K_S.gguf")
IMAGE_GEN_TIMEOUT = int(os.getenv("DUNGEON_IMAGE_GEN_TIMEOUT", "180"))
IMAGE_GEN_TILE_SIZE = int(os.getenv("DUNGEON_IMAGE_GEN_SIZE", "768"))

# L15: rich drawn interiors — furniture, props, atmospheric details for Vision/LLM narration.
# Walls and doors are composited mechanically by tile_compositor.py, so the prompt forbids them.
BASE_PROMPT = (
    "fantasy dungeon tile, top-down overhead view, richly detailed interior illustration, "
    "painted tabletop RPG art style, high detail, elaborate furniture and props: "
    "stone benches, weapon racks, chests, candelabras, iron braziers, barrels, crates, "
    "stone pillars, urns, tapestries, wall sconces, ritual objects, scattered bones and skulls, "
    "dramatic atmospheric lighting from candles and torches casting warm orange and amber glow, "
    "intricate floor stonework with cracks, moss, and stains, "
    "rich storytelling details a narrator can describe in 2-4 sentences, "
    "square tile format, overhead perspective, 2D illustrated game art, "
    "interior designed with 2-4 open pathways toward wall edges for dungeon connectivity, "
    "NO walls, NO explicit doors, NO doorways, NO archways — only floor and interior content"
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
        result = generate_chat(messages)
        return {"ok": True, "system_prompt": result.strip()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM error: {exc}")


# ── Tiles ─────────────────────────────────────────────────────────────────────

@router.get("/dungeon-tiles", dependencies=[Depends(require_admin_token)])
def list_tiles(category_key: str | None = None,
               include_inactive: bool = False,
               needs_description: bool = False) -> dict:
    sql = "SELECT * FROM dungeon_tiles WHERE 1=1"
    params: list[Any] = []
    if category_key:
        sql += " AND category_key = ?"
        params.append(category_key)
    if not include_inactive:
        sql += " AND is_active = 1"
    if needs_description:
        sql += " AND (room_description IS NULL OR room_description = '')"
    sql += " ORDER BY category_key, is_boss_tile DESC, label"
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return {"tiles": [_tile_to_dict(r) for r in rows]}


@router.post("/dungeon-tiles/generate-image-prompt",
             dependencies=[Depends(require_admin_token)])
def generate_tile_image_prompt(payload: dict = Body(...)) -> dict:
    """LLM generates an English FLUX image prompt for a tile category."""
    import re
    from app.services.llm_service import generate_chat

    category_key = (payload.get("category_key") or "").strip()
    if not category_key:
        raise HTTPException(status_code=422, detail="category_key required")

    with _conn() as c:
        cat = c.execute(
            "SELECT key, label, description, style_modifier FROM dungeon_tile_categories WHERE key = ?",
            (category_key,),
        ).fetchone()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    cat = dict(cat)
    description_hint = (payload.get("description_hint") or "").strip()

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert dungeon art director generating prompts for a FLUX image generation model. "
                "You create concise, vivid English descriptions optimized for top-down 2D dungeon tile art. "
                "Always respond with valid JSON only, no markdown, no explanation."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Create a dungeon tile definition for the '{cat['label']}' category.\n"
                f"Category style: {cat['style_modifier'] or '(not specified)'}\n"
                + (f"Room hint: {description_hint}\n" if description_hint else "")
                + '\nReturn JSON with exactly these two fields:\n'
                '{"label": "Polish tile name (3-6 words, e.g. Komnata strażnicza)", '
                '"image_gen_prompt": "English FLUX prompt (15-50 words)"}\n\n'
                "image_gen_prompt requirements:\n"
                "- Top-down 2D dungeon tile, floor and interior decor\n"
                "- Specific objects, textures, lighting atmosphere\n"
                "- Interior designed with 2-4 open pathways toward wall edges (for dungeon maze connectivity)\n"
                "- NO explicit walls, NO explicit doors — only floor and interior content\n\n"
                "Return ONLY the JSON object."
            ),
        },
    ]

    try:
        import re
        result = generate_chat(messages)
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", result).strip()
        try:
            data = json.loads(cleaned)
            image_gen_prompt = str(data.get("image_gen_prompt") or "").strip()
            suggested_label = str(data.get("label") or "").strip()
        except (json.JSONDecodeError, ValueError):
            # Fallback: treat entire response as the prompt (backward compat)
            image_gen_prompt = result.strip()
            suggested_label = ""
        return {"ok": True, "image_gen_prompt": image_gen_prompt, "suggested_label": suggested_label}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM error: {exc}")


@router.post("/dungeon-tiles/ai-create",
             dependencies=[Depends(require_admin_token)])
def ai_create_tile(payload: dict = Body(...)) -> dict:
    """LLM generates tile label + image_gen_prompt for a category and inserts the record."""
    import re
    from app.services.llm_service import generate_chat

    category_key = (payload.get("category_key") or "").strip()
    if not category_key:
        raise HTTPException(status_code=422, detail="category_key required")

    with _conn() as c:
        cat = c.execute(
            "SELECT key, label, description, style_modifier FROM dungeon_tile_categories WHERE key = ?",
            (category_key,),
        ).fetchone()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    cat = dict(cat)

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert dungeon designer creating dungeon tile definitions for a dark fantasy RPG. "
                "Always respond with valid JSON only, no markdown, no explanation."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Create a dungeon tile for the '{cat['label']}' category.\n"
                f"Category description: {cat['description'] or '(none)'}\n"
                f"Visual style: {cat['style_modifier'] or '(none)'}\n\n"
                'Return JSON with exactly these fields:\n'
                '{"label": "Polish room name (3-6 words)", '
                '"image_gen_prompt": "English FLUX prompt (15-50 words, top-down 2D tile, floor and decor only, no walls, no doors)"}\n\n'
                "Good label examples: 'Komnata strażnicza', 'Izba tortur', 'Skarbiec', 'Sala rytuałów'\n"
                "Return ONLY the JSON object."
            ),
        },
    ]

    try:
        result = generate_chat(messages)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM error: {exc}")

    try:
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", result).strip()
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LLM returned invalid JSON: {exc}. Raw: {result[:200]}",
        )

    label = str(data.get("label") or "").strip()
    image_gen_prompt = str(data.get("image_gen_prompt") or "").strip()

    if not label or not image_gen_prompt:
        raise HTTPException(
            status_code=500,
            detail=f"LLM response missing label or prompt: {data}",
        )

    with _conn() as c:
        cur = c.execute(
            "INSERT INTO dungeon_tiles (category_key, label, image_gen_prompt, doors_json, is_active) "
            "VALUES (?, ?, ?, '[]', 1)",
            (category_key, label, image_gen_prompt),
        )
        tile_id = cur.lastrowid
        tile_row = c.execute("SELECT * FROM dungeon_tiles WHERE id = ?", (tile_id,)).fetchone()

    return {"ok": True, "tile": _tile_to_dict(tile_row)}


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
    _global_size = int(_gcfg.get("image_gen.tile_size") or IMAGE_GEN_TILE_SIZE)

    steps = int((payload or {}).get("steps") or _global_steps)
    model = str((payload or {}).get("model") or _global_model)
    width = int((payload or {}).get("width") or (payload or {}).get("size") or _global_size)
    height = int((payload or {}).get("height") or (payload or {}).get("size") or _global_size)

    _gen_url = str(_gcfg.get("image_gen.url") or IMAGE_GEN_URL).strip().rstrip("/") + "/generate"
    if not _gen_url.startswith("http"):
        _gen_url = IMAGE_GEN_URL

    try:
        resp = requests.post(
            _gen_url,
            json={"prompt": prompt, "width": width, "height": height, "steps": steps, "model": model},
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
        # L15: keep the full generated resolution (768) through compositing — don't
        # downscale to the legacy 512 baseline, which flattened the new rich tiles.
        final_bytes = composite_tile(raw_bytes, doors, overlays, tile_size=height)
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
    # L15: preserve the raw image's native resolution (768 for new tiles, 512 for legacy).
    try:
        from PIL import Image as _PILImage
        import io as _io
        _raw_size = _PILImage.open(_io.BytesIO(raw_bytes)).size[0]
    except Exception:
        _raw_size = TILE_SIZE
    try:
        final_bytes = composite_tile(raw_bytes, doors, overlays, tile_size=_raw_size)
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


@router.post("/dungeon-tiles/{tile_id}/generate-description",
             dependencies=[Depends(require_admin_token)])
def generate_tile_description(tile_id: int) -> dict:
    """LLM generates a Polish room description considering active doors and tile context.

    Considers doors (N/S/E/W) so description mentions passages on correct walls.
    Saves result to dungeon_tiles.room_description.
    """
    from app.services.llm_service import generate_chat

    with _conn() as c:
        tile = c.execute("SELECT * FROM dungeon_tiles WHERE id = ?", (tile_id,)).fetchone()
        if not tile:
            raise HTTPException(status_code=404, detail="Tile not found")
        cat = c.execute(
            "SELECT label, description, system_prompt FROM dungeon_tile_categories WHERE key = ?",
            (tile["category_key"],),
        ).fetchone()

    tile_dict = _tile_to_dict(tile)
    doors = _normalize_doors(tile_dict.get("doors") or [])
    img_prompt = (tile_dict.get("image_gen_prompt") or "").strip()
    cat_label = cat["label"] if cat else tile["category_key"]
    cat_system = (cat["system_prompt"] if cat else "") or ""

    door_names = [{"N": "północnej", "S": "południowej", "E": "wschodniej", "W": "zachodniej"}[d]
                  for d in doors if d in ("N", "S", "E", "W")]
    doors_info = (
        f"Aktywne przejścia (drzwi) na ścianach: {', '.join(door_names)}."
        if door_names
        else "Brak przejść — komnata bez wyjść."
    )

    system_content = (
        cat_system + "\n\n" if cat_system else ""
    ) + (
        "Jesteś Mistrzem Gry w dark fantasy RPG. Opisujesz komnatę lochu z perspektywy gracza. "
        "Piszesz krótko, klimatycznie, po POLSKU. Uwzględniasz dokładnie na których ścianach są przejścia."
    )

    messages = [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": (
                f"Napisz opis komnaty dla Mistrza Gry.\n"
                f"Kategoria: {cat_label}\n"
                f"Wygląd (EN, dla AI): {img_prompt or '(brak)'}\n"
                f"{doors_info}\n\n"
                "Wymagania:\n"
                "- Po POLSKU, 3-5 zdań\n"
                "- Klimatyczny, konkretny opis — co gracz widzi, słyszy, czuje\n"
                "- Jeśli są drzwi: wspomnij przejścia na konkretnych ścianach\n"
                "- Jeśli brak drzwi: zaznacz że komnata jest zamknięta\n"
                "- Bez nagłówków, bez cudzysłowów, tylko sam opis"
            ),
        },
    ]

    try:
        description = generate_chat(messages)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM error: {exc}")

    description = description.strip()
    with _conn() as c:
        c.execute(
            "UPDATE dungeon_tiles SET room_description = ?, updated_at = datetime('now') WHERE id = ?",
            (description, tile_id),
        )
        c.commit()

    return {"ok": True, "room_description": description}


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
