"""
Friends router — F1.3 player-to-player friend system.

Endpoints:
- GET    /me/friends                     → {accepted, incoming, outgoing}
- GET    /me/friends/search?q=…          → users matching prefix, with friendship status
- POST   /me/friends/request             → send request (or auto-accept reverse pending)
- POST   /me/friends/{friendship_id}/accept
- DELETE /me/friends/{friendship_id}     → unfriend / decline / cancel sent request

Convention: user_friendships rows are stored with user_a_id < user_b_id (canonical),
so each pair has exactly one row. requester_id identifies who initiated.
"""

import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path
from app.core.jwt_auth import require_current_user
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Cap search results — prevents enumeration / DoS
_SEARCH_MAX_RESULTS = 20


def _db():
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _current_user_id(authorization: str | None) -> int:
    payload = require_current_user(authorization)
    uid = int(payload.get("sub") or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="invalid_token")
    return uid


def _canonical_pair(a: int, b: int) -> tuple[int, int]:
    """Return (lower, higher) so each friendship has exactly one canonical row."""
    return (a, b) if a < b else (b, a)


def _row_status_for(row: sqlite3.Row, viewer_id: int) -> str:
    """Translate a raw friendship row to a status string from viewer's perspective."""
    status = str(row["status"] or "pending")
    if status == "accepted":
        return "accepted"
    requester = int(row["requester_id"] or 0)
    if status == "pending":
        return "pending_outgoing" if requester == viewer_id else "pending_incoming"
    return status  # 'blocked' etc. — pass through


def _serialize_user(row: sqlite3.Row, friendship_id: int | None = None, status: str = "none") -> dict:
    return {
        "id":           int(row["id"]),
        "username":     str(row["username"] or ""),
        "display_name": str(row["display_name"] or row["username"] or ""),
        "avatar_url":   row["avatar_url"] if "avatar_url" in row.keys() else None,
        "status":       status,
        "friendship_id": friendship_id,
    }


# ── List ───────────────────────────────────────────────────────────────────────

@router.get("/me/friends")
def list_friends(authorization: str | None = Header(default=None)):
    """Returns three lists from the current user's perspective:
    - accepted: confirmed friends
    - incoming: pending requests sent TO me
    - outgoing: pending requests I sent
    """
    uid = _current_user_id(authorization)
    conn = _db()
    try:
        rows = conn.execute(
            """
            SELECT f.id AS friendship_id, f.status, f.requester_id, f.created_at,
                   u.id, u.username, u.display_name, u.avatar_url
            FROM user_friendships f
            JOIN users u
              ON u.id = CASE WHEN f.user_a_id = ? THEN f.user_b_id ELSE f.user_a_id END
            WHERE (f.user_a_id = ? OR f.user_b_id = ?)
              AND (u.deleted_at IS NULL)
              AND (COALESCE(u.is_active, 1) = 1)
              AND f.status != 'blocked'
            ORDER BY f.created_at DESC
            """,
            (uid, uid, uid),
        ).fetchall()

        accepted, incoming, outgoing = [], [], []
        for r in rows:
            status = _row_status_for(r, uid)
            payload = _serialize_user(r, friendship_id=int(r["friendship_id"]), status=status)
            if status == "accepted":
                accepted.append(payload)
            elif status == "pending_incoming":
                incoming.append(payload)
            elif status == "pending_outgoing":
                outgoing.append(payload)
        return {"accepted": accepted, "incoming": incoming, "outgoing": outgoing}
    finally:
        conn.close()


# ── Search ─────────────────────────────────────────────────────────────────────

@router.get("/me/friends/search")
def search_users(q: str = "", authorization: str | None = Header(default=None)):
    """Prefix-match users by username or display_name. Excludes self, soft-deleted,
    inactive. Returns up to 20 with the relationship status from viewer's view."""
    uid = _current_user_id(authorization)
    q = (q or "").strip()
    if len(q) < 2:
        return {"results": []}

    conn = _db()
    try:
        like = q + "%"
        rows = conn.execute(
            f"""
            SELECT id, username, display_name, avatar_url
            FROM users
            WHERE id != ?
              AND deleted_at IS NULL
              AND COALESCE(is_active, 1) = 1
              AND (LOWER(username) LIKE LOWER(?) OR LOWER(display_name) LIKE LOWER(?))
            ORDER BY username
            LIMIT {_SEARCH_MAX_RESULTS}
            """,
            (uid, like, like),
        ).fetchall()

        if not rows:
            return {"results": []}

        # Single query for existing friendships involving viewer + any of these matches
        match_ids = [int(r["id"]) for r in rows]
        placeholders = ",".join(["?"] * len(match_ids))
        friendship_rows = conn.execute(
            f"""
            SELECT id, user_a_id, user_b_id, status, requester_id
            FROM user_friendships
            WHERE (user_a_id = ? AND user_b_id IN ({placeholders}))
               OR (user_b_id = ? AND user_a_id IN ({placeholders}))
            """,
            (uid, *match_ids, uid, *match_ids),
        ).fetchall()
        # Map: other_user_id → friendship row
        rel_map: dict[int, sqlite3.Row] = {}
        for fr in friendship_rows:
            other = int(fr["user_b_id"]) if int(fr["user_a_id"]) == uid else int(fr["user_a_id"])
            rel_map[other] = fr

        results = []
        for r in rows:
            uid2 = int(r["id"])
            fr = rel_map.get(uid2)
            if fr is None:
                results.append(_serialize_user(r, status="none"))
            else:
                status = _row_status_for(fr, uid)
                if status == "blocked":
                    continue  # don't surface blocked users in search
                results.append(_serialize_user(r, friendship_id=int(fr["id"]), status=status))
        return {"results": results}
    finally:
        conn.close()


