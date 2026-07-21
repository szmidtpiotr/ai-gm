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
from app.services.location_factory import LocationSource, create_location  # noqa: E402
from app.services.local_hex_service import (  # noqa: E402
    auto_assign_local_hex,
    get_hub_hex_id,
    get_local_hexes,
    normalize_hub_local_hexes,
)
from sg5_grod_spec import HUB, HUB_HEX, START_DEFAULT, SUBS  # noqa: E402

REGION = "siwe_granie"

#: #1526 (fala 3) — nowe lokacje wchodza JEDNYMI drzwiami (`create_location`);
#: powtorne uruchomienie seeda odswieza tresc zwyklym UPDATE-em.
_REFRESH = """
UPDATE game_locations SET
  label=?, description=?, region=?, map_icon=?, tier=?, biome=?,
  location_subtype=?, safe_for_rest=?, is_active=1, updated_at=datetime('now')
WHERE key=?
"""


def upsert_seed_location(
    conn: sqlite3.Connection, spec: dict, *, is_sub: bool,
    parent_key: str | None = None, parent_id: int | None = None,
) -> bool:
    """Wstaw (jedne drzwi) albo odswiez lokacje krainy. Zwraca True gdy nowa."""
    res = create_location(
        conn,
        key=spec["key"],
        label=spec["label"],
        source=LocationSource.SEED,
        description=spec["desc"],
        location_type="sub" if is_sub else "macro",
        parent_key=parent_key,
        parent_id=parent_id,
        region=REGION,
        map_icon=spec["icon"],
        tier=spec["tier"],
        biome=spec["biome"],
        location_subtype=spec["subtype"],
        safe_for_rest=spec["safe"],
        visible_before_visit=(0 if is_sub else spec.get("visible", 1)),
        canonical=True,
        commit=False,
    )
    if not res["created"]:
        conn.execute(_REFRESH, (
            spec["label"], spec["desc"], REGION, spec["icon"], spec["tier"],
            spec["biome"], spec["subtype"], spec["safe"], spec["key"],
        ))
        if is_sub:
            conn.execute(
                "UPDATE game_locations SET parent_key=?, parent_id=? WHERE key=?",
                (parent_key, parent_id, spec["key"]),
            )
    return res["created"]


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
    upsert_seed_location(conn, HUB, is_sub=False)
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
        upsert_seed_location(conn, s, is_sub=True, parent_key=HUB["key"], parent_id=hub_id)
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
