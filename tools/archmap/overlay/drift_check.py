#!/usr/bin/env python3
"""
Drift guard: compare the files the map claims to cover (node-map.json) against
the files that actually exist in the combat subsystem on disk. Tells you when the
map skeleton has gone stale so you can ask an agent to add/remove nodes.

It does NOT edit the map. It only reports:
  - NEW   files on disk in scope with no node  -> map is missing them
  - GONE  paths in node-map.json with no file  -> node points at a deleted file

Scope = the directories the combat map covers. Edit SCOPE_GLOBS for other maps.

Usage:
    python3 drift_check.py            # human report, exit 0
    python3 drift_check.py --ci       # exit 1 if any drift (for CI / cron alert)
"""
import json, sys, argparse, fnmatch
from pathlib import Path

HERE = Path(__file__).resolve().parent
NODE_MAP = HERE / "node-map.json"
REPO = HERE.parents[2]   # tools/archmap/overlay -> repo root

# Which files this map is responsible for. Combat subsystem only (pilot).
SCOPE_GLOBS = [
    "backend/app/services/*combat*.py",
    "backend/app/services/spell_service.py",
    "backend/app/services/loot_service.py",
    "backend/app/services/dice.py",
    "backend/app/services/weapon_rules.py",
    "backend/app/services/wound_utils.py",
    "backend/app/services/xp_*.py",
    "backend/app/services/*death*.py",
    "backend/app/services/effect_json_migration.py",
    "backend/app/api/combat.py",
    "backend/app/api/inventory.py",
    "backend/app/routers/sandbox.py",
]

def scope_files():
    found = set()
    for g in SCOPE_GLOBS:
        for p in REPO.glob(g):
            found.add(str(p.relative_to(REPO)))
    return found

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ci", action="store_true")
    args = ap.parse_args()

    mapped = set(json.loads(NODE_MAP.read_text())["paths"].keys())
    on_disk = scope_files()

    new = sorted(on_disk - mapped)
    gone = sorted(p for p in mapped if not (REPO / p).exists())

    if not new and not gone:
        print("OK — map skeleton matches the combat subsystem on disk.")
        return 0

    if new:
        print(f"\nNEW ({len(new)}) — files in scope with no node on the map:")
        for p in new: print(f"  + {p}")
        print('  -> tell the agent: "zaktualizuj mapę — przyrost"')
    if gone:
        print(f"\nGONE ({len(gone)}) — node paths whose file no longer exists:")
        for p in gone: print(f"  - {p}")
        print('  -> tell the agent: "zaktualizuj mapę — usunięte pliki"')
    print()
    return 1 if args.ci else 0

if __name__ == "__main__":
    sys.exit(main())
