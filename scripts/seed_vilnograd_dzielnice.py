#!/usr/bin/env python3
"""KN-5 (#1500) — Vilnograd: hub-gigant + dzielnice (suby) + mapa lokalna.

Źródło prawdy: docs/world/regions/koronne_niziny.md §4 (dzielnice). Wzorzec:
scripts/seed_szept_koron.py (CB-5) — ta sama mechanika (create_location + local map),
inna kraina. Spec dzielnic INLINE (jeden plik = jedno źródło dla KN-5).

Hub `vilnograd_stolica` (macro) istnieje od wcześniejszej fali na hexie (-23,22).
Ten skrypt:
  * dostraja hub do rangi stolicy-giganta (tier 3, opis),
  * dostraja 5 istniejących subów do kanonu §4 (label/subtype/tier/opis) — BEZ zmiany
    kluczy (klucze reużyte, żeby nie osierocić przypisań NPC/sklepów),
  * dokłada 2 brakujące dzielnice: Dzielnica Gildii + Port Rzeczny,
  * zostawia 2 suby-usługi z legacy (tawerna = zajazd §8, kuźnia = naprawa) nietknięte,
  * buduje mapę lokalną map_level=1 (auto_assign_local_hex, próg ≥2 suby).

BEZ limitu subów (weryfikacja przed pracą: local_hex_service.LOCAL_MAP_THRESHOLD=2
to MINIMUM; adventure_forge #1212 odrzuca tylko >1 hub, nie liczbę subów). 9 subów OK.

NIE dotyka world_hexes map_level=0 (mapa nadrzędna = własność Piotra). auto_assign
tworzy tylko lokalne hexy map_level=1.

Idempotentny — można puszczać wielokrotnie.

URUCHOMIENIE (wewnątrz kontenera backendu — potrzebuje app.services):
    docker cp scripts/seed_vilnograd_dzielnice.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_vilnograd_dzielnice.py
    docker exec ai-gm-dev-backend-1 python /app/seed_vilnograd_dzielnice.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.hex_location_link import link_location_to_hex  # noqa: E402
from app.services.local_hex_service import (  # noqa: E402
    auto_assign_local_hex,
    get_hub_hex_id,
    get_local_hexes,
    normalize_hub_local_hexes,
)
from app.services.location_factory import LocationSource, create_location  # noqa: E402

REGION = "koronne_niziny"
HUB_KEY = "vilnograd_stolica"
HUB_HEX = (-23, 22)  # istniejący hex overworld (mapa Piotra) — tylko relink, nie ruszamy

HUB_LABEL = "Vilnograd, Stolica"
HUB_DESC = (
    "Największe miasto świata i cywilizacyjny sufit gry — latarnia porządku z Ery "
    "Latarni, dziś świecąca na kredyt. Mury obejmują siedem dzielnic o osobnym prawie i "
    "obyczaju: Zamek Królewski, Dzielnicę Gildii, Dzielnicę Złodziei, Katedrę Światła, "
    "Targ Wielki, Enklawę Krasnoludzką i Port Rzeczny nad wielką rzeką. Wszystko tu "
    "działa — pytanie tylko, dla kogo. Mrok tej stolicy nie ma kłów, ma pieczęcie, "
    "weksle i uśmiech; noża w plecy nie dostrzeżesz, bo przyjdzie w rękawiczce."
)

# ── Dzielnice §4. Klucze reużyte tam, gdzie sub już istniał (bez rename = bez sierot).
#    subtype niesie słowa-klucze usług/klimatu; safe=0 → wyższa szansa zdarzenia lokalnie.
#    kolejność listy = kolejność kanoniczna dzielnic (dla czytelności logu).
DISTRICTS = [
    dict(
        key="vilnograd_zamek", label="Vilnograd: Zamek Królewski",
        subtype="castle", icon="castle", tier=3, safe=1,
        desc="Serce jawnej władzy — tron, sale audiencyjne i gwardia królewska. Tu "
             "Korona pokazuje twarz: złoto, marmur i porządek. Pod przepychem sączy "
             "się jednak inny nurt — Rada Czterech kupuje ratami to, czego nie da się "
             "zdobyć jawnie. Kanclerz Dobrogost wita gości uśmiechem gładszym niż "
             "posadzka.",
    ),
    dict(
        key="vilnograd_dzielnica_gildii", label="Vilnograd: Dzielnica Gildii",
        subtype="guild-quarter", icon="town", tier=2, safe=1,
        desc="Kwartał cechów, kantorów rachunkowych i pieczęci — tu bije handlowe "
             "serce stolicy i tu, w skórze szacownej gildii, kult ma salony zamiast "
             "ruin. Gildmistrz Brat Aleksy Złotnik trzyma księgi cechu, a raz w "
             "tygodniu przyjmuje ktoś, kogo nazywają tylko „Rachmistrzynią” — pośredniczka "
             "Rady, której imienia nie zna nikt.",
    ),
    dict(
        key="vilnograd_dzielnica_zlodziei", label="Vilnograd: Dzielnica Złodziei",
        subtype="thieves-quarter", icon="town", tier=2, safe=0,
        desc="Świat Mizela: zaułki, mecenaty przemytu i cichy porządek półświatka, "
             "który działa sprawniej niż niejeden urząd Korony. Rządzi tu „Nocny "
             "Burmistrz” — pseudonim-urząd, o którym szepcze się, że bywa przechodni: "
             "nie człowiek, lecz stanowisko. Człowieczy łotrzyk stolicy wyrasta z tych "
             "właśnie bruków.",
    ),
    dict(
        key="vilnograd_swiatynia_swiatla", label="Vilnograd: Katedra Światła",
        subtype="cathedral", icon="town", tier=2, safe=1,
        desc="Główna katedra Światła w stolicy — leczenie, błogosławieństwa i "
             "odklinanie pod złoconą kopułą. Kapłani śpiewają o porządku równie gładko, "
             "jak dworzanie kłamią; wierni nie pytają, czyja ręka opłaca świece. "
             "Światło świeci nad Vilnogradem najjaśniej i najdrożej.",
    ),
    dict(
        key="vilnograd_rynek", label="Vilnograd: Targ Wielki",
        subtype="grand-market", icon="town", tier=2, safe=1,
        desc="Największy targ świata — wszystkie cztery trakty Volhynii kończą bieg "
             "tutaj, więc i asortyment jest o klasę wyżej niż na pograniczu: najlepsza "
             "broń, zbroje, mikstury, zwoje i towary, których na Kresach nikt nie "
             "widział. Przy Targu stoi zajazd, w którym ludzki przybysz budzi się na "
             "pierwszą scenę stolicy. Kto ma złoto — kupi tu wszystko. Kto ma glejt — "
             "kupi taniej.",
    ),
    dict(
        key="vilnograd_enklawa_krasnoludzka", label="Vilnograd: Enklawa Krasnoludzka",
        subtype="kantor", icon="town", tier=2, safe=1,
        desc="Krasnoludzki kwartał kantorów i złotników — najbezpieczniejsze skarbce "
             "stolicy i najczystsza robota jubilerska w świecie. Gundrik Złota Waga "
             "waży kruszec dokładniej niż Korona liczy podatki: u niego zamienisz "
             "majątek w klejnot albo w papier, którego kradzież ani śmierć ci nie "
             "odbiorą. (Weksle kantorów — pełna mechanika w KN-8; tu sam kantor.)",
    ),
    dict(
        key="vilnograd_port_rzeczny", label="Vilnograd: Port Rzeczny",
        subtype="river-port", icon="town", tier=2, safe=1,
        desc="Nabrzeża wielkiej rzeki, która wiąże stolicę z Wybrzeżem Łez na "
             "południu — barki ze zbożem, sól z południa, kontrabanda pod pokładem i "
             "celnicy, którzy patrzą tam, gdzie im każą patrzeć. Tędy do Vilnogradu "
             "wpływa wszystko, czego trakty nie uniosą, i wypływa wszystko, o czym "
             "lepiej nie pytać.",
    ),
]

# suby-usługi z legacy zostawiamy nietknięte (są aktywne, wejdą do mapy lokalnej):
#   vilnograd_tawerna_pod_korona (zajazd — start §8), vilnograd_kuznia (naprawa).

_REFRESH = """
UPDATE game_locations SET
  label=?, description=?, region=?, map_icon=?, tier=?,
  location_subtype=?, safe_for_rest=?, is_active=1, updated_at=datetime('now')
