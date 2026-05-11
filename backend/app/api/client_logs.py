"""
Frontend RUM ingestion endpoint.

POST /api/client-logs   — accepts a single event or a batch from the browser
                          and emits one JSON log line per event so promtail
                          picks them up and ships to Loki.

Designed to be tolerant: never raises on malformed input, applies size caps,
and silently drops oversized payloads. No auth required (anonymous RUM).
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Body, Header, Request

from app.core.logging import get_logger

router = APIRouter()
logger = get_logger("client_rum")

# Hard caps to avoid log spam / abuse.
_MAX_EVENTS_PER_REQUEST = 50
_MAX_FIELD_CHARS = 4000
_ALLOWED_LEVELS = {"debug", "info", "warn", "error"}


def _truncate(value: Any, limit: int = _MAX_FIELD_CHARS) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    s = str(value)
    if len(s) <= limit:
        return s
    return s[:limit] + f"…[+{len(s) - limit}]"


def _normalize_level(raw: Any) -> str:
    s = str(raw or "info").strip().lower()
    if s == "warning":
        s = "warn"
    return s if s in _ALLOWED_LEVELS else "info"


def _emit_one(
    payload: dict[str, Any],
    *,
    user_agent: str,
    client_ip: str,
    received_ts: float,
) -> None:
    if not isinstance(payload, dict):
        return

    level = _normalize_level(payload.get("level"))
    event = _truncate(payload.get("event") or payload.get("name") or "client_event", 200)

    fields: dict[str, Any] = {
        "source": "client",
        "client_event": event,
        "client_ts": payload.get("ts"),
        "received_ts": received_ts,
        "user_agent": _truncate(user_agent, 400),
        "client_ip": client_ip,
    }

    for key in (
        "session_id",
        "page",
        "url",
        "campaign_id",
        "character_id",
        "user_id",
        "screen",
        "ui_trace_id",
        "build",
        "release",
    ):
        if key in payload and payload[key] is not None:
            fields[key] = _truncate(payload[key], 200)

    attrs = payload.get("attrs")
    if isinstance(attrs, dict):
        for k, v in attrs.items():
            if k in fields:
                continue
            try:
                key = str(k)[:64]
            except Exception:
                continue
            fields[f"attr_{key}"] = _truncate(v)

    msg = _truncate(payload.get("message"), _MAX_FIELD_CHARS)
    if msg is not None:
        fields["message"] = msg

    err = payload.get("error")
    if isinstance(err, dict):
        for k in ("name", "message", "stack", "filename", "lineno", "colno"):
            if k in err and err[k] is not None:
                fields[f"err_{k}"] = _truncate(err[k])

    log_method = getattr(logger, level, logger.info)
    try:
        log_method("client_rum", **fields)
    except Exception:
        # Never let logging break the endpoint.
        pass


@router.post("/client-logs")
async def post_client_logs(
    request: Request,
    body: Any = Body(default=None),
    user_agent: str | None = Header(default=None),
) -> dict[str, Any]:
    """
    Accepts either a single event object or `{events: [...]}` batch, or a list.

    Always returns 200 with `{accepted: N}`, even when partial input was malformed.
    """
    received_ts = time.time()
    ip = request.client.host if request.client else ""
    ua = user_agent or request.headers.get("user-agent") or ""

    events: list[Any] = []
    if isinstance(body, dict):
        if isinstance(body.get("events"), list):
            events = body["events"]
        else:
            events = [body]
    elif isinstance(body, list):
        events = body

    if len(events) > _MAX_EVENTS_PER_REQUEST:
        events = events[:_MAX_EVENTS_PER_REQUEST]

    accepted = 0
    for ev in events:
        if isinstance(ev, dict):
            _emit_one(ev, user_agent=ua, client_ip=ip, received_ts=received_ts)
            accepted += 1

    return {"accepted": accepted}
