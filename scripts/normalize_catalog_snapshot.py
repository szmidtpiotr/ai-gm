#!/usr/bin/env python3
"""
Normalize aigm_catalog_snapshot JSON for POST /api/admin/config/catalog-snapshot/import.

- Dedupe rows per table (stable: keep last occurrence).
- 8H: drop game_config_consumables rows whose key already exists in game_config_items as consumable.
- Merge duplicate item keys (legacy double naming) and rewrite loot references.
- Fill missing effect_type on consumable items when inferable (stat_buff / remove_condition / heal_hp).
- Strip unknown columns per target schema (safe insert).
- Fix obvious stat label typo.
- Skills: fill empty descriptions with defaults; stealth rank_ceiling 6 → 5 (sheet parity).

Usage:
  python3 scripts/normalize_catalog_snapshot.py /path/to/in.json -o /path/to/out.json
"""

from __future__ import annotations

import argparse
import json
from typing import Any

# Import order matches admin_config_transfer._CATALOG_IMPORT_TABLES FK safety for orphan loot prune.
TABLE_ORDER = [
    "game_config_stats",
    "game_config_skills",
    "game_config_dc",
    "game_config_weapons",
    "game_config_conditions",
    "game_config_items",
    "game_config_consumables",
    "game_config_loot_tables",
    "game_config_enemies",
    "game_config_loot_entries",
]

# Allowed columns after migrations (8H). Omit columns not listed — import uses INSERT by pragma on server,
# but pruning avoids confusion and stale keys like proficiency_classes / weight on items.
ALLOWED_COLUMNS: dict[str, frozenset[str]] = {
    "game_config_stats": frozenset(
        {"key", "label", "description", "sort_order", "locked_at", "created_at", "updated_at"}
    ),
    "game_config_skills": frozenset(
        {"key", "label", "linked_stat", "rank_ceiling", "sort_order", "locked_at", "description", "created_at", "updated_at"}
    ),
    "game_config_dc": frozenset(
        {"key", "label", "value", "description", "sort_order", "locked_at", "created_at", "updated_at"}
    ),
    "game_config_weapons": frozenset(
        {
            "key",
            "label",
            "damage_die",
            "linked_stat",
            "allowed_classes",
            "description",
            "weapon_type",
            "two_handed",
            "finesse",
            "range_m",
            "weight_kg",
            "note",
            "is_active",
            "locked_at",
            "created_at",
            "updated_at",
            "value_gp",
            "ai_generated",
            "approved",
        }
    ),
    "game_config_conditions": frozenset(
        {
            "key",
            "label",
            "effect_json",
            "description",
            "stackable",
            "auto_remove",
            "is_active",
            "locked_at",
            "created_at",
            "updated_at",
        }
    ),
    "game_config_items": frozenset(
        {
            "key",
            "label",
            "item_type",
            "description",
            "value_gp",
            "effect_json",
            "is_active",
            "locked_at",
            "created_at",
            "updated_at",
            "note",
            "weight_kg",
            "ac_bonus",
            "effect_type",
            "effect_dice",
            "effect_bonus",
            "effect_target",
            "charges",
            "ai_generated",
            "approved",
            "allowed_classes",
        }
    ),
    "game_config_consumables": frozenset(
        {
            "key",
            "label",
            "description",
            "effect_type",
            "effect_dice",
            "effect_bonus",
            "effect_target",
            "weight_kg",
            "charges",
            "base_price",
            "note",
            "is_active",
            "locked_at",
            "created_at",
            "updated_at",
        }
    ),
    "game_config_loot_tables": frozenset(
        {
            "key",
            "label",
            "description",
            "is_active",
            "gold_min",
            "gold_max",
            "locked_at",
            "created_at",
            "updated_at",
        }
    ),
    "game_config_enemies": frozenset(
        {
            "key",
            "label",
            "hp_base",
            "ac_base",
            "attack_bonus",
            "damage_die",
            "description",
            "tier",
            "attacks_per_turn",
            "damage_bonus",
            "damage_type",
            "xp_award",
            "dex_modifier",
            "conditions_immune",
            "loot_table_key",
            "drop_chance",
            "note",
            "is_active",
            "locked_at",
            "created_at",
            "updated_at",
        }
    ),
    "game_config_loot_entries": frozenset(
        {
            "id",
            "loot_table_key",
            "item_key",
            "weapon_key",
            "currency_code",
            "weight",
            "qty_min",
            "qty_max",
        }
    ),
}

