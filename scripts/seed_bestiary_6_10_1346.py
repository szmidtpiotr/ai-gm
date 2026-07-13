#!/usr/bin/env python3
"""Issue #1346 — bestiariusz lvl 6-10: wypełnij pasma + generyczni + tereny.

Follow-up contentowy do code-fixa #1345 (siatka poszerzająca pulę). Diagnoza:
pasma lvl 6-10 były cienkie — lvl 6-9 tylko `elite`, lvl 10 tylko `boss` (5),
zero wrogów generycznych (pusty terrain_tags). Anti-repeat wymuszał powtórki na
trakcie/równinie/rzece przy wysokich poziomach.

Ten seed dosiewa 12 realnych wrogów world_scope='global'+permanent do pasm 6-10:

  • 5× standard (min 6, max 10) — teren road/plains/river/swamp/hills/forest,
  • 4× elite (min 8, max 10) — prawdziwe elity górnej połówki (nie tylko bossy),
  • 3× generyczni (pusty terrain_tags, lvl 6-10) — łatają dowolny cienki teren.

Nazwy = opisowe polskie rzeczowniki (konwencja generycznego bestiariusza jak
#1369; nie postacie fabularne). Wartości bojowe = STARTING VALUES (Numbers Policy),
kalibrowane do istniejącej skali standard/elite — strojlne w Sandboxie.

Idempotentny (INSERT OR REPLACE). Tworzy loot_<key> i auto-populuje łupy.

Run inside dev backend container:
    docker exec -i ai-gm-dev-backend-1 python3 - < scripts/seed_bestiary_6_10_1346.py
"""
from __future__ import annotations

import sqlite3
import sys

DB_PATH = "/data/ai_gm.db"

