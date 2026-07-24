#!/usr/bin/env python3
"""Generator map per-kraina dla FAZY RM (#917).

--region <key>  : siwe_granie / czarnobor / koronne_niziny / wybrzeze_lez / martwe_pustkowia
                  lub 'all' dla wszystkich 5 krain naraz
--seed N        : nadpisz domyślny seed krainy

Wyjście:
  data/regions/region_<key>.json  — heksy ABSOLUTNE koordynaty axial (status=coming)
  temp-img/region_<key>.png       — podgląd do akceptacji wizualnej Piotra

Kresy (region_kresy.json) generuje generate_kresy_map.py — nie duplikujemy tu.
"""
import argparse, json, math, random, heapq
from pathlib import Path

from region_blocks import REGION_OFFSETS, W, H  # #1542 — wzór bloków (JEDNO źródło)

ROOT = Path(__file__).resolve().parent.parent

# ── PALETA (zgodna z map.js / world_hexes) ──────────────────────────────────
COLORS = {
    "water":   (40, 78, 110), "coast": (74, 120, 150), "swamp": (74, 86, 64),
    "plains":  (150, 156, 92), "hills": (138, 122, 74), "mountain": (110, 104, 96),
    "forest":  (60, 92, 64),   "river": (66, 120, 158), "road": (150, 116, 64),
    "ruins":   (120, 96, 70),  "city": (210, 180, 90),  "town": (200, 160, 70),
    "village": (196, 150, 80), "snow": (210, 214, 220), "bridge": (180, 130, 70),
    "sea": (30, 60, 100), "lake": (62, 108, 150), "tundra": (158, 166, 148),
    "heath": (140, 110, 116),
}

ENCOUNTER_CHANCE = {
    "ruins": 0.55, "forest": 0.25, "swamp": 0.30, "mountain": 0.20, "snow": 0.20,
    "tundra": 0.18, "hills": 0.15, "heath": 0.15, "coast": 0.12, "plains": 0.10,
    "river": 0.12, "lake": 0.08, "sea": 0.0, "water": 0.0,
    "city": 0.0, "town": 0.0, "village": 0.0, "road": 0.05, "bridge": 0.40,
}

# ── UKŁAD KONTYNENTU — absolutne offsety axial (q_off, r_off) ───────────────
# Absolutny axial: q = local_col + q_off
#                  r = (local_row - (local_col - local_col%2)//2) + r_off
# Offsety NIE są już hardkodowane tutaj — pochodzą z jednego źródła prawdy
# `scripts/region_blocks.py` (wzór q_off=50·col, r_off=75·row−25·col; #1542).
# Wynik jest identyczny co dawny literał (Kresy 0/0, Czarnobór 50/−25 wg CB-4);
# strażnik `test_1542_region_blocks.py` pilnuje, by generator i wzór się zgadzały.
# REGION_OFFSETS importowane wyżej z region_blocks.