ALLOWED_ITEM_TYPES = frozenset({"weapon", "armor", "consumable", "misc", "quest", "narrative"})
EFFECT_TYPES = frozenset({"heal_hp", "restore_mana", "remove_condition", "add_condition", "stat_buff", "misc"})

# Default skill descriptions when export has null (tooltips / roll hints).
SKILL_DESCRIPTION_DEFAULTS: dict[str, str] = {
    "arcana": "Knowledge of spells, magical theory, and arcane phenomena.",
    "athletics": "Climbing, jumping, swimming, lifting, sprinting — raw physical prowess.",
    "attack": "Melee strikes and weapon blows (non-ranged).",
    "awareness": "Noticing threats, ambushes, traps, and subtle environmental cues.",
    "initiative": "Reacting first in combat when surprise or timing matters.",
    "intimidation": "Coercion through threats, presence, or fear.",
    "investigation": "Deduction, searching scenes, and interpreting clues.",
    "lore": "History, legends, cultures, and general scholarship.",
    "medicine": "Treating wounds, stabilizing allies, and diagnosing poisons or disease.",
    "persuasion": "Honest influence, deals, and good-faith negotiation.",
    "ranged_attack": "Accuracy with bows, thrown weapons, and ranged arms.",
    "stealth": "Moving unseen, hiding, and quiet approach.",
    "survival": "Foraging, tracking, weather, and enduring the wild.",
}


