"""Showcase endpoints — email subscribe (W13 #914) + admin CMS (W15 #920)."""
import json
import os
import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path
from app.core.jwt_auth import current_user_optional
from app.services.admin_auth import verify_admin_token

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SHOWCASE_DATA_DIR = Path(os.environ.get("SHOWCASE_DATA_PATH", "/app/showcase_data"))

_ALLOWED_KEYS = frozenset({"historia", "swiat", "changelog", "faq", "roadmap"})


class SubscribeRequest(BaseModel):
    email: str


def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


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


@router.get("/api/showcase/regions")
def showcase_regions():
    """#1484 — publiczna prawda o tym, które krainy są grywalne.

    Wizytówka woła to zamiast ufać ręcznemu polu w `swiat.json`; plik zostaje
    fallbackiem (lustrem), gdy backend nie odpowie.
    """
    from app.services.showcase_region_mirror import public_region_states
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    try:
        return {"regions": public_region_states(conn)}
    finally:
        conn.close()


@router.get("/api/showcase/bestiary")
def showcase_bestiary(user=Depends(current_user_optional)):
    """#1191 / #915 — public bestiary gallery. Anonymous: portrait + name +
    one-sentence teaser. Logged-in game account (unified auth #915): enemies the
    account's heroes have defeated are enriched with full lore + kill count.
    """
    from app.services.bestiary_service import get_showcase_bestiary
    uid = None
    if user:
        try:
            uid = int(user.get("sub"))
        except (TypeError, ValueError):
            uid = None
    return get_showcase_bestiary(uid)


@router.get("/api/admin/showcase/{content}")
def showcase_get(content: str, _: None = Depends(_require_admin)):
    """Return showcase JSON content file for admin editing."""
    if content not in _ALLOWED_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown content key: {content}")
    data_dir = SHOWCASE_DATA_DIR
    path = data_dir / f"{content}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Data file not found: {content}.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read {content}.json: {e}")


@router.put("/api/admin/showcase/{content}")
def showcase_put(content: str, body: dict, _: None = Depends(_require_admin)):
    """Overwrite showcase JSON content file."""
    if content not in _ALLOWED_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown content key: {content}")
    data_dir = SHOWCASE_DATA_DIR
    path = data_dir / f"{content}.json"
    try:
        path.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write {content}.json: {e}")
    return {"ok": True}
