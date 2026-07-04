"""
Admin image generation — proxy to local FLUX service on .170:8765
Images stored in /usr/share/nginx/html/images/tiles/ (bind-mounted from ./frontend/images/tiles/)
Flask API returns b64-encoded image so no shared filesystem needed.
"""
import json
import os
import sqlite3
import time
import base64
import httpx
from pathlib import Path
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from typing import Any

from app.routers.admin import require_admin_token

router = APIRouter(prefix="/api/admin/images", tags=["admin-images"], dependencies=[Depends(require_admin_token)])

IMAGE_GEN_URL = os.getenv("IMAGE_GEN_URL", "http://192.168.1.170:8765")
TILES_DIR = Path(os.getenv("IMAGES_TILES_DIR", "/app/tiles"))
TILES_URL_PREFIX = "/images/tiles"
_DB_PATH = Path("/data/ai_gm.db")

_IMAGE_GEN_KEYS = (
    "image_gen.url", "image_gen.steps", "image_gen.refine_steps",
    "image_gen.checkpoint", "image_gen.portrait_width", "image_gen.portrait_height",
)
_IMAGE_GEN_DEFAULTS: dict[str, Any] = {
    "image_gen.url": IMAGE_GEN_URL,
    "image_gen.steps": 4,
    "image_gen.refine_steps": 8,
    "image_gen.checkpoint": "",
    "image_gen.portrait_width": 576,
    "image_gen.portrait_height": 1024,
}


def _read_visual(key: str, default: Any = None) -> Any:
    try:
        with sqlite3.connect(_DB_PATH) as c:
            row = c.execute("SELECT value FROM game_config_visual WHERE key = ?", (key,)).fetchone()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return default


def _get_image_gen_url() -> str:
    url = _read_visual("image_gen.url", IMAGE_GEN_URL)
    return str(url).strip() or IMAGE_GEN_URL


def _get_image_config() -> dict[str, Any]:
    try:
        with sqlite3.connect(_DB_PATH) as c:
            rows = c.execute(
                "SELECT key, value FROM game_config_visual WHERE key IN (?,?,?,?)",
                _IMAGE_GEN_KEYS,
            ).fetchall()
        result = dict(_IMAGE_GEN_DEFAULTS)
        for key, val in rows:
            try:
                result[key] = json.loads(val)
            except Exception:
                result[key] = val
        return result
    except Exception:
        return dict(_IMAGE_GEN_DEFAULTS)


@router.get("/config")
async def get_image_config():
    cfg = _get_image_config()
    return {
        "url": cfg.get("image_gen.url", IMAGE_GEN_URL),
        "steps": cfg.get("image_gen.steps", 4),
        "refine_steps": cfg.get("image_gen.refine_steps", 8),
        "checkpoint": cfg.get("image_gen.checkpoint", ""),
        "portrait_width": int(cfg.get("image_gen.portrait_width", 576)),
        "portrait_height": int(cfg.get("image_gen.portrait_height", 1024)),
    }


class ImageConfigPatch(BaseModel):
    url: str | None = None
    steps: int | None = None
    refine_steps: int | None = None
    checkpoint: str | None = None
    portrait_width: int | None = None
    portrait_height: int | None = None


@router.patch("/config")
async def patch_image_config(req: ImageConfigPatch):
    updates: list[tuple[str, str]] = []
    if req.url is not None:
        updates.append(("image_gen.url", json.dumps(req.url.strip())))
    if req.steps is not None:
        updates.append(("image_gen.steps", json.dumps(max(1, min(50, req.steps)))))
    if req.refine_steps is not None:
        updates.append(("image_gen.refine_steps", json.dumps(max(1, min(50, req.refine_steps)))))
    if req.checkpoint is not None:
        updates.append(("image_gen.checkpoint", json.dumps(req.checkpoint.strip())))
    if req.portrait_width is not None:
        updates.append(("image_gen.portrait_width", json.dumps(max(64, min(2048, req.portrait_width)))))
    if req.portrait_height is not None:
        updates.append(("image_gen.portrait_height", json.dumps(max(64, min(2048, req.portrait_height)))))
    if updates:
        with sqlite3.connect(_DB_PATH) as c:
            for key, val in updates:
                c.execute(
                    "INSERT INTO game_config_visual (key, value, updated_at) VALUES (?,?,datetime('now')) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
                    (key, val),
                )
            c.commit()
    return {"ok": True}


