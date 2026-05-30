"""
Admin image generation — proxy to local FLUX service on .170:8765
Images stored in /usr/share/nginx/html/images/tiles/ (bind-mounted from ./frontend/images/tiles/)
Flask API returns b64-encoded image so no shared filesystem needed.
"""
import os
import time
import base64
import httpx
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/images", tags=["admin-images"])

IMAGE_GEN_URL = os.getenv("IMAGE_GEN_URL", "http://192.168.1.170:8765")
TILES_DIR = Path(os.getenv("IMAGES_TILES_DIR", "/app/tiles"))
TILES_URL_PREFIX = "/images/tiles"


class GenerateRequest(BaseModel):
    prompt: str
    width: int = 512
    height: int = 512
    steps: int = 4


class RefineRequest(BaseModel):
    source_filename: str       # existing tile filename in TILES_DIR
    prompt: str
    denoise: float = 0.6       # 0.1 = subtle tweak, 0.9 = big change
    steps: int = 8


@router.post("/generate")
async def generate_image(req: GenerateRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt required")

    TILES_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            r = await client.post(f"{IMAGE_GEN_URL}/generate", json={
                "prompt": req.prompt,
                "width": req.width,
                "height": req.height,
                "steps": req.steps,
            })
            r.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Image generator offline (192.168.1.170:8765)")
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
            resp = await dl.get(f"{IMAGE_GEN_URL}/files/{src_filename}")
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

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            r = await client.post(f"{IMAGE_GEN_URL}/refine", json={
                "prompt": req.prompt,
                "image_b64": image_b64,
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
    dest_name = f"aigm_{ts}_refined_{data['filename']}"
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
