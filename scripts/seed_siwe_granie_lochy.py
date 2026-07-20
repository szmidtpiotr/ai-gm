#!/usr/bin/env python3
"""SG-7 (#1481) — lochy Siwych Grań: Sztolnia Umarłego Rodu (farmowalny seed).

Źródło prawdy: docs/world/regions/siwe_granie.md §4 („Sztolnia Umarłego Rodu —
opuszczona kopalnia, farmowalny dungeon seed, tier niżej niż Hutman").

USTALENIE Z KODU (ważne przy dobieraniu bossa):
  W trybie kafelkowym (FAZA L) o tym, z kim walczysz w komnacie bossa, decyduje
  KAFELEK, nie kolumna `game_dungeons.boss_enemy` — `dungeon_tile_service.
  resolve_tile_content` czyta `dungeon_tiles.enemies_json` i skaluje je flagą
  `is_boss`. Dlatego `boss_tile_id` dobrany jest tak, by pasował do lore, a
  `boss_enemy` ustawiony na TEGO SAMEGO wroga (spójność wyświetlania i trybu
  bez kafli).

DRUGIE USTALENIE: `_tile_enemies_allowed` odrzuca kafle, których wrogowie nie
mieszczą się w `enemy_pool` lochu. Pula musi więc zawierać nie tylko wrogów
„fabularnych", ale i tych osadzonych w kaflach kategorii — inaczej ścieżka nie
ma z czego się zbudować.

DODATKOWO (poprawka SG-6): przypisanie `wynaturzony_trup` do Kohlgrundu było
błędem — ten wróg ma `review_status='discarded'` (treść odrzucona). Skrypt
podmienia go na zatwierdzone `wynaturzona_bestia` + `zombie`.

URUCHOMIENIE (wewnątrz kontenera backendu):
    docker cp scripts/seed_siwe_granie_lochy.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_siwe_granie_lochy.py
    docker exec ai-gm-dev-backend-1 python /app/seed_siwe_granie_lochy.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

sys.path.insert(0, "/app")

DUNGEONS = [
    dict(
        key="sztolnia_umarlego_rodu",
        label="Sztolnia Umarłego Rodu",
        location_key="sztolnia_umarlego_rodu",
        rooms=6,
        tile_category_key="jaskinie",
        tile_count=6,
        # kafel 87 „Komnata Kamiennego Strażnika" — golem_stone; strażnik grobu rodu
        boss_tile_id=87,
        boss_enemy="golem_stone",
        # pula: wrogowie fabularni (martwy ród) + wrogowie osadzeni w kaflach
        # kategorii `jaskinie` (bez nich filtr kafli wyciąłby połowę ścieżek)
        enemy_pool=["skeleton", "ghoul", "giant_spider", "cave_bear",
                    "giant_rat", "slime", "wolf"],
        loot_tier="rare",
        chest_loot_table_key="loot_standard",
        boss_loot_table_key="loot_rich",
        room_loot_chance=0.15,
        cooldown_hours=48,
        min_level=2,
        dungeon_difficulty=1,
        rest_heal_pct=20,
        rest_charges=2,
        atmosphere="Sztolnia rodu, którego już nie ma — płytsza i starsza niż Hutman, "
                   "ale schodzi w tę samą ciemność. Zawalone chodniki, pordzewiałe wózki "
                   "na wykrzywionych szynach i przeciąg, który idzie z dołu, nie z góry. "
                   "Rodowe znaki przy każdym rozwidleniu są jeszcze czytelne, jakby ktoś "
                   "je odnawiał. W głębi, tam gdzie kończy się mapa, stoi coś kamiennego, "
                   "co pilnuje grobu — i nie zauważyło jeszcze, że nie ma już czego pilnować.",
    ),
]

UPSERT = """
INSERT INTO game_dungeons
  (key, label, location_key, rooms, enemy_pool, boss_enemy, loot_tier, atmosphere,
   cooldown_hours, min_level, is_active, chest_loot_table_key, boss_loot_table_key,
   room_loot_chance, riddle_source, riddle_max_hints, dungeon_difficulty,
   tile_category_key, tile_count, boss_tile_id, endless_growth_n,
   rest_heal_pct, rest_charges)
VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?,'database',2,?,?,?,?,0,?,?)
ON CONFLICT(key) DO UPDATE SET
  label=excluded.label, location_key=excluded.location_key, rooms=excluded.rooms,
  enemy_pool=excluded.enemy_pool, boss_enemy=excluded.boss_enemy,
  loot_tier=excluded.loot_tier, atmosphere=excluded.atmosphere,
  cooldown_hours=excluded.cooldown_hours, min_level=excluded.min_level,
  chest_loot_table_key=excluded.chest_loot_table_key,
  boss_loot_table_key=excluded.boss_loot_table_key,
  room_loot_chance=excluded.room_loot_chance,
  dungeon_difficulty=excluded.dungeon_difficulty,
  tile_category_key=excluded.tile_category_key, tile_count=excluded.tile_count,
  boss_tile_id=excluded.boss_tile_id, rest_heal_pct=excluded.rest_heal_pct,
  rest_charges=excluded.rest_charges, is_active=1
