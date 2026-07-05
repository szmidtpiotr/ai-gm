"""Fog-of-war (FOW) known-state computation — PM1 (#1220).

Three-state FOW per campaign: ``outline`` < ``known`` < ``discovered``.

- ``discovered`` — hero physically visited: full detail (unchanged, written by
  ``hex_travel_service`` / ``combat_service`` / ``map_reveal_service``).
- ``known`` — hero *knows the hex exists*: terrain (``hex_type``) visible +
  ``label`` only for landmarks / canonical settlements. NEVER exposes
  ``location_key`` or anything from ``game_locations`` (sub-locations, encounters,
  loot, campaign adventure sites).
- ``outline`` — dashed empty outline for adjacent unvisited hexes.

The ``known`` set is the union of three computed layers (W1/W2/W3) plus any
persisted ``known`` rows written by R6 (#1246, travelled-route hexes). Layer 4
(new-region unlock) is PM2 (#1221) — NOT implemented here.

Design constraints (Piotr, 2026-07-05, frozen):
- one pass over the hex index, sets in memory, zero per-hex query;
- reusable gazetteer predicate (PM2 reuses it for other regions);
- ``discovered`` wins over ``known`` wins over ``outline``.
"""

from __future__ import annotations

# Landmark hex types — always get a visible label when known.
# NB: DB uses both 'town' and 'city' for major settlements; include both.
LANDMARK_HEX_TYPES = {"city", "town", "village", "bridge", "road", "river"}

# World layer (W3) — visible everywhere regardless of distance: major cities +
# big rivers. Canonical settlements added on top of these.
WORLD_HEX_TYPES = {"city", "town", "river"}

# Settlement hex types — canonical settlements shown globally (W3).
SETTLEMENT_HEX_TYPES = {"city", "town", "village"}

DEFAULT_BUBBLE_RADIUS = 4


def is_landmark_hex(row: dict, canonical_keys: set[str]) -> bool:
    """Gazetteer predicate — reusable (PM2 uses it for other regions).

    A hex qualifies as a gazetteer landmark when its terrain is a landmark type
    (settlement / road / bridge / river) OR it carries a ``location_key`` that
    maps to a canonical location. Region scoping is the caller's job.
    """
    if row.get("hex_type") in LANDMARK_HEX_TYPES:
        return True
    lk = row.get("location_key")
    return bool(lk and lk in canonical_keys)


def _is_world_hex(row: dict, canonical_keys: set[str]) -> bool:
    """W3 predicate — visible globally without radius."""
    ht = row.get("hex_type")
    if ht in WORLD_HEX_TYPES:
        return True
    lk = row.get("location_key")
    return bool(lk and lk in canonical_keys and ht in SETTLEMENT_HEX_TYPES)


def _coords_within(center: tuple[int, int], radius: int):
    """Yield all axial coords within ``radius`` of ``center`` (inclusive)."""
    cq, cr = center
    for dq in range(-radius, radius + 1):
        lo = max(-radius, -dq - radius)
        hi = min(radius, -dq + radius)
        for dr in range(lo, hi + 1):
            yield (cq + dq, cr + dr)


