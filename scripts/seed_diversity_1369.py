#!/usr/bin/env python3
"""Issue #1369 — seed różnorodności spotkań poz. 1-2 dla road/plains/bridge/river.

Diagnoza #1369: realna pula wrogów poz. 1-2 na trakcie to praktycznie rodzina
bandytów (+ śmieci testowe). Ten seed:

  1. Dodaje 5 realnych wrogów poz. 1-2 dla terenów road/plains/heath/snow/river
     (mapowanych z hex_type w encounter_service #1369): dziki pies, wilk stepowy,
     zbieg, kłusownik, pijawczy rój.
  2. Rozszerza istniejącego `wolf` o teren road,plains (dziś tylko forest/hills/
     wilderness) — „wilk na trakcie".
  3. Przeklasyfikowuje rekordy testowe/placeholdery (enemy, old_man, s2_pw_*,
     s4_pw_*, goblin_u31, unknown_attacker) na world_scope='template', żeby zniknęły
     z puli i z list admina (silnik i tak filtruje je guardem #1369, to sprzątanie DB).

Idempotentny (INSERT OR REPLACE + UPDATE). Tworzy loot_<key> i auto-populuje łupy.
Wartości bojowe = STARTING VALUES (Numbers Policy), strojlne w Sandboxie.

Run inside dev backend container:
    docker exec -i ai-gm-dev-backend-1 python3 - < scripts/seed_diversity_1369.py
"""
from __future__ import annotations

import sqlite3
import sys

DB_PATH = "/data/ai_gm.db"

# key, label, tier, hp, ac, atk, die, dmg_bonus, apt, xp, terrain_tags, description
NEW_ENEMIES = [
    ("dziki_pies", "Dziki Pies", "weak", 8, 12, 2, "d4", 0, 1, 15,
     "road,plains,heath,hills",
     "Wychudzony kundel z nastroszonym karkiem. Poluje w sforze przy traktach i "
     "pustkowiach — pojedynczo tchórzliwy, w watasze zajada się padliną i podróżnymi."),
    ("wilk_stepowy", "Wilk Stepowy", "standard", 12, 12, 3, "d6", 0, 1, 30,
     "road,plains,wilderness",
     "Szary drapieżnik równin o zapadniętych bokach i żółtych ślepiach. Trzyma się "
     "traktów i rozłogów, gdzie łatwiej dopaść zabłąkanego wędrowca."),
    ("zbieg", "Zbieg", "standard", 10, 12, 2, "d6", 0, 1, 28,
     "road,plains,forest",
     "Dezerter w wyliniałym kaftanie, z wyszczerbionym mieczem. Napada na trakcie z "
     "desperacji — nie ma dokąd wrócić, więc bierze co znajdzie przy pasie."),
    ("klusownik", "Kłusownik", "weak", 8, 12, 2, "d6", 0, 1, 18,
     "road,forest,heath,hills",
     "Milczek w skórzniach, z krótkim łukiem i sidłami u pasa. Zna każdą ścieżkę i "
     "strzela zza krzaka — nie znosi świadków swoich wnyków."),
    ("pijawczy_roj", "Pijawczy Rój", "weak", 6, 11, 1, "d4", 0, 2, 12,
     "river,swamp",
     "Kłąb czarnych pijawek grubości palca, sunący brzegiem wody. Oblepia nogi brodzących "
     "i wysysa krew, zanim ofiara zdąży wyjść na suchy ląd."),
]

JUNK_KEYS = [
    "enemy", "unknown_attacker", "old_man",
    "s2_pw_bandyta_lucznik", "s2_pw_custom_stats",
    "s4_pw_kaplan", "s4_pw_osilek", "goblin_u31",
]


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        from app.services.world_service import _auto_populate_enemy_loot
    except Exception:
        _auto_populate_enemy_loot = None

    added, looted = 0, 0
    for (key, label, tier, hp, ac, atk, die, dbon, apt, xp, tags, desc) in NEW_ENEMIES:
        loot_key = f"loot_{key}"
        conn.execute(
            """
            INSERT OR REPLACE INTO game_config_enemies
              (key, label, tier, hp_base, ac_base, attack_bonus, damage_die,
               damage_bonus, attacks_per_turn, xp_award, description, terrain_tags,
               min_level, max_level, world_scope, review_status, is_active,
               loot_table_key, drop_chance, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,2,'global','permanent',1,?,?, 'seed')
            """,
            (key, label, tier, hp, ac, atk, die, dbon, apt, xp, desc, tags,
             loot_key, 1.0),
        )
        conn.execute(
            "INSERT OR IGNORE INTO game_config_loot_tables (key, label, gold_min, gold_max) "
            "VALUES (?,?,?,?)",
            (loot_key, f"Łupy: {label}", 1, 6),
        )
        if _auto_populate_enemy_loot:
            try:
                _auto_populate_enemy_loot(conn, key, tier, label)
                looted += 1
            except Exception as e:  # noqa: BLE001
                print(f"  loot auto-populate skip {key}: {e}")
        added += 1
        print(f"  + {key:16s} [{tier}] tags={tags}")

    # „wilk na trakcie" — rozszerz istniejącego wolfa o road,plains (jeśli istnieje).
    row = conn.execute(
        "SELECT terrain_tags FROM game_config_enemies WHERE key='wolf'"
    ).fetchone()
    if row:
        tags = [t.strip() for t in (row["terrain_tags"] or "").split(",") if t.strip()]
        for extra in ("road", "plains"):
            if extra not in tags:
                tags.append(extra)
        conn.execute(
            "UPDATE game_config_enemies SET terrain_tags=? WHERE key='wolf'",
            (",".join(tags),),
        )
        print(f"  ~ wolf terrain_tags -> {','.join(tags)}")

    # Sprzątnięcie śmieci: template scope (poza pulą + poza listą global).
    reclassed = 0
    for k in JUNK_KEYS:
        cur = conn.execute(
            "UPDATE game_config_enemies SET world_scope='template' "
            "WHERE key=? AND world_scope='global'",
            (k,),
        )
        if cur.rowcount:
            reclassed += cur.rowcount
            print(f"  x {k:24s} -> world_scope=template")

    conn.commit()
    print(f"\nOK: +{added} wrogów, {looted} z lootem, {reclassed} śmieci przeklasyfikowanych.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
