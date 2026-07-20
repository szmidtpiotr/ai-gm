#!/usr/bin/env python3
"""SG-5 (#1481) — wbicie Kamiennego Grodu w hex kanonu krainy.

Kanon = data/regions/region_siwe_granie.json (git = prawda, DB = kopia robocza, #1483).
Skrypt NIE dotyka DB — zmienia jeden hex: (16,-17), zarezerwowany od SG-2.

Kontrola przed zapisem: hex musi być wolny (bez etykiety i bez lokacji) i musi
sąsiadować z siecią dróg — inaczej karawany nie dojadą do stolicy.

UŻYCIE (na .61):
  python3 scripts/sg5_place_grod.py --dry-run
  python3 scripts/sg5_place_grod.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from reseed_region_terrain import ax_neighbors, check_road_graph  # noqa: E402
from sg5_grod_spec import HUB, HUB_HEX  # noqa: E402

NETWORK = ("road", "bridge", "przelecz")
REGION = "siwe_granie"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    path = ROOT / "data" / "regions" / f"region_{REGION}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    hexes = {(h["q"], h["r"]): h for h in data["hexes"]}

    k = tuple(HUB_HEX)
    h = hexes.get(k)
    if h is None:
        raise SystemExit(f"BŁĄD: hex {k} nie istnieje w krainie")
    if (h.get("label") or h.get("location_key")) and h.get("location_key") != HUB["key"]:
        raise SystemExit(f"BŁĄD: hex {k} zajęty: {h.get('label')!r} / {h.get('location_key')!r}")

    adj = [nb for nb in ax_neighbors(*k) if hexes.get(nb, {}).get("hex_type") in NETWORK]
    if not adj:
        raise SystemExit(f"BŁĄD: hex {k} nie dotyka sieci dróg — stolica bez dojazdu")

    was = h["hex_type"]
    h["hex_type"] = HUB["hex_type"]
    h["label"] = HUB["label"]
    h["location_key"] = HUB["key"]
    h["atmosphere"] = HUB["atmo"]

    print(f"{HUB['label']}: hex {k}  {was} → {h['hex_type']}")
    print(f"  sąsiedztwo sieci dróg: {len(adj)} {adj} → dojazd OK")
    ok, msg = check_road_graph(hexes)
    print(f"  GRAPH-CHECK: {msg} (spójna: {ok})")
    if not ok:
        raise SystemExit("BŁĄD: sieć dróg rozpadła się — przerwane")

    if a.dry_run:
        print("--dry-run: plik NIE zapisany")
        return
    data["hexes"] = [hexes[key] for key in sorted(hexes)]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Zapisano {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