@router.get("/status")
async def get_image_gen_status():
    url = _get_image_gen_url()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{url}/status")
            data = r.json() if r.status_code == 200 else {}
            return {"online": True, "url": url, "data": data}
    except Exception as ex:
        return {"online": False, "url": url, "error": str(ex)}


# #1168 — duplicate GET /models removed here; canonical definition (with
# 503/502 error surfacing) lives further down in this module.


class GenerateRequest(BaseModel):
    prompt: str
    width: int = 512
    height: int = 512
    steps: int | None = None       # None → read from DB config (image_gen.steps)
    checkpoint: str | None = None


class RefineRequest(BaseModel):
    source_filename: str       # existing tile filename in TILES_DIR
    prompt: str
    denoise: float = 0.6       # 0.1 = subtle tweak, 0.9 = big change
    steps: int | None = None   # None → read from DB config (image_gen.refine_steps)


@router.post("/generate")
async def generate_image(req: GenerateRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt required")

    TILES_DIR.mkdir(parents=True, exist_ok=True)
    gen_url = _get_image_gen_url()

    steps = req.steps if req.steps is not None else int(_read_visual("image_gen.steps", 4))
    payload: dict[str, Any] = {
        "prompt": req.prompt,
        "width": req.width,
        "height": req.height,
        "steps": steps,
    }
    # Use per-request checkpoint, fall back to DB default
    checkpoint = req.checkpoint if req.checkpoint is not None else _read_visual("image_gen.checkpoint", "")
    if checkpoint:
        payload["checkpoint"] = checkpoint

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            r = await client.post(f"{gen_url}/generate", json=payload)
            r.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail=f"Image generator offline ({gen_url})")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Image generator timeout")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"Generator error: {e.response.text}")

    data = r.json()
    if data.get("status") != "ok":
        raise HTTPException(status_code=502, detail=data.get("error", "generation failed"))

    src_filename = data["filename"]
    ts = int(time.time())
    dest_name = f"aigm_{ts}_{src_filename}"
    dest_path = TILES_DIR / dest_name

    # Flask API v2 includes b64 image data — write directly, no file-system sharing needed
    b64_data = data.get("b64")
    if b64_data:
        dest_path.write_bytes(base64.b64decode(b64_data))
    else:
        # Fallback: download via /files endpoint on Flask API
        async with httpx.AsyncClient(timeout=60) as dl:
            resp = await dl.get(f"{gen_url}/files/{src_filename}")
            if resp.status_code == 200:
                dest_path.write_bytes(resp.content)
            else:
                raise HTTPException(status_code=500, detail="Could not retrieve generated image")

    url = f"{TILES_URL_PREFIX}/{dest_name}"
    return {"status": "ok", "filename": dest_name, "url": url}


@router.post("/refine")
async def refine_image(req: RefineRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt required")
    if "/" in req.source_filename or "\\" in req.source_filename:
        raise HTTPException(status_code=400, detail="invalid filename")

    src_path = TILES_DIR / req.source_filename
    if not src_path.exists():
        raise HTTPException(status_code=404, detail="source image not found")

    image_b64 = base64.b64encode(src_path.read_bytes()).decode()

    steps = req.steps if req.steps is not None else int(_read_visual("image_gen.refine_steps", 8))
    ref_url = _get_image_gen_url()
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            r = await client.post(f"{ref_url}/refine", json={
                "prompt": req.prompt,
                "image_b64": image_b64,
                "denoise": req.denoise,
                "steps": steps,
            })
            r.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail=f"Image generator offline ({ref_url})")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Image generator timeout")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"Generator error: {e.response.text}")

    data = r.json()
    if data.get("status") != "ok":
        raise HTTPException(status_code=502, detail=data.get("error", "refine failed"))

    TILES_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    dest_name = f"aigm_{ts}_refined_{data['filename']}"
    dest_path = TILES_DIR / dest_name

    b64_data = data.get("b64")
    if b64_data:
        dest_path.write_bytes(base64.b64decode(b64_data))
    else:
        async with httpx.AsyncClient(timeout=60) as dl:
            resp = await dl.get(f"{ref_url}/files/{data['filename']}")
            if resp.status_code == 200:
                dest_path.write_bytes(resp.content)
            else:
                raise HTTPException(status_code=500, detail="Could not retrieve refined image")

    url = f"{TILES_URL_PREFIX}/{dest_name}"
    return {"status": "ok", "filename": dest_name, "url": url}


