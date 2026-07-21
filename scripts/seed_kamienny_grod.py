#!/usr/bin/env python3
"""SG-5 (#1481) — Kamienny Gród w DB: hub + sub-lokacje + mapa lokalna.

Content-as-code (#1202): katalog = scripts/sg5_grod_spec.py w git, ten skrypt tylko
odtwarza go w bazie. Idempotentny — można puszczać wielokrotnie.

Co robi, po kolei:
 1. upsert huba `kamienny_grod` (macro) i 5 sub-lokacji (`location_type='sub'`,
    `parent_key`/`parent_id` → hub) — struktura osady wg #1212,
 2. spina hub z hexem (16,-17) przez `link_location_to_hex` (#1305/#1243 — goły
    UPDATE na world_hexes zostałby zmieciony przez reconcile),
 3. NAPRAWA po reseedzie krainy: `seed_world_map.py --region … --force` kasuje
    i wstawia od nowa hexy map_level=0, więc hub dostaje NOWE `world_hexes.id`,
    a lokalne hexy (map_level=1) zostają z osieroconym `parent_hex_id`. Skrypt
    przepina je na aktualny id huba, zanim cokolwiek dołoży,
 4. buduje mapę lokalną map_level=1 (`auto_assign_local_hex`, FAZA ML #993) —
    próg to ≥2 sub-lokacje, więc 5 subów aktywuje grid od razu.

URUCHOMIENIE (wewnątrz kontenera backendu — potrzebuje `app.services`):
    docker cp scripts/sg5_grod_spec.py ai-gm-dev-backend-1:/app/
    docker cp scripts/seed_kamienny_grod.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_kamienny_grod.py
    docker exec ai-gm-dev-backend-1 python /app/seed_kamienny_grod.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.hex_location_link import link_location_to_hex  # noqa: E402
from app.services.local_hex_service import (  # noqa: E402
    auto_assign_local_hex,
    get_hub_hex_id,
    get_local_hexes,
    normalize_hub_local_hexes,
)
from sg5_grod_spec import HUB, HUB_HEX, START_DEFAULT, SUBS  # noqa: E402

REGION = "siwe_granie"

UPSERT_MACRO = """
INSERT INTO game_locations
  (key, label, description, location_type, region, created_by, approved, canonical,
   map_icon, tier, biome, location_subtype, safe_for_rest,
   visible_before_visit, review_status, is_active)
VALUES (?,?,?,'macro',?, 'seed', 1, 1, ?,?,?,?,?, ?, 'permanent', 1)
ON CONFLICT(key) DO UPDATE SET
  label=excluded.label, description=excluded.description, region=excluded.region,
  map_icon=excluded.map_icon, tier=excluded.tier, biome=excluded.biome,
  location_subtype=excluded.location_subtype, safe_for_rest=excluded.safe_for_rest,
  is_active=1, updated_at=datetime('now')
"""

UPSERT_SUB = """
INSERT INTO game_locations
  (key, label, description, location_type, region, created_by, approved, canonical,
   map_icon, tier, biome, location_subtype, safe_for_rest,
   visible_before_visit, review_status, is_active, parent_id, parent_key)
VALUES (?,?,?,'sub',?, 'seed', 1, 1, ?,?,?,?,?, 0, 'permanent', 1, ?, ?)
ON CONFLICT(key) DO UPDATE SET
  label=excluded.label, description=excluded.description, region=excluded.region,
  map_icon=excluded.map_icon, tier=excluded.tier, biome=excluded.biome,
  location_subtype=excluded.location_subtype, safe_for_rest=excluded.safe_for_rest,
  parent_id=excluded.parent_id, parent_key=excluded.parent_key,
  is_active=1, updated_at=datetime('now')