def compute_known_coords(
    all_hexes_l0: dict[tuple[int, int], dict],
    discovered_coords: set[tuple[int, int]],
    origin_region: str | None,
    canonical_keys: set[str],
    bubble_radius: int = DEFAULT_BUBBLE_RADIUS,
    known_regions: set[str] | None = None,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """Compute the ``known`` coordinate set and the label-worthy subset.

    Args:
        all_hexes_l0: overworld (map_level=0) hex index → row with at least
            ``hex_type``, ``region``, ``location_key``.
        discovered_coords: hexes already fully discovered this campaign.
        origin_region: region of the campaign's starting hex (W1 gazetteer).
        canonical_keys: set of ``game_locations.key`` where ``canonical=1``.
        bubble_radius: W2 rolling-bubble radius (axial), from setting.
        known_regions: PM2 (#1221) — every region whose gazetteer (W1) the hero
            has unlocked (start region + regions entered via travel). When given,
            the W1 gazetteer is computed for EACH region in the set. Falls back to
            ``{origin_region}`` when omitted (PM1 pre-PM2 behaviour).

    Returns:
        ``(known_coords, label_coords)`` where ``label_coords ⊆ known_coords``
        are the hexes that should expose their ``label`` (landmarks / canonical).
        ``discovered_coords`` are excluded from both (discovered wins).
    """
    known: set[tuple[int, int]] = set()
    labelable: set[tuple[int, int]] = set()

    # PM2 (#1221): W1 gazetteer spans every unlocked region, not just origin.
    _w1_regions: set[str] = set(known_regions) if known_regions else set()
    if origin_region:
        _w1_regions.add(origin_region)

    # W1 (region gazetteer) + W3 (world) — single pass over the index.
    for coord, row in all_hexes_l0.items():
        landmark = is_landmark_hex(row, canonical_keys)
        if _w1_regions and row.get("region") in _w1_regions and landmark:
            known.add(coord)
            labelable.add(coord)
        if _is_world_hex(row, canonical_keys):
            known.add(coord)
            labelable.add(coord)

    # W2 rolling bubble — full terrain within radius of every discovered hex.
    if bubble_radius and bubble_radius > 0:
        for dc in discovered_coords:
            for coord in _coords_within(dc, bubble_radius):
                row = all_hexes_l0.get(coord)
                if row is None:
                    continue
                known.add(coord)
                if is_landmark_hex(row, canonical_keys):
                    labelable.add(coord)

    # discovered wins over known.
    known -= discovered_coords
    labelable -= discovered_coords
    return known, labelable


def compute_campaign_known_discovered(conn, campaign_id, character_id):
    """PM3 #1222: campaign FOW sets for the descriptive-travel resolver.

    Mirrors the world-map endpoint's known/discovered computation (turns.py) in a
    reusable form: returns ``(known_coords, discovered_coords, all_hexes_l0)`` where
    ``all_hexes_l0`` is the overworld hex index (coord → row). ``known_coords``
    already excludes ``discovered_coords`` (discovered wins).
    """
    import json as _j

    all_hexes_l0: dict = {}
    for row in conn.execute(
        "SELECT q, r, hex_type, label, location_key, region FROM world_hexes "
        "WHERE is_active = 1 AND map_level = 0"
    ).fetchall():
        all_hexes_l0[(int(row["q"]), int(row["r"]))] = dict(row)

    discovered: set = set()
    persisted_known: set = set()
    # campaign_hex_data.known may be absent on legacy/test schemas — degrade.
    try:
        rows = conn.execute(
            "SELECT hex_q, hex_r, discovered, known FROM campaign_hex_data WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchall()
    except Exception:
        rows = conn.execute(
            "SELECT hex_q, hex_r, discovered FROM campaign_hex_data WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchall()
    for row in rows:
        q, r = int(row["hex_q"]), int(row["hex_r"])
        if row["discovered"]:
            discovered.add((q, r))
        elif ("known" in row.keys() and row["known"]):
            persisted_known.add((q, r))

    canonical_keys = {
        r["key"] for r in conn.execute(
            "SELECT key FROM game_locations WHERE canonical = 1 AND key IS NOT NULL"
        ).fetchall()
    }

    gs = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1", (campaign_id,)
    ).fetchone()
    sf = _j.loads((gs["session_flags"] if gs else None) or "{}")

    origin_region = None
    try:
        from app.services.hex_travel_service import resolve_starting_hex as _rsh
        _start = _rsh(campaign_id, character_id, None, conn)
        _srow = all_hexes_l0.get((int(_start["q"]), int(_start["r"])))
        if _srow:
            origin_region = _srow.get("region")
    except Exception:
        pass
    cur = sf.get("current_hex")
    if not origin_region and cur:
        _crow = all_hexes_l0.get((int(cur.get("q", 0)), int(cur.get("r", 0))))
        if _crow:
            origin_region = _crow.get("region")

    known_regions: set = set()
    if origin_region:
        known_regions.add(origin_region)
    kr = sf.get("known_regions")
    if isinstance(kr, list):
        known_regions |= {x for x in kr if x}

    bubble_radius = DEFAULT_BUBBLE_RADIUS
    try:
        _br = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = 'knowledge_bubble_radius' LIMIT 1"
        ).fetchone()
        if _br and _br["value"] is not None:
            bubble_radius = int(_br["value"])
    except Exception:
        pass

    known_coords, _label = compute_known_coords(
        all_hexes_l0, discovered, origin_region, canonical_keys, bubble_radius,
        known_regions=known_regions,
    )
    for coord in persisted_known:
        if coord not in discovered:
            known_coords.add(coord)
    return known_coords, discovered, all_hexes_l0
