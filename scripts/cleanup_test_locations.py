#!/usr/bin/env python3
"""Sprzątanie lokacji-śmieci po testach (#941/#1382/#1480).

Suity testowe zostawiają w `game_locations` rekordy typu `test_flow_<ts>` albo
`issue1105_<nazwa>_<id>`. Śmieć potrafi zająć hex mapy świata (`world_hexes.location_key`)
i przejąć sub-lokacje prawdziwej krainy — wtedy trafia do snapshotu mapy jako „kanon".

Skrypt: znajduje śmieci → raportuje wszystkie referencje → (z --apply) odpina i kasuje.

Sub-lokacje wiszące pod śmieciem NIE są kasowane. Jeśli kanon contentu
(`data/seeds/content/game_locations.json`) zna ich prawdziwego rodzica, rodzic jest
odtwarzany z kanonu i dzieci wracają pod niego; w przeciwnym razie zostają bez rodzica
(do ręcznego wpięcia) — nigdy nie znikają.

Domyślnie DRY-RUN. Zapis dopiero z --apply (zrób wcześniej ./scripts/backup_dev.sh).

    python3 scripts/cleanup_test_locations.py            # raport
    python3 scripts/cleanup_test_locations.py --apply    # sprzątanie
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON_LOCATIONS = ROOT / "data" / "seeds" / "content" / "game_locations.json"

# Wzorce kluczy-śmieci. Zgodne z CANON_FILTERS w content_seed_lib.py — jeśli
# dodajesz wzorzec tu, dodaj go też tam, inaczej śmieć wróci przez seed contentu.
JUNK_PREDICATE = (
    "key LIKE 'test\\_%' ESCAPE '\\' "
    "OR key LIKE '\\_\\_test%' ESCAPE '\\' "
    "OR key LIKE '%\\_test\\_%' ESCAPE '\\' "
    "OR key GLOB 'issue[0-9]*'"
)


def q(container: str, sql: str, db: str) -> list[dict]:
    r = subprocess.run(["docker", "exec", container, "sqlite3", "-json", db, sql],
                       text=True, capture_output=True)
    if r.returncode != 0:
        print("BŁĄD odczytu DB:", r.stderr, file=sys.stderr)
        sys.exit(1)
    return json.loads(r.stdout or "[]")


def write(container: str, sql: str, db: str):
    r = subprocess.run(["docker", "exec", "-i", container, "sqlite3", db],
                       input=sql, text=True, capture_output=True)
    if r.returncode != 0:
        print("BŁĄD zapisu:", r.stderr, file=sys.stderr)
        sys.exit(1)


def esc(v):
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def _canon_rows() -> dict[str, dict]:
    if not CANON_LOCATIONS.exists():
        return {}
    return {r["key"]: r for r in json.load(open(CANON_LOCATIONS, encoding="utf-8"))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="wykonaj zmiany (domyślnie dry-run)")
    ap.add_argument("--container", default="ai-gm-dev-backend-1")
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()
    C, DB = a.container, a.db

    junk = q(C, f"SELECT id,key,label,region FROM game_locations WHERE {JUNK_PREDICATE} ORDER BY id;", DB)
    if not junk:
        print("Brak lokacji-śmieci — nic do roboty.")
        return
    ids = [r["id"] for r in junk]
    keys = [r["key"] for r in junk]
    id_list = ",".join(str(i) for i in ids)
    key_list = ",".join(esc(k) for k in keys)

    print(f"ŚMIECI: {len(junk)} lokacji")
    for r in junk:
        print(f"  #{r['id']:<5} {r['key']}  ({r['label']}, region={r['region']})")

    hexes = q(C, f"SELECT q,r,map_level,region,location_key FROM world_hexes "
                 f"WHERE location_key IN ({key_list});", DB)
    # Dzieci będące same śmieciem znikną razem z rodzicem — nie ma czego ratować.
    kids = q(C, f"SELECT id,key,label,region,parent_id,parent_key FROM game_locations "
                f"WHERE parent_id IN ({id_list}) AND id NOT IN ({id_list});", DB)
    sess = q(C, "SELECT gs.id, gs.campaign_id, gs.current_location_id, "
                "(SELECT count(*) FROM campaigns c WHERE c.id=gs.campaign_id) AS campaign_exists "
                f"FROM game_sessions gs WHERE gs.current_location_id IN ({id_list});", DB)

    print(f"\nZAJĘTE HEKSY: {len(hexes)}")
    for h in hexes:
        print(f"  ({h['q']},{h['r']}) lvl={h['map_level']} region={h['region']} → {h['location_key']}")

    canon = _canon_rows()
    reparent: list[tuple[dict, str]] = []   # (dziecko, docelowy parent_key)
    orphan: list[dict] = []
    restore: dict[str, dict] = {}           # parent_key → wiersz kanonu do odtworzenia
    print(f"\nSUB-LOKACJE POD ŚMIECIEM: {len(kids)} (nie kasujemy)")
    for k in kids:
        want = (canon.get(k["key"]) or {}).get("parent_key")
        if want and want in canon:
            exists = q(C, f"SELECT id FROM game_locations WHERE key={esc(want)};", DB)
            if not exists:
                restore[want] = canon[want]
            reparent.append((k, want))
            print(f"  #{k['id']:<5} {k['key']} → wraca pod '{want}'"
                  + ("  (rodzic do odtworzenia z kanonu)" if not exists else ""))
        else:
            orphan.append(k)
            print(f"  #{k['id']:<5} {k['key']} → bez rodzica (kanon nie zna prawdziwego)")

    # Skan całej bazy: żadna referencja do śmiecia nie może zostać niezauważona.
    tables = [t["name"] for t in q(C, "SELECT name FROM sqlite_master WHERE type='table';", DB)]
    refs: list[tuple[str, str, int]] = []
    for t in tables:
        if t == "game_locations":
            continue
        for c in [r["name"] for r in q(C, f"PRAGMA table_info('{t}');", DB)]:
            if "location" not in c.lower():
                continue
            probe = key_list if c.lower().endswith("key") else id_list
            n = q(C, f'SELECT count(*) AS n FROM "{t}" WHERE "{c}" IN ({probe});', DB)[0]["n"]
            if n:
                refs.append((t, c, n))
    print(f"\nINNE REFERENCJE: {len(refs)}")
    for t, c, n in refs:
        print(f"  {t}.{c}: {n}")
    # world_hexes / game_sessions mają własną obsługę niżej; tabele *_log to historia
    # diagnostyczna (nie referencja funkcjonalna) — zostawiamy nietknięte.
    known = {("world_hexes", "location_key"), ("game_sessions", "current_location_id")}
    unknown = [r for r in refs if (r[0], r[1]) not in known and not r[0].endswith("_log")]
    if unknown:
        print("  UWAGA: powyższe wiersze zostaną skasowane razem ze śmieciem "
              "(przypisania NPC/wrogów do lokacji-śmieci).")

    print(f"\nSESJE WSKAZUJĄCE NA ŚMIEĆ: {len(sess)}")
    for s in sess:
        print(f"  sesja {s['id']} (kampania {s['campaign_id']}, "
              + ("kampania ISTNIEJE → tylko odpięcie" if s["campaign_exists"] else "kampania nie istnieje → kasuję sesję") + ")")

    if not a.apply:
        print("\nDRY-RUN — nic nie zmieniono. Uruchom z --apply (najpierw ./scripts/backup_dev.sh).")
        return

    stmts = ["BEGIN;"]
    for key, row in restore.items():
        cols = [c for c in ("key", "label", "description", "location_type", "parent_key", "region",
                            "biome", "location_subtype", "map_icon", "safe_for_rest",
                            "visible_before_visit", "created_by", "review_status") if c in row]
        stmts.append(f"INSERT INTO game_locations ({','.join(cols)}) VALUES "
                     f"({','.join(esc(row[c]) if isinstance(row[c], str) or row[c] is None else str(row[c]) for c in cols)});")
    for kid, want in reparent:
        stmts.append(f"UPDATE game_locations SET parent_key={esc(want)}, "
                     f"parent_id=(SELECT id FROM game_locations WHERE key={esc(want)}) "
                     f"WHERE id={kid['id']};")
    for kid in orphan:
        stmts.append(f"UPDATE game_locations SET parent_id=NULL, parent_key=NULL WHERE id={kid['id']};")
    if hexes:
        stmts.append(f"UPDATE world_hexes SET location_key=NULL WHERE location_key IN ({key_list});")
    for s in sess:
        stmts.append(f"DELETE FROM game_sessions WHERE id={esc(s['id'])};" if not s["campaign_exists"]
                     else f"UPDATE game_sessions SET current_location_id=NULL WHERE id={esc(s['id'])};")
    for t, c, _ in unknown:
        probe = key_list if c.lower().endswith("key") else id_list
        stmts.append(f'DELETE FROM "{t}" WHERE "{c}" IN ({probe});')
    stmts.append(f"DELETE FROM game_locations WHERE id IN ({id_list});")
    stmts.append("COMMIT;")
    write(C, "\n".join(stmts), DB)

    left = q(C, f"SELECT count(*) AS n FROM game_locations WHERE {JUNK_PREDICATE};", DB)[0]["n"]
    print(f"\nGOTOWE: skasowano {len(junk)} lokacji, odpięto {len(hexes)} heksów, "
          f"odtworzono {len(restore)} rodziców z kanonu, przepięto {len(reparent)}, "
          f"osierocono {len(orphan)}. Pozostało śmieci: {left}.")
    print("Pamiętaj: snapshot mapy (snapshot_world_map.py --region <key>) + commit.")


if __name__ == "__main__":
    main()
