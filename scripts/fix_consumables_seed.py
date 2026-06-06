#!/usr/bin/env python3
"""Move the 30 consumables I incorrectly inserted into game_config_consumables
into the correct table: game_config_items with item_type='consumable'.

Run inside backend container:
    docker exec ai-gm-dev-backend-1 python /tmp/fix_consumables_seed.py
"""
import json
import sqlite3
import sys

DB_PATH = "/data/ai_gm.db"

# Only the 4 effect_type values supported by CONSUMABLE_IMMEDIATE_EFFECTS:
# {heal_hp, restore_mana, remove_condition, add_condition}.
# For others we keep effect_json = NULL — UI still lists them.
SUPPORTED_EFFECT = {"heal_hp", "restore_mana", "remove_condition", "add_condition"}


def _value(dice: str | None, bonus: int) -> object:
    dice = (dice or "").strip()
    if dice and bonus:
        return f"{dice}+{bonus}"
    if dice:
        return dice
    return int(bonus)


def build_effect_json(effect_type: str, dice: str | None, bonus: int, target: str) -> str | None:
    et = (effect_type or "").strip().lower()
    if et not in SUPPORTED_EFFECT:
        return None
    if et in ("heal_hp", "restore_mana"):
        effect = {"type": et, "value": _value(dice, bonus)}
    else:
        # condition-based — target field holds condition key in legacy schema
        condition_key = (target or "").strip().lower() or "poisoned"
        effect = {"type": et if et != "add_condition" else "apply_condition",
                  "condition_key": condition_key}
    return json.dumps({
        "schema_version": 1,
        "effect_category": "consumable_immediate",
        "effects": [effect],
    }, ensure_ascii=False)