def _enrich_skill_rows(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        row = dict(r)
        k = str(row.get("key") or "").strip()
        if k == "stealth" and int(row.get("rank_ceiling") or 0) == 6:
            row["rank_ceiling"] = 5
        desc = row.get("description")
        if (desc is None or str(desc).strip() == "") and k in SKILL_DESCRIPTION_DEFAULTS:
            row["description"] = SKILL_DESCRIPTION_DEFAULTS[k]
        out.append(row)
    return out

# Legacy duplicate keys → canonical key (loot + references rewritten).
MERGE_ITEM_KEYS: dict[str, str] = {
    "elixir_of_strength": "elixir_strength",
    "elixir_of_agility": "elixir_agility",
}


def _dedupe_by_key(rows: list[dict], key_field: str = "key") -> list[dict]:
    seen: dict[str, dict] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        k = str(r.get(key_field) or "").strip()
        if not k:
            continue
        seen[k] = r
    return [seen[k] for k in sorted(seen.keys())]


def _dedupe_loot_entries(rows: list[dict]) -> list[dict]:
    """Dedupe by (loot_table_key, item_key, weapon_key); keep last."""
    seen: dict[tuple[str, str, str], dict] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        tk = str(r.get("loot_table_key") or "").strip()
        ik = str(r.get("item_key") or "").strip() if r.get("item_key") else ""
        wk = str(r.get("weapon_key") or "").strip() if r.get("weapon_key") else ""
        if not tk or (not ik and not wk):
            continue
        seen[(tk, ik, wk)] = r
    out = list(seen.values())
    out.sort(key=lambda x: (str(x.get("loot_table_key")), str(x.get("item_key")), str(x.get("weapon_key"))))
    return out


def _strip_columns(table: str, row: dict) -> dict:
    allowed = ALLOWED_COLUMNS.get(table)
    if not allowed:
        return row
    return {k: v for k, v in row.items() if k in allowed}


def _infer_effect_type(item: dict) -> str | None:
    et = item.get("effect_type")
    if et is not None and str(et).strip():
        return str(et).strip().lower()
    it = str(item.get("item_type") or "").lower()
    if it != "consumable":
        return None
    ej = item.get("effect_json")
    if ej:
        s = ej if isinstance(ej, str) else json.dumps(ej)
        if "temp_stat_mods" in s or "stat_mods" in s:
            return "stat_buff"
        if "remove_condition" in s or '"remove_condition"' in s:
            return "remove_condition"
        if "heal" in s.lower() or "restore_mana" in s.lower():
            return "heal_hp"
    bonus = int(item.get("effect_bonus") or 0)
    if bonus > 0:
        return "stat_buff"
    return None


def _prefer_item_row(a: dict, b: dict) -> dict:
    """When two rows collide on same key after rename-merge, keep richer catalog row."""
    score = lambda r: (
        1 if str(r.get("effect_type") or "").strip() else 0,
        1 if str(r.get("effect_dice") or "").strip() else 0,
        int(r.get("effect_bonus") or 0),
        len(str(r.get("description") or "")),
    )
    return a if score(a) >= score(b) else b


def _normalize_items(rows: list[dict]) -> tuple[list[dict], dict[str, str]]:
    """Returns normalized rows and key merge map applied (old -> new)."""
    merge_applied: dict[str, str] = {}
    by_key: dict[str, dict] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        r = dict(r)
        k = str(r.get("key") or "").strip()
        if not k:
            continue
        orig_k = k
        if k in MERGE_ITEM_KEYS:
            merge_applied[orig_k] = MERGE_ITEM_KEYS[k]
            k = MERGE_ITEM_KEYS[k]
            r["key"] = k
        it = str(r.get("item_type") or "misc").strip().lower()
        if it not in ALLOWED_ITEM_TYPES:
            it = "misc"
        r["item_type"] = it
        if "allowed_classes" not in r or r["allowed_classes"] in (None, ""):
            r["allowed_classes"] = "[]"
        inferred = _infer_effect_type(r)
        if inferred and not (r.get("effect_type") and str(r["effect_type"]).strip()):
            r["effect_type"] = inferred
        elif str(r.get("item_type") or "").lower() == "consumable" and not (r.get("effect_type") and str(r["effect_type"]).strip()):
            r["effect_type"] = "misc"
        et = str(r.get("effect_type") or "").strip().lower()
        if et and et not in EFFECT_TYPES:
            r["effect_type"] = "misc"
        row = _strip_columns("game_config_items", r)
        if k in by_key:
            by_key[k] = _prefer_item_row(by_key[k], row)
        else:
            by_key[k] = row
    out = [by_key[k] for k in sorted(by_key.keys())]
    return out, merge_applied


def _normalize_consumables(rows: list[dict], item_keys: set[str]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        k = str(r.get("key") or "").strip()
        if not k:
            continue
        if k in item_keys:
            continue  # 8H: jeden katalog — pomiń legacy consumable gdy istnieje wpis w game_config_items
        r = dict(r)
        if "base_price" not in r and r.get("value_gp") is not None:
            r["base_price"] = int(r["value_gp"])
        r.pop("value_gp", None)
        et = str(r.get("effect_type") or "misc").strip().lower()
        r["effect_type"] = et if et in EFFECT_TYPES else "misc"
        out.append(_strip_columns("game_config_consumables", r))
    return _dedupe_by_key(out)


def _rewrite_loot_entries(
    rows: list[dict],
    merge_map: dict[str, str],
    valid_item_keys: set[str],
    valid_weapon_keys: set[str],
    valid_table_keys: set[str],
) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        r = dict(r)
        tk = str(r.get("loot_table_key") or "").strip()
        if tk not in valid_table_keys:
            continue
        ik = r.get("item_key")
        if ik:
            ik = merge_map.get(str(ik), str(ik))
            r["item_key"] = ik if ik else None
        if r.get("item_key") and str(r["item_key"]) not in valid_item_keys:
            continue
        if r.get("weapon_key") and str(r["weapon_key"]) not in valid_weapon_keys:
            continue
        xor_ok = bool(r.get("item_key")) ^ bool(r.get("weapon_key"))
        if not xor_ok:
            continue
        r.pop("consumable_key", None)
        out.append(_strip_columns("game_config_loot_entries", r))
    return _dedupe_loot_entries(out)


def normalize_payload(data: dict[str, Any]) -> dict[str, Any]:
    tables_in = data.get("tables") or {}
    if not isinstance(tables_in, dict):
        raise ValueError("Invalid snapshot: tables must be an object")

    out_tables: dict[str, list] = {}

    # Stats — fix STR label typo
    stats = [_strip_columns("game_config_stats", dict(r)) for r in tables_in.get("game_config_stats") or [] if isinstance(r, dict)]
    for s in stats:
        if s.get("key") == "STR" and s.get("label") == "Strength Temp":
            s["label"] = "Strength"
    out_tables["game_config_stats"] = _dedupe_by_key(stats)

    skills = [_strip_columns("game_config_skills", dict(r)) for r in tables_in.get("game_config_skills") or [] if isinstance(r, dict)]
    out_tables["game_config_skills"] = _enrich_skill_rows(_dedupe_by_key(skills))

    dc = [_strip_columns("game_config_dc", dict(r)) for r in tables_in.get("game_config_dc") or [] if isinstance(r, dict)]
    out_tables["game_config_dc"] = _dedupe_by_key(dc)

    weapons = [_strip_columns("game_config_weapons", dict(r)) for r in tables_in.get("game_config_weapons") or [] if isinstance(r, dict)]
    out_tables["game_config_weapons"] = _dedupe_by_key(weapons)
    weapon_keys = {str(w["key"]) for w in out_tables["game_config_weapons"]}

    cond = [_strip_columns("game_config_conditions", dict(r)) for r in tables_in.get("game_config_conditions") or [] if isinstance(r, dict)]
    out_tables["game_config_conditions"] = _dedupe_by_key(cond)

    items_raw = [dict(r) for r in tables_in.get("game_config_items") or [] if isinstance(r, dict)]
    items, merge_map = _normalize_items(items_raw)
    out_tables["game_config_items"] = items
    item_keys = {str(i["key"]) for i in items}

    consumables = _normalize_consumables(
        [dict(r) for r in tables_in.get("game_config_consumables") or []],
        item_keys,
    )
    out_tables["game_config_consumables"] = consumables

    lt = [_strip_columns("game_config_loot_tables", dict(r)) for r in tables_in.get("game_config_loot_tables") or [] if isinstance(r, dict)]
    out_tables["game_config_loot_tables"] = _dedupe_by_key(lt)
    loot_table_keys = {str(t["key"]) for t in out_tables["game_config_loot_tables"]}

    enemies = [_strip_columns("game_config_enemies", dict(r)) for r in tables_in.get("game_config_enemies") or [] if isinstance(r, dict)]
    out_tables["game_config_enemies"] = _dedupe_by_key(enemies)

    loot_entries_raw = [dict(r) for r in tables_in.get("game_config_loot_entries") or [] if isinstance(r, dict)]
    out_tables["game_config_loot_entries"] = _rewrite_loot_entries(
        loot_entries_raw,
        merge_map,
        item_keys,
        weapon_keys,
        loot_table_keys,
    )

    payload = {
        "export_kind": "catalog_snapshot",
        "config_version": str(data.get("config_version") or "1.0.0"),
        "exported_at": data.get("exported_at"),
        "exported_by": str(data.get("exported_by") or "normalize_catalog_snapshot"),
        "tables": {k: out_tables[k] for k in TABLE_ORDER},
        "notes": (
            "Normalized for 8H import: merged duplicate item keys (elixir_of_* → elixir_*), "
            "removed consumables duplicated in game_config_items, inferred effect_type where obvious, "
            "deduped loot_entries and pruned orphan FK references."
        ),
    }
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_json", type=str)
    ap.add_argument("-o", "--output", required=True, help="Output JSON path")
    args = ap.parse_args()

    with open(args.input_json, encoding="utf-8") as f:
        raw = json.load(f)

    fixed = normalize_payload(raw)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False, indent=2)
        f.write("\n")

    counts = {t: len(fixed["tables"][t]) for t in TABLE_ORDER}
    print(json.dumps({"ok": True, "would_import_rows": counts}, indent=2))


if __name__ == "__main__":
    main()
