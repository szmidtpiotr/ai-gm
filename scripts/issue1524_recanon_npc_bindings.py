#!/usr/bin/env python3
"""#1524 fala 1 — jednorazowa przebudowa kanonu obsady lokacji (data/seeds/content).

Uruchamiany RAZ przy wdrożeniu issue #1524; zostawiony w repo jako zapis tego,
co dokładnie zrobiono z treścią (a nie tylko wynikowy diff 3 tysięcy linii JSON).

Robi dokładnie to, co uzgodniono w komentarzach #1524:

* `location_npc_assignments` = kanon; `game_locations.npc_keys` przeliczone z niego,
* gospodarze schodzą z makro-hubów do sub-lokacji (decyzja 2),
* brakujące wnętrza (kuźnie, apteka, izba znachora, kram, chaty) dopisane,
* gospoda „Pod Złamanym Rogiem" wchodzi do kanonu i wiąże się z heksem (24,13),
* śmieci `*_u31`, przypisania-duchy i osierocone suby `trzech_krukow_2_*` wylatują,
* legacy seed `npc_locations.json` kasowany.

Idempotentny: powtórne uruchomienie nic nie zmienia.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "data" / "seeds" / "content"
LOCATIONS = CONTENT / "game_locations.json"
ASSIGNMENTS = CONTENT / "location_npc_assignments.json"
NPCS = CONTENT / "npcs.json"
LEGACY = CONTENT / "npc_locations.json"
KRESY_MAP = ROOT / "data" / "regions" / "region_kresy.json"

INN_MACRO = "gospoda_pod_zlamanym_rogiem"
INN_HEX = (24, 13)
INN_HOST = "karczmarka_zlamany_rog"

# ── Nowe wnętrza: (klucz, rodzic, etykieta, podtyp, opis) ────────────────────
# Każde powstaje dlatego, że gospodarz nie miał gdzie zejść z makro-huba.
NEW_SUBS: list[tuple[str, str, str, str, str]] = [
    ("vilnograd_kuznia", "vilnograd_stolica", "Vilnograd: Kuźnia Pod Kowadłem", "smithy",
     "Stołeczna kuźnia cechowa. Trzy paleniska, wieczny hałas, zamówienia Korony przed wszystkimi innymi."),
    ("volhynia_kuznia", "volhynia_kupiecka", "Volhynia: Kuźnia Cechowa", "smithy",
     "Kuźnia pracująca na potrzeby karawan — podkowy, okucia, osie. Naprawa na poczekaniu, za dopłatą."),
    ("volhynia_apteka", "volhynia_kupiecka", "Volhynia: Apteka Pod Wagą", "shop",
     "Ciasna izba pachnąca goździkiem i spirytusem. Wagi mosiężne, słoje podpisane cyrylicą i łaciną."),
    ("czarnogrod_kuznia", "czarnogrod_port", "Czarnogród: Kuźnia Portowa", "smithy",
     "Kuźnia przy nabrzeżu — kotwice, haki, łańcuchy. O broń nikt tu głośno nie pyta."),
    ("czarnogrod_izba_chirurga", "czarnogrod_port", "Czarnogród: Izba Chirurga", "temple",
     "Izba nad składem lin. Stół, wiadro, skrzynka narzędzi. Płaci się z góry i nie zadaje pytań."),
    ("zatoka_kuznia", "zatoka_topielcow", "Zatoka: Kuźnia Kotwiczna", "smithy",
     "Kuźnia wbita w skalną półkę nad dokami. Reperuje wszystko, co pirat zdąży wyszczerbić."),
    ("zatoka_izba_znachora", "zatoka_topielcow", "Zatoka: Izba Znachora", "temple",
     "Chata z wyrzuconego przez morze drewna. Zioła suszą się pod powałą, obok amuletów z muszli."),
    ("brzezino_kuznia", "brzezino", "Brzezino: Kuźnia Pod Brzozą", "smithy",
     "Mała wiejska kuźnia. Siekiery i kliny dla drwali, rzadko coś ostrzejszego."),
    ("brzezino_kram", "brzezino", "Brzezino: Kram Przy Trakcie", "market",
     "Kram gildii kupieckiej przy trakcie. Sól, gwoździe, płótno — i wieści z Vilnogradu."),
    ("strazyn_kuznia", "strazyn", "Strażyn: Kuźnia Twierdzy", "smithy",
     "Kuźnia w murach twierdzy. Pracuje na wojsko: naprawa zbroi i grotów przed każdą wartą."),
    ("cieszowice_kuznia", "cieszowice", "Cieszowice: Kuźnia Pod Podkową", "smithy",
     "Kuźnia przy wjeździe do wsi. Sierp, lemiesz, podkowa — broń tylko na wyraźne zamówienie."),
    ("cieszowice_chata_soltysa", "cieszowice", "Cieszowice: Chata Sołtysa", "town",
     "Największa chata we wsi. Tu zapadają decyzje o daninie, warcie i o tym, kogo wpuścić na noc."),
    ("bor_chata_jagi", "bor_zmarlych", "Bór: Chata Wiedźmy Jagi", "town",
     "Chata na uboczu, obsypana popiołem i suszonym zielem. Ktokolwiek tu trafia, trafia w potrzebie."),
]

# ── Docelowa obsada: klucz sub-lokacji → lista NPC ───────────────────────────
# Wpisy powstały z ręcznego przeniesienia 33 gospodarzy z makro-hubów; reszta
# (16 wierszy) była duplikatem tego, co i tak stało już w subie — te po prostu znikają.
RELOCATE: dict[str, list[str]] = {
    # Vilnograd — stolica
    "vilnograd_kuznia": ["blacksmith_goran", "kowal_vilnograd"],
    "vilnograd_zamek": ["quest_giver_eldran", "kapitan_krolewski"],
    "vilnograd_swiatynia_swiatla": ["uzdrowiciel_vilnograd", "kronikarz_vilnograd"],
    "vilnograd_rynek": ["kupiec_vilnograd"],
    # Volhynia — miasto kupieckie
    "volhynia_targowisko": ["merchant_aldric"],
    "volhynia_gildia_kupcow": ["gildmistrz_volhynia"],
    "volhynia_kuznia": ["kowal_volhynia"],
    "volhynia_apteka": ["aptekarka_volhynia"],
    # Czarnogród — port
    "czarnogrod_nabrzeze": ["kapitan_smolny"],
    "czarnogrod_kuznia": ["kowal_czarnogrod"],
    "czarnogrod_izba_chirurga": ["chirurg_czarnogrod"],
    # Klasztor Iskry
    "klasztor_iskry_kaplica_glowna": ["matka_klasztor"],
    "klasztor_iskry_biblioteka": ["brat_tomasz_kronikarz"],
    # Zatoka Topielców
    "zatoka_pirackie_doki": ["rybak_stary_zatoka"],
    "zatoka_kuznia": ["kowal_zatoka"],
    "zatoka_izba_znachora": ["uzdrowiciel_zatoka"],
    # Brzezino
    "brzezino_kuznia": ["kowal_brzezino"],
    "brzezino_kram": ["gildia_kupiecka_brzezino"],
    "brzezino_swieta_polanka": ["zielarka_brzezino"],
    # Wolanka
    "wolanka_kosciol_swietego_floriana": ["zielarka_wolanka"],
    # Strażyn
    "strazyn_kuznia": ["kowal_strazyn"],
    "strazyn_kantyna": ["gildia_kupiecka_strazyn"],
    # Cieszowice
    "cieszowice_kuznia": ["kowal_cieszowice"],
    "cieszowice_chata_soltysa": ["soltys_cieszowice"],
    # Step Wilków / Bór Zmarłych
    "step_obozowisko_koczownikow": ["lowczy_step"],
    "bor_chata_jagi": ["wiedzma_jaga"],
    # Karczma Pod Trzema Krukami — Marta prowadzi pokoje, karczmarz szynkwas.
    # (Kanon lore wiązał Martę z „Pod Złamanym Rogiem", ale szablon kampanii
    #  „Pierwsze Kroki" gra nią w Krukach — gospoda dostaje własnego NPC.)
    "trzech_krukow_pokoje_kupcow": ["innkeeper_marta"],
    # Gospoda Pod Złamanym Rogiem
    "zlamany_rog_izba": [INN_HOST],
}

# Osierocone wnętrza po makro skasowanym w fali 0 (#1528).
DROP_LOCATIONS = {
    "trzech_krukow_2_shop", "trzech_krukow_2_shrine",
    "trzech_krukow_2_smithy", "trzech_krukow_2_tavern",
}

JUNK = ("_u31",)


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _is_junk(*keys: str) -> bool:
    return any(any(j in str(k or "") for j in JUNK) for k in keys)


def _template_row(src: dict, **over) -> dict:
    """Nowy wiersz lokacji na wzór istniejącego suba (te same kolumny co reszta seeda)."""
    row = dict(src)
    row.update(over)
    return row


def main() -> int:
    locs = _load(LOCATIONS)
    by_key = {r["key"]: r for r in locs}
    npcs = _load(NPCS)
    npc_keys = {n["key"] for n in npcs}

    # Nowe rekordy dostają id z wysokiego pasma: kanon jest wgrywany do baz, które
    # mają własne wiersze runtime (id rosną od max), więc max(seed)+1 kolidowałoby
    # z nimi przy `seed_content.py --apply` (UNIQUE constraint failed: game_locations.id).
    ID_BASE = 990000
    next_loc_id = ID_BASE + 1
    next_npc_id = ID_BASE + 1

    # 1) Osierocone suby po fali 0.
    locs = [r for r in locs if r["key"] not in DROP_LOCATIONS]
    by_key = {r["key"]: r for r in locs}

    # 2) Gospoda „Pod Złamanym Rogiem" + jej wnętrza.
    krukow = by_key["trzech_krukow"]
    izba = by_key["trzech_krukow_wielka_izba"]
    if INN_MACRO not in by_key:
        inn = _template_row(
            krukow,
            id=next_loc_id,
            key=INN_MACRO,
            label="Gospoda Pod Złamanym Rogiem",
            description=(
                "Gospoda przy trakcie, nazwana od myśliwskiego rogu, który pękł podczas "
                "obławy i wisi nad szynkwasem do dziś. Pierwszy dach nad głową dla tych, "
                "którzy dopiero wchodzą w Kresy."
            ),
            location_subtype="wayside-inn",
            world_hex_q=INN_HEX[0],
            world_hex_r=INN_HEX[1],
            npc_keys="[]",
            usage_count=0,
            created_by="seed",
            canonical=1,
            approved=1,
            review_status="permanent",
        )
        locs.append(inn)
        next_loc_id += 1
        by_key[INN_MACRO] = inn
        for sub_key, label, subtype, desc in (
            ("zlamany_rog_izba", "Pod Złamanym Rogiem: Izba Szynkowa", "tavern",
             "Niska izba z długim szynkwasem i pękniętym rogiem nad nim. Ciepło, gwarno, tanio."),
            ("zlamany_rog_pokoje", "Pod Złamanym Rogiem: Pokoje Na Górze", "tavern",
             "Cztery izdebki pod dachem. Siennik, świeca, zasuwa od środka — więcej gość nie dostanie."),
            ("zlamany_rog_stajnia", "Pod Złamanym Rogiem: Stajnia", "shop",
             "Stajnia na sześć koni, z workiem owsa na haku. Stajenny bierze grosz za noc i milczenie gratis."),
        ):
            if sub_key in by_key:
                continue
            row = _template_row(
                izba,
                id=next_loc_id,
                key=sub_key,
                label=label,
                description=desc,
                location_subtype=subtype,
                parent_id=inn["id"],
                parent_key=INN_MACRO,
                npc_keys="[]",
                usage_count=0,
                created_by="seed",
                canonical=1,
                approved=1,
                review_status="permanent",
            )
            locs.append(row)
            by_key[sub_key] = row
            next_loc_id += 1

    # 3) Nowe wnętrza pod gospodarzy schodzących z makro.
    for key, parent_key, label, subtype, desc in NEW_SUBS:
        if key in by_key:
            continue
        parent = by_key[parent_key]
        sibling = next(
            (r for r in locs if r.get("parent_key") == parent_key and r["key"] != key), parent
        )
        row = _template_row(
            sibling,
            id=next_loc_id,
            key=key,
            label=label,
            description=desc,
            location_type="sub",
            location_subtype=subtype,
            parent_id=parent["id"],
            parent_key=parent_key,
            npc_keys="[]",
            usage_count=0,
            created_by="seed",
            canonical=1,
            approved=1,
            review_status="permanent",
            world_hex_q=None,
            world_hex_r=None,
        )
        locs.append(row)
        by_key[key] = row
        next_loc_id += 1

    # 4) Nowy gospodarz gospody (Marta zostaje w Krukach — nie dublujemy postaci).
    if INN_HOST not in npc_keys:
        template = next(n for n in npcs if n["key"] == "karczmarz_krukow")
        host = dict(template)
        host.update(
            id=next_npc_id,
            key=INN_HOST,
            label="Hanka Rogowa, karczmarka",
            description=(
                "Gospodyni gospody Pod Złamanym Rogiem. Wdowa po myśliwym, którego róg wisi nad "
                "szynkwasem. Wie, kto przejeżdżał traktem i w którą stronę — ale mówi to "
                "dopiero po drugim dzbanku."
            ),
            personality_json=json.dumps(
                {
                    "personality": "rzeczowa, nieufna wobec obcych, lojalna wobec stałych gości",
                    "topics": ["trakt", "noclegi", "kto przejeżdżał", "wilki przy drodze"],
                    "secret": None,
                },
                ensure_ascii=False,
            ),
            image_url=None,
            image_url_raw=None,
            review_status="permanent",
            is_active=1,
        )
        npcs.append(host)
        npc_keys.add(INN_HOST)
        next_npc_id += 1

    # 5) Kanon przypisań: wyrzuć śmieci/duchy/makro, wstaw docelową obsadę.
    assignments = _load(ASSIGNMENTS)
    sub_parents = {r["key"]: r.get("parent_key") for r in locs}
    has_subs = {p for p in sub_parents.values() if p}

    kept: list[dict] = []
    for a in assignments:
        loc, npc = a["location_key"], a["npc_key"]
        if _is_junk(loc, npc):
            continue                      # śmieci testowe po U31
        if loc not in by_key or npc not in npc_keys:
            continue                      # przypisanie-duch
        if by_key[loc].get("location_type") == "macro" and loc in has_subs:
            continue                      # gospodarz zjeżdża do suba (decyzja 2)
        kept.append(a)

    seen = {(a["location_key"], a["npc_key"]) for a in kept}
    next_assign_id = max(int(a["id"]) for a in assignments) + 1
    for loc_key, keys in RELOCATE.items():
        for npc in keys:
            if npc not in npc_keys or loc_key not in by_key:
                raise SystemExit(f"BŁĄD: brak {npc!r} lub {loc_key!r} w kanonie")
            if (loc_key, npc) in seen:
                continue
            kept.append({
                "id": next_assign_id,
                "location_key": loc_key,
                "npc_key": npc,
                "assignment_type": "resident",
                "notes": None,
                "is_active": 1,
            })
            seen.add((loc_key, npc))
            next_assign_id += 1

    kept.sort(key=lambda a: (a["location_key"], a["npc_key"]))
    for i, a in enumerate(kept, start=1):
        a["id"] = i

    # 6) Lustro npc_keys — przeliczone z przypisań dla KAŻDEJ lokacji.
    mirror: dict[str, list[str]] = {}
    for a in kept:
        if int(a.get("is_active", 1) or 0) == 1:
            mirror.setdefault(a["location_key"], []).append(a["npc_key"])
    for row in locs:
        row["npc_keys"] = json.dumps(sorted(mirror.get(row["key"], [])), ensure_ascii=False)

    # 7) Heks (24,13) wskazuje gospodę.
    kresy = json.loads(KRESY_MAP.read_text(encoding="utf-8"))
    for hexrow in kresy["hexes"]:
        if (hexrow.get("q"), hexrow.get("r")) == INN_HEX:
            hexrow["location_key"] = INN_MACRO
            break

    _dump(LOCATIONS, locs)
    _dump(ASSIGNMENTS, kept)
    _dump(NPCS, npcs)
    KRESY_MAP.write_text(
        json.dumps(kresy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if LEGACY.exists():
        os.remove(LEGACY)

    print(f"lokacje: {len(locs)} · przypisania: {len(kept)} · NPC: {len(npcs)}")
    print(f"obsadzonych lokacji: {len(mirror)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
