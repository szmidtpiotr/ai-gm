#!/usr/bin/env python3
"""CB-5 (#1489/#1490) — Szept Koron: hub + sub-lokacje + mapa lokalna.

Źródło prawdy: docs/world/regions/czarnobor.md §4 (hub + suby). Wzorzec:
scripts/seed_kamienny_grod.py + sg5_grod_spec.py (SG-5) — ta sama mechanika,
inna kraina. Spec wpisany INLINE (jeden plik = jedno źródło dla CB-5).

Hub `szept_koron` (macro) istnieje od CB-4 na hexie (74,-12); ten skrypt dokłada
5 sub-lokacji (`location_type='sub'`, `parent_key`/`parent_id` → hub) i buduje
mapę lokalną map_level=1 (`auto_assign_local_hex`, FAZA ML #993; próg ≥2 suby).

KOLEJNOŚĆ SUB-LOKACJI MA ZNACZENIE: `auto_assign_local_hex` układa je po `id ASC`,
więc pierwsza (Gościnne Drzewo) dostaje hex (0,0) — środek mapy lokalnej i domyślny
punkt wejścia obcego (lore §9: default start elfa = Gościnne Drzewo).

Idempotentny — można puszczać wielokrotnie.

URUCHOMIENIE (wewnątrz kontenera backendu — potrzebuje `app.services`):
    docker cp scripts/seed_szept_koron.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_szept_koron.py
    docker exec ai-gm-dev-backend-1 python /app/seed_szept_koron.py --db /tmp/verify.db
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
from app.services.location_factory import LocationSource, create_location  # noqa: E402

REGION = "czarnobor"

HUB_KEY = "szept_koron"
HUB_HEX = (74, -12)  # z CB-4 (seed_czarnobor_locations.py)

# Sub-lokacje osady. `subtype` niesie słowa-klucze usług (location_services.py):
#   'guest-inn'    → 'inn'  → nocleg/posiłek (Gościnne Drzewo — jedyny nocleg obcych),
#   'bowyer-forge' → 'forge'→ blacksmith_repair (Łukodzielnia — naprawa sprzętu),
#   pozostałe (grove/hall/market) bez usług — czysty handel lub tło narracyjne.
# safe=1 → niższa szansa zdarzenia na mapie lokalnej (SAFE 0.10 vs RISKY 0.20).
SUBS = [
    dict(
        key="szept_goscinne_drzewo", label="Szept Koron: Gościnne Drzewo",
        subtype="guest-inn", icon="town", safe=1, tier=1, biome="forest",
        desc="Jedyne miejsce w Szepcie Koron, gdzie obcy może przenocować — potężny "
             "dąb z pomostami i izbami wplecionymi w konarach, z dala od Kręgu. "
             "Elfy przyjmują tu gościa, ale nie wpuszczają go głębiej: kto śpi na "
             "Gościnnym Drzewie, ten boru jeszcze nie zobaczył.",
        atmo="Ciepłe światło próchna w plecionych lampionach, skrzypienie konarów "
             "i cichy szept liści, który nigdy do końca nie milknie.",
    ),
    dict(
        key="szept_targ_wymienny", label="Szept Koron: Targ Wymienny",
        subtype="barter-market", icon="town", safe=1, tier=1, biome="forest",
        desc="Pomost handlu wymiennego rozpięty między koronami: łuki, strzały, "
             "skóry i zioła kniei kładzie się tu obok towarów, które zwiadowcy "
             "przynieśli spoza boru. Elfy nie liczą w złocie chętnie — liczą w tym, "
             "co się komu przyda.",
        atmo="Zapach żywicy, garbowanej skóry i suszonych ziół; towar wisi na "
             "sznurach między gałęziami i kołysze się na wietrze.",
    ),
    dict(
        key="szept_lukodzielnia", label="Szept Koron: Łukodzielnia",
        subtype="bowyer-forge", icon="town", safe=1, tier=2, biome="forest",
        desc="Warsztat łuczniczy Sylvara wpleciony w rozłożysty konar — tu gnie się "
             "cis, kręci cięciwy i pierzy strzały. Łukmistrz naprawi i przekuje "
             "sprzęt, a o drewnie boru wie więcej niż niejeden Stroiciel.",
        atmo="Woń struganego drewna i wosku, rzędy naciągów schnących pod stropem "
             "i miarowy dźwięk struganego cisu.",
    ),
    dict(
        key="szept_krag_starszych", label="Szept Koron: Krąg Starszych",
        subtype="council-grove", icon="forest", safe=1, tier=2, biome="forest",
        desc="Polana w koronie najstarszego drzewa, gdzie Krąg Starszych stroi "
             "gasnące wardy i spiera się o los boru: zamknąć się i cierpliwie "
             "śpiewać, czy otworzyć i szukać przyczyny na zewnątrz. Obcych wpuszcza "
             "się tu rzadko i nie bez powodu.",
        atmo="Krąg żywych pni splecionych w salę bez ścian; pieśń strojenia niesie "
             "się nisko, a tam, gdzie ward zgasł, słychać tylko wiatr.",
    ),
    dict(
        key="szept_piesniarnia", label="Szept Koron: Pieśniarnia",
        subtype="song-hall", icon="forest", safe=1, tier=1, biome="forest",
        desc="Serce strojenia — sala, w której pieśń podtrzymująca stróżowe drzewa "
             "przechodzi z pokolenia na pokolenie. Aerlin uczy tu młodych zwiadowców "
             "słyszeć, które drzewo milknie, zanim sczernieje.",
        atmo="Głosy splecione w jeden ton, który drży w piersi; między zwrotkami "
             "cisza tak pełna, że słychać własne tętno.",
    ),
]

START_DEFAULT = "szept_goscinne_drzewo"  # lore §9 — domyślne wejście obcego/elfa

_REFRESH = """
UPDATE game_locations SET
  label=?, description=?, region=?, map_icon=?, tier=?, biome=?,
  location_subtype=?, safe_for_rest=?, is_active=1, updated_at=datetime('now')
