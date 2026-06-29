#!/usr/bin/env python3
"""Jednorazowy split: world_map_seed.json → data/regions/region_kresy.json.

Czyta stary monolityczny plik seed (docs/world/world_map_seed.json lub
data-dev/world_map_seed.json) i zapisuje go jako per-region DLC paczka.
Stary plik zostaje jako legacy/backup.

Uruchom raz, zacommituj data/regions/region_kresy.json.
"""
import json, argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGIONS_DIR = ROOT / "data" / "regions"

# Priorytety źródła (zgodne z seed_world_map.py)
_DATA_SEED = ROOT / "data-dev" / "world_map_seed.json"
_GIT_SEED = ROOT / "docs" / "world" / "world_map_seed.json"

# world_regions seed — dane krain (kanon, sekcja 2 FAZA_RM_MAPA_KRAIN.md)
REGION_META = {
    "kresy":            {"label": "Kresy",            "status": "live",   "sort_order": 1},
    "koronne_niziny":   {"label": "Koronne Niziny",    "status": "coming", "sort_order": 2},
    "czarnobor":        {"label": "Czarnobór",         "status": "coming", "sort_order": 3},
    "siwe_granie":      {"label": "Siwe Granie",       "status": "coming", "sort_order": 4},
    "wybrzeze_lez":     {"label": "Wybrzeże Łez",      "status": "coming", "sort_order": 5},
    "martwe_pustkowia": {"label": "Martwe Pustkowia",  "status": "coming", "sort_order": 6},
}


def split(dry_run: bool = False) -> dict:
    src = _DATA_SEED if _DATA_SEED.exists() else _GIT_SEED
    if not src.exists():
        print(f"BŁĄD: brak pliku seed: {src}", file=sys.stderr)
        sys.exit(1)

    data = json.load(open(src, encoding="utf-8"))
    hexes = data.get("hexes", [])
    if not hexes:
        print("BŁĄD: plik seed nie zawiera heksów.", file=sys.stderr)
        sys.exit(1)

    # Safeguard — stary seed to wszystkie Kresy (2500 heksów)
    if len(hexes) < 50:
        print(f"BŁĄD: za mało heksów ({len(hexes)}) — safeguard odmawia.", file=sys.stderr)
        sys.exit(1)

    # Weryfikacja duplikatów (q,r)
    seen: set = set()
    dupes = 0
    for h in hexes:
        key = (h["q"], h["r"])
        if key in seen:
            dupes += 1
        seen.add(key)
    if dupes:
        print(f"OSTRZEŻENIE: {dupes} duplikatów (q,r) w źródle.", file=sys.stderr)

    meta = REGION_META.get("kresy", {})
    region_data = {
        "region":  "kresy",
        "label":   meta.get("label", "Kresy"),
        "status":  meta.get("status", "live"),
        "w":       data.get("w", 50),
        "h":       data.get("h", 50),
        "note":    (
            "DLC paczka FAZY RM — Kresy. Kanon = ten plik w git (commit = zgoda Piotra). "
            "Seed: scripts/seed_world_map.py --region kresy. "
            "Snapshot: scripts/snapshot_world_map.py --region kresy."
        ),
        "hexes":   [
            {
                "q":                h["q"],
                "r":                h["r"],
                "hex_type":         h.get("hex_type", "plains"),
                "label":            h.get("label"),
                "atmosphere":       h.get("atmosphere"),
                "encounter_chance": h.get("encounter_chance", 0.15),
            }
            for h in hexes
        ],
    }

    out = REGIONS_DIR / "region_kresy.json"
    if dry_run:
        print(f"[dry-run] Zapisałbym {len(hexes)} heksów → {out}")
        return {"hexes": len(hexes), "out": str(out), "dry_run": True}

    REGIONS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    json.dump(region_data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tmp.replace(out)

    # Weryfikacja diff (q,r,hex_type) vs stare źródło
    old_set = {(h["q"], h["r"], h.get("hex_type", "plains")) for h in hexes}
    new_set = {(h["q"], h["r"], h["hex_type"]) for h in region_data["hexes"]}
    diff = old_set.symmetric_difference(new_set)
    if diff:
        print(f"OSTRZEŻENIE: diff q,r,hex_type vs stare źródło: {len(diff)} różnic.", file=sys.stderr)
    else:
        print("Weryfikacja diff OK — 0 różnic w (q,r,hex_type).")

    print(f"Zapisano {len(hexes)} heksów (region=kresy) → {out}")
    print(f"Stare źródło: {src} — zostaje jako legacy/backup.")
    return {"hexes": len(hexes), "out": str(out), "diff": len(diff)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="pokaż plan bez zapisu")
    a = ap.parse_args()
    split(dry_run=a.dry_run)


if __name__ == "__main__":
    main()
