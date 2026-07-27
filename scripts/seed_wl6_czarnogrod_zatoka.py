#!/usr/bin/env python3
"""WL-6 (#1504) — Czarnogród + Zatoka Topielców: pełne huby + obsada.

Źródło prawdy: docs/world/regions/wybrzeze_lez.md §2/§7/§9/§10. Wzorzec:
scripts/seed_szept_koron.py (CB-5, hub+mapa lokalna) + seed_czarnobor_obsada.py
(CB-5, frakcje+NPC+przypisania). Ta sama mechanika, inna kraina.

Zawartość zastana (NIE tworzę od zera — rozwijam):
  makro: czarnogrod_port (id 55), zatoka_topielcow (106), wybrzeze_lez (105) — na hexach (WL-3)
  suby Czarnogrodu (6): Czarny Targ, Latarnia Topielców, Nabrzeże, Pod Topielcem,
                        Kuźnia Portowa, Izba Chirurga
  suby Zatoki (6): Jaskinie Skarbów, Karczma Kapitańska, Pirackie Doki, Rada Piracka,
                   Kuźnia Kotwiczna, Izba Znachora
  NPC (6): Ruda Magda, Doktor Szkalpel, Kapitan Smolny, Wielki Borek, Halina Morska, Florian

Co robi ten skrypt:
  1. NOWY sub Czarnogrodu — Dzielnica Wyspiarzy (diaspora, lore §7/§10).
  2. Wzbogaca opisy kluczowych subów (Zatoka 4 nazwane + Czarny Targ + diaspora).
  3. Buduje mapę lokalną (map_level=1) dla obu hubów — bez niej wejście do huba
     nie pokazuje subów (FAZA ML #993; auto_assign_local_hex + normalize).
  4. Frakcje: korona, rada_piracka, diaspora_wyspiarzy.
  5. NPC: Kapitan Roggen (Korona/blokada), Taio (starszy diaspory),
     Nakea (kapitanka-przemytniczka/Czarny Targ), Malua (szefowa doków),
     Ravu (egzekutor Rady). Florianowi i Smolnemu dopisuje role wg lore.
  6. Przypisania NPC → lokacja + przelicza game_locations.npc_keys.

Idempotentny — można puszczać wielokrotnie (INSERT OR IGNORE + UPDATE refresh).

URUCHOMIENIE (wewnątrz kontenera backendu):
    docker cp scripts/seed_wl6_czarnogrod_zatoka.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_wl6_czarnogrod_zatoka.py
    docker exec ai-gm-dev-backend-1 python /app/seed_wl6_czarnogrod_zatoka.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.local_hex_service import (  # noqa: E402
    auto_assign_local_hex,
    get_local_hexes,
    normalize_hub_local_hexes,
)
from app.services.location_factory import LocationSource, create_location  # noqa: E402

REGION = "wybrzeze_lez"

HUB_CZARNOGROD = "czarnogrod_port"
HUB_ZATOKA = "zatoka_topielcow"

# ── 1. NOWY sub: Dzielnica Wyspiarzy (diaspora, lore §7 — własna dzielnica portowa)
DIASPORA_SUB = dict(
    key="czarnogrod_dzielnica_wyspiarzy", label="Czarnogród: Dzielnica Wyspiarzy",
    subtype="islander-quarter", icon="town", safe=1, tier=2, biome="coast",
    desc="Portowa dzielnica ludu bez domu — pomosty, sieci i łodzie o wysokich "
         "dziobach wciśnięte między czarnogrodzkie spichlerze. Wyspiarze przybili tu "
         "dwa pokolenia temu, gdy Sztorm Wieczny zamknął im drogę do ojczyzny, i już "
         "nie odpłynęli. Pachnie wędzoną rybą, obcymi ziołami i solą; wieczorem znad "
         "wody niesie się pieśń w języku, którego w Czarnogrodzie nikt inny nie zna. "
         "Tu obcy wyspiarz znajdzie nocleg, wieści i jedyny na Kresach kąt, który "
         "diaspora nazywa swoim.",
    atmo="Kołyszące się latarnie na masztach łodzi, mokre deski pomostów i cichy, "
         "monotonny śpiew starych rybaczek naprawiających sieci po zmroku.",
)

# ── 2. Wzbogacone opisy zastanych subów (UPDATE — refresh, nie nadpisuje reszty) ──
SUB_DESCRIPTIONS = {
    # Zatoka Topielców — 4 nazwane suby z wizytówki/lore
    "zatoka_rada_piracka":
        "Sala Rady Pirackiej w sercu wyspiarskiej twierdzy — kamienny półokrąg z "
        "pięcioma kapitańskimi ławami. Cztery są zajęte; PIĄTA STOI PUSTA, odkąd "
        "zaginął jej właściciel, a fotel jest do wzięcia dla tego, kto zbierze dość "
        "głosów, złota i noży. Rada rządzi Zatoką, dzieli łupy i decyduje, czyj "
        "statek pływa, a czyj idzie na dno. Kto wchodzi tu bez zaproszenia, wychodzi "
        "rzadko.",
    "zatoka_kapitanska_karczma":
        "Kapitańska Karczma — najgłośniejsza knajpa twierdzy, gdzie kapitanowie i ich "
        "załogi piją, grają i załatwiają spory szablą, nie słowem. Tu werbuje się "
        "załogę na rejs, kupuje wieści o kursach koronnych konwojów i słyszy pierwsze "
        "plotki o pustym fotelu Rady. Za stołem w rogu ktoś zawsze obserwuje drzwi.",
    "zatoka_pirackie_doki":
        "Pirackie Doki — smoliste pochylnie, na których łata się czarne galery po "
        "sztormach i abordażach. Przy robocie tłoczą się niewolnicy i zdesperowani "
        "wolni; pachnie smołą, potem i przypływem. Stąd wypływają wszystkie rejsy "
        "Zatoki i tu wraca łup — jeśli morze i latarnia pozwolą.",
    "zatoka_jaskinie_skarbow":
        "Jaskinie Skarbów — kręty labirynt nadmorskich grot, w których kapitanowie "
        "chowają zdobycze za pułapkami i strażnikami. Ale coś w tych korytarzach "
        "przecieka: klątwa spod dna sprawia, że łupy złożone tu za długo wracają "
        "jako nieumarli obrońcy. Farmowalny loch — im głębiej, tym bogaciej i tym "
        "martwiej.",
    # Czarnogród — Czarny Targ (kontrabanda) + diaspora
    "czarnogrod_giełda_kontrabandy":
        "Czarny Targ — nieoficjalny bazar pod molem, gdzie kupisz wszystko, o co "
        "Korona każe pytać dwa razy: sól bez glejtu, towar „z głębin”, truciznę, a "
        "za odpowiednią cenę i człowieka. Tu zaczyna się szmugiel-pętla: co tanie na "
        "Wybrzeżu, w Nizinach warte krocie — o ile przemkniesz przez rogatki. "
        "Handlem rządzą przemytnicy, a najgłośniejszy głos ma tu wyspiarska "
        "kapitanka.",
    "czarnogrod_dzielnica_wyspiarzy": DIASPORA_SUB["desc"],
}

_REFRESH_DESC = "UPDATE game_locations SET description=?, updated_at=datetime('now') WHERE key=?"

# ── 4. Frakcje krainy (oś §3 — Korona vs Rada Piracka; diaspora obok) ─────────────
FACTIONS = [
    ("korona", "Korona", "order",
     "Prawo Korony kończące się na linii przyboju. W Czarnogrodzie trzyma blokadę "
     "portu i celników, marzy o zduszeniu Zatoki Topielców i odzyskaniu kontroli nad "
     "handlem, którym faktycznie rządzą kupcy i przemytnicy."),
    ("rada_piracka", "Rada Piracka", "guild",
     "Pięciu kapitanów (czterech — piąty fotel pusty) rządzących wyspiarską twierdzą "
     "Zatoki Topielców. Żyją z abordażu, wraków i handlu niewolnikami; ich słowo jest "
     "na wyspie prawem, a chaos u wybrzeży to ich zysk."),
    ("diaspora_wyspiarzy", "Diaspora Wyspiarzy", "clan",
     "Lud bez domu — wyspiarze odcięci od ojczyzny za Sztormem Wiecznym. Rozeszli się "
     "po świecie jako marynarze, przemytnicy i najemnicy; własną dzielnicę mają tylko "
     "w porcie Czarnogrodu. Jako jedyni nie mają dokąd wrócić."),
]

# ── 5. NPC do dodania (lore §7/§9 — imiona i role WPROST z rozdziału) ──────────────
NPCS = [
    dict(key="kapitan_roggen", label="Kapitan Roggen", npc_type="quest_giver",
         faction="korona", shop=0, quest=1, crafter=None, kw=["korona", "blokada", "celnik", "glejt"],
         desc="Oficer Korony dowodzący blokadą czarnogrodzkiego portu. Sztywny, "
              "nieprzekupny na pierwszy rzut oka, z listą statków, których nie wolno "
              "wypuścić. Nienawidzi Rady Pirackiej i przemytników, a Czarnogród "
              "traktuje jak wrzód, który wreszcie da się wypalić — jeśli Korona da mu "
              "dość ludzi i pretekst.",
         prompt="Mówi krótko, rozkazami, waży rozmówcę jak ładunek do przeszukania. "
                "Zleca zadania Korony: rozbić przemyt, znaleźć dowód na Radę, zdusić "
                "kontrabandę. Pod maską służbisty tli się ambicja — kto pomoże mu "
                "zamknąć Zatokę, dostanie posłuch, ale nigdy pełnego zaufania."),
    dict(key="taio_starszy", label="Taio, starszy diaspory", npc_type="quest_giver",
         faction="diaspora_wyspiarzy", shop=0, quest=1, crafter=None, kw=["wyspiarze", "diaspora", "sztorm", "ojczyzna"],
         desc="Najstarszy głos wyspiarskiej diaspory w Czarnogrodzie — pamięć ludu, "
              "który stracił dom. Zna każdą rodzinę na pomostach i każdą pieśń o "
              "ziemi za Sztormem Wiecznym, dokąd od dwóch pokoleń nikt nie dopłynął. "
              "Gości obcych wyspiarzy, ale i lądowych, jeśli przychodzą z szacunkiem, "
              "a nie z pogardą Korony.",
         prompt="Mówi spokojnie, obrazami morza i wiatru, waży słowa jak stary "
                "żeglarz pogodę. Zleca zadania diaspory: wieści o zaginionych, opieka "
                "nad swoimi, ochrona dzielnicy przed Koroną i Radą. O ojczyźnie za "
                "Sztormem mówi z tęsknotą, ale nigdy nie twierdzi, że wie, co się z "
                "nią stało — to pytanie, nie odpowiedź."),
    dict(key="nakea_przemytniczka", label="Nakea, kapitanka-przemytniczka", npc_type="merchant",
         faction="diaspora_wyspiarzy", shop=1, quest=1, crafter=None, kw=["kontrabanda", "przemyt", "towar", "szmugiel"],
         desc="Wyspiarska kapitanka, która na Czarnym Targu handluje tym, o co Korona "
              "każe pytać dwa razy. Zna każdą lukę w blokadzie Roggena i każdą trasę "
              "między rafami. Sprzedaje tanio sól i towar „z głębin”, a kupuje wszystko, "
              "co da się przemknąć w Niziny — jej pokład to jedyny dom, jaki jej "
              "został.",
         prompt="Szybka, bystra, targuje się z uśmiechem i nożem w zasięgu ręki. "
                "Sprzedaje kontrabandę i podrzuca zlecenia szmuglerskie: przewieź, "
                "przemknij, sprzedaj w Nizinach. Lojalna wobec diaspory, wroga wobec "
                "Korony, ostrożna wobec Rady — z każdym rejsem ryzykuje szubienicę "
                "Roggena."),
    dict(key="malua_doki", label="Malua, szefowa doków", npc_type="merchant",
         faction="diaspora_wyspiarzy", shop=1, quest=1, crafter=None, kw=["doki", "remont", "galera", "rejs"],
         desc="Wyspiarka rządząca Pirackimi Dokami Zatoki twardą ręką — to ona "
              "decyduje, czyja galera schodzi z pochylni pierwsza, a czyja gnije w "
              "kolejce. Prowadzi remonty, nabór załóg i połowę zakulisowych układów "
              "wyspy. Bez jej zgody z Zatoki nie wypływa nic.",
         prompt="Rzeczowa, głośna, zna cenę każdej deski i każdej pary rąk przy "
                "robocie. Za złoto i przysługę załatwi rejs, remont albo miejsce w "
                "załodze. Nie lubi Korony, toleruje Radę, a wyspiarzom pomaga poza "
                "kolejnością — dokom rządzi ona, nie kapitanowie."),
    dict(key="ravu_egzekutor", label="Ravu, egzekutor Rady", npc_type="neutral",
         faction="rada_piracka", shop=0, quest=1, crafter=None, kw=["egzekutor", "rada", "dług", "zabijaka"],
         desc="Wyspiarski zabijaka na żołdzie Rady Pirackiej — ściąga długi, ucisza "
              "kłopoty i pilnuje, by wyrok kapitanów zapadł tam, gdzie trzeba. Milczący, "
              "ogromny, budzi strach samą obecnością. Dla Rady narzędzie, dla dłużników "
              "koniec rozmowy, dla wyspiarzy — rodak, który wybrał zły pokład.",
         prompt="Mówi mało i groźnie, każde zdanie brzmi jak ostatnie ostrzeżenie. "
                "Zleca brudną robotę Rady: ściągnij dług, przekaż wyrok, zniknij "
                "kłopot. Kupić go trudno, zastraszyć niepodobna — ale wyspiarska krew "
                "czasem waży u niego więcej niż rozkaz kapitanów."),
]

# ── 6. Dopisanie ról zastanym NPC (lore §2/§9 — haki krainy) ──────────────────────
NPC_ROLE_UPDATES = [
    ("rybak_stary_zatoka", "diaspora_wyspiarzy",
     "Dziadek Florian — stary rybak z Zatoki, który widział „coś dużego” tam, gdzie "
     "morze nie powinno nic ukrywać. Nikt mu nie wierzy, a on nie przestaje szukać "
     "śmiałka gotowego popłynąć i sprawdzić. Wie o pływach, rafach i wrakach więcej "
     "niż cała Rada, bo przeżył to, czego inni nie opowiedzą.",
     "Gadatliwy, przesądny, wraca do jednego: tam COŚ jest. Zleca zadania ku morzu — "
     "ku miejscu, gdzie widział cień pod falą. Traktowany poważnie, otworzy skarbiec "
     "wiedzy o Głębi; wyśmiany, zamilknie i popłynie sam."),
    ("kapitan_smolny", None,
     "Kapitan Jacek Smolny — żeglarz, który spisał mapę klifów, raf i bezpiecznych "
     "kursów Wybrzeża. Na tę MAPĘ komuś bardzo zależy: z nią rejsy są mniej "
     "zabójcze, a latarnia mniej kłamie. Smolny wie, ile jest warta, więc trzyma ją "
     "blisko i sprzedaje tylko zaufaniu.",
     "Nieufny, konkretny, mówi kursami i głębokościami. Zleca zadania wokół swojej "
     "mapy: odzyskać, obronić, uzupełnić brakujące odcinki. Kto zdobędzie jego "
     "zaufanie, dostanie realny kontrprzedmiot na rafy; kto go zdradzi, nie wypłynie "
     "drugi raz."),
]

# ── 7. Przypisania NPC → lokacja (hub = cała osada, sub = pinezka) ────────────────
NPC_ASSIGNMENTS = [
    # Czarnogród
    ("czarnogrod_port", "kapitan_roggen", "resident"),
    ("czarnogrod_port", "taio_starszy", "resident"),
    ("czarnogrod_port", "nakea_przemytniczka", "resident"),
    ("czarnogrod_nabrzeze", "kapitan_roggen", "resident"),        # blokada portu przy molu
    ("czarnogrod_dzielnica_wyspiarzy", "taio_starszy", "resident"),
    ("czarnogrod_giełda_kontrabandy", "nakea_przemytniczka", "resident"),  # Czarny Targ
    # Zatoka
    ("zatoka_topielcow", "malua_doki", "resident"),
    ("zatoka_topielcow", "ravu_egzekutor", "resident"),
    ("zatoka_pirackie_doki", "malua_doki", "resident"),
    ("zatoka_rada_piracka", "ravu_egzekutor", "resident"),
]

# Sklep Nakei — kontrabanda z narzutem (szmugiel-loop lore §6). Klucze realne z DB.
NAKEA_SHOP = json.dumps([
    {"type": "item", "key": "krag_soli", "price": 12},
    {"type": "item", "key": "szczypta_soli", "price": 3},
    {"type": "item", "key": "tabliczka_plywow", "price": 45},
    {"type": "item", "key": "torch"},
], ensure_ascii=False)

# Malua — drobny handel dokowy (liny, smoła zastąpione realnym kluczem + narzut)
MALUA_SHOP = json.dumps([
    {"type": "item", "key": "torch"},
    {"type": "item", "key": "tabliczka_plywow", "price": 40},
], ensure_ascii=False)

SHOP_INV = {"nakea_przemytniczka": NAKEA_SHOP, "malua_doki": MALUA_SHOP}


def ensure_diaspora_sub(conn):
    hub = conn.execute("SELECT id FROM game_locations WHERE key=?", (HUB_CZARNOGROD,)).fetchone()
    if hub is None:
        print(f"  ✗ brak huba {HUB_CZARNOGROD}"); return False
    s = DIASPORA_SUB
    res = create_location(
        conn, key=s["key"], label=s["label"], source=LocationSource.SEED,
        description=s["desc"], location_type="sub",
        parent_key=HUB_CZARNOGROD, parent_id=hub["id"], region=REGION,
        map_icon=s["icon"], tier=s["tier"], biome=s["biome"],
        location_subtype=s["subtype"], safe_for_rest=s["safe"],
        visible_before_visit=0, canonical=False, commit=False,
    )
    if not res["created"]:
        conn.execute(
            "UPDATE game_locations SET label=?, description=?, region=?, map_icon=?, "
            "tier=?, biome=?, location_subtype=?, safe_for_rest=?, parent_key=?, "
            "parent_id=?, is_active=1, updated_at=datetime('now') WHERE key=?",
            (s["label"], s["desc"], REGION, s["icon"], s["tier"], s["biome"],
             s["subtype"], s["safe"], HUB_CZARNOGROD, hub["id"], s["key"]),
        )
    print(f"  sub diaspora {s['key']} {'NEW' if res['created'] else 'refresh'}")
    return True


def refresh_descriptions(conn):
    n = 0
    for key, desc in SUB_DESCRIPTIONS.items():
        cur = conn.execute(_REFRESH_DESC, (desc, key))
        n += cur.rowcount or 0
    print(f"  opisy subów odświeżone: {n}")


def build_local_map(conn, hub_key):
    subs = [r[0] for r in conn.execute(
        "SELECT key FROM game_locations WHERE parent_key=? AND is_active=1 ORDER BY id", (hub_key,))]
    if len(subs) < 2:
        print(f"  {hub_key}: <2 subów, pomijam mapę lokalną"); return
    auto_assign_local_hex(conn, subs[0], hub_key)
    normalize_hub_local_hexes(conn, hub_key)
    conn.commit()
    local = get_local_hexes(conn, hub_key)
    print(f"  {hub_key}: mapa lokalna {len(local)} hexów map_level=1 (subów={len(subs)})")


def apply_obsada(conn):
    n_fac = n_npc = n_na = 0
    for key, name, ftype, desc in FACTIONS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO game_config_factions (key, name, faction_type, description, is_active) "
            "VALUES (?, ?, ?, ?, 1)", (key, name, ftype, desc))
        n_fac += cur.rowcount or 0

    for n in NPCS:
        shop_inv = SHOP_INV.get(n["key"], "[]")
        cur = conn.execute(
            """INSERT OR IGNORE INTO npcs
                 (key, label, npc_type, description, personality_json, personality_prompt,
                  is_shop, shop_inventory_json, is_quest_giver, is_crafter, crafter_type,
                  faction_key, is_active, review_status, keyword_triggers)
               VALUES (?, ?, ?, ?, '{}', ?, ?, ?, ?, ?, ?, ?, 1, 'permanent', ?)""",
            (n["key"], n["label"], n["npc_type"], n["desc"], n["prompt"],
             int(n["shop"]), shop_inv, int(n["quest"]), int(bool(n["crafter"])),
             n["crafter"], n["faction"], json.dumps(n["kw"], ensure_ascii=False)))
        n_npc += cur.rowcount or 0

    # Dopisanie ról zastanym NPC (UPDATE — nadpisuje opis/prompt, ustawia frakcję jeśli podana)
    for key, faction, desc, prompt in NPC_ROLE_UPDATES:
        if faction:
            conn.execute("UPDATE npcs SET description=?, personality_prompt=?, faction_key=?, "
                         "updated_at=datetime('now') WHERE key=?", (desc, prompt, faction, key))
        else:
            conn.execute("UPDATE npcs SET description=?, personality_prompt=?, "
                         "updated_at=datetime('now') WHERE key=?", (desc, prompt, key))

    for loc, npc, atype in NPC_ASSIGNMENTS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO location_npc_assignments (location_key, npc_key, assignment_type, is_active) "
            "VALUES (?, ?, ?, 1)", (loc, npc, atype))
        n_na += cur.rowcount or 0

    # przelicz game_locations.npc_keys dla dotkniętych lokacji
    touched = {a[0] for a in NPC_ASSIGNMENTS}
    for loc in sorted(touched):
        npc_keys = [r[0] for r in conn.execute(
            "SELECT npc_key FROM location_npc_assignments WHERE location_key=? AND is_active=1 ORDER BY npc_key", (loc,))]
        conn.execute("UPDATE game_locations SET npc_keys=? WHERE key=?",
                     (json.dumps(npc_keys, ensure_ascii=False), loc))
    conn.commit()
    return {"factions": n_fac, "npcs": n_npc, "npc_assignments": n_na}


def verify(conn):
    problems = []
    for loc, npc, _ in NPC_ASSIGNMENTS:
        if not conn.execute("SELECT 1 FROM game_locations WHERE key=? AND is_active=1", (loc,)).fetchone():
            problems.append(f"przypisanie do nieistniejącej lokacji: {loc}")
        if not conn.execute("SELECT 1 FROM npcs WHERE key=? AND is_active=1", (npc,)).fetchone():
            problems.append(f"nieistniejący NPC: {npc}")
    for n in NPCS:
        if n["faction"] and not conn.execute(
                "SELECT 1 FROM game_config_factions WHERE key=?", (n["faction"],)).fetchone():
            problems.append(f"{n['key']}: brak frakcji {n['faction']}")
    # sklepy — klucze towaru muszą istnieć (item = game_items LUB game_config_items)
    for npc_key, inv in SHOP_INV.items():
        for row in json.loads(inv):
            if row["type"] != "item":
                continue
            in_items = conn.execute(
                "SELECT 1 FROM game_items WHERE key=? AND is_active=1", (row["key"],)).fetchone()
            in_config = conn.execute(
                "SELECT 1 FROM game_config_items WHERE key=?", (row["key"],)).fetchone()
            if not in_items and not in_config:
                problems.append(f"{npc_key}: brak towaru item.{row['key']}")
    # oba huby muszą mieć mapę lokalną pokrywającą wszystkie suby
    for hub in (HUB_CZARNOGROD, HUB_ZATOKA):
        orphan = conn.execute(
            "SELECT count(*) c FROM game_locations WHERE parent_key=? AND is_active=1 "
            "AND key NOT IN (SELECT location_key FROM world_hexes WHERE map_level=1 "
            "AND location_key IS NOT NULL)", (hub,)).fetchone()["c"]
        if orphan:
            problems.append(f"{hub}: {orphan} subów bez hexa na mapie lokalnej")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    print("── 1. sub diaspory + opisy ──")
    ensure_diaspora_sub(conn)
    refresh_descriptions(conn)
    conn.commit()

    print("── 2. mapy lokalne hubów ──")
    build_local_map(conn, HUB_CZARNOGROD)
    build_local_map(conn, HUB_ZATOKA)

    print("── 3. frakcje + NPC + przypisania ──")
    res = apply_obsada(conn)
    print(f"  frakcje nowe:         {res['factions']}")
    print(f"  NPC nowe:             {res['npcs']}")
    print(f"  przypisania nowe:     {res['npc_assignments']}")

    rows = conn.execute("""
        SELECT gl.label AS loc, n.label AS npc, a.assignment_type
        FROM location_npc_assignments a
        JOIN game_locations gl ON gl.key = a.location_key
        JOIN npcs n ON n.key = a.npc_key
        WHERE gl.region = ? AND a.is_active = 1
        ORDER BY gl.label, n.label""", (REGION,)).fetchall()
    print(f"\n  obsada krainy ({len(rows)} przypisań):")
    for r in rows:
        print(f"    {r['loc']:36s} ← {r['npc']} ({r['assignment_type']})")

    problems = verify(conn)
    conn.commit()
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
