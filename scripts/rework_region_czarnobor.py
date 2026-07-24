#!/usr/bin/env python3
"""Przeróbka pliku seedu CZARNOBORU wg lore §5 (CB-2, #1483 / rozdział czarnobor.md).

KONTEKST
  Surowy generator (FAZA RM) wypluł `data/regions/region_czarnobor.json`:
  2500 hexów, 94% `forest`, 6 lokacji z PRZYPADKOWYMI typami (Step Wilków jako
  `ruins` itd.). Ten skrypt nakłada budżet terenu i układ pasów z rozdziału krainy
  (`docs/world/regions/czarnobor.md` §5), naprawia typy 6 POI i zszywa trakt
  z Kresów → Ostęp Graniczny → w głąb w JEDEN spójny graf dróg.

  DB NIE JEST RUSZANA (bramka #1483: kanon = plik krainy w git). Seed do
  `world_hexes` to osobny krok (`scripts/seed_world_map.py`) PO akceptacji PNG
  przez Piotra.

CO ROBI
  1. naprawia hex_type 6 POI (patrz POI_FIX),
  2. redystrybuuje teren „dzikich" hexów (forest/swamp) wg budżetu §5 i pasów
     kierunkowych (zachód/płd-zachód/centrum/południe/wschód-płn-wschód),
  3. dokłada zachodni trakt z Kresów i zszywa sieć dróg w jedną składową
     (Zarośnięty Trakt na południe CELOWO zostaje nieprzejezdny — to przyszła
      lokacja-ruina, nie droga),
  4. renderuje podgląd PNG PRZED / PO + tabelkę rozkładu hex_type,
  5. zapisuje przerobiony JSON (chyba że `--dry-run`).

CO ZOSTAJE NIETKNIĘTE (hexy „zamrożone")
  * każdy hex z `label` (teasery „ku Kresom" / „ku Martwym Pustkowiu") lub
    `location_key` (6 POI),
  * istniejąca sieć: `road`/`bridge`/`przelecz`, woda `river`/`lake`.
  Zmieniane są WYŁĄCZNIE dzikie hexy typu `forest`/`swamp`.

DETERMINIZM
  Wszystko z jednego ziarna (`--seed`, domyślnie SEED) — dwa uruchomienia dają
  bit w bit ten sam wynik. Żadnych wywołań zegara.

UŻYCIE
  python3 scripts/rework_region_czarnobor.py --dry-run          # podgląd, plik NIE zapisany
  python3 scripts/rework_region_czarnobor.py                    # zapis + oba PNG
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# reużycie narzędzi z fali Grań (SG-2/SG-3) — ten sam styl PNG i ta sama kontrola grafu
from reseed_region_terrain import (  # noqa: E402
    COLORS, PL_NAMES, ax_dist, ax_neighbors, check_road_graph,
    distribution_table, noise_field, save_png,
)
import stitch_region_roads as roads  # noqa: E402

REGION = "czarnobor"
SEED = 2020

# ── nowe typy terenu Czarnoboru (kolory 1:1 z hex_type_config, migrations_admin.py) ──
COLORS.update({
    "czarny_las":  (16, 29, 21),    # #101d15 — smoliste pnie
    "trzesawisko": (44, 59, 59),    # #2c3b3b — mgła nad wodą
    "step":        (156, 175, 62),  # #9caf3e — trawy po horyzont
})
PL_NAMES.update({
    "czarny_las":  "czarny las",
    "trzesawisko": "trzęsawisko",
    "step":        "step",
    "swamp":       "bagno",
})
# koszt podróży dla stitcha (czarny_las/trzesawisko przejezdne, ale drogie; step łatwy)
roads.TERRAIN_COST.update({
    "czarny_las": 4,     # nawiedzony, plączący bór (jak mountain)
    "trzesawisko": 7,    # grzęźnie się (gorzej niż swamp=6)
    "step": 1,           # trawy — łatwo
})

# ── POI: naprawa typów (lore §4 „Istniejące POI — typy do naprawy") ──────────
# klucz lokacji → (nowy hex_type, uzasadnienie)
POI_FIX = {
    "step_wilkow":      ("step",        "Step Wilków leży na stepie, nie w ruinach"),
    "bor_zmarlych":     ("czarny_las",  "Bór Zmarłych = wygasłe stróżowe drzewa (§2)"),
    "knieja_czarnych":  ("czarny_las",  "Knieja Czarnych Drzew = las czarnych drzew (§2)"),
    "trzesawiska_mgl":  ("trzesawisko", "Trzęsawiska Mgieł = mgła nad wodą"),
    "bagienna_knieja":  ("trzesawisko", "Bagienna Knieja = mokra knieja (POI, nie osada)"),
    "ostep_graniczny":  ("village",     "Ostęp Graniczny = osada wymiany (§4) — zostaje osadą"),
}

# ── BUDŻET TERENU (lore §5) — WARTOŚCI STARTOWE (Numbers Policy) ──────────────
BUDGET = {
    "step":        350,   # §5: ~350 — wschód/płn-wschód, kraniec kontynentu
    "czarny_las":  250,   # §5: ~250 — płd-zachód (Bór Zmarłych rozrasta się ku Kresom)
    "trzesawisko": 200,   # §5: ~200 — południe, przejście ku Pustkowiom
    "swamp":       200,   # §5: ~200 — bagna na południu
    "heath":       150,   # §5: ~150 — polany/wrzosowiska rozsiane
    "water":        15,   # §5: oczka wodne i strumienie
    # reszta dzikich → forest (§5: ~1300)
}

# kotwice (q, r) — wprost z pliku seedu; teren rośnie od tych POI
ANCHORS = {
    "step":        [(92, -7)],            # Step Wilków
    "czarny_las":  [(74, 8), (66, 20)],   # Bór Zmarłych, Knieja Czarnych Drzew
    "trzesawisko": [(75, 29), (85, 17)],  # Trzęsawiska Mgieł, Bagienna Knieja
}

FROZEN_TYPES = {"road", "bridge", "przelecz", "river", "lake", "water"}
WILD_TYPES = {"forest", "swamp"}


def load():
    path = ROOT / "data" / "regions" / f"region_{REGION}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    hexes = {(h["q"], h["r"]): dict(h) for h in data["hexes"]}
    return data, hexes, path


def is_frozen(h: dict) -> bool:
    return bool(h.get("label") or h.get("location_key")) or h["hex_type"] in FROZEN_TYPES


def fix_pois(hexes: dict) -> list[str]:
    """Naprawia typy 6 POI wg POI_FIX. Zwraca log zmian."""
    by_key = {h["location_key"]: k for k, h in hexes.items() if h.get("location_key")}
    log = []
    for key, (new_type, why) in POI_FIX.items():
        k = by_key.get(key)
        if k is None:
            log.append(f"  ! POI '{key}' nie znaleziony w pliku — pominięto")
            continue
        old = hexes[k]["hex_type"]
        hexes[k]["hex_type"] = new_type
        log.append(f"  {hexes[k].get('label', key)} {k}: {old} → {new_type}  ({why})")
    return log


def norm_coords(keys):
    """Znormalizowane osie: nx 0=zachód→1=wschód, ny 0=północ→1=południe.
    x ∝ q, y ∝ q/2+r — dokładnie jak renderuje gra (flat-top axial)."""
    xs = {k: float(k[0]) for k in keys}
    ys = {k: k[0] / 2.0 + k[1] for k in keys}
    xlo, xhi = min(xs.values()), max(xs.values())
    ylo, yhi = min(ys.values()), max(ys.values())
    xspan = (xhi - xlo) or 1.0
    yspan = (yhi - ylo) or 1.0
    nx = {k: (xs[k] - xlo) / xspan for k in keys}
    ny = {k: (ys[k] - ylo) / yspan for k in keys}
    return nx, ny


def anchor_dist(keys, anchors):
    """Minimalna odległość heksowa do najbliższej kotwicy (0..∞)."""
    return {k: min(ax_dist(k, a) for a in anchors) for k in keys}


def replan_terrain(hexes: dict, seed: int):
    import random
    rng = random.Random(seed)
    keys = sorted(hexes.keys())

    nx, ny = norm_coords(keys)
    n1 = noise_field(keys, rng, passes=5)   # duże pasy klimatyczne
    n2 = noise_field(keys, rng, passes=3)   # drobne plamy (polany, oczka)

    frozen = {k for k in keys if is_frozen(hexes[k])}
    wild = [k for k in keys if k not in frozen and hexes[k]["hex_type"] in WILD_TYPES]

    d_step = anchor_dist(keys, ANCHORS["step"])
    d_czar = anchor_dist(keys, ANCHORS["czarny_las"])
    d_trze = anchor_dist(keys, ANCHORS["trzesawisko"])
    dmax = max(len(keys) ** 0.5, 1.0)

    assigned: dict[tuple, str] = {}

    def take(score, n, hex_type, pool=None):
        cand = [k for k in (pool or wild) if k not in assigned]
        cand.sort(key=lambda k: (-score(k), k))
        for k in cand[:n]:
            assigned[k] = hex_type
        return cand[:n]

    # 1. STEP — wschód + północ (kraniec kontynentu), blob od Stepu Wilków
    take(lambda k: nx[k] * 1.1 + (1 - ny[k]) * 0.7
                   + max(0.0, (18 - d_step[k]) / 18) * 0.8 + n1[k] * 0.5,
         BUDGET["step"], "step")

    # 2. CZARNY_LAS — płd-zachód, rośnie od kotwic ku Kresom (zachód = niski nx)
    take(lambda k: max(0.0, (30 - d_czar[k]) / 30) * 1.4
                   + (1 - nx[k]) * 0.45 + n2[k] * 0.5,
         BUDGET["czarny_las"], "czarny_las")

    # 3. TRZESAWISKO — południe, blob od Trzęsawisk Mgieł / Bagiennej Kniei
    take(lambda k: max(0.0, (16 - d_trze[k]) / 16) * 1.3
                   + ny[k] * 0.7 + n2[k] * 0.4,
         BUDGET["trzesawisko"], "trzesawisko")

    # 4. SWAMP — bagna na dalekim południu (ku Martwym Pustkowiom)
    take(lambda k: ny[k] * 1.2 + n2[k] * 0.5,
         BUDGET["swamp"], "swamp")

    # 5. HEATH — polany rozsiane po środku boru (plamy szumu, unikamy skrajów)
    take(lambda k: n2[k] * 1.0 - abs(ny[k] - 0.5) * 0.6 - abs(nx[k] - 0.4) * 0.3,
         BUDGET["heath"], "heath")

    # 6. WODA — kilka oczek w wilgotnych zagłębieniach południa (małe bloby)
    lake_pool = sorted((k for k in wild if k not in assigned and ny[k] > 0.45),
                       key=lambda k: (n2[k], k))
    seeds = []
    for k in lake_pool:
        if all(ax_dist(k, s) > 7 for s in seeds):
            seeds.append(k)
        if len(seeds) >= 5:
            break
    placed = 0
    for s in seeds:
        if placed >= BUDGET["water"]:
            break
        blob = [s] + [nb for nb in sorted(ax_neighbors(*s))
                      if nb in hexes and nb not in assigned and nb not in frozen
                      and hexes[nb]["hex_type"] in WILD_TYPES]
        for k in blob[:3]:
            if placed >= BUDGET["water"]:
                break
            assigned[k] = "water"
            placed += 1

    # ── zastosuj plan; reszta dzikich zostaje forest ─────────────────────────
    for k, t in assigned.items():
        hexes[k]["hex_type"] = t

    stats = {
        "frozen": len(frozen),
        "wild": len(wild),
        "assigned": Counter(assigned.values()),
    }
    return stats


def add_west_trakt(hexes: dict) -> list[tuple]:
    """Dokłada zachodni trakt: od najbliższego dzikiego sąsiada teasera „ku Kresom"
    do istniejącej sieci dróg (trakt z Kresów wchodzi w głąb boru)."""
    net = {k for k, h in hexes.items() if h["hex_type"] in roads.NETWORK}
    kresom = [k for k, h in hexes.items() if h.get("label") == "ku Kresom"]
    # dzicy (paveable) sąsiedzi teaserów = źródła zachodniego wjazdu
    sources = {nb for k in kresom for nb in ax_neighbors(*k)
               if nb in hexes and roads.cost_of(hexes, nb) is not None}
    path, cost = roads.dijkstra_to_targets(hexes, sources, net)
    if path is None:
        raise SystemExit("BŁĄD: nie da się doprowadzić traktu z Kresów do sieci")
    added = []
    for k in path:
        if hexes[k]["hex_type"] in roads.NETWORK:
            continue
        hexes[k]["hex_type"] = "bridge" if hexes[k]["hex_type"] == "river" else "road"
        added.append(k)
    print(f"  zachodni trakt: {path[0]} → {path[-1]} — {len(added)} nowych hexów (koszt {cost})")
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--dry-run", action="store_true", help="nie zapisuj JSON-a")
    ap.add_argument("--png-before", default="docs/world/previews/czarnobor_terrain_before.png")
    ap.add_argument("--png-after", default="docs/world/previews/czarnobor_terrain_after.png")
    ap.add_argument("--md-table", default=None)
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()

    data, hexes, path = load()
    before = {k: dict(h) for k, h in hexes.items()}
    print(f"źródło: {path.relative_to(ROOT)} ({len(hexes)} hexów), ziarno={args.seed}")

    print("\n[1] naprawa typów POI:")
    for line in fix_pois(hexes):
        print(line)

    print("\n[2] redystrybucja terenu (budżet §5):")
    stats = replan_terrain(hexes, args.seed)
    print(f"  zamrożone: {stats['frozen']}  dzikie: {stats['wild']}")
    print(f"  przydział: {dict(stats['assigned'])}")

    print("\n[3] trakt z Kresów + zszycie grafu dróg:")
    ok_b, msg_b = check_road_graph(hexes)
    print(f"  PRZED  {msg_b}")
    add_west_trakt(hexes)
    roads.stitch(hexes)
    ok_a, msg_a = check_road_graph(hexes)
    print(f"  PO     {msg_a} (spójna: {ok_a})")

    # kontrola: żaden zamrożony teaser/POI nie zmienił label/location_key
    for k, h in before.items():
        assert (hexes[k].get("label"), hexes[k].get("location_key")) == \
               (h.get("label"), h.get("location_key")), f"ruszony hex {k}"
    assert ok_a, "graf dróg NIE spójny — przerwane"

    table = distribution_table(before, hexes)
    print("\n[4] rozkład hex_type PRZED/PO:\n")
    print(table)
    if args.md_table:
        Path(args.md_table).write_text(table + "\n", encoding="utf-8")
        print(f"\ntabelka: {args.md_table}")

    if not args.no_png:
        p1 = save_png(before, "CZARNOBÓR — PRZED",
                      "surowy generator RM5 (git: data/regions/region_czarnobor.json)",
                      ROOT / args.png_before)
        p2 = save_png(hexes, "CZARNOBÓR — PO (plan czarnobor.md §5)",
                      f"redystrybucja terenu, seed={args.seed} — DB NIE RUSZANA",
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
