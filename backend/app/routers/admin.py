from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.admin_auth import verify_admin_token

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
