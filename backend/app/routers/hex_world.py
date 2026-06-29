"""
Hex World Builder API — Task 40.
Admin endpoints for the hex grid world map.
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
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
    region: str = "kresy"


class HexUpdate(BaseModel):
    hex_type: Optional[str] = None
    label: Optional[str] = None
    atmosphere: Optional[str] = None
    encounter_chance: Optional[float] = None
    encounter_pool: Optional[list[str]] = None
    location_key: Optional[str] = None
    is_active: Optional[int] = None
    region: Optional[str] = None


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
def get_world_map(
    authorization: str | None = Header(default=None),
    region: Optional[str] = Query(default=None),
):
    """Full world map: all hexes + teleport connections + world_regions list. Admin only.

    ?region=<key> filters to that region's hexes only.
    Without ?region, returns hexes from all 'live' regions.
    Always includes 'regions' list with all 6 world_regions entries.
    """
    _require_admin(authorization)
    conn = _get_db()
    try:
        regions = [dict(r) for r in conn.execute(
            "SELECT key, label, color, status, entry_q, entry_r, sort_order, note "
            "FROM world_regions ORDER BY sort_order"
        ).fetchall()]

        if region:
            hexes = [dict(r) for r in conn.execute(
                "SELECT * FROM world_hexes WHERE is_active = 1 AND parent_hex_id IS NULL "
                "AND region = ? ORDER BY q, r",
                (region,),
            ).fetchall()]
        else:
            live_keys = [r["key"] for r in regions if r["status"] == "live"]
            if live_keys:
                placeholders = ",".join("?" * len(live_keys))
                hexes = [dict(r) for r in conn.execute(
                    f"SELECT * FROM world_hexes WHERE is_active = 1 AND parent_hex_id IS NULL "
                    f"AND region IN ({placeholders}) ORDER BY q, r",
                    live_keys,
                ).fetchall()]
            else:
                hexes = []

        for h in hexes:
            try:
                h["encounter_pool"] = json.loads(h.get("encounter_pool") or "[]")
            except Exception:
                h["encounter_pool"] = []

        teleports = [dict(r) for r in conn.execute(
            "SELECT * FROM hex_teleport_connections WHERE is_active = 1"
        ).fetchall()]

        return {"hexes": hexes, "teleport_connections": teleports, "regions": regions}
    finally:
        conn.close()


_REGION_META = {
    "kresy":            {"label": "Kresy",            "status": "live"},
    "koronne_niziny":   {"label": "Koronne Niziny",   "status": "coming"},
    "czarnobor":        {"label": "Czarnobór",        "status": "coming"},
    "siwe_granie":      {"label": "Siwe Granie",      "status": "coming"},
    "wybrzeze_lez":     {"label": "Wybrzeże Łez",     "status": "coming"},
    "martwe_pustkowia": {"label": "Martwe Pustkowia", "status": "coming"},
}


@router.post("/map/snapshot")
def snapshot_world_map(
    region: Optional[str] = Query(default=None, description="Snapshot jednej krainy; brak = wszystkie"),
    authorization: str | None = Header(default=None),
):
    """Zapisz mapę świata → /data/regions/region_<key>.json (per-region DLC paczka).

    Bez ?region= — snapshot wszystkich krain do osobnych plików + legacy /data/world_map_seed.json.
    Z ?region=<key> — snapshot tylko tej krainy.
    /data jest bind-mountem na hoście (./data-dev), plik trwały między rebuildami."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        where = "map_level = 0" + (f" AND region = ?" if region else "")
        params_q = (region,) if region else ()
        rows = conn.execute(
            f"SELECT q, r, hex_type, label, atmosphere, encounter_chance, region "
            f"FROM world_hexes WHERE {where} ORDER BY region, r, q",
            params_q,
        ).fetchall()
        hexes = [dict(x) for x in rows]
        # Safeguard tylko dla full snapshot lub krainy Kresy (2500 heksów) — nie blokuj
        # nowych krain (RM5+) które mają < 50 heksów na starcie DLC workflow.
        if not region and len(hexes) < 50:
            raise HTTPException(
                status_code=409,
                detail=f"Mapa wygląda na niezainicjalizowaną ({len(hexes)} heks.) — odmawiam nadpisania kanonu.")

        os.makedirs("/data/regions", exist_ok=True)

        def _write_region(rkey: str, rhexes: list[dict]) -> str:
            stripped = [{k: v for k, v in h.items() if k != "region"} for h in rhexes]
            meta = _REGION_META.get(rkey, {"label": rkey, "status": "coming"})
            data = {
                "region": rkey, "label": meta["label"], "status": meta["status"],
                "w": 50, "h": 50,
                "note": f"DLC paczka FAZY RM — {meta['label']}. Kanon = ten plik w git.",
                "hexes": stripped,
            }
            out = f"/data/regions/region_{rkey}.json"
            tmp = out + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, out)
            return out

        if region:
            out = _write_region(region, hexes)
            return {"ok": True, "count": len(hexes), "path": out, "region": region}

        # Snapshot wszystkich krain
        by_region: dict[str, list[dict]] = {}
        for h in hexes:
            rk = h.get("region") or "kresy"
            by_region.setdefault(rk, []).append(h)

        paths = []
        for rk, rhexes in sorted(by_region.items()):
            paths.append(_write_region(rk, rhexes))

        # Legacy backward-compat
        kresy = by_region.get("kresy", [])
        if kresy:
            legacy_data = {
                "name": "Kresy", "w": 50, "h": 50,
                "note": "KANON mapy świata (legacy). Nowe krainy w data/regions/region_<key>.json.",
                "hexes": [{k: v for k, v in h.items() if k != "region"} for h in kresy],
            }
            legacy_path = "/data/world_map_seed.json"
            tmp = legacy_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(legacy_data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, legacy_path)

        return {"ok": True, "count": len(hexes), "regions": list(by_region.keys()), "paths": paths}
    finally:
        conn.close()


