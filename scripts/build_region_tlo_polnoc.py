#!/usr/bin/env python3
"""build_region_tlo_polnoc.py — ZIEMIE PÓŁNOCY tła kontynentu (#1549, TŁO-3/4).

Dwa sloty tła nad pasem row=0, po obu stronach Siwych Grań:
  * NW  blok (-1,-1) offset (-50,-25) — Ziemie Północy ZACHÓD (nad Koronnymi Nizinami)
  * NE  blok ( 1,-1) offset ( 50,-75) — Ziemie Północy WSCHÓD (nad Czarnoborem)

To NIE krainy z rosteru (lore = 6 krain) — to *terra incognita*: bogaty, zróżnicowany
teren z nazwanymi POI pod przyszłe kampanie-wyprawy Kuźni. Globalnie NIEPRZECHODNIE
(world_regions status 'locked'), rysowane ZAWSZE bez mgły wojny (#1549 „widoczność
bez FOW"). Ciekawość = paliwo Kuźni.

ZASADY TERENU (#1549 + #1545):
  * PÓŁNOC = BARIERA: górne 1–2 rzędy = grań (nieprzechodnia, kraniec świata) +
    lodowiec/śnieg. NIE ściana górska po całości — tylko od góry.
  * WNĘTRZE duże i zróżnicowane: tundra (dominuje) + tajga iglasta + wzgórza +
    góry kępami + śnieg; kilka jezior TYLKO z dala od gór (morze/jezioro nigdy
    obok gór — reguła #1545 zostaje).
  * GRADIENTY do sąsiadów (żadnych ostrych linii bloków):
      NW: styk wschodni (Siwe Granie) = pogórze (hills/mountain);
          styk południowy (Koronne Niziny) = miękkie zejście we wrzosowiska/równiny.
      NE: styk zachodni (Siwe Granie) = pogórze (hills/mountain);
          styk południowy (Czarnobór) = śnieżna tajga → czarny las.

POI (nazwane, LABEL-only — bez obsady; materializuje je dopiero szablon Kuźni,
osobne issue). Kronika: „białe plamy z nazwą".
  NW: Twierdza Przełęczy · Kopalnie pod Grzbietem (#916 krasnoludy)
  NE: Obserwatorium Pradawnych · Lodowa Paszcza (loch endgame) · Wrak na lodzie

DETERMINIZM: jedno ziarno (--seed). DB NIE RUSZANA — seed osobno:
  scripts/seed_world_map.py --region tlo_polnoc_nw
  scripts/seed_world_map.py --region tlo_polnoc_ne

UŻYCIE (na .61):
  python3 scripts/build_region_tlo_polnoc.py --slot nw --dry-run --no-png
  python3 scripts/build_region_tlo_polnoc.py --slot nw
  python3 scripts/build_region_tlo_polnoc.py --slot ne
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from region_blocks import W, H, region_offsets  # noqa: E402
from reseed_region_terrain import (  # noqa: E402
    COLORS, PL_NAMES, ax_dist, ax_neighbors, noise_field, save_png,
)

# kolory/nazwy dla PNG (typy istnieją w hex_type_config; tu tylko podgląd)
COLORS.setdefault("czarny_las", (16, 29, 21))   # #101d15
COLORS.setdefault("las_iglasty", (31, 69, 54))  # #1f4536
COLORS.setdefault("lodowiec", (191, 227, 242))  # #bfe3f2
COLORS.setdefault("grania", (90, 90, 102))      # #5a5a66
COLORS.setdefault("tundra", (138, 173, 173))    # #8aadad
PL_NAMES.update({
    "tundra": "tundra", "las_iglasty": "tajga iglasta", "lodowiec": "lodowiec",
    "grania": "grań", "snow": "śnieg", "czarny_las": "czarny las",
    "mountain": "góry", "hills": "wzgórza", "lake": "jezioro",
})

# ── KONFIG SLOTÓW ─────────────────────────────────────────────────────────────
#   grania_side: krawędź(-e) z pogórzem od Siwych Grań ('E' dla NW, 'W' dla NE)
#   south_mode:  'heath'  → wrzosowiska/równiny (zejście do Koronnych Nizin, NW)
#                'taiga'  → śnieżna tajga → czarny las (zejście do Czarnoboru, NE)
#   POI: (col, row, label, atmosphere)
SLOTS = {
    "nw": {
        "region": "tlo_polnoc_nw",
        "label": "Ziemie Północy (zachód)",
        "seed": 15490,
        "grania_side": "E",   # wschodni styk = Siwe Granie
        "south_mode": "heath",
        "poi": [
            (24, 6, "Twierdza Przełęczy",
             "Opuszczona forteca nad jedyną przełęczą w barierze lodu. Za jej bramą "
             "kończy się znany świat; przyszła brama do tego, co dalej."),
            (14, 18, "Kopalnie pod Grzbietem",
             "Zawalone sztolnie krasnoludzkich miast pod szczytami (hak #916). Kto "
             "zejdzie w mrok Grzbietu, może nie wróci — ale rdzeń tam śpiewa."),
        ],
    },
    "ne": {
        "region": "tlo_polnoc_ne",
        "label": "Ziemie Północy (wschód)",
        "seed": 15491,
        "grania_side": "W",   # zachodni styk = Siwe Granie
        "south_mode": "taiga",
        "poi": [
            (30, 7, "Obserwatorium Pradawnych",
             "Kamienny pierścień na śnieżnym szczycie — Pradawni czytali stąd niebo. "
             "Mechanizm wciąż mruga w mrozie. Zagadka, nie forteca."),
            (36, 20, "Lodowa Paszcza",
             "Jaskinia lodowcowa ziejąca chłodem. Głęboko, farmowalnie, endgame — "
             "i coś w środku nie zamarzło do końca."),
            (20, 30, "Wrak na lodzie",
             "Statek zamarznięty setki kilometrów od morza. Jak się tu znalazł? "
             "Czysty początek wyprawy — komu przyśni się jego pokład."),
        ],
    },
}

# ── BARIERA PÓŁNOCNA (WARTOŚCI STARTOWE — Numbers Policy) ─────────────────────
BARRIER_GRANIA_ROWS = 1   # rząd 0 = grań (nieprzechodnia, kraniec świata)
BARRIER_ICE_ROWS = 2      # rzędy 0..1 = lodowiec/śnieg strefa lodu

# ── BUDŻET WNĘTRZA (na ~2400 hexów po odjęciu bariery) ───────────────────────
BUDGET = {
    "las_iglasty": 420,   # tajga iglasta kępami
    "hills": 260,         # pogórze / faliste
    "mountain": 200,      # góry kępami (jeziora trzymają się z dala — #1545)
    "snow": 220,          # płaty śniegu w wyższych partiach
    # reszta = tundra (dominuje — mroźna równina)
}
N_LAKES = 4               # kilka jezior, TYLKO z dala od gór


def off2ax(col, row):
    return (col, row - (col - (col & 1)) // 2)


def build_grid(region):
    q_off, r_off = region_offsets(region)
    hexes, local = {}, {}
    for row in range(H):
        for col in range(W):
            aq, ar = off2ax(col, row)
            k = (aq + q_off, ar + r_off)
            hexes[k] = {"q": k[0], "r": k[1], "hex_type": "tundra",
                        "label": None, "location_key": None,
                        "atmosphere": None, "encounter_chance": 0.0}
            local[k] = (col, row)
    return hexes, local, (q_off, r_off)


def paint_interior(hexes, local, rng):
    """Wnętrze: tundra-dominant + kępy tajgi / wzgórz / gór / śniegu wg szumu.

    NIE maluje bariery (rzędy < BARRIER_ICE_ROWS) ani pól, które i tak przejmą
    gradienty — te nadpisujemy później.
    """
    keys = [k for k, (c, r) in local.items() if r >= BARRIER_ICE_ROWS]
    moist = noise_field(keys, rng, passes=4)   # wilgoć → kępy tajgi
    elev = noise_field(keys, rng, passes=3)     # wysokość → góry/śnieg
    var = noise_field(keys, rng, passes=2)      # urozmaicenie → wzgórza
    assigned = {}

    def take(score, n, typ):
        pick = sorted([k for k in keys if k not in assigned],
                      key=lambda k: (-score(k), k))[:n]
        for k in pick:
            assigned[k] = typ
        return pick

    # góry — najwyższe partie (zwarte kępy)
    take(lambda k: elev[k], BUDGET["mountain"], "mountain")
    # śnieg — wysokie, ale nie-górskie
    take(lambda k: elev[k], BUDGET["snow"], "snow")
    # tajga iglasta — wilgotne plamy
    take(lambda k: moist[k], BUDGET["las_iglasty"], "las_iglasty")
    # wzgórza — zmienność
    take(lambda k: var[k], BUDGET["hills"], "hills")

    for k in keys:
        hexes[k]["hex_type"] = assigned.get(k, "tundra")


def paint_north_range(hexes, local, cfg, rng, foreign):
    """Pas gór na północy (#1549, spójność z masywem Siwych Grań).

    Masyw Grań siedzi w PIONOWYM środku swojego bloku, a bloki tła są
    przesunięte schodkowo o ±25 rzędów — więc „pas przy górnej krawędzi"
    nie trafiał w szerokość geograficzną masywu i łańcuch urywał się na szwie.

    Ten pass kotwiczy się w DANYCH sąsiada: na krawędzi od strony Grań
    znajduje pełną rozpiętość kontaktu z masywem (rodzina MOUNTAIN) i maluje
    KLIN — przy szwie pokrywa całą rozpiętość kontaktu (masyw wpływa w tło),
    a ku przeciwnej krawędzi zwęża się łukiem do wąskiego grzbietu pod barierą
    lodową. Efekt: brązowa masa masywu ciągnie się przez oba tła."""
    sg_east = cfg["grania_side"] == "E"     # NW: Granie na wschodzie
    edge_c = (W - 1) if sg_east else 0

    # rozpiętość kontaktu z masywem: wiersze lokalne krawędzi SG, których
    # obcy sąsiad (axial) jest rodziny MOUNTAIN
    contact = []
    for k, (c, r) in local.items():
        if c != edge_c:
            continue
        for nb in ax_neighbors(*k):
            if nb in foreign and BLEND_FAM.get(foreign[nb]) == "MOUNTAIN":
                contact.append(r)
                break
    deep = max(contact) if contact else 12   # dolny skraj klina przy szwie
    shallow = 4                              # wąski grzbiet na drugim końcu

    # jitter per KOLUMNA → krawędź klina faluje gładko, nie szumi per hex
    jitter = [2.0 * (rng.random() - 0.5) + 1.2 * (rng.random() - 0.5)
              for _ in range(W)]
    for k, (c, r) in sorted(local.items()):
        prox = (c / (W - 1)) if sg_east else (1 - c / (W - 1))
        depth = shallow + (deep - shallow) * (prox ** 1.6) + jitter[c]
        band_r = r - BARRIER_ICE_ROWS
        if band_r < 0 or band_r >= depth:
            continue
        if hexes[k]["hex_type"] == "lake":
            continue
        rel = band_r / max(depth, 1)         # 0 = pod barierą, 1 = dolny skraj
        roll = rng.random()
        if rel < 0.7:                        # rdzeń grzbietu — lity jak masyw Grań
            hexes[k]["hex_type"] = "mountain" if roll < 0.8 else "snow"
        else:                                # pogórze na dolnym skraju
            hexes[k]["hex_type"] = "hills" if roll < 0.55 else \
                ("mountain" if roll < 0.75 else "tundra")


def carve_lakes(hexes, local, rng, n_lakes=N_LAKES):
    """Jeziora TYLKO z dala od gór (reguła #1545: woda nigdy obok gór)."""
    def near_mountain(k):
        return any(hexes[nb]["hex_type"] == "mountain"
                   for nb in ax_neighbors(*k) if nb in hexes)

    pool = sorted([k for k, (c, r) in local.items()
                   if BARRIER_ICE_ROWS + 2 < r < H - 3 and 4 < c < W - 4
                   and hexes[k]["hex_type"] in ("tundra", "snow")
                   and not near_mountain(k)],
                  key=lambda k: (k[1], k[0]))
    rng.shuffle(pool)
    seeds, cells = [], []
    for k in pool:
        if all(ax_dist(k, s) > 9 for s in seeds) and not near_mountain(k):
            seeds.append(k)
        if len(seeds) >= n_lakes:
            break
    for s in seeds:
        blob = [s]
        for nb in sorted(ax_neighbors(*s)):
            if len(blob) >= 4:
                break
            if nb in hexes and hexes[nb]["hex_type"] in ("tundra", "snow") \
                    and not near_mountain(nb) and rng.random() < 0.5:
                blob.append(nb)
        for k in blob:
            hexes[k]["hex_type"] = "lake"
            cells.append(k)
    return cells


def paint_barrier(hexes, local, rng):
    """Górne rzędy = bariera lodowa: grań (nieprzechodnia) + lodowiec/śnieg."""
    n = 0
    for k, (c, r) in local.items():
        if r < BARRIER_GRANIA_ROWS:
            hexes[k]["hex_type"] = "grania"            # kraniec świata, nieprzechodni
            n += 1
        elif r < BARRIER_ICE_ROWS:
            # strefa lodu z lekkim szumem: lodowiec / śnieg / miejscami grań
            roll = rng.random()
            hexes[k]["hex_type"] = "grania" if roll < 0.25 else \
                ("lodowiec" if roll < 0.7 else "snow")
            n += 1
    return n


# ── BLEND DO SĄSIADÓW (data-driven, #1545/#1549) ─────────────────────────────
# Zamiast ślepych pasów per-krawędź: czytamy FAKTYCZNY teren sąsiadów z kanonu
# (data/regions/*.json), BFS od obcych hexów w głąb tła i rampujemy teren ku
# rodzinie konkretnego odcinka granicy. Tam gdzie Granie mają śnieg → tło ma
# góry; gdzie Granie mają rzekę/jezioro → tło ma dolinę (NIE górę, #1545);
# gdzie Niziny mają równiny → tło schodzi wrzosem w równiny; gdzie Czarnobór
# ma las → tło gęstnieje w śnieżną tajgę/czarny las.
BLEND_BAND = 8            # głębokość rampy (hexy w głąb tła)

BLEND_FAM = {
    "mountain": "MOUNTAIN", "snow": "MOUNTAIN", "grania": "MOUNTAIN",
    "lodowiec": "MOUNTAIN", "peak": "MOUNTAIN",
    "hills": "HILL", "foothills": "HILL", "przelecz": "HILL",
    "forest": "FOREST", "czarny_las": "FOREST", "las_iglasty": "FOREST",
    "plains": "OPEN", "heath": "OPEN", "step": "OPEN", "tundra": "OPEN",
    "grassland": "OPEN", "pola_uprawne": "OPEN",
    "river": "WATER", "lake": "WATER", "water": "WATER", "sea": "WATER",
    "morze": "WATER", "brod": "WATER", "coast": "WATER",
    "swamp": "WETLAND", "bagno": "WETLAND", "trzesawisko": "WETLAND",
}


def load_foreign(self_region):
    """Kanon terenu wszystkich innych krain: {(q,r): hex_type}."""
    foreign = {}
    for p in sorted((ROOT / "data" / "regions").glob("region_*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("region") == self_region:
            continue
        for h in data["hexes"]:
            foreign[(h["q"], h["r"])] = h["hex_type"]
    return foreign


def blend_to_neighbors(hexes, local, rng, foreign, band=BLEND_BAND):
    """Rampa terenu tła ku rodzinie faktycznego sąsiada (BFS od granicy).

    Zwraca liczbę przemalowanych hexów. Bariera (górne rzędy), jeziora i grań
    nietykalne. Szum deterministyczny (rng slotu) strzępi krawędź rampy."""
    from collections import deque, Counter as C

    dist, votes = {}, {}
    dq = deque()
    for k in hexes:
        v = C()
        for nb in ax_neighbors(*k):
            if nb in foreign:
                f = BLEND_FAM.get(foreign[nb])
                if f:
                    v[f] += 1
        if v:
            dist[k] = 1; votes[k] = v; dq.append(k)
    while dq:
        k = dq.popleft()
        if dist[k] >= band:
            continue
        for nb in ax_neighbors(*k):
            if nb in hexes:
                if nb not in dist:
                    dist[nb] = dist[k] + 1; votes[nb] = C(votes[k]); dq.append(nb)
                elif dist[nb] == dist[k] + 1:
                    votes[nb].update(votes[k])

    n = 0
    for k, d in sorted(dist.items()):
        h = hexes[k]
        c, r = local[k]
        if r < BARRIER_ICE_ROWS or h["hex_type"] in ("lake", "grania"):
            continue
        fam_n = votes[k].most_common(1)[0][0]
        # siła rampy: 1.0 na krawędzi → 0 na końcu pasa, ze strzępiącym szumem
        p = (band - d + 1) / band + 0.25 * (rng.random() - 0.5)
        cur = h["hex_type"]; new = None
        if fam_n == "MOUNTAIN":
            if BLEND_FAM.get(cur) == "MOUNTAIN":
                new = None                     # już górski (np. klin masywu) — nie rozcieńczaj
            elif d <= 2:
                new = "mountain" if rng.random() < 0.7 else "snow"
            elif d <= 4 and rng.random() < p:
                new = "mountain" if rng.random() < 0.35 else "hills"
            elif d <= 6 and rng.random() < p:
                new = "hills"
        elif fam_n == "HILL":
            if d <= 3 and rng.random() < p:
                new = "hills"
        elif fam_n == "FOREST":
            if d <= 2:
                new = "czarny_las" if rng.random() < 0.35 else "las_iglasty"
            elif d <= 5 and rng.random() < p:
                new = "las_iglasty"
        elif fam_n == "OPEN":
            if d <= 2:
                # równiny/wrzos przy krawędzi; góry/las ustępują (zakaz MOUNTAIN↔OPEN)
                new = "plains" if rng.random() < 0.4 else "heath"
            elif d <= 5 and rng.random() < p:
                if cur in ("mountain", "snow"):
                    new = "hills"                  # pogórze mostkuje
                elif cur not in ("hills",):
                    new = "heath"
        elif fam_n == "WATER":
            # dolina przy wodzie sąsiada: nigdy góra/śnieg przy rzece/jeziorze (#1545)
            if d <= 2 and cur in ("mountain", "snow", "lodowiec"):
                new = "tundra"
        if new and new != cur:
            h["hex_type"] = new; n += 1

    # sprzątanie: żaden hex tła przy obcej wodzie nie może być górą/śniegiem
    for k in [k for k, d in dist.items() if d == 1]:
        if hexes[k]["hex_type"] in ("mountain", "snow", "lodowiec"):
            if any(BLEND_FAM.get(foreign[nb]) == "WATER"
                   for nb in ax_neighbors(*k) if nb in foreign):
                hexes[k]["hex_type"] = "tundra"; n += 1
    return n


def enforce_edge_compat(hexes, foreign):
    """Twardy strażnik #1545 na samej granicy: hex tła nie może tworzyć
    zakazanej pary z ŻADNYM obcym sąsiadem (sąsiadów NIE ruszamy — kanon
    Piotra). Retyp na pierwszy zgodny mostek: hills (uniwersalny) → tundra →
    heath. Wyjątek: grań bariery (rząd 0, kraniec świata) zostaje."""
    from border_reconcile import fam, is_harsh
    fixed, stuck = 0, []
    for _ in range(3):   # retyp może odsłonić kolejną parę — domknij iteracyjnie
        dirty = False
        for k in sorted(hexes):
            h = hexes[k]
            if h["hex_type"] in ("grania", "lake"):
                continue
            ffams = [fam(foreign[nb]) for nb in ax_neighbors(*k) if nb in foreign]
            if not ffams:
                continue
            if not any(is_harsh(fam(h["hex_type"]), f) for f in ffams):
                continue
            for cand in ("hills", "tundra", "heath"):
                if not any(is_harsh(fam(cand), f) for f in ffams):
                    h["hex_type"] = cand; fixed += 1; dirty = True
                    break
            else:
                stuck.append(k)
        if not dirty:
            break
    return fixed, stuck


def place_poi(hexes, local, cfg):
    """POI = nazwane landmarki (label + atmosphere, BEZ location_key)."""
    placed = []
    # mapowanie (col,row) → klucz axial
    by_local = {v: k for k, v in local.items()}
    for col, row, label, atm in cfg["poi"]:
        # nie stawiaj POI na barierze; zejdź niżej jeśli trzeba
        row = max(row, BARRIER_ICE_ROWS + 1)
        # najbliższy istniejący hex do (col,row), nie-jeziorny, bez label
        target = min(local, key=lambda k: (abs(local[k][0] - col) + abs(local[k][1] - row)))
        cand = [k for k in hexes
                if hexes[k]["hex_type"] not in ("lake", "grania")
                and not hexes[k].get("label")]
        pos = min(cand, key=lambda k: (ax_dist(k, target), k)) if cand else target
        hexes[pos]["label"] = label
        hexes[pos]["atmosphere"] = atm
        placed.append((label, pos))
    return placed


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
    ap.add_argument("--slot", choices=list(SLOTS), required=True)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--png", default=None)
    args = ap.parse_args()

    cfg = SLOTS[args.slot]
    region = cfg["region"]
    seed = args.seed if args.seed is not None else cfg["seed"]
    rng = random.Random(seed)

    hexes, local, (q_off, r_off) = build_grid(region)
    print(f"[{args.slot.upper()}] {cfg['label']} — siatka {W}×{H}={len(hexes)}, "
          f"offset ({q_off},{r_off}), ziarno={seed}")

    print("[1] wnętrze: tundra-dominant + tajga/wzgórza/góry/śnieg")
    paint_interior(hexes, local, rng)

    foreign = load_foreign(region)

    print("[1b] pas gór na północy (klin od masywu Grań, kotwiczony w danych)")
    paint_north_range(hexes, local, cfg, rng, foreign)

    print("[2] jeziora (z dala od gór — #1545)")
    lakes = carve_lakes(hexes, local, rng)
    print(f"  jeziora: {len(lakes)} hexów")

    print("[3] blend do sąsiadów (data-driven z kanonu, pas %d hexów)" % BLEND_BAND)
    n_blend = blend_to_neighbors(hexes, local, rng, foreign)
    print(f"  przemalowane: {n_blend} hexów")
    # blend mógł postawić górę przy naszym jeziorze — pogórze mostkuje (#1545)
    for k in list(hexes):
        if hexes[k]["hex_type"] == "mountain" and any(
                hexes[nb]["hex_type"] == "lake"
                for nb in ax_neighbors(*k) if nb in hexes):
            hexes[k]["hex_type"] = "hills"

    print("[4] bariera północna: grań (nieprzechodnia) + lodowiec/śnieg")
    n_bar = paint_barrier(hexes, local, rng)
    print(f"  bariera: {n_bar} hexów")

    print("[4b] strażnik krawędzi: zero zakazanych par z obcymi sąsiadami")
    n_fix, stuck = enforce_edge_compat(hexes, foreign)
    print(f"  domknięte: {n_fix}; nierozwiązywalne: {len(stuck)} {stuck[:5]}")

    print("[5] POI (label-only)")
    poi = place_poi(hexes, local, cfg)
    for label, pos in poi:
        print(f"  {label}: {pos}")

    # walidacja #1545: żadne jezioro nie sąsiaduje z górami
    bad = [k for k in hexes if hexes[k]["hex_type"] == "lake"
           and any(hexes[nb]["hex_type"] == "mountain"
                   for nb in ax_neighbors(*k) if nb in hexes)]
    assert not bad, f"#1545 złamane: jezioro obok gór przy {bad[:5]}"
    print(f"  #1545 OK: 0 jezior przy górach")

    table = dist_table(hexes)
    print("\n[6] rozkład hex_type:\n")
    print(table)

    if not args.no_png:
        png = args.png or f"docs/world/previews/{region}.png"
        p = save_png(hexes, f"TŁO — {cfg['label'].upper()} (#1549)",
                     f"terra incognita: bariera lodu (N) + bogate wnętrze + POI; "
                     f"seed={seed} — nieprzechodnie, bez FOW — DB NIE RUSZANA",
                     ROOT / png)
        print(f"\nPNG: {p.relative_to(ROOT)}")

    if args.dry_run:
        print("\n--dry-run: JSON NIE zapisany")
        return

    q_vals = [k[0] for k in hexes]
    r_vals = [k[1] for k in hexes]
    out = {
        "region": region,
        "label": cfg["label"],
        "status": "background",
        "w": W, "h": H,
        "q_offset": q_off, "r_offset": r_off,
        "bounds": {"q_min": min(q_vals), "q_max": max(q_vals),
                   "r_min": min(r_vals), "r_max": max(r_vals)},
        "terrain_plan_seed": seed,
        "note": (f"Ziemie Północy — slot tła {args.slot.upper()} (#1549): terra incognita, "
                 f"NIE kraina z rosteru. Bariera lodu (grań nieprzechodnia + lodowiec/śnieg) "
                 f"tylko od góry; bogate wnętrze (tundra/tajga/góry/wzgórza), jeziora z dala "
                 f"od gór (#1545); gradienty do Grań (pogórze) i na południe. POI label-only "
                 f"(Kronika: białe plamy z nazwą). world_regions status 'locked' — "
                 f"nieprzechodnie, rysowane bez FOW. DB NIE RUSZANA — seed: "
                 f"scripts/seed_world_map.py --region {region}."),
        "hexes": [hexes[k] for k in sorted(hexes)],
    }
    path = ROOT / "data" / "regions" / f"region_{region}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {path.relative_to(ROOT)} ({len(out['hexes'])} hexów)")


if __name__ == "__main__":
    main()
