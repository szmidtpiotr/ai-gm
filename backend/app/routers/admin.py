from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.admin_auth import verify_admin_token
from app.services.admin_config import list_dc, list_skills, list_stats

router = APIRouter()


class AdminAuthReq(BaseModel):
    token: str


def require_admin_token(
    authorization: str | None = Header(default=None),
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.post("/admin/auth")
def admin_auth(req: AdminAuthReq):
    if not verify_admin_token(req.token):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return {"ok": True}


@router.get("/admin/verify")
def admin_verify(_: None = Depends(require_admin_token)):
    return {"ok": True}


@router.get("/admin/stats")
def admin_stats(_: None = Depends(require_admin_token)):
    return {"items": list_stats()}


@router.get("/admin/skills")
def admin_skills(_: None = Depends(require_admin_token)):
    return {"items": list_skills()}


@router.get("/admin/dc")
def admin_dc(_: None = Depends(require_admin_token)):
    return {"items": list_dc()}
