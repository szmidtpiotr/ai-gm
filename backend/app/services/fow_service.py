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
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """Compute the ``known`` coordinate set and the label-worthy subset.

    Args:
        all_hexes_l0: overworld (map_level=0) hex index → row with at least
            ``hex_type``, ``region``, ``location_key``.
        discovered_coords: hexes already fully discovered this campaign.
        origin_region: region of the campaign's starting hex (W1 gazetteer).
        canonical_keys: set of ``game_locations.key`` where ``canonical=1``.
        bubble_radius: W2 rolling-bubble radius (axial), from setting.

    Returns:
        ``(known_coords, label_coords)`` where ``label_coords ⊆ known_coords``
        are the hexes that should expose their ``label`` (landmarks / canonical).
        ``discovered_coords`` are excluded from both (discovered wins).
    """
    known: set[tuple[int, int]] = set()
    labelable: set[tuple[int, int]] = set()

    # W1 (region gazetteer) + W3 (world) — single pass over the index.
    for coord, row in all_hexes_l0.items():
        landmark = is_landmark_hex(row, canonical_keys)
        if origin_region and row.get("region") == origin_region and landmark:
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