# key, label, tier, hp, ac, atk, die, dmg_bonus, apt, xp, min_lvl, max_lvl,
#   terrain_tags (None = generyczny), fear_aura, fear_dc, description
NEW_ENEMIES = [
    # ── STANDARD lvl 6-10 (teren) ──
    ("rozbojnik_traktowy", "Rozbójnik Traktowy", "standard", 30, 14, 6, "d8", 2, 1, 175,
     6, 10, "road,plains", 0, 12,
     "Zaprawiony w bojach zbój z blizną przez policzek i kuszą u pasa. Ściąga myto "
     "z każdego, kto samotnie wjedzie na jego odcinek traktu — zapłacisz monetą albo krwią."),
    ("lowca_rubiezy", "Łowca Rubieży", "standard", 28, 14, 6, "d8", 1, 1, 170,
     6, 10, "road,forest,heath", 0, 12,
     "Milczący tropiciel w wilczej skórze, zna każdą ścieżkę pogranicza. Strzela zza "
     "drzew i znika, zanim opadnie cięciwa — poluje na ludzi tak samo jak na zwierza."),
    ("bagienny_topielec", "Bagienny Topielec", "standard", 34, 13, 6, "d8", 2, 1, 185,
     6, 10, "river,swamp", 0, 12,
     "Nabrzmiały trup wciągnięty niegdyś pod wodę, teraz sunie mętnym nurtem. Chwyta "
     "za kostki brodzących i ściąga w głębinę, żeby dołączyli do jego cichej gromady."),
    ("stepowy_grasant", "Stepowy Grasant", "standard", 30, 14, 6, "d10", 1, 1, 180,
     6, 10, "plains,hills", 0, 12,
     "Konny łupieżca z rozłogów, w kożuchu podbitym zdobyczną skórą. Nadjeżdża z "
     "kurzem na horyzoncie i bierze co się da — bydło, ziarno, ludzi na sprzedaż."),
    ("rzeczny_oprych", "Rzeczny Oprych", "standard", 32, 14, 6, "d8", 2, 1, 180,
     6, 10, "river,road", 0, 12,
     "Przewoźnik, który dawno porzucił uczciwe wiosło. Czeka przy brodzie i mostku, "
     "a gdy podróżny sięgnie po sakiewkę za przeprawę — dostaje bosakiem między oczy."),

    # ── ELITE lvl 8-10 (prawdziwe elity górnej połówki) ──
    ("hetman_rozbojcow", "Hetman Rozbójców", "elite", 50, 16, 8, "d10", 2, 1, 420,
     8, 10, "road,plains,ruins", 0, 12,
     "Wódz watahy zbójeckiej w zrabowanej kolczudze i płaszczu z niedźwiedzia. Rządzi "
     "traktem twardą ręką i toporem — jego ludzie boją się go bardziej niż stryczka."),
    ("mrozny_wilkolak", "Mroźny Wilkołak", "elite", 48, 15, 8, "2d6", 2, 1, 450,
     8, 10, "forest,hills,snow", 0, 12,
     "Przeklęty myśliwy, którego zima zamieniła w bestię o srebrnym karku. Poluje w "
     "mroźne noce, a jego wycie ścina krew — pazur rozdziera kolczugę jak płótno."),
    ("bagienna_jedza", "Bagienna Jędza", "elite", 45, 14, 7, "d10", 2, 1, 430,
     8, 10, "river,swamp,forest", 0, 12,
     "Stara wiedźma z mokradeł, palce jak korzenie, oczy jak ślepia ropuchy. Miesza w "
     "kotle klątwy i mgły, a kto zboczy z grobli w jej ostęp, rzadko wraca sobą."),
    ("kamienny_wojownik", "Kamienny Wojownik", "elite", 55, 17, 7, "2d6", 2, 1, 440,
     8, 10, "mountain,ruins,dungeon,road", 0, 12,
     "Zbudzony strażnik z runicznego głazu, ciężki i nieustępliwy jak lawina. Broni "
     "starych szlaków i ruin — nie czuje bólu, nie zna litości, nie zna zmęczenia."),

    # ── GENERYCZNI (pusty terrain_tags — dowolny hex) ──
    ("wynaturzona_bestia", "Wynaturzona Bestia", "elite", 46, 14, 7, "d12", 2, 1, 400,
     6, 10, None, 0, 12,
     "Zwierz spaczony czymś, co nie powinno chodzić po tym świecie — zbyt wiele kończyn, "
     "zbyt wiele zębów. Trafia się wszędzie, gdzie skaza sięgnęła ziemi."),
    ("najemny_zabojca", "Najemny Zabójca", "standard", 34, 15, 7, "d8", 2, 1, 200,
     6, 10, None, 0, 12,
     "Cichy człowiek bez herbu i imienia, płatny za jeden precyzyjny cios. Pojawia się "
     "na każdym trakcie i w każdym zaułku — bo złoto na kontrakt znajdzie się wszędzie."),
    ("bladzacy_upior", "Błądzący Upiór", "elite", 40, 15, 7, "d8", 2, 1, 380,
     7, 10, None, 1, 13,
     "Dusza, która nie znalazła spoczynku, wlecze się przez świat niesiona żalem i "
     "gniewem. Chłód bije od niej na krok — samo jej zbliżenie ściska serce strachem."),
]


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        from app.services.world_service import _auto_populate_enemy_loot
    except Exception:
        _auto_populate_enemy_loot = None

    added, looted = 0, 0
    for (key, label, tier, hp, ac, atk, die, dbon, apt, xp, min_lvl, max_lvl,
         tags, fear, fear_dc, desc) in NEW_ENEMIES:
        loot_key = f"loot_{key}"
        conn.execute(
            """
            INSERT OR REPLACE INTO game_config_enemies
              (key, label, tier, hp_base, ac_base, attack_bonus, damage_die,
               damage_bonus, attacks_per_turn, xp_award, description, terrain_tags,
               min_level, max_level, fear_aura, fear_dc, world_scope, review_status,
               is_active, loot_table_key, drop_chance, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'global','permanent',1,?,?, 'seed')
            """,
            (key, label, tier, hp, ac, atk, die, dbon, apt, xp, desc, tags,
             min_lvl, max_lvl, fear, fear_dc, loot_key, 1.0),
        )
        conn.execute(
            "INSERT OR IGNORE INTO game_config_loot_tables (key, label, gold_min, gold_max) "
            "VALUES (?,?,?,?)",
            (loot_key, f"Łupy: {label}", 3, 20),
        )
        if _auto_populate_enemy_loot:
            try:
                _auto_populate_enemy_loot(conn, key, tier, label)
                looted += 1
            except Exception as e:  # noqa: BLE001
                print(f"  loot auto-populate skip {key}: {e}")
        added += 1
        gen = "generyczny" if tags is None else tags
        print(f"  + {key:20s} [{tier}] lvl {min_lvl}-{max_lvl} tags={gen}")

    conn.commit()
    print(f"\nOK: +{added} wrogów lvl 6-10, {looted} z lootem.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