WHERE key=?
"""


def upsert_sub(conn, spec, hub_id):
    res = create_location(
        conn,
        key=spec["key"], label=spec["label"], source=LocationSource.SEED,
        description=spec["desc"], location_type="sub",
        parent_key=HUB_KEY, parent_id=hub_id, region=REGION,
        map_icon=spec["icon"], tier=spec["tier"], biome=spec["biome"],
        location_subtype=spec["subtype"], safe_for_rest=spec["safe"],
        visible_before_visit=0, canonical=False, commit=False,
    )
    if not res["created"]:
        conn.execute(_REFRESH, (
            spec["label"], spec["desc"], REGION, spec["icon"], spec["tier"],
            spec["biome"], spec["subtype"], spec["safe"], spec["key"],
        ))
        conn.execute(
            "UPDATE game_locations SET parent_key=?, parent_id=? WHERE key=?",
            (HUB_KEY, hub_id, spec["key"]),
        )
    return res["created"]


def reattach_local_hexes(conn, sub_keys):
    hub_hex_id = get_hub_hex_id(conn, HUB_KEY)
    if hub_hex_id is None or not sub_keys:
        return 0
    marks = ",".join("?" * len(sub_keys))
    cur = conn.execute(
        f"UPDATE world_hexes SET parent_hex_id=? "
        f"WHERE map_level=1 AND location_key IN ({marks}) "
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

    # ── 1. hub musi już istnieć (CB-4) i wisieć na swoim hexie ────────────────
    hub = conn.execute("SELECT id FROM game_locations WHERE key=?", (HUB_KEY,)).fetchone()
    if hub is None:
        print(f"  ✗ brak huba {HUB_KEY} — najpierw seed_czarnobor_locations.py (CB-4)")
        return 1
    hub_id = hub["id"]
    q, r = HUB_HEX
    if conn.execute("SELECT 1 FROM world_hexes WHERE map_level=0 AND q=? AND r=?", (q, r)).fetchone() is None:
        print(f"  ✗ brak hexa ({q},{r}) — najpierw seed_world_map.py --region {REGION} --force")
        return 1
    link_location_to_hex(conn, HUB_KEY, q, r)
    print(f"  HUB {HUB_KEY} id={hub_id} @ ({q},{r})")

    # ── 2. sub-lokacje ───────────────────────────────────────────────────────
    for s in SUBS:
        created = upsert_sub(conn, s, hub_id)
        print(f"  sub {s['label']:38s} safe={s['safe']} {'NEW' if created else 'refresh'}")
    conn.commit()

    # ── 3. naprawa osieroconych lokalnych hexów po reseedzie krainy ──────────
    fixed = reattach_local_hexes(conn, [s["key"] for s in SUBS])
    if fixed:
        print(f"  przepięto lokalnych hexów na hex huba: {fixed}")
    conn.commit()

    # ── 4. mapa lokalna (FAZA ML #993) ───────────────────────────────────────
    auto_assign_local_hex(conn, SUBS[0]["key"], HUB_KEY)
    normalize_hub_local_hexes(conn, HUB_KEY)
    conn.commit()

    local = get_local_hexes(conn, HUB_KEY)
    print(f"\n  mapa lokalna: {len(local)} hexów map_level=1")
    for h in sorted(local, key=lambda x: (x["q"], x["r"])):
        print(f"    ({h['q']},{h['r']})  {h['label']}")

    # ── kontrola ─────────────────────────────────────────────────────────────
    problems = []
    canon = conn.execute(
        "SELECT location_key FROM world_hexes WHERE map_level=0 AND q=? AND r=?", (q, r)
    ).fetchone()
    if not canon or canon["location_key"] != HUB_KEY:
        problems.append(f"hex ({q},{r}) nie wskazuje na {HUB_KEY}")
    orphan = conn.execute(
        "SELECT count(*) c FROM game_locations WHERE parent_key=? AND is_active=1 "
        "AND key NOT IN (SELECT location_key FROM world_hexes WHERE map_level=1 "
        "AND location_key IS NOT NULL)", (HUB_KEY,)).fetchone()["c"]
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
