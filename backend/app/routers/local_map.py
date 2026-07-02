"""Local map API — #993 FAZA ML.

Player-facing endpoints for the local hex grid (map_level=1) inside a settlement.

  GET  /api/campaigns/{campaign_id}/local-map
       Returns the local hex grid for the hub the party currently occupies,
       plus the party's current local hex position (if any).

  POST /api/campaigns/{campaign_id}/local-travel
       Move the party to a local hex (+15 min game clock).
       Body: {"hex_id": <world_hexes.id>}
"""
from __future__ import annotations

import json
import random
import sqlite3
from typing import Optional

# PT10 #1120: fallback enemy pool when local hex has no encounter_pool set
_LOCAL_ENCOUNTER_FALLBACK_POOL = ["bandit", "unknown_attacker", "goblin"]

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.local_hex_service import (
    LOCAL_TRAVEL_MINUTES,
    get_hub_hex_id,
    get_local_hexes,
    get_local_hex_for_subloc,
)
from app.services.world_service import maybe_lazy_enrich_subloc

DB_PATH = "/data/ai_gm.db"
router = APIRouter(tags=["local-map"])


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_campaign_session(conn: sqlite3.Connection, campaign_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT id, session_flags, current_location_id FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    return dict(row) if row else None


def _get_location(conn: sqlite3.Connection, location_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM game_locations WHERE id = ? AND is_active = 1", (location_id,)
    ).fetchone()
    return dict(row) if row else None


def _hub_key_for_location(loc: dict) -> Optional[str]:
    """Resolve hub key: if loc is a sub-loc, return parent_key; if macro, return loc.key."""
    if loc.get("location_type") == "sub":
        return loc.get("parent_key")
    return loc["key"]


def _check_local_encounter(target: dict, cleared_local_hexes: list) -> Optional[dict]:
    """PT10 #1120: Roll encounter for a local hex.

    Returns encounter dict {"enemy_key": str, "hex_label": str} if triggered, else None.
    Respects encounter_cleared guard (cleared_local_hexes = list of hex IDs already fought).
    """
    chance = float(target.get("encounter_chance") or 0.0)
    if chance <= 0.0:
        return None

    hex_id = target.get("id")
    if hex_id is not None and hex_id in cleared_local_hexes:
        return None

    if random.random() >= chance:
        return None

    pool = target.get("encounter_pool") or []
    if isinstance(pool, str):
        try:
            pool = json.loads(pool)
        except Exception:
            pool = []
    if not pool:
        pool = _LOCAL_ENCOUNTER_FALLBACK_POOL

    enemy_key = random.choice(pool)
    return {"enemy_key": enemy_key, "hex_label": target.get("label", "sub-lokacja")}


# ── GET /api/campaigns/{id}/local-map ─────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/local-map")
def get_local_map(campaign_id: int):
    """Return local hex grid for the hub the party currently occupies.

    Response:
      {
        "hub_key": str,
        "hub_label": str,
        "hexes": [...],           # map_level=1 world_hexes rows
        "current_local_hex": {...} | null,  # party's local position
        "has_local_map": bool     # false when hub has <2 sub-locs
      }
    """
    conn = _db()
    try:
        session = _get_campaign_session(conn, campaign_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        current_loc_id = session.get("current_location_id")
        if not current_loc_id:
            return {"hub_key": None, "hub_label": None, "hexes": [], "current_local_hex": None, "has_local_map": False}

        loc = _get_location(conn, current_loc_id)
        if not loc:
            return {"hub_key": None, "hub_label": None, "hexes": [], "current_local_hex": None, "has_local_map": False}

        hub_key = _hub_key_for_location(loc)
        if not hub_key:
            return {"hub_key": None, "hub_label": None, "hexes": [], "current_local_hex": None, "has_local_map": False}

        # Resolve hub label
        hub_row = conn.execute(
            "SELECT label FROM game_locations WHERE key = ? AND is_active = 1", (hub_key,)
        ).fetchone()
        hub_label = hub_row["label"] if hub_row else hub_key

        hexes = get_local_hexes(conn, hub_key)

        # Current local hex: read from session_flags.local_hex
        flags = json.loads(session.get("session_flags") or "{}")
        current_local_hex = flags.get("local_hex")

        return {
            "hub_key": hub_key,
            "hub_label": hub_label,
            "hexes": hexes,
            "current_local_hex": current_local_hex,
            "has_local_map": len(hexes) > 0,
        }
    finally:
        conn.close()


# ── POST /api/campaigns/{id}/local-travel ─────────────────────────────────────

class LocalTravelRequest(BaseModel):
    hex_id: int


@router.post("/campaigns/{campaign_id}/local-travel")
def local_travel(campaign_id: int, body: LocalTravelRequest):
    """Move party to a local hex (+15 in-game minutes).

    Validates the target hex is map_level=1 and belongs to the hub the party
    is currently in.  Updates session_flags.local_hex and advances the clock.

    Response:
      {
        "moved": bool,
        "local_hex": {...},
        "location_key": str,
        "clock": {...}
      }
    """
    conn = _db()
    try:
        # Load target hex
        target_row = conn.execute(
            "SELECT * FROM world_hexes WHERE id = ? AND map_level = 1 AND is_active = 1",
            (body.hex_id,),
        ).fetchone()
        if not target_row:
            raise HTTPException(status_code=404, detail="Local hex not found")
        target = dict(target_row)

        session = _get_campaign_session(conn, campaign_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        current_loc_id = session.get("current_location_id")
        loc = _get_location(conn, current_loc_id) if current_loc_id else None
        hub_key = _hub_key_for_location(loc) if loc else None

        # Verify target hex belongs to this hub
        if hub_key:
            hub_hex_id = get_hub_hex_id(conn, hub_key)
            if hub_hex_id and target.get("parent_hex_id") != hub_hex_id:
                raise HTTPException(status_code=400, detail="Hex does not belong to current hub")

        # Resolve sub-location id if hex has a location_key
        loc_key = target.get("location_key")
        new_loc_id: int | None = None
        if loc_key:
            new_loc_row = conn.execute(
                "SELECT id FROM game_locations WHERE key = ? AND is_active = 1", (loc_key,)
            ).fetchone()
            if new_loc_row:
                new_loc_id = int(new_loc_row["id"])

        # Read current local hex id before updating — for already-here guard (#1115)
        _pre_sf = json.loads(
            (conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone() or {}).get("session_flags") or "{}"
        )
        current_hex_id = (_pre_sf.get("local_hex") or {}).get("hex_id")

        # #1112: atomic position write via canonical service
        from app.services.location_state_service import set_position
        set_position(
            conn,
            campaign_id=campaign_id,
            local_hex={
                "hex_id": target["id"],
                "q": target["q"],
                "r": target["r"],
                "location_key": loc_key,
            },
            current_location_id=new_loc_id,
        )
        # Keep local reference in sync for the return value
        flags = json.loads(
            (conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone() or {}).get("session_flags") or "{}"
        )

        # Advance clock +15 min — skip when player is already at target hex (#1115)
        clock_state: dict = {}
        encounter_result: Optional[dict] = None
        if body.hex_id != current_hex_id:
            try:
                from app.services.clock_service import advance_clock
                clock_state = advance_clock(campaign_id, minutes=LOCAL_TRAVEL_MINUTES, reason="local_travel")
            except Exception as _clk_err:
                pass  # clock must never break movement

            # PT10 #1120: encounter check for risky local hexes
            try:
                cleared_local_hexes = flags.get("cleared_local_hexes") or []
                encounter_result = _check_local_encounter(target, cleared_local_hexes)
                if encounter_result:
                    # Re-read flags after set_position + clock writes
                    _sf_enc = conn.execute(
                        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                        (campaign_id,),
                    ).fetchone()
                    _flags_enc = json.loads((_sf_enc["session_flags"] if _sf_enc else None) or "{}")
                    _flags_enc["local_travel_hint"] = {
                        "destination_label": target.get("label", "sub-lokacja"),
                    }
                    conn.execute(
                        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                        (json.dumps(_flags_enc, ensure_ascii=False), campaign_id),
                    )
            except Exception as _enc_err:
                pass  # encounter check must never break movement

        conn.commit()

        if loc_key:
            try:
                maybe_lazy_enrich_subloc(conn, loc_key)
            except Exception:
                pass  # lazy enrichment must never break movement

        return {
            "moved": True,
            "local_hex": flags.get("local_hex"),
            "location_key": loc_key,
            "clock": clock_state,
            "encounter": encounter_result,
        }
    finally:
        conn.close()
