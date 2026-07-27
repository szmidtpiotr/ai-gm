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


def paint_gradients(hexes, local, cfg, rng):
    """Pogórze od Grań (E/W) + zejście południowe (heath / taiga→czarny_las)."""
    band = 3  # głębokość pasa gradientowego
    grania_side = cfg["grania_side"]

    for k, (c, r) in local.items():
        if r < BARRIER_ICE_ROWS:
            continue  # bariera nienaruszalna

        # ── pogórze od Siwych Grań (E dla NW / W dla NE) ──
        edge_d = (W - 1 - c) if grania_side == "E" else c
        if edge_d < band:
            # bliżej krawędzi = więcej gór, dalej = wzgórza; z szumem
            if edge_d == 0 and rng.random() < 0.6:
                hexes[k]["hex_type"] = "mountain"
            elif rng.random() < 0.65:
                hexes[k]["hex_type"] = "hills" if hexes[k]["hex_type"] not in ("mountain",) \
                    else "mountain"

        # ── zejście południowe (ostatnie rzędy) ──
        south_d = (H - 1) - r
        if south_d < band:
            if cfg["south_mode"] == "heath":
                # miękkie zejście do Koronnych Nizin: wrzosowiska / równiny
                if hexes[k]["hex_type"] not in ("lake", "mountain"):
                    hexes[k]["hex_type"] = "heath" if rng.random() < 0.6 else "plains"
            else:  # taiga → czarny las (do Czarnoboru)
                if hexes[k]["hex_type"] not in ("lake", "mountain"):
                    if south_d == 0 and rng.random() < 0.5:
                        hexes[k]["hex_type"] = "czarny_las"
                    else:
                        hexes[k]["hex_type"] = "las_iglasty"


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

    print("[2] jeziora (z dala od gór — #1545)")
    lakes = carve_lakes(hexes, local, rng)
    print(f"  jeziora: {len(lakes)} hexów")

    print("[3] gradienty: pogórze od Grań + zejście południowe")
    paint_gradients(hexes, local, cfg, rng)

    print("[4] bariera północna: grań (nieprzechodnia) + lodowiec/śnieg")
    n_bar = paint_barrier(hexes, local, rng)
    print(f"  bariera: {n_bar} hexów")

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
