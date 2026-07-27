#!/usr/bin/env python3
"""Budowa mapy KORONNYCH NIZIN OD ZERA wg lore §5 (KN-2, #1483 / koronne_niziny.md).

KONTEKST — KRAINA UNIKALNA
  `data/regions/region_koronne_niziny.json` to PLACEHOLDER z 2 hexami (nie ma
  siatki 2500 hexów — jedyna taka kraina). Wszystkie inne krainy dostały surówkę
  z generatora FAZY RM; Niziny NIE. Ten skrypt GENERUJE pełną siatkę 50×50 od zera
  w bounding-boxie krainy (offset kontynentalny z region_blocks: q_off=-50, r_off=25,
  q -50..-1, r 1..74), po czym maluje teren wg rozdziału krainy (§5):

    RÓWNINY CYWILIZOWANE (odwrotność Martwych Pustkowi — drogi są WSZĘDZIE):
    (a) plains/heath dominują (serce spichlerza),
    (b) `pola_uprawne` (złote łany, typ z KN-1 #1501) wokół osad i wzdłuż rzeki (~400),
    (c) lasy kępami w głębi (~250),
    (d) DUŻA RZEKA z północnego-wschodu przez VILNOGRAD (Port Rzeczny) do południowej
        krawędzi — nić fabularna do Wybrzeża Łez (WL river-source ~q-35),
    (e) jeziora / stawy młyńskie,
    (f) GĘSTA SIEĆ TRAKTÓW: 4 trakty krzyżują się w VOLHYNII (wschodni→granica Kresów,
        zachodni, północny→Vilnograd, południowy→Wybrzeże), mosty na rzece, rogatki
        na wjazdach; graf spójny (BFS).

  Trakt WSCHODNI spina się z istniejącym przejściem po stronie Kresów: Kresy mają
  most na (0,13) + trakt r=13 ku zachodniej krawędzi. KN kończy trakt wschodni
  road-hexem na (-1,13) = axial-sąsiad mostu Kresów → graf ciągły po zaseedowaniu.

  DB NIE JEST RUSZANA (bramka #1483/#1482: kanon = plik krainy w git). Seed do
  `world_hexes` to osobny krok (`scripts/seed_world_map.py`) PO akceptacji PNG.

DETERMINIZM
  Wszystko z jednego ziarna (`--seed`, domyślnie SEED). Bez zegara.

UŻYCIE (na .61)
  python3 scripts/build_region_koronne_niziny.py --dry-run   # podgląd, plik NIE zapisany
  python3 scripts/build_region_koronne_niziny.py             # zapis JSON + PNG
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from region_blocks import W, H, region_offsets  # noqa: E402  wzór bloków (JEDNO źródło)
from reseed_region_terrain import (  # noqa: E402
    COLORS, PL_NAMES, ax_dist, ax_neighbors, check_road_graph, noise_field, save_png,
)
import stitch_region_roads as roads  # noqa: E402

REGION = "koronne_niziny"
SEED = 1612

# ── typ terenu pola_uprawne (KN-1 #1501; kolor 1:1 z hex_type_config map_color) ──
COLORS.update({"pola_uprawne": (216, 177, 74)})   # #d8b14a — złote łany
PL_NAMES.update({"pola_uprawne": "pola uprawne", "heath": "wrzosowiska",
                 "plains": "równiny", "road": "trakt", "bridge": "most"})

# trakt utwardza także łany (cywilizacja) — koszt niski jak plains/heath
roads.TERRAIN_COST.update({"pola_uprawne": 1})

# encounter_chance per typ — kraina najbezpieczniejsza w świecie (§1)
ENCOUNTER = {
    "pola_uprawne": 0.10, "plains": 0.10, "heath": 0.15, "hills": 0.15,
    "forest": 0.25, "river": 0.12, "lake": 0.08, "swamp": 0.30, "ruins": 0.35,
    "road": 0.05, "bridge": 0.40, "city": 0.0, "town": 0.0, "village": 0.0,
}

# ── BUDŻET TERENU (§5) — WARTOŚCI STARTOWE (Numbers Policy) ──────────────────
BUDGET = {
    "forest": 250,        # §5 ~250 — lasy kępami
    "heath": 200,         # suchy skraj równin (urozmaicenie)
    "hills": 80,          # łagodne wzniesienia
    "pola_uprawne": 400,  # §5 ~400 — łany wokół osad + wzdłuż rzeki
    # reszta = plains (dominują — serce spichlerza)
}

# ── OSADY (§4 + generate_region_map RM5): (key, label, hex_type, col, row) ─────
#   col: 0=W → 49=E(Kresy)   row: 0=N → 49=S(Wybrzeże)
VILNOGRAD = (27, 10)   # stolica, na rzece (Port Rzeczny) — hub-gigant
VOLHYNIA  = (30, 22)   # miasto kupieckie, SKRZYŻOWANIE 4 TRAKTÓW (§2)
SETTLEMENTS = [
    ("vilnograd_stolica", "Vilnograd",           "city",    *VILNOGRAD),
    ("volhynia",          "Volhynia",            "town",    *VOLHYNIA),
    ("klasztor_iskry",    "Klasztor Iskry",      "village", 11, 13),   # NW — centrum Światła
    ("osada_kupiecka",    "Osada Kupiecka",      "village", 22,  5),   # N
    ("zachodnia_straz",   "Zachodnia Straż",     "town",     4, 26),   # daleki W — trakt zachodni
    ("wielkie_targi",     "Wielkie Targi",       "town",    34, 33),   # centrum-S
    ("kasztel_rycerski",  "Kasztel Rycerski",    "town",    14, 37),   # SW
    ("nowe_dobra",        "Nowe Dobra",          "village", 42, 33),   # E
    ("przeprawa_krol",    "Przeprawa Królewska", "village", 17, 45),   # S — przeprawa ku Wybrzeżu
]
ATM = {
    "vilnograd_stolica": ("Stolica Korony u Portu Rzecznego. Gildie, katedra Światła, "
                          "dzielnica złodziei — i cień Rady Czterech. Latarnia świeci na kredyt."),
    "volhynia":          ("Skrzyżowanie czterech traktów. Aukcje, karawany, plotki z całego "
                          "świata; sufit ekonomii gry."),
    "klasztor_iskry":    ("Centrum wiary w Światło. Matka Urszula, Brat Kazimierz uzdrawia, "
                          "Brat Tomasz skupuje relikty (łącznik z Pustkowiami)."),
}

# ── KOTWICE RZEKI (col,row) ──────────────────────────────────────────────────
RIVER_SRC   = (44,  4)   # NE — źródło (z pogórza za wschodnią granicą)
RIVER_MOUTH = (16, 49)   # S krawędź — nić do Wybrzeża (WL source ~q-35)

# ── TRAKTY: wyloty graniczne (col,row) — road-hexy przy krawędzi ─────────────
EAST_EXIT  = (49, 12)    # (-1,13) — axial-sąsiad mostu Kresów (0,13)
SOUTH_EXIT = (16, 49)    # przy ujściu rzeki, wylot ku Wybrzeżu

FROZEN_LABEL_PREFIX = "ku "


# ── SIATKA OD ZERA ───────────────────────────────────────────────────────────
def off2ax(col, row):
    """offset-coords (flat-top) → axial lokalny (jak generate_region_map)."""
    return (col, row - (col - (col & 1)) // 2)


def build_grid():
    """Pełna siatka 50×50 w absolutnych axial (offset kontynentalny KN)."""
    q_off, r_off = region_offsets(REGION)   # (-50, 25)
    hexes, local = {}, {}
    for row in range(H):
        for col in range(W):
            aq, ar = off2ax(col, row)
            k = (aq + q_off, ar + r_off)
            hexes[k] = {"q": k[0], "r": k[1], "hex_type": "plains",
                        "label": None, "location_key": None,
                        "atmosphere": None, "encounter_chance": 0.15}
            local[k] = (col, row)
    return hexes, local, (q_off, r_off)


def nearest(hexes, local, col, row, ok):
    """Hex najbliższy docelowym (col,row) spełniający predykat ok(k)."""
    target = min(local, key=lambda k: (abs(local[k][0] - col) + abs(local[k][1] - row)))
    cand = [k for k in hexes if ok(k)]
    return min(cand, key=lambda k: (ax_dist(k, target), k)) if cand else target


# ── TEREN: plains-dominant + forest/heath/hills wg szumu ─────────────────────
def paint_terrain(hexes, rng):
    keys = sorted(hexes.keys())
    moist = noise_field(keys, rng, passes=4)   # wilgoć → kępy lasu
    var = noise_field(keys, rng, passes=2)     # urozmaicenie → wzgórza/wrzosy
    assigned = {}

    def take(pool, score, n, typ):
        pick = sorted([k for k in pool if k not in assigned],
                      key=lambda k: (-score(k), k))[:n]
        for k in pick:
            assigned[k] = typ
        return pick

    # lasy — najwilgotniejsze plamy (szum wygładzony → zwarte kępy)
    take(keys, lambda k: moist[k], BUDGET["forest"], "forest")
    # wrzosowiska — suchy skraj (niska wilgoć)
    take(keys, lambda k: 1.0 - moist[k], BUDGET["heath"], "heath")
    # wzgórza — wysoka zmienność
    take(keys, lambda k: var[k], BUDGET["hills"], "hills")

    for k in keys:
        hexes[k]["hex_type"] = assigned.get(k, "plains")
    return moist


# ── RZEKA: NE → Vilnograd → S; greedy ku celowi + szum ──────────────────────
def _walk(hexes, start, goal, rng, avoid):
    """Ścieżka od start do sąsiedztwa goal, krok = sąsiad minimalizujący dystans."""
    cur, path, visited = start, [], {start}
    for _ in range(400):
        if ax_dist(cur, goal) <= 1:
            return path
        nbrs = [n for n in ax_neighbors(*cur) if n in hexes and n not in visited]
        if not nbrs:
            return path
        nxt = min(nbrs, key=lambda n: (ax_dist(n, goal) + rng.random() * 0.9, n))
        visited.add(nxt)
        if nxt in avoid:
            cur = nxt
            continue
        path.append(nxt)
        cur = nxt
    return path


def carve_river(hexes, local, rng, protect):
    src = nearest(hexes, local, *RIVER_SRC, lambda k: True)
    vil = nearest(hexes, local, *VILNOGRAD, lambda k: True)
    mouth = nearest(hexes, local, *RIVER_MOUTH, lambda k: True)
    river = []
    for a, b in ((src, vil), (vil, mouth)):
        for k in _walk(hexes, a, b, rng, protect):
            if k in protect:
                continue
            hexes[k]["hex_type"] = "river"
            river.append(k)
    return river, mouth


# ── JEZIORA / STAWY MŁYŃSKIE ─────────────────────────────────────────────────
def carve_lakes(hexes, local, rng, n_lakes=3):
    cells = []
    # środkowe równiny z dala od krawędzi — kandydaci na oczka wodne
    seeds_pool = sorted([k for k, (c, r) in local.items()
                         if 6 < c < 44 and 8 < r < 44
                         and hexes[k]["hex_type"] in ("plains", "heath")],
                        key=lambda k: (k[1], k[0]))
    rng.shuffle(seeds_pool)
    seeds = []
    for k in seeds_pool:
        if all(ax_dist(k, s) > 10 for s in seeds):
            seeds.append(k)
        if len(seeds) >= n_lakes:
            break
    for s in seeds:
        blob = [s]
        for nb in sorted(ax_neighbors(*s)):
            if len(blob) >= 4:
                break
            if nb in hexes and hexes[nb]["hex_type"] in ("plains", "heath") and rng.random() < 0.5:
                blob.append(nb)
        for k in blob:
            hexes[k]["hex_type"] = "lake"
            cells.append(k)
    return cells


# ── OSADY ────────────────────────────────────────────────────────────────────
def place_settlements(hexes, local):
    placed = {}
    used = set()
    no_settle = ("river", "lake", "sea", "water")
    for key, label, typ, col, row in SETTLEMENTS:
        pos = nearest(hexes, local, col, row,
                      lambda k: k not in used
                      and hexes[k]["hex_type"] not in no_settle
                      and not hexes[k].get("location_key"))
        hexes[pos]["hex_type"] = typ
        hexes[pos]["label"] = label
        hexes[pos]["location_key"] = key
        hexes[pos]["atmosphere"] = ATM.get(key)
        used.add(pos)
        placed[key] = pos
    return placed


# ── TRAKTY: 4 z Volhynii + reszta osad; graf spójny ─────────────────────────
def paveable_neighbors(hexes, pos):
    return {nb for nb in ax_neighbors(*pos)
            if nb in hexes and roads.cost_of(hexes, nb) is not None}


def build_roads(hexes, placed, east_exit, south_exit):
    net = set()
    root = placed["volhynia"]
    seed_nbrs = paveable_neighbors(hexes, root)
    if not seed_nbrs:
        raise SystemExit("BŁĄD: Volhynia bez przejezdnego sąsiada")
    for k in seed_nbrs:
        hexes[k]["hex_type"] = "road"   # hub dotyka traktu
    net |= seed_nbrs

    # 4 TRAKTY z Volhynii + pozostałe osady (kolejność = 4 kierunki najpierw)
    order = [
        ("trakt wschodni → Kresy", {east_exit}),
        ("trakt zachodni",          paveable_neighbors(hexes, placed["zachodnia_straz"])),
        ("trakt północny → Vilnograd", paveable_neighbors(hexes, placed["vilnograd_stolica"])),
        ("trakt południowy → Wybrzeże", {south_exit}),
        ("Wielkie Targi",  paveable_neighbors(hexes, placed["wielkie_targi"])),
        ("Kasztel Rycerski", paveable_neighbors(hexes, placed["kasztel_rycerski"])),
        ("Nowe Dobra",     paveable_neighbors(hexes, placed["nowe_dobra"])),
        ("Przeprawa Król.", paveable_neighbors(hexes, placed["przeprawa_krol"])),
        ("Klasztor Iskry", paveable_neighbors(hexes, placed["klasztor_iskry"])),
        ("Osada Kupiecka", paveable_neighbors(hexes, placed["osada_kupiecka"])),
    ]
    added, log = [], []
    for name, tset in order:
        if not tset:
            log.append(f"  ! {name}: brak przejezdnego celu — pominięto")
            continue
        path, cost = roads.dijkstra_to_targets(hexes, set(net), tset)
        if path is None:
            log.append(f"  ! {name}: brak trasy — pominięto")
            continue
        new = []
        for k in path:
            if hexes[k]["hex_type"] in roads.NETWORK:
                continue
            hexes[k]["hex_type"] = "bridge" if hexes[k]["hex_type"] == "river" else "road"
            new.append(k)
        added += new
        net |= set(path)
        log.append(f"  {name}: {path[0]} → {path[-1]} — {len(new)} hexów (koszt {cost})")
    for line in log:
        print(line)
    return added


# ── ROGATKI na wjazdach (labelowany road-hex — zostaje w sieci) ─────────────
def place_rogatki(hexes, east_exit, south_exit):
    out = []
    # Rogatka Wschodnia — komora celna na trakcie z Kresów (§4)
    e_inland = min((nb for nb in ax_neighbors(*east_exit)
                    if nb in hexes and hexes[nb]["hex_type"] in roads.NETWORK),
                   key=lambda k: (k[0], k[1]), default=None)
    if e_inland and not hexes[e_inland].get("location_key"):
        hexes[e_inland]["label"] = "Rogatka Wschodnia"
        hexes[e_inland]["location_key"] = "rogatka_wschodnia"
        hexes[e_inland]["atmosphere"] = ("Komora celna na trakcie z Kresów: glejty, myto, "
                                         "kontrola papierów. Berta Twarda Pieczęć nie mruga.")
        out.append(e_inland)
    # Rogatka Południowa — wjazd ku Wybrzeżu
    if south_exit in hexes and hexes[south_exit]["hex_type"] in roads.NETWORK \
            and not hexes[south_exit].get("location_key"):
        hexes[south_exit]["label"] = "Rogatka Południowa"
        hexes[south_exit]["location_key"] = "rogatka_poludniowa"
        hexes[south_exit]["atmosphere"] = "Rogatka na trakcie ku Wybrzeżu Łez. Za nią prawo Korony słabnie."
        out.append(south_exit)
    return out


# ── POLA UPRAWNE: łany wokół osad + wzdłuż rzeki (§5 ~400) ───────────────────
def sow_fields(hexes, placed, river, target=400):
    settle = set(placed.values())
    riverset = set(river)
    convertible = ("plains", "heath")
    scored = []
    for k, h in hexes.items():
        if h["hex_type"] not in convertible or h.get("location_key"):
            continue
        d_set = min((ax_dist(k, s) for s in settle), default=99)
        d_riv = min((ax_dist(k, s) for s in riverset), default=99)
        d = min(d_set, d_riv)
        if d <= 3:
            scored.append((d, k))
    scored.sort()
    fields = [k for _, k in scored[:target]]
    for k in fields:
        hexes[k]["hex_type"] = "pola_uprawne"
    return fields


# ── TEASERY GRANICZNE ────────────────────────────────────────────────────────
def add_border_teasers(hexes, local, east_exit, south_exit):
    east_col = {k for k, (c, r) in local.items() if c == W - 1}       # q = -1 (Kresy)
    south_row = {k for k, (c, r) in local.items() if r == H - 1}      # S krawędź (Wybrzeże)
    n = 0
    for k in sorted(east_col, key=lambda k: local[k][1]):
        if local[k][1] % 4 == 0 and k != east_exit \
                and not hexes[k].get("label") and hexes[k]["hex_type"] not in roads.NETWORK:
            hexes[k]["label"] = "ku Kresom"
            n += 1
    for k in sorted(south_row, key=lambda k: local[k][0]):
        if local[k][0] % 4 == 0 and k != south_exit \
                and not hexes[k].get("label") and hexes[k]["hex_type"] not in roads.NETWORK:
            hexes[k]["label"] = "ku Wybrzeżu Łez"
            n += 1
    return n


def set_encounter(hexes):
    for h in hexes.values():
        t = h["hex_type"]
        if t in ("city", "town", "village", "road", "bridge"):
            h["encounter_chance"] = 0.0
        elif t in ENCOUNTER:
            h["encounter_chance"] = ENCOUNTER[t]


def dist_table(hexes):
    c = Counter(h["hex_type"] for h in hexes.values())
    lines = ["| hex_type | ile | % |", "|---|---:|---:|"]
    tot = sum(c.values())
    for t, n in c.most_common():
        lines.append(f"| `{t}` ({PL_NAMES.get(t, t)}) | {n} | {100*n/tot:.1f}% |")
    lines.append(f"| **RAZEM** | **{tot}** | 100% |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--dry-run", action="store_true", help="nie zapisuj JSON-a")
    ap.add_argument("--png", default="docs/world/previews/koronne_niziny_kn2_after.png")
    ap.add_argument("--md-table", default=None)
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    hexes, local, (q_off, r_off) = build_grid()
    print(f"siatka {W}×{H} = {len(hexes)} hexów, offset ({q_off},{r_off}), ziarno={args.seed}")

    print("[1] teren: plains-dominant + kępy lasu / wrzosy / wzgórza")
    paint_terrain(hexes, rng)

    print("[2] rzeka NE → Vilnograd → S (nić do Wybrzeża)")
    vil = nearest(hexes, local, *VILNOGRAD, lambda k: True)
    river, mouth = carve_river(hexes, local, rng, protect={vil})
    print(f"  rzeka: {len(river)} hexów, ujście przy {mouth}")

    print("[3] jeziora / stawy młyńskie")
    lakes = carve_lakes(hexes, local, rng)
    print(f"  jeziora: {len(lakes)} hexów")

    print("[4] osady (§4)")
    placed = place_settlements(hexes, local)
    for key, pos in placed.items():
        print(f"  {key}: {pos} ({hexes[pos]['hex_type']})")

    east_exit = nearest(hexes, local, *EAST_EXIT,
                        lambda k: not hexes[k].get("location_key")
                        and hexes[k]["hex_type"] not in ("lake", "river"))
    south_exit = mouth if hexes[mouth]["hex_type"] != "lake" else \
        nearest(hexes, local, *SOUTH_EXIT, lambda k: hexes[k]["hex_type"] not in ("lake",))

    print("[5] trakty: 4 z Volhynii + osady (graf spójny)")
    added = build_roads(hexes, placed, east_exit, south_exit)
    roads.stitch(hexes)
    ok, msg = check_road_graph(hexes)
    print(f"  trakt {len(added)} hexów; {msg} (spójny: {ok})")
    assert ok, "graf traktów NIE spójny — przerwane"

    print("[6] rogatki na wjazdach")
    rog = place_rogatki(hexes, east_exit, south_exit)
    print(f"  rogatki: {[hexes[k]['label'] for k in rog]}")

    print("[7] pola uprawne wokół osad + wzdłuż rzeki (§5 ~400)")
    fields = sow_fields(hexes, placed, river)
    print(f"  łany: {len(fields)} hexów")

    print("[8] teasery graniczne (ku Kresom / ku Wybrzeżu Łez)")
    n_teaser = add_border_teasers(hexes, local, east_exit, south_exit)
    print(f"  teasery: {n_teaser}")

    set_encounter(hexes)

    # kontrola: trakt wschodni dolega do granicy Kresów (-1,13 ↔ most 0,13)
    kn_border = (-1, 13)
    assert kn_border in hexes, "brak hexa granicznego (-1,13)"
    border_ok = hexes[kn_border]["hex_type"] in roads.NETWORK or any(
        hexes[nb]["hex_type"] in roads.NETWORK for nb in ax_neighbors(*kn_border) if nb in hexes)
    print(f"  granica z Kresami (-1,13): typ={hexes[kn_border]['hex_type']}, "
          f"trakt dolega={border_ok}")

    table = dist_table(hexes)
    print("\n[9] rozkład hex_type:\n")
    print(table)
    if args.md_table:
        Path(args.md_table).write_text(table + "\n", encoding="utf-8")
        print(f"\ntabelka: {args.md_table}")

    if not args.no_png:
        p = save_png(hexes, "KORONNE NIZINY — mapa od zera (KN-2, §5)",
                     f"równiny cywilizowane + 4 trakty Volhynii + rzeka NE→Vilnograd→S, "
                     f"seed={args.seed} — DB NIE RUSZANA",
                     ROOT / args.png)
        print(f"\nPNG: {p.relative_to(ROOT)}")

    if args.dry_run:
        print("\n--dry-run: JSON NIE zapisany")
        return

    q_vals = [k[0] for k in hexes]
    r_vals = [k[1] for k in hexes]
    out = {
        "region": REGION,
        "label": "Koronne Niziny",
        "status": "coming",
        "w": W, "h": H,
        "q_offset": q_off, "r_offset": r_off,
        "bounds": {"q_min": min(q_vals), "q_max": max(q_vals),
                   "r_min": min(r_vals), "r_max": max(r_vals)},
        "terrain_plan_seed": args.seed,
        "note": ("Mapa zbudowana OD ZERA wg koronne_niziny.md §5 (KN-2, #1483): "
                 "równiny cywilizowane (plains/heath dominują), pola_uprawne wokół osad "
                 "i wzdłuż rzeki, kępy lasu, rzeka NE→Vilnograd→S (nić do Wybrzeża), "
                 "4 trakty krzyżują się w Volhynii, rogatki na wjazdach; trakt wschodni "
                 "spina się z przejściem Kresów (-1,13 ↔ most 0,13). DB NIE RUSZANA — "
                 "seed: scripts/seed_world_map.py --region koronne_niziny PO akceptacji PNG."),
        "hexes": [hexes[k] for k in sorted(hexes)],
    }
    path = ROOT / "data" / "regions" / f"region_{REGION}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {path.relative_to(ROOT)} ({len(out['hexes'])} hexów)")


if __name__ == "__main__":
    main()
