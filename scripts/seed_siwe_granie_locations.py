#!/usr/bin/env python3
"""SG-4 (#1481) — seed lokacji makro Siwych Grań do `game_locations` + spięcie z hexami.

Content-as-code (#1202): katalog = scripts/sg4_locations_spec.py w git, ten skrypt
tylko odtwarza go w DB. Idempotentny — można puszczać wielokrotnie.

Spięcie z mapą idzie WYŁĄCZNIE przez `link_location_to_hex` (#1305/#1243):
goły INSERT bez hexa albo goły UPDATE na `world_hexes` zostałby wyczyszczony
przez reconcile. Kanon = `world_hexes.location_key`, `game_locations.world_hex_q/r`
to tylko cache.

URUCHOMIENIE (wewnątrz kontenera backendu — potrzebuje `app.services`):
    docker cp scripts/sg4_locations_spec.py ai-gm-dev-backend-1:/app/
    docker cp scripts/seed_siwe_granie_locations.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_siwe_granie_locations.py
    docker exec ai-gm-dev-backend-1 python /app/seed_siwe_granie_locations.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.hex_location_link import link_location_to_hex  # noqa: E402
from app.services.location_factory import LocationSource, create_location  # noqa: E402
from sg4_locations_spec import LOCATIONS  # noqa: E402

REGION = "siwe_granie"

#: #1526 (fala 3) — nowe lokacje wchodza JEDNYMI drzwiami (`create_location`);
#: powtorne uruchomienie seeda odswieza tresc zwyklym UPDATE-em. Stary UPSERT
#: pisal tez kolumne `ai_generated`, skasowana w fali 2 (#1525) — czyli od tamtej
#: pory ten seed by sie wywalil. Jedne drzwi likwiduja ta klase bledow.
_REFRESH = """
UPDATE game_locations SET
  label=?, description=?, region=?, map_icon=?, tier=?, biome=?,
  location_subtype=?, safe_for_rest=?, is_active=1, updated_at=datetime('now')
WHERE key=?
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    added = updated = 0

    for loc in LOCATIONS:
        # Hex bierzemy z KANONU już wsianego do world_hexes (plik krainy w git
        # niesie `location_key`) — nie duplikujemy współrzędnych w dwóch miejscach.
        hx = conn.execute(
            "SELECT q, r FROM world_hexes WHERE map_level=0 AND location_key=?",
            (loc["key"],)).fetchone()
        if hx is None:
            print(f"  ✗ {loc['key']}: brak hexa z tym location_key — najpierw "
                  f"seed_world_map.py --region {REGION} --force")
            return 1
        q, r = hx["q"], hx["r"]
        res = create_location(
            conn,
            key=loc["key"],
            label=loc["label"],
            source=LocationSource.SEED,
            description=loc["desc"],
            location_type="macro",
            region=REGION,
            map_icon=loc["icon"],
            tier=loc["tier"],
            biome=loc["biome"],
            location_subtype=loc["subtype"],
            safe_for_rest=loc["safe"],
            visible_before_visit=True,
            canonical=True,
            hex_q=q,
            hex_r=r,
            commit=False,
        )
        exists = not res["created"]
        if exists:
            conn.execute(_REFRESH, (
                loc["label"], loc["desc"], REGION, loc["icon"], loc["tier"],
                loc["biome"], loc["subtype"], loc["safe"], loc["key"],
            ))
        ok = link_location_to_hex(conn, loc["key"], q, r)
        if exists:
            updated += 1
        else:
            added += 1
        print(f"  {loc['cls']} {loc['label']:38s} ({q},{r})  "
              f"{'UPDATE' if exists else 'INSERT'}  link={'OK' if ok else 'FAIL'}")

    # Kontrola: hex kanonu wskazuje tę lokację, a cache zgadza się z hexem.
    drift = conn.execute("""
        SELECT gl.key, gl.world_hex_q, gl.world_hex_r, wh.location_key
        FROM game_locations gl
        LEFT JOIN world_hexes wh
          ON wh.q = gl.world_hex_q AND wh.r = gl.world_hex_r AND wh.map_level = 0
        WHERE gl.region = ? AND gl.location_type = 'macro' AND gl.world_hex_q IS NOT NULL
          AND (wh.location_key IS NULL OR wh.location_key != gl.key)
    """, (REGION,)).fetchall()

    if a.dry_run:
        conn.rollback()
        print("\n--dry-run: rollback")
    else:
        conn.commit()

    print(f"\nnowych: {added}, zaktualizowanych: {updated}, rozjazdów hex↔lokacja: {len(drift)}")
    for d in drift:
        print("  ✗", dict(d))
    conn.close()
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
