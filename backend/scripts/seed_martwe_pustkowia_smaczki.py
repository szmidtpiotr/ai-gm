#!/usr/bin/env python3
"""MP-5 (#1494) — towar krainy do katalogu: sól premium + relikty + sprzęt kopacza.

Źródło prawdy: docs/world/regions/martwe_pustkowia.md §6 (sól premium, kościany
kompas), §4 (relikty z ruin), §1 (gorączka reliktów). Wzorzec: seed_czarnobor_smaczki.py
(CB-7) — INSERT OR REPLACE do legacy game_config_* + dual-write do game_items.

DLACZEGO TU (read-path silnika): sklepy i sprzedaż czytają `game_items`. Bez wpisu w
katalogu handel MP-5 wywala się na walidacji „brak w katalogu", a gracz nie może ani
kupić soli u Nadiry, ani sprzedać reliktu Fabianowi (skup = zwykły `sell_item` do NPC).

Sól premium (lore §6): trio z Siwych Grań — Krąg / Klinga / Szczypta — u Piętnowanych
w najczystszej postaci. Powstały tu, na progu pęknięć, więc tłumią Rdzeń najmocniej.
Kanonicznie te przedmioty NIE istniały jeszcze w katalogu (ani Granie ich nie sprzedawały
— por. TODO w seed_grod_handel.py); MP-5 jest punktem ich wdrożenia. Wartości startowe.

Idempotentny.

    docker cp scripts/seed_martwe_pustkowia_smaczki.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_martwe_pustkowia_smaczki.py
    docker exec ai-gm-dev-backend-1 python /app/seed_martwe_pustkowia_smaczki.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

REGION = "martwe_pustkowia"


def _cols(db: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}


def _upsert(db: sqlite3.Connection, table: str, row: dict, valid: set[str]) -> None:
    row = {k: v for k, v in row.items() if k in valid}
    keys = list(row)
    placeholders = ",".join(["?"] * len(keys))
    collist = ",".join(keys)
    db.execute(
        f"INSERT OR REPLACE INTO {table} ({collist}) VALUES ({placeholders})",
        [row[k] for k in keys],
    )


# ── SÓL PREMIUM — trio Krąg / Klinga / Szczypta (lore §6) ─────────────────────
KRAG_SOLI = {
    "key": "krag_soli",
    "label": "Krąg soli",
    "item_type": "gear",
    "description": (
        "Woreczek najczystszej soli świata — tej, którą równina wyrzuciła najbliżej "
        "pęknięcia. Rozsypany w krąg wokół obozowiska tworzy próg, którego nieumarli "
        "nie przekraczają chętnie: sól tłumi Rdzeń, który je trzyma na nogach. "
        "U Piętnowanych czystszy niż wszystko, co przywiozą z Siwych Grań."
    ),
    "value_gp": 18,
    "price_gp": 18,
    "weight_kg": 0.4,
    "charges": 1,
    "rarity": 2,
    "effect_json": json.dumps(
        {"effect_category": "ward", "ward_vs": "undead", "scope": "rest", "purity": "premium"}
    ),
    "is_active": 1,
    "approved": 1,
    "review_status": "permanent",
    "min_level": 1,
    "location_tags": "martwe_pustkowia,siwe_granie",
    "created_by": "seed",
    "no_trade": 0,
    "note": "Sól-izolator Rdzenia (§6). Rozsypana w krąg zmniejsza szansę zasadzki nieumarłych na odpoczynku. Wersja premium — czystsza od solnych towarów z Grań.",
}

SZCZYPTA_SOLI = {
    "key": "szczypta_soli",
    "label": "Szczypta soli",
    "description": (
        "Garść solnego pyłu rzucona w twarz nieumarłemu rwie na chwilę Rdzeń, który "
        "go ożywia — pustka wzdryga się, jakby ją oślepiono. Piętnowani noszą "
        "szczyptę zawsze przy pasie: na pustkowiach to tańsze niż modlitwa i pewniejsze."
    ),
    "effect_type": "misc",
    "effect_target": "enemy",
    "weight_kg": 0.1,
    "charges": 1,
    "base_price": 8,
    "price_gp": 8,
    "rarity": 1,
    "approved": 1,
    "min_level": 1,
    "location_tags": "martwe_pustkowia,siwe_granie",
    "effect_json": json.dumps(
        {"effect_category": "salt_disrupt", "target_type": "undead", "purity": "premium"}
    ),
    "is_active": 1,
    "note": "Rzucona w nieumarłego zakłóca go na turę (§6). Wartości startowe.",
}

SOLONA_KLINGA = {
    "key": "solona_klinga",
    "label": "Solona klinga",
    "damage_die": "d4",
    "weapon_type": "melee",
    "linked_stat": "DEX",
    "allowed_classes": json.dumps(["warrior", "ranger", "scholar"]),
    "two_handed": 0,
    "finesse": 1,
    "targeting": "single",
    "weight_kg": 0.6,
    "description": (
        "Wąskie ostrze przetrawione solą aż do matowej bieli — nie tnie żywych "
        "lepiej niż zwykły sztylet, ale wbite w nieumarłego pali jego Rdzeń jak "
        "kwas. Piętnowani kują je z soli leżakowanej najbliżej pęknięć."
    ),
    "note": "Solą-izolatorem rani nieumarłych mocniej niż zwykła stal (§6).",
    "value_gp": 24,
    "price_gp": 24,
    "rarity": 2,
    "is_active": 1,
    "approved": 1,
    "review_status": "permanent",
    "min_level": 1,
    "location_tags": "martwe_pustkowia",
    "durability_base": 70,
    "effect_json": json.dumps(
        {"effect_category": "salt_edge", "bonus_vs": "undead", "purity": "premium"}
    ),
}

# ── RELIKTY — towar gorączki reliktów (lore §1, §4) ───────────────────────────
KOSCIANY_KOMPAS = {
    "key": "kosciany_kompas",
    "label": "Kościany kompas",
    "item_type": "gear",
    "description": (
        "Igła z kości Pradawnych osadzona w solnej oprawie. Drga sama, gdy zbliżysz "
        "się do pęknięcia Rdzenia — reakcja fizyczna, nie magia. Kto go czyta, ten "
        "rzadziej wpada w zasadzkę nieumarłych i widzi w ruinach więcej niż inni."
    ),
    "value_gp": 30,
    "price_gp": 30,
    "weight_kg": 0.3,
    "charges": 0,
    "rarity": 3,
    "effect_json": json.dumps(
        {"effect_category": "utility", "ambush_reduction": True, "perception_in_ruins": 2}
    ),
    "is_active": 1,
    "approved": 1,
    "review_status": "permanent",
    "min_level": 1,
    "location_tags": "martwe_pustkowia",
    "created_by": "seed",
    "no_trade": 0,
    "note": "Kanoniczny smaczek §6. Igła z kości Pradawnych drga przy pęknięciach: -szansa zasadzki, +percepcja w ruinach.",
}

RELIKT_PRADAWNYCH = {
    "key": "relikt_pradawnych",
    "label": "Relikt Pradawnych",
    "item_type": "treasure",
    "description": (
        "Przedmiot wyniesiony spod piasku martwych miast — kawał obcego kruszcu, "
        "wygładzony czas i sól, wciąż ciepły, choć nic go nie grzeje. Nikt nie wie, "
        "do czego służył. Brat Tomasz przez swoich agentów płaci za takie znaleziska, "
        "więc na skraj pustkowi ściągnęła gorączka reliktów."
    ),
    "value_gp": 40,
    "price_gp": 40,
    "weight_kg": 0.5,
    "charges": 0,
    "rarity": 3,
    "effect_json": json.dumps({"effect_category": "trade_good", "buyer": "relic_fence"}),
    "is_active": 1,
    "approved": 1,
    "review_status": "permanent",
    "min_level": 1,
    "location_tags": "martwe_pustkowia",
    "created_by": "seed",
    "no_trade": 0,
    "note": "Towar handlowy gorączki reliktów (§1). Fabian (skup) płaci za znaleziska z ruin — sprzedawany przez sell_item do NPC.",
}

# ── SPRZĘT KOPACZA — kramy Grety w Obozie Gorączki (lore §4) ──────────────────
KILOF_KOPACZA = {
    "key": "kilof_kopacza",
    "label": "Kilof kopacza",
    "item_type": "gear",
    "description": (
        "Ciężki kilof z hartowanym grotem — chleb powszedni poszukiwacza reliktów. "
        "Rozbija spieczoną sól i skorupę martwej ziemi, pod którą śpią martwe miasta. "
        "W Obozie Gorączki kupisz go u Grety razem z bukłakiem na drogę."
    ),
    "value_gp": 6,
    "price_gp": 6,
    "weight_kg": 3.0,
    "charges": 0,
    "rarity": 1,
    "effect_json": json.dumps({"effect_category": "tool", "use": "dig"}),
    "is_active": 1,
    "approved": 1,
    "review_status": "permanent",
    "min_level": 1,
    "location_tags": "martwe_pustkowia",
    "created_by": "seed",
    "no_trade": 0,
    "note": "Sprzęt kopacza — narzędzie do rozkopywania ruin. Sprzedawany przez Gretę.",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    ic = _cols(db, "game_config_items")
    cc = _cols(db, "game_config_consumables")
    wc = _cols(db, "game_config_weapons")

    items = [KRAG_SOLI, KOSCIANY_KOMPAS, RELIKT_PRADAWNYCH, KILOF_KOPACZA]
    for row in items:
        _upsert(db, "game_config_items", row, ic)
    _upsert(db, "game_config_consumables", SZCZYPTA_SOLI, cc)
    _upsert(db, "game_config_weapons", SOLONA_KLINGA, wc)
    db.commit()

    # U11c dual-write: legacy game_config_* → unified game_items (sklepy/loot/sell czytają
    # game_items). Bez tego handel MP-5 wywala się na „brak w katalogu".
    sys.path.insert(0, "/app")
    try:
        from app.services import game_items_service as gis
        for row in items:
            gis.sync_from_legacy(db, "game_config_items", row["key"])
        gis.sync_from_legacy(db, "game_config_consumables", SZCZYPTA_SOLI["key"])
        gis.sync_from_legacy(db, "game_config_weapons", SOLONA_KLINGA["key"])
        db.commit()
    except Exception as e:  # noqa: BLE001
        print(f"WARN: game_items sync failed: {e}")

    # ── kontrola: wszystko w game_items z ceną > 0 ────────────────────────────
    ok = True
    want = {
        "krag_soli": "item", "szczypta_soli": "consumable", "solona_klinga": "weapon",
        "kosciany_kompas": "item", "relikt_pradawnych": "item", "kilof_kopacza": "item",
    }
    for key, kind in want.items():
        r = db.execute(
            "SELECT kind, COALESCE(price_gp,0) p FROM game_items WHERE key=? AND is_active=1", (key,)
        ).fetchone()
        if not r:
            print(f"  ✗ {key}: brak w game_items"); ok = False; continue
        note = "" if float(r["p"]) > 0 else "  ⚠ cena 0"
        kind_ok = (kind == "item" and r["kind"] in ("gear", "treasure", "item")) or r["kind"] == kind
        if not kind_ok:
            note += f"  ⚠ kind={r['kind']} (oczek. {kind})"; ok = False
        print(f"  {key:22s} kind={r['kind']:10s} price={r['p']}{note}")

    db.close()
    print("\n" + ("KONTROLA OK" if ok else "PROBLEMY — patrz ⚠ wyżej"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
