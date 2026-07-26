#!/usr/bin/env python3
"""MP-5 (#1494) — Solny Próg: hub Piętnowanych + sub-lokacje + mapa lokalna.

Źródło prawdy: docs/world/regions/martwe_pustkowia.md §4 (hub + suby), §8 (start).
Wzorzec: scripts/seed_szept_koron.py (CB-5) — ta sama mechanika, inna kraina.

Hub `solny_prog` (macro) istnieje od MP-4 na hexie (64,37); ten skrypt dokłada
5 sub-lokacji (`location_type='sub'`, `parent_key`/`parent_id` → hub) i buduje
mapę lokalną map_level=1 (`auto_assign_local_hex`, FAZA ML #993; próg ≥2 suby).

KOLEJNOŚĆ SUB-LOKACJI MA ZNACZENIE: `auto_assign_local_hex` układa je po `id ASC`,
więc pierwsza (gospoda) dostaje hex (0,0) — środek mapy lokalnej i domyślny punkt
wejścia obcego (lore §8: default start Piętnowanego = gospoda w Solnym Progu).

Idempotentny — można puszczać wielokrotnie.

URUCHOMIENIE (wewnątrz kontenera backendu — potrzebuje `app.services`):
    docker cp scripts/seed_solny_prog.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_solny_prog.py
    docker exec ai-gm-dev-backend-1 python /app/seed_solny_prog.py --db /tmp/verify.db
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

REGION = "martwe_pustkowia"

HUB_KEY = "solny_prog"
HUB_HEX = (64, 37)  # z MP-4 (seed_martwe_pustkowia_locations.py)

# Sub-lokacje enklawy. `subtype` niesie słowa-klucze usług (location_services.py):
#   'guest-inn'  → 'inn' → nocleg/posiłek (gospoda — jedyne miejsce dla obcych),
#   pozostałe (council/hall/market/warehouse) bez usług — handel lub tło narracyjne.
# safe=1 → niższa szansa zdarzenia na mapie lokalnej (SAFE 0.10 vs RISKY 0.20).
SUBS = [
    dict(
        key="solny_prog_gospoda", label="Solny Próg: Gospoda dla Obcych",
        subtype="guest-inn", icon="town", safe=1, tier=1, biome="wasteland",
        desc="Jedyny dom w Solnym Progu, który przyjmuje obcego pod dach — niska "
             "izba z bielonych solą cegieł, gdzie karawaniarze, poszukiwacze i "
             "pielgrzymi śpią obok siebie i nikt nie pyta o nazwisko. Woda jest tu "
             "droga i pilnowana: na pustkowiach studnia znaczy więcej niż złoto.",
        atmo="Zapach solanki i baraniego łoju, cichy pomruk trzech mów naraz i "
             "kropla wody odmierzana z glinianego dzbana jak lekarstwo.",
    ),
    dict(
        key="solny_prog_dom_starszych", label="Solny Próg: Dom Starszych",
        subtype="council-hall", icon="town", safe=1, tier=2, biome="wasteland",
        desc="Najstarszy budynek enklawy — kamienna sala rady, gdzie Starsi "
             "Piętnowanych ważą, komu otworzyć bramę, a przed kim ją zatrzasnąć. "
             "Tu zapada decyzja: ukryć się przed okiem Światła i kultów, czy sprzedać "
             "obcym przewodnictwo po ruinach. Obcego wpuszcza się rzadko i nie za darmo.",
        atmo="Chłód grubych murów, blade oczy Starszych lśniące w półmroku i "
             "cisza, w której każde słowo waży jak sól na wagę.",
    ),
    dict(
        key="solny_prog_cicha_sala", label="Solny Próg: Cicha Sala",
        subtype="memory-hall", icon="town", safe=1, tier=1, biome="wasteland",
        desc="Sala pamięci Wycofania — ściany pokryte imionami tych, których Korona "
             "porzuciła, gdy zwinęła kolonię w jedno pokolenie. Piętnowani przychodzą "
             "tu milczeć, nie modlić się. Sami nie są pewni własnej historii, więc "
             "strzegą jedynego, co im zostało: pamięci, że zostali sami.",
        atmo="Zupełna cisza wchłaniana przez sól na ścianach; setki wyrytych imion, "
             "starte świecowym dymem, i chłód, od którego cichnie nawet oddech.",
    ),
    dict(
        key="solny_prog_targ_przewodnikow", label="Solny Próg: Targ Przewodników",
        subtype="guides-market", icon="town", safe=1, tier=1, biome="wasteland",
        desc="Serce otwarcia enklawy — kramy, przy których najmuje się przewodników "
             "na wyprawy w ruiny, kupuje mapy nakreślone kością i relikty wyniesione "
             "spod piasku. Piętnowani to jedyni, którzy umieją żyć na pustkowiach: "
             "przewodnictwo po martwych miastach jest tu warte więcej niż broń.",
        atmo="Gwar targowania, szelest zwijanych map z wyprawionej skóry i brzęk "
             "kościanych igieł kompasów, drgających, gdy ktoś przejdzie zbyt blisko.",
    ),
    dict(
        key="solny_prog_solne_magazyny", label="Solny Próg: Solne Magazyny",
        subtype="salt-warehouse", icon="town", safe=1, tier=1, biome="wasteland",
        desc="Chłodne składy, gdzie leżakuje najczystsza sól świata — ta, którą "
             "równina wyrzuciła najbliżej pęknięć i która najmocniej tłumi Rdzeń. "
             "Stąd rusza szlak handlowy do Siwych Grań: sól premium, czystsza niż "
             "wszystko, co przywiozą z gór. Paradoks krainy — najcenniejszy towar "
             "rośnie na progu piekła.",
        atmo="Oślepiająca biel usypanych hałd, chrzęst kryształów pod butem i "
             "suche, gryzące powietrze, od którego pierzchną wargi.",
    ),
]

START_DEFAULT = "solny_prog_gospoda"  # lore §8 — domyślne wejście obcego/Piętnowanego

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

    # ── 1. hub musi już istnieć (MP-4) i wisieć na swoim hexie ────────────────
    hub = conn.execute("SELECT id FROM game_locations WHERE key=?", (HUB_KEY,)).fetchone()
    if hub is None:
        print(f"  ✗ brak huba {HUB_KEY} — najpierw seed_martwe_pustkowia_locations.py (MP-4)")
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
        print(f"  sub {s['label']:42s} safe={s['safe']} {'NEW' if created else 'refresh'}")
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
