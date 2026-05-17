"""
Hex World Builder API — Task 40.
Admin endpoints for the hex grid world map.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.admin_auth import verify_admin_token

DB_PATH = "/data/ai_gm.db"
router = APIRouter(prefix="/api/admin/world", tags=["hex-world"])


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _require_admin(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing auth")
    if not verify_admin_token(authorization.removeprefix("Bearer ").strip()):
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Request models ────────────────────────────────────────────────────────────

class HexCreate(BaseModel):
    q: int
    r: int
    hex_type: str = "plains"
    label: Optional[str] = None
    atmosphere: Optional[str] = None
    encounter_chance: float = 0.15
    encounter_pool: list[str] = []
    location_key: Optional[str] = None
    campaign_id: Optional[int] = None  # if placed by GM mid-session
    created_by_gm: int = 0


class HexUpdate(BaseModel):
    hex_type: Optional[str] = None
    label: Optional[str] = None
    atmosphere: Optional[str] = None
    encounter_chance: Optional[float] = None
    encounter_pool: Optional[list[str]] = None
    location_key: Optional[str] = None
    is_active: Optional[int] = None


class TeleportCreate(BaseModel):
    from_q: int
    from_r: int
    to_q: int
    to_r: int
    travel_type: str = "boat"
    travel_hours: float = 8.0
    encounter_chance: float = 0.20
    requires_item_key: Optional[str] = None
    label: Optional[str] = None
    is_bidirectional: int = 1


class CampaignHexOverlay(BaseModel):
    campaign_id: int
    narrative_encounter: Optional[str] = None
    campaign_label: Optional[str] = None
    campaign_notes: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/map")
def get_world_map(authorization: str | None = Header(default=None)):
    """Full world map: all hexes + teleport connections. Admin only."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        hexes = [dict(r) for r in conn.execute(
            "SELECT * FROM world_hexes WHERE is_active = 1 ORDER BY q, r"
        ).fetchall()]
        for h in hexes:
            try:
                h["encounter_pool"] = json.loads(h.get("encounter_pool") or "[]")
            except Exception:
                h["encounter_pool"] = []

        teleports = [dict(r) for r in conn.execute(
            "SELECT * FROM hex_teleport_connections WHERE is_active = 1"
        ).fetchall()]

        return {"hexes": hexes, "teleport_connections": teleports}
    finally:
        conn.close()


@router.get("/hex-types")
def get_hex_types(authorization: str | None = Header(default=None)):
    """Terrain type config — for admin painting palette."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM hex_type_config WHERE is_active = 1 ORDER BY hex_type"
        ).fetchall()
        return {"hex_types": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.post("/hexes")
def create_hex(body: HexCreate, authorization: str | None = Header(default=None)):
    """Paint a hex on the map."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM world_hexes WHERE q = ? AND r = ?", (body.q, body.r)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"Hex ({body.q},{body.r}) already exists")

        conn.execute(
            """INSERT INTO world_hexes
               (q, r, hex_type, label, atmosphere, encounter_chance, encounter_pool,
                location_key, discovered_in_campaign_id, created_by_gm, created_by_campaign_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (body.q, body.r, body.hex_type, body.label, body.atmosphere,
             body.encounter_chance, json.dumps(body.encounter_pool),
             body.location_key, body.campaign_id, body.created_by_gm, body.campaign_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM world_hexes WHERE q = ? AND r = ?", (body.q, body.r)
        ).fetchone()
        result = dict(row)
        result["encounter_pool"] = json.loads(result.get("encounter_pool") or "[]")
        return {"hex": result}
    finally:
        conn.close()


@router.patch("/hexes/{q}/{r}")
def update_hex(q: int, r: int, body: HexUpdate, authorization: str | None = Header(default=None)):
    """Update a hex's global layer."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        existing = conn.execute(
            "SELECT * FROM world_hexes WHERE q = ? AND r = ?", (q, r)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Hex not found")

        updates = {}
        if body.hex_type is not None: updates["hex_type"] = body.hex_type
        if body.label is not None: updates["label"] = body.label
        if body.atmosphere is not None: updates["atmosphere"] = body.atmosphere
        if body.encounter_chance is not None: updates["encounter_chance"] = body.encounter_chance
        if body.encounter_pool is not None: updates["encounter_pool"] = json.dumps(body.encounter_pool)
        if body.location_key is not None: updates["location_key"] = body.location_key
        if body.is_active is not None: updates["is_active"] = body.is_active

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE world_hexes SET {set_clause} WHERE q = ? AND r = ?",
                list(updates.values()) + [q, r],
            )
            conn.commit()

        row = conn.execute("SELECT * FROM world_hexes WHERE q = ? AND r = ?", (q, r)).fetchone()
        result = dict(row)
        result["encounter_pool"] = json.loads(result.get("encounter_pool") or "[]")
        return {"hex": result}
    finally:
        conn.close()


