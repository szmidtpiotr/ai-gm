#!/usr/bin/env python3
"""SG-4 (#1481) — rozstawienie lokacji makro Siwych Grań na pliku KANONU.

Kanon = data/regions/region_siwe_granie.json (git = prawda, DB = kopia robocza, #1483).
Ten skrypt NIE dotyka DB.

FAZY (kolejność ma znaczenie):
  --phase a   sadzi lokacje klasy A (zasiedlone) + dokłada im hex-zaczep `road`
              + zaczep-terminus na skraju tundry. Potem uruchamiasz
              scripts/stitch_region_roads.py — on scali zaczepy z siecią.
  --phase bc  sadzi klasy B (opuszczone) i C (za granicą dróg) — DOPIERO PO
              zszyciu, bo pozycja klasy B jest liczona względem GOTOWEGO traktu
              (twarde 2–5 hexów od drogi).
  --audit     nic nie zmienia: tabelka lokacja → hex → klasa → odległość od traktu,
              analiza pasów bez lokacji, zasięg traktu na północ.

UŻYCIE (na .61, z katalogu repo):
  python3 scripts/sg4_place_locations.py --phase a
  python3 scripts/stitch_region_roads.py --region siwe_granie --hub 16,-17
  python3 scripts/sg4_place_locations.py --phase bc
  python3 scripts/sg4_place_locations.py --audit
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from reseed_region_terrain import ax_dist, ax_neighbors, check_road_graph  # noqa: E402
from sg4_locations_spec import B_TERRAIN, LOCATIONS, TERMINUS_ANCHOR  # noqa: E402

NETWORK = ("road", "bridge", "przelecz")
REGION = "siwe_granie"


def row_of(q: int, r: int) -> int:
    """Wiersz północ-południe mapy: 1 = południowa granica, 51 = lodowiec."""
    return -r - q // 2


def load():
    path = ROOT / "data" / "regions" / f"region_{REGION}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    hexes = {(h["q"], h["r"]): h for h in data["hexes"]}
    return data, hexes, path


def save(data, hexes, path):
    data["hexes"] = [hexes[k] for k in sorted(hexes)]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Zapisano {path.relative_to(ROOT)}")


def net_keys(hexes) -> set:
    return {k for k, h in hexes.items() if h["hex_type"] in NETWORK}


def net_distances(hexes) -> dict:
    """Odległość każdego hexa do najbliższego hexa sieci (BFS po siatce hexów)."""
    net = net_keys(hexes)
    dist = {k: 0 for k in net}
    dq = deque(net)
    while dq:
        cur = dq.popleft()
        for nb in ax_neighbors(*cur):
            if nb in hexes and nb not in dist:
                dist[nb] = dist[cur] + 1
                dq.append(nb)
    return dist


def stamp(hexes, key, loc):
    """Wbij lokację w hex kanonu: etykieta, location_key, typ hexa, atmosfera."""
    h = hexes[key]
    h["label"] = loc["label"]
    h["location_key"] = loc["key"]
    h["atmosphere"] = loc["atmo"]
    if loc.get("hex_type"):
        h["hex_type"] = loc["hex_type"]


def place_a(hexes) -> list[str]:
    log = []
    for loc in [l for l in LOCATIONS if l["cls"] == "A"]:
        k = tuple(loc["fixed"])
        h = hexes.get(k)
        if h is None:
            raise SystemExit(f"BŁĄD: hex {k} ({loc['key']}) nie istnieje w krainie")
        if h.get("location_key") and h["location_key"] != loc["key"]:
            raise SystemExit(f"BŁĄD: hex {k} zajęty przez {h['location_key']}")
        was = h["hex_type"]
        stamp(hexes, k, loc)
        log.append(f"  A {loc['label']:34s} {str(k):10s} row {row_of(*k):2d}  "
                   f"{was} → {h['hex_type']}")
        a = loc.get("anchor")
        if a:
            a = tuple(a)
            ah = hexes.get(a)
            if ah is None:
                raise SystemExit(f"BŁĄD: zaczep {a} nie istnieje")
            if ah.get("label") or ah.get("location_key"):
                raise SystemExit(f"BŁĄD: zaczep {a} ma już etykietę {ah.get('label')!r}")
            if ah["hex_type"] not in NETWORK:
                log.append(f"      zaczep traktu {a}: {ah['hex_type']} → road")
                ah["hex_type"] = "road"
    # terminus: koniec traktu na skraju tundry (lore §4b) — bez lokacji
    t = tuple(TERMINUS_ANCHOR)
    th = hexes[t]
    if th.get("label") or th.get("location_key"):
        raise SystemExit(f"BŁĄD: terminus {t} ma etykietę")
    if th["hex_type"] not in NETWORK:
        log.append(f"  ⟂ terminus traktu  {t} row {row_of(*t)}: {th['hex_type']} → road")
        th["hex_type"] = "road"
    return log


def pick_b(hexes, dist, loc, taken) -> tuple:
    """Wybór hexa dla klasy B: |row−target| ≤ 2, 2–5 hexów od traktu, teren górski,
    z dala od innych lokacji. Deterministycznie — bez losowości."""
    tr, side = loc["target_row"], loc["side"]
    qs = [q for q, _ in hexes]
    q_mid = (min(qs) + max(qs)) / 2
    cands = []
    for k, h in hexes.items():
        if h.get("label") or h.get("location_key"):
            continue
        if h["hex_type"] in NETWORK or h["hex_type"] not in B_TERRAIN:
            continue
        d = dist.get(k)
        if d is None or not (2 <= d <= 5):
            continue
        row = row_of(*k)
        if abs(row - tr) > 2:
            continue
        if any(ax_dist(k, t) < 3 for t in taken):
            continue
        side_ok = 0 if ((k[0] < q_mid) == (side == "w")) else 1
        cands.append((side_ok, abs(d - 3), abs(row - tr), k[0], k[1], k))
    if not cands:
        raise SystemExit(f"BŁĄD: brak kandydata dla {loc['key']} (row≈{tr}, strona {side})")
    return min(cands)[-1]


def place_bc(hexes) -> list[str]:
    dist = net_distances(hexes)
    taken = [k for k, h in hexes.items() if h.get("location_key")]
    log = []
    for loc in [l for l in LOCATIONS if l["cls"] == "B"]:
        k = pick_b(hexes, dist, loc, taken)
        was = hexes[k]["hex_type"]
        stamp(hexes, k, loc)
        taken.append(k)
        log.append(f"  B {loc['label']:34s} {str(k):10s} row {row_of(*k):2d}  "
                   f"dist {dist[k]}  {was} → {hexes[k]['hex_type']}")
    for loc in [l for l in LOCATIONS if l["cls"] == "C"]:
        k = tuple(loc["fixed"])
        h = hexes.get(k)
        if h is None:
            raise SystemExit(f"BŁĄD: hex {k} ({loc['key']}) nie istnieje")
        if h.get("location_key") and h["location_key"] != loc["key"]:
            raise SystemExit(f"BŁĄD: hex {k} zajęty przez {h['location_key']}")
        if h["hex_type"] not in ("lodowiec", "tundra", "snow"):
            raise SystemExit(f"BŁĄD: {loc['key']} nie stoi na lodzie/tundrze ({h['hex_type']})")
        was = h["hex_type"]
        stamp(hexes, k, loc)
        taken.append(k)
        log.append(f"  C {loc['label']:34s} {str(k):10s} row {row_of(*k):2d}  "
                   f"dist {dist.get(k, '—')}  {was} → {h['hex_type']}")
    return log


def audit(hexes):
    dist = net_distances(hexes)
    net = net_keys(hexes)
    spec_cls = {l["key"]: l["cls"] for l in LOCATIONS}

    locs = [(k, h) for k, h in hexes.items() if h.get("location_key")]
    locs.sort(key=lambda x: -row_of(*x[0]))
    print("\n| Lokacja | hex (q,r) | wiersz | klasa | hex_type | hexów od traktu |")
    print("|---|---|---:|:---:|---|---:|")
    for k, h in locs:
        cls = spec_cls.get(h["location_key"], "—")
        print(f"| {h.get('label')} | ({k[0]},{k[1]}) | {row_of(*k)} | {cls} | "
              f"`{h['hex_type']}` | {dist.get(k, '—')} |")

    print("\nWERYFIKACJA KLAS")
    bad = 0
    for k, h in locs:
        cls, d = spec_cls.get(h["location_key"]), dist.get(k)
        if cls == "A" and d is not None and d > 1:
            print(f"  ✗ A {h['label']}: {d} hexów od traktu (max 1)"); bad += 1
        if cls == "B" and (d is None or not 2 <= d <= 5):
            print(f"  ✗ B {h['label']}: {d} hexów od traktu (wymagane 2–5)"); bad += 1
        if cls == "B" and h["hex_type"] in NETWORK:
            print(f"  ✗ B {h['label']}: stoi NA drodze"); bad += 1
    print(f"  {'wszystkie klasy OK' if not bad else str(bad) + ' naruszeń'}")

    print("\nPASY BEZ LOKACJI (wiersz północ-południe)")
    rows = sorted({row_of(*k) for k, _ in locs})
    all_rows = sorted({row_of(q, r) for q, r in hexes})
    lo, hi = min(all_rows), max(all_rows)
    prev, worst = lo - 1, (0, None)
    for row in rows + [hi + 1]:
        gap = row - prev - 1
        if gap > worst[0]:
            worst = (gap, (prev + 1, row - 1))
        prev = row
    print(f"  lokacje w wierszach: {rows}")
    print(f"  najszerszy pas bez lokacji: {worst[0]} wierszy {worst[1]} "
          f"({'OK ≤10' if worst[0] <= 10 else 'PRZEKROCZONE'})")

    ok, msg = check_road_graph(hexes)
    print(f"\nGRAPH-CHECK: {msg} (spójna: {ok})")
    n_row = max(row_of(*k) for k in net)
    n_hex = max((k for k in net), key=lambda k: (row_of(*k), -k[0]))
    print(f"  najdalej na północ trakt sięga wiersza {n_row} (hex {n_hex}) "
          f"z {hi} wierszy mapy")
    oboz = next(k for k, h in hexes.items() if h.get("location_key") == "oboz_wygnancow_lodu") \
        if any(h.get("location_key") == "oboz_wygnancow_lodu" for h in hexes.values()) else None
    if oboz:
        d = min(ax_dist(oboz, k) for k in net)
        print(f"  Obóz Wygnańców Lodu {oboz}: {d} hexów od końca traktu")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("a", "bc"))
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    data, hexes, path = load()
    if a.phase == "a":
        print("FAZA A — lokacje zasiedlone + zaczepy traktu:")
        print("\n".join(place_a(hexes)))
    elif a.phase == "bc":
        print("FAZA B/C — opuszczone i za granicą dróg:")
        print("\n".join(place_bc(hexes)))

    if a.audit or a.phase:
        audit(hexes)

    if a.phase and not a.dry_run:
        save(data, hexes, path)
    elif a.phase:
        print("\n--dry-run: plik NIE zapisany")


if __name__ == "__main__":
    main()
