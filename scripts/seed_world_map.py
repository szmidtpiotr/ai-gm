#!/usr/bin/env python3
"""Seed/restore świata (world_hexes, map_level=0) z KANONU.

Źródło prawdy = pliki w git (commit = zgoda Piotra).

Tryby:
  (domyślnie)          — seed jeśli mapa pusta; stitch z data/regions/*.json (live),
                         fallback → docs/world/world_map_seed.json.
  --region <key>       — załaduj tylko tę krainę z data/regions/region_<key>.json;
                         usuwa istniejące heksy tej krainy, wstawia nowe (bezpieczny partial).
  --force              — WYMAGA --region: nadpisz istniejące heksy tej jednej krainy.
  --force-all          — pełny wipe+reseed CAŁEJ mapy (map_level=0). Niebezpieczne —
                         wymaga interaktywnego 'TAK' lub flagi --yes.

Safeguard: < 50 heksów w pliku krainy → odmowa (per-region + globalnie).

Uruchom na hoście DEV (.61):
    python3 scripts/seed_world_map.py
    python3 scripts/seed_world_map.py --region kresy
    python3 scripts/seed_world_map.py --region kresy --force
    python3 scripts/seed_world_map.py --force-all --yes
"""
import json, subprocess, sys, argparse, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGIONS_DIR = ROOT / "data" / "regions"

# Legacy fallback (monolityczny seed)
_DATA_SEED = ROOT / "data-dev" / "world_map_seed.json"
_GIT_SEED = ROOT / "docs" / "world" / "world_map_seed.json"

# Guard kompletności — kraina z mniejszą liczbą heksów wygląda na niezainicjalizowaną.
MIN_HEX = 50


def dexec(container: str, sql: str, piped: bool = False):
    cmd = ["docker", "exec"] + (["-i"] if piped else []) + [container, "sqlite3", "/data/ai_gm.db"]
    if not piped:
        cmd.append(sql)
    return subprocess.run(cmd, input=(sql if piped else None), text=True, capture_output=True)


def _row_sql(h: dict) -> str:
    def esc(s):
        return "NULL" if s is None else "'" + str(s).replace("'", "''") + "'"

    region = h.get("region", "kresy")
    return (
        f"({h['q']},{h['r']},'{h.get('hex_type','plains')}',"
        f"{esc(h.get('label'))},{esc(h.get('atmosphere'))},"
        f"{h.get('encounter_chance', 0.15)},'[]',NULL,1,1,0,{esc(region)})"
    )


COLS = "(q,r,hex_type,label,atmosphere,encounter_chance,encounter_pool,location_key,created_by_gm,is_active,map_level,region)"


def _load_region_file(path: Path) -> list[dict]:
    if not path.exists():
        print(f"BŁĄD: brak pliku: {path}", file=sys.stderr)
        sys.exit(1)
    d = json.load(open(path, encoding="utf-8"))
    hexes = d.get("hexes", [])
    region_key = d.get("region", path.stem.replace("region_", ""))
    for h in hexes:
        h.setdefault("region", region_key)
    return hexes


def _build_insert_sql(hexes: list[dict]) -> str:
    rows = [_row_sql(h) for h in hexes]
    chunks = []
    for i in range(0, len(rows), 200):
        chunks.append(f"INSERT INTO world_hexes {COLS} VALUES " + ",".join(rows[i:i+200]) + ";")
    return "\n".join(chunks)