@router.delete("/hexes/{q}/{r}")
def delete_hex(q: int, r: int, authorization: str | None = Header(default=None)):
    """Delete a hex (blocked if campaign data references it)."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM world_hexes WHERE q = ? AND r = ?", (q, r)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Hex not found")

        # Check campaign references — only block if the referencing campaigns still exist
        refs = conn.execute(
            """SELECT COUNT(*) AS n FROM campaign_hex_data chd
               INNER JOIN campaigns c ON c.id = chd.campaign_id
               WHERE chd.hex_q = ? AND chd.hex_r = ?""",
            (q, r),
        ).fetchone()
        if refs and int(refs["n"]) > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Hex ({q},{r}) is referenced by {refs['n']} active campaign(s). Remove campaign data first.",
            )
        # Clean up orphaned hex data (campaigns deleted but data remains)
        conn.execute(
            "DELETE FROM campaign_hex_data WHERE hex_q = ? AND hex_r = ?", (q, r)
        )

        conn.execute("DELETE FROM world_hexes WHERE q = ? AND r = ?", (q, r))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.post("/hexes/{q}/{r}/overlay")
def set_campaign_overlay(q: int, r: int, body: CampaignHexOverlay, authorization: str | None = Header(default=None)):
    """Set campaign-specific overlay on a hex."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO campaign_hex_data (campaign_id, hex_q, hex_r, narrative_encounter, campaign_label, campaign_notes)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(campaign_id, hex_q, hex_r) DO UPDATE SET
                 narrative_encounter = excluded.narrative_encounter,
                 campaign_label = excluded.campaign_label,
                 campaign_notes = excluded.campaign_notes""",
            (body.campaign_id, q, r, body.narrative_encounter, body.campaign_label, body.campaign_notes),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.post("/teleport-connections")
def create_teleport(body: TeleportCreate, authorization: str | None = Header(default=None)):
    """Create a non-adjacent travel connection (boat, portal, tunnel)."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO hex_teleport_connections
               (from_q, from_r, to_q, to_r, travel_type, travel_hours, encounter_chance,
                requires_item_key, label, is_bidirectional)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (body.from_q, body.from_r, body.to_q, body.to_r, body.travel_type,
             body.travel_hours, body.encounter_chance, body.requires_item_key,
             body.label, body.is_bidirectional),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM hex_teleport_connections WHERE id = last_insert_rowid()"
        ).fetchone()
        return {"connection": dict(row)}
    finally:
        conn.close()


