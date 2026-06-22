#!/usr/bin/env python3
"""Snapshot bieżącej mapy świata (world_hexes, map_level=0) -> docs/world/world_map_seed.json.

Zapisuje TWOJE edycje z admin->Mapa jako nowy KANON. Po uruchomieniu ZACOMMITUJ plik —
dopiero commit czyni edycje trwałymi (i odpornymi na czyszczenie DB przez innych agentów,
bo seed_world_map.py odtworzy mapę z tego pliku).

Uruchom na hoście DEV (.61):
    python3 scripts/snapshot_world_map.py
"""
import json, subprocess, argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "docs/world/world_map_seed.json"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--container", default="ai-gm-dev-backend-1")
    a = ap.parse_args()

    out = subprocess.run(
        ["docker", "exec", a.container, "sqlite3", "-json", "/data/ai_gm.db",
         "SELECT q,r,hex_type,label,atmosphere,encounter_chance FROM world_hexes "
         "WHERE map_level=0 ORDER BY r,q;"],
        text=True, capture_output=True)
    if out.returncode != 0:
        print("BŁĄD odczytu DB:", out.stderr, file=sys.stderr); sys.exit(1)
    hexes = json.loads(out.stdout or "[]")
    if not hexes:
        print("world_hexes (map_level=0) puste — nic do zapisania. Najpierw seed_world_map.py."); sys.exit(1)

    data = {"name": "Kresy",
            "note": "KANON mapy świata (world_hexes map_level=0). Źródło prawdy = ten plik w git "
                    "(commit = zgoda Piotra). Snapshot: snapshot_world_map.py. Seed: seed_world_map.py.",
            "w": 50, "h": 50, "hexes": hexes}
    json.dump(data, open(SEED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Zapisano {len(hexes)} heksów -> {SEED}. ZACOMMITUJ plik, aby utrwalić edycje.")

if __name__ == "__main__":
    main()
