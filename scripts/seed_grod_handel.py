#!/usr/bin/env python3
"""SG-5b (#1481) — handel i usługi Kamiennego Grodu: asortyment 3 punktów handlowych.

Źródło prawdy: docs/world/regions/siwe_granie.md §4 (lokacje Grodu), §6 (sól), §8 (obsada).
Wzorzec: scripts/seed_siwe_granie_obsada.py (SG-6) — ta sama mechanika, inny zakres.

DLACZEGO TO JEST POTRZEBNE (read-path silnika, ustalone recon 2026-07-20):
  `shop_service._effective_shop_entries()` działa dwutorowo:
    1) jawny `npcs.shop_inventory_json` — wygrywa zawsze,
    2) pusty → `_default_stock_for_npc()` dobiera z katalogu `game_items` NAJTAŃSZE
       pozycje wg roli NPC: is_crafter → 4 bronie + 3 zbroje, uzdrowiciel (słowa
       klucze w key/label) → 6 konsumowalnych, reszta → 3 konsum. + 3 przedmioty + 1 broń.
  Efekt uboczny: mistrz Wielkiej Kuźni z pustym polem sprzedawał kij, laskę,
  drewnianą tarczę i sztylet + rękawiczki/czapkę/płaszcz — czyli najtańszy śmieć
  z całej gry, bez związku z krainą. Dlatego trzy punkty Grodu dostają JAWNY
  asortyment; reszta gry zostaje na dynamicznym fallbacku (29/31 kupców).

Ceny NIE są tu zapisywane — cena bierze się zawsze z `game_items.price_gp`
przemnożonej przez `shop_service.combined_buy_multiplier()` (CHA × targowanie ×
rasa krasnolud −15% × reputacja regionu/frakcji × noc × wydarzenie regionalne,
klamra [0.4, 2.0]). Seeder wpina TOWAR, nie cennik.

Usługi (nocleg/posiłek/naprawa) NIE są tu seedowane — `location_services.py`
wnioskuje je ze `location_subtype` lokacji: 'smithy' → blacksmith_repair,
'tavern' → inn_night / inn_night_fine / tavern_meal / tavern_drink / stable_night.
Suby Grodu mają już właściwe podtypy (weryfikacja poniżej, funkcja verify()).

Idempotentny: UPDATE po kluczu NPC, ta sama treść przy powtórnym uruchomieniu.
Każdy klucz towaru jest walidowany względem katalogu (`game_items`, is_active=1,
price_gp > 0) — nieistniejący klucz = błąd, nie cichy pusty sklep.

URUCHOMIENIE (wewnątrz kontenera backendu):
    docker cp scripts/seed_grod_handel.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_grod_handel.py
    docker exec ai-gm-dev-backend-1 python /app/seed_grod_handel.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

# ── Trzy punkty handlowe Grodu (NPC i lokacje istnieją od SG-5/SG-6) ──────────
#
# TODO SG-7 (sól): docs/world/regions/siwe_granie.md §6 opisuje trzy przedmioty
# solne (Krąg soli, Solona klinga, Szczypta soli) jako drugi towar eksportowy
# Grań. Na 2026-07-20 NIE MA ich w katalogu `game_items` (sprawdzone: 0 trafień na
# 'sol'/'salt'), więc Helga handluje na razie zaopatrzeniem karawanowym. Gdy SG-7
# doda przedmioty solne — dopisać ich klucze do HELGA i przepuścić seeder ponownie.
SHOPS: list[dict] = [
    dict(
        npc_key="torvin_mistrz_kuzni",
        location_key="grod_wielka_kuznia",
        # Wielka Kuźnia: krasnoludzki warsztat — obuchy i ciężkie żelastwo,
        # pełny przekrój zbroi, drobiazgi kowalskie. Nie ma tu łuków ani różdżek.
        stock=[
            ("weapon", "dagger"),
            ("weapon", "mace"),
            ("weapon", "spear"),
            ("weapon", "warhammer"),
            ("weapon", "battleaxe"),
            ("weapon", "greataxe"),
            ("weapon", "shield"),
            ("weapon", "tower_shield"),
            ("armor", "iron_helm"),
            ("armor", "great_helm"),
            ("armor", "plate_gauntlets"),
            ("armor", "leather_armor"),
            ("armor", "chainmail_shirt"),
            ("armor", "scale_mail"),
            ("armor", "breastplate"),
            ("item", "whetstone"),
            ("item", "hammer_small"),
            ("item", "iron_spikes_10"),
            ("item", "iron_ore"),
        ],
    ),
    dict(
        npc_key="helga_solnobroda",
        location_key="grod_targ_solny",
        # Targ Solny: koniec traktu karawanowego — zaopatrzenie na drogę i futra
        # na przełęcze. Broni nie sprzedaje (od tego jest Kuźnia po drugiej stronie).
        stock=[
            ("item", "rope_hemp"),
            ("item", "torch"),
            ("item", "tinderbox"),
            ("item", "oil_flask"),
            ("item", "waterskin"),
            ("item", "bedroll"),
            ("item", "backpack"),
            ("item", "belt_pouch"),
            ("item", "shovel"),
            ("item", "lantern_hooded"),
            ("item", "climbing_kit"),
            ("consumable", "bandage"),
            ("consumable", "healing_herb"),
            ("consumable", "arrows"),
            ("consumable", "bolts"),
            ("armor", "travelers_cloak"),
            ("armor", "hooded_cloak"),
            ("armor", "fur_mantle"),
        ],
    ),
    dict(
        npc_key="grimm_rdzawy",
        location_key="grod_pod_rdzawym_mlotem",
        # Szynk: sam nocleg i strawa idą przez modal Usług (podtyp 'tavern'),
        # więc Grimm trzyma na zapleczu tylko to, po co pyta gość nad ranem.
        # Plotki NIE tutaj — to osobne zadanie SG-6b (#1190, world_rumors).
        stock=[
            ("consumable", "bandage"),
            ("consumable", "sobering_draught"),
            ("consumable", "healing_herb"),
            ("item", "waterskin"),
            ("item", "bedroll"),
            ("item", "torch"),
            ("item", "dice_set"),
        ],
    ),
]

# Podtyp lokacji → usługi, których oczekujemy po `location_services.py`.
EXPECTED_SERVICES: dict[str, tuple[str, ...]] = {
    "grod_wielka_kuznia": ("blacksmith_repair",),
    "grod_pod_rdzawym_mlotem": ("inn_night", "tavern_meal"),
}


def _validate_stock(conn: sqlite3.Connection) -> list[str]:
    """Każdy klucz musi istnieć w katalogu z ceną > 0 — inaczej sklep byłby pusty."""
    problems: list[str] = []
    for shop in SHOPS:
        for kind, key in shop["stock"]:
            row = conn.execute(
                "SELECT kind, COALESCE(price_gp, 0) AS p FROM game_items "
                "WHERE key = ? AND is_active = 1",
                (key,),
            ).fetchone()
            if not row:
                problems.append(f"{shop['npc_key']}: brak w katalogu → {key}")
                continue
            if float(row["p"]) <= 0:
                problems.append(f"{shop['npc_key']}: cena 0 → {key}")
            if str(row["kind"]) != kind:
                problems.append(
                    f"{shop['npc_key']}: {key} ma kind='{row['kind']}', wpisano '{kind}'"
                )
    return problems


def apply(conn: sqlite3.Connection) -> dict:
    res = {"updated": 0, "unchanged": 0}
    for shop in SHOPS:
        payload = json.dumps(
            [{"type": t, "key": k} for t, k in shop["stock"]], ensure_ascii=False
        )
        row = conn.execute(
            "SELECT id, shop_inventory_json FROM npcs WHERE key = ?", (shop["npc_key"],)
        ).fetchone()
        if not row:
            raise SystemExit(f"BŁĄD: brak NPC {shop['npc_key']} — najpierw SG-6 (obsada)")
        if (row["shop_inventory_json"] or "") == payload:
            res["unchanged"] += 1
            continue
        conn.execute(
            "UPDATE npcs SET shop_inventory_json = ?, is_shop = 1, is_active = 1, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (payload, int(row["id"])),
        )
        res["updated"] += 1
    return res


def verify(conn: sqlite3.Connection) -> list[str]:
    problems = _validate_stock(conn)
    for shop in SHOPS:
        npc = conn.execute(
            "SELECT id, is_shop, is_active, shop_inventory_json FROM npcs WHERE key = ?",
            (shop["npc_key"],),
        ).fetchone()
        if not npc or int(npc["is_shop"] or 0) != 1 or int(npc["is_active"] or 0) != 1:
            problems.append(f"{shop['npc_key']}: nie jest aktywnym sklepem")
            continue
        if len(json.loads(npc["shop_inventory_json"] or "[]")) != len(shop["stock"]):
            problems.append(f"{shop['npc_key']}: asortyment nie zapisał się w całości")
        # Kupno waliduje obecność NPC w lokacji (shop_service._npc_serves_location).
        assigned = conn.execute(
            "SELECT 1 FROM location_npc_assignments "
            "WHERE npc_key = ? AND location_key = ? AND COALESCE(is_active, 1) = 1",
            (shop["npc_key"], shop["location_key"]),
        ).fetchone()
        if not assigned:
            problems.append(
                f"{shop['npc_key']}: brak przypisania do {shop['location_key']}"
            )
    # Usługi: sprawdzamy realnym resolverem, nie założeniem o podtypie.
    try:
        sys.path.insert(0, "/app")
        from app.services.location_services import get_available_service_keys

        for loc, expected in EXPECTED_SERVICES.items():
            keys = get_available_service_keys(conn, loc)
            missing = [s for s in expected if s not in keys]
            if missing:
                problems.append(f"{loc}: brak usług {missing} (podtyp lokacji?)")
    except ImportError:
        problems.append("nie udało się zaimportować location_services — usługi niesprawdzone")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    pre = _validate_stock(conn)
    if pre:
        print("PRZERWANE — asortyment nie zgadza się z katalogiem:")
        for p in pre:
            print("  " + p)
        return 1

    res = apply(conn)
    conn.commit()
    print(f"  sklepy zaktualizowane:   {res['updated']}")
    print(f"  bez zmian (idempotent):  {res['unchanged']}")

    for shop in SHOPS:
        row = conn.execute(
            "SELECT n.label, n.faction_key, n.shop_inventory_json FROM npcs n WHERE n.key = ?",
            (shop["npc_key"],),
        ).fetchone()
        entries = json.loads(row["shop_inventory_json"] or "[]")
        total = conn.execute(
            "SELECT COUNT(*) FROM game_items WHERE key IN (%s)"
            % ",".join("?" * len(entries)),
            [e["key"] for e in entries],
        ).fetchone()[0]
        print(
            f"\n  {row['label']} @ {shop['location_key']} "
            f"(frakcja: {row['faction_key'] or '—'})"
        )
        print(f"    pozycji: {len(entries)} (w katalogu: {total})")

    problems = verify(conn)
    conn.close()
    print("\n" + ("KONTROLA OK" if not problems else "PROBLEMY:\n  " + "\n  ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
