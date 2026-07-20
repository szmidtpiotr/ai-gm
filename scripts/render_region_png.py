#!/usr/bin/env python3
"""Podgląd PNG krainy z pliku kanonu — tym samym rendererem co SG-2/SG-3.

Renderer = `save_png` z scripts/reseed_region_terrain.py (flat-top axial, dokładnie
tak jak rysuje grę). Rysuje teren + markery i etykiety lokacji.

UŻYCIE (na .61):
  python3 scripts/render_region_png.py --region siwe_granie \
      --out docs/world/previews/siwe_granie_sg4_after.png \
      --title "SIWE GRANIE — PO SG-4" --subtitle "lokacje makro + oś traktu na północ"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from reseed_region_terrain import save_png  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="siwe_granie")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--scale", type=int, default=13)
    a = ap.parse_args()

    src = ROOT / "data" / "regions" / f"region_{a.region}.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    hexes = {(h["q"], h["r"]): h for h in data["hexes"]}
    title = a.title or f"{data.get('label', a.region).upper()}"
    out = save_png(hexes, title, a.subtitle, Path(a.out), S=a.scale)
    print(f"Zapisano {out} ({len(hexes)} heksów)")


if __name__ == "__main__":
    main()
