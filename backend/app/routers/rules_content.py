"""Rules-book content overrides (Księga Zasad, /rules/).

Lets an authenticated admin fix narrative text in the static rules page without
editing HTML. Each editable text block on the page has a stable `block_id`; an
override stored here replaces that block's inner HTML at render time.

- GET  /api/rules/content        — public; returns {block_id: html} overrides.
- PUT  /api/admin/rules/content  — admin only; upserts one block override.
- DELETE /api/admin/rules/content/{block_id} — admin only; reverts to original.

Content is admin-authored, but we still strip <script>/<iframe>/on*-handlers as
defence in depth so a stored override can never inject active content.
"""
import re
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.migrations_admin import DB_PATH
from app.services.admin_auth import verify_admin_token

router = APIRouter(prefix="/api", tags=["rules-content"])


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS rules_content (
               block_id   TEXT PRIMARY KEY,
               html       TEXT NOT NULL,
               updated_by TEXT,
               updated_at TEXT NOT NULL DEFAULT (datetime('now'))
           )"""
    )
    return conn


def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


_SCRIPT_RE = re.compile(r"<\s*(script|iframe|object|embed)\b[^>]*>.*?<\s*/\s*\1\s*>", re.I | re.S)
_SELFCLOSE_RE = re.compile(r"<\s*(script|iframe|object|embed)\b[^>]*/?>", re.I)
_ON_ATTR_RE = re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_JS_HREF_RE = re.compile(r"(href|src)\s*=\s*([\"'])\s*javascript:[^\"']*\2", re.I)


def _sanitize(html: str) -> str:
    html = _SCRIPT_RE.sub("", html)
    html = _SELFCLOSE_RE.sub("", html)
    html = _ON_ATTR_RE.sub("", html)
    html = _JS_HREF_RE.sub(r"\1=\2#\2", html)
    return html.strip()


class BlockReq(BaseModel):
    block_id: str
    html: str


@router.get("/rules/content")
def get_rules_content() -> dict:
    """Public — all stored overrides as {block_id: html}."""
    with _conn() as conn:
        rows = conn.execute("SELECT block_id, html FROM rules_content").fetchall()
    return {r["block_id"]: r["html"] for r in rows}


@router.put("/admin/rules/content")
def put_rules_content(req: BlockReq, _: None = Depends(_require_admin)) -> dict:
    bid = (req.block_id or "").strip()
    if not bid or len(bid) > 200:
        raise HTTPException(status_code=400, detail="block_id required (≤200 chars)")
    if len(req.html) > 100_000:
        raise HTTPException(status_code=400, detail="html too large")
    clean = _sanitize(req.html)
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            """INSERT INTO rules_content (block_id, html, updated_by, updated_at)
               VALUES (?, ?, 'admin', ?)
               ON CONFLICT(block_id) DO UPDATE SET html=excluded.html,
                   updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
            (bid, clean, now),
        )
        conn.commit()
    return {"ok": True, "block_id": bid, "html": clean}


@router.delete("/admin/rules/content/{block_id}")
def delete_rules_content(block_id: str, _: None = Depends(_require_admin)) -> dict:
    with _conn() as conn:
        conn.execute("DELETE FROM rules_content WHERE block_id = ?", (block_id,))
        conn.commit()
    return {"ok": True, "block_id": block_id}
