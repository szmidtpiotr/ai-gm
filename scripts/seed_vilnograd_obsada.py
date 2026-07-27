#!/usr/bin/env python3
"""KN-5 (#1500) — obsada Vilnogradu: 5 NPC-ikon stolicy + frakcje + sklepy top-tier.

Źródło prawdy: docs/world/regions/koronne_niziny.md §7 (obsada) + §6 (smaczki/kantor).
Wzorzec: scripts/seed_czarnobor_obsada.py (CB-5) — ta sama mechanika, inna kraina.

Read-path silnika (dlaczego to działa w grze):
  turn_pipeline → world_service.build_available_content_index() wstrzykuje do LLM blok
  "[AVAILABLE CONTENT]" z location_npc_assignments → narrator przedstawia KANONICZNĄ
  postać zamiast wymyślać zastępczą. npcs.faction_key czyta reputacja per-frakcja (#1103).

NPC-ikony §7 (styl: dwór = archaiczno-dworskie słowiańskie; półświatek = pseudonimy-urzędy;
krasnoludy = nordyckie imię + polski przydomek; gildia-kanon bez zmian):
  * Kanclerz Dobrogost   — twarz Korony            → Zamek Królewski
  * „Rachmistrzyni”       — pośredniczka Rady        → Dzielnica Gildii (imienia nie zna nikt,
                            przyjmuje raz w tygodniu → assignment_type='visitor', faction=None
                            aby uszanować „Sekret Rady” §4: skład/cel nigdy nieujawnione)
  * „Nocny Burmistrz”     — władca dzielnicy złodziei → Dzielnica Złodziei (pseudonim-urząd)
  * Gundrik Złota Waga   — bankier+jubiler enklawy  → Enklawa (ISTNIEJE — upgrade + sklep)
  * Brat Aleksy Złotnik  — gildmistrz (KANON)        → Dzielnica Gildii

Handel top-tier §2/§4:
  * Targ Wielki  = kupiec_vilnograd (Mirna Zbożowa, ISTNIEJE) → asortyment o klasę wyżej niż
                   pogranicze (najlepsza broń/zbroje/mikstury/zwoje + glejt/list).
  * Enklawa      = Gundrik → kantor + jubilerstwo (kosztowności zbywalne + glejt/list).
                   Weksle = mechanika KN-8; TU sam sklep (bez pozycji „weksel” — item powstaje w KN-8).

Idempotentny: frakcje/NPC/przypisania INSERT OR IGNORE; kluczowe pola ikon i sklepów
wymuszane explicit UPDATE (bezpieczne na już-istniejących Gundriku/Mirnie).

URUCHOMIENIE (wewnątrz kontenera backendu):
    docker cp scripts/seed_vilnograd_obsada.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_vilnograd_obsada.py
    docker exec ai-gm-dev-backend-1 python /app/seed_vilnograd_obsada.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

sys.path.insert(0, "/app")

REGION = "koronne_niziny"

# ── Frakcje stolicy (reputacja per-frakcja #1103; tag = nie ujawnia sekretu Rady) ──
FACTIONS = [
    ("korona_vilnograd", "Korona", "order",
     "Jawna władza Vilnogradu — tron, gwardia, kanclerz. Uśmiech, marmur i porządek na "
     "wierzchu; pod spodem Rada Czterech kupuje ratami to, czego jawnie zdobyć nie może."),
    ("gildie_vilnogradu", "Gildie Vilnogradu", "guild",
     "Cechy i kantory rachunkowe Dzielnicy Gildii — handlowe serce stolicy, w którego "
     "skórze kult ma salony zamiast ruin."),
    ("polswiatek_vilnogradu", "Półświatek", "clan",
     "Cichy porządek Dzielnicy Złodziei — świat Mizela. Rządzi „Nocny Burmistrz”, "
     "pseudonim-urząd, o którym mówi się, że bywa przechodni."),
    ("enklawa_krasnoludzka", "Enklawa Krasnoludzka", "guild",
     "Krasnoludzki kwartał kantorów i złotników — najbezpieczniejsze skarbce i najczystsza "
     "robota jubilerska w świecie."),
]

# ── Sklepy top-tier (shop_inventory_json; type: weapon=game_config_weapons, reszta=game_items) ──
# Targ Wielki — sufit ekonomii gry: najlepsza broń/zbroje/mikstury/zwoje + dokumenty §6.
TARG_WIELKI_STOCK = [
    {"type": "weapon", "key": "silver_sword"},
    {"type": "weapon", "key": "burning_blade"},
    {"type": "weapon", "key": "healing_staff"},
    {"type": "weapon", "key": "greatsword"},
    {"type": "weapon", "key": "longsword"},
    {"type": "weapon", "key": "longbow"},
    {"type": "weapon", "key": "crossbow"},
    {"type": "weapon", "key": "rapier"},
    {"type": "armor", "key": "full_plate"},
    {"type": "armor", "key": "half_plate"},
    {"type": "item", "key": "potion_healing_major"},
    {"type": "item", "key": "potion_mana_major"},
    {"type": "item", "key": "scroll_fireball"},
    {"type": "item", "key": "spyglass"},
    {"type": "item", "key": "glejt_kupiecki"},
    {"type": "item", "key": "list_zelazny"},
]
# Enklawa (Gundrik) — kantor + jubilerstwo: kosztowności zbywalne + dokumenty (weksel = KN-8).
ENKLAWA_STOCK = [
    {"type": "item", "key": "golden_idol"},
    {"type": "item", "key": "dragon_scale_shard"},
    {"type": "item", "key": "glejt_kupiecki"},
    {"type": "item", "key": "list_zelazny"},
]

# ── 5 NPC-ikon + upgrade Mirny (Targ) ──────────────────────────────────────────
# pola: key,label,npc_type,faction,shop,shop_json,quest,crafter,crafter_type,kw,desc,prompt
NPCS = [
    dict(
        key="kanclerz_dobrogost", label="Kanclerz Dobrogost", npc_type="quest_giver",
        faction="korona_vilnograd", shop=0, shop_json="[]", quest=1,
        crafter=0, crafter_type=None,
        kw=["dobrogost", "kanclerz", "korona", "zamek", "dwor", "dwór"],
        desc="Twarz Korony w stolicy — pierwszy urzędnik tronu, który wita gości "
             "uśmiechem gładszym niż posadzka sali audiencyjnej. Zna każdy dług "
             "twierdz granicznych i każdą pieczęć, jaką Korona zdążyła sprzedać. "
             "Mówi o porządku, a między słowami waży, komu porządek jeszcze służy.",
        prompt="Dworny, opanowany, nigdy nie podnosi głosu. Dobiera słowa jak monety — "
               "policzone i wymienne. Zleca sprawy Korony tak, by interesant myślał, że "
               "to jego własny pomysł. O Radzie Czterech nie powie ani słowa; o „Ostatniej "
               "Warcie” i wycofaniu Strzegwachtu wypowie się gładko i pusto. Nigdy nie "
               "przyzna, że tron płaci już tylko wekslem.",
    ),
    dict(
        key="rachmistrzyni", label="„Rachmistrzyni”", npc_type="quest_giver",
        faction=None, shop=0, shop_json="[]", quest=1, crafter=0, crafter_type=None,
        kw=["rachmistrzyni", "rachmistrz", "rada", "ksiegi", "księgi", "rachunki"],
        desc="Pośredniczka Rady Czterech — prowadzi jej rachunki i przyjmuje interesantów "
             "raz w tygodniu, w Dzielnicy Gildii, za zasłoną, której nikt nie odsuwa. "
             "Imienia nie zna nikt; jest urzędem, nie osobą. Kto trafi na jej dzień "
             "przyjęć, dotyka najcieńszej nici największej intrygi stolicy — i nigdy "
             "nie widzi całej sieci.",
        prompt="Beznamiętna, precyzyjna, mówi cyframi i warunkami. Nie grozi i nie obiecuje "
               "— proponuje rachunek: tyle za to, tyle za tamto. Nigdy nie ujawnia, czyje "
               "polecenia wykonuje ani ilu jest w Radzie; kto pyta wprost, dostaje ciszę i "
               "zamkniętą księgę. Zleca zadania, które są zawsze tylko jedną ratą czegoś "
               "większego.",
    ),
    dict(
        key="nocny_burmistrz", label="„Nocny Burmistrz”", npc_type="quest_giver",
        faction="polswiatek_vilnogradu", shop=0, shop_json="[]", quest=1,
        crafter=0, crafter_type=None,
        kw=["nocny burmistrz", "burmistrz", "zlodziei", "złodziei", "polswiatek",
            "półświatek", "mizel"],
        desc="Władca Dzielnicy Złodziei — pseudonim-urząd, nie człowiek. Trzyma szlaki "
             "przemytu, mecenaty i cichy porządek, który działa sprawniej niż niejeden "
             "magistrat Korony. Szepcze się, że „Nocny Burmistrz” bywa przechodni: kto "
             "dziś nosi ten tytuł, jutro może już nie żyć — a urząd trwa.",
        prompt="Spokojny, uprzejmy, groźny bez jednego twardego słowa. Traktuje przysługę "
               "jak walutę i pamięta każdy dług. Nie mówi, kim jest naprawdę, i lubi, gdy "
               "rozmówca nie jest pewien, czy gada z człowiekiem, czy z urzędem. Zleca "
               "robotę półświatka — cichą, opłacalną i z drugim dnem.",
    ),
    dict(
        key="gundrik_zlota_waga", label="Gundrik Złota Waga", npc_type="merchant",
        faction="enklawa_krasnoludzka", shop=1, shop_json=json.dumps(ENKLAWA_STOCK),
        quest=0, crafter=1, crafter_type="jeweler",
        kw=["gundrik", "zlota waga", "złota waga", "kantor", "weksel", "jubiler",
            "bankier", "enklawa", "klejnot"],
        desc="Bankier i złotnik Enklawy Krasnoludzkiej — waży kruszec dokładniej, niż "
             "Korona liczy podatki. U niego zamienisz majątek w klejnot albo w papier "
             "kantoru, którego ani kradzież, ani śmierć ci nie odbiorą. Najbezpieczniejszy "
             "skarbiec stolicy i najczystsza robota jubilerska w świecie.",
        prompt="Rzeczowy, cierpliwy, mierzy człowieka jak sztabę — po próbie, nie po "
               "słowach. Za dobry interes szanuje, za oszustwo zamyka drzwi kantoru na "
               "zawsze. O wekslach mówi jak o rzeczy oczywistej (pełna mechanika dopiero "
               "nadchodzi); jubilerstwo to jego duma. Nie targuje się długo — jego cena "
               "jest jego ceną.",
    ),
    dict(
        key="brat_aleksy_zlotnik", label="Brat Aleksy Złotnik", npc_type="quest_giver",
        faction="gildie_vilnogradu", shop=0, shop_json="[]", quest=1,
        crafter=0, crafter_type=None,
        kw=["aleksy", "zlotnik", "złotnik", "gildia", "gildmistrz", "cech", "gildii"],
        desc="Gildmistrz Vilnogradu (kanon) — trzyma księgi cechu i klucz do Dzielnicy "
             "Gildii. Pod szacowną pieczęcią gildii sączą się jednak inne prądy: to tu, "
             "w salonach, a nie w ruinach, kult nosi najczystszą skórę. Aleksy wie, kto "
             "komu winien i kto raz w tygodniu przyjmuje za zasłoną.",
        prompt="Uprzejmy, wpływowy, mówi językiem umów i przysług. Otwiera drzwi cechu "
               "temu, kto się przydaje, i zamyka temu, kto zadaje niewłaściwe pytania o "
               "„Rachmistrzynię”. Zleca sprawy gildii — z pozoru handlowe, w rdzeniu "
               "polityczne. Nigdy nie powie wprost, po której stronie stoi.",
    ),
    # Upgrade istniejącej Mirny → kupiec Targu Wielkiego (sufit ekonomii).
    dict(
        key="kupiec_vilnograd", label="Mirna Zbożowa, kupcowa Targu Wielkiego",
        npc_type="merchant", faction="gildie_vilnogradu", shop=1,
        shop_json=json.dumps(TARG_WIELKI_STOCK), quest=0, crafter=0, crafter_type=None,
        kw=["mirna", "targ", "targ wielki", "kupiec", "kupcowa", "rynek", "handel"],
        desc="Pierwsza kupcowa Targu Wielkiego — tam, gdzie kończą bieg wszystkie cztery "
             "trakty Volhynii. Ma asortyment o klasę wyżej niż całe pogranicze razem "
             "wzięte: najlepszą broń, zbroje, mikstury i zwoje, jakich na Kresach nikt "
             "nie widział. Kto ma złoto — kupi u niej wszystko; kto ma glejt — kupi taniej.",
        prompt="Bystra, szybka w rachunku, uprzejma dla każdego, kto ma czym płacić. Zna "
               "cenę wszystkiego i wartość każdego glejtu. Nie oszukuje — na Targu "
               "Wielkim reputacja jest droższa niż jeden dobry utarg. Chętnie doradzi, co "
               "kupić na daleką drogę.",
    ),
]

# ── Przypisania NPC → lokacja (hub = cała stolica, sub = dzielnica) ─────────────
NPC_ASSIGNMENTS = [
    # poziom huba: ikony widoczne z poziomu miasta
    ("vilnograd_stolica", "kanclerz_dobrogost", "resident"),
    ("vilnograd_stolica", "brat_aleksy_zlotnik", "resident"),
    ("vilnograd_stolica", "nocny_burmistrz", "resident"),
    ("vilnograd_stolica", "gundrik_zlota_waga", "resident"),
    # dzielnice
    ("vilnograd_zamek", "kanclerz_dobrogost", "resident"),
    ("vilnograd_dzielnica_gildii", "brat_aleksy_zlotnik", "resident"),
    ("vilnograd_dzielnica_gildii", "rachmistrzyni", "visitor"),        # przyjmuje raz w tygodniu
    ("vilnograd_dzielnica_zlodziei", "nocny_burmistrz", "resident"),
    ("vilnograd_enklawa_krasnoludzka", "gundrik_zlota_waga", "resident"),
    ("vilnograd_rynek", "kupiec_vilnograd", "resident"),               # Targ Wielki
]

_ICON_UPDATE = """
UPDATE npcs SET
  label=?, npc_type=?, description=?, personality_prompt=?, faction_key=?,
  is_shop=?, shop_inventory_json=?, is_quest_giver=?, is_crafter=?, crafter_type=?,
  keyword_triggers=?, is_active=1, review_status='permanent', updated_at=datetime('now')
