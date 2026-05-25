"""
World Review Queue Router — V2 Phase 03 Task 10

Admin endpoints for reviewing and approving/discarding pending_review
world entities created by the GM during sessions.
"""

import sqlite3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pydantic import BaseModel as _BaseModel
from app.services.world_service import (
    get_pending_review_counts,
    get_pending_locations,
    get_pending_npcs,
    get_pending_enemies,
    get_pending_weapons,
    approve_entity,
    discard_entity,
)

DB_PATH = "/data/ai_gm.db"

router = APIRouter(prefix="/api/admin/world", tags=["admin-world-review"])


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/pending/counts")
def pending_counts():
    """Total count of pending_review entities per type. Used for admin badge."""
    conn = _get_db()
    try:
        counts = get_pending_review_counts(conn)
        counts["total"] = sum(counts.values())
        return counts
    finally:
        conn.close()


@router.get("/pending/locations")
def pending_locations():
    conn = _get_db()
    try:
        return {"items": get_pending_locations(conn)}
    finally:
        conn.close()


@router.get("/pending/npcs")
def pending_npcs():
    conn = _get_db()
    try:
        return {"items": get_pending_npcs(conn)}
    finally:
        conn.close()


@router.get("/pending/enemies")
def pending_enemies():
    conn = _get_db()
    try:
        return {"items": get_pending_enemies(conn)}
    finally:
        conn.close()


@router.get("/pending/weapons")
def pending_weapons():
    conn = _get_db()
    try:
        return {"items": get_pending_weapons(conn)}
    finally:
        conn.close()


class ReviewAction(BaseModel):
    action: str  # "approve" or "discard"


class WeaponPatchReq(_BaseModel):
    label: str | None = None
    damage_die: str | None = None
    weapon_type: str | None = None
    linked_stat: str | None = None
    attack_bonus: int | None = None
    description: str | None = None
    note: str | None = None


@router.patch("/pending/weapons/{key}")
def patch_pending_weapon(key: str, req: WeaponPatchReq):
    """Edit a pending narrative weapon before approving/discarding."""
    conn = _get_db()
    try:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            return {"ok": True}
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE game_config_weapons SET {sets} WHERE key = ? AND review_status = 'pending_review'",
                     list(updates.values()) + [key])
        conn.commit()
        row = conn.execute("SELECT key, label, damage_die, weapon_type, description FROM game_config_weapons WHERE key = ?", (key,)).fetchone()
        return {"ok": True, "weapon": dict(row) if row else {}}
    finally:
        conn.close()


# ── AP1: GET + PATCH for pending NPCs ────────────────────────────────────────

class NpcPendingPatchReq(_BaseModel):
    label: str | None = None
    npc_type: str | None = None
    description: str | None = None
    personality_prompt: str | None = None
    is_active: int | None = None
    # Multi-role capability flags (mirror existing is_shop). `npc_type` is
    # auto-derived from these on save for backward compat with consumers that
    # still read the single-value column.
    is_shop: int | None = None
    is_quest_giver: int | None = None
    is_ally: int | None = None


def _derive_primary_npc_type(is_shop: int, is_quest_giver: int, is_ally: int) -> str:
    """Pick a single primary role for the legacy npc_type column.
    Priority: merchant > quest_giver > ally > neutral."""
    if int(is_shop or 0):
        return "merchant"
    if int(is_quest_giver or 0):
        return "quest_giver"
    if int(is_ally or 0):
        return "ally"
    return "neutral"


