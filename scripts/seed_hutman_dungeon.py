#!/usr/bin/env python3
"""SG-7b (#1481) — Kopalnia Czarnego Hutmana: endgame krainy + własna kategoria kafli.

Domyka punkt „Dungeon seeds" z checklisty #1481. Blokery zdjęte:
  * Piotr zaakceptował `straznik_rdzenia` jako bossa (review_status='permanent'),
  * kategoria kafli `kopalnia_krasnoludzka` powstaje w tym skrypcie (14 kafli),
    bo w `jaskinie` żadna z 6 komnat bossa (trol, smok, wywerna, lisz, matka
    pająków, golem) nie pasuje do serca mitu krainy.

Co robi:
 1. kategoria kafli `kopalnia_krasnoludzka` (styl + prompt bazowy w konwencji
    pozostałych kategorii),
 2. 14 kafli: 13 zwykłych + komnata bossa „Serce Głębokiego Bicia" ze Strażnikiem
    Rdzenia. Opisy i drzwi pisane ręcznie (content-as-code #1202) — obrazki
    dogenerowuje się osobno: scripts/generate_tiles_batch.py --category kopalnia_krasnoludzka,
 3. loch `kopalnia_czarnego_hutmana` (min_level 7, 8 kafli, cooldown 72 h),
 4. NAPRAWA STATÓW BOSSA: `straznik_rdzenia` przyszedł z planu LLM z szablonowymi
    zerami (attack_bonus 0, damage_bonus 0, xp 150) — tak wygląda KAŻDY boss
    z `created_by='llm_plan'`. Boss endgame z zerowym bonusem do trafienia
    praktycznie nie trafia w bohatera 7+ poziomu. Wartości startowe wyrównane do
    reszty katalogu bossów (Pradawny Troll 80/16/+9, Lisz 90/17/+9) — Numbers
    Policy: do strojenia w Sandboksie.

Idempotentny: kafle rozpoznawane po (kategoria, etykieta); istniejące `image_url`
NIE są nadpisywane, więc ponowny seed nie kasuje wygenerowanej grafiki.

URUCHOMIENIE (wewnątrz kontenera backendu):
    docker cp scripts/seed_hutman_dungeon.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_hutman_dungeon.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

CATEGORY = dict(
    key="kopalnia_krasnoludzka",
    label="Kopalnia Krasnoludzka",
    description="Krasnoludzka kopalnia głębinowa — kute w skale chodniki, szyny wózków, "
                "kołowroty i solne okucia. Im głębiej, tym bliżej Rdzenia.",
    style_modifier="dwarven deep mine interior, hand-carved stone galleries, iron mine cart "
                   "rails, timber and iron pit props, salt-crusted fittings, ore veins "
                   "glinting in the rock, lantern light, industrial underground aesthetic",
    system_prompt="Opisujesz komorę krasnoludzkiej kopalni głębinowej. Skup się na detalach: "
                  "kutym w skale chodniku, szynach i wózkach, belkach i stemplach, solnych "
                  "nalotach, żyłach rudy, kurzu i kapiącej wodzie, świetle lamp. Opis po "
                  "polsku, 2-3 zdania klimatyczne. Używaj zmysłowych szczegółów — co gracz "
                  "czuje, słyszy i widzi pod stopami. W głębi zawsze da się usłyszeć stukanie.",
    base_prompt="dwarven deep mine chamber seen from directly straight above, hand-carved "
                "stone gallery walls forming the irregular boundary of the room, rough rock "
                "floor with iron mine cart rails running across it, timber and iron pit props "
                "bracing the walls, scattered tools, ore chunks and broken cart parts, white "
                "salt crust on the stonework, 2-3 dark tunnel mouths leading off the edges as "
                "passages, warm lantern lighting, painted tabletop RPG battlemap art style, "
                "high detail, strict top-down orthographic overhead view, square map tile, "
                "2D game art, NO perspective, NO side view, flat overhead, no text, no UI",
    sort_order=60,
)

# doors: kierunki wyjść. Ścieżka łączy kafle przez PRZECIWLEGŁE drzwi, więc pula
# musi mieć dużo kafli 3-4 drzwiowych, inaczej budowa ścieżki zapętla się i pada.
# Kafel wejściowy MUSI być bez wrogów (silnik nie odpala walki na kaflu startowym).
TILES = [
    dict(label="Szyb Zjazdowy", doors=["N", "S", "E"], enemies=[],
         desc="Drewniana klatka szybu skrzypi na łańcuchu, choć nikt jej nie ruszał od lat. "
              "Z dołu ciągnie chłodem i zapachem mokrego kamienia. Na desce nad wejściem "
              "ktoś wyskrobał liczbę, a potem ją przekreślił."),
    dict(label="Rozdroże Sztolni", doors=["N", "S", "E", "W"], enemies=[],
         desc="Cztery chodniki zbiegają się pod stemplem grubym jak pień. Na każdej ścianie "
              "wykuto znak innego rodu, a pod nimi strzałki — wszystkie prowadzą w tę samą "
              "stronę, w górę."),
    dict(label="Komora Kołowrotu", doors=["N", "S", "E"], enemies=[{"enemy_key": "skeleton", "count": 2}],
         desc="Wielki kołowrót stoi zaklinowany, lina zwisa w ciemność. Ktoś próbował go "
              "odblokować i został tu na dobre — kości leżą wciąż przy korbie."),
    dict(label="Zalane Chodniki", doors=["N", "S", "W"], enemies=[{"enemy_key": "ghoul", "count": 2}],
         desc="Woda sięga kostek i jest cieplejsza, niż powinna. Pod powierzchnią widać "
              "szyny biegnące w dół i kształty, które nie ruszają się z prądem."),
    dict(label="Kaplica Górnicza", doors=["N", "E", "W"], enemies=[],
         desc="Mała nisza z kamiennym ołtarzem i wyżłobieniem na sól. Świece wypaliły się "
              "do końca, ale wosk jest miękki. Ktoś tu bywa."),
    dict(label="Skład Solny", doors=["N", "S", "E", "W"], enemies=[],
         desc="Ściany pokrywa gruby biały nalot, a pod nogami chrzęszczą kryształy. "
              "To jedyne miejsce w tej kopalni, gdzie stukanie milknie — i każdy górnik "
              "wiedział dlaczego."),
    dict(label="Stare Wyrobisko", doors=["N", "S", "E"],
         enemies=[{"enemy_key": "skeleton", "count": 2}, {"enemy_key": "ghoul", "count": 1}],
         desc="Wybrana do gołej skały komora ze śladami kilofów gęstymi jak łuska. "
              "Porzucone wózki stoją w rzędzie, załadowane rudą, której nikt nie wywiózł."),
    dict(label="Sala Pomp", doors=["N", "S", "W"], enemies=[{"enemy_key": "bladzacy_upior", "count": 1}],
         desc="Rząd żeliwnych pomp milczy nad zbiornikiem czarnej wody. Jedno koło obraca "
              "się powoli, choć nie ma kto go kręcić."),
    dict(label="Nadszybie Głębokiego Bicia", doors=["N", "S", "E", "W"],
         enemies=[{"enemy_key": "wynaturzona_bestia", "count": 1}],
         desc="Stąd zaczęto drążyć w dół dwadzieścia lat temu. Tablica z rozpiską zmian "
              "wisi krzywo, a ostatni wpis urwano w połowie słowa."),
    dict(label="Chodnik Poniżej Linii Soli", doors=["N", "S"],
         enemies=[{"enemy_key": "kamienny_wojownik", "count": 1}],
         desc="Solne okucia kończą się nagle, jakby ktoś uciął je jednym cięciem. Dalej "
              "kamień jest ciepły w dotyku, a stukanie słychać nie w uszach, lecz w zębach."),
    dict(label="Grobowiec Sztygara", doors=["N", "E", "W"],
         enemies=[{"enemy_key": "bladzacy_upior", "count": 1}],
         desc="Nisza zamurowana od środka. Na płycie wykuto imię i jedno zdanie: "
              "„Zamknąłem to, co mogłem”. Mur jest pęknięty od strony grobu."),
    dict(label="Pęknięta Żyła", doors=["N", "S", "E"],
         enemies=[{"enemy_key": "wynaturzona_bestia", "count": 1}],
         desc="Ściana rozeszła się wzdłuż srebrnej żyły, a szczelina pulsuje słabym światłem "
              "w rytm, który zaczynasz mimowolnie odliczać."),
    dict(label="Zawalisko", doors=["N", "S"], enemies=[],
         desc="Strop osiadł i zostawił szczelinę na jednego człowieka. Gruz jest świeży, "
              "a spod niego wystaje kilof z rękojeścią startą do połysku."),
    dict(label="Serce Głębokiego Bicia", doors=["N", "S", "E", "W"], boss=True,
         enemies=[{"enemy_key": "straznik_rdzenia", "count": 1}],
         desc="Komora, do której dowiercili się dwadzieścia lat temu. Nie ma tu rudy ani "
              "soli — jest gładka, kolista ściana z materiału, którego górnicy nie umieli "
              "nazwać, i coś przed nią, co uderza w nią miarowo od środka. Stukanie, które "
              "słychać w całym paśmie, zaczyna się dokładnie tutaj."),
]

DUNGEON = dict(
    key="kopalnia_czarnego_hutmana",
    label="Kopalnia Czarnego Hutmana",
    location_key="kopalnia_czarnego_hutmana",
    rooms=8,
    tile_category_key=CATEGORY["key"],
    tile_count=8,
    boss_tile_label="Serce Głębokiego Bicia",
    boss_enemy="straznik_rdzenia",
    enemy_pool=["skeleton", "ghoul", "bladzacy_upior", "wynaturzona_bestia",
                "kamienny_wojownik"],
    loot_tier="rich",
    chest_loot_table_key="loot_rich",
    boss_loot_table_key="loot_treasure",
    room_loot_chance=0.15,
    cooldown_hours=72,
    min_level=7,
    dungeon_difficulty=2,
    rest_heal_pct=20,
    rest_charges=2,
    atmosphere="Kopalnia, w której zaczęło się Głębokie Bicie. Starszyzna zakazała tu "
               "schodzić, Młotodzierżcy chcą ją odbić, a stukanie niesie się srebrnymi "
               "żyłami po całym paśmie. Solne okucia kończą się w połowie drogi — dalej "
               "nikt ich nie zdążył wykuć. To endgame Siwych Grań: schodzisz nie po rudę, "
               "tylko po odpowiedź.",
)

# Numbers Policy — wartości startowe, do strojenia w Sandboksie.
# Powód: boss z planu LLM przyszedł z szablonowymi zerami (patrz docstring).
BOSS_STATS_FIX = dict(
    key="straznik_rdzenia",
    hp_base=85, ac_base=17, attack_bonus=9,
    damage_die="2d8", damage_bonus=2, attacks_per_turn=1, xp_award=950,
)


def seed_category(conn: sqlite3.Connection) -> str:
    c = CATEGORY
    existing = conn.execute("SELECT key FROM dungeon_tile_categories WHERE key=?", (c["key"],)).fetchone()
    if existing:
        conn.execute(
            "UPDATE dungeon_tile_categories SET label=?, description=?, style_modifier=?, "
            "system_prompt=?, base_prompt=?, sort_order=?, is_active=1 WHERE key=?",
            (c["label"], c["description"], c["style_modifier"], c["system_prompt"],
             c["base_prompt"], c["sort_order"], c["key"]))
        return "UPDATE"
    conn.execute(
        "INSERT INTO dungeon_tile_categories (key, label, description, style_modifier, "
        "system_prompt, base_prompt, sort_order, is_active) VALUES (?,?,?,?,?,?,?,1)",
        (c["key"], c["label"], c["description"], c["style_modifier"], c["system_prompt"],
         c["base_prompt"], c["sort_order"]))
    return "INSERT"


def seed_tiles(conn: sqlite3.Connection) -> tuple[int, int, int]:
    added = updated = 0
    boss_id = None
    for t in TILES:
        row = conn.execute(
            "SELECT id FROM dungeon_tiles WHERE category_key=? AND label=?",
            (CATEGORY["key"], t["label"])).fetchone()
        is_boss = 1 if t.get("boss") else 0
        if row:
            # NIE dotykamy image_url — wygenerowana grafika ma przetrwać reseed
            conn.execute(
                "UPDATE dungeon_tiles SET doors_json=?, room_description=?, enemies_json=?, "
                "is_boss_tile=?, is_active=1, updated_at=datetime('now') WHERE id=?",
                (json.dumps(t["doors"]), t["desc"], json.dumps(t["enemies"], ensure_ascii=False),
                 is_boss, row["id"]))
            tid = row["id"]
            updated += 1
        else:
            cur = conn.execute(
                "INSERT INTO dungeon_tiles (category_key, label, image_gen_prompt, doors_json, "
                "room_description, enemies_json, items_json, active_states_json, "
                "exit_conditions_json, is_boss_tile, is_active) "
                "VALUES (?,?,?,?,?,?,'[]','[]','[]',?,1)",
                (CATEGORY["key"], t["label"], CATEGORY["base_prompt"], json.dumps(t["doors"]),
                 t["desc"], json.dumps(t["enemies"], ensure_ascii=False), is_boss))
            tid = cur.lastrowid
            added += 1
        if is_boss:
            boss_id = tid
    return added, updated, boss_id


def fix_boss_stats(conn: sqlite3.Connection) -> bool:
    f = BOSS_STATS_FIX
    before = conn.execute(
        "SELECT hp_base, ac_base, attack_bonus, damage_die, damage_bonus, xp_award "
        "FROM game_config_enemies WHERE key=?", (f["key"],)).fetchone()
    if not before:
        return False
    conn.execute(
        "UPDATE game_config_enemies SET hp_base=?, ac_base=?, attack_bonus=?, damage_die=?, "
        "damage_bonus=?, attacks_per_turn=?, xp_award=? WHERE key=?",
        (f["hp_base"], f["ac_base"], f["attack_bonus"], f["damage_die"], f["damage_bonus"],
         f["attacks_per_turn"], f["xp_award"], f["key"]))
    print(f"  boss {f['key']}: HP {before['hp_base']}→{f['hp_base']}, AC {before['ac_base']}→{f['ac_base']}, "
          f"atak {before['attack_bonus']:+d}→{f['attack_bonus']:+d}, "
          f"obr. {before['damage_die']}+{before['damage_bonus']}→{f['damage_die']}+{f['damage_bonus']}, "
          f"XP {before['xp_award']}→{f['xp_award']}")
    return True


DUNGEON_UPSERT = """
INSERT INTO game_dungeons
  (key, label, location_key, rooms, enemy_pool, boss_enemy, loot_tier, atmosphere,
   cooldown_hours, min_level, is_active, chest_loot_table_key, boss_loot_table_key,
   room_loot_chance, riddle_source, riddle_max_hints, dungeon_difficulty,
   tile_category_key, tile_count, boss_tile_id, endless_growth_n, rest_heal_pct, rest_charges)
VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?,'database',2,?,?,?,?,0,?,?)
ON CONFLICT(key) DO UPDATE SET
  label=excluded.label, location_key=excluded.location_key, rooms=excluded.rooms,
  enemy_pool=excluded.enemy_pool, boss_enemy=excluded.boss_enemy, loot_tier=excluded.loot_tier,
  atmosphere=excluded.atmosphere, cooldown_hours=excluded.cooldown_hours,
  min_level=excluded.min_level, chest_loot_table_key=excluded.chest_loot_table_key,
  boss_loot_table_key=excluded.boss_loot_table_key, room_loot_chance=excluded.room_loot_chance,
  dungeon_difficulty=excluded.dungeon_difficulty, tile_category_key=excluded.tile_category_key,
  tile_count=excluded.tile_count, boss_tile_id=excluded.boss_tile_id,
  rest_heal_pct=excluded.rest_heal_pct, rest_charges=excluded.rest_charges, is_active=1
"""


def verify(conn: sqlite3.Connection, boss_tile_id: int) -> list[str]:
    p = []
    d = DUNGEON
    if not conn.execute("SELECT 1 FROM game_locations WHERE key=? AND is_active=1",
                        (d["location_key"],)).fetchone():
        p.append(f"brak lokacji {d['location_key']}")
    for e in set(d["enemy_pool"]) | {d["boss_enemy"]}:
        row = conn.execute("SELECT review_status FROM game_config_enemies WHERE key=?", (e,)).fetchone()
        if not row:
            p.append(f"nieznany wróg {e}")
        elif row["review_status"] != "permanent":
            p.append(f"wróg {e} ma status {row['review_status']}")
    # każdy wróg z kafli musi mieścić się w puli lochu — inaczej filtr wytnie kafel
    pool = set(d["enemy_pool"]) | {d["boss_enemy"]}
    for t in TILES:
        for e in t["enemies"]:
            if e["enemy_key"] not in pool:
                p.append(f"kafel {t['label']!r}: wróg {e['enemy_key']} spoza puli lochu")
    # kafel bossa musi zawierać dokładnie tego bossa (w trybie kafelkowym kafel rządzi)
    bt = conn.execute("SELECT enemies_json, is_boss_tile, category_key FROM dungeon_tiles WHERE id=?",
                      (boss_tile_id,)).fetchone()
    if not bt or not bt["is_boss_tile"]:
        p.append("kafel bossa nie istnieje lub nie ma flagi bossa")
    else:
        ek = [e.get("enemy_key") for e in json.loads(bt["enemies_json"] or "[]")]
        if d["boss_enemy"] not in ek:
            p.append(f"boss_enemy={d['boss_enemy']} nie stoi na kaflu bossa ({ek})")
    n_free = sum(1 for t in TILES if not t["enemies"] and not t.get("boss"))
    if n_free == 0:
        p.append("brak kafla bez wrogów — silnik nie ma gdzie postawić wejścia")
    n_tiles = conn.execute("SELECT count(*) c FROM dungeon_tiles WHERE category_key=? AND is_active=1",
                           (CATEGORY["key"],)).fetchone()["c"]
    if n_tiles < d["tile_count"]:
        p.append(f"kategoria ma {n_tiles} kafli, loch potrzebuje {d['tile_count']}")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    print(f"  kategoria kafli {CATEGORY['key']}: {seed_category(conn)}")
    added, updated, boss_tile_id = seed_tiles(conn)
    print(f"  kafle: {added} nowych, {updated} zaktualizowanych, kafel bossa id={boss_tile_id}")
    fix_boss_stats(conn)

    d = DUNGEON
    conn.execute(DUNGEON_UPSERT, (
        d["key"], d["label"], d["location_key"], d["rooms"],
        json.dumps(d["enemy_pool"], ensure_ascii=False), d["boss_enemy"], d["loot_tier"],
        d["atmosphere"], d["cooldown_hours"], d["min_level"], d["chest_loot_table_key"],
        d["boss_loot_table_key"], d["room_loot_chance"], d["dungeon_difficulty"],
        d["tile_category_key"], d["tile_count"], boss_tile_id, d["rest_heal_pct"], d["rest_charges"],
    ))
    print(f"  loch {d['label']}: kafle={d['tile_category_key']}/{d['tile_count']} "
          f"boss={d['boss_enemy']}@kafel{boss_tile_id} min_lvl={d['min_level']} cooldown={d['cooldown_hours']}h")

    no_img = conn.execute(
        "SELECT count(*) c FROM dungeon_tiles WHERE category_key=? AND (image_url IS NULL OR image_url='')",
        (CATEGORY["key"],)).fetchone()["c"]
    problems = verify(conn, boss_tile_id)
    conn.commit()
    conn.close()
    if no_img:
        print(f"  UWAGA: {no_img} kafli bez grafiki — dogeneruj: "
              f"python3 scripts/generate_tiles_batch.py --category {CATEGORY['key']}")
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
