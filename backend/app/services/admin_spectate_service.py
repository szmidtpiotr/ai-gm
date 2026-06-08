"""Admin spectator + resume — Issue #400.

Lets an admin browse EVERY campaign in the system (active, inactive, or detached
from its hero), preview it read-only, and resume it (re-attach the hero that
played it + reactivate the campaign) so it becomes playable from the frontend
again. A user-picker dropdown filters the list by owner (default: own).

Backend core (część 1). Endpoints + frontend live in the router / player UI.
"""
from __future__ import annotations

import sqlite3
from typing import Any


def is_admin_user(conn: sqlite3.Connection, user_id: int) -> bool:
    """True only when the user exists and has is_admin=1."""
    try:
        row = conn.execute(
            "SELECT COALESCE(is_admin, 0) AS is_admin FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
        return bool(row and int(row["is_admin"]))
    except Exception:
        return False


def list_users(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Users for the admin dropdown (id + display name + admin flag)."""
    rows = conn.execute(
        """
        SELECT id,
               COALESCE(NULLIF(TRIM(display_name), ''), username) AS display_name,
               COALESCE(is_admin, 0) AS is_admin
        FROM users
        ORDER BY id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def list_all_campaigns(
    conn: sqlite3.Connection, user_id: int | None = None
) -> list[dict[str, Any]]:
    """Every campaign with meta (owner, hero, status, last turn).

    `user_id` filters by owner (the dropdown). The hero is resolved from the
    campaign's last turn so even detached campaigns show who played them.
    """
    where = ""
    params: list[Any] = []
    if user_id is not None:
        where = "WHERE c.owner_user_id = ?"
        params.append(int(user_id))

    rows = conn.execute(
        f"""
        SELECT c.id, c.title, c.status, c.owner_user_id,
               u.display_name AS owner_name,
               (SELECT MAX(turn_number) FROM campaign_turns WHERE campaign_id = c.id) AS last_turn,
               (SELECT character_id FROM campaign_turns
                  WHERE campaign_id = c.id AND character_id IS NOT NULL
                  ORDER BY id DESC LIMIT 1) AS character_id,
               c.created_at
        FROM campaigns c
        LEFT JOIN users u ON u.id = c.owner_user_id
        {where}
        ORDER BY c.id DESC
        """,
        params,
    ).fetchall()

    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["last_turn"] = int(d.get("last_turn") or 0)
        cid = d.get("character_id")
        d["character_name"] = None
        if cid:
            cr = conn.execute("SELECT name FROM characters WHERE id = ?", (cid,)).fetchone()
            if cr:
                d["character_name"] = cr["name"]
        out.append(d)
    return out


def resume_campaign(conn: sqlite3.Connection, campaign_id: int) -> dict[str, Any]:
    """Re-attach the campaign's hero and reactivate it so it's playable again.

    Finds the hero by its current attachment, else from the campaign's turn
    history (Hero-First detaches set characters.campaign_id = NULL). Returns
    {ok, campaign_id, character_id} or {ok: False, reason}.
    """
    cid = int(campaign_id)
    camp = conn.execute("SELECT id FROM campaigns WHERE id = ?", (cid,)).fetchone()
    if not camp:
        return {"ok": False, "reason": "campaign_not_found", "campaign_id": cid}

    row = conn.execute(
        "SELECT id FROM characters WHERE campaign_id = ? ORDER BY is_active DESC, id DESC LIMIT 1",
        (cid,),
    ).fetchone()
    char_id = int(row["id"]) if row else None

    if char_id is None:
        hist = conn.execute(
            "SELECT character_id FROM campaign_turns "
            "WHERE campaign_id = ? AND character_id IS NOT NULL ORDER BY id DESC LIMIT 1",
            (cid,),
        ).fetchone()
        if hist and hist["character_id"] is not None:
            char_id = int(hist["character_id"])

    if char_id is None:
        return {"ok": False, "reason": "no_character", "campaign_id": cid}

    conn.execute(
        "UPDATE characters SET campaign_id = ?, status = 'active', is_active = 1 WHERE id = ?",
        (cid, char_id),
    )
    conn.execute("UPDATE campaigns SET status = 'active' WHERE id = ?", (cid,))
    conn.commit()
    return {"ok": True, "campaign_id": cid, "character_id": char_id}
