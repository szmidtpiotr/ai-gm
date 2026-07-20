#!/usr/bin/env python3
"""Zszycie sieci traktów krainy w JEDEN spójny graf (SG-3, #1481, lore §4b).

PROBLEM
  Silnik podróży liczy po hexach `road`/`bridge`/`przelecz`. Rozłączne składowe =
  ślepe odcinki i nieosiągalne lokacje (bug klasy #1293). Siwe Granie miały 45 hexów
  sieci rozbitych na 7 składowych.

CO ROBI
  Dokłada MINIMALNĄ liczbę nowych hexów traktu, tak by wszystkie składowe zlały się
  w jedną. Algorytm = Prim po składowych: wielo-źródłowa Dijkstra z „wyrośniętej"
  sieci szuka najtańszej ścieżki do najbliższej jeszcze niepodłączonej składowej,
  ścieżkę utwardza na trakt i powtarza. Koszt = teren (patrz TERRAIN_COST).

ZASADY (lore §4b — twarde)
  * lodowiec i tundra są NIEPRZEJEZDNE — przez nie trakt nie idzie nigdy
    (izolacja Wygnańców i sanktuarium; podróż tam = przeprawa, nie spacer),
  * `grania` nieprzechodnia, jeziora omijamy,
  * hexy z `label`/`location_key` są nietykalne (przejścia „ku Kresom", lokacje) —
    nie wolno ich przemalować, więc trasa je omija,
  * istniejące mosty i przełęcze zostają jak są,
  * nowy hex na rzece dostaje `bridge` (przeprawa), w innym terenie `road`.

CO ROBI *NIE*
  * nie łączy się z DB (kanon = plik krainy w git, #1483),
  * nie zmienia liczby hexów ani żadnego hexa spoza dołożonej trasy.

UŻYCIE
  python3 scripts/stitch_region_roads.py --region siwe_granie --dry-run
  python3 scripts/stitch_region_roads.py --region siwe_granie --hub 16,-17
"""
from __future__ import annotations

import argparse
import heapq
import json
import sys
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from reseed_region_terrain import ax_neighbors, check_road_graph  # noqa: E402

NETWORK = ("road", "bridge", "przelecz")

# koszt wejścia na hex; None = nieprzejezdne
TERRAIN_COST = {
    "plains": 1, "heath": 2, "hills": 2, "forest": 3, "las_iglasty": 3,
    "mountain": 4, "snow": 5, "siarka": 6, "coast": 3, "swamp": 6,
    "river": 8,          # przeprawa → most
    "ruins": None, "city": None, "town": None, "village": None,
    "lake": None, "sea": None, "water": None,
    "grania": None,      # grzbiet nieprzechodni (lore §5)
    "lodowiec": None,    # lore §4b: lodowiec BEZ dróg
    "tundra": None,      # lore §4b: głęboka tundra BEZ dróg
}


def load(region: str):
    path = ROOT / "data" / "regions" / f"region_{region}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    hexes = {(h["q"], h["r"]): h for h in data["hexes"]}
    return data, hexes, path


def components(hexes: dict) -> list[list[tuple]]:
    net = {k for k, h in hexes.items() if h["hex_type"] in NETWORK}
    todo, comps = set(net), []
    while todo:
        s = min(todo)
        seen, dq = {s}, deque([s])
        while dq:
            cur = dq.popleft()
            for nb in ax_neighbors(*cur):
                if nb in net and nb not in seen:
                    seen.add(nb)
                    dq.append(nb)
        comps.append(sorted(seen))
        todo -= seen
    comps.sort(key=len, reverse=True)
    return comps


def cost_of(hexes: dict, k: tuple):
    """Koszt wejścia na hex, albo None gdy nieprzejezdny / nietykalny."""
    h = hexes.get(k)
    if h is None:
        return None
    if h["hex_type"] in NETWORK:
        return 0
    if h.get("label") or h.get("location_key"):
        return None            # lokacje i przejścia „ku Kresom" — nie ruszamy
    return TERRAIN_COST.get(h["hex_type"])