CONSUMABLES: list[dict] = [
    # ── healing ──
    {"key": "potion_healing_small", "label": "Mała mikstura leczenia",
     "effect_type": "heal_hp", "effect_dice": "2d4", "effect_bonus": 2,
     "base_price": 25, "weight_kg": 0.2,
     "description": "Mała szklana ampułka czerwonej cieczy o cierpkim posmaku ziół. Wypita zalewa rany ciepłem."},
    {"key": "potion_healing_medium", "label": "Mikstura leczenia",
     "effect_type": "heal_hp", "effect_dice": "4d4", "effect_bonus": 4,
     "base_price": 75, "weight_kg": 0.3,
     "description": "Pełna fiolka rubinowej cieczy. Smakuje jak żelazo i kwiat lipy — goi nawet poważne rany."},
    {"key": "potion_healing_large", "label": "Wielka mikstura leczenia",
     "effect_type": "heal_hp", "effect_dice": "8d4", "effect_bonus": 8,
     "base_price": 250, "weight_kg": 0.5,
     "description": "Duża flakon z mikstury alchemika. Przywróci do walki nawet człowieka konającego w kałuży krwi."},
    {"key": "healing_herb", "label": "Lecznicze zioła",
     "effect_type": "heal_hp", "effect_dice": "1d4", "effect_bonus": 1,
     "base_price": 8, "weight_kg": 0.1,
     "description": "Pęczek suszonych ziół owinięty w len. Przyłożone do rany przyspieszają gojenie."},
    {"key": "bandage", "label": "Bandaż",
     "effect_type": "heal_hp", "effect_dice": "1d6", "effect_bonus": 0,
     "base_price": 2, "weight_kg": 0.2,
     "description": "Czysty zwój lnianego płótna. Pozwala opatrzyć ranę towarzysza w polu walki."},
    # ── mana ──
    {"key": "potion_mana_small", "label": "Mała mikstura many",
     "effect_type": "restore_mana", "effect_dice": "1d6", "effect_bonus": 2,
     "base_price": 30, "weight_kg": 0.2,
     "description": "Lazurowa ciecz w okrągłej ampułce. Pachnie miętą i wapnem — przywraca część zużytej mocy magicznej."},
    {"key": "potion_mana_medium", "label": "Mikstura many",
     "effect_type": "restore_mana", "effect_dice": "2d6", "effect_bonus": 4,
     "base_price": 90, "weight_kg": 0.3,
     "description": "Granatowy eliksir o przyjemnym ziołowym posmaku. Odnawia więcej many niż mała mikstura."},
    {"key": "potion_mana_large", "label": "Wielka mikstura many",
     "effect_type": "restore_mana", "effect_dice": "4d6", "effect_bonus": 8,
     "base_price": 300, "weight_kg": 0.5,
     "description": "Wielki flakon ciemnogranatowej mikstury z migocącymi iskierkami. Niemal w pełni regeneruje arkany kastującego."},
    {"key": "focus_crystal", "label": "Kryształ skupienia",
     "effect_type": "restore_mana", "effect_dice": "1d4", "effect_bonus": 1,
     "base_price": 15, "weight_kg": 0.1, "charges": 3,
     "description": "Mały szmaragdowy kryształ. Po skupieniu woli można z niego wydobyć trochę many — wystarczy na trzy razy."},
    # ── buffs (narrative — effect_json stays NULL) ──
    {"key": "potion_strength", "label": "Mikstura siły",
     "effect_type": None, "base_price": 60, "weight_kg": 0.2,
     "description": "Mętna brunatna mikstura o zapachu byczej krwi. Wypita daje na minutę siłę osiłka — i kaca na cały dzień."},
    {"key": "potion_haste", "label": "Mikstura pośpiechu",
     "effect_type": None, "base_price": 80, "weight_kg": 0.2,
     "description": "Bladozielona ciecz pulsująca delikatnym światłem. Wyostrza refleks i przyspiesza krok."},
    {"key": "potion_stealth", "label": "Mikstura skradania",
     "effect_type": None, "base_price": 70, "weight_kg": 0.2,
     "description": "Szara ciecz bez zapachu. Wypita tłumi kroki i sprawia, że cienie zdają się garnąć do bohatera."},
    {"key": "potion_resistance", "label": "Mikstura odporności",
     "effect_type": None, "base_price": 100, "weight_kg": 0.2,
     "description": "Mętna biaława mikstura. Po wypiciu skóra twardnieje, a ciosy ślizgają się po niej jakby były tępe."},
    {"key": "potion_giant_strength", "label": "Mikstura siły olbrzyma",
     "effect_type": None, "base_price": 250, "weight_kg": 0.3,
     "description": "Gęsta brązowa mikstura w kamiennym dzbanuszku. Daje krótko siłę pozwalającą podnieść wóz albo wyrwać drzwi z zawiasów."},
    # ── scrolls (narrative) ──
    {"key": "scroll_magic_bolt", "label": "Zwój: Magiczna Strzała",
     "effect_type": None, "base_price": 40, "weight_kg": 0.1,
     "description": "Zwitek pergaminu zapisany świetlistym inkaustem. Czytanie wyzwala pojedynczy pocisk mocy w wybrany cel (1d10 obrażeń)."},
    {"key": "scroll_mend", "label": "Zwój: Zaszycie Ran",
     "effect_type": None, "base_price": 35, "weight_kg": 0.1,
     "description": "Pergamin zapisany srebrnym pismem. Rozwinięcie i wypowiedzenie formuły zalecza ranę towarzysza (2d4+2 HP)."},
    {"key": "scroll_shield", "label": "Zwój: Arkana Tarcza",
     "effect_type": None, "base_price": 50, "weight_kg": 0.1,
     "description": "Zwój oprawiony w cienki bambus. Wypowiedziane słowa otaczają kastującego półprzeźroczystą tarczą mocy (+3 AC)."},
    {"key": "scroll_light", "label": "Zwój: Światło",
     "effect_type": None, "base_price": 15, "weight_kg": 0.1,
     "description": "Krótka formuła wypisana na pergaminie. Sprawia, że trzymany przedmiot zaczyna świecić jak pochodnia."},
    {"key": "scroll_fireball", "label": "Zwój: Kula Ognia",
     "effect_type": None, "base_price": 350, "weight_kg": 0.2,
     "description": "Gruby zwój zapisany czerwonym pigmentem. Wypowiedzenie formuły wyzwala kulę ognia (8d6 obrażeń w obszarze)."},
    # ── food/drink ──
    {"key": "bread_loaf", "label": "Bochenek chleba",
     "effect_type": None, "base_price": 1, "weight_kg": 0.6,
     "description": "Świeży bochenek żytniego chleba. Zaspokoi głód na cały dzień marszu."},
    {"key": "dried_meat", "label": "Suszone mięso",
     "effect_type": None, "base_price": 2, "weight_kg": 0.3,
     "description": "Solone, suszone mięso wieprzowe albo z dziczyzny. Zachowuje świeżość tygodniami."},
    {"key": "cheese_wheel", "label": "Krąg sera",
     "effect_type": None, "base_price": 3, "weight_kg": 1.5,
     "description": "Mały krąg owczego sera w wosku. Sycący i odporny na zepsucie."},
    {"key": "apple", "label": "Jabłko",
     "effect_type": None, "base_price": 1, "weight_kg": 0.2,
     "description": "Soczyste czerwone jabłko. Niewielki posiłek, ale orzeźwia po długim marszu."},
    {"key": "hardtack", "label": "Suchar",
     "effect_type": None, "base_price": 1, "weight_kg": 0.2,
     "description": "Twardy, prawie niezniszczalny suchar. Można nim wybić ząb, ale wytrzyma rok w plecaku."},
    {"key": "wineskin", "label": "Bukłak wina",
     "effect_type": None, "base_price": 5, "weight_kg": 1.5, "charges": 4,
     "description": "Skórzany bukłak wypełniony cierpkim czerwonym winem. Cztery porządne łyki — odwagi przed walką lub nocy zapomnienia."},
    # ── throwables (narrative) ──
    {"key": "vial_of_acid", "label": "Fiolka kwasu",
     "effect_type": None, "base_price": 25, "weight_kg": 0.2,
     "description": "Szklana fiolka z mętnym, parującym kwasem. Rzucona na cel parzy ciało i metal (2d6 obrażeń)."},
    {"key": "holy_water", "label": "Woda święcona",
     "effect_type": None, "base_price": 25, "weight_kg": 0.2,
     "description": "Mała ampułka z modlitwą wyrytą na korku. Wylana albo rozbita na nieumarłym spala go jak ogień (2d6 obrażeń przeciw nieumarłym)."},
    {"key": "alchemist_fire", "label": "Ogień alchemika",
     "effect_type": None, "base_price": 50, "weight_kg": 0.5,
     "description": "Gęsta oleista substancja w szklanym pojemniku. Rzucona na cel zapala go i pali przez kilka chwil (1d4 obrażeń + płonięcie)."},
    {"key": "smoke_bomb", "label": "Bomba dymna",
     "effect_type": None, "base_price": 30, "weight_kg": 0.3,
     "description": "Mała gliniana kulka z sproszkowanymi ziołami. Rzucona o podłogę wybucha kłębem szarego dymu — idealna na ucieczkę."},
    {"key": "antitoxin_vial", "label": "Antydot",
     "effect_type": "remove_condition", "effect_target": "poisoned",
     "base_price": 50, "weight_kg": 0.1,
     "description": "Mętna ciecz o gorzkim posmaku w małej fiolce. Neutralizuje większość znanych trucizn — jeśli wypić w porę."},
]


