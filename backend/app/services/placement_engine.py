"""U28 — Placement engine: mechaniczne osadzanie lokacji na hexach."""
import json
import random
import sqlite3
from typing import Optional

from app.core.constants import DEFAULT_REGION


def try_place_location_on_hex(
    conn: sqlite3.Connection,
    q: int,
    r: int,
    hex_type: str,
    campaign_seed: int = 0,
    region: str = DEFAULT_REGION,
) -> Optional[str]:
    """
    Próbuje osadzić lokację z bazy na hexie (q,r) wg reguł terenu i krainy.
    Zwraca location_key jeśli osadzono lub hex miał już lokację, None jeśli hex pozostaje pusty.

    Deterministyczne per (q, r, campaign_seed) — ta sama kampania zawsze daje ten sam wynik.
    Lokacja osadzona raz (wskazana przez heks — kanon #1243) nie wchodzi ponownie do puli.
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

    # #1408: only TOP-LEVEL locations may become standalone overworld POIs.
    # `location_type='sub'` rows are CHILDREN of a hub (e.g. "Brzezino: Święta
    # Polanka" under the village Brzezino) and belong to the parent's LOCAL map,
    # not the world map. Without this guard a floating sub with a matching
    # terrain_tag (a forest shrine) was stamped onto a random overworld forest
    # hex far from its parent, showing a settlement-style POI label in the wild.
    # #1525: pula floating liczona z KANONU (żaden heks nie wskazuje lokacji),
    # nie ze skasowanej kolumny `placement`.
    from app.services.hex_location_link import not_placed_sql

    candidates = conn.execute(
        "SELECT key, terrain_tags FROM game_locations"
        " WHERE approved=1 AND is_active=1"
        f" AND {not_placed_sql(conn)}"
        " AND COALESCE(location_type, '') != 'sub'"
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

    # #1243: single writer — hex canon + derived cache. (region already validated
    # above, so the extra region predicate the old direct UPDATE carried is moot.)
    from app.services.hex_location_link import link_location_to_hex
    link_location_to_hex(conn, chosen_key, q, r)
    conn.commit()

    return chosen_key


def get_floating_locations(conn: sqlite3.Connection) -> list:
    """Zwraca listę approved lokacji w stanie floating (niezakotwiczonych na hexach).

    #1525: „floating" = żaden heks świata nie wskazuje tej lokacji (kanon #1243).
    """
    from app.services.hex_location_link import not_placed_sql

    rows = conn.execute(
        "SELECT key, label, location_type, location_subtype, terrain_tags, biome, tier,"
        " description, parent_key, created_by, region"  # #590: full fields for preview/edit modal
        " FROM game_locations"
        f" WHERE approved=1 AND is_active=1 AND {not_placed_sql(conn)}"
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
