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
before this fix).

#1243: the start/hub location now also claims its OVERWORLD hex canon via
`link_location_to_hex` (hex wins). Previously this wrote only
`game_locations.world_hex_q/r` — under hex-canon that cache would be cleared by
`reconcile_location_hex_links` on the next boot, un-anchoring the start location
(the #1152 drift). Claiming the hex closes that gap at the source. Sub-locations
stay on the FAZA ML local map (map_level=1) via `local_hex_service`.
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
        # #1212 — settlement structure: sub-locations reference their hub via `parent`
        if isinstance(loc, dict) and loc.get("parent") == old_key:
            loc["parent"] = new_key
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

    from app.services.hex_location_link import link_location_to_hex

    if row is None:
        _insert(key)
        link_location_to_hex(conn, key, q, r)  # #1243: claim hex canon
        conn.commit()
        logger.info(
            "template_start_location_created",
            template_id=template_id, key=key, q=q, r=r,
        )
        return {"key": key, "status": "created", "q": q, "r": r}

    anchored = row["world_hex_q"] is not None and row["world_hex_r"] is not None
    if anchored and int(row["world_hex_q"]) == q and int(row["world_hex_r"]) == r:
        link_location_to_hex(conn, key, q, r)  # #1243: ensure hex canon matches cache
        conn.commit()
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
        link_location_to_hex(conn, key, q, r)  # #1243: claim hex canon
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
    link_location_to_hex(conn, new_key, q, r)  # #1243: claim hex canon for the copy
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


# ── #1212 — settlement structure: hub + sub-locations → FAZA ML local map ─────

def _plan_settlement_structure(plan: dict) -> "dict | None":
    """Extract {hub: {...}, subs: [...]} from key_locations scale/parent fields.

    Returns None when the plan declares no hub or fewer than 1 sub — the caller
    then falls back to the flat #1206 start-anchor behavior. `parent` on a sub
    defaults to the hub key.
    """
    if not isinstance(plan, dict):
        return None
    locs = [l for l in (plan.get("key_locations") or []) if isinstance(l, dict) and l.get("key")]
    hubs = [l for l in locs if l.get("scale") == "hub"]
    if not hubs:
        return None
    hub = hubs[0]
    subs = [
        l for l in locs
        if l.get("scale") == "sub"
        and (l.get("parent") or hub["key"]) == hub["key"]
    ]
    if not subs:
        return None
    return {"hub": hub, "subs": subs}


def _template_owns_row(row, template_id: int, start_q: int, start_r: int) -> bool:
    """A game_locations row this template may safely restructure:
    its own forge stub, or the row materialized on its start hex (#1206 era)."""
    if (
        row["created_by"] == "forge"
        and row["source_campaign_id"] is not None
        and int(row["source_campaign_id"]) == int(template_id)
    ):
        return True
    return (
        row["world_hex_q"] is not None
        and int(row["world_hex_q"]) == start_q
        and int(row["world_hex_r"]) == start_r
    )


def ensure_template_location_structure(
    conn: sqlite3.Connection,
    template_id: int,
    campaign_id: "int | None" = None,
) -> "dict | None":
    """#1212 — materialize the plan's settlement: hub anchored on the start hex,
    sub-locations (parent_key → hub) on the FAZA ML local map (map_level=1).

    Returns {"hub_key", "start_key", "sub_keys", "q", "r"} or None when the plan
    declares no hub/sub structure (caller falls back to
    `ensure_template_start_location`). Idempotent; key conflicts with foreign
    locations follow the #1206 rule (unique-key copy + plan rewrite, never steal).
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

    struct = _plan_settlement_structure(plan)
    if not struct:
        return None
    q, r = int(tpl["start_hex_q"]), int(tpl["start_hex_r"])
    now = datetime.now(timezone.utc).isoformat()
    renames: list[tuple[str, str]] = []

    def _materialize(loc: dict, *, is_hub: bool) -> str:
        key = str(loc["key"])
        label = str(loc.get("name") or key)
        desc = str(loc.get("description") or loc.get("role") or "")
        loc_type = "macro" if is_hub else "sub"
        parent_key = None if is_hub else str(struct["hub"]["key"])
        hex_q, hex_r = (q, r) if is_hub else (None, None)
        # start sub = safe (tavern-like start); other subs default risky
        safe = 1 if is_hub or key == start_key else 0

        # #1292 — resolve the hub's integer id so sub-locations carry BOTH parent_key
        # AND parent_id. The hub is materialized before the subs, so its row exists.
        # Without parent_id, every parent_id-based location path (declared-move hub-sub
        # resolver, rest anchor, etc.) silently failed and "idę do X" resolved to
        # foreign floating orphans instead of the plan's own sub-locations.
        parent_id = None
        if parent_key:
            _prow = conn.execute(
                "SELECT id FROM game_locations WHERE key = ? AND is_active = 1 LIMIT 1",
                (parent_key,),
            ).fetchone()
            if _prow:
                parent_id = _prow["id"]

        row = conn.execute(
            "SELECT id, key, world_hex_q, world_hex_r, created_by, source_campaign_id, "
            "location_type, parent_key, parent_id FROM game_locations WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            conn.execute(
                """INSERT INTO game_locations
                   (key, label, description, location_type, parent_key, parent_id,
                    review_status, is_active, ai_generated, created_by,
                    source_campaign_id, safe_for_rest, world_hex_q, world_hex_r,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', 1, 1, 'forge', ?, ?, ?, ?, ?, ?)""",
                (key, label, desc, loc_type, parent_key, parent_id,
                 template_id, safe, hex_q, hex_r, now, now),
            )
            return key
        # Already in the desired shape (earlier materialization of THIS structure) —
        # idempotent no-op. Without this check a restructured sub (world anchor
        # cleared, foreign created_by) failed the ownership test on every next
        # campaign launch and spawned a `_2` copy (dwie karczmy — #1212 regres).
        if (
            (row["location_type"] or "macro") == loc_type
            and (row["parent_key"] or None) == parent_key
            and (row["parent_id"] if row["parent_id"] is not None else None) == parent_id
            and (row["world_hex_q"] is None) == (hex_q is None)
            and (
                hex_q is None
                or (int(row["world_hex_q"]) == hex_q and int(row["world_hex_r"]) == hex_r)
            )
        ):
            return key
        if _template_owns_row(row, template_id, q, r):
            conn.execute(
                "UPDATE game_locations SET location_type = ?, parent_key = ?, parent_id = ?, "
                "world_hex_q = ?, world_hex_r = ?, is_active = 1, updated_at = ? "
                "WHERE id = ?",
                (loc_type, parent_key, parent_id, hex_q, hex_r, now, row["id"]),
            )
            return key
        # foreign row under this key → #1206 conflict rule: copy + rename in plans
        new_key = _unique_location_key(conn, key)
        conn.execute(
            """INSERT INTO game_locations
               (key, label, description, location_type, parent_key, parent_id,
                review_status, is_active, ai_generated, created_by,
                source_campaign_id, safe_for_rest, world_hex_q, world_hex_r,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', 1, 1, 'forge', ?, ?, ?, ?, ?, ?)""",
            (new_key, label, desc, loc_type, parent_key, parent_id,
             template_id, safe, hex_q, hex_r, now, now),
        )
        renames.append((key, new_key))
        return new_key

    # plan's start location (visit beat of act 1) — usually one of the subs
    _start = _start_location_from_plan(plan)
    start_key = _start[0] if _start else str(struct["subs"][0]["key"])

    hub_key = _materialize(struct["hub"], is_hub=True)
    sub_keys = [_materialize(s, is_hub=False) for s in struct["subs"]]

    # apply conflict renames to THIS campaign's plan copy only (and start_key).
    # #1292: renaming campaign_templates here was a bug — a key collision hit by
    # ONE campaign launch (e.g. a stray foreign location happening to share a key)
    # permanently mutated the SHARED, reusable template in the Forge, poisoning
    # every future campaign started from it with the renamed key forever. The
    # conflict is per-launch and must stay scoped to this campaign's own copy.
    for old_key, new_key in renames:
        if campaign_id is not None:
            _rewrite_stored_plan(conn, "campaigns", int(campaign_id), old_key, new_key)
        if start_key == old_key:
            start_key = new_key
        if hub_key == old_key:
            hub_key = new_key
    # #1243: the hub sits on the overworld start hex — claim hex canon so the
    # derived cache is not cleared by reconcile on the next boot. (Subs are
    # map_level=1, handled by local_hex_service below — out of hex-canon scope.)
    from app.services.hex_location_link import link_location_to_hex
    link_location_to_hex(conn, hub_key, q, r)
    conn.commit()

    # FAZA ML: build the local map now (threshold #993 — needs ≥2 subs)
    try:
        from app.services.local_hex_service import auto_assign_local_hex
        anchor_sub = start_key if start_key in sub_keys else sub_keys[0]
        auto_assign_local_hex(conn, anchor_sub, hub_key, campaign_id=campaign_id)
    except Exception as _lh_err:
        logger.warning(
            "template_local_map_error", template_id=template_id, error=str(_lh_err)
        )

    if start_key not in sub_keys and start_key != hub_key:
        # start location outside the settlement (standalone) — session anchors to hub
        start_key = hub_key

    logger.info(
        "template_settlement_materialized",
        template_id=template_id, hub_key=hub_key, sub_keys=sub_keys,
        start_key=start_key, q=q, r=r,
    )
    return {"hub_key": hub_key, "start_key": start_key, "sub_keys": sub_keys, "q": q, "r": r}


# ── Overworld hex placement for the plan's OTHER macro locations ──────────────
# The hub/start location sits on the template start hex (handled above) and
# sub-locations live on the FAZA ML local map (map_level=1). Every OTHER macro
# location in the plan (a distant dungeon, ruins, a second settlement) is a
# floating orphan unless it is placed on its own overworld hex — the travel /
# distance engine cannot route to a location with no world hex (same class of
# bug as the bogus-distance #1293). `ensure_plan_location_hexes` gives each such
# location a free hex in a ring around the start, spread apart.

_HEX_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
_RING_MIN = 2          # keep plan locations off the start hex's immediate skirt
_RING_MAX = 6          # …but within a short travel radius
_PREFERRED_TYPES = {"town", "plains", "forest"}


def _hex_dist(q1: int, r1: int, q2: int, r2: int) -> int:
    """Axial hex distance."""
    return (abs(q1 - q2) + abs(r1 - r2) + abs((q1 + r1) - (q2 + r2))) // 2


def _free_overworld_hexes(
    conn: sqlite3.Connection, template_id: int, exclude: "set[tuple[int, int]]"
) -> "list[dict]":
    """Every active overworld hex free for a plan location.

    Hard exclusions (identical to #1094 so the Kresy world map — Piotr-owned — is
    never touched): named POI (non-empty label), a hex already claimed by an
    active game_location, another template's start hex, and anything in `exclude`.
    """
    taken = set(exclude)
    for row in conn.execute(
        "SELECT start_hex_q, start_hex_r FROM campaign_templates "
        "WHERE start_hex_q IS NOT NULL AND id != ?",
        (template_id,),
    ).fetchall():
        taken.add((int(row["start_hex_q"]), int(row["start_hex_r"])))
    try:
        for row in conn.execute(
            "SELECT world_hex_q, world_hex_r FROM game_locations "
            "WHERE world_hex_q IS NOT NULL AND world_hex_r IS NOT NULL AND is_active = 1"
        ).fetchall():
            taken.add((int(row["world_hex_q"]), int(row["world_hex_r"])))
    except sqlite3.Error:
        pass

    out: list[dict] = []
    for row in conn.execute(
        "SELECT q, r, hex_type, label FROM world_hexes WHERE map_level = 0 AND is_active = 1"
    ).fetchall():
        q, r = int(row["q"]), int(row["r"])
        if (row["label"] or "").strip():
            continue
        if (q, r) in taken:
            continue
        out.append({"q": q, "r": r, "hex_type": row["hex_type"] or ""})
    return out


def _pick_plan_hex(
    free: "list[dict]",
    start_q: int,
    start_r: int,
    chosen: "list[tuple[int, int]]",
    min_spacing: int,
) -> "dict | None":
    """Pick the best free hex for a plan location: inside the [RING_MIN, RING_MAX]
    ring around the start, spread from already-chosen locations (>= min_spacing
    preferred, enforced when possible), mild preference for hospitable terrain."""
    best = None
    best_score = -1e18
    for h in free:
        q, r = h["q"], h["r"]
        d_start = _hex_dist(q, r, start_q, start_r)
        min_chosen = min((_hex_dist(q, r, cq, cr) for cq, cr in chosen), default=999)
        # spacing: heavily reward keeping locations apart (fixes "za blisko siebie")
        spacing_score = min(min_chosen, min_spacing) * 1000 + min_chosen
        # ring: penalise hexes outside [RING_MIN, RING_MAX] by how far off they are
        if d_start < _RING_MIN:
            ring_pen = (_RING_MIN - d_start) * 300
        elif d_start > _RING_MAX:
            ring_pen = (d_start - _RING_MAX) * 120
        else:
            ring_pen = 0
        pref = 30 if h["hex_type"] in _PREFERRED_TYPES else 0
        score = spacing_score - ring_pen + pref
        if score > best_score:
            best_score = score
            best = h
    return best


def _overworld_macro_locations(plan: dict) -> "list[dict]":
    """key_locations that need their OWN overworld hex: everything that is not a
    sub-location (those go on the local map) and not the hub/start (already on the
    start hex). Returns the raw loc dicts, order preserved."""
    if not isinstance(plan, dict):
        return []
    locs = [l for l in (plan.get("key_locations") or []) if isinstance(l, dict) and l.get("key")]
    hub_key = next((str(l["key"]) for l in locs if l.get("scale") == "hub"), None)
    start = _start_location_from_plan(plan)
    start_key = start[0] if start else None
    anchored = {k for k in (hub_key, start_key) if k}
    return [
        l for l in locs
        if l.get("scale") != "sub" and str(l["key"]) not in anchored
    ]


def ensure_plan_location_hexes(
    conn: sqlite3.Connection,
    template_id: int,
    *,
    force: bool = False,
    min_spacing: int = 2,
) -> "dict | None":
    """Give every OTHER macro location in the plan its own free overworld hex.

    - Reused locations (a row that already carries a world-hex canon) keep their
      hex and are reported under `reused` — never moved (answers "sprawdzaj w
      bazie czy lokacje mają już przydzielony globalny hex").
    - Fresh locations get a free hex in a ring around the start, spread apart.
    - `force=True` (admin "rozrzuć ponownie") first releases the hexes this
      template's plan locations currently hold, then re-allocates all of them with
      `min_spacing` — used to spread out locations the auto-pass packed too close.

    Writes via `link_location_to_hex` so the placement survives
    `reconcile_location_hex_links`. Idempotent. Returns
    {"assigned": [...], "reused": [...], "unplaced": [...]} or None when the
    template has no start hex / no macro locations to place.
    """
    from app.services.hex_location_link import (
        link_location_to_hex,
        resolve_location_to_hex,
    )

    tpl = conn.execute(
        "SELECT start_hex_q, start_hex_r, gm_plan_json FROM campaign_templates WHERE id = ?",
        (template_id,),
    ).fetchone()
    if not tpl or tpl["start_hex_q"] is None or tpl["start_hex_r"] is None:
        return None
    try:
        plan = json.loads(tpl["gm_plan_json"] or "{}")
    except Exception:
        return None

    macro = _overworld_macro_locations(plan)
    if not macro:
        return {"assigned": [], "reused": [], "unplaced": []}

    start_q, start_r = int(tpl["start_hex_q"]), int(tpl["start_hex_r"])
    labels = {
        str(l["key"]): str(l.get("name") or l["key"])
        for l in (plan.get("key_locations") or [])
        if isinstance(l, dict) and l.get("key")
    }

    assigned: list[dict] = []
    reused: list[dict] = []
    unplaced: list[dict] = []
    chosen: list[tuple[int, int]] = [(start_q, start_r)]  # start hex is off-limits

    for loc in macro:
        key = str(loc["key"])
        row = conn.execute(
            "SELECT id FROM game_locations WHERE key = ? AND is_active = 1 LIMIT 1", (key,)
        ).fetchone()
        if row is None:
            # stub not created yet (e.g. plan changed) — skip; a later publish/launch
            # pass will create it and re-run this allocator.
            unplaced.append({"key": key, "name": labels.get(key, key), "reason": "no_location_row"})
            continue

        existing = resolve_location_to_hex(conn, key)
        if existing is not None and not force:
            chosen.append(existing)
            reused.append({"key": key, "name": labels.get(key, key),
                           "q": existing[0], "r": existing[1]})
            continue

        if existing is not None and force:
            # release the old hex canon so the slot frees up for re-allocation
            conn.execute(
                "UPDATE world_hexes SET location_key = NULL "
                "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1",
                (existing[0], existing[1]),
            )
            conn.execute(
                "UPDATE game_locations SET world_hex_q = NULL, world_hex_r = NULL "
                "WHERE key = ? AND is_active = 1",
                (key,),
            )

        free = _free_overworld_hexes(conn, template_id, exclude=set(chosen))
        pick = _pick_plan_hex(free, start_q, start_r, chosen, min_spacing)
        if pick is None:
            unplaced.append({"key": key, "name": labels.get(key, key), "reason": "no_free_hex"})
            continue
        link_location_to_hex(conn, key, pick["q"], pick["r"])
        chosen.append((pick["q"], pick["r"]))
        assigned.append({"key": key, "name": labels.get(key, key),
                         "q": pick["q"], "r": pick["r"], "hex_type": pick["hex_type"]})

    conn.commit()
    logger.info(
        "plan_location_hexes_ensured",
        template_id=template_id,
        assigned=len(assigned), reused=len(reused), unplaced=len(unplaced),
        force=force,
    )
    return {"assigned": assigned, "reused": reused, "unplaced": unplaced}


def ensure_template_locations(
    conn: sqlite3.Connection,
    template_id: int,
    campaign_id: "int | None" = None,
) -> "dict | None":
    """#1206 + #1212 — one entry point for template location materialization.

    Settlement-structured plans (hub+subs) get the full FAZA ML treatment;
    flat plans fall back to the single anchored start location. In both cases the
    plan's OTHER macro locations then get their own overworld hexes so the travel
    engine can route to them.
    """
    struct = ensure_template_location_structure(conn, template_id, campaign_id=campaign_id)
    if struct:
        result = {"key": struct["start_key"], "status": "settlement",
                  "q": struct["q"], "r": struct["r"], **struct}
    else:
        result = ensure_template_start_location(conn, template_id, campaign_id=campaign_id)

    # Place the plan's remaining macro locations on their own overworld hexes.
    try:
        placed = ensure_plan_location_hexes(conn, template_id)
        if placed and isinstance(result, dict):
            result["plan_location_hexes"] = placed
    except Exception as _plh_err:
        logger.warning(
            "plan_location_hexes_error", template_id=template_id, error=str(_plh_err)
        )
    return result