def dijkstra_to_targets(hexes: dict, sources: set, targets: set):
    """Najtańsza ścieżka ze zbioru źródeł do dowolnego hexa docelowego."""
    dist = {s: 0 for s in sources}
    prev: dict = {}
    pq = [(0, s) for s in sorted(sources)]
    heapq.heapify(pq)
    while pq:
        d, cur = heapq.heappop(pq)
        if d > dist.get(cur, 1 << 30):
            continue
        if cur in targets:
            path = [cur]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return list(reversed(path)), d
        for nb in ax_neighbors(*cur):
            c = cost_of(hexes, nb)
            if c is None:
                continue
            nd = d + c
            if nd < dist.get(nb, 1 << 30):
                dist[nb] = nd
                prev[nb] = cur
                heapq.heappush(pq, (nd, nb))
    return None, None


def stitch(hexes: dict) -> list[tuple]:
    """Dokłada hexy traktu aż sieć ma jedną składową. Zwraca listę dodanych hexów."""
    comps = components(hexes)
    if len(comps) <= 1:
        return []
    grown = set(comps[0])
    pending = [set(c) for c in comps[1:]]
    added: list[tuple] = []

    while pending:
        targets = set().union(*pending)
        path, cost = dijkstra_to_targets(hexes, set(grown), targets)
        if path is None:
            raise SystemExit(
                "BŁĄD: nie da się połączyć składowych bez łamania zasad §4b "
                f"(pozostało {len(pending)} składowych) — przerwane")
        new = []
        for k in path:
            if hexes[k]["hex_type"] in NETWORK:
                continue
            hexes[k]["hex_type"] = "bridge" if hexes[k]["hex_type"] == "river" else "road"
            new.append(k)
        added.extend(new)
        end = path[-1]
        hit = next(c for c in pending if end in c)
        grown |= hit | set(path)
        pending.remove(hit)
        print(f"  + trasa {path[0]} → {end}: {len(new)} nowych hexów (koszt {cost})")
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="siwe_granie")
    ap.add_argument("--hub", default=None,
                    help="q,r hexa hubu (Kamienny Gród) — sprawdzenie sąsiedztwa z siecią")
    ap.add_argument("--dry-run", action="store_true", help="nie zapisuj pliku")
    a = ap.parse_args()

    data, hexes, path = load(a.region)
    before_types = Counter(h["hex_type"] for h in hexes.values())

    ok_b, msg_b = check_road_graph(hexes)
    print(f"PRZED {msg_b} (spójna: {ok_b})")

    frozen_before = {k: (h.get("label"), h.get("location_key")) for k, h in hexes.items()
                     if h.get("label") or h.get("location_key")}

    added = stitch(hexes)

    ok_a, msg_a = check_road_graph(hexes)
    print(f"PO    {msg_a} (spójna: {ok_a})")
    print(f"dołożono {len(added)} hexów: {sorted(added)}")

    # kontrola: żaden hex z etykietą/lokacją nie został ruszony
    for k, val in frozen_before.items():
        assert (hexes[k].get("label"), hexes[k].get("location_key")) == val, f"ruszony hex {k}"
    assert all(k not in frozen_before for k in added), "trasa weszła na hex z etykietą"

    after_types = Counter(h["hex_type"] for h in hexes.values())
    print("\n| hex_type | przed zszyciem | po zszyciu | zmiana |")
    print("|---|---:|---:|---:|")
    for t in sorted(set(before_types) | set(after_types), key=lambda t: -after_types.get(t, 0)):
        b, x = before_types.get(t, 0), after_types.get(t, 0)
        d = x - b
        print(f"| `{t}` | {b} | {x} | {'—' if d == 0 else (f'+{d}' if d > 0 else d)} |")

    if a.hub:
        q, r = (int(x) for x in a.hub.split(","))
        net = {k for k, h in hexes.items() if h["hex_type"] in NETWORK}
        adj = [nb for nb in ax_neighbors(q, r) if nb in net]
        print(f"\nhub ({q},{r}): teren={hexes[(q, r)]['hex_type']}, "
              f"sąsiadów sieci={len(adj)} {adj} → {'OK' if adj else 'BRAK POŁĄCZENIA'}")

    if not a.dry_run:
        data["hexes"] = [hexes[k] for k in sorted(hexes)]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nZapisano {path.relative_to(ROOT)}")
    else:
        print("\n--dry-run: plik NIE zapisany")

    if not ok_a:
        sys.exit(1)


if __name__ == "__main__":
    main()