@router.get("/pending/npc/{key}")
def get_pending_npc(key: str):
    """Full row for one pending NPC — used by 'Edytuj i Zatwierdź' modal.

    Legacy compatibility: if all role booleans are 0 but `npc_type` is a
    non-neutral value (LLM/raw inserts that didn't set the booleans), derive
    the matching flag so the modal pre-fills correctly. The DB row isn't
    rewritten — that only happens on save.
    """
    conn = _get_db()
    try:
        row = conn.execute(
            """SELECT key, label, npc_type, description, personality_prompt,
                      is_active, is_shop, is_quest_giver, is_ally, review_status
               FROM npcs WHERE key = ?""",
            (key,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="NPC not found")
        item = dict(row)
        flags_sum = int(item.get("is_shop") or 0) + int(item.get("is_quest_giver") or 0) + int(item.get("is_ally") or 0)
        if flags_sum == 0:
            nt = item.get("npc_type") or "neutral"
            if nt == "merchant":    item["is_shop"] = 1
            elif nt == "quest_giver": item["is_quest_giver"] = 1
            elif nt == "ally":      item["is_ally"] = 1
        return {"item": item}
    finally:
        conn.close()


@router.patch("/pending/npcs/{key}")
def patch_pending_npc(key: str, req: NpcPendingPatchReq):
    """Edit a pending NPC before approving/discarding."""
    conn = _get_db()
    try:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        # If any role flag was sent, also (re)derive npc_type so legacy callers
        # see a consistent primary role. Read the current row first so unset
        # flags fall back to the stored value, not to 0.
        role_keys = {"is_shop", "is_quest_giver", "is_ally"}
        if updates.keys() & role_keys:
            cur = conn.execute(
                "SELECT is_shop, is_quest_giver, is_ally FROM npcs WHERE key = ?", (key,)
            ).fetchone()
            cur_flags = dict(cur) if cur else {"is_shop": 0, "is_quest_giver": 0, "is_ally": 0}
            merged = {**cur_flags, **{k: updates[k] for k in role_keys if k in updates}}
            updates["npc_type"] = _derive_primary_npc_type(
                merged.get("is_shop", 0),
                merged.get("is_quest_giver", 0),
                merged.get("is_ally", 0),
            )
        if not updates:
            return {"ok": True}
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE npcs SET {sets} WHERE key = ? AND review_status = 'pending_review'",
            list(updates.values()) + [key],
        )
        conn.commit()
        row = conn.execute(
            "SELECT key, label, npc_type, is_shop, is_quest_giver, is_ally, description FROM npcs WHERE key = ?",
            (key,),
        ).fetchone()
        return {"ok": True, "npc": dict(row) if row else {}}
    finally:
        conn.close()


# ── AP1: GET + PATCH for pending enemies ─────────────────────────────────────

class EnemyPendingPatchReq(_BaseModel):
    label: str | None = None
    tier: str | None = None
    hp_base: int | None = None
    ac_base: int | None = None
    attack_bonus: int | None = None
    damage_die: str | None = None
    damage_type: str | None = None
    xp_award: int | None = None
    description: str | None = None
    note: str | None = None


@router.get("/pending/enemy/{key}")
def get_pending_enemy(key: str):
    """Full row for one pending enemy — used by 'Edytuj i Zatwierdź' modal."""
    conn = _get_db()
    try:
        row = conn.execute(
            """SELECT key, label, tier, hp_base, ac_base, attack_bonus,
                      damage_die, damage_type, xp_award, description, note,
                      review_status
               FROM game_config_enemies WHERE key = ?""",
            (key,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Enemy not found")
        return {"item": dict(row)}
    finally:
        conn.close()


@router.patch("/pending/enemies/{key}")
def patch_pending_enemy(key: str, req: EnemyPendingPatchReq):
    """Edit a pending enemy before approving/discarding."""
    conn = _get_db()
    try:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            return {"ok": True}
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE game_config_enemies SET {sets} WHERE key = ? AND review_status = 'pending_review'",
            list(updates.values()) + [key],
        )
        conn.commit()
        row = conn.execute(
            "SELECT key, label, tier, hp_base FROM game_config_enemies WHERE key = ?", (key,)
        ).fetchone()
        return {"ok": True, "enemy": dict(row) if row else {}}
    finally:
        conn.close()


@router.patch("/locations/{key}/promote-canonical")
def promote_canonical(key: str):
    """Stage 2B-Schema S18 — flip canonical=1 for a location, independent of review_status."""
    conn = _get_db()
    try:
        cursor = conn.execute(
            "UPDATE game_locations SET canonical = 1, updated_at = datetime('now') "
            "WHERE key = ? AND is_active = 1",
            (key,),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Lokalizacja '{key}' nie istnieje")
        return {"ok": True, "key": key, "canonical": True}
    finally:
        conn.close()


@router.post("/review/{entity_type}/{key}")
def review_entity(entity_type: str, key: str, req: ReviewAction):
    """
    Approve or discard a pending_review entity.
    entity_type: location | npc | enemy | weapon
    action: approve | discard
    """
    if entity_type not in ("location", "npc", "enemy", "weapon"):
        raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type}")
    if req.action not in ("approve", "discard"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'discard'")

    conn = _get_db()
    try:
        if req.action == "approve":
            ok = approve_entity(conn, entity_type, key)
        else:
            ok = discard_entity(conn, entity_type, key)

        if not ok:
            raise HTTPException(status_code=404, detail=f"{entity_type} '{key}' not found")
        return {"ok": True, "entity_type": entity_type, "key": key, "action": req.action}
    finally:
        conn.close()
