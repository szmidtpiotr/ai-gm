from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.services.admin_auth import verify_admin_token
from app.services.admin_analytics import get_combat, get_dice, get_economy, get_overview

router = APIRouter()


def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.get("/admin/analytics/overview")
def analytics_overview(
    days: int = Query(default=30, ge=1, le=365),
    _: None = Depends(_require_admin),
):
    return get_overview(days)


@router.get("/admin/analytics/dice")
def analytics_dice(
    days: int = Query(default=30, ge=1, le=365),
    _: None = Depends(_require_admin),
):
    return get_dice(days)


@router.get("/admin/analytics/combat")
def analytics_combat(
    days: int = Query(default=30, ge=1, le=365),
    _: None = Depends(_require_admin),
):
    return get_combat(days)


@router.get("/admin/analytics/economy")
def analytics_economy(
    days: int = Query(default=30, ge=1, le=365),
    _: None = Depends(_require_admin),
):
    return get_economy(days)
