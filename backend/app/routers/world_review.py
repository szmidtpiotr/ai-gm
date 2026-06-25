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
    get_pending_items,
    approve_entity,
    discard_entity,
    generate_sublocs_for_settlement,
    enrich_sublocs_labels,
    SETTLEMENT_SUBLOC_DEFAULTS,
    SETTLEMENT_SUBTYPES,
    SUBLOC_SAFE_FOR_REST,
    _SUBLOC_LABELS,
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


@router.get("/pending/items")
def pending_items():
    """D1 (#376) — narrative items awaiting admin review."""
    conn = _get_db()
    try:
        return {"items": get_pending_items(conn)}
    finally:
        conn.close()


# ── D4 (#379) — Auto-screening kolejki ────────────────────────────────────────

_PENDING_FETCHER = {
    "item": get_pending_items,
    "weapon": get_pending_weapons,
    "npc": get_pending_npcs,
    "enemy": get_pending_enemies,
    "location": get_pending_locations,
}


class EncounterConfigReq(_BaseModel):
    n_turns_interval: int | None = None
    dwell_settle_turns: int | None = None


@router.get("/encounter-config")
def get_encounter_config_ep():
    """D7 (#382) — bieżący config encounterów (interwał n_turns, dwell)."""
    from app.services.encounter_config_service import get_encounter_config
    return get_encounter_config()


@router.post("/encounter-config")
def set_encounter_config_ep(req: EncounterConfigReq):
    """D7 (#382) — strojenie częstotliwości encounterów z admin3."""
    from app.services.encounter_config_service import set_encounter_config
    try:
        return set_encounter_config(
            n_turns_interval=req.n_turns_interval,
            dwell_settle_turns=req.dwell_settle_turns,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/encounter-templates")
def encounter_templates(level: int = 1, location_tag: str | None = None):
    """D7 (#382) — generyczne encountery pasujące do poziomu + terenu (deterministyczne).
    Jeden punkt prawdy doboru template per teren/poziom dla pipeline'u spotkań."""
    from app.services.encounter_service import match_encounter_templates
    conn = _get_db()
    try:
        cands = match_encounter_templates(conn, level=level, location_tag=location_tag)
        return {"level": level, "location_tag": location_tag,
                "count": len(cands), "candidates": cands}
    finally:
        conn.close()


@router.post("/auto-screen/{entity_type}/{key}")
def auto_screen_one(entity_type: str, key: str, dry_run: bool = False):
    """D4 — screen a single pending record. `dry_run=1` runs L1 only (no LLM, no
    approval) so the contract can be checked deterministically."""
    from app.services.screening_service import (
        auto_screen_record, validate_level1, _load_record,
    )
    conn = _get_db()
    try:
        if dry_run:
            rec = _load_record(conn, entity_type, key)
            if rec is None:
                raise HTTPException(status_code=404, detail="record not found")
            return {
                "dry_run": True, "entity_type": entity_type, "key": key,
                "l1": validate_level1(entity_type, rec),
            }
        return auto_screen_record(conn, entity_type, key)
    finally:
        conn.close()


@router.post("/auto-screen-queue/{entity_type}")
def auto_screen_queue(entity_type: str, dry_run: bool = False):
    """D4 — screen every pending record of a type. Returns per-record decisions
    (dry_run → L1 only). High-score + L1-pass records are auto-approved."""
    from app.services.screening_service import (
        auto_screen_record, validate_level1, _load_record,
    )
    fetcher = _PENDING_FETCHER.get(entity_type)
    if not fetcher:
        raise HTTPException(status_code=400, detail=f"unknown entity_type: {entity_type}")
    conn = _get_db()
    try:
        results = []
        for rec in fetcher(conn):
            key = rec.get("key")
            if not key:
                continue
            if dry_run:
                # Pending-list dicts are column-truncated; L1 needs the full row.
                full = _load_record(conn, entity_type, key) or rec
                results.append({"key": key, "l1": validate_level1(entity_type, full)})
            else:
                results.append(auto_screen_record(conn, entity_type, key))
        approved = sum(1 for r in results if r.get("decision") == "auto_approve")
        return {"entity_type": entity_type, "dry_run": dry_run,
                "screened": len(results), "auto_approved": approved, "results": results}
    finally:
        conn.close()


class ReviewAction(BaseModel):
    action: str  # "approve" or "discard"
    generate_sublocs: list[str] | None = None  # #995: subtypes to auto-generate (location approve only)


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
    if entity_type not in ("location", "npc", "enemy", "weapon", "item"):
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

        # #995: auto-generate sub-locations when approving a settlement location
        generated_sublocs: list[dict] = []
        if req.action == "approve" and entity_type == "location" and req.generate_sublocs:
            generated_sublocs = generate_sublocs_for_settlement(conn, key, req.generate_sublocs)

        return {
            "ok": True, "entity_type": entity_type, "key": key, "action": req.action,
            "generated_sublocs": generated_sublocs,
        }
    finally:
        conn.close()


@router.get("/locations/{key}/subloc-defaults")
def get_subloc_defaults(key: str):
    """#995 — Return default sub-location checklist for a settlement pending review.

    Returns is_settlement=False for non-settlement subtypes so the frontend
    can conditionally show the generation UI.
    """
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT location_subtype FROM game_locations WHERE key = ? AND is_active = 1",
            (key,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Location '{key}' not found")

        subtype = row["location_subtype"] or ""
        defaults = SETTLEMENT_SUBLOC_DEFAULTS.get(subtype, [])
        checklist = [
            {
                "subtype": s,
                "label": _SUBLOC_LABELS.get(s, s.capitalize()),
                "safe_for_rest": SUBLOC_SAFE_FOR_REST.get(s, 0),
                "selected": True,
            }
            for s in defaults
        ]
        return {
            "settlement_subtype": subtype,
            "is_settlement": subtype in SETTLEMENT_SUBTYPES,
            "checklist": checklist,
        }
    finally:
        conn.close()


class EnrichSublocsRequest(_BaseModel):
    subloc_keys: list[str] | None = None


@router.post("/locations/{key}/enrich-sublocs")
def enrich_sublocs(key: str, req: EnrichSublocsRequest = None):
    """#996 — LLM-enrich labels/descriptions for auto-generated sub-locations.

    Calls the LLM with settlement context + sub-location subtypes and
    stores thematic Polish names.  Sub-locs with ai_generated=1 are skipped
    (idempotent).  On LLM failure the sub-locs keep their generic labels.
    """
    if req is None:
        req = EnrichSublocsRequest()
    conn = _get_db()
    try:
        updated = enrich_sublocs_labels(conn, key, subloc_keys=req.subloc_keys)
        return {"enriched": len(updated), "sublocs": updated}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()
