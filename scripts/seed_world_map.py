#!/usr/bin/env python3
"""Seed/restore świata (world_hexes, map_level=0) z KANONU: docs/world/world_map_seed.json.

Źródło prawdy = plik w git (commit = zgoda Piotra). Domyślnie seeduje TYLKO gdy mapa
pusta (idempotentne — nie nadpisuje istniejących edycji). --force nadpisuje.

Uruchom na hoście DEV (.61):
    python3 scripts/seed_world_map.py            # seed jeśli pusto
    python3 scripts/seed_world_map.py --force    # nadpisz mapę z pliku
"""
import json, subprocess, sys, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "docs/world/world_map_seed.json"

def dexec(container, sql, piped=False):
    cmd = ["docker", "exec"] + (["-i"] if piped else []) + [container, "sqlite3", "/data/ai_gm.db"]
    if not piped:
        cmd.append(sql)
    return subprocess.run(cmd, input=(sql if piped else None), text=True, capture_output=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="nadpisz nawet gdy mapa niepusta")
    ap.add_argument("--container", default="ai-gm-dev-backend-1")
    a = ap.parse_args()

    cnt = int((dexec(a.container, "SELECT count(*) FROM world_hexes WHERE map_level=0;").stdout or "0").strip() or 0)
    if cnt > 0 and not a.force:
        print(f"world_hexes ma {cnt} heksów (map_level=0) — pomijam. Użyj --force by nadpisać z {SEED.name}.")
        return

    d = json.load(open(SEED, encoding="utf-8"))
    def esc(s): return "NULL" if s is None else "'" + str(s).replace("'", "''") + "'"
    rows = [f"({h['q']},{h['r']},'{h['hex_type']}',{esc(h.get('label'))},{esc(h.get('atmosphere'))},"
            f"{h.get('encounter_chance',0.15)},'[]',NULL,1,1,0)" for h in d["hexes"]]
    cols = "(q,r,hex_type,label,atmosphere,encounter_chance,encounter_pool,location_key,created_by_gm,is_active,map_level)"
    sql = ("BEGIN;\nDELETE FROM world_hexes WHERE map_level=0;\n"
           + "\n".join(f"INSERT INTO world_hexes {cols} VALUES " + ",".join(rows[i:i+200]) + ";"
                       for i in range(0, len(rows), 200))
           + "\nCOMMIT;")
    r = dexec(a.container, sql, piped=True)
    if r.returncode != 0:
        print("BŁĄD seedowania:", r.stderr, file=sys.stderr); sys.exit(1)
    print(f"Zaseedowano {len(rows)} heksów z {SEED.name} (force={a.force}).")

if __name__ == "__main__":
    main()
