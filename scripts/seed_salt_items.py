#!/usr/bin/env python3
"""SG-7 (#1481) — sól jako materiał przeciw-Rdzeniowy: kondycje, przedmioty, klasy istot.

Źródło prawdy: docs/world/regions/siwe_granie.md §6 (ZATWIERDZONE). Sól nie jest
magiczna — jest *obojętna na Rdzeń* (izolator). Stąd Linia Soli i woreczek soli
przy pasie górnika, a w mechanice trzy przedmioty:

  * Krąg soli      — istoty Rdzenia nie wchodzą do ZWARCIA przez 3 rundy (1 użycie),
  * Solona klinga  — +1k4 obrażeń istotom Rdzenia przez jedną walkę,
  * Szczypta soli  — następny miscast łagodniejszy o 1 stopień, ale −1 do obrażeń
                     czarów do końca walki (sól tłumi też własny kanał maga).

CO CZYTA SILNIK:
  * `game_config_conditions` → kondycje nakładane zwykłą ścieżką użycia przedmiotu
    (`loot_service.use_inventory_item` → effect_json.apply_condition/target=self),
  * `salt_service` → czyta te kondycje w walce (doskok wroga, obrażenia, miscast),
  * `game_config_enemies.creature_type` → kto jest „istotą Rdzenia" (undead/demon/rdzen),
  * `npcs.shop_inventory_json` (Helga Solnobroda) → gdzie się to kupuje.

WARTOŚCI STARTOWE (Numbers Policy): 3 rundy kręgu, kość 1k4 klingi, −1 do obrażeń
czarów, ceny — wszystko do strojenia w Sandboksie.

Idempotentny: kondycje/przedmioty INSERT OR IGNORE po kluczu, klasa istoty ustawiana
tylko tam, gdzie jest pusta, asortyment Helgi dokładany bez duplikatów.

    docker cp scripts/seed_salt_items.py ai-gm-dev-backend-1:/app/
    docker exec ai-gm-dev-backend-1 python /app/seed_salt_items.py
    docker exec ai-gm-dev-backend-1 python /app/seed_salt_items.py --db /tmp/verify.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3

SALT_MERCHANT_KEY = "helga_solnobroda"

# ── 1. KONDYCJE ───────────────────────────────────────────────────────────────
# `clear_on: combat_end` = kondycja ważna „na jedną walkę" (zdejmowana w end_combat).
# `on_apply: push_core_beings` = rytuał wypycha istoty Rdzenia ze zwarcia już przy użyciu.
CONDITIONS: list[dict] = [
    dict(
        key="salt_circle",
        label="Krąg soli",
        description=(
            "Wokół ciebie zamknięty krąg grubej soli kopalnianej. Istoty Rdzenia — "
            "nieumarli, demony, twory żyły — nie przekroczą go przez 3 rundy. Żywym "
            "wrogom sól nie robi nic."
        ),
        effect_json={
            "schema_version": 1,
            "effect_category": "character_condition",
            "clear_on": "combat_end",
            "on_apply": "push_core_beings",
            "effects": [
                {
                    "type": "salt_ward",
                    "blocks": "zone_change_to_engaged",
                    "target_creature_types": ["undead", "demon", "rdzen"],
                    "expires": "duration_rounds:3",
                }
            ],
        },
        auto_remove="duration_rounds:3",
    ),
    dict(
        key="salted_blade",
        label="Solona klinga",
        description=(
            "Ostrze natarte solą. Cięcie w istotę Rdzenia dokłada 1k4 obrażeń — "
            "sól rozrywa to, co żyłę trzyma w kupie. Trzyma się broni przez jedną walkę."
        ),
        effect_json={
            "schema_version": 1,
            "effect_category": "character_condition",
            "clear_on": "combat_end",
            "effects": [
                {
                    "type": "salt_edge",
                    "bonus_dice": "1d4",
                    "target_creature_types": ["undead", "demon", "rdzen"],
                }
            ],
        },
        auto_remove="combat_end",
    ),
    dict(
        key="salt_pinch",
        label="Szczypta soli",
        description=(
            "Sól na dłoniach i języku. Najbliższe odbicie czaru będzie o stopień "
            "łagodniejsze — ale sól tłumi też twój własny kanał: −1 do obrażeń "
            "czarów do końca walki."
        ),
        effect_json={
            "schema_version": 1,
            "effect_category": "character_condition",
            "clear_on": "combat_end",
            "effects": [
                {"type": "salt_miscast_softening", "steps": 1, "uses": 1},
                {"type": "salt_spell_damping", "spell_damage_penalty": 1},
            ],
        },
        auto_remove="combat_end",
    ),
]

# ── 2. PRZEDMIOTY (consumables) ───────────────────────────────────────────────
# Ceny startowe: sól jest drugim towarem eksportowym Grań, więc tanio u źródła.
CONSUMABLES: list[dict] = [
    dict(
        key="salt_circle_pouch",
        label="Krąg soli",
        description=(
            "Woreczek grubej soli z sztolni Grań, na tyle duży, by wysypać krąg wokół "
            "siebie albo wokół obozowego ogniska. Górnicy noszą taki przy pasie od "
            "czasu Głębokiego Bicia — sól jest obojętna na Rdzeń, więc to, co stuka, "
            "przez nią nie przechodzi. Jedno użycie."
        ),
        note="Istoty Rdzenia nie wchodzą do zwarcia przez 3 rundy; przy obozie — bezpieczny odpoczynek w strefie skażonej.",
        price=35,
        weight=0.5,
        rarity="uncommon",
        condition_key="salt_circle",
    ),
    dict(
        key="salted_blade_kit",
        label="Solona klinga",
        description=(
            "Płócienny zawiniątko z solą i tłuszczem — naciera się nim ostrze przed "
            "zejściem pod Linię Soli. Sól nie tnie żywych lepiej, ale w tym, co "
            "trzyma się Rdzenia, robi rany, które się nie zamykają. Starcza na jedną walkę."
        ),
        note="+1k4 obrażeń przeciw istotom Rdzenia (nieumarli, demony, twory żyły) przez jedną walkę.",
        price=45,
        weight=0.3,
        rarity="uncommon",
        condition_key="salted_blade",
    ),
    dict(
        key="salt_pinch_vial",
        label="Szczypta soli",
        description=(
            "Maleńka fiolka soli warzonej, jakiej używają starsi rodów przy próbach "
            "żyły. Mag bierze szczyptę na dłoń przed walką: odbicie czaru będzie "
            "łagodniejsze, ale i własny kanał przygaśnie."
        ),
        note="Najbliższy miscast o 1 stopień łagodniejszy; −1 do obrażeń czarów do końca walki.",
        price=30,
        weight=0.1,
        rarity="uncommon",
        condition_key="salt_pinch",
    ),
]

# ── 3. KLASY ISTOT (creature_type) ────────────────────────────────────────────
# Słowa-klucze szukane w kluczu, nazwie, opisie i notce wroga. Klasyfikacja minimalna:
# rozstrzyga wyłącznie „czy sól działa", nie jest taksonomią bestiariusza.
CREATURE_TYPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("demon", ("demon", "diab", "czart", "imp", "arcydemon", "czeluś")),
    ("rdzen", ("rdzeń", "rdzen", "żyła rdzenia", "strażnik rdzenia", "głębokie bicie")),
    ("undead", (
        "nieumar", "zombie", "szkielet", "kościej", "kościany", "upi", "upiór", "widm",
        "wraith", "zjaw", "ghul", "lisz", "lich", "trup", "trupiar", "mumia", "nekro",
        "grobow", "krypt", "zamarznięty pielgrzym", "beznamienny",
    )),
]

# Ręczne rozstrzygnięcia — mają pierwszeństwo przed słowami-kluczami.
CREATURE_TYPE_EXPLICIT: dict[str, str] = {
    "straznik_rdzenia": "rdzen",
    "zamarzniety_pielgrzym": "undead",
    "widmo_lodowe": "undead",
    "golem_kamienny": "",          # konstrukt z kamienia, nie z Rdzenia — sól nie działa
    "salamandra_siarkowa": "",     # żywe zwierzę mimo ognistego opisu
    "ognik_siarkowy": "",          # zjawisko naturalne (wyziew), nie istota Rdzenia
    "kultysta_cienia_pod_popiolem": "",   # żywy człowiek, choć służy nieumarłym
    "dark_priest": "",             # żywy kapłan — nekromanta, nie nieumarły
    "stepowy_grasant": "",         # żywy bandyta (heurystyka złapała „trup" z opisu)
    "szczury_grobowe": "",         # żywe robactwo z grobowców, nie nieumarli
    "popielny_wyznawca": "",       # żywy kultysta, nie demon
    "spaczony_prorok": "",         # żywy prorok kultu, nie demon
    "marek_voss_final": "",        # żywy człowiek z wiernymi, boss fabularny
    "moc_rozbitej_gwiazdy": "",    # zjawisko/wybuch, nie istota
}


def seed_conditions(conn: sqlite3.Connection) -> int:
    n = 0
    for c in CONDITIONS:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO game_config_conditions
                (key, label, description, effect_json, is_active, stackable, auto_remove)
            VALUES (?, ?, ?, ?, 1, 0, ?)
            """,
            (c["key"], c["label"], c["description"],
             json.dumps(c["effect_json"], ensure_ascii=False), c["auto_remove"]),
        )
        n += cur.rowcount or 0
    return n