class RefineUploadRequest(BaseModel):
    prompt: str
    upload_b64: str            # base64 image uploaded from browser
    ext: str = "png"
    denoise: float = 0.6
    steps: int = 8


@router.post("/refine-upload")
async def refine_uploaded(req: RefineUploadRequest):
    """Refine using an image uploaded directly from the browser."""
    if not req.prompt.strip() or not req.upload_b64:
        raise HTTPException(status_code=400, detail="prompt and upload_b64 required")

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            r = await client.post(f"{IMAGE_GEN_URL}/refine", json={
                "prompt": req.prompt,
                "image_b64": req.upload_b64,
                "denoise": req.denoise,
                "steps": req.steps,
            })
            r.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Image generator offline")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Image generator timeout")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"Generator error: {e.response.text}")

    data = r.json()
    if data.get("status") != "ok":
        raise HTTPException(status_code=502, detail=data.get("error", "refine failed"))

    TILES_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    dest_name = f"aigm_{ts}_ref_{data['filename']}"
    dest_path = TILES_DIR / dest_name

    b64_data = data.get("b64")
    if b64_data:
        dest_path.write_bytes(base64.b64decode(b64_data))
    else:
        async with httpx.AsyncClient(timeout=60) as dl:
            resp = await dl.get(f"{IMAGE_GEN_URL}/files/{data['filename']}")
            if resp.status_code == 200:
                dest_path.write_bytes(resp.content)
            else:
                raise HTTPException(status_code=500, detail="Could not retrieve image")

    url = f"{TILES_URL_PREFIX}/{dest_name}"
    return {"status": "ok", "filename": dest_name, "url": url}


class DescribePromptRequest(BaseModel):
    text: str           # Polish description text
    context: str = ""   # optional extra context (location type, biome etc.)


