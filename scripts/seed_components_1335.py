#!/usr/bin/env python3
"""BL-B3 (#1335) — crafting components as an item class + loot wiring.

Content-as-code (#1202): rewrites the committed seed JSON in place. Idempotent —
running twice yields byte-identical output.

Three moves:
1. game_config_items: stamp is_component/component_type/created_by on EVERY row
   (the seed loader keys columns off row[0], and is_component is NOT NULL, so the
   fields must exist on all rows). Flag existing materials; append ~14 new Kresy
   components (created_by='seed').
2. Loot wiring: thematic components per beast (wolf→fang/pelt, spider→gland/silk,
   skeleton→bone dust, rat→fang, bear→hide/fat, lizardman→scale). Beasts get their
   own loot table with gold zeroed — a wolf carrying a coin purse is absurd; the
   reward is the carcass.  Tier-table components live in migrate_loot_tiers_1333.py.
3. game_config_enemies: repoint beasts that shared a generic pool to their own
   component table.

Run order in the pipeline: 1333 (tier content) → 1334 (fragment/flavour) → 1335.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds" / "content"
ITEMS_PATH = SEED_DIR / "game_config_items.json"
TABLES_PATH = SEED_DIR / "game_config_loot_tables.json"
ENTRIES_PATH = SEED_DIR / "game_config_loot_entries.json"
ENEMIES_PATH = SEED_DIR / "game_config_enemies.json"

_TS = "2026-07-12 00:00:00"

# ── existing materials to flag as components ──────────────────────────────────
FLAG_EXISTING: dict[str, str] = {
    "wolf_pelt": "pelt",
    "bear_hide": "pelt",
    "bone_dust": "part",
    "healing_herb": "herb",
    "dragon_scale_shard": "part",
    "alchemical_reagent": "essence",
}

# ── new components (Kresy flavour: MIX słowiańsko-germański) ───────────────────
# (key, label, component_type, value_gp, description)
NEW_COMPONENTS: list[tuple[str, str, str, int, str]] = [
    ("kiel_wilczy", "Kieł wilczy", "fang", 6,
     "Zakrzywiony kieł wyrwany z pyska wilka. Rzeźbiarze run i płatnerze cenią go za twardość."),
    ("gruczol_pajeczy", "Gruczoł jadowy pająka", "essence", 12,
     "Nabrzmiały gruczoł ścięty tuż za szczękoczułkami. Sączy się z niego mętny jad."),
    ("jedwab_pajeczy", "Pajęczy jedwab", "part", 10,
     "Zwój lepkiej, srebrzystej nici zdartej z gniazda. Mocniejszy niż lniana przędza."),
    ("kiel_szczurzy", "Kieł szczurzy", "fang", 3,
     "Żółty siekacz olbrzymiego szczura. Drobny, lecz ostry jak igła."),
    ("luska_jaszczura", "Łuska jaszczura", "pelt", 8,
     "Twarda, rogowa łuska zdarta z grzbietu jaszczuroludka. Lśni oliwkowo."),
    ("sadlo_niedzwiedzie", "Sadło niedźwiedzie", "part", 10,
     "Warstwa tłustego sadła. Palona daje długo tlący się olej, w maściach koi rany."),
    ("krew_wilkolaka", "Krew wilkołaka", "essence", 30,
     "Czarna, dymiąca posoka bestii. W zamkniętej fioli wciąż pulsuje ciepłem."),
    ("ruda_zelaza", "Ruda żelaza", "ore", 9,
     "Bryła rudej skały żyłkowanej metalem. Surowiec dla każdej kuźni."),
    ("ruda_miedzi", "Ruda miedzi", "ore", 6,
     "Zielonkawa gruda z połyskiem. Miękka, łatwa do wytopu na stopy i okucia."),
    ("odprysk_obsydianu", "Odprysk obsydianu", "ore", 14,
     "Ostry jak brzytwa okruch czarnego szkła wulkanicznego. Kruchy, lecz tnący."),
    ("esencja_cienia", "Esencja cienia", "essence", 25,
     "Kłąb zimnej mgły zamknięty w krysztale. Wije się i ucieka od światła."),
    ("esencja_upiora", "Esencja upiora", "essence", 22,
     "Blada poświata zdarta z rozpraszającego się nieumarłego. Chłodzi dłoń przez szkło."),
    ("korzen_zmornika", "Korzeń zmornika", "herb", 7,
     "Sękaty korzeń grzęzawiskowego zioła. Gorzki, lecz zbija gorączkę i krzepi krew."),
    ("kapelusz_bledunia", "Kapelusz bledunia", "herb", 6,
     "Blady kapelusz leśnego grzyba rosnącego w cieniu głazów. Suszony wchodzi do wywarów."),
]

# ── beast loot tables: (table_key, label, enemy_key_to_repoint_or_None, entries)
#    entries: [(item_key, weight, qty_min, qty_max), ...]. gold zeroed on all.
BEAST_TABLES: list[tuple[str, str, str | None, list[tuple[str, int, int, int]]]] = [
    ("loot_wolf", "Łupy: Wilk", None, [
        ("kiel_wilczy", 60, 1, 2), ("wolf_pelt", 45, 1, 1)]),
    ("loot_rykar_wilkowy", "Łupy: Rykar Wilkowy", None, [
        ("kiel_wilczy", 55, 1, 3), ("wolf_pelt", 45, 1, 2), ("krew_wilkolaka", 25, 1, 1)]),
    ("loot_szczury_grobowe", "Łupy: Szczury Grobowe", None, [
        ("kiel_szczurzy", 55, 1, 3)]),
    ("loot_skeleton", "Łupy: Szkielet", None, [
        ("bone_dust", 60, 1, 2)]),
    ("loot_giant_spider", "Łupy: Olbrzymi Pająk", "giant_spider", [
        ("gruczol_pajeczy", 60, 1, 1), ("jedwab_pajeczy", 50, 1, 2)]),
    ("loot_cave_bear", "Łupy: Niedźwiedź Jaskiniowy", "cave_bear", [
        ("bear_hide", 60, 1, 1), ("sadlo_niedzwiedzie", 50, 1, 2), ("kiel_wilczy", 20, 1, 1)]),
    ("loot_giant_rat", "Łupy: Olbrzymi Szczur", "giant_rat", [
        ("kiel_szczurzy", 60, 1, 2)]),
    ("loot_lizardman", "Łupy: Jaszczuroludek", "lizardman", [
        ("luska_jaszczura", 55, 1, 2)]),
]

# item keys owned by BL-B3 wiring — stripped before re-adding (idempotency).
_COMPONENT_LOOT_KEYS = {ik for _, _, _, ents in BEAST_TABLES for ik, *_ in ents}
_BEAST_TABLE_KEYS = {tk for tk, *_ in BEAST_TABLES}


def _base_item_template(sample: dict) -> dict:
    """A neutral game_config_items row shaped like the existing seed rows."""
    return {k: (0 if k in ("is_active", "ac_bonus", "charges", "ai_generated",
                           "effect_bonus", "hidden", "is_component")
                else 1 if k in ("approved", "rarity", "min_level")
                else None)
            for k in sample.keys()}


def main(dry_run: bool = False) -> int:
    items = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    tables = json.loads(TABLES_PATH.read_text(encoding="utf-8"))
    entries = json.loads(ENTRIES_PATH.read_text(encoding="utf-8"))
    enemies = json.loads(ENEMIES_PATH.read_text(encoding="utf-8"))

    # ── 1a. stamp component columns on ALL item rows (loader keys off row[0];
    #        is_component is NOT NULL so every row must carry it) ───────────────
    for it in items:
        it.setdefault("is_component", 0)
        it.setdefault("component_type", None)
        it.setdefault("created_by", None)
        # normalize position so the three keys exist on every row
        it["is_component"] = 1 if it["key"] in FLAG_EXISTING else int(it.get("is_component") or 0)
        if it["key"] in FLAG_EXISTING:
            it["component_type"] = FLAG_EXISTING[it["key"]]

    existing_keys = {it["key"] for it in items}
    tmpl = items[0]

    # ── 1b. append new components (idempotent by key) ─────────────────────────
    added = 0
    for key, label, ctype, value, desc in NEW_COMPONENTS:
        if key in existing_keys:
            # already present → refresh the component flags in place
            for it in items:
                if it["key"] == key:
                    it.update(is_component=1, component_type=ctype, created_by="seed")
            continue
        rec = _base_item_template(tmpl)
        rec.update({
            "key": key, "label": label, "item_type": "material", "description": desc,
            "value_gp": value, "price_gp": value, "weight_kg": 0.3,
            "allowed_classes": "[]", "effect_target": "self",
            "review_status": "permanent", "created_at": _TS, "updated_at": _TS,
            "is_component": 1, "component_type": ctype, "created_by": "seed",
        })
        items.append(rec)
        added += 1

    # ── 2. beast loot tables (create/refresh) + gold zero ─────────────────────
    tbl_by_key = {t["key"]: t for t in tables}
    for tk, label, _enemy, _ents in BEAST_TABLES:
        if tk in tbl_by_key:
            tbl_by_key[tk]["gold_min"] = 0
            tbl_by_key[tk]["gold_max"] = 0
        else:
            tables.append({
                "key": tk, "label": label, "description": "",
                "is_active": 1, "locked_at": None,
                "created_at": _TS, "updated_at": _TS,
                "gold_min": 0, "gold_max": 0,
            })

    # ── 2b. strip prior BL-B3 component entries from beast tables, re-add ──────
    kept = [
        e for e in entries
        if not (e.get("loot_table_key") in _BEAST_TABLE_KEYS
                and e.get("item_key") in _COMPONENT_LOOT_KEYS)
    ]
    for tk, _label, _enemy, ents in BEAST_TABLES:
        for ik, w, qmin, qmax in ents:
            kept.append({
                "id": None, "loot_table_key": tk,
                "item_key": ik, "consumable_key": None, "weapon_key": None,
                "weight": w, "qty_min": qmin, "qty_max": qmax, "game_item_key": None,
            })
    for i, e in enumerate(kept, start=1):
        e["id"] = i

    # ── 3. repoint beasts that shared a generic pool ──────────────────────────
    repointed = 0
    en_by_key = {e["key"]: e for e in enemies}
    for tk, _label, enemy_key, _ents in BEAST_TABLES:
        if enemy_key and enemy_key in en_by_key:
            if en_by_key[enemy_key].get("loot_table_key") != tk:
                en_by_key[enemy_key]["loot_table_key"] = tk
                repointed += 1

    # ── report ────────────────────────────────────────────────────────────────
    n_comp = sum(1 for it in items if it.get("is_component"))
    print(f"components total: {n_comp} (new appended: {added})")
    print(f"beast tables: {len(BEAST_TABLES)} | enemies repointed: {repointed}")
    print(f"loot entries: {len(entries)} -> {len(kept)}")

    if dry_run:
        print("(dry-run — no files written)")
        return 0

    # deterministic table order (last writer in the pipeline → byte-idempotent
    # regardless of the order 1333 appended tier rows in).
    tables.sort(key=lambda t: t["key"])
    ITEMS_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    TABLES_PATH.write_text(json.dumps(tables, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ENTRIES_PATH.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ENEMIES_PATH.write_text(json.dumps(enemies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("seed rewritten.")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