def seed_consumables(conn: sqlite3.Connection) -> int:
    n = 0
    for item in CONSUMABLES:
        effect_json = {
            "effect_category": "consumable_immediate",
            "effects": [
                {"type": "apply_condition", "condition_key": item["condition_key"], "target": "self"}
            ],
        }
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO game_config_consumables
                (key, label, description, effect_type, effect_target, effect_json,
                 weight_kg, charges, base_price, price_gp, note, rarity,
                 is_active, approved, ai_generated, min_level, location_tags)
            VALUES (?, ?, ?, 'add_condition', 'self', ?, ?, 1, ?, ?, ?, ?, 1, 1, 0, 1, 'siwe_granie')
            """,
            (item["key"], item["label"], item["description"],
             json.dumps(effect_json, ensure_ascii=False),
             item["weight"], item["price"], item["price"], item["note"], item["rarity"]),
        )
        n += cur.rowcount or 0
    return n


def _creature_type_for(row: sqlite3.Row) -> str:
    key = str(row["key"] or "").strip().lower()
    if key in CREATURE_TYPE_EXPLICIT:
        return CREATURE_TYPE_EXPLICIT[key]
    blob = " ".join([
        key,
        str(row["label"] or ""),
        str(row["description"] or "") if "description" in row.keys() else "",
        str(row["note"] or "") if "note" in row.keys() else "",
    ]).lower()
    for ctype, words in CREATURE_TYPE_KEYWORDS:
        if any(w in blob for w in words):
            return ctype
    return ""


def ensure_creature_type_column(conn: sqlite3.Connection) -> None:
    """Kolumna powstaje w migracji (v2-enemies-creature-type); tu tylko zabezpieczenie,
    żeby seed dało się puścić na kopii bazy sprzed restartu backendu."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(game_config_enemies)")]
    if "creature_type" not in cols:
        conn.execute("ALTER TABLE game_config_enemies ADD COLUMN creature_type TEXT DEFAULT NULL")