@router.post("/describe-prompt")
async def describe_prompt(req: DescribePromptRequest):
    """Translate Polish location description → English image-gen keywords via LLM."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text required")

    from app.services.llm_service import generate_chat

    system = (
        "You are a visual prompt engineer for fantasy RPG image generation. "
        "The user will give you a Polish description of a game location OR a character "
        "(NPC, enemy, creature). The [Context: ...] line tells you which. "
        "Your job: extract the visual essence and output ONLY a short English comma-separated "
        "list of image generation keywords (15-30 words max). "
        "For a character: focus on who/what they are, appearance, clothing/armor, age, gender, "
        "role, expression, mood. For a location: focus on setting, atmosphere, lighting, "
        "architecture, nature elements, mood. "
        "Always reflect the actual subject described — do not output generic adventurer keywords. "
        "No explanations. No Polish words. No sentences. Only English keywords."
    )
    user_msg = req.text.strip()
    if req.context:
        user_msg = f"[Context: {req.context}]\n\n{user_msg}"

    try:
        reply = generate_chat(messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    keywords = reply.strip().strip(".,")
    return {"keywords": keywords}


@router.get("/list")
async def list_images():
    TILES_DIR.mkdir(parents=True, exist_ok=True)
    images = []
    for f in sorted(TILES_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            images.append({
                "filename": f.name,
                "url": f"{TILES_URL_PREFIX}/{f.name}",
                "size": f.stat().st_size,
                "created_at": int(f.stat().st_mtime),
            })
    return {"images": images}


@router.get("/models")
async def list_models():
    """Proxy to image gen service /models — returns available checkpoints with metadata."""
    url = _get_image_gen_url()
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"{url}/models")
            r.raise_for_status()
            return {"models": r.json()}
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"Image generator offline ({url})")
    except Exception as ex:
        raise HTTPException(status_code=502, detail=str(ex))


@router.post("/remove-bg/{filename}")
async def remove_background(filename: str, threshold: int = 30, feather: int = 35):
    """Remove near-black background from a tile image, returning new PNG with alpha.
    threshold: pixels with max(R,G,B) < threshold become fully transparent (default 30).
    feather: soft edge width above threshold (default 35).
    """
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="invalid filename")
    threshold = max(0, min(120, threshold))
    feather = max(1, min(80, feather))
    src_path = TILES_DIR / filename
    if not src_path.exists():
        raise HTTPException(status_code=404, detail="not found")

    try:
        from PIL import Image, ImageChops
    except ImportError:
        raise HTTPException(status_code=500, detail="Pillow not installed")

    img = Image.open(src_path).convert("RGBA")
    r, g, b, _ = img.split()
    max_rgb = ImageChops.lighter(r, ImageChops.lighter(g, b))

    mask = max_rgb.point(lambda p:
        0 if p < threshold else
        255 if p > threshold + feather else
        int(255 * (p - threshold) / feather)
    )
    img.putalpha(mask)

    ts = int(time.time())
    base = filename if not filename.endswith(".png") else filename[:-4]
    dest_name = f"aigm_{ts}_nobg_{base}.png"
    dest_path = TILES_DIR / dest_name
    TILES_DIR.mkdir(parents=True, exist_ok=True)
    img.save(str(dest_path), "PNG")

    url = f"{TILES_URL_PREFIX}/{dest_name}"
    return {"status": "ok", "filename": dest_name, "url": url}


@router.delete("/{filename}")
async def delete_image(filename: str):
    # Safety: no path traversal
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="invalid filename")
    path = TILES_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    path.unlink()
    return {"status": "ok"}


# ── Per-enemy image generation ────────────────────────────────────────────────

class EnemyGenerateRequest(BaseModel):
    force: bool = False   # regenerate even if image_url already set
    steps: int | None = None
    width: int | None = None   # None → read from image_gen.portrait_width config (default 576)
    height: int | None = None  # None → read from image_gen.portrait_height config (default 1024)


@router.get("/enemy/missing")
async def list_enemies_missing_images():
    """List active enemies without image_url (for batch generation)."""
    with sqlite3.connect(_DB_PATH) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT key, label, tier, description, image_url, image_gen_prompt "
            "FROM game_config_enemies "
            "WHERE (image_url IS NULL OR image_url = '') AND is_active = 1 "
            "ORDER BY key"
        ).fetchall()
    return {"enemies": [dict(r) for r in rows], "count": len(rows)}


@router.post("/enemy/{key}/generate")
async def generate_enemy_image(key: str, req: EnemyGenerateRequest = Body(default=None)):
    """Generate portrait for an enemy. Saves image_url + image_gen_prompt to DB.
    Skips (status=skipped) if image already exists unless force=true.
    """
    if req is None:
        req = EnemyGenerateRequest()

    with sqlite3.connect(_DB_PATH) as c:
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM game_config_enemies WHERE key = ?", (key,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Enemy not found: {key}")
    row = dict(row)

    if row.get("image_url") and not req.force:
        return {"status": "skipped", "key": key, "reason": "already has image", "image_url": row["image_url"]}

    # Use saved prompt if available, else generate via LLM
    saved_prompt = (row.get("image_gen_prompt") or "").strip()
    if not saved_prompt:
        description = (row.get("description") or row.get("label") or key).strip()
        tier = row.get("tier") or "standard"
        from app.services.llm_service import generate_chat
        system = (
            "You are a visual prompt engineer for dark fantasy RPG image generation. "
            "The user will give you a Polish description of a monster or enemy creature. "
            "Output ONLY a short English comma-separated list of image generation keywords (20-35 words). "
            "Focus on: creature appearance, armor/weapons, dark atmosphere, dramatic lighting. "
            "End with: character portrait, dramatic side lighting, dark fantasy illustration, no text, no UI. "
            "No explanations. No Polish words. No full sentences. Only English keywords."
        )
        user_msg = f"[Context: enemy tier:{tier}, type:creature]\n\n{description}"
        try:
            reply = generate_chat(messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ])
            keywords = reply.strip().strip(".,")
            saved_prompt = keywords + ", character portrait, dramatic side lighting, dark fantasy illustration, no text, no UI"
        except Exception:
            label = row.get("label") or key
            saved_prompt = (
                f"{label}, fantasy creature, dark atmosphere, "
                "character portrait, dramatic side lighting, dark fantasy illustration, no text, no UI"
            )

    steps = req.steps if req.steps is not None else int(_read_visual("image_gen.steps", 4))
    width = req.width if req.width is not None else int(_read_visual("image_gen.portrait_width", 576))
    height = req.height if req.height is not None else int(_read_visual("image_gen.portrait_height", 1024))
    checkpoint = str(_read_visual("image_gen.checkpoint", "") or "")
    gen_url = _get_image_gen_url()

    payload: dict[str, Any] = {
        "prompt": saved_prompt,
        "width": width,
        "height": height,
        "steps": steps,
    }
    if checkpoint:
        payload["checkpoint"] = checkpoint

    TILES_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            r = await client.post(f"{gen_url}/generate", json=payload)
            r.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail=f"Image generator offline ({gen_url})")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Image generator timeout")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"Generator error: {e.response.text}")

    data = r.json()
    if data.get("status") != "ok":
        raise HTTPException(status_code=502, detail=data.get("error", "generation failed"))

    ts = int(time.time())
    dest_name = f"aigm_{ts}_{data['filename']}"
    dest_path = TILES_DIR / dest_name

    b64_data = data.get("b64")
    if b64_data:
        dest_path.write_bytes(base64.b64decode(b64_data))
    else:
        async with httpx.AsyncClient(timeout=60) as dl:
            resp = await dl.get(f"{gen_url}/files/{data['filename']}")
            if resp.status_code == 200:
                dest_path.write_bytes(resp.content)
            else:
                raise HTTPException(status_code=500, detail="Could not retrieve generated image")

    image_url = f"{TILES_URL_PREFIX}/{dest_name}"

    with sqlite3.connect(_DB_PATH) as c:
        c.execute(
            "UPDATE game_config_enemies SET image_url = ?, image_gen_prompt = ?, updated_at = datetime('now') WHERE key = ?",
            (image_url, saved_prompt, key),
        )

    return {"status": "ok", "key": key, "image_url": image_url, "image_gen_prompt": saved_prompt}


async def _run_flux_generate(prompt: str, width: int, height: int, steps: int) -> str:
    """Call FLUX service, save PNG to TILES_DIR, return image_url. Raises HTTPException on error."""
    checkpoint = str(_read_visual("image_gen.checkpoint", "") or "")
    gen_url = _get_image_gen_url()
    payload: dict[str, Any] = {"prompt": prompt, "width": width, "height": height, "steps": steps}
    if checkpoint:
        payload["checkpoint"] = checkpoint

    TILES_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            r = await client.post(f"{gen_url}/generate", json=payload)
            r.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail=f"Image generator offline ({gen_url})")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Image generator timeout")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"Generator error: {e.response.text}")

    data = r.json()
    if data.get("status") != "ok":
        raise HTTPException(status_code=502, detail=data.get("error", "generation failed"))

    ts = int(time.time())
    dest_name = f"aigm_{ts}_{data['filename']}"
    dest_path = TILES_DIR / dest_name
    b64_data = data.get("b64")
    if b64_data:
        dest_path.write_bytes(base64.b64decode(b64_data))
    else:
        async with httpx.AsyncClient(timeout=60) as dl:
            resp = await dl.get(f"{gen_url}/files/{data['filename']}")
            if resp.status_code == 200:
                dest_path.write_bytes(resp.content)
            else:
                raise HTTPException(status_code=500, detail="Could not retrieve generated image")
    return f"{TILES_URL_PREFIX}/{dest_name}"


# ── Per-NPC image generation ──────────────────────────────────────────────────

class NpcGenerateRequest(BaseModel):
    force: bool = False
    steps: int | None = None
    width: int | None = None
    height: int | None = None


@router.get("/npc/missing")
async def list_npcs_missing_images():
    """List active NPCs without image_url (for batch generation)."""
    with sqlite3.connect(_DB_PATH) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT id, key, label, npc_type, description, image_url, image_gen_prompt "
            "FROM npcs "
            "WHERE (image_url IS NULL OR image_url = '') AND is_active = 1 "
            "ORDER BY label"
        ).fetchall()
    return {"npcs": [dict(r) for r in rows], "count": len(rows)}


@router.post("/npc/{npc_id}/generate")
async def generate_npc_image(npc_id: int, req: NpcGenerateRequest = Body(default=None)):
    """Generate portrait for an NPC. Saves image_url + image_gen_prompt to DB.
    Skips (status=skipped) if image already exists unless force=true.
    """
    if req is None:
        req = NpcGenerateRequest()

    with sqlite3.connect(_DB_PATH) as c:
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM npcs WHERE id = ?", (npc_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"NPC not found: {npc_id}")
    row = dict(row)

    if row.get("image_url") and not req.force:
        return {"status": "skipped", "id": npc_id, "reason": "already has image", "image_url": row["image_url"]}

    saved_prompt = (row.get("image_gen_prompt") or "").strip()
    if not saved_prompt:
        description = (row.get("description") or row.get("label") or row.get("key") or "").strip()
        npc_type = row.get("npc_type") or "neutral"
        from app.services.llm_service import generate_chat
        system = (
            "You are a visual prompt engineer for fantasy RPG NPC portrait generation. "
            "The user will give you a Polish description of a friendly or neutral NPC character. "
            "Output ONLY a short English comma-separated list of image generation keywords (20-35 words). "
            "Focus on: character appearance, clothing, expression, warm atmosphere. "
            "End with: character portrait, warm fantasy lighting, detailed illustration, no text, no UI. "
            "No explanations. No Polish words. No full sentences. Only English keywords."
        )
        user_msg = f"[Context: NPC type:{npc_type}]\n\n{description}"
        try:
            reply = generate_chat(messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ])
            keywords = reply.strip().strip(".,")
            saved_prompt = keywords + ", character portrait, warm fantasy lighting, detailed illustration, no text, no UI"
        except Exception:
            label = row.get("label") or row.get("key") or "NPC"
            saved_prompt = (
                f"{label}, fantasy NPC character, "
                "character portrait, warm fantasy lighting, detailed illustration, no text, no UI"
            )

    steps = req.steps if req.steps is not None else int(_read_visual("image_gen.steps", 4))
    width = req.width if req.width is not None else int(_read_visual("image_gen.portrait_width", 576))
    height = req.height if req.height is not None else int(_read_visual("image_gen.portrait_height", 1024))

    image_url = await _run_flux_generate(saved_prompt, width, height, steps)

    with sqlite3.connect(_DB_PATH) as c:
        c.execute(
            "UPDATE npcs SET image_url = ?, image_gen_prompt = ?, updated_at = datetime('now') WHERE id = ?",
            (image_url, saved_prompt, npc_id),
        )

    return {"status": "ok", "id": npc_id, "image_url": image_url, "image_gen_prompt": saved_prompt}


# ── Per-item image generation ─────────────────────────────────────────────────

class ItemGenerateRequest(BaseModel):
    force: bool = False
    steps: int | None = None
    width: int | None = None
    height: int | None = None
    prompt: str | None = None  # custom prompt override; None → LLM builds from item metadata


@router.post("/item/{key}/generate")
async def generate_item_image(key: str, req: ItemGenerateRequest = Body(default=None)):
    """Generate icon for an item. Saves image_url + image_gen_prompt to DB.
    Skips (status=skipped) if image already exists unless force=true.
    """
    if req is None:
        req = ItemGenerateRequest()

    with sqlite3.connect(_DB_PATH) as c:
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM game_config_items WHERE key = ?", (key,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Item not found: {key}")
    row = dict(row)

    if row.get("image_url") and not req.force:
        return {"status": "skipped", "key": key, "reason": "already has image", "image_url": row["image_url"]}

    # Priority: provided prompt > saved prompt > LLM-built prompt
    saved_prompt = (req.prompt or row.get("image_gen_prompt") or "").strip()
    if not saved_prompt:
        description = (row.get("description") or row.get("label") or key).strip()
        item_type = row.get("item_type") or "misc"
        rarity = row.get("rarity") or 1
        rarity_label = {1: "common", 2: "uncommon", 3: "rare", 4: "epic", 5: "legendary"}.get(int(rarity), "common")
        from app.services.llm_service import generate_chat
        system = (
            "You are a visual prompt engineer for dark fantasy RPG game item icon generation. "
            "The user will give you a Polish description of an inventory item. "
            "Output ONLY a short English comma-separated list of image generation keywords (15-25 words). "
            "Focus on: item appearance, material, shape, texture, lighting. "
            "End with: dramatic atmospheric lighting, dark fantasy, isolated on black background, detailed fantasy illustration, no text, no UI. "
            "No explanations. No Polish words. No full sentences. Only English keywords."
        )
        user_msg = f"[Context: item_type:{item_type}, rarity:{rarity_label}]\n\n{description}"
        try:
            reply = generate_chat(messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ])
            keywords = reply.strip().strip(".,")
            saved_prompt = keywords + ", dramatic atmospheric lighting, dark fantasy, isolated on black background, detailed fantasy illustration, no text, no UI"
        except Exception:
            label = row.get("label") or key
            saved_prompt = (
                f"{label}, {item_type}, {rarity_label} rarity, dark fantasy item, "
                "dramatic atmospheric lighting, dark fantasy, isolated on black background, detailed fantasy illustration, no text, no UI"
            )

    steps = req.steps if req.steps is not None else int(_read_visual("image_gen.steps", 4))
    width = req.width if req.width is not None else 512
    height = req.height if req.height is not None else 512

    image_url = await _run_flux_generate(saved_prompt, width, height, steps)

    with sqlite3.connect(_DB_PATH) as c:
        c.execute(
            "UPDATE game_config_items SET image_url = ?, image_gen_prompt = ?, updated_at = datetime('now') WHERE key = ?",
            (image_url, saved_prompt, key),
        )

    return {"status": "ok", "key": key, "image_url": image_url, "image_gen_prompt": saved_prompt}


# ── Per-weapon image generation (#1076) ──────────────────────────────────────

class WeaponGenerateRequest(BaseModel):
    force: bool = False
    steps: int | None = None
    width: int | None = None
    height: int | None = None
    prompt: str | None = None


@router.get("/weapon/missing")
async def list_weapons_missing_images():
    """List active weapons without image_url (for batch generation)."""
    with sqlite3.connect(_DB_PATH) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT key, label, weapon_type, description, image_url, image_gen_prompt "
            "FROM game_config_weapons "
            "WHERE (image_url IS NULL OR image_url = '') AND is_active = 1 "
            "ORDER BY key"
        ).fetchall()
    return {"weapons": [dict(r) for r in rows], "count": len(rows)}


@router.post("/weapon/{key}/generate")
async def generate_weapon_image(key: str, req: WeaponGenerateRequest = Body(default=None)):
    """Generate icon for a weapon. Saves image_url + image_gen_prompt to DB.
    Skips (status=skipped) if image already exists unless force=true.
    """
    if req is None:
        req = WeaponGenerateRequest()

    with sqlite3.connect(_DB_PATH) as c:
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM game_config_weapons WHERE key = ?", (key,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Weapon not found: {key}")
    row = dict(row)

    if row.get("image_url") and not req.force:
        return {"status": "skipped", "key": key, "reason": "already has image", "image_url": row["image_url"]}

    saved_prompt = (req.prompt or row.get("image_gen_prompt") or "").strip()
    if not saved_prompt:
        description = (row.get("description") or row.get("label") or key).strip()
        weapon_type = row.get("weapon_type") or "melee"
        rarity = row.get("rarity") or 1
        rarity_label = {1: "common", 2: "uncommon", 3: "rare", 4: "epic", 5: "legendary"}.get(int(rarity), "common")
        from app.services.llm_service import generate_chat
        system = (
            "You are a visual prompt engineer for dark fantasy RPG game weapon icon generation. "
            "The user will give you a Polish description of a weapon or piece of equipment. "
            "Output ONLY a short English comma-separated list of image generation keywords (15-25 words). "
            "Focus on: weapon shape, material (steel/wood/bone/magic), rarity glow, dark fantasy style. "
            "End with: dramatic atmospheric lighting, dark fantasy, isolated on black background, detailed fantasy illustration, no text, no UI. "
            "No explanations. No Polish words. No full sentences. Only English keywords."
        )
        user_msg = f"[Context: weapon_type:{weapon_type}, rarity:{rarity_label}]\n\n{description}"
        try:
            reply = generate_chat(messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ])
            keywords = reply.strip().strip(".,")
            saved_prompt = keywords + ", dramatic atmospheric lighting, dark fantasy, isolated on black background, detailed fantasy illustration, no text, no UI"
        except Exception:
            label = row.get("label") or key
            saved_prompt = (
                f"{label}, {weapon_type} weapon, {rarity_label} rarity, dark fantasy, "
                "dramatic atmospheric lighting, dark fantasy, isolated on black background, detailed fantasy illustration, no text, no UI"
            )

    steps = req.steps if req.steps is not None else int(_read_visual("image_gen.steps", 4))
    width = req.width if req.width is not None else 512
    height = req.height if req.height is not None else 512

    image_url = await _run_flux_generate(saved_prompt, width, height, steps)

    with sqlite3.connect(_DB_PATH) as c:
        c.execute(
            "UPDATE game_config_weapons SET image_url = ?, image_gen_prompt = ?, updated_at = datetime('now') WHERE key = ?",
            (image_url, saved_prompt, key),
        )

    return {"status": "ok", "key": key, "image_url": image_url, "image_gen_prompt": saved_prompt}


# ── Per-consumable image generation (#1076) ───────────────────────────────────

class ConsumableGenerateRequest(BaseModel):
    force: bool = False
    steps: int | None = None
    width: int | None = None
    height: int | None = None
    prompt: str | None = None


@router.get("/consumable/missing")
async def list_consumables_missing_images():
    """List active consumables without image_url (for batch generation)."""
    with sqlite3.connect(_DB_PATH) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT key, label, effect_type, description, image_url, image_gen_prompt "
            "FROM game_config_consumables "
            "WHERE (image_url IS NULL OR image_url = '') AND is_active = 1 "
            "ORDER BY key"
        ).fetchall()
    return {"consumables": [dict(r) for r in rows], "count": len(rows)}


@router.post("/consumable/{key}/generate")
async def generate_consumable_image(key: str, req: ConsumableGenerateRequest = Body(default=None)):
    """Generate icon for a consumable. Saves image_url + image_gen_prompt to DB.
    Skips (status=skipped) if image already exists unless force=true.
    """
    if req is None:
        req = ConsumableGenerateRequest()

    with sqlite3.connect(_DB_PATH) as c:
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM game_config_consumables WHERE key = ?", (key,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Consumable not found: {key}")
    row = dict(row)

    if row.get("image_url") and not req.force:
        return {"status": "skipped", "key": key, "reason": "already has image", "image_url": row["image_url"]}

    saved_prompt = (req.prompt or row.get("image_gen_prompt") or "").strip()
    if not saved_prompt:
        description = (row.get("description") or row.get("label") or key).strip()
        effect_type = row.get("effect_type") or "misc"
        rarity = row.get("rarity") or 1
        rarity_label = {1: "common", 2: "uncommon", 3: "rare", 4: "epic", 5: "legendary"}.get(int(rarity), "common")
        from app.services.llm_service import generate_chat
        system = (
            "You are a visual prompt engineer for dark fantasy RPG game potion/consumable icon generation. "
            "The user will give you a Polish description of a potion, elixir, food, or consumable item. "
            "Output ONLY a short English comma-separated list of image generation keywords (15-25 words). "
            "Focus on: container shape (vial/flask/jar), liquid color, glowing effect, dark fantasy style. "
            "End with: dramatic atmospheric lighting, dark fantasy, isolated on black background, detailed fantasy illustration, no text, no UI. "
            "No explanations. No Polish words. No full sentences. Only English keywords."
        )
        user_msg = f"[Context: effect_type:{effect_type}, rarity:{rarity_label}]\n\n{description}"
        try:
            reply = generate_chat(messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ])
            keywords = reply.strip().strip(".,")
            saved_prompt = keywords + ", dramatic atmospheric lighting, dark fantasy, isolated on black background, detailed fantasy illustration, no text, no UI"
        except Exception:
            label = row.get("label") or key
            saved_prompt = (
                f"{label}, {effect_type} potion, {rarity_label} rarity, glowing flask, dark fantasy, "
                "dramatic atmospheric lighting, dark fantasy, isolated on black background, detailed fantasy illustration, no text, no UI"
            )

    steps = req.steps if req.steps is not None else int(_read_visual("image_gen.steps", 4))
    width = req.width if req.width is not None else 512
    height = req.height if req.height is not None else 512

    image_url = await _run_flux_generate(saved_prompt, width, height, steps)

    with sqlite3.connect(_DB_PATH) as c:
        c.execute(
            "UPDATE game_config_consumables SET image_url = ?, image_gen_prompt = ?, updated_at = datetime('now') WHERE key = ?",
            (image_url, saved_prompt, key),
        )

    return {"status": "ok", "key": key, "image_url": image_url, "image_gen_prompt": saved_prompt}
