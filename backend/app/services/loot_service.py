"""Phase 8C / T18 — loot, inventory and consumable runtime."""

from __future__ import annotations

import json
import random
import re
import sqlite3
from typing import Any

from app.core.logging import get_logger
from app.services.dice import parse_character_sheet
from app.services.effect_json_migration import legacy_effect_fields_from_json

LOOT_DB_PATH = "/data/ai_gm.db"

logger = get_logger(__name__)

_SLOT_VALUES = {
    "head",
    "torso",
    "l_arm",
    "r_arm",
    "l_leg",
    "r_leg",
    "hands",
    "main_hand",
    "off_hand",
}

# Stage 5 E1/E2/E4: armor_coverage enum → which slots a single equipped row
# claims. 'full' anchors to torso but locks all four limbs simultaneously.
_ARMOR_COVERAGE_TO_SLOTS = {
    "head": ("head",),
    "torso": ("torso",),
    "limb_arm": ("l_arm", "r_arm"),  # caller picks one at equip time
    "limb_leg": ("l_leg", "r_leg"),  # caller picks one at equip time
    "hands": ("hands",),
    "full": ("torso", "l_arm", "r_arm", "l_leg", "r_leg"),
}
_VALID_ARMOR_COVERAGE = frozenset(_ARMOR_COVERAGE_TO_SLOTS.keys())

# Stage 5 follow-up: weapon_slot enum → which slots a weapon can occupy.
# 'two_handed' anchors at main_hand but locks off_hand too.
_VALID_WEAPON_SLOT = frozenset({"main_hand", "two_handed", "off_hand_only", "either"})


def _auto_pick_armor_slot(conn, character_id: int, coverage: str) -> str:
    """Map armor_coverage → anatomical doll slot for the 'armor'/'auto' equip sentinel.

    Single source of truth shared with admin_cheat auto-equip. For paired limb coverage
    picks the free side (left first). 'full' anchors to torso (limb-freeing handled by the
    caller's coverage=='full' branch). Raises for coverage with no anatomical slot.
    """
    cov = str(coverage or "").lower()
    if cov in ("torso", "full"):
        return "torso"
    if cov in ("head", "hands"):
        return cov
    if cov in ("limb_arm", "limb_leg"):
        left, right = _ARMOR_COVERAGE_TO_SLOTS[cov]
        taken = {
            str(r["slot"])
            for r in conn.execute(
                "SELECT slot FROM character_inventory "
                "WHERE character_id = ? AND equipped = 1 AND slot IN (?, ?)",
                (int(character_id), left, right),
            ).fetchall()
        }
        return left if left not in taken else right
    raise ValueError(f"armor coverage '{cov}' has no auto-equip slot")

# When game_config_items.item_type is wrong (e.g. quest) but effect_* matches consumable mechanics (8H).
_CONSUMABLE_EFFECT_SIGNAL = frozenset(
    {"heal_hp", "restore_mana", "remove_condition", "add_condition", "stat_buff"}
)
_SUPPORTED_ITEM_USE_EFFECTS = {"heal_hp", "apply_condition", "remove_condition", "narrative_only", "damage_enemy"}


_LEGACY_JOINS = """
            FROM character_inventory ci
            LEFT JOIN game_config_items gi ON gi.key = ci.item_key
            LEFT JOIN game_config_weapons gw ON gw.key = ci.weapon_key
                OR (ci.weapon_key LIKE 'weapon_%' AND gw.key = SUBSTR(ci.weapon_key, 8))
            LEFT JOIN game_config_consumables gc ON gc.key = ci.consumable_key
                OR (ci.consumable_key LIKE 'consumable_%' AND gc.key = SUBSTR(ci.consumable_key, 12))
            LEFT JOIN game_config_consumables gc_item ON gc_item.key = ci.item_key
                AND ci.weapon_key IS NULL AND (ci.consumable_key IS NULL OR ci.consumable_key = '')
            WHERE ci.character_id = ?
            ORDER BY ci.id ASC"""

_LEGACY_COLS_COMMON = """SELECT ci.id, ci.slot, ci.equipped, ci.quantity, ci.source, ci.acquired_at,
                   ci.item_key, ci.weapon_key, ci.consumable_key,
                   NULL AS narrative_label, ci.meta_json AS ci_meta_json,
                   gi.label AS item_label, gi.item_type AS item_kind,
                   NULL AS gi_armor_coverage, NULL AS gi_effect_json,"""


def _inventory_rows_sql_legacy() -> str:
    """Fallback do starych tabel — zawiera effect_type/dice gdy game_config_items je ma."""
    return (
        _LEGACY_COLS_COMMON
        + """ gi.effect_type AS gi_effect_type, gi.effect_dice AS gi_effect_dice,
                   gw.label AS weapon_label,
                   NULL AS gw_weapon_slot,
                   gc.label AS consumable_label,
                   gc_item.key AS consumable_catalog_item_key,
                   gc_item.label AS consumable_by_item_key_label"""
        + _LEGACY_JOINS
    )


def _inventory_rows_sql_legacy_minimal() -> str:
    """Ultra-minimal fallback — baza bez kolumn effect_type/effect_dice w game_config_items."""
    return (
        _LEGACY_COLS_COMMON
        + """ NULL AS gi_effect_type, NULL AS gi_effect_dice,
                   gw.label AS weapon_label,
                   NULL AS gw_weapon_slot,
                   gc.label AS consumable_label,
                   gc_item.key AS consumable_catalog_item_key,
                   gc_item.label AS consumable_by_item_key_label"""
        + _LEGACY_JOINS
    )