# ── Request ────────────────────────────────────────────────────────────────────

class FriendRequestReq(BaseModel):
    target_user_id: int


@router.post("/me/friends/request")
def request_friend(req: FriendRequestReq, authorization: str | None = Header(default=None)):
    """Send a friend request. If a reverse-pending row exists (the target sent me a
    request first), this acts as an accept. Idempotent if accepted already."""
    uid = _current_user_id(authorization)
    target = int(req.target_user_id)
    if target == uid:
        raise HTTPException(status_code=400, detail="Nie możesz dodać siebie")

    conn = _db()
    try:
        # Verify target exists and is reachable
        t = conn.execute(
            "SELECT id FROM users WHERE id = ? AND deleted_at IS NULL AND COALESCE(is_active, 1) = 1",
            (target,),
        ).fetchone()
        if not t:
            raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")

        a, b = _canonical_pair(uid, target)
        existing = conn.execute(
            "SELECT id, status, requester_id FROM user_friendships WHERE user_a_id = ? AND user_b_id = ?",
            (a, b),
        ).fetchone()

        now = datetime.now(timezone.utc).isoformat()
        if existing is None:
            cur = conn.execute(
                """
                INSERT INTO user_friendships (user_a_id, user_b_id, status, requester_id, created_at)
                VALUES (?, ?, 'pending', ?, ?)
                """,
                (a, b, uid, now),
            )
            conn.commit()
            fid = int(cur.lastrowid)
            logger.info("friend_request_sent", from_user=uid, to_user=target, friendship_id=fid)
            return {"ok": True, "friendship_id": fid, "status": "pending_outgoing"}

        status = str(existing["status"] or "")
        requester = int(existing["requester_id"] or 0)
        if status == "accepted":
            return {"ok": True, "friendship_id": int(existing["id"]), "status": "accepted"}
        if status == "blocked":
            raise HTTPException(status_code=403, detail="Nie można wysłać zaproszenia")
        if status == "pending":
            if requester == uid:
                # I already sent; idempotent
                return {"ok": True, "friendship_id": int(existing["id"]), "status": "pending_outgoing"}
            # Reverse pending — accept it
            conn.execute(
                "UPDATE user_friendships SET status = 'accepted', responded_at = ? WHERE id = ?",
                (now, int(existing["id"])),
            )
            conn.commit()
            logger.info("friend_request_auto_accepted", user=uid, friendship_id=int(existing["id"]))
            return {"ok": True, "friendship_id": int(existing["id"]), "status": "accepted"}
        raise HTTPException(status_code=409, detail=f"Nieznany status: {status}")
    finally:
        conn.close()


# ── Accept ─────────────────────────────────────────────────────────────────────

@router.post("/me/friends/{friendship_id}/accept")
def accept_friend(friendship_id: int, authorization: str | None = Header(default=None)):
    uid = _current_user_id(authorization)
    conn = _db()
    try:
        row = conn.execute(
            "SELECT id, user_a_id, user_b_id, status, requester_id FROM user_friendships WHERE id = ?",
            (friendship_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Zaproszenie nie istnieje")
        if uid != int(row["user_a_id"]) and uid != int(row["user_b_id"]):
            raise HTTPException(status_code=403, detail="Brak dostępu")
        if str(row["status"]) != "pending":
            raise HTTPException(status_code=409, detail=f"Status to '{row['status']}' — nie można zaakceptować")
        if int(row["requester_id"]) == uid:
            raise HTTPException(status_code=400, detail="Nie można zaakceptować własnego zaproszenia")

        conn.execute(
            "UPDATE user_friendships SET status = 'accepted', responded_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), friendship_id),
        )
        conn.commit()
        logger.info("friend_request_accepted", user=uid, friendship_id=friendship_id)
        return {"ok": True, "friendship_id": friendship_id, "status": "accepted"}
    finally:
        conn.close()


# ── Delete (decline / unfriend / cancel) ───────────────────────────────────────

@router.delete("/me/friends/{friendship_id}")
def delete_friendship(friendship_id: int, authorization: str | None = Header(default=None)):
    """Single endpoint covers: decline pending, cancel my outgoing, unfriend accepted."""
    uid = _current_user_id(authorization)
    conn = _db()
    try:
        row = conn.execute(
            "SELECT id, user_a_id, user_b_id, status FROM user_friendships WHERE id = ?",
            (friendship_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Nie znaleziono")
        if uid != int(row["user_a_id"]) and uid != int(row["user_b_id"]):
            raise HTTPException(status_code=403, detail="Brak dostępu")
        conn.execute("DELETE FROM user_friendships WHERE id = ?", (friendship_id,))
        conn.commit()
        logger.info("friendship_deleted", user=uid, friendship_id=friendship_id, prev_status=str(row["status"]))
        return {"ok": True}
    finally:
        conn.close()