def backfill_creature_types(conn: sqlite3.Connection) -> dict[str, int]:
    ensure_creature_type_column(conn)
    stats: dict[str, int] = {}
    rows = conn.execute("SELECT * FROM game_config_enemies").fetchall()
    for row in rows:
        current = ""
        if "creature_type" in row.keys():
            current = str(row["creature_type"] or "").strip()
        if current:
            continue
        ctype = _creature_type_for(row)
        if not ctype:
            continue
        conn.execute(
            "UPDATE game_config_enemies SET creature_type = ? WHERE key = ?",
            (ctype, row["key"]),
        )
        stats[ctype] = stats.get(ctype, 0) + 1
    return stats


def seed_salt_merchant(conn: sqlite3.Connection) -> int:
    """Dołóż sól do asortymentu Helgi Solnobrodej (kupcowa solna, Targ Kamiennego Grodu)."""
    row = conn.execute(
        "SELECT key, shop_inventory_json FROM npcs WHERE key = ?", (SALT_MERCHANT_KEY,)
    ).fetchone()
    if not row:
        print(f"  UWAGA: brak NPC {SALT_MERCHANT_KEY} — pomijam asortyment (TODO po SG-5)")
        return 0
    try:
        inv = json.loads(row["shop_inventory_json"] or "[]")
    except (ValueError, TypeError):
        inv = []
    if not isinstance(inv, list):
        inv = []
    have = {str(e.get("key")) for e in inv if isinstance(e, dict)}
    added = 0
    for item in CONSUMABLES:
        if item["key"] in have:
            continue
        inv.append({"type": "consumable", "key": item["key"]})
        added += 1
    if added:
        conn.execute(
            "UPDATE npcs SET shop_inventory_json = ?, updated_at = datetime('now') WHERE key = ?",
            (json.dumps(inv, ensure_ascii=False), SALT_MERCHANT_KEY),
        )
    return added


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    cond_n = seed_conditions(conn)
    cons_n = seed_consumables(conn)
    types = backfill_creature_types(conn)
    shop_n = seed_salt_merchant(conn)
    conn.commit()

    print(f"  kondycje nowe:       {cond_n} (z {len(CONDITIONS)})")
    print(f"  przedmioty nowe:     {cons_n} (z {len(CONSUMABLES)})")
    print(f"  asortyment Helgi:    +{shop_n}")
    print(f"  klasy istot nadane:  {types or 'brak (już nadane)'}")

    total = conn.execute(
        "SELECT creature_type, COUNT(*) n FROM game_config_enemies "
        "WHERE COALESCE(creature_type,'') != '' GROUP BY creature_type ORDER BY n DESC"
    ).fetchall()
    print("  istoty Rdzenia w bestiariuszu:")
    for r in total:
        print(f"    {r['creature_type']:10s} {r['n']}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