def main() -> int:
    print(f"Connecting to {DB_PATH}…")
    conn = sqlite3.connect(DB_PATH)
    try:
        # 1. Delete the 30 rows from the deprecated table (cleanup my earlier mistake)
        wrong_keys = [c["key"] for c in CONSUMABLES]
        placeholders = ",".join("?" * len(wrong_keys))
        cur = conn.execute(
            f"DELETE FROM game_config_consumables WHERE key IN ({placeholders})",
            wrong_keys,
        )
        print(f"Cleaned {cur.rowcount} rows from deprecated game_config_consumables")

        # 2. Insert each into game_config_items with item_type='consumable'
        n = 0
        for c in CONSUMABLES:
            effect_json = None
            if c.get("effect_type"):
                effect_json = build_effect_json(
                    c["effect_type"],
                    c.get("effect_dice"),
                    int(c.get("effect_bonus") or 0),
                    c.get("effect_target") or "self",
                )
            conn.execute(
                """
                INSERT OR REPLACE INTO game_config_items
                    (key, label, item_type, description, value_gp, weight_kg,
                     ac_bonus, armor_coverage, allowed_classes, charges, effect_json,
                     approved, is_active, ai_generated)
                VALUES (?, ?, 'consumable', ?, ?, ?, 0, 'torso', '[]', ?, ?, 1, 1, 0)
                """,
                (
                    c["key"], c["label"], c.get("description", ""),
                    int(c.get("base_price") or 0),
                    float(c.get("weight_kg") or 0),
                    int(c.get("charges") or 1),
                    effect_json,
                ),
            )
            n += 1
        conn.commit()
        print(f"✓ Inserted/updated {n} consumables in game_config_items (item_type='consumable')")

        # Sanity
        cnt = conn.execute(
            "SELECT COUNT(*) FROM game_config_items WHERE item_type = 'consumable'"
        ).fetchone()[0]
        print(f"  game_config_items WHERE item_type='consumable': {cnt} rows total")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
