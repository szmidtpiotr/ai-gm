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
    "village": (196, 150, 80), "snow": (210, 214, 220),
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

def neighbors(q, r):
    # offset even-r
    if r % 2 == 0:
        d = [(1,0),(-1,0),(0,-1),(-1,-1),(0,1),(-1,1)]
    else:
        d = [(1,0),(-1,0),(1,-1),(0,-1),(1,1),(0,1)]
    out = []
    for dq, dr in d:
        nq, nr = q+dq, r+dr
        if 0 <= nq < W and 0 <= nr < H:
            out.append((nq, nr))
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

    # gradienty regionalne (Kresy = pogranicze): góry na płn (Siwe Granie),
    # las/bagno na wsch (Czarnobór), woda w narożniku pd-zach (ku Wybrzeżu), rdzeń = równiny
    for r in range(H):
        for q in range(W):
            ny = r / (H-1); nx = q / (W-1)
            north = (1.0 - ny) ** 1.7            # mocne, skupione na północy
            east  = nx ** 1.3
            sw    = max(0.0, (1-nx)*0.6 + ny*0.6 - 0.82)
            elev[r][q] = elev[r][q]*0.50 + north*0.58 - sw*0.6
            moist[r][q] = moist[r][q]*0.55 + east*0.44 + sw*0.25

    def classify(e, m):
        if e < 0.15: return "water"
        if e < 0.21: return "coast" if m < 0.5 else "swamp"
        if e > 0.86: return "snow"
        if e > 0.74: return "mountain"
        if e > 0.60: return "hills"
        if m > 0.64: return "swamp" if e < 0.32 else "forest"
        if m > 0.52: return "forest"
        return "plains"

    hexes = {}
    for r in range(H):
        for q in range(W):
            hexes[(q, r)] = {"q": q, "r": r, "hex_type": classify(elev[r][q], moist[r][q]),
                             "label": None, "location_key": None}

    # ── RZEKI: źródła w górach, spływ do najniższego sąsiada aż do wody/krawędzi ──
    mountains = [(q, r) for (q, r) in hexes if hexes[(q, r)]["hex_type"] in ("mountain", "snow")]
    rng.shuffle(mountains)
    river_hexes = set()
    main_river_path = []
    for si, src in enumerate(mountains[:5]):
        cur = src; path = []; steps = 0
        while steps < 200:
            steps += 1
            nbrs = neighbors(*cur)
            if not nbrs: break
            cur_e = elev[cur[1]][cur[0]]
            lower = min(nbrs, key=lambda n: elev[n[1]][n[0]])
            if elev[lower[1]][lower[0]] >= cur_e:  # lokalne minimum -> stop
                break
            t = hexes[lower]["hex_type"]
            if t in ("water",): path.append(lower); break
            if t not in ("mountain", "snow", "city", "town", "village"):
                hexes[lower]["hex_type"] = "river"; river_hexes.add(lower)
            path.append(lower); cur = lower
        if len(path) > len(main_river_path):
            main_river_path = path

    # ── OSADY (lore Kresów) sadzone na pasujących heksach blisko docelowej strefy ──
    settlements = [
        ("warowny_straz", "Strażyn",                 "town",    0.70, 0.42, ("plains","hills")),
        ("pod_zlamanym_rogiem", "Pod Złamanym Rogiem","village", 0.50, 0.52, ("plains",)),
        ("brzezino",      "Brzezino",                 "village", 0.80, 0.60, ("plains","forest")),
        ("wolanka",       "Wolanka",                  "village", 0.40, 0.24, ("hills","plains")),
        ("cieszowice",    "Cieszowice",               "village", 0.28, 0.56, ("plains",)),
        ("karczma_kruki", "Karczma Pod Trzema Krukami","village",0.46, 0.70, ("plains",)),
        ("zgliszcza",     "Zgliszcza (zgliszcza)",    "ruins",   0.74, 0.76, ("plains","forest")),
    ]
    placed = {}
    used = set()
    def best_hex(tx, ty, prefer):
        cx, cy = tx*(W-1), ty*(H-1)
        cand = []
        for (q, r), h in hexes.items():
            if (q, r) in used: continue
            if h["hex_type"] in ("water","river","mountain","snow"): continue
            d = math.hypot(q-cx, r-cy)
            pref = 0 if h["hex_type"] in prefer else 6
            cand.append((d+pref, (q, r)))
        cand.sort()
        return cand[0][1]
    for key, name, typ, tx, ty, prefer in settlements:
        pos = best_hex(tx, ty, prefer)
        used.add(pos)
        hexes[pos]["hex_type"] = typ
        hexes[pos]["label"] = name
        hexes[pos]["location_key"] = key
        placed[key] = pos

    # ── DROGI: trakt łączący osady (MST po A*) ──
    COST = {"plains":1,"hills":3,"forest":4,"coast":3,"swamp":7,"river":8,
            "mountain":20,"snow":25,"water":999,"road":1,
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

    bridges = []
    for a, b in edges:
        for hx in astar(a, b):
            t = hexes[hx]["hex_type"]
            if t == "river":
                hexes[hx]["hex_type"] = "town" if False else "road"
                hexes[hx]["label"] = hexes[hx]["label"] or "Most Czarnej Rzeki"
                hexes[hx]["location_key"] = hexes[hx]["location_key"] or "most_czarnej_rzeki"
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
           "settlements": [{"key": k, "q": p[0], "r": p[1], "label": hexes[p]["label"], "type": hexes[p]["hex_type"]} for k, p in placed.items()]}
    # pełny dump wszystkich heksów (nadpisz powyższy skrót — chcemy komplet 2500)
    out["hexes"] = list(hexes.values())
    (ROOT / "docs/world").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/world/kresy_map.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── PODGLĄD PNG (PIL) ──
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("PIL brak — pomijam PNG; JSON zapisany."); return
    S = 15  # rozmiar heksa
    hw = S * math.sqrt(3); vh = S * 1.5
    img_w = int(hw * (W + 1)); img_h = int(vh * H + S)
    im = Image.new("RGB", (img_w, img_h), (10, 9, 8)); dr = ImageDraw.Draw(im)
    for (q, r), h in hexes.items():
        cx = hw * (q + 0.5 + (0.5 if r % 2 else 0)) + 4
        cy = vh * r + S + 4
        pts_poly = [(cx + S*math.sin(math.pi/3*i), cy + S*math.cos(math.pi/3*i)) for i in range(6)]
        col = COLORS.get(h["hex_type"], (80, 80, 80))
        dr.polygon(pts_poly, fill=col, outline=(20, 18, 15))
        if h["hex_type"] in ("city", "town", "village", "ruins"):
            dr.ellipse([cx-4, cy-4, cx+4, cy+4], fill=(245, 225, 150), outline=(20,18,15))
    im.save(ROOT / "temp-img/kresy_map.png")

    counts = {}
    for h in hexes.values(): counts[h["hex_type"]] = counts.get(h["hex_type"], 0) + 1
    print("OK kresy_map: docs/world/kresy_map.json + temp-img/kresy_map.png")
    print("osady:", ", ".join(f"{hexes[p]['label']}@{p}" for p in placed.values()))
    print("rzeka(main) dł.:", len(main_river_path), "| mosty:", len(bridges))
    print("teren:", {k: counts[k] for k in sorted(counts, key=lambda x: -counts[x])})

if __name__ == "__main__":
    main()
