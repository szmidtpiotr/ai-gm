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


# ── #1482: ochrona ręcznie budowanej mapy świata ──────────────────────────────
# Świat Kresów powstaje ręcznie (heks po heksie), a źródłem prawdy są pliki
# data/regions/region_<klucz>.json w gicie. Każda operacja kasująca CAŁE
# map_level=0 jednym ruchem może w sekundę skasować godziny pracy, więc jest
# zablokowana dopóki mapa nie jest pusta. Pojedyncze PATCH/DELETE hexa, malowanie
# i generate-local (podmapy osad) nie są objęte guardem.

def _map_level0_counts(conn) -> list[tuple[str, int, str]]:
    """(region, liczba heksów map_level=0, status krainy) — malejąco po liczbie."""
    try:
        rows = conn.execute(
            "SELECT h.region AS region, COUNT(*) AS n, "
            "       COALESCE(r.status, 'unknown') AS status "
            "FROM world_hexes h "
            "LEFT JOIN world_regions r ON r.key = h.region "
            "WHERE h.map_level = 0 "
            "GROUP BY h.region ORDER BY n DESC"
        ).fetchall()
    except sqlite3.Error:
        return []
    return [(r["region"] or "?", int(r["n"]), r["status"]) for r in rows]


def _guard_bulk_wipe(conn, what: str) -> None:
    """403, gdy operacja masowa skasowałaby/nadpisała istniejącą mapę świata (#1482)."""
    counts = _map_level0_counts(conn)
    total = sum(n for _, n, _ in counts)
    if total == 0:
        return  # pusta mapa (świeża baza) — odtworzenie musi być możliwe
    listing = ", ".join(f"{reg} — {n} heksów [{st}]" for reg, n, st in counts)
    raise HTTPException(
        status_code=403,
        detail=(
            f"Zablokowane (#1482): {what} skasowałoby ręcznie budowaną mapę świata "
            f"({total} heksów: {listing}). Mapę budujemy ręcznie, a źródłem prawdy są "
            "pliki data/regions/region_<klucz>.json w gicie. Użyj operacji per-kraina "
            "(POST /api/admin/world/map/restore?region=<klucz>) albo skryptu "
            "scripts/seed_world_map.py na serwerze."
        ),
    )


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


def _region_file_meta(rkey: str) -> Optional[dict]:
    """R1 (#1241) — status/label krainy = plik data/regions/region_<key>.json (kanon).

    Zwraca {"label", "status"} z istniejącego pliku lub None gdy pliku brak
    (nowa kraina). NIGDY nie zwraca hardcode'owanego statusu — snapshot writer
    przepisuje status zastany w pliku, nie regresuje go."""
    path = f"/data/regions/region_{rkey}.json"
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return {"label": d.get("label", rkey), "status": d.get("status", "coming")}


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
            # Kanon statusu = plik krainy. Nowa kraina (brak pliku) → status z
            # world_regions (deklaracja), fallback 'coming'. Nigdy nie regresujemy.
            meta = _region_file_meta(rkey)
            if meta is None:
                row = conn.execute(
                    "SELECT label, status FROM world_regions WHERE key = ?", (rkey,)
                ).fetchone()
                meta = {
                    "label": (row["label"] if row else rkey),
                    "status": (row["status"] if row else "coming"),
                }
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
    # #1482 — legacy restore kasuje WSZYSTKIE krainy i wstawia je z powrotem
    # jako 'kresy'; na wielokrainowej mapie to cichy wipe Siwych Grani itd.
    # Guard PRZED BEGIN — inaczej except-ROLLBACK strzela w nieistniejącą transakcję.
    try:
        _guard_bulk_wipe(conn, "pełne odtworzenie mapy z legacy world_map_seed.json")
    except HTTPException:
        conn.close()
        raise
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


@router.post("/generate")
def generate_world(authorization: str | None = Header(default=None)):
    """USUNIĘTY (#1482) — proceduralny generator całego świata.

    Świat Kresów budujemy ręcznie (Piotr + Claude); jedno kliknięcie generatora
    nadpisywało godziny ręcznej pracy. Odtworzenie mapy: per-kraina z gita.
    """
    _require_admin(authorization)
    raise HTTPException(
        status_code=410,
        detail=(
            "Generator świata został usunięty (#1482). Mapa Kresów jest budowana ręcznie, "
            "a źródłem prawdy są pliki data/regions/region_<klucz>.json w gicie. "
            "Odtworzenie krainy: POST /api/admin/world/map/restore?region=<klucz> "
            "albo scripts/seed_world_map.py na serwerze. Podmapy osad generuje nadal "
            "POST /api/admin/world/generate-local."
        ),
    )


