#!/usr/bin/env python3
"""build_region_tlo_morze.py — SLOT MORSKI tła kontynentu (#1549, TŁO-2).

Blok (0, 1) siatki kontynentu — pomiędzy Wybrzeżem Łez (blok SW) a Martwymi
Pustkowiami (blok SE), pod statycznymi trasami rejsów WL↔MP (SEA_ROUTES, WL-4).
To DEKORACJA: ~2500 hexów `morze`, zero lokacji, zero spotkań (encounter 0).

Nie jest krainą z rosteru (lore = 6 krain). W `world_regions` dostanie status
`locked` (globalnie nieprzechodni) — ale rysowany ZAWSZE, bez mgły wojny, żeby
mapa nie miała czarnej dziury (patrz #1549 „widoczność bez FOW").

GRADIENTY GRANICZNE (per #1545 — żadnych ostrych linii bloków):
  * ZACHÓD (Wybrzeże Łez): pas `plycizna` (płycizna) 1–2 hexy w głąb, z szumem
    na krawędzi — łagodne zejście wybrzeże → płycizna → morze.
  * WSCHÓD (Martwe Pustkowia): `sol` może stykać się z `morze` BEZPOŚREDNIO
    (decyzja Piotra — sól jest w wodzie morskiej, bez klifów) → BRAK bufora,
    morze do samej krawędzi.
  * PÓŁNOC (Kresy, południowa krawędź): pas `coast` 1–2 hexy — bufor lądowy.
    Stronę Kresów Piotr poprawia ręcznie / pass reconcile.

DETERMINIZM: wszystko z jednego ziarna (--seed). Bez zegara.
DB NIE JEST RUSZANA — seed osobno: scripts/seed_world_map.py --region tlo_morze.

UŻYCIE (na .61):
  python3 scripts/build_region_tlo_morze.py --dry-run   # podgląd, JSON nie zapisany
  python3 scripts/build_region_tlo_morze.py             # zapis JSON + PNG
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
from reseed_region_terrain import COLORS, PL_NAMES, save_png  # noqa: E402

REGION = "tlo_morze"
SEED = 1549

# kolory/nazwy dla PNG (typy istnieją już w hex_type_config; tu tylko podgląd)
COLORS.setdefault("morze", (11, 42, 82))       # #0b2a52
COLORS.setdefault("plycizna", (111, 176, 201)) # #6fb0c9
COLORS.setdefault("coast", (90, 154, 170))     # #5a9aaa
PL_NAMES.update({"morze": "morze", "plycizna": "płycizna", "coast": "wybrzeże"})

# szerokość pasów granicznych (WARTOŚCI STARTOWE — Numbers Policy)
WEST_SHALLOW_COLS = 2   # zachód: płycizna w głąb (styk z Wybrzeżem Łez)
NORTH_COAST_ROWS = 2    # północ: coast w głąb (styk z Kresami)


def off2ax(col, row):
    """offset-coords (flat-top) → axial lokalny (jak generate_region_map / KN build)."""
    return (col, row - (col - (col & 1)) // 2)


def build_grid():
    """Pełna siatka 50×50 morza w absolutnych axial (offset bloku morskiego)."""
    q_off, r_off = region_offsets(REGION)   # (0, 50)
    hexes, local = {}, {}
    for row in range(H):
        for col in range(W):
            aq, ar = off2ax(col, row)
            k = (aq + q_off, ar + r_off)
            hexes[k] = {"q": k[0], "r": k[1], "hex_type": "morze",
                        "label": None, "location_key": None,
                        "atmosphere": None, "encounter_chance": 0.0}
            local[k] = (col, row)
    return hexes, local, (q_off, r_off)


def paint_borders(hexes, local, rng):
    """Pasy graniczne: płycizna na zachodzie, coast na północy (z szumem krawędzi)."""
    n_shallow = n_coast = 0
    for k, (col, row) in local.items():
        # ZACHÓD — płycizna (styk z Wybrzeżem Łez); krawędź poszarpana szumem
        depth = WEST_SHALLOW_COLS + (1 if rng.random() < 0.35 else 0)
        if col < depth:
            hexes[k]["hex_type"] = "plycizna"
            n_shallow += 1
        # PÓŁNOC — coast (bufor lądowy do Kresów); wygrywa w narożnikach
        depth_n = NORTH_COAST_ROWS + (1 if rng.random() < 0.35 else 0)
        if row < depth_n:
            hexes[k]["hex_type"] = "coast"
            n_coast += 1
    # WSCHÓD (Martwe Pustkowia): sol↔morze bezpośrednio — BRAK bufora (decyzja Piotra).
    return n_shallow, n_coast


def set_encounter(hexes):
    """Morze = dekoracja: zero spotkań wszędzie (rejsy są na SEA_ROUTES, nie na hexach)."""
    for h in hexes.values():
        h["encounter_chance"] = 0.0


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
    ap.add_argument("--png", default="docs/world/previews/tlo_morze.png")
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    hexes, local, (q_off, r_off) = build_grid()
    print(f"siatka {W}×{H} = {len(hexes)} hexów morza, offset ({q_off},{r_off}), ziarno={args.seed}")

    print("[1] pasy graniczne: płycizna (W) / coast (N); wschód = sol↔morze bez bufora")
    n_shallow, n_coast = paint_borders(hexes, local, rng)
    print(f"  płycizna: {n_shallow} hexów, coast: {n_coast} hexów")

    set_encounter(hexes)

    table = dist_table(hexes)
    print("\n[2] rozkład hex_type:\n")
    print(table)

    if not args.no_png:
        p = save_png(hexes, "TŁO — SLOT MORSKI (#1549, TŁO-2)",
                     f"morze WL↔MP; płycizna na W, coast na N; encounter 0; "
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
        "label": "Morze",
        "status": "background",
        "w": W, "h": H,
        "q_offset": q_off, "r_offset": r_off,
        "bounds": {"q_min": min(q_vals), "q_max": max(q_vals),
                   "r_min": min(r_vals), "r_max": max(r_vals)},
        "terrain_plan_seed": args.seed,
        "note": ("Slot morski tła kontynentu (#1549, TŁO-2): ~2500 hexów morza, "
                 "zero lokacji/spotkań. Płycizna na zachodzie (styk Wybrzeże Łez), "
                 "coast na północy (bufor Kresy); wschód sol↔morze bezpośrednio "
                 "(decyzja Piotra). Nie kraina z rosteru — world_regions status "
                 "'locked' (nieprzechodni), rysowany zawsze bez FOW. DB NIE RUSZANA — "
                 "seed: scripts/seed_world_map.py --region tlo_morze."),
        "hexes": [hexes[k] for k in sorted(hexes)],
    }
    path = ROOT / "data" / "regions" / f"region_{REGION}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {path.relative_to(ROOT)} ({len(out['hexes'])} hexów)")


if __name__ == "__main__":
    main()
