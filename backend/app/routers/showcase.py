"""Showcase public endpoints — email subscribe (W13 #914)."""
import re
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SubscribeRequest(BaseModel):
    email: str


@router.post("/api/showcase/subscribe")
def subscribe_email(req: SubscribeRequest):
    """Save email to showcase_subscribers. Idempotent on duplicate."""
    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid email address")
    db_path = resolve_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO showcase_subscribers (email) VALUES (?)",
            (email,),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