@router.delete("/clear")
def clear_world(authorization: str | None = Header(default=None)):
    """Delete all top-level world hexes (map_level=0, no parent).

    #1482 — dozwolone tylko na PUSTEJ mapie; niepusta = 403 (ręczna praca).
    """
    _require_admin(authorization)
    conn = _get_db()
    try:
        _guard_bulk_wipe(conn, "wyczyszczenie całej mapy świata")
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
        # #1407: match the "Do zatwierdzenia" LIST exactly (get_pending_locations)
        # — same status string + is_active filter — so the badge never lies about
        # a queue that renders empty (was 'pending', no is_active → 31 vs 0 shown).
        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM game_locations WHERE review_status = 'pending_review' AND is_active = 1"
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
    # PT-F6 #1140: travel_hours < 0.5 breaks the A* heuristic (min terrain cost 0.5 →
    # heuristic would overestimate → suboptimal routes). Enforce on the server, not
    # just the client min="0.5".
    if float(body.travel_hours) < 0.5:
        raise HTTPException(status_code=400, detail="travel_hours musi wynosić co najmniej 0.5")
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
    # PT-F6 #1140: enforce the A* heuristic floor on edits too.
    if "travel_hours" in updates and float(updates["travel_hours"]) < 0.5:
        raise HTTPException(status_code=400, detail="travel_hours musi wynosić co najmniej 0.5")
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
    force: bool = False


