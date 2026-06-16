from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.services.admin_auth import verify_admin_token
from app.services.admin_analytics import (
    get_combat,
    get_dashboard,
    get_dice,
    get_economy,
    get_errors,
    get_events,
    get_llm,
    get_overview,
    get_players,
)

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


@router.get("/admin/analytics/events")
def analytics_events(
    days: int = Query(default=30, ge=1, le=365),
    event_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    campaign_id: int | None = Query(default=None),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    _: None = Depends(_require_admin),
):
    return get_events(
        days=days,
        limit=limit,
        event_type=event_type,
        severity=severity,
        campaign_id=campaign_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/admin/analytics/llm")
def analytics_llm(
    days: int = Query(default=1, ge=1, le=365),
    period: str | None = Query(default=None),
    _: None = Depends(_require_admin),
):
    return get_llm(days=days, period=period)


@router.get("/admin/analytics/dashboard")
def analytics_dashboard(_: None = Depends(_require_admin)):
    return get_dashboard()


@router.get("/admin/analytics/players")
def analytics_players(_: None = Depends(_require_admin)):
    return get_players()


@router.get("/admin/analytics/errors")
def analytics_errors(
    limit: int = Query(default=20, ge=1, le=200),
    _: None = Depends(_require_admin),
):
    return get_errors(limit=limit)