# ── KONFIGURACJA KRAIN ───────────────────────────────────────────────────────
REGION_CONFIG = {
    "siwe_granie": {
        "label": "Siwe Granie",
        "status": "coming",
        "seed": 2001,
        "note": "Północne góry krasnoludzkie. Generacja RM5 (FAZA RM). Status: coming — pilot RM7.",
        # (src_region, label) dla każdej krawędzi: north/south/east/west
        "neighbors": {
            "south": ("kresy", "ku Kresom"),
        },
        # (key, label, hex_type, tx 0-1, ty 0-1, prefer_types)
        "settlements": [
            ("kopalnia_hutmana",     "Kopalnia Czarnego Hutmana", "ruins",   0.58, 0.82, ("mountain","hills")),
            ("krzyz_gor",            "Krzyż Gór",                 "ruins",   0.32, 0.48, ("mountain","snow")),
            ("tron_bialej_bogini",   "Tron Białej Bogini",        "ruins",   0.68, 0.28, ("snow","mountain")),
            ("czarne_skaly",         "Czarne Skały",              "ruins",   0.78, 0.58, ("mountain","hills")),
            ("lodowy_pas",           "Lodowy Pas",                "village", 0.20, 0.72, ("tundra","hills")),
            ("gorska_straznica",     "Górska Strażnica",          "village", 0.45, 0.92, ("hills","tundra")),
        ],
        "atm": {
            "kopalnia_hutmana":    "Opuszczona kopalnia. Krasnoludy odeszły 20 lat temu — w głębi coś nadal stuka.",
            "krzyz_gor":           "Najwyższe pasmo Siwych Grani. Wiatr wyje bez przerwy.",
            "tron_bialej_bogini":  "Lodowy tron w masywie. Miejscowe legendy mówią o śpiącej bogini.",
        },
    },
    "czarnobor": {
        "label": "Czarnobór",
        "status": "coming",
        "seed": 1337,
        "note": "Mroczny las i bagna. Generacja RM5 (FAZA RM). Status: coming.",
        "neighbors": {
            "west":  ("kresy", "ku Kresom"),
            "south": ("martwe_pustkowia", "ku Martwym Pustkowiu"),
        },
        "settlements": [
            ("bor_zmarlych",      "Bór Zmarłych",            "ruins",   0.38, 0.35, ("forest",)),
            ("bagienna_knieja",   "Bagienna Knieja",         "village", 0.62, 0.65, ("swamp","forest")),
            ("trzesawiska_mgl",   "Trzęsawiska Mgieł",       "ruins",   0.42, 0.80, ("swamp",)),
            ("step_wilkow",       "Step Wilków",              "ruins",   0.75, 0.22, ("forest","plains")),
            ("knieja_czarnych",   "Knieja Czarnych Drzew",   "ruins",   0.22, 0.52, ("forest","swamp")),
            ("ostep_graniczny",   "Ostęp Graniczny",          "village", 0.50, 0.92, ("forest",)),
        ],
        "atm": {
            "bor_zmarlych":    "Pnie czarne jak smoła, żadne ptaki nie śpiewają. Cień porusza się wbrew wiatrowi.",
            "bagienna_knieja": "Gęsta mgła nie opada nawet w południe. Ziemia ssie buty przy każdym kroku.",
            "trzesawiska_mgl": "Mgła pożera wędrowców. Utopce wołają głosami umarłych znajomych.",
        },
    },
    "koronne_niziny": {
        "label": "Koronne Niziny",
        "status": "coming",
        "seed": 1612,
        "note": "Serce cywilizacji — równiny, miasta i trakty. Generacja RM5 (FAZA RM). Status: coming.",
        "neighbors": {
            "east":  ("kresy", "ku Kresom"),
            "south": ("wybrzeze_lez", "ku Wybrzeżu Łez"),
        },
        "settlements": [
            ("vilnograd",       "Vilnograd",            "city",    0.50, 0.42, ("plains",)),
            ("volhynia",        "Volhynia",             "town",    0.72, 0.28, ("plains",)),
            ("klasztor_iskry",  "Klasztor Iskry",       "village", 0.28, 0.30, ("plains","hills")),
            ("wielkie_targi",   "Wielkie Targi",        "town",    0.60, 0.58, ("plains",)),
            ("kasztel_rycerski","Kasztel Rycerski",     "town",    0.38, 0.70, ("hills","plains")),
            ("przeprawa_krol",  "Przeprawa Królewska",  "village", 0.55, 0.82, ("plains","coast")),
            ("zachodnia_straz", "Zachodnia Straż",      "town",    0.14, 0.50, ("plains","hills")),
            ("nowe_dobra",      "Nowe Dobra",           "village", 0.82, 0.65, ("plains",)),
            ("osada_kupiecka",  "Osada Kupiecka",       "village", 0.44, 0.18, ("plains",)),
        ],
        "atm": {
            "vilnograd":       "Stolica Korony. Gildie, świątynia Światła, dzielnica złodziei. I cień Rady Czterech.",
            "volhynia":        "Skrzyżowanie czterech traktów. Handel, plotki i kupcy z całego świata.",
            "klasztor_iskry":  "Centrum wiary w Światło. Brat Kazimierz leczy, Brat Tomasz zbiera relikwie.",
        },
    },
    "wybrzeze_lez": {
        "label": "Wybrzeże Łez",
        "status": "coming",
        "seed": 1588,
        "note": "Mroczne wybrzeże z piratami i tajemnicami morza. Generacja RM5 (FAZA RM). Status: coming.",
        "neighbors": {
            "north": ("koronne_niziny", "ku Koronnym Nizinom"),
        },
        "settlements": [
            ("czarnograd",         "Czarnogród",           "town",    0.68, 0.28, ("coast","plains")),
            ("zatoka_topielcow",   "Zatoka Topielców",     "town",    0.45, 0.52, ("coast","swamp")),
            ("wybrzeze_lez_port",  "Port Łez",             "village", 0.25, 0.40, ("coast",)),
            ("przystan_piratow",   "Przystań Piratów",     "village", 0.80, 0.58, ("coast",)),
            ("mokradla_solne",     "Mokradła Solne",       "ruins",   0.35, 0.78, ("swamp",)),
        ],
        "atm": {
            "czarnograd":       "Smolisty port bez pytań. Kontrabanda, morderstwa na zamówienie, najemnicy.",
            "zatoka_topielcow": "Pirackie miasto bez prawa. Szubienica pełna, ale morze strzela wyżej niż prawo.",
            "mokradla_solne":   "Biała sól i czarna woda. Coś dużego porusza się pod powierzchnią.",
        },
    },
    "martwe_pustkowia": {
        "label": "Martwe Pustkowia",
        "status": "coming",
        "seed": 666,
        "note": "Pustkowie ruin Pradawnych — Rdzeń blisko powierzchni. Generacja RM5 (FAZA RM). Status: coming.",
        "neighbors": {
            "north": ("czarnobor", "ku Czarnoborowi"),
            "west":  ("kresy", "ku Kresom"),
        },
        "settlements": [
            ("pustkowie_solne",      "Pustkowie Solne",            "ruins", 0.35, 0.45, ("heath","tundra")),
            ("swiatynia_pradawnych", "Świątynia Pradawnych",       "ruins", 0.60, 0.30, ("heath","ruins")),
            ("klasztor_pradawny",    "Ruiny Pradawnego Klasztoru", "ruins", 0.25, 0.65, ("heath",)),
            ("krypta_hrabiego",      "Krypta Krwawego Hrabiego",   "ruins", 0.72, 0.62, ("heath","ruins")),
            ("twierdza_bezimiennego","Twierdza Bezimiennego",      "ruins", 0.50, 0.80, ("ruins","heath")),
        ],
        "atm": {
            "swiatynia_pradawnych":  "Wnętrze martwego boga. Pęknięcie nad samym Rdzeniem. Nikt nie wraca do środka.",
            "krypta_hrabiego":       "Wampir śpi tu od wieków. Nocą drzwi otwierają się od środka.",
            "twierdza_bezimiennego": "Nikt nie wrócił. Nikt.",
        },
    },
}