"""

# Poprawka SG-6: Kohlgrund miał wroga `wynaturzony_trup` (review_status='discarded')
SG6_FIX_OLD = ("kohlgrund", "wynaturzony_trup")
SG6_FIX_NEW = [("kohlgrund", "wynaturzona_bestia", 0.3, 1),
               ("kohlgrund", "zombie", 0.5, 3)]


def fix_sg6(conn: sqlite3.Connection) -> tuple[int, int]:
    loc, bad = SG6_FIX_OLD
    removed = conn.execute(
        "DELETE FROM location_enemy_assignments WHERE location_key=? AND enemy_key=?",
        (loc, bad)).rowcount or 0
    added = 0
    for l, e, s, m in SG6_FIX_NEW:
        added += conn.execute(
            "INSERT OR IGNORE INTO location_enemy_assignments "
            "(location_key, enemy_key, spawn_chance, max_count, is_active) VALUES (?,?,?,?,1)",
            (l, e, float(s), int(m))).rowcount or 0
    keys = [r[0] for r in conn.execute(
        "SELECT enemy_key FROM location_enemy_assignments WHERE location_key=? AND is_active=1 "
        "ORDER BY enemy_key", (loc,))]
    conn.execute("UPDATE game_locations SET enemy_keys=? WHERE key=?",
                 (json.dumps(keys, ensure_ascii=False), loc))
    return removed, added


def verify(conn: sqlite3.Connection) -> list[str]:
    problems = []
    for d in DUNGEONS:
        if not conn.execute("SELECT 1 FROM game_locations WHERE key=? AND is_active=1",
                            (d["location_key"],)).fetchone():
            problems.append(f"{d['key']}: brak lokacji {d['location_key']}")
        for e in d["enemy_pool"] + [d["boss_enemy"]]:
            row = conn.execute(
                "SELECT review_status FROM game_config_enemies WHERE key=?", (e,)).fetchone()
            if not row:
                problems.append(f"{d['key']}: nieznany wróg {e}")
            elif row["review_status"] != "permanent":
                problems.append(f"{d['key']}: wróg {e} ma status {row['review_status']}")
        for t in (d["chest_loot_table_key"], d["boss_loot_table_key"]):
            if not conn.execute("SELECT 1 FROM game_config_loot_tables WHERE key=?", (t,)).fetchone():
                problems.append(f"{d['key']}: brak tabeli łupów {t}")
        bt = conn.execute(
            "SELECT category_key, is_boss_tile, is_active, enemies_json FROM dungeon_tiles WHERE id=?",
            (d["boss_tile_id"],)).fetchone()
        if not bt:
            problems.append(f"{d['key']}: brak kafla bossa {d['boss_tile_id']}")
        else:
            if bt["category_key"] != d["tile_category_key"]:
                problems.append(f"{d['key']}: kafel bossa spoza kategorii {d['tile_category_key']}")
            if not bt["is_boss_tile"] or not bt["is_active"]:
                problems.append(f"{d['key']}: kafel {d['boss_tile_id']} nie jest aktywnym kaflem bossa")
            # boss z kafla MUSI zgadzać się z boss_enemy — w trybie kafelkowym
            # to kafel decyduje, kto stoi w komnacie
            tile_enemies = [e.get("enemy_key") for e in json.loads(bt["enemies_json"] or "[]")]
            if d["boss_enemy"] not in tile_enemies:
                problems.append(f"{d['key']}: boss_enemy={d['boss_enemy']} nie występuje "
                                f"na kaflu bossa (kafel ma {tile_enemies})")
        # czy zostaje dość kafli po filtrze puli wrogów
        pool = set(d["enemy_pool"])
        usable = 0
        for r in conn.execute(
                "SELECT enemies_json FROM dungeon_tiles WHERE category_key=? AND is_active=1 "
                "AND is_boss_tile=0", (d["tile_category_key"],)):
            es = [e.get("enemy_key") for e in json.loads(r["enemies_json"] or "[]")]
            if not es or set(es) <= pool:
                usable += 1
        if usable < d["tile_count"]:
            problems.append(f"{d['key']}: tylko {usable} kafli przechodzi filtr puli "
                            f"(potrzeba ≥{d['tile_count']})")
        else:
            print(f"  kafli dostępnych po filtrze puli: {usable} (potrzeba {d['tile_count']})")
    if conn.execute("SELECT 1 FROM location_enemy_assignments WHERE enemy_key=?",
                    (SG6_FIX_OLD[1],)).fetchone():
        problems.append(f"{SG6_FIX_OLD[1]} (discarded) wciąż jest przypisany do jakiejś lokacji")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    for d in DUNGEONS:
        conn.execute(UPSERT, (
            d["key"], d["label"], d["location_key"], d["rooms"],
            json.dumps(d["enemy_pool"], ensure_ascii=False), d["boss_enemy"],
            d["loot_tier"], d["atmosphere"], d["cooldown_hours"], d["min_level"],
            d["chest_loot_table_key"], d["boss_loot_table_key"], d["room_loot_chance"],
            d["dungeon_difficulty"], d["tile_category_key"], d["tile_count"],
            d["boss_tile_id"], d["rest_heal_pct"], d["rest_charges"],
        ))
        print(f"  loch {d['label']:28s} kafle={d['tile_category_key']}/{d['tile_count']} "
              f"boss={d['boss_enemy']}@kafel{d['boss_tile_id']} min_lvl={d['min_level']}")

    rm, add = fix_sg6(conn)
    print(f"  poprawka SG-6: usunięto {rm} przypisań discarded, dodano {add} zatwierdzonych")

    problems = verify(conn)
    conn.commit()
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
