#!/usr/bin/env python3
"""Przenieś lokację (hex z `label`/`location_key`) na inny hex w pliku krainy.

Operuje na KANONIE (`data/regions/region_<key>.json`) — plik w git jest źródłem prawdy,
DB to kopia robocza (#1483). DB dostaje ten stan dopiero przez `seed_world_map.py`,
a powiązanie hex↔`game_locations` domyka `link_location_to_hex` (#1305/#1243).

CO ROBI
  * przenosi CAŁY „ładunek lokacji" ze źródłowego hexa na docelowy:
    hex_type, label, atmosphere, encounter_chance, encounter_pool, location_key,
  * hex źródłowy wraca do terenu dzikiego (`--fallback`, domyślnie `mountain`),
    dzięki czemu kolejny przebieg `reseed_region_terrain.py` przemaluje go wg planu §5,
  * odmawia, gdy hex docelowy ma już `label`/`location_key` (nie kradniemy lokacji).

CO ROBI *NIE*
  * nie dotyka DB ani innych hexów, nie zmienia liczby hexów w krainie.

UŻYCIE
  python3 scripts/move_region_location.py --region siwe_granie --from 31,-27 --to 32,-65
  python3 scripts/move_region_location.py --region siwe_granie --from 10,-15 --to 38,-64
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# pola, które „jadą" razem z lokacją
CARGO = ("hex_type", "label", "atmosphere", "encounter_chance", "encounter_pool", "location_key")


def parse_qr(s: str) -> tuple[int, int]:
    q, r = s.replace(" ", "").split(",")
    return int(q), int(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--from", dest="src", required=True, help="q,r hexa źródłowego")
    ap.add_argument("--to", dest="dst", required=True, help="q,r hexa docelowego")
    ap.add_argument("--fallback", default="mountain", help="typ terenu dla zwolnionego hexa")
    a = ap.parse_args()

    src, dst = parse_qr(a.src), parse_qr(a.dst)
    path = ROOT / "data" / "regions" / f"region_{a.region}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    idx = {(h["q"], h["r"]): h for h in data["hexes"]}

    if src not in idx:
        raise SystemExit(f"BŁĄD: brak hexa źródłowego {src} w {path.name}")
    if dst not in idx:
        raise SystemExit(f"BŁĄD: brak hexa docelowego {dst} w {path.name}")
    s, d = idx[src], idx[dst]
    if d.get("label") or d.get("location_key"):
        raise SystemExit(f"BŁĄD: hex docelowy {dst} jest już zajęty ({d.get('label')!r}) — przerwane")

    label = s.get("label")
    for f in CARGO:
        if f in s:
            d[f] = s[f]
        else:
            d.pop(f, None)
    # źródło wraca do terenu dzikiego — plan §5 przemaluje je przy kolejnym przebiegu
    s["hex_type"] = a.fallback
    s["label"] = None
    s["atmosphere"] = None
    s.pop("location_key", None)
    s.pop("encounter_pool", None)
    s["encounter_chance"] = 0.15

    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Przeniesiono {label!r}: {src} → {dst} "
          f"(location_key={d.get('location_key')!r}, hex_type={d.get('hex_type')!r}); "
          f"hex {src} → {a.fallback}. Zapisano {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