# ── POMOCNICY SIATKI (identyczne co generate_kresy_map.py) ──────────────────
_AX_DIRS = [(1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)]

def off2ax(col, row):
    return (col, row - (col - (col & 1)) // 2)

def ax2off(q, r):
    return (q, r + (q - (q & 1)) // 2)

def neighbors(col, row):
    q, r = off2ax(col, row)
    out = []
    for dq, dr in _AX_DIRS:
        nc, nr = ax2off(q+dq, r+dr)
        if 0 <= nc < W and 0 <= nr < H:
            out.append((nc, nr))
    return out

def axial_dist(a, b):
    return (abs(a[0]-b[0]) + abs(a[1]-b[1])) / 1.5

def smooth(grid, passes=3):
    for _ in range(passes):
        ng = [[0.0]*W for _ in range(H)]
        for r in range(H):
            for q in range(W):
                s = c = 0
                for dr in (-1, 0, 1):
                    for dq in (-1, 0, 1):
                        rr, qq = r+dr, q+dq
                        if 0 <= rr < H and 0 <= qq < W:
                            s += grid[rr][qq]; c += 1
                ng[r][q] = s / c
        grid = ng
    return grid

def gen_field(rng):
    g = [[rng.random() for _ in range(W)] for _ in range(H)]
    return smooth(g, 4)

# ── GRADIENTY PER KRAINA ─────────────────────────────────────────────────────
def apply_gradients(region_key, elev, moist, var, rng):
    if region_key == "siwe_granie":
        for r in range(H):
            for q in range(W):
                ny = r / (H-1); nx = q / (W-1)
                # Silnie górski: północ = szczyty (snow), południe = przedgórze (tundra/hills)
                north_peak = (1.0 - ny) ** 1.2
                elev[r][q] = elev[r][q]*0.20 + 0.58 + north_peak*0.28 - ny*0.10
                moist[r][q] = moist[r][q]*0.22 + 0.12 + nx*0.06
    elif region_key == "czarnobor":
        for r in range(H):
            for q in range(W):
                ny = r / (H-1); nx = q / (W-1)
                # Nizinny, wilgotny; bagna w południowych zagłębieniach
                elev[r][q] = elev[r][q]*0.50 + 0.18 + (1.0-ny)*0.12
                # moist niższy bazowo, żeby nie utonąć w lesie wszędzie
                moist[r][q] = moist[r][q]*0.50 + 0.25 + nx*0.12
    elif region_key == "koronne_niziny":
        for r in range(H):
            for q in range(W):
                ny = r / (H-1); nx = q / (W-1)
                swdist = math.hypot(nx - 0.5, ny - 1.0)
                sea = max(0.0, 0.16 - swdist)
                elev[r][q] = elev[r][q]*0.38 + 0.40 + (1.0-ny)*0.04 - sea*1.0
                moist[r][q] = moist[r][q]*0.42 + 0.28 + sea*0.30
    elif region_key == "wybrzeze_lez":
        for r in range(H):
            for q in range(W):
                ny = r / (H-1); nx = q / (W-1)
                sea_s = ny ** 1.1
                sea_w = max(0.0, (1.0-nx)**1.5 - 0.25)
                elev[r][q] = elev[r][q]*0.28 + 0.55 - sea_s*0.50 - sea_w*0.18
                moist[r][q] = moist[r][q]*0.28 + 0.20 + sea_s*0.55 + sea_w*0.30
    elif region_key == "martwe_pustkowia":
        for r in range(H):
            for q in range(W):
                ny = r / (H-1); nx = q / (W-1)
                # Nizkie, płaskie i suche — heath dominuje
                elev[r][q] = elev[r][q]*0.32 + 0.28 + (1.0-ny)*0.05
                moist[r][q] = moist[r][q]*0.18 + 0.05  # bardzo suche

# ── KLASYFIKACJA BIOMU PER KRAINA ───────────────────────────────────────────
def make_classifier(region_key):
    if region_key == "siwe_granie":
        def classify(e, m, v):
            if e > 0.84: return "snow"
            if e > 0.74: return "mountain"
            if e > 0.62: return "snow" if v < 0.35 else "mountain"
            if e > 0.52: return "tundra"
            if e > 0.42: return "hills"
            if m > 0.55 and e < 0.36: return "lake"
            if v < 0.28: return "tundra"
            return "hills"
    elif region_key == "czarnobor":
        def classify(e, m, v):
            if e < 0.10: return "lake"
            if e < 0.25: return "swamp"
            if e < 0.36 and m > 0.55: return "swamp"
            if e > 0.68: return "hills"
            if m > 0.60: return "forest"
            if v > 0.55: return "forest"
            if v < 0.28 and e < 0.50: return "swamp"
            return "forest"
    elif region_key == "koronne_niziny":
        def classify(e, m, v):
            if e < 0.12: return "sea"
            if e < 0.19: return "coast" if m < 0.5 else "swamp"
            if e > 0.76: return "mountain"
            if e > 0.63: return "hills"
            if m > 0.72: return "forest" if e > 0.38 else "swamp"
            if v > 0.73: return "forest"
            if v < 0.24: return "heath"
            return "plains"
    elif region_key == "wybrzeze_lez":
        def classify(e, m, v):
            if e < 0.16: return "sea"
            if e < 0.25: return "coast"
            if e < 0.36: return "coast" if m < 0.52 else "swamp"
            if m > 0.65 and e < 0.48: return "swamp"
            if m > 0.55: return "forest"
            if e > 0.66: return "hills"
            if v < 0.28: return "swamp"
            return "plains"
    elif region_key == "martwe_pustkowia":
        def classify(e, m, v):
            if e < 0.10: return "lake"
            if e > 0.78: return "mountain"
            if e > 0.66: return "hills"
            if v > 0.70: return "ruins"
            if v < 0.28: return "tundra"
            return "heath"
    else:
        raise ValueError(f"Unknown region: {region_key}")
    return classify

# ── RZEKI ────────────────────────────────────────────────────────────────────
def gen_rivers(hexes, elev, rng, n_rivers=5, prefer_south=False):
    """Rzeki od gór/wysokich terenów ku nizinom/wodzie."""
    sw_corner = (0, H-1) if prefer_south else (W//2, H-1)
    mountains = [(q, r) for (q, r) in hexes if hexes[(q,r)]["hex_type"] in ("mountain","snow","hills")]
    rng.shuffle(mountains)
    river_hexes = set()
    main_path = []
    for src in mountains[:n_rivers]:
        cur = src; path = []; steps = 0; visited = {cur}
        while steps < 250:
            steps += 1
            nbrs = [n for n in neighbors(*cur) if n not in visited]
            if not nbrs: break
            cur_e = elev[cur[1]][cur[0]]
            lower = min(nbrs, key=lambda n: elev[n[1]][n[0]])
            if elev[lower[1]][lower[0]] >= cur_e:
                lower = min(nbrs, key=lambda n: axial_dist(n, sw_corner))
            t = hexes[lower]["hex_type"]
            if t in ("sea","lake"):
                path.append(lower); break
            if t not in ("mountain","snow","city","town","village"):
                hexes[lower]["hex_type"] = "river"; river_hexes.add(lower)
            visited.add(lower); path.append(lower); cur = lower
        if path:
            end = path[-1]
            if hexes[end]["hex_type"] not in ("sea","lake"):
                hexes[end]["hex_type"] = "lake"
                for nb in neighbors(*end):
                    if hexes[nb]["hex_type"] == "river" and rng.random() < 0.45:
                        hexes[nb]["hex_type"] = "lake"
        if len(path) > len(main_path):
            main_path = path
    return river_hexes, main_path

# ── OSADY I DROGI ────────────────────────────────────────────────────────────
ROAD_COST = {
    "plains":1,"hills":3,"forest":4,"coast":3,"swamp":7,"river":8,
    "mountain":20,"snow":25,"water":999,"sea":999,"lake":999,
    "tundra":6,"heath":2,"road":1,"ruins":3,
    "city":1,"town":1,"village":1,
}

def astar(hexes, start, goal):
    pq = [(0, start)]; came = {start: None}; g = {start: 0}
    while pq:
        _, cur = heapq.heappop(pq)
        if cur == goal: break
        for n in neighbors(*cur):
            c = ROAD_COST.get(hexes[n]["hex_type"], 5)
            ng = g[cur] + c
            if n not in g or ng < g[n]:
                g[n] = ng
                heapq.heappush(pq, (ng + axial_dist(n, goal), n))
                came[n] = cur
    if goal not in came: return []
    path = []; c = goal
    while c is not None: path.append(c); c = came[c]
    return path[::-1]

def place_settlements(hexes, elev, settlements, rng):
    placed = {}; used = set()
    no_settle = ("water","sea","lake","river","mountain","snow")
    def best_hex(tx, ty, prefer):
        cx, cy = tx*(W-1), ty*(H-1)
        cand = []
        for (q, r), h in hexes.items():
            if (q,r) in used: continue
            if h["hex_type"] in no_settle: continue
            near = min((math.hypot(q-uq, r-ur) for (uq,ur) in used), default=99)
            if near < 3: continue
            d = math.hypot(q-cx, r-cy)
            pref = 0 if h["hex_type"] in prefer else 5
            cand.append((d+pref, (q,r)))
        cand.sort()
        return cand[0][1] if cand else None
    for key, name, typ, tx, ty, prefer in settlements:
        pos = best_hex(tx, ty, prefer)
        if pos is None: continue
        used.add(pos)
        hexes[pos]["hex_type"] = typ
        hexes[pos]["label"] = name
        hexes[pos]["location_key"] = key
        placed[key] = pos
    return placed

def gen_roads(hexes, placed, rng):
    pts = list(placed.values())
    if len(pts) < 2: return []
    in_tree = {pts[0]}; edges = []
    while len(in_tree) < len(pts):
        best = None
        for a in in_tree:
            for b in pts:
                if b in in_tree: continue
                d = axial_dist(a, b)
                if best is None or d < best[0]: best = (d, a, b)
        _, a, b = best; edges.append((a,b)); in_tree.add(b)
    bridges = []
    bridge_names = ["Most Graniczny","Most na Rzece","Stary Most","Most Wschodni","Most Zachodni"]
    for a, b in edges:
        for hx in astar(hexes, a, b):
            t = hexes[hx]["hex_type"]
            if t == "river":
                nm = bridge_names[len(bridges) % len(bridge_names)]
                hexes[hx]["hex_type"] = "bridge"
                hexes[hx]["label"] = hexes[hx]["label"] or nm
                hexes[hx]["location_key"] = hexes[hx]["location_key"] or f"most_{len(bridges)+1}"
                hexes[hx]["encounter_chance"] = 0.40
                bridges.append(hx)
            elif t in ("plains","hills","forest","coast","swamp","heath","tundra"):
                hexes[hx]["hex_type"] = "road"
    return bridges

# ── ETYKIETY GRANIC ──────────────────────────────────────────────────────────
def add_border_labels(hexes, neighbors_cfg):
    """Dodaj 'ku <Krainie>' na heksach przy granicy z inną krainą."""
    for edge, (_, label) in neighbors_cfg.items():
        if edge == "south":
            border_cells = [(q, H-1) for q in range(0, W, 3)]
        elif edge == "north":
            border_cells = [(q, 0) for q in range(0, W, 3)]
        elif edge == "east":
            border_cells = [(W-1, r) for r in range(0, H, 3)]
        elif edge == "west":
            border_cells = [(0, r) for r in range(0, H, 3)]
        else:
            continue
        for pos in border_cells:
            if pos in hexes and hexes[pos]["label"] is None:
                hexes[pos]["label"] = label

# ── PNG PODGLĄD ───────────────────────────────────────────────────────────────
def save_png(region_key, region_label, hexes, placed, out_path):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("PIL brak — pomijam PNG; JSON zapisany."); return
    S = 14
    hw = S * math.sqrt(3); vh = S * 1.5
    legend_h = 110
    img_w = int(hw * (W + 1)); img_h = int(vh * H + S + legend_h)
    im = Image.new("RGB", (img_w, img_h), (10, 9, 8))
    dr = ImageDraw.Draw(im)
    def font(sz):
        for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
        return ImageFont.load_default()
    f_lbl = font(11); f_leg = font(11); f_title = font(18)
    def center(q, r):
        return hw * (q + 0.5 + (0.5 if r % 2 else 0)) + 4, vh * r + S + 4
    for (q, r), h in hexes.items():
        cx, cy = center(q, r)
        poly = [(cx + S*math.sin(math.pi/3*i), cy + S*math.cos(math.pi/3*i)) for i in range(6)]
        dr.polygon(poly, fill=COLORS.get(h["hex_type"], (80,80,80)), outline=(22,20,16))
    def text_w(s, fnt):
        try: return dr.textlength(s, font=fnt)
        except Exception: return len(s)*6
    for k, p in placed.items():
        cx, cy = center(*p)
        lab = hexes[p]["label"] or ""
        dr.ellipse([cx-4, cy-4, cx+4, cy+4], fill=(245,225,150), outline=(20,18,15))
        tw = text_w(lab, f_lbl); tx = cx + 7; ty = cy - 6
        if tx + tw > img_w - 4: tx = cx - 7 - tw
        dr.rectangle([tx-2, ty-1, tx+tw+2, ty+13], fill=(10,9,8))
        dr.text((tx, ty), lab, fill=(240,222,150), font=f_lbl)
    ly = int(vh * H + S + 6)
    dr.text((10, ly), f"{region_label.upper()} — mapa krainy (RM5, status: coming)", fill=(180,150,70), font=f_title)
    types_shown = set(h["hex_type"] for h in hexes.values())
    items = [(t, t) for t in sorted(types_shown) if t in COLORS]
    lx = 10; lyy = ly + 32; col_w = 160
    for i, (t, name) in enumerate(items[:16]):
        cxx = lx + (i % 8) * col_w; cyy = lyy + (i // 8) * 28
        dr.rectangle([cxx, cyy, cxx+18, cyy+14], fill=COLORS.get(t,(80,80,80)), outline=(40,36,28))
        dr.text((cxx+24, cyy+1), name, fill=(200,190,170), font=f_leg)
    im.save(out_path)
    print(f"  PNG: {out_path}")

# ── GENERACJA JEDNEJ KRAINY ──────────────────────────────────────────────────
def generate(region_key, seed_override=None):
    cfg = REGION_CONFIG[region_key]
    seed = seed_override if seed_override is not None else cfg["seed"]
    rng = random.Random(seed)

    elev = gen_field(rng)
    moist = gen_field(rng)
    var = smooth([[rng.random() for _ in range(W)] for _ in range(H)], 1)
    vlo = min(min(row) for row in var); vhi = max(max(row) for row in var)
    if vhi > vlo:
        var = [[(v-vlo)/(vhi-vlo) for v in row] for row in var]

    apply_gradients(region_key, elev, moist, var, rng)
    classify = make_classifier(region_key)

    q_off, r_off = REGION_OFFSETS[region_key]

    hexes = {}
    for r in range(H):
        for q in range(W):
            hexes[(q, r)] = {
                "q": q, "r": r,
                "hex_type": classify(elev[r][q], moist[r][q], var[r][q]),
                "label": None, "location_key": None,
                "encounter_chance": 0.15, "atmosphere": None
            }

    # rzeki (pomiń w pustkowiach — suche)
    if region_key != "martwe_pustkowia":
        n_riv = {"siwe_granie": 3, "czarnobor": 3, "koronne_niziny": 3, "wybrzeze_lez": 2}.get(region_key, 3)
        prefer_s = region_key in ("siwe_granie", "koronne_niziny")
        gen_rivers(hexes, elev, rng, n_rivers=n_riv, prefer_south=prefer_s)

    # jeziora śródlądowe
    low = sorted([(q, r) for (q,r), h in hexes.items()
                  if h["hex_type"] in ("plains","heath","swamp","tundra")],
                 key=lambda p: elev[p[1]][p[0]])
    lake_seeds = []
    for p in low:
        if elev[p[1]][p[0]] > 0.30: break
        if all(axial_dist(p, s) > 10 for s in lake_seeds):
            lake_seeds.append(p)
        if len(lake_seeds) >= 2: break
    for s in lake_seeds:
        if hexes[s]["hex_type"] in ("sea",): continue
        hexes[s]["hex_type"] = "lake"
        for nb in neighbors(*s):
            if hexes[nb]["hex_type"] in ("plains","heath","swamp","tundra") and rng.random() < 0.55:
                hexes[nb]["hex_type"] = "lake"

    placed = place_settlements(hexes, elev, cfg["settlements"], rng)

    # drogi tylko tam gdzie sens
    if region_key not in ("martwe_pustkowia",):
        gen_roads(hexes, placed, rng)

    add_border_labels(hexes, cfg.get("neighbors", {}))

    # atmosfera dla kluczowych lokacji
    atm_map = cfg.get("atm", {})
    for key, pos in placed.items():
        if key in atm_map:
            hexes[pos]["atmosphere"] = atm_map[key]

    # encounter_chance per biom
    for h in hexes.values():
        if h["hex_type"] in ENCOUNTER_CHANCE and h["hex_type"] not in ("city","town","village","road","bridge"):
            h["encounter_chance"] = ENCOUNTER_CHANCE[h["hex_type"]]

    # ── EKSPORT axial z offsetem ─────────────────────────────────────────────
    def ax_hex(h):
        aq, ar = off2ax(h["q"], h["r"])
        return {
            "q":  aq + q_off,
            "r":  ar + r_off,
            "hex_type": h["hex_type"],
            "label": h["label"],
            "location_key": h["location_key"],
            "encounter_chance": h["encounter_chance"],
            "atmosphere": h["atmosphere"],
        }

    hex_list = [ax_hex(h) for h in hexes.values()]
    q_vals = [h["q"] for h in hex_list]; r_vals = [h["r"] for h in hex_list]
    out = {
        "region": region_key,
        "label":  cfg["label"],
        "status": cfg["status"],
        "w": W, "h": H,
        "q_offset": q_off, "r_offset": r_off,
        "bounds": {"q_min": min(q_vals), "q_max": max(q_vals),
                   "r_min": min(r_vals), "r_max": max(r_vals)},
        "note": cfg["note"],
        "hexes": hex_list,
    }

    out_dir = ROOT / "data" / "regions"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"region_{region_key}.json"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  JSON: {json_path} ({len(hex_list)} heksów)")

    # PNG
    png_dir = ROOT / "temp-img"
    png_dir.mkdir(parents=True, exist_ok=True)
    save_png(region_key, cfg["label"], hexes, placed, png_dir / f"region_{region_key}.png")

    # statystyki
    counts = {}
    for h in hexes.values(): counts[h["hex_type"]] = counts.get(h["hex_type"],0) + 1
    print(f"  teren: {dict(sorted(counts.items(), key=lambda x:-x[1])[:8])}")
    print(f"  bounds: q={min(q_vals)}..{max(q_vals)}, r={min(r_vals)}..{max(r_vals)}")
    return out

# ── MAIN ─────────────────────────────────────────────────────────────────────
ALL_REGIONS = ["siwe_granie", "czarnobor", "koronne_niziny", "wybrzeze_lez", "martwe_pustkowia"]

def main():
    ap = argparse.ArgumentParser(description="Generacja mapy krainy (FAZA RM)")
    ap.add_argument("--region", required=True, help="klucz krainy lub 'all'")
    ap.add_argument("--seed", type=int, default=None, help="nadpisz seed (tylko dla jednej krainy)")
    args = ap.parse_args()

    targets = ALL_REGIONS if args.region == "all" else [args.region]
    if args.region != "all" and args.region not in REGION_CONFIG:
        ap.error(f"Nieznana kraina: {args.region}. Dostępne: {', '.join(ALL_REGIONS)}")

    for key in targets:
        print(f"\n=== {REGION_CONFIG[key]['label']} ({key}) ===")
        generate(key, seed_override=args.seed if args.region != "all" else None)

    print("\nGotowe. Wszystkie mapy mają status='coming' — RM7 odblokowuje pilota.")

if __name__ == "__main__":
    main()
