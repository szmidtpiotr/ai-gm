#!/usr/bin/env python3
"""KN-6 (#1500) — obsada osad + usługi Światła Koronnych Nizin.

Źródło prawdy: docs/world/regions/koronne_niziny.md §4/§7. Wzorzec:
scripts/seed_vilnograd_obsada.py (KN-5) — ta sama mechanika (npcs + frakcje +
location_npc_assignments), inne NPC.

CO ROBI:
  1. Klasztor Iskry — 3 NPC-ikony (§7) + frakcja świetlista:
       * Matka Urszula (matka_klasztor)   — przeorysza (istnieje: doszlifowanie).
       * Brat Kazimierz (brat_kazimierz)  — uzdrowiciel Światła (NOWY).
       * Brat Tomasz Kronikarz            — SKUP reliktów (istnieje jako quest_giver →
         upgrade do is_shop=1). „Lustro Fabiana z Pustkowi”: TE SAME przedmioty co
         fabian_paser (relikt_pradawnych, treasure_map, torch, oil_flask). SKUP =
         zwykły sell_item gracz→NPC (shop_service), bez osobnego pola — jak Fabian.
  2. Usługi Światła (#1292/#1394): oprócz leczenia (healer_light/heavy, już są) dodaje
     do game_config_services dwie NOWE usługi świetliste — TE muszą też być wpięte w
     _HEALER_SERVICES w location_services.py (zrobione w tym samym commicie):
       * blessing_light  — błogosławieństwo (cennik startowy 20 gp)
       * curse_removal   — odklęcie/odklinanie (cennik startowy 60 gp)
     Dostępność liczy keyword na label/subtype lokalizacji: kaplica/klasztor/katedra
     → oferuje Światło. Klasztor (Wielka Kaplica subtype=temple + hub „Klasztor Iskry”)
     wpada w keyword, więc Usługi modal pokazuje leczenie+błogosławieństwo+odklęcie.
  3. Rogatka Wschodnia — Berta Twarda Pieczęć (istnieje jako neutral: doszlifowanie
     osobowości/keywordów; kontrola papierów = KN-8) + przypięcie do Izby Celnej.

Cennik = WARTOŚCI STARTOWE (Numbers Policy) — dostrajalne z admina/sandboxa.
Idempotentny: INSERT OR IGNORE + wymuszony UPDATE kanonicznych pól.

URUCHOMIENIE (w kontenerze backendu):
    docker cp scripts/seed_kn6_obsada_uslugi.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_kn6_obsada_uslugi.py
    docker exec ai-gm-dev-backend-1 python /app/seed_kn6_obsada_uslugi.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

sys.path.insert(0, "/app")

REGION = "koronne_niziny"

# ── Frakcja świetlista Klasztoru (reputacja per-frakcja #1103; CHECK: guild/clan/order) ──
FACTIONS = [
    ("swiatlo_iskry", "Klasztor Iskry", "order",
     "Zakon Światła strzegący Iskry — leczenie, błogosławieństwa i odklinanie dla "
     "całej krainy. Śpiewa o porządku równie gładko, jak dwór; wierni nie pytają, "
     "czyja ręka opłaca świece."),
]

# ── Nowe usługi Światła (game_config_services). Leczenie już jest (healer_light/heavy). ──
# (key, label, cost_gp, description) — cost_gp = wartość STARTOWA.
SERVICES = [
    ("blessing_light", "Klasztor: błogosławieństwo", 20,
     "Błogosławieństwo Światła przed drogą lub bitwą — kapłani proszą Iskrę o pomyślność."),
    ("curse_removal", "Klasztor: odklęcie", 60,
     "Odklinanie — zdjęcie klątwy lub złego uroku przez obrzęd Światła w kaplicy."),
]

# „Lustro Fabiana”: Brat Tomasz skupuje TE SAME przedmioty co fabian_paser.
RELIC_STOCK = [
    {"type": "item", "key": "relikt_pradawnych"},
    {"type": "item", "key": "treasure_map"},
    {"type": "item", "key": "torch"},
    {"type": "item", "key": "oil_flask"},
]

# ── NPC-ikony. pola: key,label,npc_type,faction,shop,shop_json,quest,ally,kw,desc,prompt ──
NPCS = [
    dict(
        key="matka_klasztor", label="Matka Urszula", npc_type="ally",
        faction="swiatlo_iskry", shop=0, shop_json="[]", quest=1, ally=1,
        kw=["urszula", "matka", "przeorysza", "klasztor", "iskra", "iskry", "swiatlo",
            "światło"],
        desc="Przeorysza Klasztoru Iskry — twarz Światła w Koronnych Nizinach. Trzyma "
             "regułę zakonu twardziej niż Korona trzyma prawo, a jej „tak” waży w "
             "krainie więcej niż niejedna pieczęć. Do niej idą po błogosławieństwo "
             "przed drogą i po pociechę, gdy Światło zdaje się milczeć.",
        prompt="Spokojna, dostojna, mówi krótko i celnie. Widzi człowieka na wylot i nie "
               "udaje, że nie widzi. Zleca sprawy zakonu — pielgrzymki, ratunek, odklęcie "
               "— nigdy dla zysku, zawsze dla porządku Światła. O polityce Korony wypowie "
               "się ostrożnie; wie więcej, niż powie.",
    ),
    dict(
        key="brat_kazimierz", label="Brat Kazimierz", npc_type="ally",
        faction="swiatlo_iskry", shop=0, shop_json="[]", quest=0, ally=1,
        kw=["kazimierz", "brat", "uzdrowiciel", "leczenie", "lecz", "rany", "ranny",
            "medyk", "swiatlo", "błogosławieństwo", "blogoslawienstwo", "odklęcie",
            "odklecie"],
        desc="Uzdrowiciel Klasztoru Iskry — dłonie ma spracowane od bandaży i modlitwy. "
             "Zszywa ranę i prosi Światło o resztę; nie pyta, po której stronie stanął "
             "ranny, zanim zaczął krwawić. To on prowadzi w kaplicy leczenie, "
             "błogosławieństwa i obrzęd odklęcia — za datek na zakon.",
        prompt="Ciepły, rzeczowy, cierpliwy. Mówi o ranach jak rzemieślnik o robocie, o "
               "Świetle jak o starym przyjacielu. Wyleczy każdego, kto zapłaci datek — i "
               "niejednego, kto nie ma czym, jeśli Matka pozwoli. Ostrzega, że odklęcie "
               "nie zawsze bierze za pierwszym razem.",
    ),
    dict(
        key="brat_tomasz_kronikarz", label="Brat Tomasz Kronikarz", npc_type="merchant",
        faction=None, shop=1, shop_json=json.dumps(RELIC_STOCK), quest=1, ally=0,
        kw=["tomasz", "kronikarz", "kronika", "skup", "relikt", "relikty", "relikwia",
            "znalezisko", "pradawn"],
        desc="Kronikarz Klasztoru Iskry — spisuje dzieje krainy i po cichu skupuje "
             "relikty z ruin i Pustkowi. To jego agentem jest Fabian z Obozu Gorączki: "
             "co Fabian kupi na pograniczu, odsprzedaje tu, Tomaszowi, jeszcze drożej. "
             "Płaci uczciwie za dobre znalezisko i nigdy nie mówi, po co zakonowi tyle "
             "starego kruszcu i szkła.",
        prompt="Uprzejmy, uczony, ciekawski jak kronika, która nigdy się nie kończy. "
               "Kupi każdy relikt i wypyta, z której ruiny pochodzi i co jeszcze tam "
               "leżało. Skup prowadzi dyskretnie, w bibliotece, nie na widoku. O celu "
               "kolekcji milczy równie gładko, jak Fabian milczy o nim.",
    ),
    dict(
        key="berta_twarda_pieczec", label="Berta Twarda Pieczęć", npc_type="neutral",
        faction="korona", shop=0, shop_json="[]", quest=0, ally=0,
        kw=["berta", "pieczec", "pieczęć", "celniczka", "celnik", "myto", "clo", "cło",
            "glejt", "papiery", "rogatka", "szlaban", "list żelazny"],
        desc="Celniczka Rogatki Wschodniej — pierwsza pieczęć Korony, jaką widzi "
             "przybysz ze wschodu. Czyta papiery uważniej niż twarze i nie podnosi "
             "szlabanu przed stemplem. Glejt kupiecki obniża jej myto, list żelazny "
             "otwiera drzwi bez pytań, fałszywe papiery to gra o wolność. Mrok krainy "
             "pokazuje przy niej pierwszy ząb: nie kły, a stempel.",
        prompt="Twarda, opanowana, nieprzekupna dla byle kogo. Pyta krótko: skąd, dokąd, "
               "z czym. Papierom wierzy bardziej niż ludziom, ale ludzi czyta dobrze. "
               "Fałsz wietrzy nosem; kto kłamie gładko, i tak zostawia jej pieczęć na "
               "sumieniu. (Pełna mechanika kontroli papierów — KN-8.)",
    ),
]

# ── Przypisania NPC → lokacja ────────────────────────────────────────────────────
NPC_ASSIGNMENTS = [
    # poziom huba Klasztoru (widoczni z centrum wiary)
    ("klasztor_iskry_centrum", "matka_klasztor", "resident"),
    ("klasztor_iskry_centrum", "brat_kazimierz", "resident"),
    ("klasztor_iskry_centrum", "brat_tomasz_kronikarz", "resident"),
    # dzielnice/suby Klasztoru
    ("klasztor_iskry_kaplica_glowna", "matka_klasztor", "resident"),
    ("klasztor_iskry_kaplica_glowna", "brat_kazimierz", "resident"),    # uzdrowiciel przy usługach
    ("klasztor_iskry_biblioteka", "brat_tomasz_kronikarz", "resident"),  # skup reliktów
    # Rogatka Wschodnia — Berta w izbie celnej (+ istniejące przypisanie do makro)
    ("rogatka_izba_celna", "berta_twarda_pieczec", "resident"),
]

_ICON_UPDATE = """
UPDATE npcs SET
  label=?, npc_type=?, description=?, personality_prompt=?, faction_key=?,
  is_shop=?, shop_inventory_json=?, is_quest_giver=?, is_ally=?,
  keyword_triggers=?, is_active=1, review_status='permanent', updated_at=datetime('now')
