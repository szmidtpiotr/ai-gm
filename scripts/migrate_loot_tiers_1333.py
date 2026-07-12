#!/usr/bin/env python3
"""BL-B1 (#1333) — migrate generic loot entries from ~79 per-enemy tables into
shared tier tables (loot_tier_weak/standard/elite/boss).

Content-as-code (#1202): this rewrites the committed seed JSON in place. The
result is the source of truth; deploy_dev.sh / deploy_prod.sh apply it via
scripts/seed_content.py (full DELETE+INSERT).

Idempotent: the four tier tables are regenerated from the spec each run, and
generic supply keys are stripped from every per-enemy table. Running twice
yields byte-identical output.

Usage:
    python3 scripts/migrate_loot_tiers_1333.py            # rewrite seed in place
    python3 scripts/migrate_loot_tiers_1333.py --dry-run  # print summary only
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds" / "content"
TABLES_PATH = SEED_DIR / "game_config_loot_tables.json"
ENTRIES_PATH = SEED_DIR / "game_config_loot_entries.json"

# Tables that are NOT per-enemy uniques — never strip generics from these.
# (dungeon/generic pools + the tier tables themselves.)
PROTECTED_TABLES = {
    "loot_poor", "loot_standard", "loot_rich", "loot_treasure", "loot_enemy",
    "loot_tier_weak", "loot_tier_standard", "loot_tier_elite", "loot_tier_boss",
}

# Universal supply keys that now live in the tier tables instead of being
# duplicated across per-enemy tables. Weapons/armor and thematic reagents stay
# per-enemy (the "unikaty per wróg"). fragment_mapy_skarbow is a #1196 treasure
# hook, deliberately per-enemy — NOT generic.
GENERIC_SUPPLY_KEYS = {
    "torch", "bandage", "healing_herb", "waterskin",
    "potion_healing_minor", "potion_healing_standard", "potion_mana_standard",
    "antidote", "potion_resistance", "rope_hemp", "oil_flask", "holy_water",
    "bedroll", "lockpicks", "shovel", "parchment_sheets", "silk_thread",
    "caltrops_bag",
}

_TS = "2026-07-12 00:00:00"

# Tier table definitions (loot_tables rows). Gold stays 0 — gold is rolled from
# the enemy's OWN per-enemy table (roll_gold_drop), never the tier table.
TIER_TABLE_ROWS = [
    ("loot_tier_weak", "Tier: Słaby (wróg weak)"),
    ("loot_tier_standard", "Tier: Standardowy (wróg standard)"),
    ("loot_tier_elite", "Tier: Elitarny (wróg elite)"),
    ("loot_tier_boss", "Tier: Boss (wróg boss)"),
]

# Curated tier entries. Numbers Policy (#1333): weights are STARTING values;
# target ≥40% użytkowe (consumable/weapon) per tier. Sandbox/admin-tunable.
# Format: (table_key, [(kind, key, weight, qty_min, qty_max), ...])
#   kind ∈ {"item", "consumable", "weapon"} → chooses the XOR column.
TIER_ENTRIES: dict[str, list[tuple[str, str, int, int, int]]] = {
    "loot_tier_weak": [
        ("item", "torch", 45, 1, 2),
        ("item", "bandage", 50, 1, 2),
        ("item", "healing_herb", 40, 1, 2),
        ("item", "waterskin", 30, 1, 1),
        ("item", "potion_healing_minor", 22, 1, 1),
        ("weapon", "dagger", 12, 1, 1),
    ],
    "loot_tier_standard": [
        ("item", "bandage", 45, 1, 2),
        ("item", "potion_healing_minor", 40, 1, 2),
        ("item", "rope_hemp", 35, 1, 1),
        ("item", "torch", 30, 1, 2),
        ("item", "potion_healing_standard", 22, 1, 1),
        ("item", "antidote", 20, 1, 1),
        ("weapon", "shortsword", 15, 1, 1),
    ],
    "loot_tier_elite": [
        ("item", "potion_healing_standard", 40, 1, 2),
        ("item", "bandage", 35, 1, 2),
        ("item", "potion_mana_standard", 25, 1, 1),
        ("item", "antidote", 22, 1, 1),
        ("item", "potion_resistance", 18, 1, 1),
        ("item", "oil_flask", 20, 1, 1),
        ("weapon", "longsword", 14, 1, 1),
        ("item", "scale_mail", 12, 1, 1),
    ],
    "loot_tier_boss": [
        ("item", "potion_healing_standard", 45, 1, 2),
        ("item", "potion_healing_major", 30, 1, 1),
        ("item", "potion_mana_standard", 28, 1, 1),
        ("item", "potion_resistance", 25, 1, 1),
        ("weapon", "longsword", 20, 1, 1),
        ("item", "scale_mail", 18, 1, 1),
        ("item", "holy_water", 15, 1, 1),
    ],
}

_KIND_COL = {"item": "item_key", "consumable": "consumable_key", "weapon": "weapon_key"}


def _entry_raw_key(e: dict) -> str:
    return str(e.get("weapon_key") or e.get("item_key") or e.get("consumable_key") or "").strip()


def main(dry_run: bool = False) -> int:
    tables = json.loads(TABLES_PATH.read_text(encoding="utf-8"))
    entries = json.loads(ENTRIES_PATH.read_text(encoding="utf-8"))

    tier_keys = {k for k, _ in TIER_TABLE_ROWS}

    # ── 1. tables: drop existing tier rows, append fresh (idempotent) ──────────
    kept_tables = [t for t in tables if t.get("key") not in tier_keys]
    for key, label in TIER_TABLE_ROWS:
        kept_tables.append({
            "key": key, "label": label, "description": "",
            "is_active": 1, "locked_at": None,
            "created_at": _TS, "updated_at": _TS,
            "gold_min": 0, "gold_max": 0,
        })

    # ── 2. entries: strip tier-owned generics from per-enemy tables + drop old
    #       tier entries (regenerated below) ──────────────────────────────────
    stripped = 0
    kept_entries: list[dict] = []
    for e in entries:
        tk = e.get("loot_table_key")
        if tk in tier_keys:
            continue  # regenerated from spec
        if tk not in PROTECTED_TABLES and _entry_raw_key(e) in GENERIC_SUPPLY_KEYS:
            stripped += 1
            continue  # generic supply → moved to tier table
        kept_entries.append(e)

    # ── 3. append curated tier entries ────────────────────────────────────────
    tier_added = 0
    for table_key, rows in TIER_ENTRIES.items():
        for kind, key, weight, qmin, qmax in rows:
            entry = {
                "id": None,  # reindexed below
                "loot_table_key": table_key,
                "item_key": None, "consumable_key": None, "weapon_key": None,
                "weight": weight, "qty_min": qmin, "qty_max": qmax,
                "game_item_key": None,
            }
            entry[_KIND_COL[kind]] = key
            kept_entries.append(entry)
            tier_added += 1

    # ── 4. reindex ids sequentially (stable) ──────────────────────────────────
    for i, e in enumerate(kept_entries, start=1):
        e["id"] = i

    # ── report ────────────────────────────────────────────────────────────────
    print(f"tier tables: {len(TIER_TABLE_ROWS)} | tier entries: {tier_added}")
    print(f"generic entries stripped from per-enemy tables: {stripped}")
    print(f"total tables: {len(tables)} -> {len(kept_tables)}")
    print(f"total entries: {len(entries)} -> {len(kept_entries)}")

    # sanity: no generic left in any per-enemy table
    leftover = [
        e for e in kept_entries
        if e["loot_table_key"] not in PROTECTED_TABLES
        and _entry_raw_key(e) in GENERIC_SUPPLY_KEYS
    ]
    assert not leftover, f"generic still in per-enemy tables: {leftover[:3]}"

    if dry_run:
        print("(dry-run — no files written)")
        return 0

    TABLES_PATH.write_text(json.dumps(kept_tables, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ENTRIES_PATH.write_text(json.dumps(kept_entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("seed rewritten.")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
