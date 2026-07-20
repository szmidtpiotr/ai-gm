#!/usr/bin/env python3
"""Redystrybucja terenu krainy wg planu pasów z rozdziału lore (SG-2, #1481).

CO ROBI
  Czyta AKTUALNY stan krainy z gitowego pliku prawdy `data/regions/region_<key>.json`,
  nakłada plan pasów terenu z rozdziału krainy (`docs/world/regions/<key>.md` §5)
  i produkuje:
    * podgląd PNG PRZED  (stan zastany)
    * podgląd PNG PO     (plan)
    * tabelkę rozkładu hex_type przed/po (stdout + opcjonalnie markdown)
    * opcjonalnie nowy JSON krainy (--out) — TYLKO na wyraźne żądanie

CZEGO NIE ROBI (twarda zasada SG-2)
  * NIE łączy się z bazą i NIE zapisuje niczego do `world_hexes` (ani żywej, ani kopii).
  * NIE nadpisuje `data/regions/region_<key>.json` — chyba że podasz `--out` z tą ścieżką.
  Seeding do DB to osobny krok (`scripts/seed_world_map.py`) PO akceptacji PNG.

CO ZOSTAJE NIETKNIĘTE (hexy „zamrożone")
  1. każdy hex z `label` lub `location_key` (lokacje + przejścia „ku Kresom"),
  2. sieć komunikacyjna: `road`, `bridge`, `przelecz`,
  3. sieć wodna zastana: `river`, `lake`,
  4. `grania` — grzbiety zostają grzbietami (lore §5),
  5. typy osadnicze: `city`, `town`, `village`, `ruins`.
  Zmieniane są WYŁĄCZNIE hexy „dzikie": mountain / snow / tundra / hills / heath / plains / forest.

DETERMINIZM
  Wszystko liczone z jednego ziarna (`--seed`, domyślnie z konfiguracji krainy) —
  dwa uruchomienia dają bit w bit ten sam wynik. Żadnych wywołań zegara.

UŻYCIE
  python3 scripts/reseed_region_terrain.py --region siwe_granie
  python3 scripts/reseed_region_terrain.py --region siwe_granie \
      --png-before docs/world/previews/siwe_granie_before.png \
      --png-after  docs/world/previews/siwe_granie_after.png \
      --md-table   /tmp/table.md
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── paleta podglądu (1:1 z hex_type_config w migrations_admin.py) ────────────
COLORS = {
    "water": (40, 78, 110), "coast": (74, 120, 150), "swamp": (74, 86, 64),
    "plains": (150, 156, 92), "hills": (138, 122, 74), "mountain": (110, 104, 96),
    "forest": (60, 92, 64), "river": (66, 120, 158), "road": (150, 116, 64),
    "ruins": (120, 96, 70), "city": (210, 180, 90), "town": (200, 160, 70),
    "village": (196, 150, 80), "snow": (210, 214, 220), "bridge": (180, 130, 70),
    "sea": (40, 78, 110), "lake": (62, 108, 150), "tundra": (158, 166, 148),
    "heath": (140, 110, 116),
    "grania": (90, 90, 102),        # #5a5a66
    "przelecz": (176, 160, 128),    # #b0a080
    "lodowiec": (191, 227, 242),    # #bfe3f2
    "siarka": (201, 162, 39),       # #c9a227
    "las_iglasty": (31, 69, 54),    # #1f4536
}

PL_NAMES = {
    "mountain": "góry", "snow": "śnieg", "grania": "grań (nieprzechodnia)",
    "tundra": "tundra", "lodowiec": "lodowiec", "siarka": "pola siarkowe",
    "las_iglasty": "las iglasty", "hills": "wzgórza (doliny)", "heath": "wrzosowiska",
    "river": "rzeka", "lake": "jezioro", "road": "trakt", "bridge": "most",
    "przelecz": "przełęcz", "ruins": "ruiny", "village": "osada", "town": "miasteczko",
    "city": "miasto", "forest": "las", "plains": "równiny",
}

# hexy, których NIGDY nie ruszamy
FROZEN_TYPES = {
    "road", "bridge", "przelecz",          # sieć dróg (spójność grafu — lore §4b)
    "river", "lake",                        # sieć wodna zastana
    "grania",                               # grzbiety zostają (lore §5)
    "city", "town", "village", "ruins",     # lokacje
}
# hexy, które wolno przemalować
WILD_TYPES = {"mountain", "snow", "tundra", "hills", "heath", "plains", "forest"}

_AX_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def ax_neighbors(q, r):
    return [(q + dq, r + dr) for dq, dr in _AX_DIRS]


def ax_dist(a, b):
    dq, dr = a[0] - b[0], a[1] - b[1]
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


# ── PLAN PASÓW PER KRAINA ────────────────────────────────────────────────────
# Budżety wprost z rozdziału lore (§5). To są WARTOŚCI STARTOWE — do strojenia
# po akceptacji PNG (Numbers Policy).
REGION_PLANS = {
    "siwe_granie": {
        "seed": 2001,
        "label": "Siwe Granie",
        "doc": "docs/world/regions/siwe_granie.md §5",
        # ilościowe cele (liczba hexów)
        "budget": {
            "lodowiec": 150,        # lore: ~150
            "tundra_north": 180,    # pas przejściowy tundra→lodowiec (lore: „północ = tundra→lodowiec")
            "siarka": 55,           # lore: ~50-60
            "las_iglasty": 275,     # lore: ~250-300
            "doliny": 200,          # lore: hills/heath ~200
            "jeziora": 14,          # lore: +12-15
        },
        "doliny_split": 0.65,       # 65% hills (doliny osadnicze), reszta heath (suchy skraj)
        # granice pasów w znormalizowanej osi północ(0)→południe(1)
        "band": {
            "glacier_max": 0.34,    # lodowiec tylko w tym pasie
            "tundra_max": 0.50,     # pas tundry pod lodowcem
            "south_min": 0.62,      # las + doliny na południowych stokach
            "mid_lake_min": 0.34,   # jeziora górskie w środkowym masywie
            "mid_lake_max": 0.72,
        },
        # kotwica strefy wulkanicznej: hex „Czarne Skały" (siarka rozlewa się pod nim)
        "sulphur_anchor_label": "Czarne Skały",
        "sulphur_radius": 8,
    },
}


# ── WCZYTANIE STANU ZASTANEGO ────────────────────────────────────────────────
def load_region(region_key: str):
    path = ROOT / "data" / "regions" / f"region_{region_key}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    hexes = {}
    for h in data["hexes"]:
        hexes[(h["q"], h["r"])] = dict(h)
    return data, hexes, path


def is_frozen(h: dict) -> bool:
    if h.get("label"):
        return True
    if h.get("location_key"):
        return True
    return h["hex_type"] in FROZEN_TYPES


# ── SZUM (deterministyczny, po sąsiedztwie heksowym) ─────────────────────────
def noise_field(keys, rng: random.Random, passes: int = 5):
    """Wartościowy szum wygładzony po SĄSIEDZTWIE HEKSOWYM (nie po prostokącie),
    dzięki czemu granice pasów są organiczne, a nie proste jak linijka."""
    field = {k: rng.random() for k in keys}
    keyset = set(keys)
    for _ in range(passes):
        nxt = {}
        for k in keys:
            s = field[k]
            c = 1
            for nb in ax_neighbors(*k):
                if nb in keyset:
                    s += field[nb]
                    c += 1
            nxt[k] = s / c
        field = nxt
    lo = min(field.values())
    hi = max(field.values())
    span = (hi - lo) or 1.0
    return {k: (v - lo) / span for k, v in field.items()}


def bfs_distance(keyset, sources):
    """Odległość heksowa od zbioru źródeł (sieć dróg / lokacje)."""
    dist = {s: 0 for s in sources if s in keyset}
    dq = deque(sorted(dist))
    while dq:
        cur = dq.popleft()
        for nb in ax_neighbors(*cur):
            if nb in keyset and nb not in dist:
                dist[nb] = dist[cur] + 1
                dq.append(nb)
    big = len(keyset)
    return {k: dist.get(k, big) for k in keyset}


# ── GŁÓWNA REDYSTRYBUCJA ─────────────────────────────────────────────────────
def replan_terrain(region_key: str, hexes: dict, seed: int):
    plan = REGION_PLANS[region_key]
    band = plan["band"]
    budget = plan["budget"]
    rng = random.Random(seed)

    keys = sorted(hexes.keys())
    keyset = set(keys)

    # oś północ→południe = ta sama, którą rysuje gra (flat-top axial: y ∝ q/2 + r)
    ys = {k: k[0] / 2.0 + k[1] for k in keys}
    y_lo, y_hi = min(ys.values()), max(ys.values())
    y_span = (y_hi - y_lo) or 1.0
    ny = {k: (ys[k] - y_lo) / y_span for k in keys}   # 0 = północ, 1 = południe

    n1 = noise_field(keys, rng, passes=5)   # pasy klimatyczne
    n2 = noise_field(keys, rng, passes=4)   # plamy (las vs dolina, siarka)

    frozen = {k for k in keys if is_frozen(hexes[k])}
    wild = [k for k in keys if k not in frozen and hexes[k]["hex_type"] in WILD_TYPES]
    wildset = set(wild)

    # odległość od sieci dróg + lokacji — doliny osadnicze lgną do traktu
    network = [k for k in keys if hexes[k]["hex_type"] in ("road", "bridge", "przelecz")
               or hexes[k].get("label") or hexes[k].get("location_key")]
    dist_net = bfs_distance(keyset, network)

    assigned: dict[tuple, str] = {}

    def take(candidates, score, n, hex_type):
        """Weź n najlepszych wolnych kandydatów wg score → przypisz hex_type."""
        pool = [k for k in candidates if k not in assigned]
        pool.sort(key=lambda k: (-score(k), k))
        for k in pool[:n]:
            assigned[k] = hex_type
        return pool[:n]

    # 1. LODOWIEC — czapa na dalekiej północy (lore: Lodowy Pas / Tron Białej Bogini)
    glacier_pool = [k for k in wild if ny[k] <= band["glacier_max"]]
    take(glacier_pool,
         lambda k: (band["glacier_max"] - ny[k]) / band["glacier_max"] + n1[k] * 0.55,
         budget["lodowiec"], "lodowiec")

    # 2. TUNDRA — pas przejściowy pod czapą lodową
    tundra_pool = [k for k in wild if ny[k] <= band["tundra_max"]]
    take(tundra_pool,
         lambda k: (band["tundra_max"] - ny[k]) / band["tundra_max"] + n1[k] * 0.45,
         budget["tundra_north"], "tundra")

    # 3. SIARKA — plama geotermalna pod „Czarnymi Skałami" (wschód krainy)
    anchor = None
    for k in keys:
        if hexes[k].get("label") == plan["sulphur_anchor_label"]:
            anchor = k
            break
    if anchor is not None:
        rad = plan["sulphur_radius"]
        sulphur_pool = [k for k in wild if ax_dist(k, anchor) <= rad]
        take(sulphur_pool,
             lambda k: (rad - ax_dist(k, anchor)) / rad + n2[k] * 0.85,
             budget["siarka"], "siarka")

    # 4. LAS IGLASTY — świerkowy pas dolnych stoków południowych
    south_pool = [k for k in wild if ny[k] >= band["south_min"]]
    take(south_pool,
         lambda k: (ny[k] - band["south_min"]) / (1 - band["south_min"]) * 0.9 + n2[k] * 1.2,
         budget["las_iglasty"], "las_iglasty")

    # 5. DOLINY — wzgórza/wrzosowiska wokół traktu i osad (to, co zostało na południu)
    valley = take(south_pool,
                  lambda k: (ny[k] - band["south_min"]) / (1 - band["south_min"]) * 0.5
                            + (1.0 - n2[k]) * 0.9
                            + max(0.0, (6 - dist_net[k]) / 6.0) * 1.1,
                  budget["doliny"], "hills")
    # najdalsze od traktu doliny = suchy skraj (heath)
    n_heath = int(round(len(valley) * (1.0 - plan["doliny_split"])))
    for k in sorted(valley, key=lambda k: (-dist_net[k], k))[:n_heath]:
        assigned[k] = "heath"

    # 6. JEZIORA GÓRSKIE — kilka małych oczek w środkowym masywie
    lake_pool = [k for k in wild
                 if band["mid_lake_min"] <= ny[k] <= band["mid_lake_max"] and k not in assigned]
    lake_pool.sort(key=lambda k: (n1[k], k))   # lokalne „zagłębienia" pola szumu
    seeds = []
    for k in lake_pool:
        if all(ax_dist(k, s) > 9 for s in seeds):
            seeds.append(k)
        if len(seeds) >= 4:
            break
    lake_cells = []
    for s in seeds:
        if len(lake_cells) >= budget["jeziora"]:
            break
        blob = [s]
        for nb in sorted(ax_neighbors(*s)):
            if len(blob) >= 4:
                break
            if nb in wildset and nb not in assigned and nb not in blob and n1[nb] < 0.55:
                blob.append(nb)
        for k in blob:
            if len(lake_cells) >= budget["jeziora"]:
                break
            assigned[k] = "lake"
            lake_cells.append(k)

    # ── zastosowanie planu ───────────────────────────────────────────────────
    after = {}
    for k in keys:
        h = dict(hexes[k])
        if k in assigned:
            h["hex_type"] = assigned[k]
        after[k] = h

    stats = {
        "frozen": len(frozen),
        "wild": len(wild),
        "changed": sum(1 for k in keys if after[k]["hex_type"] != hexes[k]["hex_type"]),
        "assigned": Counter(assigned.values()),
    }
    return after, stats


# ── KONTROLA SPÓJNOŚCI SIECI DRÓG (lore §4b) ─────────────────────────────────
def check_road_graph(hexes: dict) -> tuple[bool, str]:
    net = {k for k, h in hexes.items()
           if h["hex_type"] in ("road", "bridge", "przelecz")}
    if not net:
        return True, "brak sieci dróg — nic do sprawdzenia"
    todo = set(net)
    comps = []
    while todo:
        start = min(todo)
        seen = {start}
        dq = deque([start])
        while dq:
            cur = dq.popleft()
            for nb in ax_neighbors(*cur):
                if nb in net and nb not in seen:
                    seen.add(nb)
                    dq.append(nb)
        comps.append(sorted(seen))
        todo -= seen
    comps.sort(key=len, reverse=True)
    ok = len(comps) == 1
    detail = ", ".join(f"{len(c)}@{c[0]}" for c in comps)
    return ok, (f"sieć dróg: {len(net)} hexów, {len(comps)} składowych "
                f"(największa {len(comps[0])}) → [{detail}]")


# ── PODGLĄD PNG (flat-top axial — dokładnie tak jak renderuje gra) ───────────
def save_png(hexes: dict, title: str, subtitle: str, out_path: Path, S: int = 13):
    from PIL import Image, ImageDraw, ImageFont

    keys = sorted(hexes.keys())
    def px(q, r):
        return 1.5 * S * q, math.sqrt(3) * S * (q / 2.0 + r)

    pts = [px(*k) for k in keys]
    x_lo = min(p[0] for p in pts) - S - 6
    y_lo = min(p[1] for p in pts) - S - 6
    x_hi = max(p[0] for p in pts) + S + 6
    y_hi = max(p[1] for p in pts) + S + 6

    legend_h = 172
    img_w = int(x_hi - x_lo)
    img_h = int(y_hi - y_lo) + legend_h
    im = Image.new("RGB", (img_w, img_h), (10, 9, 8))
    dr = ImageDraw.Draw(im)

    def font(sz, bold=True):
        cands = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
        if not bold:
            cands.reverse()
        for p in cands:
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
        return ImageFont.load_default()

    f_lbl = font(12)
    f_leg = font(13, bold=False)
    f_title = font(26)
    f_sub = font(15, bold=False)

    def center(k):
        x, y = px(*k)
        return x - x_lo, y - y_lo

    for k in keys:
        cx, cy = center(k)
        poly = [(cx + S * math.cos(math.pi / 3 * i), cy + S * math.sin(math.pi / 3 * i))
                for i in range(6)]
        dr.polygon(poly, fill=COLORS.get(hexes[k]["hex_type"], (80, 80, 80)),
                   outline=(22, 20, 16))

    def text_w(s, fnt):
        try:
            return dr.textlength(s, font=fnt)
        except Exception:
            return len(s) * 7

    # etykiety lokacji (pomijamy powtarzalne „ku Kresom" — tylko marker)
    for k in keys:
        lab = hexes[k].get("label")
        if not lab:
            continue
        cx, cy = center(k)
        if lab.startswith("ku "):
            dr.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(230, 210, 150))
            continue
        dr.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(245, 225, 150), outline=(20, 18, 15))
        tw = text_w(lab, f_lbl)
        tx, ty = cx + 9, cy - 7
        if tx + tw > img_w - 6:
            tx = cx - 9 - tw
        dr.rectangle([tx - 3, ty - 2, tx + tw + 3, ty + 15], fill=(10, 9, 8))
        dr.text((tx, ty), lab, fill=(240, 222, 150), font=f_lbl)

    # legenda + statystyki
    counts = Counter(h["hex_type"] for h in hexes.values())
    ly = int(y_hi - y_lo) + 6
    dr.text((12, ly), title, fill=(201, 165, 74), font=f_title)
    dr.text((12, ly + 32), subtitle, fill=(160, 150, 130), font=f_sub)
    items = [t for t, _ in counts.most_common()]
    ncol = 4
    lx, lyy = 12, ly + 56
    col_w = (img_w - 2 * lx) / ncol
    for i, t in enumerate(items[:20]):
        cxx = lx + (i % ncol) * col_w
        cyy = lyy + (i // ncol) * 22
        dr.rectangle([cxx, cyy, cxx + 20, cyy + 15], fill=COLORS.get(t, (80, 80, 80)),
                     outline=(40, 36, 28))
        dr.text((cxx + 26, cyy + 1), f"{PL_NAMES.get(t, t)} — {counts[t]}",
                fill=(200, 190, 170), font=f_leg)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path)
    return out_path


# ── TABELKA PRZED/PO ─────────────────────────────────────────────────────────
def distribution_table(before: dict, after: dict) -> str:
    cb = Counter(h["hex_type"] for h in before.values())
    ca = Counter(h["hex_type"] for h in after.values())
    types = sorted(set(cb) | set(ca), key=lambda t: (-ca.get(t, 0), t))
    lines = ["| hex_type | PRZED | PO | zmiana |", "|---|---:|---:|---:|"]
    for t in types:
        b, a = cb.get(t, 0), ca.get(t, 0)
        d = a - b
        arrow = "—" if d == 0 else (f"+{d}" if d > 0 else str(d))
        name = PL_NAMES.get(t, t)
        lines.append(f"| `{t}` ({name}) | {b} | {a} | {arrow} |")
    lines.append(f"| **RAZEM** | **{sum(cb.values())}** | **{sum(ca.values())}** | — |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="siwe_granie", choices=sorted(REGION_PLANS))
    ap.add_argument("--seed", type=int, default=None, help="nadpisz ziarno krainy")
    ap.add_argument("--png-before", default="docs/world/previews/siwe_granie_terrain_before.png")
    ap.add_argument("--png-after", default="docs/world/previews/siwe_granie_terrain_after.png")
    ap.add_argument("--md-table", default=None, help="zapisz tabelkę przed/po do pliku .md")
    ap.add_argument("--out", default=None,
                    help="ZAPISZ nowy JSON krainy pod tą ścieżką (domyślnie: nic nie zapisuje)")
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()

    plan = REGION_PLANS[args.region]
    seed = args.seed if args.seed is not None else plan["seed"]

    data, before, src_path = load_region(args.region)
    print(f"źródło: {src_path.relative_to(ROOT)} ({len(before)} hexów), ziarno={seed}")

    after, stats = replan_terrain(args.region, before, seed)

    ok_b, msg_b = check_road_graph(before)
    ok_a, msg_a = check_road_graph(after)
    frozen_intact = all(
        before[k]["hex_type"] == after[k]["hex_type"]
        for k in before if is_frozen(before[k])
    )

    print(f"zamrożone hexy: {stats['frozen']} (nietknięte: {frozen_intact})")
    print(f"dzikie hexy:    {stats['wild']}  → zmienionych: {stats['changed']}")
    print(f"przydział:      {dict(stats['assigned'])}")
    print(f"PRZED {msg_b} (spójna: {ok_b})")
    print(f"PO    {msg_a} (spójna: {ok_a})")
    assert frozen_intact, "BŁĄD: zmieniono zamrożony hex — przerwane"

    table = distribution_table(before, after)
    print()
    print(table)

    if args.md_table:
        Path(args.md_table).write_text(table + "\n", encoding="utf-8")
        print(f"\ntabelka: {args.md_table}")

    if not args.no_png:
        p1 = save_png(before, f"{plan['label'].upper()} — PRZED",
                      "stan zastany (git: data/regions/region_%s.json)" % args.region,
                      ROOT / args.png_before)
        p2 = save_png(after, f"{plan['label'].upper()} — PO (plan {plan['doc'].split()[-1]})",
                      "propozycja redystrybucji terenu, seed=%d — DB NIE RUSZANA" % seed,
                      ROOT / args.png_after)
        print(f"PNG przed: {p1.relative_to(ROOT)}")
        print(f"PNG po:    {p2.relative_to(ROOT)}")

    if args.out:
        out = dict(data)
        out["hexes"] = [after[k] for k in sorted(after)]
        out["terrain_plan_seed"] = seed
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"JSON zapisany: {args.out}")
    else:
        print("\nJSON NIE zapisany (brak --out) — to jest krok podglądowy (bramka Piotra).")


if __name__ == "__main__":
    main()
