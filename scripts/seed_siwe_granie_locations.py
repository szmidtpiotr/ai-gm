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
from sg4_locations_spec import LOCATIONS  # noqa: E402

REGION = "siwe_granie"

UPSERT = """
INSERT INTO game_locations
  (key, label, description, location_type, region, created_by, approved, canonical,
   ai_generated, map_icon, tier, biome, location_subtype, safe_for_rest,
   visible_before_visit, review_status, is_active)
VALUES (?,?,?,'macro',?, 'seed', 1, 1, 0, ?,?,?,?,?, 1, 'permanent', 1)
ON CONFLICT(key) DO UPDATE SET
  label=excluded.label,
  description=excluded.description,
  region=excluded.region,
  map_icon=excluded.map_icon,
  tier=excluded.tier,
  biome=excluded.biome,
  location_subtype=excluded.location_subtype,
  safe_for_rest=excluded.safe_for_rest,
  is_active=1,
  updated_at=datetime('now')
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
        exists = conn.execute("SELECT 1 FROM game_locations WHERE key=?", (loc["key"],)).fetchone()
        conn.execute(UPSERT, (
            loc["key"], loc["label"], loc["desc"], REGION,
            loc["icon"], loc["tier"], loc["biome"], loc["subtype"], loc["safe"],
        ))
        q, r = hx["q"], hx["r"]
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
