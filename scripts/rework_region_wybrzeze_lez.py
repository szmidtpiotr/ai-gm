#!/usr/bin/env python3
"""Budowa mapy WYBRZEŻA ŁEZ OD ZERA wg lore §5 (WL-2, #1483 / wybrzeze_lez.md).

KONTEKST
  `data/regions/region_wybrzeze_lez.json` to SURÓWKA generatora FAZY RM
  (31% swamp, 5% sea — patrz wybrzeze_lez.md §0). To NIE jest ustalenie.
  Ten skrypt bierze z surówki WYŁĄCZNIE siatkę 2500 hexów (te same axial q,r,
  ten sam offset kontynentalny) i 17 teaserów „ku Koronnym Nizinom" na krawędzi
  północnej — a CAŁY teren buduje od nowa wg układu z rozdziału krainy (§5):

    NW → SE:
    (a) zaplecze lądowe: trakt z Koronnych Nizin + ujście rzeki + wsie + kępy lasu,
    (b) pas wybrzeża: CZARNOGRÓD przy ujściu rzeki (port rzeczno-morski), klify,
    (c) pas pływowy `plycizna`: wsie na palach + warzelnie soli,
    (d) `rafy` — pas grozy żeglarskiej przy latarni,
    (e) `morze` na wschodzie i południu (nieprzejezdne pieszo),
    (f) WYSPY (celowo bez połączenia lądowego — dostęp tylko rejsami WL-4):
        duża wyspa pod ZATOKĘ TOPIELCÓW + 3 wysepki (kryjówka przemytników,
        opuszczona latarnia, wysepka diaspory wyspiarzy).

  Nowe typy terenu z WL-1 (#1505): morze / plycizna / rafy / wydmy.

  DB NIE JEST RUSZANA (bramka #1483/#1482: kanon = plik krainy w git). Seed do
  `world_hexes` to osobny krok (`scripts/seed_world_map.py`) PO akceptacji PNG.

DETERMINIZM
  Wszystko z jednego ziarna (`--seed`, domyślnie SEED). Bez zegara.

UŻYCIE
  python3 scripts/rework_region_wybrzeze_lez.py --dry-run   # podgląd, plik NIE zapisany
  python3 scripts/rework_region_wybrzeze_lez.py             # zapis + oba PNG
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

# reużycie narzędzi z fal Grań/Czarnobór/Pustkowia — ten sam styl PNG + kontrola grafu
from reseed_region_terrain import (  # noqa: E402
    COLORS, PL_NAMES, ax_dist, ax_neighbors, check_road_graph,
    distribution_table, noise_field, save_png,
)
import stitch_region_roads as roads  # noqa: E402

REGION = "wybrzeze_lez"
SEED = 1588

# ── nowe typy terenu WL-1 (kolory 1:1 z hex_type_config, migrations_admin.py) ──
COLORS.update({
    "morze":    (11, 42, 82),      # #0b2a52 — otwarte morze (nieprzejezdne pieszo)
    "plycizna": (111, 176, 201),   # #6fb0c9 — mielizna pływowa
    "rafy":     (46, 125, 125),    # #2e7d7d — rafy (nieprzejezdne pieszo)
    "wydmy":    (217, 196, 143),   # #d9c48f — wydmy nadmorskie
})
PL_NAMES.update({
    "morze":    "morze",
    "plycizna": "płycizna",
    "rafy":     "rafy",
    "wydmy":    "wydmy",
    "coast":    "wybrzeże/klify",
    "swamp":    "bagna ujścia",
})

# koszt podróży dla dijkstry traktu LĄDOWEGO.
#   morze / rafy nieprzejezdne (is_passable=0) → None.
#   plycizna is_passable=1, ale trakt jej NIE utwardza (pływy WL-5) → None, chodzi się pieszo.
#   wydmy tanie, coast jak plaża/klif.
roads.TERRAIN_COST.update({
    "morze":    None,
    "rafy":     None,
    "plycizna": None,
    "wydmy":    2,
    "coast":    3,
    "swamp":    6,
})

# encounter_chance per nowy typ (WL-1 hex_type_config)
ENCOUNTER_NEW = {"morze": 0.0, "plycizna": 0.02, "rafy": 0.02, "wydmy": 0.05}
ENCOUNTER_STD = {
    "forest": 0.25, "swamp": 0.30, "hills": 0.15, "coast": 0.12, "plains": 0.10,
    "river": 0.12, "ruins": 0.35, "road": 0.05, "bridge": 0.40,
    "city": 0.0, "town": 0.0, "village": 0.0,
}

# ── BUDŻET TERENU (lore §5) — WARTOŚCI STARTOWE (Numbers Policy) ──────────────
# Kolejność = koncentryczne pasy od najgłębszego morza ku lądowi (rank po seaness).
# Wyspy dokładane osobno (zjadają część morza). Lądowy interior dzielony na końcu.
BUDGET = {
    "morze":    700,   # §5 ~700 — E + S
    "rafy":     150,   # §5 ~150 — pas przy latarni, ring między morzem a płycizną
    "plycizna": 450,   # §5 ~450 — pas pływowy
    "coast":    250,   # §5 ~250 — klify / plaże wraków
    "wydmy":    120,   # §5 ~120 — wydmy tuż za linią brzegu
    # reszta (najniższa seaness) = interior lądowy (§5 plains/heath ~400 + forest ~250)
    "forest":   250,   # §5 ~250 — kępy lasu w głębi lądu
    "swamp":     45,   # bagna ujścia (przy Czarnogrodzie)
}

# ── kotwice geograficzne (docelowe q,r; snapowane do najbliższego pasującego) ──
# NW land → SE sea. q -50..-1 (W→E), r 51..124 (N→S).
# #1542 fix: blok wybrzeze_lez wyrównany do wzoru bloków (q_off=-50, NIE -55) — kotwice +5.
RIVER_SOURCE = (-35, 58)     # skąd wpływa rzeka z Koronnych Nizin (N ląd)
CZARNOGROD_HINT = (-25, 80)  # okolica ujścia — Czarnogród snapuje do faktycznego ujścia
LATARNIA_HINT = (-13, 88)    # Latarnia Topielców — przy pasie raf, ląd/klif

# wyspy: (key, label, hex_type, q, r, rozmiar, rafy_ring?)
ISLANDS = [
    ("zatoka_topielcow",      "Zatoka Topielców",       "town",    -20, 102, 42, False),
    ("kryjowka_przemytnikow", "Kryjówka Przemytników",  "ruins",    -8,  93,  8, False),
    ("opuszczona_latarnia",   "Opuszczona Latarnia",    "ruins",    -7, 111,  7, True),
    ("wysepka_diaspory",      "Wysepka Diaspory",       "village", -28, 114,  9, False),
]

# osady lądowe (key, label, hex_type, docelowe qn 0-1 W→E, yn 0-1 N→S, dozwolone typy)
LAND_SETTLEMENTS = [
    ("wybrzeze_lez_port", "Port Łez",       "village", 0.30, 0.55, ("coast", "wydmy")),
    ("osada_rybacka",     "Rybacka Przystań", "village", 0.20, 0.42, ("coast", "wydmy", "plains")),
    ("osada_rolna",       "Rolne Sioło",     "village", 0.30, 0.22, ("plains", "heath")),
    ("mokradla_ujscia",   "Mokradła Ujścia", "ruins",   0.45, 0.40, ("swamp", "plains")),
]
# osady pływowe (na palach + warzelnie) — SIEDZĄ na płyciźnie (bez traktu, WL-5)
TIDAL_SETTLEMENTS = [
    ("wsie_na_palach",  "Wsie na Palach",  "village", 0.42, 0.58, ("plycizna",)),
    ("warzelnie_solne", "Warzelnie Soli",  "ruins",   0.52, 0.66, ("plycizna",)),
]

FROZEN_LABEL_PREFIX = "ku "   # teasery graniczne


def load():
    path = ROOT / "data" / "regions" / f"region_{REGION}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    hexes = {(h["q"], h["r"]): dict(h) for h in data["hexes"]}
    return data, hexes, path


# ── SEANESS: gradient rosnący ku E + S; ląd w NW ─────────────────────────────
def build_seaness(keys, rng):
    qs = [q for q, r in keys]
    ys = {(q, r): q / 2.0 + r for (q, r) in keys}   # ekranowa oś N→S (flat-top)
    q_lo, q_hi = min(qs), max(qs)
    y_lo, y_hi = min(ys.values()), max(ys.values())
    qspan = (q_hi - q_lo) or 1
    yspan = (y_hi - y_lo) or 1
    n1 = noise_field(keys, rng, passes=5)   # organiczny brzeg
    sea = {}
    for k in keys:
        q, r = k
        qn = (q - q_lo) / qspan            # 0 W → 1 E
        yn = (ys[k] - y_lo) / yspan        # 0 N → 1 S
        core = 0.50 * qn + 0.60 * yn + 0.20 * qn * yn   # najgłębiej w SE, rośnie E+S
        sea[k] = core + (n1[k] - 0.5) * 0.22
    return sea


def assign_bands(hexes, keys, sea, frozen):
    """Koncentryczne pasy morze→ląd przez ranking seaness (gwarantuje budżet)."""
    wild = [k for k in keys if k not in frozen]
    order = sorted(wild, key=lambda k: (-sea[k], k))   # od najgłębszego morza
    assigned = {}
    idx = 0
    for typ in ("morze", "rafy", "plycizna", "coast", "wydmy"):
        n = BUDGET[typ]
        for k in order[idx:idx + n]:
            assigned[k] = typ
        idx += n
    interior = order[idx:]   # najniższa seaness = ląd
    return assigned, interior


def assign_interior(hexes, interior, sea, rng):
    """Ląd (najniższa seaness): forest (kępy, po szumie wilgoci), swamp (ujście),
       reszta plains/heath (rolniczo-rybackie zaplecze)."""
    n2 = noise_field(interior, rng, passes=3)
    out = {}
    # las — najwilgotniejsze plamy w głębi lądu (najniższa seaness → najdalej od morza)
    land_sorted = sorted(interior, key=lambda k: (sea[k], k))   # od najgłębszego lądu
    forest = sorted(land_sorted[: int(len(land_sorted) * 0.7)],
                    key=lambda k: (-n2[k], k))[: BUDGET["forest"]]
    fset = set(forest)
    for k in forest:
        out[k] = "forest"
    # reszta lądu → plains, z pasmem heath na suchym skraju + trochę hills
    rest = [k for k in interior if k not in fset]
    for k in rest:
        v = n2[k]
        if v < 0.30:
            out[k] = "heath"
        elif v > 0.82:
            out[k] = "hills"
        else:
            out[k] = "plains"
    return out


# ── RZEKA: greedy „w dół" seaness od źródła do brzegu; ujście = Czarnogród ────
def snap(hexes, hint, pred):
    cand = [k for k in hexes if pred(k)]
    return min(cand, key=lambda k: (ax_dist(k, hint), k)) if cand else None


def carve_river(hexes, sea):
    """Rzeka z Nizin (N) do pierwszego hexa brzegowego. Zwraca (river_cells, mouth)."""
    src = snap(hexes, RIVER_SOURCE,
               lambda k: hexes[k]["hex_type"] in ("plains", "heath", "forest")
               and not hexes[k].get("label") and not hexes[k].get("location_key"))
    shore = {"coast", "plycizna", "wydmy"}
    cur = src
    river = []
    visited = {cur}
    for _ in range(200):
        nbrs = [n for n in ax_neighbors(*cur) if n in hexes and n not in visited]
        if not nbrs:
            break
        nxt = max(nbrs, key=lambda n: (sea[n], n))   # ku morzu
        t = hexes[nxt]["hex_type"]
        if t in shore or t == "morze":
            return river, cur   # cur = ostatni ląd = ujście (port rzeczno-morski)
        if hexes[nxt].get("label") or hexes[nxt].get("location_key"):
            visited.add(nxt); continue
        if t in ("plains", "heath", "forest", "hills"):
            hexes[nxt]["hex_type"] = "river"
            river.append(nxt)
        visited.add(nxt); cur = nxt
    return river, cur


# ── WYSPY: bloby lądu w morzu, otoczone morzem (bez lądowego mostu) ──────────
def carve_island(hexes, center, size, rng, rafy_ring=False):
    """Zamień `size` najbliższych hexów morza wokół `center` na ląd wyspy.
       Wewnątrz hills/plains, dalej wydmy, brzeg coast; opcjonalny pierścień raf."""
    if center not in hexes or hexes[center]["hex_type"] != "morze":
        # snapuj do najbliższego morza
        center = min((k for k in hexes if hexes[k]["hex_type"] == "morze"),
                     key=lambda k: (ax_dist(k, center), k))
    # flood po morzu od centrum
    seen = {center}
    dq = deque([center])
    blob = []
    while dq and len(blob) < size:
        cur = dq.popleft()
        if hexes[cur]["hex_type"] == "morze" and not hexes[cur].get("label"):
            blob.append(cur)
        for nb in sorted(ax_neighbors(*cur)):
            if nb in hexes and nb not in seen and hexes[nb]["hex_type"] == "morze":
                seen.add(nb); dq.append(nb)
    # przypisz teren wg odległości od centrum
    for k in blob:
        d = ax_dist(k, center)
        if d <= 1:
            hexes[k]["hex_type"] = "hills"
        elif d <= 2:
            hexes[k]["hex_type"] = "plains"
        elif d <= 3:
            hexes[k]["hex_type"] = "wydmy"
        else:
            hexes[k]["hex_type"] = "coast"
    # brzeg blobu = coast (styk z morzem)
    for k in blob:
        for nb in ax_neighbors(*k):
            if nb in hexes and hexes[nb]["hex_type"] == "morze" and hexes[k]["hex_type"] not in ("coast", "wydmy"):
                pass
    if rafy_ring:
        for k in list(blob):
            for nb in ax_neighbors(*k):
                if nb in hexes and hexes[nb]["hex_type"] == "morze" and rng.random() < 0.5:
                    hexes[nb]["hex_type"] = "rafy"
    return blob, center


# ── OSADY ────────────────────────────────────────────────────────────────────
def norm_coords(hexes):
    qs = [q for q, r in hexes]
    ys = {(q, r): q / 2.0 + r for (q, r) in hexes}
    q_lo, q_hi = min(qs), max(qs)
    y_lo, y_hi = min(ys.values()), max(ys.values())
    qspan = (q_hi - q_lo) or 1
    yspan = (y_hi - y_lo) or 1
    return {k: ((k[0] - q_lo) / qspan, (ys[k] - y_lo) / yspan) for k in hexes}


def mainland_mask(hexes, start):
    """Ląd stały (BFS od ujścia rzeki) — wszystko poza morzem/rafami spójne z lądem.
       Wyspy są odcięte pierścieniem morza, więc wypadają z maski."""
    seen = {start}
    dq = deque([start])
    while dq:
        cur = dq.popleft()
        for nb in ax_neighbors(*cur):
            if nb in hexes and nb not in seen and hexes[nb]["hex_type"] not in ("morze", "rafy"):
                seen.add(nb); dq.append(nb)
    return seen


def place_settlement(hexes, nc, used, key, label, typ, qn, yn, allowed, mask=None):
    cand = []
    for k, (kx, ky) in nc.items():
        if k in used:
            continue
        if mask is not None and k not in mask:
            continue
        if hexes[k]["hex_type"] not in allowed:
            continue
        if hexes[k].get("label") or hexes[k].get("location_key"):
            continue
        near = min((ax_dist(k, u) for u in used), default=99)
        if near < 3:
            continue
        cand.append((math.hypot(kx - qn, ky - yn), k))
    if not cand:
        return None
    cand.sort()
    pos = cand[0][1]
    hexes[pos]["hex_type"] = typ
    hexes[pos]["label"] = label
    hexes[pos]["location_key"] = key
    used.add(pos)
    return pos


# ── TRAKT LĄDOWY: granica Niziny → Czarnogród → wsie lądowe (spójny graf) ─────
def build_roads(hexes, czarnogrod, land_targets):
    def paveable_neighbors(pos):
        return {nb for nb in ax_neighbors(*pos)
                if nb in hexes and roads.cost_of(hexes, nb) is not None}

    # wjazd = teaser „ku Koronnym Nizinom" najbliżej Czarnogrodu, jego przejezdni sąsiedzi
    teasers = [k for k, h in hexes.items()
               if (h.get("label") or "").startswith(FROZEN_LABEL_PREFIX)]
    entry_teaser = min(teasers, key=lambda k: (ax_dist(k, czarnogrod), k))
    net_sources = paveable_neighbors(entry_teaser)
    if not net_sources:
        raise SystemExit(f"BŁĄD: teaser {entry_teaser} bez przejezdnego sąsiada")

    net = set(net_sources)
    added = []
    order = [("Czarnogród", czarnogrod)] + [("wieś", t) for t in land_targets]
    log = []
    for name, target in order:
        tgt = paveable_neighbors(target)
        if not tgt:
            log.append(f"  ! {name} {target}: brak przejezdnego sąsiada — pominięto")
            continue
        path, cost = roads.dijkstra_to_targets(hexes, set(net), tgt)
        if path is None:
            log.append(f"  ! {name} {target}: brak trasy — pominięto")
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
    return added, entry_teaser


def set_encounter(hexes):
    for h in hexes.values():
        t = h["hex_type"]
        if t in ("city", "town", "village", "road", "bridge"):
            h["encounter_chance"] = 0.0
        elif t in ENCOUNTER_NEW:
            h["encounter_chance"] = ENCOUNTER_NEW[t]
        elif t in ENCOUNTER_STD:
            h["encounter_chance"] = ENCOUNTER_STD[t]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--dry-run", action="store_true", help="nie zapisuj JSON-a")
    ap.add_argument("--png-before", default="docs/world/previews/wybrzeze_lez_terrain_before.png")
    ap.add_argument("--png-after", default="docs/world/previews/wybrzeze_lez_terrain_after.png")
    ap.add_argument("--md-table", default=None)
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    data, hexes, path = load()
    before = {k: dict(h) for k, h in hexes.items()}
    keys = sorted(hexes.keys())
    print(f"źródło: {path.relative_to(ROOT)} ({len(hexes)} hexów), ziarno={args.seed}")

    # zamrożone = teasery „ku Koronnym Nizinom" (przenoszone 1:1, wymuszony ląd)
    frozen = {k for k in keys if (hexes[k].get("label") or "").startswith(FROZEN_LABEL_PREFIX)}
    print(f"\n[0] teasery graniczne (zamrożone, ląd): {len(frozen)}")

    # skasuj CAŁY zastany teren + etykiety osad z surówki (budujemy od zera)
    for k in keys:
        if k in frozen:
            hexes[k]["hex_type"] = "plains"       # granica z Nizinami = ląd
            hexes[k]["location_key"] = None
        else:
            hexes[k]["hex_type"] = "morze"
            hexes[k]["label"] = None
            hexes[k]["location_key"] = None
        hexes[k]["atmosphere"] = None

    print("[1] pasy terenu NW→SE (rank po seaness):")
    sea = build_seaness(keys, rng)
    band, interior = assign_bands(hexes, keys, sea, frozen)
    for k, t in band.items():
        hexes[k]["hex_type"] = t
    inter = assign_interior(hexes, interior, sea, rng)
    for k, t in inter.items():
        hexes[k]["hex_type"] = t
    print(f"  pasy: {dict(Counter(band.values()))}")
    print(f"  interior: {dict(Counter(inter.values()))}")

    print("\n[2] rzeka + ujście (Czarnogród, port rzeczno-morski):")
    river, mouth = carve_river(hexes, sea)
    # Czarnogród na ujściu (ostatni ląd przy brzegu)
    hexes[mouth]["hex_type"] = "town"
    hexes[mouth]["label"] = "Czarnogród"
    hexes[mouth]["location_key"] = "czarnogrod_port"
    hexes[mouth]["atmosphere"] = ("Smolisty port rzeczno-morski u ujścia rzeki z Nizin. "
                                  "8 tysięcy dusz, prawo Korony kończy się na linii przyboju.")
    # bagna ujścia wokół
    est = 0
    for nb in ax_neighbors(*mouth):
        if nb in hexes and hexes[nb]["hex_type"] in ("plains", "heath", "coast") and est < 3:
            hexes[nb]["hex_type"] = "swamp"; est += 1
    print(f"  rzeka: {len(river)} hexów, źródło→ujście={mouth}  (bagien ujścia +{est})")

    print("\n[3] wyspy (bez mostu lądowego — dostęp tylko rejsami WL-4):")
    for key, label, typ, q, r, size, ring in ISLANDS:
        blob, center = carve_island(hexes, (q, r), size, rng, rafy_ring=ring)
        hexes[center]["hex_type"] = typ
        hexes[center]["label"] = label
        hexes[center]["location_key"] = key
        print(f"  {label}: {len(blob)} hexów wyspy, centrum={center}"
              + ("  (+rafy)" if ring else ""))

    print("\n[4] osady lądowe + pływowe:")
    nc = norm_coords(hexes)
    mask = mainland_mask(hexes, mouth)   # tylko ląd stały — wyspy odcięte
    used = {k for k, h in hexes.items() if h.get("location_key")}
    land_targets = []
    for key, label, typ, qn, yn, allowed in LAND_SETTLEMENTS:
        pos = place_settlement(hexes, nc, used, key, label, typ, qn, yn, allowed, mask=mask)
        if pos:
            print(f"  {label}: {pos} ({typ})")
            if typ in ("village", "town", "ruins"):
                land_targets.append(pos)
    # Latarnia Topielców — na najbardziej wysuniętym w morze cyplu lądu stałego
    lat_cand = [k for k in mask
                if hexes[k]["hex_type"] in ("coast", "wydmy")
                and not hexes[k].get("label") and not hexes[k].get("location_key")]
    lat = max(lat_cand, key=lambda k: (sea[k], k)) if lat_cand else None
    if lat:
        hexes[lat]["hex_type"] = "ruins"
        hexes[lat]["label"] = "Latarnia Topielców"
        hexes[lat]["location_key"] = "latarnia_topielcow"
        hexes[lat]["atmosphere"] = ("Opuszczona, lecz nocą zapala się sama i wciąga statki na rafy. "
                                    "Kto stoi na niej z ogniem?")
        used.add(lat)
        print(f"  Latarnia Topielców: {lat} (przy rafach)")
    for key, label, typ, qn, yn, allowed in TIDAL_SETTLEMENTS:
        pos = place_settlement(hexes, nc, used, key, label, typ, qn, yn, allowed, mask=mask)
        if pos:
            print(f"  {label}: {pos} ({typ}, na płyciźnie — bez traktu)")

    print("\n[5] trakt lądowy (granica Nizin → Czarnogród → wsie; BFS spójny):")
    added, entry = build_roads(hexes, mouth, land_targets)
    roads.stitch(hexes)
    ok, msg = check_road_graph(hexes)
    print(f"  wjazd z Nizin przy teaserze {entry}; trakt {len(added)} hexów")
    print(f"  {msg} (spójny: {ok})")

    set_encounter(hexes)

    # kontrola: wyspy NIE mają lądowego połączenia z siecią dróg
    net = {k for k, h in hexes.items() if h["hex_type"] in roads.NETWORK}
    island_keys = {key for key, *_ in ISLANDS}
    for k, h in hexes.items():
        if h.get("location_key") in island_keys:
            assert not any(nb in net for nb in ax_neighbors(*k)), \
                f"wyspa {h['location_key']} dotyka traktu — złamana izolacja WL-4"

    assert ok, "graf dróg NIE spójny — przerwane"

    table = distribution_table(before, hexes)
    print("\n[6] rozkład hex_type PRZED/PO:\n")
    print(table)
    if args.md_table:
        Path(args.md_table).write_text(table + "\n", encoding="utf-8")
        print(f"\ntabelka: {args.md_table}")

    if not args.no_png:
        p1 = save_png(before, "WYBRZEŻE ŁEZ — PRZED (surówka RM)",
                      "surowy generator (git: data/regions/region_wybrzeze_lez.json)",
                      ROOT / args.png_before)
        p2 = save_png(hexes, "WYBRZEŻE ŁEZ — PO (plan wybrzeze_lez.md §5)",
                      f"mapa od zera + trakt + wyspy, seed={args.seed} — DB NIE RUSZANA",
                      ROOT / args.png_after)
        print(f"\nPNG przed: {p1.relative_to(ROOT)}")
        print(f"PNG po:    {p2.relative_to(ROOT)}")

    if args.dry_run:
        print("\n--dry-run: JSON NIE zapisany")
    else:
        data["hexes"] = [hexes[k] for k in sorted(hexes)]
        data["status"] = data.get("status", "coming")
        data["terrain_plan_seed"] = args.seed
        data["note"] = ("Mapa zbudowana OD ZERA wg wybrzeze_lez.md §5 (WL-2, #1483): "
                        "pasy NW→SE morze/plycizna/rafy/coast/wydmy, Czarnogród u ujścia rzeki, "
                        "wyspy bez mostu lądowego (rejsy WL-4). Surówka RM nadpisana.")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nZapisano {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
