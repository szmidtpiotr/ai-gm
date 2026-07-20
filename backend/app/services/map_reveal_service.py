"""PT13 (#1123) — Map items reveal fog of war.

One discovery engine, three modes (``radius`` | ``region`` | ``hexes``). Given a
map "recipe" (payload dict, usually an item's ``effect_json``) plus a campaign,
compute the target overworld hexes and mark them discovered in
``campaign_hex_data``. Idempotent. The map item is never consumed here — reveal
is a one-shot effect and the item stays in the player's inventory (Piotr's
decision 2026-07-02).
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any
from app.core.db_runtime import resolve_db_path

DB_PATH = resolve_db_path()

_MODES = {"radius", "region", "hexes", "location"}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hex_distance(q1: int, r1: int, q2: int, r2: int) -> int:
    """Axial hex distance between two hexes."""
    return (abs(q1 - q2) + abs(r1 - r2) + abs(q1 + r1 - q2 - r2)) // 2


def extract_map_payload(effect_json: Any) -> dict[str, Any] | None:
    """Pull the map-reveal recipe out of an item's ``effect_json``.

    Accepts a flat recipe ``{"mode": "radius", ...}`` or a wrapped one
    ``{"effects": [{"type": "map_reveal", "mode": "radius", ...}]}``.
    Returns ``None`` when no map-reveal recipe is present (e.g. a heal potion).
    """
    parsed: Any = effect_json
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except (ValueError, TypeError):
            return None
    if not isinstance(parsed, dict):
        return None
    effects = parsed.get("effects")
    if isinstance(effects, list):
        for e in effects:
            if isinstance(e, dict) and str(e.get("type") or "").strip().lower() == "map_reveal":
                return e
        return None
    if str(parsed.get("mode") or "").strip().lower() in _MODES:
        return parsed
    return None


def _dedup(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []
    for p in pairs:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def compute_reveal_hexes(conn: sqlite3.Connection, payload: dict[str, Any]) -> list[tuple[int, int]]:
    """Resolve a map recipe to the list of overworld ``(q, r)`` hexes it reveals.

    - ``radius``: every active overworld hex (``map_level=0``) within hex-distance
      ``radius`` of ``(center_q, center_r)``.
    - ``region``: every active overworld hex tagged with ``region``.
    - ``hexes``: exactly the explicit ``list`` / ``hexes`` of ``[q, r]`` pairs.
    """
    mode = str(payload.get("mode") or "").strip().lower()

    if mode == "radius":
        try:
            cq = int(payload["center_q"])
            cr = int(payload["center_r"])
            rad = int(payload["radius"])
        except (KeyError, TypeError, ValueError):
            return []
        if rad < 0:
            return []
        rows = conn.execute(
            "SELECT q, r FROM world_hexes WHERE map_level = 0 AND is_active = 1"
        ).fetchall()
        return _dedup([
            (int(row["q"]), int(row["r"]))
            for row in rows
            if hex_distance(cq, cr, int(row["q"]), int(row["r"])) <= rad
        ])

    if mode == "region":
        region = str(payload.get("region") or "").strip()
        if not region:
            return []
        rows = conn.execute(
            "SELECT q, r FROM world_hexes WHERE map_level = 0 AND is_active = 1 AND region = ?",
            (region,),
        ).fetchall()
        return _dedup([(int(row["q"]), int(row["r"])) for row in rows])

    if mode == "hexes":
        raw = payload.get("list") or payload.get("hexes") or []
        out: list[tuple[int, int]] = []
        if isinstance(raw, list):
            for pair in raw:
                try:
                    out.append((int(pair[0]), int(pair[1])))
                except (TypeError, ValueError, IndexError, KeyError):
                    continue
        return _dedup(out)

    if mode == "location":
        # #1308 — reveal the overworld hex(es) of named plan locations. Reads the
        # canon (`world_hexes.location_key` via resolve_location_to_hex) so it never
        # drifts when a location is re-placed — unlike hard-coded (q, r) pairs.
        raw = payload.get("list") or payload.get("locations") or payload.get("keys") or []
        if not isinstance(raw, list):
            return []
        from app.services.hex_location_link import resolve_location_to_hex
        out2: list[tuple[int, int]] = []
        for key in raw:
            if not key:
                continue
            hx = resolve_location_to_hex(conn, str(key))
            if hx is not None:
                out2.append((int(hx[0]), int(hx[1])))
        return _dedup(out2)

    return []


def _table_cols(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def reveal_hexes(conn: sqlite3.Connection, campaign_id: int, hexes: list[tuple[int, int]]) -> int:
    """Mark each ``(q, r)`` discovered for the campaign. Idempotent. Returns count.

    #1308 — also sets the FOW ``known`` flag and backfills
    ``world_hexes.discovered_in_campaign_id`` so BOTH fog systems (per-campaign
    ``campaign_hex_data`` and the legacy ``world_hexes`` overlay, unioned as
    known∪discovered by #1220/#1293) agree. Column writes are guarded so the
    minimal #1123 test schema (no ``known``/``discovered_in_campaign_id``) still
    passes.
    """
    has_known = "known" in _table_cols(conn, "campaign_hex_data")
    has_disc_cid = "discovered_in_campaign_id" in _table_cols(conn, "world_hexes")
    n = 0
    for q, r in hexes:
        if has_known:
            conn.execute(
                """INSERT INTO campaign_hex_data (campaign_id, hex_q, hex_r, discovered, known)
                   VALUES (?,?,?,1,1)
                   ON CONFLICT(campaign_id, hex_q, hex_r)
                   DO UPDATE SET discovered = 1, known = 1""",
                (int(campaign_id), int(q), int(r)),
            )
        else:
            conn.execute(
                """INSERT INTO campaign_hex_data (campaign_id, hex_q, hex_r, discovered)
                   VALUES (?,?,?,1)
                   ON CONFLICT(campaign_id, hex_q, hex_r) DO UPDATE SET discovered = 1""",
                (int(campaign_id), int(q), int(r)),
            )
        if has_disc_cid:
            conn.execute(
                "UPDATE world_hexes SET discovered_in_campaign_id = ? "
                "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1 "
                "AND discovered_in_campaign_id IS NULL",
                (int(campaign_id), int(q), int(r)),
            )
        n += 1
    return n


def reveal_from_payload(
    campaign_id: int,
    payload: dict[str, Any],
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Resolve a map recipe and reveal its hexes for the campaign.

    Pass ``conn`` to reuse an open transaction (caller commits); otherwise a
    connection is opened and committed here.
    """
    own = conn is None
    c = conn or _conn()
    try:
        hexes = compute_reveal_hexes(c, payload)
        count = reveal_hexes(c, int(campaign_id), hexes)
        if own:
            c.commit()
        return {
            "mode": str(payload.get("mode") or "").strip().lower(),
            "count": count,
            "revealed_hexes": [list(h) for h in hexes],
        }
    finally:
        if own:
            c.close()
