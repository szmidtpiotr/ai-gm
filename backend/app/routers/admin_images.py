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
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/api/admin/images", tags=["admin-images"])

IMAGE_GEN_URL = os.getenv("IMAGE_GEN_URL", "http://192.168.1.170:8765")
TILES_DIR = Path(os.getenv("IMAGES_TILES_DIR", "/app/tiles"))
TILES_URL_PREFIX = "/images/tiles"
_DB_PATH = Path("/data/ai_gm.db")

_IMAGE_GEN_KEYS = ("image_gen.url", "image_gen.steps", "image_gen.refine_steps", "image_gen.checkpoint")
_IMAGE_GEN_DEFAULTS: dict[str, Any] = {
    "image_gen.url": IMAGE_GEN_URL,
    "image_gen.steps": 4,
    "image_gen.refine_steps": 8,
    "image_gen.checkpoint": "",
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
    }


class ImageConfigPatch(BaseModel):
    url: str | None = None
    steps: int | None = None
    refine_steps: int | None = None
    checkpoint: str | None = None


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


@router.get("/models")
async def list_models():
    url = _get_image_gen_url()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{url}/models")
            r.raise_for_status()
            return {"models": r.json()}
    except Exception as ex:
        return {"models": [], "error": str(ex)}


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
        "The user will give you a Polish description of a game location. "
        "Your job: extract the visual essence and output ONLY a short English comma-separated "
        "list of image generation keywords (15-30 words max). "
        "Focus on: setting, atmosphere, lighting, architecture, nature elements, mood. "
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
