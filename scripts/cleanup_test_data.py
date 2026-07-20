#!/usr/bin/env python3
"""Sprzątanie danych-śmieci po testach (#941/#1382/#1480/#1487 Faza 3).

Suity testowe i ręczne przebiegi zostawiają w bazie DEV rekordy, po których nikt nie
sprząta. Od #1487 Fazy 2 pytest pracuje na kopii bazy, ale pozostają inne kanały
(Playwright z panelu admina — #1488, MCP, ręczne testy przez API), więc ten skrypt
zostaje jako stała sieć bezpieczeństwa (cron, patrz `--apply`).

Co kasuje AUTOMATYCZNIE (tylko rzeczy jednoznacznie martwe):
  1. lokacje o kluczach testowych (`test_*`, `__test*`, `*_test_*`, `issue<N>*`)
  2. sesje wskazujące na nieistniejącą kampanię
  3. postacie, których kampania nie istnieje, o testowej nazwie
  4. konta testowe (`test<cyfry>_*`) bez ani jednej kampanii i postaci

Czego NIE rusza (świadomie — raportuje i zostawia decyzję człowiekowi):
  * sub-lokacji pod śmieciem — prawdziwy rodzic jest odtwarzany z kanonu contentu
    (`data/seeds/content/game_locations.json`) i dziecko wraca pod niego; gdy kanon go
    nie zna, dziecko zostaje bez rodzica, ale nigdy nie ginie
  * klonów `[SBX]`/`[SCN]` z żywą kampanią — sandbox czyści je sam przy każdym setupie
  * kont `ai_test_*` — to seed trybu testowego, nie śmieć
  * kampanii — bywają nazwane numerem issue i służą do wglądu

Domyślnie DRY-RUN. Zapis dopiero z --apply (zrób wcześniej ./scripts/backup_dev.sh).

    python3 scripts/cleanup_test_data.py            # raport
    python3 scripts/cleanup_test_data.py --apply    # sprzątanie
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


def section_locations(C, DB) -> tuple[list[str], str]:
    """Lokacje-śmieci + wszystko, co na nie wskazuje. Zwraca (SQL, podsumowanie)."""
    junk = q(C, f"SELECT id,key,label,region FROM game_locations WHERE {JUNK_PREDICATE} ORDER BY id;", DB)
    if not junk:
        print("LOKACJE: brak śmieci.")
        return [], "lokacje 0"
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
    reparent: list[tuple[dict, str]] = []  # (dziecko, docelowy parent_key)
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

    stmts: list[str] = []
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

    if hexes:
        print("  UWAGA: odpięto heksy mapy — po --apply zrób snapshot regionu "
              "(snapshot_world_map.py --region <key>) i zacommituj.")
    return stmts, (f"lokacje {len(junk)}, heksy odpięte {len(hexes)}, "
                   f"rodzice z kanonu {len(restore)}, przepięte {len(reparent)}, osierocone {len(orphan)}")


# Kasujemy PO WARUNKU, nie po liście id: część sesji ma `id` NULL (9 sztuk na DEV),
# a `WHERE id IN (...)` nigdy takiego wiersza nie złapie — cicho zostawałyby w bazie.
ORPHAN_SESSION_WHERE = "campaign_id NOT IN (SELECT id FROM campaigns)"


def section_orphan_sessions(C, DB) -> tuple[list[str], str]:
    """Sesje wskazujące na nieistniejącą kampanię — jednoznacznie martwe."""
    rows = q(C, f"SELECT id, campaign_id FROM game_sessions WHERE {ORPHAN_SESSION_WHERE};", DB)
    print(f"\nOSIEROCONE SESJE: {len(rows)}")
    if not rows:
        return [], "sesje 0"
    for r in rows[:10]:
        print(f"  sesja {r['id'] or '(bez id)'} → kampania {r['campaign_id']} (nie istnieje)")
    if len(rows) > 10:
        print(f"  … i {len(rows) - 10} więcej")
    return [f"DELETE FROM game_sessions WHERE {ORPHAN_SESSION_WHERE};"], f"sesje {len(rows)}"


def section_orphan_characters(C, DB) -> tuple[list[str], str]:
    """Postacie testowe bez kampanii + kaskada po `character_id`.

    Klony `[SBX]`/`[SCN]` z ŻYWĄ kampanią zostają — sandbox czyści je sam przy setupie.
    """
    # Klasy znaków `[0-9]` działają w GLOB, nie w LIKE. Nazw seedowych (`ai_test*`)
    # celowo tu nie ma — seed nie jest śmieciem (#1488).
    rows = q(C, "SELECT id, name, campaign_id FROM characters "
                "WHERE (name GLOB 'TEST[0-9]*' OR name LIKE '[[]SBX]%' OR name LIKE '[[]SCN]%') "
                "  AND (campaign_id IS NULL OR campaign_id NOT IN (SELECT id FROM campaigns));", DB)
    print(f"\nOSIEROCONE POSTACIE TESTOWE: {len(rows)}")
    if not rows:
        return [], "postacie 0"
    for r in rows:
        print(f"  #{r['id']} {r['name']} (kampania {r['campaign_id'] or '—'} nie istnieje)")
    ids = ",".join(str(r["id"]) for r in rows)
    stmts = []
    for t in [x["name"] for x in q(C, "SELECT name FROM sqlite_master WHERE type='table';", DB)]:
        if t == "characters":
            continue
        cols = [c["name"] for c in q(C, f"PRAGMA table_info('{t}');", DB)]
        if "character_id" in cols:
            n = q(C, f'SELECT count(*) AS n FROM "{t}" WHERE character_id IN ({ids});', DB)[0]["n"]
            if n:
                print(f"    ↳ {t}: {n} powiązanych wierszy")
                stmts.append(f'DELETE FROM "{t}" WHERE character_id IN ({ids});')
    stmts.append(f"DELETE FROM characters WHERE id IN ({ids});")
    return stmts, f"postacie {len(rows)}"


def section_orphan_users(C, DB) -> tuple[list[str], str]:
    """Konta z testów (`test<cyfry>_*`) bez ani jednej kampanii i postaci.

    `ai_test_*` to seed trybu testowego — nigdy nie ruszamy.
    """
    rows = q(C, "SELECT id, username FROM users WHERE username GLOB 'test[0-9]*' "
                "AND id NOT IN (SELECT owner_user_id FROM campaigns WHERE owner_user_id IS NOT NULL) "
                "AND id NOT IN (SELECT user_id FROM characters WHERE user_id IS NOT NULL);", DB)
    print(f"\nOSIEROCONE KONTA TESTOWE: {len(rows)}")
    if not rows:
        return [], "konta 0"
    for r in rows:
        print(f"  #{r['id']} {r['username']} (0 kampanii, 0 postaci)")
    ids = ",".join(str(r["id"]) for r in rows)
    return [f"DELETE FROM users WHERE id IN ({ids});"], f"konta {len(rows)}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="wykonaj zmiany (domyślnie dry-run)")
    ap.add_argument("--container", default="ai-gm-dev-backend-1")
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()
    C, DB = a.container, a.db

    stmts: list[str] = []
    summary: list[str] = []
    for section in (section_locations, section_orphan_sessions,
                    section_orphan_characters, section_orphan_users):
        s, info = section(C, DB)
        stmts += s
        summary.append(info)

    if not stmts:
        print("\nBaza czysta — nic do sprzątania.")
        return
    if not a.apply:
        print("\nDRY-RUN — nic nie zmieniono. Uruchom z --apply "
              "(najpierw ./scripts/backup_dev.sh).")
        return

    write(C, "BEGIN;\n" + "\n".join(stmts) + "\nCOMMIT;", DB)
    left = q(C, f"SELECT count(*) AS n FROM game_locations WHERE {JUNK_PREDICATE};", DB)[0]["n"]
    print(f"\nGOTOWE: {'; '.join(summary)}. Pozostało lokacji-śmieci: {left}.")


if __name__ == "__main__":
    main()
