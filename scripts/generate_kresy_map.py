#!/usr/bin/env python3
"""Generator logicznej mapy 50x50 hex dla krainy KRESY (wstępna kraina gry).

NIE losowa: teren = seeded value-noise + gradienty regionalne (góry na płn = granica
Siwych Grani, las/bagno na wsch = granica Czarnoboru, woda w narożniku = ku Wybrzeżu,
rdzeń = równiny/wzgórza). Rzeki spływają z gór do wody/krawędzi. Drogi (trakt) łączą
osady przez A* po koszcie terenu, z mostem na rzece. Osady z lore gry sadzone na
pasujących heksach.

Wyjście:
  - docs/world/kresy_map.json   — dane zgodne z world_hexes (q,r,hex_type,label,location_key)
                                  do PRZYSZŁEGO importu do gry (teraz NIE importowane)
  - temp-img/kresy_map.png      — podgląd wizualny

Użycie: python3 scripts/generate_kresy_map.py [--seed 1984]
"""
import argparse, json, math, random, heapq
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W = H = 50

# paleta hex_type (zgodna z map.js / world_hexes) -> kolor podglądu
COLORS = {
    "water":   (40, 78, 110), "coast": (74, 120, 150), "swamp": (74, 86, 64),
    "plains":  (150, 156, 92), "hills": (138, 122, 74), "mountain": (110, 104, 96),
    "forest":  (60, 92, 64),   "river": (66, 120, 158), "road": (150, 116, 64),
    "ruins":   (120, 96, 70),  "city": (210, 180, 90),  "town": (200, 160, 70),
    "village": (196, 150, 80), "snow": (210, 214, 220), "bridge": (180, 130, 70),
    "sea": (40, 78, 110), "lake": (62, 108, 150), "tundra": (158, 166, 148),
    "heath": (140, 110, 116),
}

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