@router.post("/generate-local")
def generate_local(body: LocalGenRequest, authorization: str | None = Header(default=None)):
    """Generate a local sub-hex map for a world hex using Voronoi clustering."""
    _require_admin(authorization)
    if body.radius > 6:
        raise HTTPException(status_code=400, detail="Max local radius: 6")
    conn = _get_db()
    try:
        parent = conn.execute(
            "SELECT id, hex_type, region FROM world_hexes WHERE q = ? AND r = ? AND parent_hex_id IS NULL",
            (body.parent_q, body.parent_r),
        ).fetchone()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent hex not found")

        # R2 #1242: sub-hexes carrying a location_key are a generated settlement
        # ring (FAZA ML, local_hex_service) — NOT random terrain. Refuse to wipe
        # them unless the admin confirms with force=true.
        settlement_hexes = conn.execute(
            "SELECT id FROM world_hexes WHERE parent_hex_id = ? AND location_key IS NOT NULL",
            (parent["id"],),
        ).fetchall()
        if settlement_hexes and not body.force:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Ten hex ma mapę osady ({len(settlement_hexes)} sublokacji) — "
                    "wygenerowanie zniszczy ją. Potwierdź, aby nadpisać."
                ),
            )
        if settlement_hexes and body.force:
            # Clear session_flags.local_hex for any game_session whose local_hex
            # points at a row we're about to DELETE — otherwise the player hangs
            # on a hex that no longer exists.
            _doomed_ids = {
                int(r["id"])
                for r in conn.execute(
                    "SELECT id FROM world_hexes WHERE parent_hex_id = ?",
                    (parent["id"],),
                ).fetchall()
            }
            for _s in conn.execute(
                "SELECT id, session_flags FROM game_sessions WHERE session_flags LIKE '%local_hex%'"
            ).fetchall():
                try:
                    _sf = json.loads(_s["session_flags"] or "{}")
                except Exception:
                    continue
                _lh = _sf.get("local_hex")
                if _lh and _lh.get("hex_id") in _doomed_ids:
                    _sf.pop("local_hex", None)
                    conn.execute(
                        "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                        (json.dumps(_sf, ensure_ascii=False), _s["id"]),
                    )

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
                          is_active, map_level, parent_hex_id, region)
                   VALUES (?, ?, ?, ?, '[]', 1, 1, ?, ?)""",
                (q, r, hex_type, 0.15, parent["id"], parent["region"]),
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



# ── Chain travel endpoint ─────────────────────────────────────────────────────

class HexTravelReq(BaseModel):
    character_id: int
    destination_q: int
    destination_r: int


@router.post("/campaigns/{campaign_id}/hex-travel")
def hex_chain_travel(campaign_id: int, req: HexTravelReq,
                     authorization: str | None = Header(default=None)):
    """
    Chain travel to a destination hex via A* pathfinding.
    Rolls encounters per hex along the route.
    Returns: travel result including narrative context for the narrator.

    #1154: admin-only surface (25/27 tras tego routera woła _require_admin) —
    dodano guard. Gracze podróżują przez /api/campaigns/{id}/hex-travel (turns.py).
    """
    _require_admin(authorization)
    # #1244 (R4): delegate to the shared travel pipeline so the admin route
    # produces identical state to the player routes (origin fallback via
    # resolve_starting_hex, clock, scenes, synthetic turn — same as /travel).
    from app.services.hex_travel_service import execute_travel, open_conn, TravelError

    target = {"hex": {"q": req.destination_q, "r": req.destination_r}}
    conn = open_conn()
    try:
        return execute_travel(conn, campaign_id, target, actor=req.character_id)
    except TravelError as e:
        _status = {"character_not_found": 404, "location_not_placed": 400}.get(e.code, 422)
        raise HTTPException(status_code=_status, detail=e.message)
    finally:
        conn.close()


# ── #1196 Treasure placement (admin/event) ───────────────────────────────────

class TreasurePlaceReq(BaseModel):
    hex_q: int
    hex_r: int
    character_id: int
    campaign_id: Optional[int] = None
    label: Optional[str] = None
    loot_table_key: Optional[str] = None
    guardian_enemy_key: Optional[str] = None
    dc: int = 12
    total_parts: int = 1
    gold_bonus: int = 0
    loot_tier_bonus: Optional[int] = None
    gold_mult: Optional[float] = None
    extra_loot_rolls: Optional[int] = None


@router.post("/treasures")
def place_treasure(req: TreasurePlaceReq, authorization: str | None = Header(default=None)):
    """#1196 — bury a treasure on a hex and hand the completed map to a hero."""
    _require_admin(authorization)
    from app.services import treasure_service
    conn = _get_db()
    try:
        camp = req.campaign_id
        if camp is None:
            row = conn.execute(
                "SELECT campaign_id FROM characters WHERE id = ?", (req.character_id,)
            ).fetchone()
            camp = int(row["campaign_id"]) if row and row["campaign_id"] else 0
        tid = treasure_service.admin_place_treasure(
            conn, character_id=req.character_id, campaign_id=int(camp or 0),
            hex_q=req.hex_q, hex_r=req.hex_r, label=req.label,
            loot_table_key=req.loot_table_key, guardian=req.guardian_enemy_key,
            dc=req.dc, total_parts=req.total_parts, gold_bonus=req.gold_bonus,
            loot_tier_bonus=req.loot_tier_bonus, gold_mult=req.gold_mult,
            extra_loot_rolls=req.extra_loot_rolls,
        )
        if tid is None:
            raise HTTPException(status_code=400, detail="Could not place treasure")
        return {"ok": True, "treasure_id": tid}
    finally:
        conn.close()


@router.get("/treasures")
def list_treasures(state: str | None = Query(default=None),
                   authorization: str | None = Header(default=None)):
    """#1196 — list treasures (optionally filtered by state)."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        sql = ("SELECT id, map_key, label, hex_q, hex_r, region, state, total_parts, "
               "guardian_enemy_key, dc, character_id, created_by, found_at "
               "FROM world_treasures")
        params: list[Any] = []
        if state:
            sql += " WHERE state = ?"
            params.append(state)
        sql += " ORDER BY id DESC LIMIT 500"
        return {"treasures": [dict(r) for r in conn.execute(sql, params).fetchall()]}
    finally:
        conn.close()


@router.delete("/treasures/{treasure_id}")
def delete_treasure(treasure_id: int, authorization: str | None = Header(default=None)):
    """#1196 — remove a treasure and its fragments."""
    _require_admin(authorization)
    conn = _get_db()
    try:
        conn.execute("DELETE FROM character_map_fragments WHERE treasure_id = ?", (treasure_id,))
        conn.execute("DELETE FROM world_treasures WHERE id = ?", (treasure_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