@router.post("/map/restore")
def restore_world_map(
    region: Optional[str] = Query(default=None, description="Przywróć jedną krainę; brak = legacy stitch"),
    authorization: str | None = Header(default=None),
):
    """Wczytaj mapę świata z pliku kanon → world_hexes (map_level=0).

    Z ?region=<key> — partial restore: usuwa heksy tej krainy, wstawia z /data/regions/region_<key>.json.
    Bez ?region= — full restore z /data/world_map_seed.json (legacy, cała mapa)."""
    _require_admin(authorization)

    def _insert_hexes(conn, hexes: list[dict], region_key: Optional[str] = None):
        cols = "(q, r, hex_type, label, atmosphere, encounter_chance, encounter_pool, created_by_gm, is_active, map_level, region)"
        chunk = 200
        for i in range(0, len(hexes), chunk):
            batch = hexes[i:i + chunk]
            placeholders = ",".join(["(?,?,?,?,?,?,?,?,?,?,?)"] * len(batch))
            params: list[Any] = []
            for h in batch:
                params.extend([
                    h["q"], h["r"], h.get("hex_type", "plains"),
                    h.get("label"), h.get("atmosphere"),
                    h.get("encounter_chance", 0.15),
                    json.dumps(h.get("encounter_pool", [])),
                    0, 1, 0, region_key or h.get("region", "kresy"),
                ])
            conn.execute(f"INSERT INTO world_hexes {cols} VALUES {placeholders}", params)

    if region:
        seed_path = f"/data/regions/region_{region}.json"
        if not os.path.exists(seed_path):
            raise HTTPException(
                status_code=404,
                detail=f"Brak pliku kanon ({seed_path}). Najpierw snapshot_world_map.py --region {region}.",
            )
        with open(seed_path, encoding="utf-8") as f:
            data = json.load(f)
        hexes = data.get("hexes", [])
        if not hexes:
            raise HTTPException(status_code=409, detail=f"Plik kanon regionu '{region}' nie zawiera heksów.")
        conn = _get_db()
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM world_hexes WHERE map_level = 0 AND region = ?", (region,))
            _insert_hexes(conn, hexes, region)
            conn.execute("COMMIT")
            return {"ok": True, "count": len(hexes), "region": region, "source": seed_path}
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # Legacy full restore
    seed_path = "/data/world_map_seed.json"
    if not os.path.exists(seed_path):
        raise HTTPException(
            status_code=404,
            detail="Brak pliku kanon (/data/world_map_seed.json). Najpierw zapisz mapę przyciskiem 'Zapisz mapę (kanon)'.",
        )
    with open(seed_path, encoding="utf-8") as f:
        data = json.load(f)
    hexes = data.get("hexes", [])
    if not hexes:
        raise HTTPException(status_code=409, detail="Plik kanon nie zawiera heksów.")
    conn = _get_db()
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM world_hexes WHERE map_level = 0")
        _insert_hexes(conn, hexes, "kresy")
        conn.execute("COMMIT")
        return {"ok": True, "count": len(hexes), "source": seed_path}
    except Exception:
        conn.execute("ROLLBACK")
        raise
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
            "SELECT id FROM world_hexes WHERE q = ? AND r = ? AND parent_hex_id IS NULL", (body.q, body.r)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"Hex ({body.q},{body.r}) already exists")

        conn.execute(
            """INSERT INTO world_hexes
               (q, r, hex_type, label, atmosphere, encounter_chance, encounter_pool,
                location_key, discovered_in_campaign_id, created_by_gm, created_by_campaign_id, region)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (body.q, body.r, body.hex_type, body.label, body.atmosphere,
             body.encounter_chance, json.dumps(body.encounter_pool),
             body.location_key, body.campaign_id, body.created_by_gm, body.campaign_id,
             body.region),
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


class HexBulkPaintItem(BaseModel):
    q: int
    r: int
    hex_type: str
    encounter_chance: float = 0.15


class HexBulkPaint(BaseModel):
    hexes: list[HexBulkPaintItem]


@router.post("/hexes/bulk-paint")
def bulk_paint_hexes(body: HexBulkPaint, authorization: str | None = Header(default=None)):
    """Upsert many top-level hexes in one call — backs drag-painting on the map.

    Each item sets hex_type + encounter_chance; an existing hex is updated
    (label/atmosphere/encounter_pool preserved), a missing one is created.
    """
    _require_admin(authorization)
    if not body.hexes:
        return {"hexes": []}
    conn = _get_db()
    try:
        coords: list[tuple[int, int]] = []
        for it in body.hexes:
            existing = conn.execute(
                "SELECT id FROM world_hexes WHERE q = ? AND r = ? AND parent_hex_id IS NULL",
                (it.q, it.r),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE world_hexes SET hex_type = ?, encounter_chance = ? WHERE id = ?",
                    (it.hex_type, it.encounter_chance, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO world_hexes
                       (q, r, hex_type, encounter_chance, encounter_pool, created_by_gm)
                       VALUES (?,?,?,?,'[]',0)""",
                    (it.q, it.r, it.hex_type, it.encounter_chance),
                )
            coords.append((it.q, it.r))
        conn.commit()

        out = []
        for q, r in coords:
            row = conn.execute(
                "SELECT * FROM world_hexes WHERE q = ? AND r = ? AND parent_hex_id IS NULL",
                (q, r),
            ).fetchone()
            if row:
                d = dict(row)
                d["encounter_pool"] = json.loads(d.get("encounter_pool") or "[]")
                out.append(d)
        return {"hexes": out}
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
        if body.region is not None: updates["region"] = body.region

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


