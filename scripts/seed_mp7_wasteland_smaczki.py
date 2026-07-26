#!/usr/bin/env python3
"""MP-7 (#1494) — smaczki Martwych Pustkowi: sól premium + kompas + szlak handlowy.

Źródło prawdy: docs/world/regions/martwe_pustkowia.md §6 (ZATWIERDZONE).

DECYZJE (odnotowane):
  * Sól premium Piętnowanych = te same TRZY efekty co sól z Grań (SG-7 #1481:
    kondycje ``salt_circle`` / ``salted_blade`` / ``salt_pinch``, czytane przez
    ``salt_service`` w walce), ale **czystsza = TAŃSZA** (§6 „tańsze albo tier
    wyżej" — wybieramy tańsze; MP-5 wyceniło już 18/24/8 < Grań 35/45/30).
  * Trzy przedmioty ujednolicone jako **consumables** (ścieżka use_inventory_item →
    apply_condition), żeby wpięły się w istniejący silnik soli bez nowego kodu
    walki. Stub-broń ``solona_klinga`` i stub-item ``krag_soli`` z MP-5 zostają
    zastąpione wariantem consumable (kit do natarcia ostrza / woreczek).
  * Szlak handlowy: sól z Pustkowi trafia też do Helgi Solnobrodej w Graniach,
    ale **drożej** (narzut per-wpis ``price`` w shop_inventory_json — nowe, opcjonalne
    pole obsługiwane przez shop_service).
  * ``kosciany_kompas`` (item) i ``waterskin`` (bukłak) zostają jak w MP-5; ich
    mechanikę czyta ``wasteland_service`` (kompas: zasadzka/percepcja; bukłak: rest).

Idempotentny: kasuje i wstawia od nowa nasze trzy consumable, zdejmuje duplikaty
stub-broni/itemu, a asortyment sklepów przelicza (usuwa nasze klucze i dokłada
kanoniczne wpisy).

    docker cp scripts/seed_mp7_wasteland_smaczki.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_mp7_wasteland_smaczki.py
    docker exec ai-gm-dev-backend-1 python /app/seed_mp7_wasteland_smaczki.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3

NADIRA_KEY = "nadira_zniwiarka"
HELGA_KEY = "helga_solnobroda"

# ── premium sól Piętnowanych (consumables → kondycje SG-7) ────────────────────
# (klucz, label, opis, note, cena, klucz kondycji)
PREMIUM_SALT: list[dict] = [
    dict(
        key="krag_soli",
        label="Krąg soli",
        description=(
            "Woreczek najczystszej soli świata — tej, którą równina wyrzuciła najbliżej "
            "pęknięcia. Rozsypana w krąg trzyma istoty Rdzenia (nieumarłych, demony, twory "
            "żyły) poza zwarciem przez 3 rundy. U Piętnowanych czystsza i tańsza niż towar "
            "z Siwych Grań."
        ),
        note="Istoty Rdzenia nie wchodzą do zwarcia przez 3 rundy. Wariant premium (§6).",
        price=18,
        condition_key="salt_circle",
    ),
    dict(
        key="solona_klinga",
        label="Solona klinga",
        description=(
            "Zawiniątko soli i tłuszczu do natarcia ostrza przed wyprawą w ruiny. Sól "
            "rani istoty Rdzenia mocniej niż stal: +1k4 obrażeń przez jedną walkę. "
            "Piętnowani warzą je z soli-bliźni — czystsze i tańsze niż kity z Grań."
        ),
        note="+1k4 obrażeń przeciw istotom Rdzenia przez jedną walkę. Wariant premium (§6).",
        price=24,
        condition_key="salted_blade",
    ),
    dict(
        key="szczypta_soli",
        label="Szczypta soli",
        description=(
            "Fiolka soli warzonej z równiny. Wzięta na dłoń przed walką łagodzi najbliższy "
            "miscast o stopień, choć przygasza własny kanał maga (−1 do obrażeń czarów do "
            "końca walki). U Piętnowanych tańsza niż gdziekolwiek na świecie."
        ),
        note="Najbliższy miscast o 1 stopień łagodniejszy; −1 do obrażeń czarów. Premium (§6).",
        price=8,
        condition_key="salt_pinch",
    ),
]

#: Narzut Helgi (Granie) — sól z Pustkowi drożej niż u źródła (szlak handlowy §6).
HELGA_SALT_MARKUP: dict[str, int] = {
    "krag_soli": 36,
    "solona_klinga": 48,
    "szczypta_soli": 16,
}


def seed_premium_consumables(conn: sqlite3.Connection) -> int:
    # Zdejmij stub-broń i stub-item o tych samych kluczach (MP-5), żeby nie dublować.
    conn.execute("DELETE FROM game_config_weapons WHERE key = 'solona_klinga'")
    conn.execute("DELETE FROM game_config_items WHERE key = 'krag_soli'")
    conn.execute(
        "DELETE FROM game_config_consumables WHERE key IN ('krag_soli','solona_klinga','szczypta_soli')"
    )
    n = 0
    for it in PREMIUM_SALT:
        effect_json = {
            "effect_category": "consumable_immediate",
            "effects": [
                {"type": "apply_condition", "condition_key": it["condition_key"], "target": "self"}
            ],
        }
        conn.execute(
            """
            INSERT INTO game_config_consumables
                (key, label, description, effect_type, effect_dice, effect_bonus,
                 effect_target, weight_kg, charges, base_price, price_gp, note, rarity,
                 is_active, approved, ai_generated, min_level, location_tags, hidden,
                 effect_json, created_at, updated_at)
            VALUES (?, ?, ?, 'add_condition', NULL, 0, 'self', 0.2, 1, ?, ?, ?, 2,
                    1, 1, 0, 1, 'martwe_pustkowia', 0, ?, datetime('now'), datetime('now'))
            """,
            (it["key"], it["label"], it["description"],
             it["price"], it["price"], it["note"],
             json.dumps(effect_json, ensure_ascii=False)),
        )
        n += 1
    return n


def _load_inv(conn: sqlite3.Connection, npc_key: str) -> list[dict] | None:
    row = conn.execute(
        "SELECT shop_inventory_json FROM npcs WHERE key = ?", (npc_key,)
    ).fetchone()
    if not row:
        print(f"  UWAGA: brak NPC {npc_key} — pomijam asortyment")
        return None
    try:
        inv = json.loads(row["shop_inventory_json"] or "[]")
    except (ValueError, TypeError):
        inv = []
    return inv if isinstance(inv, list) else []


def _save_inv(conn: sqlite3.Connection, npc_key: str, inv: list[dict]) -> None:
    conn.execute(
        "UPDATE npcs SET shop_inventory_json = ?, updated_at = datetime('now') WHERE key = ?",
        (json.dumps(inv, ensure_ascii=False), npc_key),
    )


def seed_nadira(conn: sqlite3.Connection) -> int:
    """Nadira (Solne Żniwa): sprzedaje sól premium jako consumable + bukłak."""
    inv = _load_inv(conn, NADIRA_KEY)
    if inv is None:
        return 0
    salt_keys = {it["key"] for it in PREMIUM_SALT}
    kept = [e for e in inv if isinstance(e, dict) and e.get("key") not in salt_keys]
    new_salt = [{"type": "consumable", "key": it["key"]} for it in PREMIUM_SALT]
    _save_inv(conn, NADIRA_KEY, new_salt + kept)
    return len(new_salt)


def seed_helga(conn: sqlite3.Connection) -> int:
    """Helga (Granie): dokłada sól z Pustkowi z narzutem (szlak handlowy §6)."""
    inv = _load_inv(conn, HELGA_KEY)
    if inv is None:
        return 0
    salt_keys = set(HELGA_SALT_MARKUP)
    kept = [e for e in inv if isinstance(e, dict) and e.get("key") not in salt_keys]
    imported = [
        {"type": "consumable", "key": k, "price": p} for k, p in HELGA_SALT_MARKUP.items()
    ]
    _save_inv(conn, HELGA_KEY, kept + imported)
    return len(imported)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    cons_n = seed_premium_consumables(conn)
    nadira_n = seed_nadira(conn)
    helga_n = seed_helga(conn)
    conn.commit()

    print(f"  sól premium (consumables): {cons_n}")
    print(f"  asortyment Nadiry:         {nadira_n}")
    print(f"  asortyment Helgi (import): {helga_n}")
    # sanity: kompas i bukłak nadal w katalogu
    for tbl, key in (("game_config_items", "kosciany_kompas"), ("game_config_items", "waterskin")):
        r = conn.execute(f"SELECT 1 FROM {tbl} WHERE key = ?", (key,)).fetchone()
        print(f"  {key:18s} w katalogu: {'TAK' if r else 'BRAK!'}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
