"""U28 — Placement engine: mechaniczne osadzanie lokacji na hexach."""
import json
import random
import sqlite3
from typing import Optional


def try_place_location_on_hex(
    conn: sqlite3.Connection,
    q: int,
    r: int,
    hex_type: str,
    campaign_seed: int = 0,
    region: str = "kresy",
) -> Optional[str]:
    """
    Próbuje osadzić lokację z bazy na hexie (q,r) wg reguł terenu i krainy.
    Zwraca location_key jeśli osadzono lub hex miał już lokację, None jeśli hex pozostaje pusty.

    Deterministyczne per (q, r, campaign_seed) — ta sama kampania zawsze daje ten sam wynik.
    Lokacja osadzona raz (placement='placed') nie wchodzi ponownie do puli.
    Filtruje kandydatów wg region — lokacje z innej krainy nie trafią na hex tej krainy.
    """
    existing = conn.execute(
        "SELECT location_key FROM world_hexes"
        " WHERE q=? AND r=? AND map_level=0 AND region=? AND is_active=1",
        (q, r, region),
    ).fetchone()
    if existing and existing["location_key"]:
        return existing["location_key"]

    cfg = conn.execute(
        "SELECT location_spawn_chance FROM hex_type_config WHERE hex_type=?",
        (hex_type,),
    ).fetchone()
    spawn_chance = cfg["location_spawn_chance"] if cfg else 0.15

    rng = random.Random(q * 31 + r * 17 + campaign_seed)
    if rng.random() > spawn_chance:
        return None

    candidates = conn.execute(
        "SELECT key, terrain_tags FROM game_locations"
        " WHERE approved=1 AND placement='floating' AND is_active=1"
        " AND (region = ? OR region IS NULL)",
        (region,),
    ).fetchall()

    matching = []
    for row in candidates:
        try:
            tags = json.loads(row["terrain_tags"] or "[]")
        except (json.JSONDecodeError, TypeError):
            tags = []
        if hex_type in tags:
            matching.append(row["key"])

    if not matching:
        return None

    chosen_key = rng.choice(matching)

    conn.execute(
        "UPDATE world_hexes SET location_key=?"
        " WHERE q=? AND r=? AND map_level=0 AND region=? AND is_active=1",
        (chosen_key, q, r, region),
    )
    conn.execute(
        "UPDATE game_locations SET placement='placed', world_hex_q=?, world_hex_r=? WHERE key=?",
        (q, r, chosen_key),
    )
    conn.commit()

    return chosen_key


def get_floating_locations(conn: sqlite3.Connection) -> list:
    """Zwraca listę approved lokacji w stanie floating (niezakotwiczonych na hexach)."""
    rows = conn.execute(
        "SELECT key, label, location_type, location_subtype, terrain_tags, biome, tier,"
        " description, parent_key, ai_generated, region"  # #590: full fields for preview/edit modal
        " FROM game_locations"
        " WHERE placement='floating' AND approved=1 AND is_active=1"
        " ORDER BY label",
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["terrain_tags"] = json.loads(d["terrain_tags"] or "[]")
        except (json.JSONDecodeError, TypeError):
            d["terrain_tags"] = []
        result.append(d)
    return result