def _stitch_hexes() -> list[dict]:
    """Zbierz heksy ze wszystkich live region-plików + legacy fallback."""
    region_files = sorted(REGIONS_DIR.glob("region_*.json"))
    if region_files:
        all_hexes: list[dict] = []
        for rf in region_files:
            d = json.load(open(rf, encoding="utf-8"))
            if d.get("status") != "live":
                print(f"  Pomijam {rf.name} (status={d.get('status')!r}, nie live)")
                continue
            hexes = d.get("hexes", [])
            region_key = d.get("region", rf.stem.replace("region_", ""))
            # Guard per-region: live kraina z < MIN_HEX heksów = niekompletny plik.
            # Odmawiamy, by nie wsiać dziurawej mapy zamiast pełnej.
            if len(hexes) < MIN_HEX:
                print(f"BŁĄD: live kraina '{region_key}' ma tylko {len(hexes)} heksów "
                      f"(< {MIN_HEX}) w {rf.name} — plik niekompletny, odmawiam stitcha.",
                      file=sys.stderr)
                sys.exit(1)
            for h in hexes:
                h.setdefault("region", region_key)
            print(f"  Dołączam {rf.name}: {len(hexes)} heksów (region={region_key})")
            all_hexes.extend(hexes)
        if all_hexes:
            return all_hexes
        print("OSTRZEŻENIE: brak live region-plików — fallback do legacy seed.", file=sys.stderr)

    # Fallback do monolitycznego seeda
    src = _DATA_SEED if _DATA_SEED.exists() else _GIT_SEED
    if not src.exists():
        print(f"BŁĄD: brak pliku seed: {src}", file=sys.stderr)
        sys.exit(1)
    d = json.load(open(src, encoding="utf-8"))
    hexes = d.get("hexes", [])
    for h in hexes:
        h.setdefault("region", "kresy")
    print(f"  Fallback: {src.name}: {len(hexes)} heksów")
    return hexes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region",    default=None,        help="seeduj tylko tę krainę (partial update)")
    ap.add_argument("--force",     action="store_true", help="WYMAGA --region: nadpisz istniejące heksy tej krainy")
    ap.add_argument("--force-all", dest="force_all", action="store_true",
                    help="pełny wipe+reseed CAŁEJ mapy (map_level=0) — niebezpieczne")
    ap.add_argument("--yes",       action="store_true", help="pomiń interaktywne potwierdzenie --force-all")
    ap.add_argument("--container", default="ai-gm-dev-backend-1")
    a = ap.parse_args()

    # --force bez --region jest dwuznaczne: kiedyś oznaczało pełny wipe. Odmawiamy,
    # by przypadkowy --force nie wymiótł całej mapy. Pełny wipe → --force-all.
    if a.force and not a.region:
        print("BŁĄD: --force wymaga --region <key> (wipe per-region). "
              "Pełny wipe+reseed całej mapy → --force-all.", file=sys.stderr)
        sys.exit(2)

    if a.region:
        # --- Tryb partial: jedna kraina ---
        rf = REGIONS_DIR / f"region_{a.region}.json"
        hexes = _load_region_file(rf)
        if len(hexes) < MIN_HEX:
            print(f"BŁĄD: za mało heksów ({len(hexes)}) w {rf.name} — safeguard odmawia.", file=sys.stderr)
            sys.exit(1)

        cnt = int((dexec(a.container,
            f"SELECT count(*) FROM world_hexes WHERE map_level=0 AND region='{a.region}';").stdout or "0").strip() or 0)
        if cnt > 0 and not a.force:
            print(f"world_hexes ma {cnt} heksów regionu '{a.region}' — pomijam. Użyj --force by nadpisać.")
            return

        sql = (
            "BEGIN;\n"
            f"DELETE FROM world_hexes WHERE map_level=0 AND region='{a.region}';\n"
            + _build_insert_sql(hexes)
            + "\nCOMMIT;"
        )
        r = dexec(a.container, sql, piped=True)
        if r.returncode != 0:
            print("BŁĄD seedowania:", r.stderr, file=sys.stderr)
            sys.exit(1)
        print(f"Zaseedowano {len(hexes)} heksów (region={a.region}) z {rf.name} (force={a.force}).")

    else:
        # --- Tryb stitch: wszystkie live krainy ---
        cnt = int((dexec(a.container, "SELECT count(*) FROM world_hexes WHERE map_level=0;").stdout or "0").strip() or 0)
        if cnt > 0 and not a.force_all:
            print(f"world_hexes ma {cnt} heksów (map_level=0) — pomijam (idempotentny seed pustej mapy). "
                  "Pełny wipe+reseed → --force-all.")
            return

        if cnt > 0 and a.force_all and not a.yes:
            ans = input(f"⚠️  PEŁNY WIPE {cnt} heksów (map_level=0) i reseed z plików kanon. "
                        "Wpisz 'TAK' by potwierdzić: ")
            if ans.strip() != "TAK":
                print("Anulowano — mapa nietknięta.")
                return

        print("Stitch mode — zbieranie live krain:")
        hexes = _stitch_hexes()
        if len(hexes) < MIN_HEX:
            print(f"BŁĄD: za mało heksów ({len(hexes)}) — safeguard odmawia.", file=sys.stderr)
            sys.exit(1)

        sql = (
            "BEGIN;\n"
            "DELETE FROM world_hexes WHERE map_level=0;\n"
            + _build_insert_sql(hexes)
            + "\nCOMMIT;"
        )
        r = dexec(a.container, sql, piped=True)
        if r.returncode != 0:
            print("BŁĄD seedowania:", r.stderr, file=sys.stderr)
            sys.exit(1)
        print(f"Zaseedowano {len(hexes)} heksów (stitch, force_all={a.force_all}).")


if __name__ == "__main__":
    main()
