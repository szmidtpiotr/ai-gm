#!/usr/bin/env python3
"""Przeróbka pliku seedu MARTWYCH PUSTKOWI wg lore §5 (MP-2, #1483 / martwe_pustkowia.md).

KONTEKST
  Surowy generator (FAZA RM) wypluł `data/regions/region_martwe_pustkowia.json`:
  2500 hexów, 79% `heath`, 226 `tundra` (ARTEFAKT generatora), 299 `ruins`
  rozrzuconych, ZERO dróg. Ten skrypt nakłada budżet terenu i układ z rozdziału
  krainy (`docs/world/regions/martwe_pustkowia.md` §5): martwa_ziemia w środku,
  sól wokół Pustkowia Solnego, ruiny zagęszczone w „miasta umarłych", heath na
  obrzeżach — oraz buduje OD ZERA imperialny trakt (granica Czarnoboru → Koniec
  Traktu → Aschfeld, odnoga do Solnego Progu). Reszta krainy CELOWO bez dróg.

  DB NIE JEST RUSZANA (bramka #1483: kanon = plik krainy w git). Seed do
  `world_hexes` to osobny krok (`scripts/seed_world_map.py`) PO akceptacji PNG
  przez Piotra.

CO ROBI
  1. Pustkowie Solne (POI) → hex_type `sol` = CENTRUM strefy soli (label +
     location_key ZOSTAJĄ). Pozostałe 4 POI zostają `ruins`.
  2. przemapowuje CAŁY teren dzikich hexów (heath/tundra/rozrzucone ruins) wg
     budżetu §5 i geografii: sól (blob od Pustkowia Solnego) · ruiny (4 skupiska
     „miasta umarłych" przy POI) · martwa_ziemia (rdzeń krainy) · heath (obrzeża).
     tundra 226 = artefakt — znika w całości.
  3. buduje imperialny trakt OD ZERA: dijkstra granica Czarnoboru → Koniec Traktu
     → Aschfeld + odnoga do Solnego Progu; spójny graf (BFS). Reszta bez dróg.
  4. renderuje podgląd PNG PRZED / PO + tabelkę rozkładu hex_type,
  5. zapisuje przerobiony JSON (chyba że `--dry-run`).

CO ZOSTAJE NIETKNIĘTE (hexy „zamrożone")
  * każdy hex z `label` (33 teasery „ku Czarnoborowi" / „ku Kresom") lub
    `location_key` (5 POI) — zmieniamy WYŁĄCZNIE hex_type Pustkowia Solnego
    (ruins→sol), etykiet i kluczy nie dotykamy.

DETERMINIZM
  Wszystko z jednego ziarna (`--seed`, domyślnie SEED) — dwa uruchomienia dają
  bit w bit ten sam wynik. Żadnych wywołań zegara.

UŻYCIE
  python3 scripts/rework_region_martwe_pustkowia.py --dry-run   # podgląd, plik NIE zapisany
  python3 scripts/rework_region_martwe_pustkowia.py             # zapis + oba PNG
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# reużycie narzędzi z fal Grań/Czarnobór — ten sam styl PNG i kontrola grafu
from reseed_region_terrain import (  # noqa: E402
    COLORS, PL_NAMES, ax_dist, ax_neighbors, check_road_graph,
    distribution_table, noise_field, save_png,
)
import stitch_region_roads as roads  # noqa: E402

REGION = "martwe_pustkowia"
SEED = 2026

# ── nowe typy terenu Martwych Pustkowi (kolory 1:1 z hex_type_config, MP-1) ──
COLORS.update({
    "sol":           (234, 227, 207),   # #eae3cf — biała solna równina
    "martwa_ziemia": (111, 106, 99),    # #6f6a63 — szary popiół, serce krainy
})
PL_NAMES.update({
    "sol":           "sól",
    "martwa_ziemia": "martwa ziemia",
    "heath":         "wrzosowiska",
    "ruins":         "ruiny",
    "tundra":        "tundra",
})
# koszt podróży dla dijkstry traktu (ruins = None w stitchu → trakt je omija)
roads.TERRAIN_COST.update({
    "martwa_ziemia": 3,   # popiół — przejezdny, ale jałowy
    "sol":           5,   # solna równina — trakt jej unika, dochodzi tylko do skraju
    "heath":         2,   # wrzos — łatwo
})

# ── POI: jedyna korekta hex_type (lore §4/§5: Pustkowie Solne = strefa `sol`) ──
# Pozostałe 4 POI zostają `ruins`. Label + location_key NIETKNIĘTE.
POI_FIX = {
    "pustkowie_solne": ("sol", "Pustkowie Solne = CENTRUM strefy soli (lore §4/§5)"),
}

# ── kotwice geograficzne (q, r) — wprost z pliku seedu ────────────────────────
SOL_ANCHOR = (72, 89)                       # Pustkowie Solne — centrum soli
CENTER = (78, 91)                           # centroid 5 POI — rdzeń krainy
RUINS_POI = [(84, 76), (90, 88), (67, 101), (79, 102)]  # 4 ruiny (miasta umarłych)

# ── trakt imperialny — kotwice ideowe (snapowane do najbliższego przejezdnego) ─
CROSSING_TEASER = (76, 65)   # „ku Czarnoborowi" — przejście z Czarnoboru
KONIEC_TRAKTU = (75, 72)     # brama-ruina, gdzie urywa się trakt (§4)
ASCHFELD = (80, 84)          # porzucona kolonia imperialna (§4, farmowalny dungeon)
SOLNY_PROG = (69, 86)        # enklawa Piętnowanych „na skraju solnej równiny" (§4)

# ── BUDŻET TERENU (lore §5) — WARTOŚCI STARTOWE (Numbers Policy) ──────────────
# Liczby = ile DZIKICH hexów przydzielić. Frozen dokłada: +1 sol (Pustkowie Solne),
# +4 ruins (POI). Reszta dzikich → heath (obrzeża). road budowany osobno (~55).
BUDGET = {
    "sol":           349,   # §5 ~350 (z frozen POI = 350)
    "ruins":         295,   # §5 ~300 (z 4 frozen POI ≈ 299) — skupiska przy POI
    "martwa_ziemia": 700,   # §5 ~700 — rdzeń krainy
    # reszta dzikich → heath (§5 ~800 obrzeża + slack)
}

FROZEN_TYPES = {"road", "bridge", "przelecz", "river", "lake", "water"}


def load():
    path = ROOT / "data" / "regions" / f"region_{REGION}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    hexes = {(h["q"], h["r"]): dict(h) for h in data["hexes"]}
    return data, hexes, path


def is_frozen(h: dict) -> bool:
    return bool(h.get("label") or h.get("location_key")) or h["hex_type"] in FROZEN_TYPES


def fix_pois(hexes: dict) -> list[str]:
    """Korekta hex_type Pustkowia Solnego (ruins→sol). Label/location_key ZOSTAJĄ."""
    by_key = {h["location_key"]: k for k, h in hexes.items() if h.get("location_key")}
    log = []
    for key, (new_type, why) in POI_FIX.items():
        k = by_key.get(key)
        if k is None:
            log.append(f"  ! POI '{key}' nie znaleziony — pominięto")
            continue
        old = hexes[k]["hex_type"]
        hexes[k]["hex_type"] = new_type
        log.append(f"  {hexes[k].get('label', key)} {k}: {old} → {new_type}  ({why})")
    return log


def anchor_dist(keys, anchors):
    """Minimalna odległość heksowa do najbliższej kotwicy."""
    return {k: min(ax_dist(k, a) for a in anchors) for k in keys}


def replan_terrain(hexes: dict, seed: int):
    import random
    rng = random.Random(seed)
    keys = sorted(hexes.keys())

    n1 = noise_field(keys, rng, passes=5)   # duże pasy
    n2 = noise_field(keys, rng, passes=3)   # drobne plamy

    frozen = {k for k in keys if is_frozen(hexes[k])}
    wild = [k for k in keys if k not in frozen]   # WSZYSTKO poza etykietami/POI

    d_sol = anchor_dist(keys, [SOL_ANCHOR])
    d_poi = anchor_dist(keys, RUINS_POI)
    d_ctr = anchor_dist(keys, [CENTER])

    assigned: dict[tuple, str] = {}

    def take(score, n, hex_type):
        cand = [k for k in wild if k not in assigned]
        cand.sort(key=lambda k: (-score(k), k))
        for k in cand[:n]:
            assigned[k] = hex_type
        return cand[:n]

    # 1. SÓL — blob od Pustkowia Solnego (najbliższe hexy), organiczny brzeg
    take(lambda k: (1.0 - d_sol[k] / 25.0) + n2[k] * 0.18,
         BUDGET["sol"], "sol")

    # 2. RUINY — 4 skupiska „miasta umarłych" przy POI (najbliższe do POI)
    take(lambda k: (1.0 - d_poi[k] / 22.0) + n2[k] * 0.16,
         BUDGET["ruins"], "ruins")

    # 3. MARTWA ZIEMIA — rdzeń krainy (najbliższe do centroidu POI)
    take(lambda k: (1.0 - d_ctr[k] / 30.0) + n1[k] * 0.25,
         BUDGET["martwa_ziemia"], "martwa_ziemia")

    # 4. HEATH — obrzeża: cała reszta dzikich hexów
    for k in wild:
        if k not in assigned:
            assigned[k] = "heath"

    for k, t in assigned.items():
        hexes[k]["hex_type"] = t

    return {"frozen": len(frozen), "wild": len(wild),
            "assigned": Counter(assigned.values())}


def snap_paveable(hexes: dict, ideal: tuple) -> tuple:
    """Najbliższy hex do `ideal`, na który da się wejść traktem (cost_of != None)."""
    cand = [k for k in hexes if roads.cost_of(hexes, k) is not None]
    return min(cand, key=lambda k: (ax_dist(k, ideal), k))


def build_trakt(hexes: dict) -> list[tuple]:
    """Buduje imperialny trakt OD ZERA (plik nie ma dróg):
       granica Czarnoboru → Koniec Traktu → Aschfeld + odnoga do Solnego Progu."""
    def to_road(path):
        out = []
        for k in path:
            if hexes[k]["hex_type"] in roads.NETWORK:
                continue
            hexes[k]["hex_type"] = "bridge" if hexes[k]["hex_type"] == "river" else "road"
            out.append(k)
        return out

    # źródło wjazdu = przejezdni sąsiedzi teasera „ku Czarnoborowi"
    src = {nb for nb in ax_neighbors(*CROSSING_TEASER)
           if nb in hexes and roads.cost_of(hexes, nb) is not None}
    if not src:
        raise SystemExit(f"BŁĄD: teaser {CROSSING_TEASER} nie ma przejezdnego sąsiada")

    koniec = snap_paveable(hexes, KONIEC_TRAKTU)
    asch = snap_paveable(hexes, ASCHFELD)
    prog = snap_paveable(hexes, SOLNY_PROG)

    added = []
    log = []
    for label, sources, target in [
        ("granica Czarnoboru → Koniec Traktu", src, {koniec}),
        ("Koniec Traktu → Aschfeld", {koniec}, {asch}),
    ]:
        path, cost = roads.dijkstra_to_targets(hexes, set(sources), set(target))
        if path is None:
            raise SystemExit(f"BŁĄD: brak trasy ({label})")
        new = to_road(path)
        added += new
        log.append(f"  {label}: {path[0]} → {path[-1]} — {len(new)} hexów (koszt {cost})")

    # odnoga do Solnego Progu — od dowolnego hexa istniejącego już traktu
    net = {k for k, h in hexes.items() if h["hex_type"] in roads.NETWORK}
    path, cost = roads.dijkstra_to_targets(hexes, net, {prog})
    if path is None:
        raise SystemExit("BŁĄD: brak trasy odnogi do Solnego Progu")
    new = to_road(path)
    added += new
    log.append(f"  odnoga → Solny Próg: {path[0]} → {path[-1]} — {len(new)} hexów (koszt {cost})")

    for line in log:
        print(line)
    print(f"  kotwice: Koniec Traktu={koniec}  Aschfeld={asch}  Solny Próg={prog}")
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--dry-run", action="store_true", help="nie zapisuj JSON-a")
    ap.add_argument("--png-before", default="docs/world/previews/martwe_pustkowia_terrain_before.png")
    ap.add_argument("--png-after", default="docs/world/previews/martwe_pustkowia_terrain_after.png")
    ap.add_argument("--md-table", default=None)
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()

    data, hexes, path = load()
    before = {k: dict(h) for k, h in hexes.items()}
    print(f"źródło: {path.relative_to(ROOT)} ({len(hexes)} hexów), ziarno={args.seed}")

    print("\n[1] korekta hex_type POI (Pustkowie Solne → sól):")
    for line in fix_pois(hexes):
        print(line)

    print("\n[2] redystrybucja terenu (budżet §5):")
    stats = replan_terrain(hexes, args.seed)
    print(f"  zamrożone: {stats['frozen']}  dzikie: {stats['wild']}")
    print(f"  przydział: {dict(stats['assigned'])}")

    print("\n[3] budowa imperialnego traktu (od zera):")
    added = build_trakt(hexes)
    roads.stitch(hexes)   # gwarancja jednej składowej
    ok_a, msg_a = check_road_graph(hexes)
    print(f"  trakt: {len(added)} hexów — {msg_a} (spójna: {ok_a})")

    # kontrola: żadna etykieta/location_key nie ruszona (hex_type Pustkowia Solnego OK)
    for k, h in before.items():
        assert (hexes[k].get("label"), hexes[k].get("location_key")) == \
               (h.get("label"), h.get("location_key")), f"ruszona etykieta/POI {k}"
    assert ok_a, "graf dróg NIE spójny — przerwane"

    table = distribution_table(before, hexes)
    print("\n[4] rozkład hex_type PRZED/PO:\n")
    print(table)
    if args.md_table:
        Path(args.md_table).write_text(table + "\n", encoding="utf-8")
        print(f"\ntabelka: {args.md_table}")

    if not args.no_png:
        p1 = save_png(before, "MARTWE PUSTKOWIA — PRZED",
                      "surowy generator RM (git: data/regions/region_martwe_pustkowia.json)",
                      ROOT / args.png_before)
        p2 = save_png(hexes, "MARTWE PUSTKOWIA — PO (plan martwe_pustkowia.md §5)",
                      f"redystrybucja terenu + trakt, seed={args.seed} — DB NIE RUSZANA",
                      ROOT / args.png_after)
        print(f"\nPNG przed: {p1.relative_to(ROOT)}")
        print(f"PNG po:    {p2.relative_to(ROOT)}")

    if args.dry_run:
        print("\n--dry-run: JSON NIE zapisany")
    else:
        data["hexes"] = [hexes[k] for k in sorted(hexes)]
        data["status"] = data.get("status", "coming")
        data["terrain_plan_seed"] = args.seed
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nZapisano {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