@router.delete("/teleport-connections/{conn_id}")
def delete_teleport(conn_id: int, authorization: str | None = Header(default=None)):
    """Delete a teleport connection."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        conn.execute("DELETE FROM hex_teleport_connections WHERE id = ?", (conn_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ── Player-facing map endpoint ─────────────────────────────────────────────────

@router.get("/player-map/{campaign_id}")
def get_player_map(campaign_id: int, character_id: int = 0):
    """
    Player world map: only discovered hexes + empty outlines for adjacent unvisited.
    Also returns campaign overlays for discovered hexes.
    """
    conn = _get_db()
    try:
        # Get discovered hexes for this campaign
        discovered = {
            (r["hex_q"], r["hex_r"]): dict(r)
            for r in conn.execute(
                "SELECT * FROM campaign_hex_data WHERE campaign_id = ? AND discovered = 1",
                (campaign_id,),
            ).fetchall()
        }

        if not discovered:
            return {"hexes": [], "teleport_connections": [], "current_hex": None}

        # Get all placed hexes that are discovered
        disc_coords = list(discovered.keys())
        placeholders = ",".join(["(?,?)" for _ in disc_coords])
        flat = [x for pair in disc_coords for x in pair]
        discovered_hexes = conn.execute(
            f"SELECT * FROM world_hexes WHERE is_active = 1 AND (q,r) IN ({placeholders})",
            flat,
        ).fetchall() if disc_coords else []

        # Build adjacent "empty outline" hexes (known to exist but unvisited)
        def hex_neighbors(q, r):
            directions = [(1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)]
            return [(q+dq, r+dr) for dq, dr in directions]

        outline_coords = set()
        for (q, r) in discovered.keys():
            for nq, nr in hex_neighbors(q, r):
                if (nq, nr) not in discovered:
                    # Check if hex exists
                    outline_coords.add((nq, nr))

        result_hexes = []
        for h in discovered_hexes:
            d = dict(h)
            d["encounter_pool"] = json.loads(d.get("encounter_pool") or "[]")
            d["status"] = "discovered"
            overlay = discovered.get((d["q"], d["r"]), {})
            if overlay.get("campaign_label"):
                d["display_label"] = overlay["campaign_label"]
            result_hexes.append(d)

        # Add outline stubs
        existing_coords = {(h["q"], h["r"]) for h in result_hexes}
        for (q, r) in outline_coords:
            exists = conn.execute(
                "SELECT id FROM world_hexes WHERE q = ? AND r = ? AND is_active = 1",
                (q, r),
            ).fetchone()
            if exists and (q, r) not in existing_coords:
                result_hexes.append({"q": q, "r": r, "status": "outline", "hex_type": None})

        # Teleport connections (only where at least one endpoint is discovered)
        teleports = conn.execute(
            "SELECT * FROM hex_teleport_connections WHERE is_active = 1"
        ).fetchall()
        visible_teleports = [
            dict(t) for t in teleports
            if (t["from_q"], t["from_r"]) in discovered or (t["to_q"], t["to_r"]) in discovered
        ]

        # Current hex
        char_row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? AND campaign_id = ?",
            (character_id, campaign_id),
        ).fetchone() if character_id else None
        current_hex = None
        if char_row:
            import json as _json
            sheet = _json.loads(char_row["sheet_json"] or "{}")
            current_hex = sheet.get("current_hex")  # {q, r}

        return {
            "hexes": result_hexes,
            "teleport_connections": visible_teleports,
            "current_hex": current_hex,
        }
    finally:
        conn.close()


# ── Chain travel endpoint ─────────────────────────────────────────────────────

class HexTravelReq(BaseModel):
    character_id: int
    destination_q: int
    destination_r: int


@router.post("/campaigns/{campaign_id}/hex-travel")
def hex_chain_travel(campaign_id: int, req: HexTravelReq):
    """
    Chain travel to a destination hex via A* pathfinding.
    Rolls encounters per hex along the route.
    Returns: travel result including narrative context for the narrator.
    """
    import json as _json
    from app.services.hex_travel_service import resolve_chain_travel

    conn = _get_db()
    try:
        # Get character sheet
        char = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? AND campaign_id = ?",
            (req.character_id, campaign_id),
        ).fetchone()
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        sheet = _json.loads(char["sheet_json"] or "{}")

        # Get current hex from session_flags
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        flags = _json.loads((gs["session_flags"] if gs else None) or "{}")
        current_hex_dict = flags.get("current_hex")

        if current_hex_dict:
            from_hex = (int(current_hex_dict["q"]), int(current_hex_dict["r"]))
        else:
            # No hex position yet: place player at origin so pathfinding from (0,0)
            # or use destination directly if no hexes built yet (first placement)
            origin_exists = conn.execute(
                "SELECT 1 FROM world_hexes WHERE q=0 AND r=0 AND is_active=1"
            ).fetchone()
            from_hex = (0, 0) if origin_exists else (req.destination_q, req.destination_r)

        to_hex = (req.destination_q, req.destination_r)

        result = resolve_chain_travel(
            campaign_id=campaign_id,
            character_id=req.character_id,
            from_hex=from_hex,
            to_hex=to_hex,
            character_sheet=sheet,
            conn=conn,
        )

        return result
    finally:
        conn.close()
