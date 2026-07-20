#!/usr/bin/env python3
"""Snapshot bieżącej mapy świata (world_hexes, map_level=0) → pliki kanon.

Zapisuje TWOJE edycje z admin→Mapa jako nowy KANON. Po uruchomieniu ZACOMMITUJ pliki —
dopiero commit czyni edycje trwałymi i odpornymi na czyszczenie DB.

Tryby:
  (domyślnie)          — snapshot WSZYSTKICH live krain do osobnych data/regions/region_<key>.json
                         + legacy docs/world/world_map_seed.json (backward compat).
  --region <key>       — snapshot tylko tej krainy do data/regions/region_<key>.json.

Uruchom na hoście DEV (.61):
    python3 scripts/snapshot_world_map.py
    python3 scripts/snapshot_world_map.py --region kresy
"""
import json, subprocess, argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGIONS_DIR = ROOT / "data" / "regions"
LEGACY_SEED = ROOT / "docs" / "world" / "world_map_seed.json"

def _existing_region_meta(region_key: str) -> dict:
    """R1 (#1241) — status/label/w/h krainy = istniejący plik region_<key>.json (kanon).

    Snapshot PRZEPISUJE status zastany w pliku — nigdy go nie zmienia. Nowa kraina
    (brak pliku) → domyślnie status 'coming', 50×50."""
    p = REGIONS_DIR / f"region_{region_key}.json"
    if p.exists():
        try:
            d = json.load(open(p, encoding="utf-8"))
            meta = {
                "label":  d.get("label", region_key),
                "status": d.get("status", "coming"),
                "w":      d.get("w", 50),
                "h":      d.get("h", 50),
            }
            # SG-9 (#1481): klucze, których snapshot nie generuje (np. terrain_plan_seed
            # zapisany przez generator terenu) muszą przetrwać round-trip — inaczej
            # pierwszy snapshot po seedzie cicho kasuje wejście generatora.
            meta["_extra"] = {
                k: v for k, v in d.items()
                if k not in ("region", "label", "status", "w", "h", "note", "hexes")
            }
            return meta
        except (OSError, ValueError):
            pass
    return {"label": region_key, "status": "coming", "w": 50, "h": 50, "_extra": {}}


# Kolumny o wartości domyślnej pomijamy w pliku (mniejszy plik, czytelny diff).
# Seed używa dokładnie tych samych domyślnych wartości, więc round-trip jest 1:1.
HEX_DEFAULTS = {"encounter_pool": "[]", "location_key": None, "created_by_gm": 1, "is_active": 1}


def _query_hexes(container: str, region: str | None = None, db: str = "/data/ai_gm.db") -> list[dict]:
    where = "map_level=0" + (f" AND region='{region}'" if region else "")
    out = subprocess.run(
        ["docker", "exec", container, "sqlite3", "-json", db,
         f"SELECT q,r,hex_type,label,atmosphere,encounter_chance,encounter_pool,"
         f"location_key,created_by_gm,is_active,region "
         f"FROM world_hexes WHERE {where} ORDER BY region,r,q;"],
        text=True, capture_output=True,
    )
    if out.returncode != 0:
        print("BŁĄD odczytu DB:", out.stderr, file=sys.stderr)
        sys.exit(1)
    return json.loads(out.stdout or "[]")


def _strip_hex(h: dict) -> dict:
    """Usuń 'region' (jest w top-level) i kolumny o wartości domyślnej."""
    return {
        k: v for k, v in h.items()
        if k != "region" and not (k in HEX_DEFAULTS and v == HEX_DEFAULTS[k])
    }


def _save_region(hexes: list[dict], region_key: str) -> Path:
    meta = _existing_region_meta(region_key)
    stripped = [_strip_hex(h) for h in hexes]
    data = {
        "region": region_key,
        "label":  meta["label"],
        "status": meta["status"],
        "w":      meta["w"],
        "h":      meta["h"],
        "note": (
            f"DLC paczka FAZY RM — {meta['label']}. Kanon = ten plik w git (commit = zgoda Piotra). "
            f"Seed: scripts/seed_world_map.py --region {region_key}. "
            f"Snapshot: scripts/snapshot_world_map.py --region {region_key}."
        ),
        "hexes": stripped,
    }
    data.update(meta.get("_extra") or {})
    REGIONS_DIR.mkdir(parents=True, exist_ok=True)
    out = REGIONS_DIR / f"region_{region_key}.json"
    tmp = out.with_suffix(".json.tmp")
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tmp.replace(out)
    return out


def _save_legacy(hexes: list[dict]) -> Path:
    stripped = [_strip_hex(h) for h in hexes]
    data = {
        "name": "Kresy",
        "note": (
            "KANON mapy świata (world_hexes map_level=0). Źródło prawdy = ten plik w git "
            "(commit = zgoda Piotra). Snapshot: snapshot_world_map.py. Seed: seed_world_map.py. "
            "LEGACY: nowe krainy w data/regions/region_<key>.json."
        ),
        "w": 50, "h": 50, "hexes": stripped,
    }
    tmp = LEGACY_SEED.with_suffix(".json.tmp")
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tmp.replace(LEGACY_SEED)
    return LEGACY_SEED


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region",    default=None, help="snapshot tylko tej krainy")
    ap.add_argument("--container", default="ai-gm-dev-backend-1")
    ap.add_argument("--db", default="/data/ai_gm.db",
                    help="ścieżka DB wewnątrz kontenera (np. kopia do weryfikacji)")
    a = ap.parse_args()

    if a.region:
        # --- Snapshot jednej krainy ---
        hexes = _query_hexes(a.container, a.region, a.db)
        if not hexes:
            print(f"world_hexes (region={a.region}, map_level=0) puste — nic do zapisania.")
            sys.exit(1)
        if len(hexes) < 50:
            print(f"OSTRZEŻENIE: tylko {len(hexes)} heksów regionu '{a.region}' — wygląda niezainicjalizowane.")
        out = _save_region(hexes, a.region)
        print(f"Zapisano {len(hexes)} heksów (region={a.region}) → {out}. ZACOMMITUJ plik.")
    else:
        # --- Snapshot wszystkich krain (per-region) ---
        all_hexes = _query_hexes(a.container, None, a.db)
        if not all_hexes:
            print("world_hexes (map_level=0) puste — nic do zapisania. Najpierw seed_world_map.py.")
            sys.exit(1)

        # Grupuj wg regionu
        by_region: dict[str, list[dict]] = {}
        for h in all_hexes:
            r = h.get("region") or "kresy"
            by_region.setdefault(r, []).append(h)

        for region_key, hexes in sorted(by_region.items()):
            out = _save_region(hexes, region_key)
            print(f"  Zapisano {len(hexes)} heksów (region={region_key}) → {out}")

        # Legacy backward-compat (tylko kresy)
        kresy_hexes = by_region.get("kresy", [])
        if kresy_hexes:
            legacy = _save_legacy(kresy_hexes)
            print(f"  Legacy: {len(kresy_hexes)} heksów → {legacy}")

        total = len(all_hexes)
        print(f"Snapshot {total} heksów ({len(by_region)} krain). ZACOMMITUJ pliki.")


if __name__ == "__main__":
    main()