WHERE key=?
"""


def apply(conn):
    n_fac = n_npc = n_na = 0
    for key, name, ftype, desc in FACTIONS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO game_config_factions (key, name, faction_type, description, is_active) "
            "VALUES (?, ?, ?, ?, 1)", (key, name, ftype, desc))
        n_fac += cur.rowcount or 0

    for n in NPCS:
        cur = conn.execute(
            """INSERT OR IGNORE INTO npcs
                 (key, label, npc_type, description, personality_json, personality_prompt,
                  is_shop, shop_inventory_json, is_quest_giver, is_crafter, crafter_type,
                  faction_key, is_active, review_status, keyword_triggers)
               VALUES (?, ?, ?, ?, '{}', ?, ?, ?, ?, ?, ?, ?, 1, 'permanent', ?)""",
            (n["key"], n["label"], n["npc_type"], n["desc"], n["prompt"],
             int(n["shop"]), n["shop_json"], int(n["quest"]), int(n["crafter"]),
             n["crafter_type"], n["faction"],
             json.dumps(n["kw"], ensure_ascii=False)))
        n_npc += cur.rowcount or 0
        # wymuś kanoniczne pola także na już-istniejących (Gundrik/Mirna)
        conn.execute(_ICON_UPDATE, (
            n["label"], n["npc_type"], n["desc"], n["prompt"], n["faction"],
            int(n["shop"]), n["shop_json"], int(n["quest"]), int(n["crafter"]),
            n["crafter_type"], json.dumps(n["kw"], ensure_ascii=False), n["key"]))

    for loc, npc, atype in NPC_ASSIGNMENTS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO location_npc_assignments (location_key, npc_key, assignment_type, is_active) "
            "VALUES (?, ?, ?, 1)", (loc, npc, atype))
        n_na += cur.rowcount or 0

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
            problems.append(f"przypisanie NPC do nieistniejącej lokacji: {loc}")
        if not conn.execute("SELECT 1 FROM npcs WHERE key=? AND is_active=1", (npc,)).fetchone():
            problems.append(f"nieistniejący NPC: {npc}")
    for n in NPCS:
        if n["faction"] and not conn.execute(
                "SELECT 1 FROM game_config_factions WHERE key=?", (n["faction"],)).fetchone():
            problems.append(f"{n['key']}: brak frakcji {n['faction']}")
    # sklepy top-tier muszą mieć niepusty asortyment
    for k in ("kupiec_vilnograd", "gundrik_zlota_waga"):
        row = conn.execute("SELECT shop_inventory_json FROM npcs WHERE key=?", (k,)).fetchone()
        if not row or not row["shop_inventory_json"] or row["shop_inventory_json"] in ("[]", ""):
            problems.append(f"sklep {k}: pusty asortyment")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    res = apply(conn)
    print(f"  frakcje stolicy nowe:   {res['factions']}")
    print(f"  NPC-ikony nowe:         {res['npcs']}")
    print(f"  przypisania NPC nowe:   {res['npc_assignments']}")

    rows = conn.execute("""
        SELECT gl.label AS loc, n.label AS npc, a.assignment_type, n.is_shop
        FROM location_npc_assignments a
        JOIN game_locations gl ON gl.key = a.location_key
        JOIN npcs n ON n.key = a.npc_key
        WHERE a.location_key LIKE 'vilnograd%' AND a.is_active = 1
        ORDER BY gl.label, n.label""").fetchall()
    print(f"\n  obsada Vilnogradu ({len(rows)} przypisań):")
    for r in rows:
        tag = " 🛒" if r["is_shop"] else ""
        print(f"    {r['loc']:38s} ← {r['npc']}{tag} ({r['assignment_type']})")

    problems = verify(conn)
    conn.commit()
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