# ── World generation ──────────────────────────────────────────────────────────

def _hex_dist(q1: int, r1: int, q2: int, r2: int) -> float:
    dq, dr = q1 - q2, r1 - r2
    return (abs(dq) + abs(dr) + abs(dq + dr)) / 2.0


def _generate_biome_map(
    all_hexes: list[tuple[int, int]],
    types: list[str],
    weights: list[int],
    rng: random.Random,
    n_seeds: int | None = None,
    chaos: float = 2.5,
) -> dict[tuple[int, int], str]:
    """Voronoi biome clustering: each hex assigned to nearest biome seed with boundary noise.

    chaos — controls how jagged cluster edges are (0 = perfect Voronoi, >4 = nearly random).
    n_seeds — number of biome regions; defaults to 1 per ~18 hexes.
    """
    if n_seeds is None:
        n_seeds = max(8, len(all_hexes) // 18)
    n_seeds = min(n_seeds, len(all_hexes))

    seed_positions = rng.sample(all_hexes, n_seeds)
    seed_types = rng.choices(types, weights=weights, k=n_seeds)

    result: dict[tuple[int, int], str] = {}
    for q, r in all_hexes:
        best_dist = float("inf")
        chosen = types[0]
        for i, (sq, sr) in enumerate(seed_positions):
            dist = _hex_dist(q, r, sq, sr) + rng.uniform(0, chaos)
            if dist < best_dist:
                best_dist = dist
                chosen = seed_types[i]
        result[(q, r)] = chosen
    return result


# ── Placement-aware generation helpers (#507) ──────────────────────────────────

# Axial hex directions (pointy-top), used for line drawing and path walks.
_HEX_DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def _cube_round(x: float, y: float, z: float) -> tuple[int, int]:
    """Round fractional cube coords to the nearest hex, return axial (q, r)."""
    rx, ry, rz = round(x), round(y), round(z)
    dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(rz)


def _hex_line(q1: int, r1: int, q2: int, r2: int) -> list[tuple[int, int]]:
    """Hexes along the straight line between two hexes (inclusive of both ends)."""
    n = int(_hex_dist(q1, r1, q2, r2))
    if n == 0:
        return [(q1, r1)]
    x1, z1 = q1, r1
    y1 = -x1 - z1
    x2, z2 = q2, r2
    y2 = -x2 - z2
    out: list[tuple[int, int]] = []
    for i in range(n + 1):
        t = i / n
        out.append(_cube_round(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, z1 + (z2 - z1) * t))
    return out


def _carve_river(
    all_set: set[tuple[int, int]],
    rng: random.Random,
    start: tuple[int, int],
    max_len: int,
) -> list[tuple[int, int]]:
    """Momentum random-walk from `start` toward the map edge.

    Prefers continuing straight (weight 3) over a ±1 direction turn (weight 1),
    producing a meandering line rather than a tight scribble. Stops when it
    steps off the map (reaches the edge) or hits max_len.
    """
    path = [start]
    cur = start
    dir_idx = rng.randrange(6)
    seen = {start}
    for _ in range(max_len):
        choices = [(dir_idx - 1) % 6, dir_idx, (dir_idx + 1) % 6]
        dir_idx = rng.choices(choices, weights=[1, 3, 1], k=1)[0]
        dq, dr = _HEX_DIRS[dir_idx]
        nxt = (cur[0] + dq, cur[1] + dr)
        if nxt not in all_set or nxt in seen:
            break  # off the map edge, or would self-cross
        cur = nxt
        seen.add(cur)
        path.append(cur)
    return path


def _scatter_features(
    all_hexes: list[tuple[int, int]],
    placements: list[tuple[str, int]],
    occupied: set[tuple[int, int]],
    rng: random.Random,
) -> dict[tuple[int, int], str]:
    """Place feature hexes as isolated points via rejection sampling.

    placements — (hex_type, count) per scatter terrain.
    occupied — hexes that must not be used (e.g. river hexes).
    Enforces min spacing: >=3 hexes between same-type features, >=2 between any.
    """
    result: dict[tuple[int, int], str] = {}
    candidates = [h for h in all_hexes if h not in occupied]
    rng.shuffle(candidates)
    placed_by_type: dict[str, list[tuple[int, int]]] = {}
    for hex_type, count in placements:
        placed_by_type.setdefault(hex_type, [])
        added = 0
        attempts = 0
        cap = max(200, count * 40)
        idx = 0
        while added < count and attempts < cap and idx < len(candidates):
            attempts += 1
            cand = candidates[idx]
            idx += 1
            if cand in result:
                continue
            # >=2 from any feature already placed
            if any(_hex_dist(*cand, *p) < 2 for p in result):
                continue
            # >=3 from same-type
            if any(_hex_dist(*cand, *p) < 3 for p in placed_by_type[hex_type]):
                continue
            result[cand] = hex_type
            placed_by_type[hex_type].append(cand)
            added += 1
        # restart scan from top for the next type so it can reuse skipped hexes
    return result


def _build_road_network(
    nodes: list[tuple[int, int]],
    blocked: set[tuple[int, int]],
    rng: random.Random,
) -> set[tuple[int, int]]:
    """Connect every node (town/castle) into one network via a greedy MST.

    Returns the set of intermediate hexes that should become roads. Node hexes
    themselves are excluded (they keep their feature type); so are `blocked`
    hexes (other scatter features) — roads route through but don't overwrite them.
    Roads may cross rivers (treated as bridges).
    """
    if len(nodes) < 2:
        return set()
    connected = [nodes[0]]
    remaining = nodes[1:]
    road_hexes: set[tuple[int, int]] = set()
    node_set = set(nodes)
    while remaining:
        best = None
        best_d = float("inf")
        for tgt in remaining:
            for src in connected:
                d = _hex_dist(*src, *tgt)
                if d < best_d:
                    best_d, best = d, (src, tgt)
        src, tgt = best
        for h in _hex_line(*src, *tgt):
            if h not in node_set and h not in blocked:
                road_hexes.add(h)
        connected.append(tgt)
        remaining.remove(tgt)
    return road_hexes


def _placement_mode(row: Any) -> str:
    """Resolve a terrain row's placement_mode, defaulting NULL/unknown to 'biome'."""
    try:
        mode = row["placement_mode"]
    except (KeyError, IndexError, TypeError):
        mode = None
    return mode if mode in ("biome", "scatter", "path") else "biome"


def _world_hex_coords(radius: int) -> list[tuple[int, int]]:
    """Rectangular hex grid for the global world map (#589).

    The renderer places a flat-top hex at y ∝ (q/2 + r). A plain axial square
    [-R,R]² therefore draws as a RHOMBUS (each column q shifted vertically by q/2).
    To get a visual RECTANGLE we shear the per-column r-range by -floor(q/2) so the
    vertical band (q/2 + r) is identical for every column. Still (2R+1)² hexes.
    """
    coords: list[tuple[int, int]] = []
    for q in range(-radius, radius + 1):
        shift = -(q // 2)  # compensate the q/2 vertical shear
        for r in range(-radius + shift, radius + shift + 1):
            coords.append((q, r))
    return coords


class WorldGenRequest(BaseModel):
    seed: int = 42
    radius: int = 25
    # #589 — regenerate = replace. Without clearing, INSERT OR IGNORE leaves the
    # PREVIOUS world's hexes in place (e.g. an old diamond) so the new rectangle
    # never fully shows. Default True wipes top-level hexes first.
    clear_existing: bool = True


@router.post("/generate")
def generate_world(body: WorldGenRequest, authorization: str | None = Header(default=None)):
    """Procedurally generate a hex world grid using Voronoi biome clustering."""
    _require_admin(authorization)
    if body.radius > 50:
        raise HTTPException(status_code=400, detail="Max radius: 50")

    conn = _get_db()
    try:
        terrain_rows = conn.execute(
            "SELECT hex_type, spawn_weight, encounter_base_chance, placement_mode "
            "FROM hex_type_config WHERE is_active = 1 AND spawn_weight > 0"
        ).fetchall()
        if not terrain_rows:
            raise HTTPException(status_code=400, detail="No terrain types with spawn_weight > 0 configured")

        encounter_chances = {r["hex_type"]: r["encounter_base_chance"] for r in terrain_rows}
        weight_by_type = {r["hex_type"]: r["spawn_weight"] for r in terrain_rows}

        # Partition terrain types by how they should be placed (#507).
        biome_types: list[str] = []
        biome_weights: list[int] = []
        scatter: list[tuple[str, int]] = []   # (hex_type, weight)
        river_types: list[str] = []
        road_types: list[str] = []
        for r in terrain_rows:
            mode = _placement_mode(r)
            ht, w = r["hex_type"], r["spawn_weight"]
            if mode == "scatter":
                scatter.append((ht, w))
            elif mode == "path":
                (road_types if ht == "road" else river_types).append(ht)
            else:
                biome_types.append(ht)
                biome_weights.append(w)

        if not biome_types:
            raise HTTPException(status_code=400, detail="No biome terrain types configured (placement_mode='biome')")

        rng = random.Random(body.seed)

        # Build all hex coordinates (full square grid — #589)
        all_hexes = _world_hex_coords(body.radius)
        all_set = set(all_hexes)
        total = len(all_hexes)

        # 1) Base biome layer — Voronoi clustering over biome types only.
        biome_map = _generate_biome_map(all_hexes, biome_types, biome_weights, rng)

        # 2) Rivers — momentum walks toward the map edge, overwrite biome.
        mountain_hexes = [h for h, t in biome_map.items() if t == "mountains"] or all_hexes
        for river_type in river_types:
            n_rivers = max(1, weight_by_type.get(river_type, 0) // 5)
            for _ in range(n_rivers):
                start = rng.choice(mountain_hexes)
                for h in _carve_river(all_set, rng, start, max_len=body.radius * 3):
                    biome_map[h] = river_type
        river_set = {h for h, t in biome_map.items() if t in river_types}

        # 3) Scatter features — isolated points, never on a river.
        scatter_counts = [
            (ht, max(1, round(w * total / 1200)))
            for ht, w in scatter
        ]
        feature_map = _scatter_features(all_hexes, scatter_counts, river_set, rng)
        for h, t in feature_map.items():
            biome_map[h] = t

        # 4) Road network — connect towns + castles via greedy MST.
        if road_types:
            road_type = road_types[0]
            nodes = [h for h, t in feature_map.items() if t in ("town", "castle")]
            blocked = set(feature_map.keys())  # don't overwrite other features
            for h in _build_road_network(nodes, blocked, rng):
                biome_map[h] = road_type

        # #589 — replace the previous top-level world so the new shape is exact
        # (old hexes outside the new set would otherwise remain and distort the map).
        if body.clear_existing:
            conn.execute(
                "DELETE FROM world_hexes WHERE map_level = 0 AND parent_hex_id IS NULL"
            )

        hexes_created = 0
        counts: dict[str, int] = {}
        for (q, r), hex_type in biome_map.items():
            enc = encounter_chances.get(hex_type, 0.15)
            try:
                conn.execute(
                    """INSERT INTO world_hexes (q, r, hex_type, encounter_chance, encounter_pool, is_active)
                       VALUES (?, ?, ?, ?, '[]', 1)
                       ON CONFLICT DO NOTHING""",
                    (q, r, hex_type, enc),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    hexes_created += 1
                    counts[hex_type] = counts.get(hex_type, 0) + 1
            except Exception:
                pass

        conn.commit()
        return {"hexes_created": hexes_created, "counts": counts, "seed": body.seed, "radius": body.radius}
    finally:
        conn.close()


@router.delete("/clear")
def clear_world(authorization: str | None = Header(default=None)):
    """Delete all top-level world hexes (map_level=0, no parent)."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        deleted = conn.execute(
            "DELETE FROM world_hexes WHERE map_level = 0 AND parent_hex_id IS NULL"
        )
        conn.commit()
        return {"hexes_deleted": deleted.rowcount}
    finally:
        conn.close()


# ── Locations map overlay ──────────────────────────────────────────────────────

@router.get("/locations-map")
def get_locations_map(authorization: str | None = Header(default=None)):
    """Locations with world hex coordinates for map overlay."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        locs = conn.execute(
            """SELECT key, label, location_type, map_icon, world_hex_q AS q, world_hex_r AS r,
                      review_status, is_active
               FROM game_locations
               WHERE world_hex_q IS NOT NULL AND world_hex_r IS NOT NULL
               ORDER BY label"""
        ).fetchall()
        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM game_locations WHERE review_status = 'pending'"
        ).fetchone()
        return {
            "locations": [dict(r) for r in locs],
            "pending_count": pending["n"] if pending else 0,
        }
    finally:
        conn.close()


# ── Terrain config CRUD ────────────────────────────────────────────────────────

@router.get("/hex-terrain-config")
def list_terrain_config(authorization: str | None = Header(default=None)):
    """All terrain types from hex_type_config (admin panel terrain tab)."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        rows = conn.execute("SELECT * FROM hex_type_config ORDER BY hex_type").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


class TerrainConfigCreate(BaseModel):
    hex_type: str
    label: str
    travel_hours: float = 1.0
    encounter_base_chance: float = 0.15
    map_color: str = "#4a6a4a"
    map_icon: Optional[str] = None
    spawn_weight: int = 0
    has_submap: int = 0
    is_passable: int = 1
    is_active: int = 1
    placement_mode: str = "biome"


@router.post("/hex-terrain-config")
def create_terrain_config(body: TerrainConfigCreate, authorization: str | None = Header(default=None)):
    """Create a new terrain type."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO hex_type_config
               (hex_type, label, travel_hours, encounter_base_chance, map_color, map_icon,
                spawn_weight, has_submap, is_passable, is_active, placement_mode)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (body.hex_type, body.label, body.travel_hours, body.encounter_base_chance,
             body.map_color, body.map_icon, body.spawn_weight, body.has_submap,
             body.is_passable, body.is_active, body.placement_mode),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM hex_type_config WHERE hex_type = ?", (body.hex_type,)).fetchone()
        return dict(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Terrain type '{body.hex_type}' already exists")
    finally:
        conn.close()


@router.patch("/hex-terrain-config/{hex_type}")
def patch_terrain_config(
    hex_type: str,
    body: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
):
    """Update terrain type fields."""
    _require_admin(authorization)
    allowed = {"label", "travel_hours", "encounter_base_chance", "map_color", "map_icon",
               "spawn_weight", "has_submap", "is_passable", "is_active", "required_item",
               "placement_mode"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    conn = _get_db()
    try:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE hex_type_config SET {set_clause} WHERE hex_type = ?",
            (*updates.values(), hex_type),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM hex_type_config WHERE hex_type = ?", (hex_type,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Terrain type not found")
        return dict(row)
    finally:
        conn.close()


# ── Submap endpoints ──────────────────────────────────────────────────────────

@router.get("/hexes/submappable")
def get_submappable_hexes(authorization: str | None = Header(default=None)):
    """World hexes whose terrain type has has_submap=1, with submap_exists flag."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT wh.id, wh.q, wh.r, wh.hex_type, wh.label,
                      htc.label AS type_label, htc.map_icon, htc.map_color,
                      (SELECT COUNT(*) FROM world_hexes sh WHERE sh.parent_hex_id = wh.id) > 0 AS submap_exists
               FROM world_hexes wh
               JOIN hex_type_config htc ON htc.hex_type = wh.hex_type
               WHERE htc.has_submap = 1 AND wh.parent_hex_id IS NULL AND wh.is_active = 1
               ORDER BY wh.q, wh.r"""
        ).fetchall()
        return {"hexes": [dict(r) for r in rows]}
    finally:
        conn.close()


class LocalGenRequest(BaseModel):
    parent_q: int
    parent_r: int
    seed: int = 0
    radius: int = 3


@router.post("/generate-local")
def generate_local(body: LocalGenRequest, authorization: str | None = Header(default=None)):
    """Generate a local sub-hex map for a world hex using Voronoi clustering."""
    _require_admin(authorization)
    if body.radius > 6:
        raise HTTPException(status_code=400, detail="Max local radius: 6")
    conn = _get_db()
    try:
        parent = conn.execute(
            "SELECT id, hex_type FROM world_hexes WHERE q = ? AND r = ? AND parent_hex_id IS NULL",
            (body.parent_q, body.parent_r),
        ).fetchone()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent hex not found")

        terrain_rows = conn.execute(
            "SELECT hex_type, spawn_weight, encounter_base_chance FROM hex_type_config WHERE is_active = 1 AND spawn_weight > 0"
        ).fetchall()
        if not terrain_rows:
            raise HTTPException(status_code=400, detail="No terrain types configured")

        types = [r["hex_type"] for r in terrain_rows]
        weights = [r["spawn_weight"] for r in terrain_rows]

        rng = random.Random(body.seed or (body.parent_q * 1000 + body.parent_r))

        all_hexes = [
            (q, r)
            for q in range(-body.radius, body.radius + 1)
            for r in range(-body.radius, body.radius + 1)
            if abs(q) + abs(r) + abs(q + r) <= 2 * body.radius
        ]

        # Fewer seeds for small local area, tighter chaos
        n_seeds = max(3, len(all_hexes) // 7)
        biome_map = _generate_biome_map(all_hexes, types, weights, rng, n_seeds=n_seeds, chaos=1.5)

        # Clear existing sub-hexes
        conn.execute("DELETE FROM world_hexes WHERE parent_hex_id = ?", (parent["id"],))

        hexes_created = 0
        for (q, r), hex_type in biome_map.items():
            conn.execute(
                """INSERT INTO world_hexes (q, r, hex_type, encounter_chance, encounter_pool,
                          is_active, map_level, parent_hex_id)
                   VALUES (?, ?, ?, ?, '[]', 1, 1, ?)""",
                (q, r, hex_type, 0.15, parent["id"]),
            )
            hexes_created += 1

        conn.commit()
        return {"hexes_created": hexes_created, "parent_q": body.parent_q, "parent_r": body.parent_r}
    finally:
        conn.close()


@router.get("/local-map/{q}/{r}")
def get_local_map(q: int, r: int, authorization: str | None = Header(default=None)):
    """Get sub-hexes for the local map of a world hex."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        parent = conn.execute(
            "SELECT * FROM world_hexes WHERE q = ? AND r = ? AND parent_hex_id IS NULL",
            (q, r),
        ).fetchone()
        if not parent:
            return {"ok": False, "error": "Parent hex not found"}

        sub_hexes = conn.execute(
            "SELECT * FROM world_hexes WHERE parent_hex_id = ? ORDER BY q, r",
            (parent["id"],),
        ).fetchall()
        if not sub_hexes:
            return {"ok": False, "error": "Brak podmopy — użyj 'Generuj' aby utworzyć."}

        return {
            "ok": True,
            "parent": dict(parent),
            "hexes": [dict(h) for h in sub_hexes],
        }
    finally:
        conn.close()


@router.patch("/local-hexes/{q}/{r}/{lq}/{lr}")
def patch_local_hex(
    q: int, r: int, lq: int, lr: int,
    body: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
):
    """Paint a sub-hex (update its hex_type or label)."""
    _require_admin(authorization)
    allowed = {"hex_type", "label", "atmosphere", "encounter_chance"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields")
    conn = _get_db()
    try:
        parent = conn.execute(
            "SELECT id FROM world_hexes WHERE q = ? AND r = ? AND parent_hex_id IS NULL",
            (q, r),
        ).fetchone()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent hex not found")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        cur = conn.execute(
            f"UPDATE world_hexes SET {set_clause} WHERE parent_hex_id = ? AND q = ? AND r = ?",
            (*updates.values(), parent["id"], lq, lr),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Sub-hex not found")
        row = conn.execute(
            "SELECT * FROM world_hexes WHERE parent_hex_id = ? AND q = ? AND r = ?",
            (parent["id"], lq, lr),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.get("/hex-location/{q}/{r}/{lq}/{lr}")
def get_hex_location(
    q: int, r: int, lq: int, lr: int,
    authorization: str | None = Header(default=None),
):
    """Location info for a sub-hex: specific (assigned to this sub-hex) + generic (parent's)."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        parent = conn.execute(
            "SELECT id, location_key FROM world_hexes WHERE q = ? AND r = ? AND parent_hex_id IS NULL",
            (q, r),
        ).fetchone()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent hex not found")

        sub = conn.execute(
            "SELECT id, location_key FROM world_hexes WHERE parent_hex_id = ? AND q = ? AND r = ?",
            (parent["id"], lq, lr),
        ).fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Sub-hex not found")

        def _loc(key):
            if not key:
                return None
            row = conn.execute(
                "SELECT key, label, description, location_type FROM game_locations WHERE key = ?", (key,)
            ).fetchone()
            return dict(row) if row else None

        specific = _loc(sub["location_key"])
        generic = _loc(parent["location_key"])

        candidates_rows = conn.execute(
            "SELECT key, label, location_type FROM game_locations WHERE is_active = 1 ORDER BY label"
        ).fetchall()
        candidates = [dict(r) for r in candidates_rows]

        return {"specific": specific, "generic": generic, "candidates": candidates}
    finally:
        conn.close()


@router.patch("/assign-hex-location/{q}/{r}/{lq}/{lr}")
def assign_hex_location(
    q: int, r: int, lq: int, lr: int,
    body: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
):
    """Assign a location to a sub-hex (sets its location_key)."""
    _require_admin(authorization)
    location_key = body.get("location_key")
    conn = _get_db()
    try:
        parent = conn.execute(
            "SELECT id FROM world_hexes WHERE q = ? AND r = ? AND parent_hex_id IS NULL",
            (q, r),
        ).fetchone()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent hex not found")
        cur = conn.execute(
            "UPDATE world_hexes SET location_key = ? WHERE parent_hex_id = ? AND q = ? AND r = ?",
            (location_key, parent["id"], lq, lr),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Sub-hex not found")
        return {"ok": True, "location_key": location_key}
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
