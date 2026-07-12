#!/usr/bin/env python3
"""BL-B2 (#1334) — loot drop rebalance.

Two moves, both operating on the committed seed JSON (content-as-code #1202):

1. `fragment_mapy_skarbow` (a #1196 treasure hook that #1196's seed sprayed into
   72 of 79 tables — the single most common drop, so it stopped being a reward)
   now lives ONLY in the tier tables (BL-B1): standard 5, elite 10, boss 15.
   This strips every non-tier occurrence and (re)adds the three tier entries.
   The three tier entries mirror the canonical spec in
   `migrate_loot_tiers_1333.py::TIER_ENTRIES`, so the two scripts converge in
   either run order.

2. Narrative "junk" items (pure flavour — hourglass, lute, fishing rod…) were
   seeded at weight 30–45, as likely as a healing potion. They are reduced (not
   removed — the flavour stays, it just stops dominating) to weight 8.

Idempotent: fragment is removed-then-re-added; flavour weights are clamped with
min(); running twice yields byte-identical output.

Usage:
    python3 scripts/migrate_loot_rebalance_1334.py            # rewrite seed
    python3 scripts/migrate_loot_rebalance_1334.py --dry-run  # summary only
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds" / "content"
ENTRIES_PATH = SEED_DIR / "game_config_loot_entries.json"

FRAGMENT_KEY = "fragment_mapy_skarbow"

# Fragment now lives ONLY in the tier tables. Weights mirror
# migrate_loot_tiers_1333.py::TIER_ENTRIES — keep both in sync.
FRAGMENT_TIER_WEIGHTS = {
    "loot_tier_standard": 5,
    "loot_tier_elite": 10,
    "loot_tier_boss": 15,
}

# Pure-flavour "junk" items seeded at 30–45 weight. Clamped to FLAVOUR_CAP so a
# healing potion out-drops a fishing rod. NOT removed — atmosphere stays.
NARRATIVE_FLAVOUR_KEYS = {
    "hourglass", "spyglass", "lute", "dice_set", "fishing_net", "fishing_rod",
    "hunting_horn", "soft_slippers", "manacles", "small_chest", "belt_pouch",
    "backpack", "lantern_hooded", "tinderbox", "whetstone", "hooded_cloak",
    "travelers_cloak",
}
FLAVOUR_CAP = 8


def main(dry_run: bool = False) -> int:
    entries = json.loads(ENTRIES_PATH.read_text(encoding="utf-8"))

    # ── 1. strip every fragment entry (tier + per-enemy + generic pools) ───────
    stripped = sum(1 for e in entries if e.get("item_key") == FRAGMENT_KEY)
    kept = [e for e in entries if e.get("item_key") != FRAGMENT_KEY]

    # ── 2. clamp narrative flavour weights ────────────────────────────────────
    clamped = 0
    for e in kept:
        if e.get("item_key") in NARRATIVE_FLAVOUR_KEYS and e["weight"] > FLAVOUR_CAP:
            e["weight"] = FLAVOUR_CAP
            clamped += 1

    # ── 3. (re)add fragment to the three tier tables ──────────────────────────
    for table_key, weight in FRAGMENT_TIER_WEIGHTS.items():
        kept.append({
            "id": None,
            "loot_table_key": table_key,
            "item_key": FRAGMENT_KEY,
            "consumable_key": None,
            "weapon_key": None,
            "weight": weight,
            "qty_min": 1,
            "qty_max": 1,
            "game_item_key": None,
        })

    # ── 4. reindex ────────────────────────────────────────────────────────────
    for i, e in enumerate(kept, start=1):
        e["id"] = i

    frag_tables = sorted({e["loot_table_key"] for e in kept if e.get("item_key") == FRAGMENT_KEY})
    print(f"fragment stripped: {stripped} | fragment tables now: {frag_tables}")
    print(f"flavour weights clamped to {FLAVOUR_CAP}: {clamped}")
    print(f"total entries: {len(entries)} -> {len(kept)}")

    assert len(frag_tables) <= 5, f"fragment leaked into {len(frag_tables)} tables"
    assert all(t.startswith("loot_tier_") for t in frag_tables), frag_tables

    if dry_run:
        print("(dry-run — no files written)")
        return 0

    ENTRIES_PATH.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("seed rewritten.")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