# Gra renderuje flat-top axial (x=1.5q, y=√3(q/2+r)). Generujemy na prostokącie
# (col,row), ale SĄSIEDZTWO liczymy w axialu gry (odd-q offset) — by rzeki/drogi
# były ciągłe i by eksport dał PROSTOKĄT, nie romb.
_AX_DIRS = [(1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)]
def off2ax(col, row): return (col, row - (col - (col & 1)) // 2)
def ax2off(q, r):     return (q, r + (q - (q & 1)) // 2)
def neighbors(col, row):
    q, r = off2ax(col, row)
    out = []
    for dq, dr in _AX_DIRS:
        nc, nr = ax2off(q+dq, r+dr)
        if 0 <= nc < W and 0 <= nr < H:
            out.append((nc, nr))
    return out

def axial_dist(a, b):
    # przybliżona odległość heksowa po offsetach (do A* heurystyki)
    return (abs(a[0]-b[0]) + abs(a[1]-b[1])) / 1.5

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1984)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    elev = gen_field(rng)
    moist = gen_field(rng)
    # pole wariacji (patchowe) — różnicuje równiny na zagajniki/wrzosowiska/pofalowania.
    # Normalizacja do 0..1, żeby progi patchy realnie strzelały.
    var = smooth([[rng.random() for _ in range(W)] for _ in range(H)], 1)
    vlo = min(min(row) for row in var); vhi = max(max(row) for row in var)
    if vhi > vlo:
        var = [[(v - vlo) / (vhi - vlo) for v in row] for row in var]

    # gradienty regionalne (Kresy = pogranicze): góry na płn (Siwe Granie),
    # las na wsch (Czarnobór), MAŁA zatoka morska w pd-zach (brak grywalności na morzu — walor wizualny).
    for r in range(H):
        for q in range(W):
            ny = r / (H-1); nx = q / (W-1)
            north = (1.0 - ny) ** 1.5
            swdist = math.hypot(nx - 0.0, ny - 1.0)
            sea = max(0.0, 0.24 - swdist)                   # MAŁA zatoka (było 0.40)
            east = nx ** 1.3
            elev[r][q] = elev[r][q]*0.44 + north*0.45 - ny*0.08 - sea*1.5
            if ny < 0.13:                                   # pasmo Siwych Grani (wąskie, strome)
                elev[r][q] += (0.13 - ny) * 2.8
            moist[r][q] = moist[r][q]*0.50 + east*0.40 + sea*0.35

    def classify(e, m, v):
        if e < 0.12: return "sea"                           # mała zatoka
        if e < 0.17: return "coast" if m < 0.5 else "swamp"
        if e > 0.86: return "snow"
        if e > 0.73: return "mountain"
        if e > 0.66: return "tundra"                        # zimne przedgórze pod Siwymi Graniami
        if e > 0.58: return "hills"
        if m > 0.64: return "swamp" if e < 0.34 else "forest"
        if m > 0.52: return "forest"
        if v > 0.70: return "forest"                        # zagajniki śród równin
        if v > 0.58 and e > 0.46: return "hills"            # pofalowania
        if v < 0.30: return "heath" if m < 0.5 else "swamp" # wrzosowiska / mokradła
        if v < 0.40 and m < 0.4: return "heath"
        return "plains"

    hexes = {}
    for r in range(H):
        for q in range(W):
            hexes[(q, r)] = {"q": q, "r": r, "hex_type": classify(elev[r][q], moist[r][q], var[r][q]),
                             "label": None, "location_key": None,
                             "encounter_chance": 0.15, "atmosphere": None}

    # ── RZEKI: źródła w górach, spływ DO MORZA (SW). Z lokalnego minimum uciekamy
    #    krokiem ku narożnikowi SW, więc rzeki zawsze docierają do wody. ──
    sw_corner = (0, H-1)
    mountains = [(q, r) for (q, r) in hexes if hexes[(q, r)]["hex_type"] in ("mountain", "snow")]
    rng.shuffle(mountains)
    river_hexes = set()
    main_river_path = []
    for si, src in enumerate(mountains[:8]):
        cur = src; path = []; steps = 0; visited = {cur}
        while steps < 300:
            steps += 1
            nbrs = [n for n in neighbors(*cur) if n not in visited]
            if not nbrs: break
            cur_e = elev[cur[1]][cur[0]]
            lower = min(nbrs, key=lambda n: elev[n[1]][n[0]])
            if elev[lower[1]][lower[0]] >= cur_e:           # lokalne minimum
                lower = min(nbrs, key=lambda n: axial_dist(n, sw_corner))  # uciekaj ku morzu
            t = hexes[lower]["hex_type"]
            if t in ("sea", "lake"):                         # dotarliśmy do wody
                path.append(lower); break
            if t not in ("mountain", "snow", "city", "town", "village"):
                hexes[lower]["hex_type"] = "river"; river_hexes.add(lower)
            visited.add(lower); path.append(lower); cur = lower
        # jeśli rzeka nie dotarła do morza — kończy małym jeziorem (river-fed)
        if path:
            end = path[-1]
            if hexes[end]["hex_type"] not in ("sea", "lake"):
                hexes[end]["hex_type"] = "lake"
                for nb in neighbors(*end):
                    if hexes[nb]["hex_type"] == "river" and rng.random() < 0.5:
                        hexes[nb]["hex_type"] = "lake"
        if len(path) > len(main_river_path):
            main_river_path = path

    # ── JEZIORA śródlądowe (walor wizualny) w nisko położonych zagłębieniach ──
    low = sorted([(q, r) for (q, r), h in hexes.items() if h["hex_type"] in ("plains", "heath", "swamp")],
                 key=lambda p: elev[p[1]][p[0]])
    lake_seeds = []
    for p in low:
        if elev[p[1]][p[0]] > 0.33: break
        if all(axial_dist(p, s) > 9 for s in lake_seeds):
            lake_seeds.append(p)
        if len(lake_seeds) >= 3: break
    for s in lake_seeds:
        hexes[s]["hex_type"] = "lake"
        for nb in neighbors(*s):
            if hexes[nb]["hex_type"] in ("plains", "heath", "swamp") and rng.random() < 0.6:
                hexes[nb]["hex_type"] = "lake"

    # ── OSADY: duży, zaludniony teren — miasta + gęsta sieć wsi/przysiółków,
    #    także na obrzeżach. Nazwy z lore gry + przysiółki dopełniające. ──
    settlements = [
        # lore (gra)
        ("warowny_straz", "Strażyn",                 "town",    0.70, 0.42, ("plains","hills")),
        ("vilnograd_targ","Targowa Wola",            "town",    0.30, 0.42, ("plains",)),
        ("pod_zlamanym_rogiem", "Pod Złamanym Rogiem","village", 0.50, 0.52, ("plains",)),
        ("brzezino",      "Brzezino",                 "village", 0.80, 0.58, ("plains","forest")),
        ("wolanka",       "Wolanka",                  "village", 0.42, 0.22, ("hills","plains")),
        ("cieszowice",    "Cieszowice",               "village", 0.24, 0.58, ("plains",)),
        ("karczma_kruki", "Karczma Pod Trzema Krukami","village",0.46, 0.70, ("plains",)),
        ("zgliszcza",     "Zgliszcza (zgliszcza)",    "ruins",   0.76, 0.74, ("plains","forest")),
        # przysiółki dopełniające teren (obrzeża + środek)
        ("debno",     "Dębno",      "village", 0.14, 0.30, ("plains","hills")),
        ("olszany",   "Olszany",    "village", 0.16, 0.74, ("plains",)),
        ("kamionka",  "Kamionka",   "village", 0.58, 0.18, ("hills","plains")),
        ("rudnik",    "Rudnik",     "village", 0.74, 0.22, ("hills","forest")),
        ("borowiec",  "Borowiec",   "village", 0.88, 0.44, ("forest","plains")),
        ("solanka",   "Solanka",    "village", 0.20, 0.88, ("coast","plains")),
        ("przewoz",   "Przewóz",    "village", 0.40, 0.84, ("plains","coast")),
        ("grabina",   "Grabina",    "village", 0.62, 0.62, ("plains","forest")),
        ("zalesie",   "Zalesie",    "village", 0.86, 0.70, ("forest",)),
        ("kobyla",    "Kobyla Łąka","village", 0.34, 0.34, ("plains",)),
    ]
    placed = {}
    used = set()
    def best_hex(tx, ty, prefer):
        cx, cy = tx*(W-1), ty*(H-1)
        cand = []
        for (q, r), h in hexes.items():
            if (q, r) in used: continue
            if h["hex_type"] in ("water","sea","lake","river","mountain","snow","tundra"): continue
            # odstęp od już postawionych osad — nie kupować się
            near = min((math.hypot(q-uq, r-ur) for (uq, ur) in used), default=99)
            if near < 4: continue
            d = math.hypot(q-cx, r-cy)
            pref = 0 if h["hex_type"] in prefer else 6
            cand.append((d+pref, (q, r)))
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

    # ── DROGI: trakt łączący osady (MST po A*) ──
    COST = {"plains":1,"hills":3,"forest":4,"coast":3,"swamp":7,"river":8,
            "mountain":20,"snow":25,"water":999,"sea":999,"lake":999,
            "tundra":6,"heath":2,"road":1,
            "city":1,"town":1,"village":1,"ruins":2}
    def astar(start, goal):
        pq = [(0, start)]; came = {start: None}; g = {start: 0}
        while pq:
            _, cur = heapq.heappop(pq)
            if cur == goal: break
            for n in neighbors(*cur):
                c = COST.get(hexes[n]["hex_type"], 5)
                ng = g[cur] + c
                if n not in g or ng < g[n]:
                    g[n] = ng
                    heapq.heappush(pq, (ng + axial_dist(n, goal), n))
                    came[n] = cur
        if goal not in came: return []
        path = []; c = goal
        while c is not None: path.append(c); c = came[c]
        return path[::-1]

    pts = list(placed.values())
    # MST (Prim) po realnych kosztach A* — trakt łączy wszystkie osady
    in_tree = {pts[0]}; edges = []
    while len(in_tree) < len(pts):
        best = None
        for a in in_tree:
            for b in pts:
                if b in in_tree: continue
                d = axial_dist(a, b)
                if best is None or d < best[0]: best = (d, a, b)
        _, a, b = best
        edges.append((a, b)); in_tree.add(b)

    # MOST (bridge): nowy teren tam, gdzie trakt krzyżuje rzekę — punkt myta/straży,
    # podwyższony encounter (strażnicy, pobór podatków).
    bridge_names = ["Most Czarnej Rzeki", "Stary Most", "Most Graniczny",
                    "Most Poborców", "Kamienny Most", "Most na Bystrzycy"]
    bridges = []
    for a, b in edges:
        for hx in astar(a, b):
            t = hexes[hx]["hex_type"]
            if t == "river":
                nm = bridge_names[len(bridges) % len(bridge_names)]
                hexes[hx]["hex_type"] = "bridge"
                hexes[hx]["label"] = hexes[hx]["label"] or nm
                hexes[hx]["location_key"] = hexes[hx]["location_key"] or ("most_%d" % (len(bridges)+1))
                hexes[hx]["encounter_chance"] = 0.45
                hexes[hx]["atmosphere"] = "Strażnicy mostu pobierają myto; podróżni czekają w kolejce, a poborca liczy monety."
                bridges.append(hx)
            elif t in ("plains","hills","forest","coast","swamp"):
                hexes[hx]["hex_type"] = "road"

    # etykiety granic regionów
    hexes[(W-1, 0)]["label"] = hexes[(W-1,0)]["label"] or "ku Czarnoborowi"
    hexes[(0, 0)]["label"] = hexes[(0,0)]["label"] or "ku Siwym Graniom"

    # ── EKSPORT JSON ──
    out = {"name": "Kresy", "seed": args.seed, "w": W, "h": H,
           "note": "Seed mapy do PRZYSZŁEGO importu do world_hexes; teraz nie importowane (backend gry pauzowany).",
           "hexes": [h for h in hexes.values() if h["hex_type"] != "plains" or h["label"]]
                    + [h for h in hexes.values() if h["hex_type"] == "plains" and not h["label"]],
           "settlements": [{"key": k, "q": off2ax(*p)[0], "r": off2ax(*p)[1], "label": hexes[p]["label"], "type": hexes[p]["hex_type"]} for k, p in placed.items()]}
    # pełny dump wszystkich heksów w AXIAL (gra renderuje flat-top axial -> prostokąt)
    def ax_hex(h):
        aq, ar = off2ax(h["q"], h["r"])
        return {**h, "q": aq, "r": ar}
    out["hexes"] = [ax_hex(h) for h in hexes.values()]
    (ROOT / "docs/world").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/world/kresy_map.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── PODGLĄD PNG (PIL) — z etykietami osad i legendą ──
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("PIL brak — pomijam PNG; JSON zapisany."); return
    S = 16  # rozmiar heksa
    hw = S * math.sqrt(3); vh = S * 1.5
    legend_h = 132
    img_w = int(hw * (W + 1)); img_h = int(vh * H + S + legend_h)
    im = Image.new("RGB", (img_w, img_h), (10, 9, 8)); dr = ImageDraw.Draw(im)
    def font(sz):
        for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
        return ImageFont.load_default()
    f_lbl = font(13); f_leg = font(13); f_title = font(22)
    def center(q, r):
        return hw * (q + 0.5 + (0.5 if r % 2 else 0)) + 4, vh * r + S + 4
    for (q, r), h in hexes.items():
        cx, cy = center(q, r)
        poly = [(cx + S*math.sin(math.pi/3*i), cy + S*math.cos(math.pi/3*i)) for i in range(6)]
        dr.polygon(poly, fill=COLORS.get(h["hex_type"], (80,80,80)), outline=(22,20,16))
    # osady: marker + etykieta z tłem
    def text_w(s, fnt):
        try: return dr.textlength(s, font=fnt)
        except Exception: return len(s)*7
    for k, p in placed.items():
        cx, cy = center(*p)
        lab = (hexes[p]["label"] or "").replace(" (zgliszcza)", "")
        dr.ellipse([cx-5, cy-5, cx+5, cy+5], fill=(245,225,150), outline=(20,18,15))
        tw = text_w(lab, f_lbl); tx = cx + 9; ty = cy - 7
        if tx + tw > img_w - 6: tx = cx - 9 - tw
        dr.rectangle([tx-3, ty-2, tx+tw+3, ty+15], fill=(10,9,8))
        dr.text((tx, ty), lab, fill=(240,222,150), font=f_lbl)
    # mosty: marker (kwadrat) + mała etykieta
    for hx in bridges:
        cx, cy = center(*hx)
        dr.rectangle([cx-4, cy-4, cx+4, cy+4], fill=(210,150,80), outline=(20,18,15))
        lab = hexes[hx]["label"] or "Most"
        tw = text_w(lab, f_lbl); tx = cx - tw/2; ty = cy + 9   # pod markerem (mniej kolizji)
        tx = max(4, min(tx, img_w - tw - 6))
        dr.rectangle([tx-3, ty-2, tx+tw+3, ty+15], fill=(10,9,8))
        dr.text((tx, ty), lab, fill=(225,180,120), font=f_lbl)
    # legenda
    ly = int(vh * H + S + 8)
    dr.text((10, ly-2), "KRESY — mapa krainy", fill=(201,165,74), font=f_title)
    items = [("plains","równiny"),("forest","las / zagajniki"),("hills","wzgórza"),
             ("heath","wrzosowiska"),("tundra","tundra"),("mountain","góry (Siwe Granie)"),
             ("snow","śnieg"),("swamp","bagno"),("sea","morze (zatoka)"),
             ("lake","jezioro"),("coast","wybrzeże"),("river","rzeka"),
             ("road","trakt"),("bridge","most"),("town","osada / ruiny")]
    lx = 10; lyy = ly + 34; col_w = 220
    for i, (t, name) in enumerate(items):
        cxx = lx + (i % 6) * col_w; cyy = lyy + (i // 6) * 30
        dr.rectangle([cxx, cyy, cxx+22, cyy+18], fill=COLORS.get(t,(80,80,80)), outline=(40,36,28))
        dr.text((cxx+30, cyy+2), name, fill=(200,190,170), font=f_leg)
    im.save(ROOT / "temp-img/kresy_map.png")

    counts = {}
    for h in hexes.values(): counts[h["hex_type"]] = counts.get(h["hex_type"], 0) + 1
    print("OK kresy_map: docs/world/kresy_map.json + temp-img/kresy_map.png")
    print("osady:", ", ".join(f"{hexes[p]['label']}@{p}" for p in placed.values()))
    print("rzeka(main) dł.:", len(main_river_path), "| mosty:", len(bridges))
    print("teren:", {k: counts[k] for k in sorted(counts, key=lambda x: -counts[x])})

if __name__ == "__main__":
    main()