WHERE key=?
"""


def apply(conn):
    n = dict(fac=0, npc=0, na=0, svc=0)

    for key, name, ftype, desc in FACTIONS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO game_config_factions (key, name, faction_type, description, is_active) "
            "VALUES (?, ?, ?, ?, 1)", (key, name, ftype, desc))
        n["fac"] += cur.rowcount or 0

    for key, label, cost, desc in SERVICES:
        cur = conn.execute(
            "INSERT OR IGNORE INTO game_config_services (key, label, cost_gp, description, is_active) "
            "VALUES (?, ?, ?, ?, 1)", (key, label, cost, desc))
        # wymuś cennik startowy także jeśli wiersz istniał
        conn.execute(
            "UPDATE game_config_services SET label=?, cost_gp=?, description=?, is_active=1, "
            "updated_at=datetime('now') WHERE key=?", (label, cost, desc, key))
        n["svc"] += cur.rowcount or 0

    for x in NPCS:
        cur = conn.execute(
            """INSERT OR IGNORE INTO npcs
                 (key, label, npc_type, description, personality_json, personality_prompt,
                  is_shop, shop_inventory_json, is_quest_giver, is_ally, faction_key,
                  is_active, review_status, keyword_triggers)
               VALUES (?, ?, ?, ?, '{}', ?, ?, ?, ?, ?, ?, 1, 'permanent', ?)""",
            (x["key"], x["label"], x["npc_type"], x["desc"], x["prompt"],
             int(x["shop"]), x["shop_json"], int(x["quest"]), int(x["ally"]), x["faction"],
             json.dumps(x["kw"], ensure_ascii=False)))
        n["npc"] += cur.rowcount or 0
        conn.execute(_ICON_UPDATE, (
            x["label"], x["npc_type"], x["desc"], x["prompt"], x["faction"],
            int(x["shop"]), x["shop_json"], int(x["quest"]), int(x["ally"]),
            json.dumps(x["kw"], ensure_ascii=False), x["key"]))

    for loc, npc, atype in NPC_ASSIGNMENTS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO location_npc_assignments (location_key, npc_key, assignment_type, is_active) "
            "VALUES (?, ?, ?, 1)", (loc, npc, atype))
        n["na"] += cur.rowcount or 0

    # odśwież game_locations.npc_keys dla dotkniętych lokacji
    touched = {a[0] for a in NPC_ASSIGNMENTS}
    for loc in sorted(touched):
        keys = [r[0] for r in conn.execute(
            "SELECT npc_key FROM location_npc_assignments WHERE location_key=? AND is_active=1 ORDER BY npc_key", (loc,))]
        conn.execute("UPDATE game_locations SET npc_keys=? WHERE key=?",
                     (json.dumps(keys, ensure_ascii=False), loc))
    conn.commit()
    return n


def verify(conn):
    problems = []
    # usługi Światła obecne i aktywne
    for key, *_ in SERVICES:
        if not conn.execute("SELECT 1 FROM game_config_services WHERE key=? AND is_active=1", (key,)).fetchone():
            problems.append(f"usługa {key} brak/nieaktywna")
    # NPC + frakcje + przypisania
    for loc, npc, _ in NPC_ASSIGNMENTS:
        if not conn.execute("SELECT 1 FROM game_locations WHERE key=? AND is_active=1", (loc,)).fetchone():
            problems.append(f"przypisanie do nieistniejącej lokacji: {loc}")
        if not conn.execute("SELECT 1 FROM npcs WHERE key=? AND is_active=1", (npc,)).fetchone():
            problems.append(f"nieaktywny NPC: {npc}")
    for x in NPCS:
        if x["faction"] and not conn.execute(
                "SELECT 1 FROM game_config_factions WHERE key=?", (x["faction"],)).fetchone():
            problems.append(f"{x['key']}: brak frakcji {x['faction']}")
    # Tomasz musi być sklepem z niepustym asortymentem (skup = sell do is_shop NPC)
    row = conn.execute("SELECT is_shop, shop_inventory_json FROM npcs WHERE key='brat_tomasz_kronikarz'").fetchone()
    if not row or not row["is_shop"] or not row["shop_inventory_json"] or row["shop_inventory_json"] in ("[]", ""):
        problems.append("brat_tomasz_kronikarz: skup nieaktywny (is_shop/asortyment)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    n = apply(conn)
    print(f"  frakcje nowe:         {n['fac']}")
    print(f"  usługi Światła nowe:  {n['svc']}")
    print(f"  NPC nowe:             {n['npc']}")
    print(f"  przypisania nowe:     {n['na']}")

    print("\n  cennik usług Światła (game_config_services):")
    for r in conn.execute(
            "SELECT key,label,cost_gp FROM game_config_services "
            "WHERE key IN ('healer_light','healer_heavy','blessing_light','curse_removal') ORDER BY cost_gp"):
        print(f"    {r['key']:16s} {r['cost_gp']:>3} gp  {r['label']}")

    rows = conn.execute("""
        SELECT gl.label AS loc, nn.label AS npc, a.assignment_type, nn.is_shop
        FROM location_npc_assignments a
        JOIN game_locations gl ON gl.key = a.location_key
        JOIN npcs nn ON nn.key = a.npc_key
        WHERE (a.location_key LIKE 'klasztor%' OR a.location_key LIKE 'rogatka%') AND a.is_active=1
        ORDER BY gl.label, nn.label""").fetchall()
    print(f"\n  obsada Klasztoru/Rogatki ({len(rows)} przypisań):")
    for r in rows:
        tag = " 🛒" if r["is_shop"] else ""
        print(f"    {r['loc']:40s} ← {r['npc']}{tag} ({r['assignment_type']})")

    problems = verify(conn)
    conn.commit()
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