def _inventory_rows_sql(effect_json_col_sql: str, effect_type_col_sql: str, effect_dice_col_sql: str) -> str:
    """U11b (#557): czyta z game_items zamiast 3 starych tabel.

    Join po kluczu COALESCE(weapon_key, item_key, consumable_key) obsługuje:
    - prefix 'weapon_*' (legacy inventory) via CASE
    - overlap I∩C (items przechowywane jako item_key, ale kind=consumable w game_items)
    """
    # Wywołujący przekazuje wyrażenia SQL, które historycznie referencjonowały gi.* / gw.*
    # Dla game_items: effect_json jest kolumną top-level; item_type/effect_type/effect_dice
    # są w item_data JSON. Podmieniamy referencje na json_extract.
    _remap = {
        "gi.effect_json AS gi_effect_json": "gi.effect_json AS gi_effect_json",
        "gi.effect_type AS gi_effect_type": "json_extract(gi.item_data, '$.effect_type') AS gi_effect_type",
        "gi.effect_dice AS gi_effect_dice": "json_extract(gi.item_data, '$.effect_dice') AS gi_effect_dice",
        "NULL AS gi_effect_json": "NULL AS gi_effect_json",
        "NULL AS gi_effect_type": "NULL AS gi_effect_type",
        "NULL AS gi_effect_dice": "NULL AS gi_effect_dice",
    }
    col_effect_json = _remap.get(effect_json_col_sql, effect_json_col_sql)
    col_effect_type = _remap.get(effect_type_col_sql, effect_type_col_sql)
    col_effect_dice = _remap.get(effect_dice_col_sql, effect_dice_col_sql)

    return f"""
            SELECT ci.id, ci.slot, ci.equipped, ci.quantity, ci.source, ci.acquired_at,
                   ci.item_key, ci.weapon_key, ci.consumable_key,
                   ci.label AS narrative_label, ci.meta_json AS ci_meta_json,
                   CASE WHEN ci.weapon_key IS NULL AND ci.consumable_key IS NULL
                        THEN gi.label ELSE NULL END AS item_label,
                   CASE WHEN ci.weapon_key IS NULL AND ci.consumable_key IS NULL
                        THEN json_extract(gi.item_data, '$.item_type')
                        ELSE NULL END AS item_kind,
                   CASE WHEN ci.weapon_key IS NULL AND ci.consumable_key IS NULL
                        THEN json_extract(gi.item_data, '$.armor_coverage')
                        ELSE NULL END AS gi_armor_coverage,
                   {col_effect_json}, {col_effect_type}, {col_effect_dice},
                   CASE WHEN ci.weapon_key IS NOT NULL THEN gi.label ELSE NULL END AS weapon_label,
                   CASE WHEN ci.weapon_key IS NOT NULL
                        THEN json_extract(gi.weapon_data, '$.weapon_slot')
                        ELSE NULL END AS gw_weapon_slot,
                   CASE WHEN ci.consumable_key IS NOT NULL THEN gi.label ELSE NULL END AS consumable_label,
                   CASE WHEN ci.weapon_key IS NULL AND ci.consumable_key IS NULL
                             AND gi.kind = 'consumable'
                        THEN gi.key ELSE NULL END AS consumable_catalog_item_key,
                   CASE WHEN ci.weapon_key IS NULL AND ci.consumable_key IS NULL
                             AND gi.kind = 'consumable'
                        THEN gi.label ELSE NULL END AS consumable_by_item_key_label
            FROM character_inventory ci
            LEFT JOIN game_items gi ON gi.key = COALESCE(
                NULLIF(TRIM(COALESCE(
                    CASE WHEN ci.weapon_key LIKE 'weapon_%' THEN SUBSTR(ci.weapon_key, 8)
                         ELSE ci.weapon_key END,
                    '')), ''),
                NULLIF(TRIM(COALESCE(ci.item_key, '')), ''),
                NULLIF(TRIM(COALESCE(
                    CASE WHEN ci.consumable_key LIKE 'consumable_%' THEN SUBSTR(ci.consumable_key, 12)
                         ELSE ci.consumable_key END,
                    '')), '')
            )
            WHERE ci.character_id = ?
            ORDER BY ci.id ASC
            """


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(LOOT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# F2 (#462): affix rolling config per dungeon loot_tier
# (max_affixes, max_affix_tier, per-slot_chances)
_LOOT_TIER_AFFIX: dict[str, tuple[int, int, list[float]]] = {
    "poor":     (0, 0, []),
    "standard": (1, 1, [0.25]),
    "rich":     (2, 2, [0.50, 0.20]),
    "treasure": (3, 3, [0.70, 0.40, 0.15]),
}


def _affixes_for_max_tier(conn: sqlite3.Connection, max_tier: int) -> list[str]:
    try:
        rows = conn.execute(
            "SELECT key FROM game_config_affixes WHERE tier <= ? AND is_active = 1",
            (max_tier,),
        ).fetchall()
    except Exception:
        return []
    return [r["key"] if hasattr(r, "keys") else r[0] for r in rows]


def roll_weapon_affixes(
    loot_tier: str | None,
    conn: sqlite3.Connection,
    force_min_one: bool = False,
) -> list[str]:
    """F2 (#462): roll affix keys for a weapon drop based on dungeon loot_tier.

    Returns a deduplicated list of affix key strings (may be empty).
    Uses Python random so random.seed() controls results deterministically in tests.

    U25 (#575): force_min_one=True guarantees at least one affix of tier
    GUARANTEED_AFFIX_TIER even when loot_tier yields none (pity timer for boss drops).
    """
    cfg = _LOOT_TIER_AFFIX.get(str(loot_tier or "").strip().lower())
    rolled: list[str] = []
    if cfg and cfg[2]:
        max_tier, _, chances = cfg
        available = _affixes_for_max_tier(conn, max_tier)
        if available:
            for chance in chances:
                if random.random() < chance:
                    candidates = [k for k in available if k not in rolled]
                    if not candidates:
                        break
                    rolled.append(random.choice(candidates))

    if force_min_one and not rolled:
        from app.services.affix_pity_service import GUARANTEED_AFFIX_TIER
        guaranteed_pool = _affixes_for_max_tier(conn, GUARANTEED_AFFIX_TIER)
        if guaranteed_pool:
            rolled.append(random.choice(guaranteed_pool))

    return rolled


def _roll_dice_value(expr: str) -> int:
    raw = str(expr or "").strip().lower()
    # Supports: "2d6", "d8", "2d6+4", "1d4-1"
    m = re.match(r"^(\d*)d(\d+)([+-]\d+)?$", raw)
    if not m:
        raise ValueError("invalid_effect_value")
    n = int(m.group(1) or 1)
    sides = int(m.group(2))
    bonus = int(m.group(3) or 0)
    return sum(random.randint(1, sides) for _ in range(max(1, n))) + bonus


def _normalize_sheet_conditions(sheet: dict[str, Any]) -> list[dict[str, Any]]:
    raw = sheet.get("conditions")
    if not isinstance(raw, list):
        raw = []
    out: list[dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, dict):
            key = str(entry.get("key") or "").strip().lower()
            if not key:
                continue
            out.append(
                {
                    "key": key,
                    "label": str(entry.get("label") or key).strip() or key,
                    "effect_json": entry.get("effect_json"),
                    "source_item_key": entry.get("source_item_key"),
                    "applied_at": entry.get("applied_at"),
                }
            )
        elif isinstance(entry, str) and entry.strip():
            key = entry.strip().lower()
            out.append({"key": key, "label": key, "effect_json": None, "source_item_key": None, "applied_at": None})
    sheet["conditions"] = out
    return out


def _decode_effect_json(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _effect_payloads_from_item_row(row: sqlite3.Row) -> list[dict[str, Any]]:
    parsed = _decode_effect_json(row["effect_json"] if "effect_json" in row.keys() else None)
    if parsed and isinstance(parsed.get("effects"), list):
        return [e for e in parsed["effects"] if isinstance(e, dict)]

    effect_type = str(row["effect_type"] if "effect_type" in row.keys() and row["effect_type"] is not None else "").strip().lower()
    if not effect_type:
        return []
    effect_bonus = int(row["effect_bonus"] if "effect_bonus" in row.keys() and row["effect_bonus"] is not None else 0)
    effect_dice = str(row["effect_dice"] if "effect_dice" in row.keys() and row["effect_dice"] is not None else "").strip()
    effect_value: int | str | None = None
    if effect_dice:
        effect_value = effect_dice
    elif effect_bonus:
        effect_value = effect_bonus

    if effect_type == "heal_hp":
        return [{"type": "heal_hp", "value": effect_value if effect_value is not None else 0}]
    if effect_type == "restore_mana":
        return [{"type": "restore_mana", "value": effect_value if effect_value is not None else 0}]
    if effect_type == "remove_condition":
        condition_key = str(row["effect_target"] if "effect_target" in row.keys() and row["effect_target"] is not None else "").strip().lower()
        return [{"type": "remove_condition", "condition_key": condition_key}] if condition_key else []
    if effect_type == "add_condition":
        condition_key = str(row["effect_target"] if "effect_target" in row.keys() and row["effect_target"] is not None else "").strip().lower()
        return [{"type": "apply_condition", "condition_key": condition_key}] if condition_key else []
    return []


def _condition_catalog_row(conn: sqlite3.Connection, condition_key: str) -> sqlite3.Row | None:
    try:
        return conn.execute(
            """
            SELECT key, label, effect_json, stackable
            FROM game_config_conditions
            WHERE key = ? AND COALESCE(is_active, 1) = 1
            LIMIT 1
            """,
            (str(condition_key or "").strip().lower(),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None


def _sync_player_state_to_active_combat(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
    current_hp: int,
    conditions: list[dict[str, Any]],
) -> None:
    try:
        row = conn.execute(
            """
            SELECT combatants
            FROM active_combat
            WHERE campaign_id = ? AND character_id = ?
            LIMIT 1
            """,
            (int(campaign_id), int(character_id)),
        ).fetchone()
    except sqlite3.OperationalError:
        return
    if not row:
        return
    try:
        combatants = json.loads(row["combatants"] or "[]")
    except Exception:
        return
    if not isinstance(combatants, list):
        return
    changed = False
    for combatant in combatants:
        if not isinstance(combatant, dict) or str(combatant.get("id")) != "player":
            continue
        combatant["hp_current"] = int(current_hp)
        combatant["conditions"] = conditions
        changed = True
        break
    if changed:
        conn.execute(
            "UPDATE active_combat SET combatants = ?, updated_at = datetime('now') WHERE campaign_id = ? AND character_id = ?",
            (json.dumps(combatants, ensure_ascii=False), int(campaign_id), int(character_id)),
        )


def _row_to_loot_entry(row: sqlite3.Row) -> dict[str, Any]:
    # `weight` is used as direct per-entry drop percent in range 1..100.
    weight = max(1, min(100, int(row["weight"] or 0)))
    chance = float(weight / 100.0)
    return {
        "item_key": row["item_key"],
        "weapon_key": row["weapon_key"],
        "consumable_key": row["consumable_key"],
        "chance": chance,
        "quantity_min": max(1, int(row["qty_min"] or 1)),
        "quantity_max": max(1, int(row["qty_max"] or 1)),
        "weight": weight,
    }


def _catalog_entry(conn: sqlite3.Connection, loot: dict[str, Any]) -> tuple[str, str, str] | None:
    """U11b (#557): czyta z game_items zamiast starych tabel.

    Priorytety klucza: weapon_key > item_key > consumable_key (XOR w loot_entries).
    Szuka po kluczu bez ograniczenia kind — obsługuje overlap I∩C (health_potion_small etc).
    """
    raw_key = (
        loot.get("weapon_key")
        or loot.get("item_key")
        or loot.get("consumable_key")
        or ""
    )
    key = str(raw_key).strip()
    if not key:
        return None

    try:
        row = conn.execute(
            "SELECT key, label, kind FROM game_items WHERE key = ? AND is_active = 1 LIMIT 1",
            (key,),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None

    if row:
        kind = str(row["kind"] or "item")
        label = str(row["label"] or row["key"])
        # Mapuj kind → item_type (loot service rozróżnia weapon/consumable/inne)
        if kind == "weapon":
            return str(row["key"]), label, "weapon"
        if kind == "consumable":
            return str(row["key"]), label, "consumable"
        return str(row["key"]), label, kind  # armor / item

    # Fallback: stare tabele (dla LLM-created items przed U11c)
    if loot.get("weapon_key"):
        old = conn.execute(
            "SELECT key, label FROM game_config_weapons WHERE key = ? AND is_active = 1",
            (key,),
        ).fetchone()
        if old:
            return str(old["key"]), str(old["label"] or old["key"]), "weapon"

    if loot.get("consumable_key"):
        old = conn.execute(
            "SELECT key, label FROM game_config_consumables WHERE key = ? AND is_active = 1",
            (key,),
        ).fetchone()
        if old:
            return str(old["key"]), str(old["label"] or old["key"]), "consumable"

    if loot.get("item_key"):
        try:
            old = conn.execute(
                "SELECT key, label, item_type FROM game_config_items WHERE key = ? AND is_active = 1",
                (key,),
            ).fetchone()
        except sqlite3.OperationalError:
            old = None
        if old:
            item_type = str(old["item_type"] or "item").strip().lower() or "item"
            return str(old["key"]), str(old["label"] or old["key"]), item_type

    return None


def get_loot_table(enemy_key: str) -> list[dict]:
    """
    Resolve enemy loot table into weighted entries.
    Returns [] when enemy or loot table is missing.
    """
    ek = str(enemy_key or "").strip()
    if not ek:
        return []

    with _conn() as conn:
        enemy = conn.execute(
            "SELECT loot_table_key FROM game_config_enemies WHERE key = ?",
            (ek,),
        ).fetchone()
        if not enemy or not enemy["loot_table_key"]:
            return []
        table_key = str(enemy["loot_table_key"])
        rows = conn.execute(
            """
            SELECT e.item_key, e.weapon_key, e.consumable_key, e.weight, e.qty_min, e.qty_max
            FROM game_config_loot_entries e
            JOIN game_config_loot_tables t ON t.key = e.loot_table_key
            WHERE e.loot_table_key = ? AND t.is_active = 1
            ORDER BY e.id ASC
            """,
            (table_key,),
        ).fetchall()
    if not rows:
        return []
    return [_row_to_loot_entry(r) for r in rows]


def roll_loot(enemy_key: str) -> list[dict]:
    """
    Roll each loot-table entry independently for enemy_key.
    Returns [] when enemy or loot table is missing, or no entry roll succeeds.
    """
    ek = str(enemy_key or "").strip()
    if not ek:
        return []
    with _conn() as conn:
        enemy = conn.execute(
            "SELECT loot_table_key FROM game_config_enemies WHERE key = ?",
            (ek,),
        ).fetchone()
    if not enemy or not enemy["loot_table_key"]:
        return []

    entries = get_loot_table(ek)
    if not entries:
        return []

    rolled: list[dict] = []
    for entry in entries:
        if random.random() > float(entry.get("chance") or 0.0):
            continue
        qmin = max(1, int(entry.get("quantity_min") or 1))
        qmax = max(qmin, int(entry.get("quantity_max") or qmin))
        qty = random.randint(qmin, qmax)
        rolled.append(
            {
                "item_key": entry.get("item_key"),
                "weapon_key": entry.get("weapon_key"),
                "consumable_key": entry.get("consumable_key"),
                "quantity": qty,
            }
        )
    return rolled


def roll_gold_drop(enemy_key: str) -> int:
    """
    Roll gold reward for an enemy from its loot table range.
    Returns 0 when enemy/table missing or range is empty.
    """
    ek = str(enemy_key or "").strip()
    if not ek:
        return 0
    try:
        with _conn() as conn:
            row = conn.execute(
                """
                SELECT t.gold_min, t.gold_max
                FROM game_config_enemies e
                JOIN game_config_loot_tables t ON t.key = e.loot_table_key
                WHERE e.key = ? AND t.is_active = 1
                LIMIT 1
                """,
                (ek,),
            ).fetchone()
    except sqlite3.Error:
        # Backward compatibility with DBs created before gold columns existed.
        return 0
    if not row:
        return 0
    gmin = max(0, int(row["gold_min"] or 0))
    gmax = max(0, int(row["gold_max"] or 0))
    if gmax <= 0:
        return 0
    if gmax < gmin:
        gmax = gmin
    return random.randint(gmin, gmax)


def _starter_durability(conn: sqlite3.Connection, key: str, item_type: str) -> int | None:
    """U16/#467 — initial durability for a weapon/armor when it enters inventory.

    Activates the (previously dormant) durability mechanic: every granted weapon/armor
    starts at full durability so it can wear down in combat and be repaired. Value =
    per-item `durability_base` from config when set, else rarity-based DEFAULT_DURABILITY
    (1→100, 2→150, 3→200). Returns None for non-gear (consumables/quest items stay untracked).
    """
    if item_type not in ("weapon", "armor"):
        return None
    from app.services.durability_service import DEFAULT_DURABILITY
    rarity = 1
    base: int | None = None
    try:
        r = conn.execute(
            "SELECT rarity, weapon_data FROM game_items WHERE key = ? AND is_active = 1",
            (str(key),),
        ).fetchone()
        if r:
            rarity = int(_rget(r, "rarity") or 1)
            wd_raw = _rget(r, "weapon_data")
            if item_type == "weapon" and wd_raw:
                try:
                    wd = json.loads(wd_raw or "{}")
                    if wd.get("durability_base"):
                        base = int(wd["durability_base"])
                except Exception:
                    pass
    except Exception:
        pass
    if base is None and item_type == "weapon":
        try:
            r2 = conn.execute(
                "SELECT durability_base, rarity FROM game_config_weapons WHERE key = ?",
                (str(key),),
            ).fetchone()
            if r2:
                if _rget(r2, "durability_base"):
                    base = int(r2["durability_base"])
                rarity = int(_rget(r2, "rarity") or rarity)
        except Exception:
            pass
    if base is None:
        base = DEFAULT_DURABILITY.get(max(1, min(3, rarity)), 100)
    return base


def _resolve_game_item_key(conn: sqlite3.Connection, key: str) -> str | None:
    """#573: map a catalog key to the unified game_items key (same namespace after the
    U11a backfill). Returns the key when it exists in game_items, else None."""
    k = str(key or "").strip()
    if not k:
        return None
    try:
        row = conn.execute(
            "SELECT 1 FROM game_items WHERE key = ? AND COALESCE(is_active, 1) = 1 LIMIT 1",
            (k,),
        ).fetchone()
    except sqlite3.Error:
        return None
    return k if row else None


def grant_loot_to_character(
    character_id: int,
    loot_items: list[dict],
    source: str = "loot",
    loot_tier: str | None = None,
    is_boss_kill: bool = False,
) -> list[dict]:
    """
    Grant rolled loot to character inventory with catalog validation.
    Item/consumable stack by key; weapons are always inserted as separate rows.

    F2 (#462): if loot_tier is provided, rolls affixes for each weapon row
    and writes them to affixes_json.

    U25 (#575): when is_boss_kill=True, applies the affix pity timer — after
    BOSS_DROP_PITY_THRESHOLD boss kills without an affixed weapon, the next weapon
    drop is guaranteed an affix; a boss kill that yields no affix bumps the counter.
    """
    cid = int(character_id)
    if not isinstance(loot_items, list):
        return []

    src = str(source or "loot").strip() or "loot"
    granted: list[dict] = []
    with _conn() as conn:
        ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not ch:
            raise ValueError("character not found")

        # U25 (#575): boss-drop pity — decide once whether this kill forces an affix.
        force_affix = False
        weapon_got_affix = False
        if is_boss_kill:
            from app.services import affix_pity_service
            force_affix = affix_pity_service.boss_drop_guaranteed(conn, cid)

        for raw in loot_items:
            if not isinstance(raw, dict):
                continue
            qty = max(1, int(raw.get("quantity") or 1))
            cat = _catalog_entry(conn, raw)
            if not cat:
                logger.warning("loot_catalog_key_missing", character_id=cid, loot_item=raw)
                continue
            key, label, item_type = cat
            dur = _starter_durability(conn, key, item_type)
            new_inventory_id: int | None = None
            _gik_row_id: int | None = None
            if item_type == "weapon":
                if loot_tier or force_affix:
                    affix_keys = roll_weapon_affixes(loot_tier, conn, force_min_one=force_affix)
                else:
                    affix_keys = []
                if affix_keys:
                    weapon_got_affix = True
                    force_affix = False  # guarantee consumed by the first weapon
                cur = conn.execute(
                    """
                    INSERT INTO character_inventory
                    (character_id, item_key, weapon_key, consumable_key, quantity, equipped, slot, source, meta_json, affixes_json, durability_current, durability_max)
                    VALUES (?, NULL, ?, NULL, ?, 0, NULL, ?, NULL, ?, ?, ?)
                    """,
                    (cid, key, qty, src, json.dumps(affix_keys), dur, dur),
                )
                new_inventory_id = cur.lastrowid
            elif item_type == "armor":
                # Armor is durable equipment — separate row (no stacking) so durability is per-piece.
                cur = conn.execute(
                    """
                    INSERT INTO character_inventory
                    (character_id, item_key, weapon_key, consumable_key, quantity, equipped, slot, source, meta_json, durability_current, durability_max)
                    VALUES (?, ?, NULL, NULL, ?, 0, NULL, ?, NULL, ?, ?)
                    """,
                    (cid, key, qty, src, dur, dur),
                )
                new_inventory_id = cur.lastrowid
            else:
                # 8H: wszystkie wiersze z game_config_items (w tym consumable) stackują po item_key
                existing = conn.execute(
                    """
                    SELECT id, quantity FROM character_inventory
                    WHERE character_id = ? AND item_key = ? AND weapon_key IS NULL AND consumable_key IS NULL
                    ORDER BY id ASC LIMIT 1
                    """,
                    (cid, key),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE character_inventory SET quantity = ? WHERE id = ?",
                        (int(existing["quantity"] or 0) + qty, int(existing["id"])),
                    )
                    _gik_row_id = int(existing["id"])
                else:
                    cur = conn.execute(
                        """
                        INSERT INTO character_inventory
                        (character_id, item_key, weapon_key, consumable_key, quantity, equipped, slot, source, meta_json)
                        VALUES (?, ?, NULL, NULL, ?, 0, NULL, ?, NULL)
                        """,
                        (cid, key, qty, src),
                    )
                    _gik_row_id = cur.lastrowid

            # #573: populate the unified FK so inventory points at game_items going forward.
            # (separate from new_inventory_id, which stays weapon/armor-only for the U17 drop card)
            _row_id = new_inventory_id if new_inventory_id is not None else _gik_row_id
            gik = _resolve_game_item_key(conn, key)
            if _row_id is not None and gik:
                conn.execute(
                    "UPDATE character_inventory SET game_item_key = ? "
                    "WHERE id = ? AND game_item_key IS NULL",
                    (gik, int(_row_id)),
                )

            entry = {"label": label, "item_type": item_type, "quantity": qty, "source": src, "key": key}
            # U17 (#565): weapon/armor rows expose their new inventory_id so callers
            # (post-combat loot claim) can build a drop-comparison celebration card.
            if new_inventory_id is not None:
                entry["inventory_id"] = int(new_inventory_id)
            granted.append(entry)

        # U25 (#575): record the boss kill outcome — reset on affix, bump on miss
        # (including a boss kill that dropped no weapon at all).
        if is_boss_kill:
            from app.services import affix_pity_service
            affix_pity_service.record_boss_drop(conn, cid, got_affix=weapon_got_affix)

        conn.commit()
    return granted


def backfill_missing_durability() -> int:
    """U16/#467 — one-time data fix: give existing weapons/armor that were granted
    before durability init their full durability. Touches only rows with NULL
    durability_max so it is idempotent. Returns the number of rows updated.
    """
    updated = 0
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, weapon_key, item_key FROM character_inventory
            WHERE durability_max IS NULL
              AND (weapon_key IS NOT NULL OR item_key IS NOT NULL)
            """,
        ).fetchall()
        for r in rows:
            if r["weapon_key"]:
                key, item_type = r["weapon_key"], "weapon"
            elif r["item_key"] and r["item_key"] != "__narrative__":
                # Only real armor gets durability; other items stay untracked.
                it = conn.execute(
                    "SELECT kind FROM game_items WHERE key = ? AND is_active = 1", (r["item_key"],)
                ).fetchone()
                if not it or str(_rget(it, "kind") or "").lower() != "armor":
                    continue
                key, item_type = r["item_key"], "armor"
            else:
                continue
            dur = _starter_durability(conn, key, item_type)
            if dur:
                conn.execute(
                    "UPDATE character_inventory SET durability_current = ?, durability_max = ? WHERE id = ?",
                    (dur, dur, int(r["id"])),
                )
                updated += 1
        conn.commit()
    return updated


def preview_loot_items(loot_items: list[dict], source: str = "loot") -> list[dict]:
    """
    Validate/normalize loot payload against catalogs without writing inventory.
    Returns the same display contract as grant_loot_to_character.
    """
    if not isinstance(loot_items, list):
        return []
    src = str(source or "loot").strip() or "loot"
    out: list[dict] = []
    with _conn() as conn:
        for raw in loot_items:
            if not isinstance(raw, dict):
                continue
            qty = max(1, int(raw.get("quantity") or 1))
            cat = _catalog_entry(conn, raw)
            if not cat:
                continue
            key, label, item_type = cat
            out.append({"label": label, "item_type": item_type, "quantity": qty, "source": src, "key": key})
    return out


def get_character_inventory(character_id: int) -> list[dict]:
    """Return unified inventory rows for a character."""
    cid = int(character_id)
    with _conn() as conn:
        ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not ch:
            raise ValueError("character not found")
        # U11b (#557): game_items ma effect_json top-level i json_extract dla effect_type/dice
        try:
            rows = conn.execute(
                _inventory_rows_sql(
                    "gi.effect_json AS gi_effect_json",
                    "gi.effect_type AS gi_effect_type",
                    "gi.effect_dice AS gi_effect_dice",
                ),
                (cid,),
            ).fetchall()
        except sqlite3.OperationalError:
            # Fallback: testowe bazy bez game_items. Próbuj z effect_type/dice, potem bez.
            try:
                rows = conn.execute(_inventory_rows_sql_legacy(), (cid,)).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(_inventory_rows_sql_legacy_minimal(), (cid,)).fetchall()
        # U16 (#564): trwałość per wiersz — osobne zapytanie, żeby nie ruszać kruchego
        # builder'a SQL powyżej. Bazy testowe bez kolumn → pusty słownik (brak trwałości).
        durability_by_id: dict[int, tuple] = {}
        try:
            for d in conn.execute(
                "SELECT id, durability_current, durability_max FROM character_inventory WHERE character_id = ?",
                (cid,),
            ).fetchall():
                durability_by_id[int(d["id"])] = (d["durability_current"], d["durability_max"])
        except sqlite3.OperationalError:
            durability_by_id = {}

    from app.services.durability_service import durability_view

    out: list[dict] = []
    for r in rows:
        # T46: Narrative item — label stored directly, no catalog key.
        # item_key may be '__narrative__' sentinel (satisfies inv_xor CHECK constraint).
        narrative_label = r["narrative_label"] if "narrative_label" in r.keys() else None
        if narrative_label and r["item_key"] in (None, "__narrative__") and not r["weapon_key"] and not r["consumable_key"]:
            try:
                meta = json.loads(r["ci_meta_json"] or "{}") if "ci_meta_json" in r.keys() else {}
            except Exception:
                meta = {}
            item_type = str(meta.get("item_type") or "narrative").strip().lower() or "narrative"
            out.append({
                "id": int(r["id"]),
                "slot": None,
                "equipped": 0,
                "quantity": int(r["quantity"] or 1),
                "source": r["source"],
                "acquired_at": r["acquired_at"],
                "label": narrative_label,
                "item_type": item_type,
                "key": None,
                "can_use": False,
                "description": meta.get("description"),
                "is_narrative": True,
            })
            continue
        if r["weapon_key"]:
            label = str(r["weapon_label"] or r["weapon_key"])
            item_type = "weapon"
            key = r["weapon_key"]
        elif r["consumable_key"]:
            label = str(r["consumable_label"] or r["consumable_key"])
            item_type = "consumable"
            key = r["consumable_catalog_item_key"] or r["consumable_key"]
        else:
            raw_kind = str(r["item_kind"] or "item").strip().lower()
            label = str(r["item_label"] or r["item_key"])
            key = r["item_key"]
            # Legacy consumables table OR catalog effect_type → consumable (fixes wrong item_type on unified catalog rows).
            legacy = legacy_effect_fields_from_json(r["gi_effect_json"]) or {}
            et = str(legacy.get("effect_type") or r["gi_effect_type"] or "").strip().lower()
            dice = str(legacy.get("effect_dice") or r["gi_effect_dice"] or "").strip()
            if r["consumable_catalog_item_key"]:
                item_type = "consumable"
                clab = r["consumable_by_item_key_label"]
                if clab:
                    label = str(clab)
            elif et in _CONSUMABLE_EFFECT_SIGNAL:
                item_type = "consumable"
            elif raw_kind == "quest" and dice:
                # Mis-tagged elixirs/potions still stored as quest; dice + consumable-like row → treat as consumable.
                item_type = "consumable"
            else:
                item_type = raw_kind or "item"
        # Stage 5 E4: surface armor_coverage + the list of slots a full-coverage
        # anchor row is locking, so the frontend can render limb cards as "covered".
        armor_coverage_raw = None
        weapon_slot_raw = None
        try:
            armor_coverage_raw = r["gi_armor_coverage"]
        except (KeyError, IndexError):
            pass
        try:
            weapon_slot_raw = r["gw_weapon_slot"]
        except (KeyError, IndexError):
            pass
        coverage = (armor_coverage_raw or "").lower() if item_type == "armor" else None
        wslot = (weapon_slot_raw or "").lower() if item_type == "weapon" else None
        covered_slots: list[str] = []
        if item_type == "armor" and int(r["equipped"] or 0) == 1 and coverage == "full":
            covered_slots = list(_ARMOR_COVERAGE_TO_SLOTS["full"])
        # Two-handed weapon: anchor at main_hand but also lock off_hand visually.
        if item_type == "weapon" and int(r["equipped"] or 0) == 1 and wslot == "two_handed":
            covered_slots = ["main_hand", "off_hand"]
        dur_cur, dur_max = durability_by_id.get(int(r["id"]), (None, None))
        out.append(
            {
                "id": int(r["id"]),
                "slot": r["slot"],
                "equipped": int(r["equipped"] or 0),
                "quantity": int(r["quantity"] or 0),
                "source": r["source"],
                "acquired_at": r["acquired_at"],
                "label": label,
                "item_type": item_type,
                "key": key,
                "can_use": item_type == "consumable",
                "armor_coverage": coverage,
                "weapon_slot": wslot,
                "covered_slots": covered_slots,
                "durability": durability_view(dur_cur, dur_max),
            }
        )
    return out


def _rget(row: sqlite3.Row, col: str, default: Any = None) -> Any:
    try:
        return row[col] if col in row.keys() else default
    except (KeyError, IndexError):
        return default


def _resolve_affixes(affix_keys: list, conn: sqlite3.Connection) -> list:
    """Resolve affix key list → [{key, name, effects}] for display in item-detail modal."""
    if not affix_keys:
        return []
    result = []
    for key in affix_keys:
        row = conn.execute(
            "SELECT key, name, effect_json FROM game_config_affixes WHERE key = ?", (key,)
        ).fetchone()
        if not row:
            result.append({"key": key, "name": key, "effects": []})
            continue
        try:
            ej = json.loads(_rget(row, "effect_json") or "null")
            effects = ej.get("effects", []) if isinstance(ej, dict) else (ej if isinstance(ej, list) else [])
        except Exception:
            effects = []
        result.append({"key": key, "name": _rget(row, "name") or key, "effects": effects})
    return result


def get_inventory_item_detail(character_id: int, inventory_id: int) -> dict:
    """D5 (#380) — full detail for one inventory entry, for the item-view modal.

    Resolves the character_inventory row to its catalog (weapon/consumable/item)
    and returns common fields (name, description, type, value, quantity, equipped)
    plus kind-specific blocks: weapon{damage_die,linked_stat,...},
    armor{ac_bonus,coverage}, consumable{effect_*}. Narrative items fall back to
    the stored label + meta description. Raises ValueError if not found.
    """
    cid = int(character_id)
    iid = int(inventory_id)
    with _conn() as conn:
        ci = conn.execute(
            "SELECT * FROM character_inventory WHERE id = ? AND character_id = ?",
            (iid, cid),
        ).fetchone()
        if not ci:
            raise ValueError("inventory item not found")
        from app.services.durability_service import durability_view
        _dur = durability_view(_rget(ci, "durability_current"), _rget(ci, "durability_max"))
        base = {
            "id": iid,
            "quantity": int(_rget(ci, "quantity", 1) or 1),
            "equipped": int(_rget(ci, "equipped", 0) or 0),
        }

        # Parse affixes from inventory row (F2 #462 — only weapons can have affixes)
        try:
            raw_affixes = json.loads(_rget(ci, "affixes_json") or "[]")
            affix_keys = raw_affixes if isinstance(raw_affixes, list) else []
        except Exception:
            affix_keys = []

        # Weapon
        if _rget(ci, "weapon_key"):
            wkey = ci["weapon_key"]
            w = conn.execute(
                "SELECT * FROM game_config_weapons WHERE key = ?", (wkey,)
            ).fetchone()
            affixes = _resolve_affixes(affix_keys, conn)
            if w:
                return {
                    **base, "kind": "weapon", "item_type": "weapon",
                    "name": _rget(w, "label") or wkey,
                    "description": _rget(w, "description"),
                    "value_gp": int(_rget(w, "value_gp", 0) or 0),
                    "note": _rget(w, "note"),
                    "weapon": {
                        "damage_die": _rget(w, "damage_die"),
                        "linked_stat": _rget(w, "linked_stat"),
                        "weapon_type": _rget(w, "weapon_type"),
                        "attack_bonus": int(_rget(w, "attack_bonus", 0) or 0),
                    },
                    "affixes": affixes,
                    "durability": _dur,
                }
            return {
                **base, "kind": "weapon", "item_type": "weapon",
                "name": _rget(ci, "label") or wkey, "description": None, "weapon": {},
                "affixes": affixes,
                "durability": _dur,
            }

        # Consumable
        if _rget(ci, "consumable_key"):
            ckey = ci["consumable_key"]
            c = conn.execute(
                "SELECT * FROM game_config_consumables WHERE key = ?", (ckey,)
            ).fetchone()
            if c:
                return {
                    **base, "kind": "consumable", "item_type": "consumable",
                    "name": _rget(c, "label") or ckey,
                    "description": _rget(c, "description"),
                    "value_gp": int(_rget(c, "base_price", 0) or 0),
                    "note": _rget(c, "note"),
                    "consumable": {
                        "effect_type": _rget(c, "effect_type"),
                        "effect_dice": _rget(c, "effect_dice"),
                        "effect_bonus": int(_rget(c, "effect_bonus", 0) or 0),
                        "effect_target": _rget(c, "effect_target"),
                    },
                }

        # Catalog item (incl. armor)
        ikey = _rget(ci, "item_key")
        if ikey and ikey != "__narrative__":
            it = conn.execute(
                "SELECT * FROM game_config_items WHERE key = ?", (ikey,)
            ).fetchone()
            if it:
                item_type = str(_rget(it, "item_type") or "item").strip().lower() or "item"
                detail = {
                    **base, "kind": item_type, "item_type": item_type,
                    "name": _rget(it, "label") or ikey,
                    "description": _rget(it, "description"),
                    "value_gp": int(_rget(it, "value_gp", 0) or 0),
                    "note": _rget(it, "note"),
                }
                if item_type == "armor":
                    detail["armor"] = {
                        "ac_bonus": int(_rget(it, "ac_bonus", 0) or 0),
                        "coverage": _rget(it, "armor_coverage"),
                    }
                    detail["durability"] = _dur
                if _rget(it, "effect_type"):
                    detail["consumable"] = {
                        "effect_type": _rget(it, "effect_type"),
                        "effect_dice": _rget(it, "effect_dice"),
                        "effect_bonus": int(_rget(it, "effect_bonus", 0) or 0),
                        "effect_target": _rget(it, "effect_target"),
                    }
                return detail

        # Narrative fallback
        try:
            meta = json.loads(_rget(ci, "meta_json") or "{}")
        except Exception:
            meta = {}
        return {
            **base, "kind": "narrative",
            "item_type": str(meta.get("item_type") or "narrative"),
            "name": _rget(ci, "label") or "Przedmiot",
            "description": meta.get("description"),
            "is_narrative": True,
        }


# ─── U17 (#565): celebracja dropu afiksowego + porównanie z założonym ─────────
# Mechanika LICZY porównanie dropu z aktualnym sprzętem; LLM tylko narruje (Zasada 1-5).

_RARITY_LABELS = {1: "common", 2: "rare", 3: "epic"}

_ARMOR_COVERAGE_TO_SUGGESTED_SLOT = {
    "head": "head",
    "torso": "torso",
    "full": "torso",
    "limb_arm": "l_arm",
    "limb_leg": "l_leg",
}


def dice_average(dice_str: Any) -> float:
    """Deterministyczna średnia rzutu typu '1d8+2' (BEZ losowania) — do porównania broni.

    Średnia kości k = (sides+1)/2; '2d6+2' → 2*3.5 + 2 = 9.0. Zwraca 0.0 przy złym zapisie.
    Osobno od mechanic_resolver.parse_dice (tamten faktycznie losuje wynik ataku).
    """
    try:
        s = str(dice_str or "").strip().lower()
        if not s:
            return 0.0
        bonus = 0
        if "+" in s:
            s, b = s.split("+", 1)
            bonus = int(b.strip())
        elif "-" in s and "d" in s:
            i = s.rindex("-")
            bonus = -int(s[i + 1:])
            s = s[:i]
        s = s.strip()
        if "d" in s:
            count_str, sides_str = s.split("d", 1)
            count = int(count_str or 1)
            sides = int(sides_str)
            return round(count * (sides + 1) / 2.0 + bonus, 2)
        return float(int(s) + bonus)
    except Exception:
        return 0.0


def _affix_stat_bonus(detail: dict, effect_type: str) -> int:
    """Suma płaskich wartości danego typu efektu (damage_bonus/ac_bonus) ze wszystkich afiksów."""
    total = 0
    for affix in (detail.get("affixes") or []):
        for eff in (affix.get("effects") or []):
            if isinstance(eff, dict) and str(eff.get("type") or "").strip().lower() == effect_type:
                try:
                    total += int(eff.get("value") or 0)
                except (TypeError, ValueError):
                    continue
    return total


def item_combat_metrics(detail: dict | None) -> dict:
    """Redukuje blok item-detail do liczb porównywalnych: broń {damage, attack_bonus}, zbroja {ac}.

    Uwzględnia bonusy z afiksów (damage_bonus do broni, ac_bonus do zbroi).
    """
    if not detail:
        return {}
    it = str(detail.get("item_type") or detail.get("kind") or "").strip().lower()
    if it == "weapon":
        w = detail.get("weapon") or {}
        dmg = dice_average(w.get("damage_die")) + _affix_stat_bonus(detail, "damage_bonus")
        return {
            "item_type": "weapon",
            "damage": round(dmg, 1),
            "attack_bonus": int(w.get("attack_bonus") or 0),
        }
    if it == "armor":
        a = detail.get("armor") or {}
        ac = int(a.get("ac_bonus") or 0) + _affix_stat_bonus(detail, "ac_bonus")
        return {"item_type": "armor", "ac": ac}
    return {"item_type": it}


def compare_item_metrics(new_detail: dict | None, equipped_detail: dict | None) -> dict:
    """Podpisany diff dropu vs aktualnie założony przedmiot (dodatni = lepszy drop).

    Bez założonego przedmiotu → diff wartości None (frontend pokaże 'brak porównania').
    """
    new_m = item_combat_metrics(new_detail)
    eq_m = item_combat_metrics(equipped_detail) if equipped_detail else {}
    diff: dict[str, Any] = {}
    for k in ("damage", "attack_bonus", "ac"):
        if k in new_m:
            if equipped_detail:
                diff[k] = round((new_m.get(k) or 0) - (eq_m.get(k) or 0), 1)
            else:
                diff[k] = None
    return {"new": new_m, "equipped": (eq_m or None), "diff": diff}


def suggested_slot_for_item(detail: dict | None) -> str | None:
    """Slot na który gracz najpewniej chce założyć drop (broń→main_hand, zbroja wg coverage)."""
    if not detail:
        return None
    it = str(detail.get("item_type") or detail.get("kind") or "").strip().lower()
    if it == "weapon":
        return "main_hand"
    if it == "armor":
        cov = str((detail.get("armor") or {}).get("coverage") or "").strip().lower()
        return _ARMOR_COVERAGE_TO_SUGGESTED_SLOT.get(cov, "torso")
    return None


def rarity_label(rarity: Any) -> str:
    """1→common, 2→rare, 3→epic (domyślnie common)."""
    try:
        return _RARITY_LABELS.get(int(rarity or 1), "common")
    except (TypeError, ValueError):
        return "common"


def is_special_drop(rarity: Any, affixes: list | None) -> bool:
    """Czy drop zasługuje na kartę celebracji: ma afiks LUB rarity >= 2 (rare+)."""
    if affixes:
        return True
    try:
        return int(rarity or 1) >= 2
    except (TypeError, ValueError):
        return False


def _inventory_item_rarity(conn: sqlite3.Connection, character_id: int, inventory_id: int) -> int:
    """Rzadkość dropu z katalogu game_items (po kluczu broni/przedmiotu z wiersza inwentarza)."""
    r = conn.execute(
        "SELECT weapon_key, item_key FROM character_inventory WHERE id = ? AND character_id = ?",
        (int(inventory_id), int(character_id)),
    ).fetchone()
    if not r:
        return 1
    key = _rget(r, "weapon_key") or _rget(r, "item_key")
    if not key:
        return 1
    try:
        g = conn.execute(
            "SELECT rarity FROM game_items WHERE key = ? AND is_active = 1 LIMIT 1",
            (str(key),),
        ).fetchone()
        if g and _rget(g, "rarity") is not None:
            return int(_rget(g, "rarity") or 1)
    except sqlite3.OperationalError:
        pass
    return 1


def _equipped_detail_for_slot(conn: sqlite3.Connection, character_id: int, slot: str | None) -> dict | None:
    """Detal przedmiotu aktualnie założonego na danym slocie (albo None)."""
    if not slot:
        return None
    row = conn.execute(
        "SELECT id FROM character_inventory WHERE character_id = ? AND equipped = 1 AND slot = ? LIMIT 1",
        (int(character_id), str(slot)),
    ).fetchone()
    if not row:
        return None
    try:
        return get_inventory_item_detail(character_id, int(_rget(row, "id")))
    except ValueError:
        return None


def build_drop_comparison(character_id: int, inventory_id: int) -> dict | None:
    """U17 (#565) — dane karty celebracji dla świeżo zdobytej broni/zbroi:
    rzadkość, afiksy, podpisany diff statów vs przedmiot założony na docelowym slocie,
    sugerowany slot do założenia. Zwraca None dla nie-sprzętu (mikstury/questowe).
    """
    new_detail = get_inventory_item_detail(character_id, inventory_id)
    it = str(new_detail.get("item_type") or "").strip().lower()
    if it not in ("weapon", "armor"):
        return None
    slot = suggested_slot_for_item(new_detail)
    affixes = new_detail.get("affixes") or []
    with _conn() as conn:
        rarity = _inventory_item_rarity(conn, character_id, inventory_id)
        equipped_detail = _equipped_detail_for_slot(conn, character_id, slot)
    cmp = compare_item_metrics(new_detail, equipped_detail)
    return {
        "inventory_id": int(inventory_id),
        "name": new_detail.get("name"),
        "item_type": it,
        "rarity": int(rarity),
        "rarity_label": rarity_label(rarity),
        "is_special": is_special_drop(rarity, affixes),
        "suggested_slot": slot,
        "affixes": [
            {"name": a.get("name"), "effects": a.get("effects") or []}
            for a in affixes
        ],
        **cmp,
    }


def _damage_enemy_in_combat(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
    damage_expr: str,
) -> tuple[int | None, list | None]:
    """Apply damage_expr to the first alive enemy in active_combat. Returns (damage_dealt, combatants) or (None, None) if no active combat."""
    try:
        row = conn.execute(
            "SELECT id, combatants FROM active_combat WHERE campaign_id = ? AND character_id = ? AND status = 'active' LIMIT 1",
            (int(campaign_id), int(character_id)),
        ).fetchone()
    except sqlite3.OperationalError:
        return None, None
    if not row:
        return None, None
    try:
        combatants = json.loads(row["combatants"] or "[]")
    except Exception:
        return None, None
    if not isinstance(combatants, list):
        return None, None

    rolled = _roll_dice_value(damage_expr) if damage_expr.strip() else 1
    rolled = max(1, int(rolled))

    target = next(
        (c for c in combatants if isinstance(c, dict) and c.get("id") != "player" and int(c.get("hp_current", 0)) > 0),
        None,
    )
    if not target:
        return rolled, combatants

    before_hp = int(target.get("hp_current", 0))
    target["hp_current"] = max(0, before_hp - rolled)
    conn.execute(
        "UPDATE active_combat SET combatants = ?, updated_at = datetime('now') WHERE id = ?",
        (json.dumps(combatants, ensure_ascii=False), int(row["id"])),
    )
    return rolled, combatants


def _apply_condition_to_enemy_in_combat(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
    condition_key: str,
    cond_row: sqlite3.Row,
    source_item_key: str,
) -> bool:
    """Apply a condition to the first alive enemy in active_combat. Returns True if applied."""
    try:
        row = conn.execute(
            "SELECT id, combatants FROM active_combat WHERE campaign_id = ? AND character_id = ? AND status = 'active' LIMIT 1",
            (int(campaign_id), int(character_id)),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if not row:
        return False
    try:
        combatants = json.loads(row["combatants"] or "[]")
    except Exception:
        return False
    if not isinstance(combatants, list):
        return False

    target = next(
        (c for c in combatants if isinstance(c, dict) and c.get("id") != "player" and int(c.get("hp_current", 0)) > 0),
        None,
    )
    if not target:
        return False

    enemy_conditions = target.get("conditions") or []
    if not isinstance(enemy_conditions, list):
        enemy_conditions = []
    already = any(str(c.get("key") or "").strip().lower() == condition_key for c in enemy_conditions)
    if not already:
        enemy_conditions.append({
            "key": str(cond_row["key"]),
            "label": str(cond_row["label"] or cond_row["key"]),
            "effect_json": cond_row["effect_json"],
            "source_item_key": source_item_key,
            "applied_at": "inventory_use",
        })
        target["conditions"] = enemy_conditions
        conn.execute(
            "UPDATE active_combat SET combatants = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(combatants, ensure_ascii=False), int(row["id"])),
        )
    return True


def use_inventory_item(character_id: int, inventory_id: int) -> dict[str, Any]:
    """Consume one inventory stack and apply supported effects to the character sheet."""
    cid = int(character_id)
    iid = int(inventory_id)
    with _conn() as conn:
        try:
            row = conn.execute(
                """
                SELECT c.id AS character_id,
                       c.campaign_id,
                       c.sheet_json,
                       ci.id AS inventory_id,
                       ci.item_key,
                       ci.weapon_key,
                       ci.consumable_key,
                       ci.quantity,
                       gi.key AS catalog_item_key,
                       gi.label AS item_label,
                       gi.item_type,
                       gi.effect_json,
                       gi.effect_type,
                       gi.effect_dice,
                       gi.effect_bonus,
                       gi.effect_target,
                       gc.key AS legacy_consumable_key,
                       gc.label AS legacy_consumable_label,
                       gc.effect_json AS legacy_effect_json,
                       gc.effect_type AS legacy_effect_type,
                       gc.effect_dice AS legacy_effect_dice,
                       gc.effect_bonus AS legacy_effect_bonus,
                       gc.effect_target AS legacy_effect_target
                FROM characters c
                JOIN character_inventory ci ON ci.character_id = c.id
                LEFT JOIN game_config_items gi ON gi.key = ci.item_key
                LEFT JOIN game_config_consumables gc
                  ON gc.key = ci.consumable_key
                     OR (ci.item_key IS NOT NULL AND gc.key = ci.item_key)
                WHERE c.id = ? AND ci.id = ?
                LIMIT 1
                """,
                (cid, iid),
            ).fetchone()
        except sqlite3.OperationalError:
            row = conn.execute(
                """
                SELECT c.id AS character_id,
                       c.campaign_id,
                       c.sheet_json,
                       ci.id AS inventory_id,
                       ci.item_key,
                       ci.weapon_key,
                       ci.consumable_key,
                       ci.quantity,
                       gi.key AS catalog_item_key,
                       gi.label AS item_label,
                       gi.item_type,
                       gi.effect_json,
                       NULL AS effect_type,
                       NULL AS effect_dice,
                       NULL AS effect_bonus,
                       NULL AS effect_target,
                       gc.key AS legacy_consumable_key,
                       gc.label AS legacy_consumable_label,
                       gc.effect_json AS legacy_effect_json,
                       gc.effect_type AS legacy_effect_type,
                       gc.effect_dice AS legacy_effect_dice,
                       gc.effect_bonus AS legacy_effect_bonus,
                       gc.effect_target AS legacy_effect_target
                FROM characters c
                JOIN character_inventory ci ON ci.character_id = c.id
                LEFT JOIN game_config_items gi ON gi.key = ci.item_key
                LEFT JOIN game_config_consumables gc
                  ON gc.key = ci.consumable_key
                     OR (ci.item_key IS NOT NULL AND gc.key = ci.item_key)
                WHERE c.id = ? AND ci.id = ?
                LIMIT 1
                """,
                (cid, iid),
            ).fetchone()
        if not row:
            ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
            if not ch:
                raise ValueError("character not found")
            raise ValueError("inventory entry not found")

        if row["weapon_key"]:
            raise ValueError("inventory item is not usable")

        catalog_key = str(row["catalog_item_key"] or row["legacy_consumable_key"] or row["item_key"] or row["consumable_key"] or "").strip()
        item_label = str(row["item_label"] or row["legacy_consumable_label"] or catalog_key or "item").strip() or "item"
        raw_item_type = str(row["item_type"] or "").strip().lower()
        if raw_item_type == "consumable" or row["legacy_consumable_key"]:
            item_type = "consumable"
        else:
            item_legacy = legacy_effect_fields_from_json(row["effect_json"]) or {}
            item_effect_type = str(item_legacy.get("effect_type") or "").strip().lower()
            legacy_effect_type = str(row["legacy_effect_type"] or "").strip().lower()
            signal = item_effect_type or legacy_effect_type
            item_type = "consumable" if signal in _CONSUMABLE_EFFECT_SIGNAL else (raw_item_type or "item")
        if item_type != "consumable":
            raise ValueError("inventory item is not usable")

        sheet = parse_character_sheet(row["sheet_json"] if "sheet_json" in row.keys() else None)
        if not isinstance(sheet, dict):
            sheet = {}
        current_hp = int(sheet.get("current_hp", 0) or 0)
        max_hp = max(1, int(sheet.get("max_hp", current_hp or 1) or (current_hp or 1)))
        current_mana = int(sheet.get("current_mana", 0) or 0)
        max_mana = max(0, int(sheet.get("max_mana", current_mana) or current_mana))
        conditions = _normalize_sheet_conditions(sheet)

        item_row: dict[str, Any] = dict(row)
        if item_row.get("legacy_consumable_key"):
            # prefer consumable's own effect_json over items table effect_json
            if item_row.get("legacy_effect_json"):
                item_row["effect_json"] = item_row["legacy_effect_json"]
            elif not item_row.get("effect_json"):
                item_row["effect_type"] = item_row.get("legacy_effect_type")
                item_row["effect_dice"] = item_row.get("legacy_effect_dice")
                item_row["effect_bonus"] = item_row.get("legacy_effect_bonus")
                item_row["effect_target"] = item_row.get("legacy_effect_target")
        effects = _effect_payloads_from_item_row(item_row) if catalog_key else []
        if not effects:
            raise ValueError("inventory item has no usable effects")

        results: list[dict[str, Any]] = []
        for effect in effects:
            effect_type = str(effect.get("type") or "").strip().lower()
            if effect_type not in _SUPPORTED_ITEM_USE_EFFECTS and effect_type != "restore_mana":
                raise ValueError("unsupported_item_effect")

            if effect_type == "heal_hp":
                value = effect.get("value", 0)
                rolled = _roll_dice_value(value) if isinstance(value, str) and value.strip() else int(value or 0)
                before = current_hp
                current_hp = max(0, min(max_hp, current_hp + int(rolled)))
                results.append({"type": "heal_hp", "amount": int(current_hp - before)})
                continue

            if effect_type == "restore_mana":
                value = effect.get("value", 0)
                rolled = _roll_dice_value(value) if isinstance(value, str) and value.strip() else int(value or 0)
                before = current_mana
                current_mana = max(0, min(max_mana, current_mana + int(rolled)))
                results.append({"type": "restore_mana", "amount": int(current_mana - before)})
                continue

            if effect_type == "remove_condition":
                condition_key = str(effect.get("condition_key") or "").strip().lower()
                if not condition_key:
                    raise ValueError("unsupported_item_effect")
                before_count = len(conditions)
                conditions = [c for c in conditions if str(c.get("key") or "").strip().lower() != condition_key]
                sheet["conditions"] = conditions
                results.append({"type": "remove_condition", "condition_key": condition_key, "removed": before_count - len(conditions)})
                continue

            if effect_type == "apply_condition":
                condition_key = str(effect.get("condition_key") or "").strip().lower()
                if not condition_key:
                    raise ValueError("unsupported_item_effect")
                cond_row = _condition_catalog_row(conn, condition_key)
                if not cond_row:
                    raise ValueError("condition_not_found")
                target_scope = str(effect.get("target") or "self").strip().lower()
                if target_scope == "enemy":
                    # Apply condition to first active enemy in active_combat
                    applied_to_enemy = _apply_condition_to_enemy_in_combat(
                        conn,
                        campaign_id=int(row["campaign_id"] or 0),
                        character_id=cid,
                        condition_key=condition_key,
                        cond_row=cond_row,
                        source_item_key=catalog_key,
                    )
                    results.append({"type": "apply_condition", "condition_key": condition_key, "target": "enemy", "applied": applied_to_enemy})
                    continue
                stackable = bool(int(cond_row["stackable"] or 0)) if "stackable" in cond_row.keys() else False
                existing_cond = next(
                    (c for c in conditions if str(c.get("key") or "").strip().lower() == condition_key),
                    None,
                )
                if existing_cond is not None:
                    if not stackable:
                        results.append({"type": "apply_condition", "condition_key": condition_key, "applied": False, "reason": "already_present"})
                        continue
                    # S9 (#604): stackable → podbij runtime.level (klamp max_level) zamiast duplikować.
                    from app.services.combat_service import _condition_level, _set_condition_level, _condition_max_level
                    cap = _condition_max_level(existing_cond)
                    _set_condition_level(existing_cond, min(cap, _condition_level(existing_cond) + 1))
                    sheet["conditions"] = conditions
                    results.append({"type": "apply_condition", "condition_key": condition_key, "applied": True, "reason": "level_bumped"})
                    continue
                conditions.append(
                    {
                        "key": str(cond_row["key"]),
                        "label": str(cond_row["label"] or cond_row["key"]),
                        "effect_json": cond_row["effect_json"],
                        "source_item_key": catalog_key,
                        "applied_at": "inventory_use",
                        "runtime": {"level": 1} if stackable else {},
                    }
                )
                sheet["conditions"] = conditions
                results.append({"type": "apply_condition", "condition_key": condition_key, "applied": True})
                continue

            if effect_type == "damage_enemy":
                value = effect.get("value", "1d4")
                damage_dealt, updated_combatants = _damage_enemy_in_combat(
                    conn,
                    campaign_id=int(row["campaign_id"] or 0),
                    character_id=cid,
                    damage_expr=str(value),
                )
                if damage_dealt is None:
                    results.append({"type": "narrative_only", "reason": "no_active_combat"})
                else:
                    results.append({"type": "damage_enemy", "damage_dealt": damage_dealt})
                continue

            if effect_type == "narrative_only":
                results.append({"type": "narrative_only"})
                continue

        sheet["current_hp"] = current_hp
        sheet["max_hp"] = max_hp
        sheet["current_mana"] = current_mana
        sheet["max_mana"] = max_mana
        sheet["conditions"] = conditions

        next_qty = int(row["quantity"] or 1) - 1
        if next_qty > 0:
            conn.execute("UPDATE character_inventory SET quantity = ? WHERE id = ?", (next_qty, iid))
        else:
            conn.execute("DELETE FROM character_inventory WHERE id = ?", (iid,))

        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), cid),
        )
        _sync_player_state_to_active_combat(
            conn,
            campaign_id=int(row["campaign_id"] or 0),
            character_id=cid,
            current_hp=current_hp,
            conditions=conditions,
        )
        conn.commit()

    return {
        "inventory_id": iid,
        "character_id": cid,
        "item": {"key": catalog_key, "label": item_label, "item_type": item_type},
        "remaining_quantity": max(0, next_qty),
        "effects_applied": results,
        "character_state": {
            "current_hp": current_hp,
            "max_hp": max_hp,
            "current_mana": current_mana,
            "max_mana": max_mana,
            "conditions": conditions,
        },
    }


def equip_item(character_id: int, inventory_id: int, slot: str) -> dict:
    """
    Equip an inventory entry on a slot, freeing whatever previously occupied
    that slot (and, for full-coverage armor, all 4 limb slots in one go).

    Coverage rules (Stage 5 E4):
    - Weapons → main_hand or off_hand (no coverage check).
    - Armor with `armor_coverage='head'` → only `slot='head'`.
    - Armor with `armor_coverage='torso'` → only `slot='torso'`.
    - Armor with `armor_coverage='limb_arm'` → caller must pass `l_arm` or `r_arm`.
    - Armor with `armor_coverage='limb_leg'` → caller must pass `l_leg` or `r_leg`.
    - Armor with `armor_coverage='full'` → row is anchored at `slot='torso'`,
      but the equip transaction also frees existing `l_arm`/`r_arm`/`l_leg`/`r_leg`
      rows. Hydration in `get_character_inventory` later reports the full row as
      occupying all 5 slots so the UI can render limb cards as "covered by full".
    """
    cid = int(character_id)
    iid = int(inventory_id)
    s = str(slot or "").strip().lower()
    # Sentinel: 'armor'/'auto' = „załóż zbroję, wylicz slot z armor_coverage" — używane przez
    # panel admina (heroes.js „Załóż") i ścieżkę cheat. Manekin gracza nie ma slotu 'armor',
    # więc generyczny slot byłby niewidoczny — tu mapujemy go na anatomiczny slot.
    auto_armor = s in ("auto", "armor")
    if not auto_armor and s not in _SLOT_VALUES:
        raise ValueError("invalid slot")

    with _conn() as conn:
        ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not ch:
            raise ValueError("character not found")

        row = conn.execute(
            """
            SELECT ci.id, ci.weapon_key, ci.item_key,
                   gi.item_type, gi.armor_coverage,
                   gw.weapon_slot AS weapon_slot
            FROM character_inventory ci
            LEFT JOIN game_config_items gi ON gi.key = ci.item_key
            LEFT JOIN game_config_weapons gw ON gw.key = ci.weapon_key
            WHERE ci.id = ? AND ci.character_id = ?
            """,
            (iid, cid),
        ).fetchone()
        if not row:
            raise ValueError("inventory entry not found")

        item_type = (row["item_type"] or "").lower()
        coverage = (row["armor_coverage"] or "").lower()
        weapon_slot_kind = (row["weapon_slot"] or "main_hand").lower()
        is_weapon = bool(row["weapon_key"]) or item_type == "weapon"
        is_armor = item_type == "armor"

        if auto_armor and not is_armor:
            raise ValueError("invalid slot")

        slots_to_free: list[str] = [s]
        anchor_slot = s

        if is_armor:
            if coverage and coverage not in _VALID_ARMOR_COVERAGE:
                raise ValueError(f"invalid armor_coverage '{coverage}'")
            if auto_armor:
                s = _auto_pick_armor_slot(conn, cid, coverage)
                anchor_slot = s
                slots_to_free = [s]
            if coverage == "head" and s != "head":
                raise ValueError("head armor can only equip to slot 'head'")
            if coverage == "torso" and s != "torso":
                raise ValueError("torso armor can only equip to slot 'torso'")
            if coverage == "limb_arm" and s not in ("l_arm", "r_arm"):
                raise ValueError("arm armor must equip to 'l_arm' or 'r_arm'")
            if coverage == "limb_leg" and s not in ("l_leg", "r_leg"):
                raise ValueError("leg armor must equip to 'l_leg' or 'r_leg'")
            if coverage == "hands" and s != "hands":
                raise ValueError("hand armor can only equip to slot 'hands'")
            if coverage == "full":
                anchor_slot = "torso"
                slots_to_free = list(_ARMOR_COVERAGE_TO_SLOTS["full"])
        elif is_weapon:
            if s not in ("main_hand", "off_hand"):
                raise ValueError("weapons can only equip to 'main_hand' or 'off_hand'")
            # Stage 5 follow-up: weapon_slot enforcement.
            if weapon_slot_kind and weapon_slot_kind not in _VALID_WEAPON_SLOT:
                raise ValueError(f"invalid weapon_slot '{weapon_slot_kind}'")
            if weapon_slot_kind == "main_hand" and s != "main_hand":
                raise ValueError("this weapon can only be equipped in main_hand")
            if weapon_slot_kind == "off_hand_only" and s != "off_hand":
                raise ValueError("this off-hand item can only be equipped in off_hand")
            if weapon_slot_kind == "two_handed":
                if s != "main_hand":
                    raise ValueError("two-handed weapons must be equipped to main_hand (they lock off_hand too)")
                # Two-handed weapons anchor to main_hand and occupy both.
                anchor_slot = "main_hand"
                slots_to_free = ["main_hand", "off_hand"]

        # Free whatever sits in any slot this equip is about to claim.
        placeholders = ",".join(["?"] * len(slots_to_free))
        params = [cid, *slots_to_free]
        conn.execute(
            f"UPDATE character_inventory SET equipped = 0, slot = NULL "
            f"WHERE character_id = ? AND slot IN ({placeholders})",
            params,
        )
        # ALSO free any existing full-coverage anchor whose locked limbs overlap
        # the target — prevents leaving phantom limbs occupied by an unequipped
        # full plate (rare, but cheap to guard).
        if is_armor and any(slot_x in slots_to_free for slot_x in ("l_arm", "r_arm", "l_leg", "r_leg", "torso")):
            conn.execute(
                """
                UPDATE character_inventory SET equipped = 0, slot = NULL
                WHERE character_id = ? AND equipped = 1 AND slot = 'torso'
                  AND id IN (
                    SELECT ci2.id FROM character_inventory ci2
                    JOIN game_config_items gi2 ON gi2.key = ci2.item_key
                    WHERE ci2.character_id = ? AND gi2.armor_coverage = 'full'
                  )
                """,
                (cid, cid),
            )

        conn.execute(
            "UPDATE character_inventory SET equipped = 1, slot = ? WHERE id = ?",
            (anchor_slot, iid),
        )
        conn.commit()

    updated = [x for x in get_character_inventory(cid) if int(x["id"]) == iid]
    if not updated:
        raise ValueError("inventory entry not found")
    return updated[0]


def unequip_item(character_id: int, inventory_id: int) -> dict:
    """Clear equipped flag and slot for one inventory row (8E-3)."""
    cid = int(character_id)
    iid = int(inventory_id)
    with _conn() as conn:
        ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not ch:
            raise ValueError("character not found")

        row = conn.execute(
            "SELECT id FROM character_inventory WHERE id = ? AND character_id = ?",
            (iid, cid),
        ).fetchone()
        if not row:
            raise ValueError("inventory entry not found")

        conn.execute(
            "UPDATE character_inventory SET equipped = 0, slot = NULL WHERE id = ? AND character_id = ?",
            (iid, cid),
        )
        conn.commit()

    updated = [x for x in get_character_inventory(cid) if int(x["id"]) == iid]
    if not updated:
        raise ValueError("inventory entry not found")
    return updated[0]


def delete_inventory_item(character_id: int, inventory_id: int, *, force: bool = False) -> dict:
    """Delete a character inventory entry (guard equipped unless force=True)."""
    cid = int(character_id)
    iid = int(inventory_id)
    with _conn() as conn:
        ch = conn.execute("SELECT id FROM characters WHERE id = ?", (cid,)).fetchone()
        if not ch:
            raise ValueError("character not found")
        row = conn.execute(
            """
            SELECT id, character_id, item_key, weapon_key, consumable_key, quantity, equipped, slot, source, acquired_at
            FROM character_inventory
            WHERE id = ? AND character_id = ?
            """,
            (iid, cid),
        ).fetchone()
        if not row:
            raise ValueError("inventory entry not found")
        if int(row["equipped"] or 0) == 1 and not force:
            raise ValueError("equipped item requires force")
        conn.execute("DELETE FROM character_inventory WHERE id = ? AND character_id = ?", (iid, cid))
        conn.commit()
    return {
        "id": int(row["id"]),
        "character_id": int(row["character_id"]),
        "item_key": row["item_key"],
        "weapon_key": row["weapon_key"],
        "consumable_key": row["consumable_key"],
        "quantity": int(row["quantity"] or 0),
        "equipped": int(row["equipped"] or 0),
        "slot": row["slot"],
        "source": row["source"],
        "acquired_at": row["acquired_at"],
    }


def list_config_items(item_type: str | None = None) -> list[dict]:
    """List game_config_items, optionally filtered by item_type."""
    t = str(item_type or "").strip().lower()
    with _conn() as conn:
        if t:
            rows = conn.execute(
                """
                SELECT key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active
                FROM game_config_items
                WHERE item_type = ?
                ORDER BY label COLLATE NOCASE ASC, key ASC
                """,
                (t,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active
                FROM game_config_items
                ORDER BY label COLLATE NOCASE ASC, key ASC
                """
            ).fetchall()
    return [
        {
            "key": r["key"],
            "label": r["label"],
            "item_type": r["item_type"],
            "description": r["description"],
            "value_gp": int(r["value_gp"] or 0),
            "weight": float(r["weight"] or 0.0),
            "weight_kg": float(r["weight_kg"] or 0.0),
            "effect_json": r["effect_json"],
            "is_active": bool(r["is_active"]),
        }
        for r in rows
    ]


def get_character_gold(character_id: int) -> int:
    """Return current gold_gp for a character (0 if column missing treated as 0)."""
    cid = int(character_id)
    with _conn() as conn:
        row = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise ValueError("character not found")
        return int(row["gold_gp"] or 0)


def apply_character_gold_delta(
    character_id: int,
    delta: int,
    reason: str | None = None,
    *,
    campaign_id: int | None = None,
) -> int:
    """
    Atomically adjust gold_gp by delta (must not go below 0).
    Stage 11 R6 — `reason` is now persisted to `character_gold_log` so the
    `gold_recent_days` resurrection mode can sum recent gains. `campaign_id`
    is used to derive the in-game day; without it, day defaults to 1 and the
    row won't be matched by a windowed lookup.
    """
    if int(delta) == 0:
        raise ValueError("delta must be non-zero")
    cid = int(character_id)
    d = int(delta)
    # U26: delegate to the central change_gold() chokepoint (mutate + journal
    # atomically). This wrapper keeps its self-contained API: opens its own
    # connection and commits.
    from app.services.economy_service import change_gold
    with _conn() as conn:
        new_g = change_gold(
            conn, cid, d, reason or "unknown", campaign_id=campaign_id,
        )
        conn.commit()
    return new_g


def get_config_item(key: str) -> dict | None:
    """Get one game_config_item by key."""
    k = str(key or "").strip()
    if not k:
        return None
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active
            FROM game_config_items
            WHERE key = ?
            """,
            (k,),
        ).fetchone()
    if not row:
        return None
    return {
        "key": row["key"],
        "label": row["label"],
        "item_type": row["item_type"],
        "description": row["description"],
        "value_gp": int(row["value_gp"] or 0),
        "weight": float(row["weight"] or 0.0),
        "weight_kg": float(row["weight_kg"] or 0.0),
        "effect_json": row["effect_json"],
        "is_active": bool(row["is_active"]),
    }
