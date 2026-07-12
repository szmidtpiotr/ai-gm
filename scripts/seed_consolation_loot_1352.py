#!/usr/bin/env python3
"""WALKA-T6 (#1352) — seed the consolation loot pool (content-as-code #1202).

After a victory the loot modal must never be empty. When an enemy's roll comes up
dry, loot_service.roll_loot_with_consolation() hands the player one worthless/narrative
trinket from the `loot_trash_common` loot table. This script seeds that table, its
entries and the backing game_config_items rows into the committed seed JSON.

Content-as-code: the seed JSON is the source of truth; deploy_dev.sh / deploy_prod.sh
apply it via scripts/seed_content.py (full DELETE+INSERT). Idempotent — re-running
yields byte-identical output.

Usage:
    python3 scripts/seed_consolation_loot_1352.py            # rewrite seed in place
    python3 scripts/seed_consolation_loot_1352.py --dry-run  # print summary only
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds" / "content"
TABLES_PATH = SEED_DIR / "game_config_loot_tables.json"
ENTRIES_PATH = SEED_DIR / "game_config_loot_entries.json"
ITEMS_PATH = SEED_DIR / "game_config_items.json"

_TS = "2026-07-13 00:00:00"
TRASH_TABLE_KEY = "loot_trash_common"

# Narrative/worthless trinkets — value 0-1 gp. STARTING values, sandbox-tunable.
# (key, label, description, value_gp)
TRASH_ITEMS = [
    ("broken_pouch", "Zniszczony mieszek",
     "Przetarty skórzany mieszek z kilkoma miedziakami na dnie. Nic wartościowego.", 1),
    ("chipped_knife", "Szczerbaty nóż",
     "Tępe, wyszczerbione ostrze — nadaje się co najwyżej na złom.", 0),
    ("bone_die", "Kościana kostka do gry",
     "Pojedyncza kostka do gry wyrzeźbiona z kości. Pamiątka, nie skarb.", 0),
    ("torn_map_scrap", "Strzęp mapy bez wartości",
     "Wystrzępiony skrawek pergaminu z nieczytelnym fragmentem mapy. Bezużyteczny.", 0),
]


def _item_row(key: str, label: str, desc: str, value_gp: int) -> dict:
    """Minimal game_config_items row for a consolation trinket."""
    return {
        "key": key, "label": label, "item_type": "junk", "description": desc,
        "value_gp": value_gp, "effect_json": None, "is_active": 1,
        "locked_at": None, "created_at": _TS, "updated_at": _TS, "note": None,
        "weight_kg": 0.1, "ac_bonus": 0, "charges": 1, "ai_generated": 0,
        "approved": 1, "allowed_classes": "[]", "armor_coverage": None,
        "rarity": 1, "effect_type": None, "effect_dice": None, "effect_bonus": 0,
        "effect_target": "self", "source_exclusive": None, "campaign_id": None,
        "review_status": "permanent", "min_level": 1, "location_tags": None,
        "price_gp": value_gp, "pending_category": None, "image_url": None,
        "image_gen_prompt": None, "template_id": None, "hidden": 0,
        "is_component": 0, "component_type": None, "created_by": "seed",
    }


def main() -> int:
    dry = "--dry-run" in sys.argv
    tables = json.loads(TABLES_PATH.read_text(encoding="utf-8"))
    entries = json.loads(ENTRIES_PATH.read_text(encoding="utf-8"))
    items = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))

    changes: list[str] = []

    # 1) loot table
    if TRASH_TABLE_KEY not in {t["key"] for t in tables}:
        tables.append({
            "key": TRASH_TABLE_KEY, "label": "Łupy: Drobiazgi (consolation)",
            "description": "T6 (#1352): gwarantowany drop minimalny po zwycięstwie.",
            "is_active": 1, "locked_at": None, "created_at": _TS, "updated_at": _TS,
            "gold_min": 0, "gold_max": 1,
        })
        changes.append(f"+table {TRASH_TABLE_KEY}")

    # 2) items
    have_items = {i["key"] for i in items}
    for key, label, desc, val in TRASH_ITEMS:
        if key not in have_items:
            items.append(_item_row(key, label, desc, val))
            changes.append(f"+item {key}")

    # 3) entries (idempotent: keyed by (table, item_key))
    have_entries = {
        (e.get("loot_table_key"), e.get("item_key"))
        for e in entries if e.get("loot_table_key") == TRASH_TABLE_KEY
    }
    next_id = max((e.get("id", 0) for e in entries), default=0) + 1
    for key, *_ in TRASH_ITEMS:
        if (TRASH_TABLE_KEY, key) not in have_entries:
            entries.append({
                "id": next_id, "loot_table_key": TRASH_TABLE_KEY, "item_key": key,
                "consumable_key": None, "weapon_key": None, "weight": 100,
                "qty_min": 1, "qty_max": 1, "game_item_key": None,
            })
            changes.append(f"+entry {TRASH_TABLE_KEY}/{key} (id={next_id})")
            next_id += 1

    if not changes:
        print("Nothing to do — consolation pool already seeded.")
        return 0

    print("\n".join(changes))
    if dry:
        print("(dry-run — no files written)")
        return 0

    TABLES_PATH.write_text(
        json.dumps(tables, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ENTRIES_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ITEMS_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(changes)} change(s) to seed JSON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