"""


def reattach_local_hexes(conn: sqlite3.Connection, hub_key: str, sub_keys: list[str]) -> int:
    """Przepnij lokalne hexy na AKTUALNY id hexa huba (patrz krok 3 w docstringu)."""
    hub_hex_id = get_hub_hex_id(conn, hub_key)
    if hub_hex_id is None or not sub_keys:
        return 0
    marks = ",".join("?" * len(sub_keys))
    cur = conn.execute(
        f"UPDATE world_hexes SET parent_hex_id = ? "
        f"WHERE map_level = 1 AND location_key IN ({marks}) "
        f"AND (parent_hex_id IS NULL OR parent_hex_id != ?)",
        (hub_hex_id, *sub_keys, hub_hex_id),
    )
    return cur.rowcount or 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    # ── 1. hub ────────────────────────────────────────────────────────────────
    conn.execute(UPSERT_MACRO, (
        HUB["key"], HUB["label"], HUB["desc"], REGION,
        HUB["icon"], HUB["tier"], HUB["biome"], HUB["subtype"], HUB["safe"], HUB["visible"],
    ))
    hub_id = conn.execute("SELECT id FROM game_locations WHERE key=?", (HUB["key"],)).fetchone()["id"]

    q, r = HUB_HEX
    hx = conn.execute(
        "SELECT location_key FROM world_hexes WHERE map_level=0 AND q=? AND r=?", (q, r)
    ).fetchone()
    if hx is None:
        print(f"  ✗ brak hexa ({q},{r}) w world_hexes — najpierw "
              f"seed_world_map.py --region {REGION} --force")
        return 1
    linked = link_location_to_hex(conn, HUB["key"], q, r)
    print(f"  HUB {HUB['label']:34s} ({q},{r})  id={hub_id}  link={'OK' if linked else 'FAIL'}")

    # ── 2. sub-lokacje ────────────────────────────────────────────────────────
    for s in SUBS:
        conn.execute(UPSERT_SUB, (
            s["key"], s["label"], s["desc"], REGION,
            s["icon"], s["tier"], s["biome"], s["subtype"], s["safe"],
            hub_id, HUB["key"],
        ))
        print(f"  sub {s['label']:44s} safe_for_rest={s['safe']}")
    conn.commit()

    # ── 3. naprawa osieroconych lokalnych hexów po reseedzie krainy ───────────
    fixed = reattach_local_hexes(conn, HUB["key"], [s["key"] for s in SUBS])
    if fixed:
        print(f"  przepięto lokalnych hexów na aktualny hex huba: {fixed}")
    conn.commit()

    # ── 4. mapa lokalna (FAZA ML #993) ────────────────────────────────────────
    auto_assign_local_hex(conn, SUBS[0]["key"], HUB["key"])
    normalize_hub_local_hexes(conn, HUB["key"])
    conn.commit()

    local = get_local_hexes(conn, HUB["key"])
    print(f"\n  mapa lokalna: {len(local)} hexów map_level=1")
    for h in sorted(local, key=lambda x: (x["q"], x["r"])):
        print(f"    ({h['q']},{h['r']})  {h['label']}  enc={h['encounter_chance']}")

    # ── kontrola ──────────────────────────────────────────────────────────────
    problems = []
    canon = conn.execute(
        "SELECT location_key FROM world_hexes WHERE map_level=0 AND q=? AND r=?", (q, r)
    ).fetchone()
    if not canon or canon["location_key"] != HUB["key"]:
        problems.append(f"hex ({q},{r}) nie wskazuje na {HUB['key']}")
    orphan = conn.execute(
        "SELECT count(*) c FROM game_locations WHERE parent_key=? AND is_active=1 "
        "AND key NOT IN (SELECT location_key FROM world_hexes WHERE map_level=1 "
        "AND location_key IS NOT NULL)", (HUB["key"],)).fetchone()["c"]
    if orphan:
        problems.append(f"{orphan} sub-lokacji bez hexa na mapie lokalnej")
    if START_DEFAULT not in [s["key"] for s in SUBS]:
        problems.append(f"domyślny start {START_DEFAULT} nie jest sub-lokacją huba")

    conn.commit()
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY: " + "; ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