WHERE key=?
"""


def upsert_district(conn, spec, hub_id):
    res = create_location(
        conn,
        key=spec["key"], label=spec["label"], source=LocationSource.SEED,
        description=spec["desc"], location_type="sub",
        parent_key=HUB_KEY, parent_id=hub_id, region=REGION,
        map_icon=spec["icon"], tier=spec["tier"], biome="urban",
        location_subtype=spec["subtype"], safe_for_rest=spec["safe"],
        visible_before_visit=0, canonical=True, commit=False,
    )
    if not res["created"]:
        conn.execute(_REFRESH, (
            spec["label"], spec["desc"], REGION, spec["icon"], spec["tier"],
            spec["subtype"], spec["safe"], spec["key"],
        ))
        conn.execute(
            "UPDATE game_locations SET parent_key=?, parent_id=? WHERE key=?",
            (HUB_KEY, hub_id, spec["key"]),
        )
    return res["created"]


def reattach_local_hexes(conn, sub_keys):
    hub_hex_id = get_hub_hex_id(conn, HUB_KEY)
    if hub_hex_id is None or not sub_keys:
        return 0
    marks = ",".join("?" * len(sub_keys))
    cur = conn.execute(
        f"UPDATE world_hexes SET parent_hex_id=? "
        f"WHERE map_level=1 AND location_key IN ({marks}) "
        f"AND (parent_hex_id IS NULL OR parent_hex_id != ?)",
        (hub_hex_id, *sub_keys, hub_hex_id),
    )
    return cur.rowcount or 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    # ── 1. hub musi istnieć i wisieć na swoim hexie overworld ─────────────────
    hub = conn.execute("SELECT id FROM game_locations WHERE key=?", (HUB_KEY,)).fetchone()
    if hub is None:
        print(f"  ✗ brak huba {HUB_KEY} — najpierw seed makro Koronnych Nizin")
        return 1
    hub_id = hub["id"]
    q, r = HUB_HEX
    if conn.execute("SELECT 1 FROM world_hexes WHERE map_level=0 AND q=? AND r=?", (q, r)).fetchone() is None:
        print(f"  ✗ brak hexa ({q},{r}) — najpierw seed_world_map.py --region {REGION}")
        return 1
    conn.execute(
        "UPDATE game_locations SET label=?, description=?, region=?, tier=3, "
        "location_type='macro', location_subtype='city', map_icon='castle', "
        "is_active=1, updated_at=datetime('now') WHERE key=?",
        (HUB_LABEL, HUB_DESC, REGION, HUB_KEY),
    )
    link_location_to_hex(conn, HUB_KEY, q, r)
    print(f"  HUB {HUB_KEY} id={hub_id} @ ({q},{r}) tier=3")

    # ── 2. dzielnice (suby) ──────────────────────────────────────────────────
    for s in DISTRICTS:
        created = upsert_district(conn, s, hub_id)
        print(f"  dz. {s['label']:36s} tier={s['tier']} safe={s['safe']} {'NEW' if created else 'refresh'}")
    conn.commit()

    # ── 3. naprawa osieroconych lokalnych hexów (po ewentualnym reseedzie) ────
    all_subs = [r["key"] for r in conn.execute(
        "SELECT key FROM game_locations WHERE parent_key=? AND is_active=1", (HUB_KEY,))]
    fixed = reattach_local_hexes(conn, all_subs)
    if fixed:
        print(f"  przepięto lokalnych hexów na hex huba: {fixed}")
    conn.commit()

    # ── 4. mapa lokalna map_level=1 (FAZA ML #993; próg ≥2 suby) ──────────────
    seed_sub = DISTRICTS[0]["key"]
    auto_assign_local_hex(conn, seed_sub, HUB_KEY)
    normalize_hub_local_hexes(conn, HUB_KEY)
    conn.commit()

    local = get_local_hexes(conn, HUB_KEY)
    print(f"\n  mapa lokalna: {len(local)} hexów map_level=1")
    for h in sorted(local, key=lambda x: (x["q"], x["r"])):
        print(f"    ({h['q']:>2},{h['r']:>2})  {h['label']}")

    # ── kontrola ─────────────────────────────────────────────────────────────
    problems = []
    canon = conn.execute(
        "SELECT location_key FROM world_hexes WHERE map_level=0 AND q=? AND r=?", (q, r)
    ).fetchone()
    if not canon or canon["location_key"] != HUB_KEY:
        problems.append(f"hex ({q},{r}) nie wskazuje na {HUB_KEY}")
    orphan = conn.execute(
        "SELECT count(*) c FROM game_locations WHERE parent_key=? AND is_active=1 "
        "AND key NOT IN (SELECT location_key FROM world_hexes WHERE map_level=1 "
        "AND location_key IS NOT NULL)", (HUB_KEY,)).fetchone()["c"]
    if orphan:
        problems.append(f"{orphan} sub-lokacji bez hexa na mapie lokalnej")
    for s in DISTRICTS:
        if not conn.execute("SELECT 1 FROM game_locations WHERE key=? AND is_active=1", (s["key"],)).fetchone():
            problems.append(f"dzielnica {s['key']} nieaktywna/niezaseedowana")

    n_subs = conn.execute(
        "SELECT count(*) c FROM game_locations WHERE parent_key=? AND is_active=1", (HUB_KEY,)
    ).fetchone()["c"]
    print(f"\n  aktywnych subów huba: {n_subs}")

    conn.commit()
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY: " + "; ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
