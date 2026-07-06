"""Upload and serve custom background images for the mobile frontend screens."""
import os
from pathlib import Path

from fastapi import APIRouter, Body, Depends, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.services.admin_auth import verify_admin_token

router = APIRouter()

BACKGROUNDS_DIR = Path("/data/backgrounds")
# #1169 — source dir for the "set background from an existing tile" gallery
# (same tiles listed by /api/admin/images/list).
TILES_DIR = Path(os.getenv("IMAGES_TILES_DIR", "/app/tiles"))
# Stage 9 follow-up: extend to all major screens so admin can theme everything.
ALLOWED_SCREENS = {
    "login", "campaigns", "new-campaign", "wizard", "game",
    "heroes", "settings", "sheet", "death", "victory",
}
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    if not verify_admin_token(authorization.removeprefix("Bearer ").strip()):
        raise HTTPException(status_code=403, detail="Invalid admin token")


def _bg_path(screen: str) -> Path | None:
    for ext in ALLOWED_EXT:
        p = BACKGROUNDS_DIR / f"bg-{screen}{ext}"
        if p.exists():
            return p
    return None


@router.post("/admin/ui/bg/{screen}", status_code=200)
async def upload_background(
    screen: str,
    file: UploadFile,
    _: None = Depends(_require_admin),
):
    if screen not in ALLOWED_SCREENS:
        raise HTTPException(status_code=400, detail=f"Unknown screen '{screen}'. Valid: {sorted(ALLOWED_SCREENS)}")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Use: jpg, png, webp")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_SIZE // 1024 // 1024} MB)")
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)

    # Remove any previous version with a different extension
    for old_ext in ALLOWED_EXT:
        old = BACKGROUNDS_DIR / f"bg-{screen}{old_ext}"
        if old.exists():
            old.unlink()

    dest = BACKGROUNDS_DIR / f"bg-{screen}{ext}"
    dest.write_bytes(content)

    return {"ok": True, "screen": screen, "url": f"/api/ui/bg/{screen}"}


@router.post("/admin/ui/bg/{screen}/from-tile", status_code=200)
def set_background_from_tile(
    screen: str,
    payload: dict = Body(...),
    _: None = Depends(_require_admin),
):
    """#1169 — Set a screen background by copying an existing tile from the gallery.

    The visual settings gallery (system.js) lets the admin pick a generated tile
    instead of uploading a file; it POSTed here with {"filename": "..."} but the
    route never existed (404). Copies TILES_DIR/<filename> → bg-<screen>.<ext>.
    """
    if screen not in ALLOWED_SCREENS:
        raise HTTPException(status_code=400, detail=f"Unknown screen '{screen}'. Valid: {sorted(ALLOWED_SCREENS)}")

    filename = str(payload.get("filename") or "").strip()
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="invalid filename")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Use: jpg, png, webp")

    src = TILES_DIR / filename
    if not src.exists() or not src.is_file():
        raise HTTPException(status_code=404, detail=f"Tile '{filename}' not found")

    BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)
    # Remove any previous version with a different extension
    for old_ext in ALLOWED_EXT:
        old = BACKGROUNDS_DIR / f"bg-{screen}{old_ext}"
        if old.exists():
            old.unlink()

    dest = BACKGROUNDS_DIR / f"bg-{screen}{ext}"
    dest.write_bytes(src.read_bytes())
    return {"ok": True, "screen": screen, "url": f"/api/ui/bg/{screen}"}


@router.delete("/admin/ui/bg/{screen}", status_code=200)
def delete_background(screen: str, _: None = Depends(_require_admin)):
    if screen not in ALLOWED_SCREENS:
        raise HTTPException(status_code=400, detail=f"Unknown screen '{screen}'")
    p = _bg_path(screen)
    if p:
        p.unlink()
    return {"ok": True, "screen": screen}


@router.get("/ui/bg/{screen}")
def serve_background(screen: str):
    if screen not in ALLOWED_SCREENS:
        raise HTTPException(status_code=404, detail="Not found")
    p = _bg_path(screen)
    if not p:
        raise HTTPException(status_code=404, detail="No custom background for this screen")
    return FileResponse(str(p))


@router.get("/ui/backgrounds")
def list_backgrounds():
    result: dict[str, str | None] = {}
    for screen in ALLOWED_SCREENS:
        p = _bg_path(screen)
        result[screen] = f"/api/ui/bg/{screen}" if p else None
    return {"backgrounds": result}
