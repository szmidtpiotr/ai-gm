"""Template start-location anchoring (#1206).

A Kuźnia template owns a start hex (campaign_templates.start_hex_q/r, allocated
collision-free by #1094/#1108) but until now nothing materialized the plan's
starting location ON that hex. `_auto_create_forge_locations` (#1092) creates an
unanchored stub — and silently skips when the key is already taken by a location
from another campaign anchored elsewhere. Result: `resolve_starting_hex` finds no
on-hex location, leaves the session unanchored (#1152 rule), and the narrator
grounds the scene in raw hex terrain ("forest") while the GM plan is set in a
tavern — the location-drift bug.

`ensure_template_start_location` closes the gap:
- figures out the plan's start location (first non-optional visit_location beat
  of act 1, falling back to key_locations[0]),
- creates it anchored at the template's start hex, or anchors the template-owned
  unanchored stub,
- on a key conflict (row owned by someone else / anchored to a different hex)
  creates a copy under a unique key and rewrites the template plan (and the
  launching campaign's plan copy, when given) to the new key — never steals a
  location another campaign may be using.

Called from: Kuźnia publish + allocate-hex + set-start-hex (eager), and from
`resolve_starting_hex` at campaign launch (safety net for templates published
before this fix). Writes game_locations + gm_plan_json only — never world_hexes.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from app.core.logging import get_logger

logger = get_logger(__name__)

_OBJ_VISIT = "visit_location"


def _start_location_from_plan(plan: dict) -> "tuple[str, str] | None":
    """Return (key, label) of the plan's starting location, or None.

    Priority: objective_value of the first non-optional visit_location beat of
    act 1 (label looked up in key_locations), else key_locations[0].
    """
    if not isinstance(plan, dict):
        return None
    key_locations = [
        loc for loc in (plan.get("key_locations") or []) if isinstance(loc, dict)
    ]
    labels = {
        str(loc.get("key")): str(loc.get("name") or loc.get("key"))
        for loc in key_locations
        if loc.get("key")
    }

    acts = plan.get("acts") or []
    first_act = acts[0] if acts and isinstance(acts[0], dict) else {}
    for beat in first_act.get("key_beats") or []:
        if (
            isinstance(beat, dict)
            and beat.get("objective_type") == _OBJ_VISIT
            and not beat.get("optional")
            and beat.get("objective_value")
        ):
            key = str(beat["objective_value"])
            return key, labels.get(key, key)

    if key_locations and key_locations[0].get("key"):
        key = str(key_locations[0]["key"])
        return key, labels.get(key, key)
    return None


def _unique_location_key(conn: sqlite3.Connection, base: str) -> str:
    key, i = base, 2
    while conn.execute("SELECT 1 FROM game_locations WHERE key = ?", (key,)).fetchone():
        key = f"{base}_{i}"
        i += 1
    return key


def _rewrite_plan_location_key(plan: dict, old_key: str, new_key: str) -> bool:
    """Rename a location key everywhere the plan references it. Returns True if changed."""
    changed = False
    for act in plan.get("acts") or []:
        if not isinstance(act, dict):
            continue
        for beat in act.get("key_beats") or []:
            if isinstance(beat, dict) and beat.get("objective_value") == old_key:
                beat["objective_value"] = new_key
                changed = True
    for loc in plan.get("key_locations") or []:
        if isinstance(loc, dict) and loc.get("key") == old_key:
            loc["key"] = new_key
            changed = True
    return changed


def _rewrite_stored_plan(
    conn: sqlite3.Connection, table: str, row_id: int, old_key: str, new_key: str
) -> None:
    row = conn.execute(
        f"SELECT gm_plan_json FROM {table} WHERE id = ?", (row_id,)
    ).fetchone()
    raw = row["gm_plan_json"] if row else None
    if not raw:
        return
    try:
        plan = json.loads(raw)
    except Exception:
        return
    if _rewrite_plan_location_key(plan, old_key, new_key):
        conn.execute(
            f"UPDATE {table} SET gm_plan_json = ? WHERE id = ?",
            (json.dumps(plan, ensure_ascii=False), row_id),
        )


def ensure_template_start_location(
    conn: sqlite3.Connection,
    template_id: int,
    campaign_id: "int | None" = None,
) -> "dict | None":
    """Make sure the template's start location exists anchored on its start hex.

    Returns {"key", "status", "q", "r"} (status: ok|created|anchored|copied)
    or None when the template has no start hex / no resolvable start location.
    When `campaign_id` is given (launch-time safety net) a conflict-copy rename
    is also applied to that campaign's own gm_plan_json copy.
    """
    tpl = conn.execute(
        "SELECT id, start_hex_q, start_hex_r, gm_plan_json FROM campaign_templates WHERE id = ?",
        (template_id,),
    ).fetchone()
    if not tpl or tpl["start_hex_q"] is None or tpl["start_hex_r"] is None:
        return None
    try:
        plan = json.loads(tpl["gm_plan_json"] or "{}")
    except Exception:
        return None

    start = _start_location_from_plan(plan)
    if not start:
        return None
    key, label = start
    q, r = int(tpl["start_hex_q"]), int(tpl["start_hex_r"])

    row = conn.execute(
        "SELECT id, key, world_hex_q, world_hex_r, created_by, source_campaign_id "
        "FROM game_locations WHERE key = ?",
        (key,),
    ).fetchone()

    now = datetime.now(timezone.utc).isoformat()

    def _insert(new_key: str) -> None:
        conn.execute(
            """INSERT INTO game_locations
               (key, label, description, review_status, is_active, ai_generated,
                created_by, source_campaign_id, safe_for_rest,
                world_hex_q, world_hex_r, created_at, updated_at)
               VALUES (?, ?, '', 'pending', 1, 1, 'forge', ?, 1, ?, ?, ?, ?)""",
            (new_key, label, template_id, q, r, now, now),
        )

    if row is None:
        _insert(key)
        conn.commit()
        logger.info(
            "template_start_location_created",
            template_id=template_id, key=key, q=q, r=r,
        )
        return {"key": key, "status": "created", "q": q, "r": r}

    anchored = row["world_hex_q"] is not None and row["world_hex_r"] is not None
    if anchored and int(row["world_hex_q"]) == q and int(row["world_hex_r"]) == r:
        return {"key": key, "status": "ok", "q": q, "r": r}

    owned = (
        row["created_by"] == "forge"
        and row["source_campaign_id"] is not None
        and int(row["source_campaign_id"]) == int(template_id)
    )
    if owned:
        # Template-owned stub (or a stale anchor after the start hex moved) —
        # anchoring/moving it cannot break anyone else.
        conn.execute(
            "UPDATE game_locations SET world_hex_q = ?, world_hex_r = ?, "
            "is_active = 1, updated_at = ? WHERE id = ?",
            (q, r, now, row["id"]),
        )
        conn.commit()
        logger.info(
            "template_start_location_anchored",
            template_id=template_id, key=key, q=q, r=r,
        )
        return {"key": key, "status": "anchored", "q": q, "r": r}

    # Key collision with a foreign location (another campaign/template/manual row,
    # possibly anchored on a different hex). Never steal it — materialize a copy
    # under a unique key and rename the reference in the template plan (and the
    # launching campaign's plan copy, if any).
    new_key = _unique_location_key(conn, key)
    _insert(new_key)
    _rewrite_stored_plan(conn, "campaign_templates", template_id, key, new_key)
    if campaign_id is not None:
        _rewrite_stored_plan(conn, "campaigns", int(campaign_id), key, new_key)
    conn.commit()
    logger.warning(
        "template_start_location_key_conflict_copied",
        template_id=template_id, old_key=key, new_key=new_key, q=q, r=r,
        foreign_created_by=row["created_by"],
    )
    return {"key": new_key, "status": "copied", "q": q, "r": r}
