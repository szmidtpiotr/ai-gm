import json
import re
import sqlite3
from pathlib import Path

from app.services.actor_stats import stats_for_actor, validate_stats_json


DB_PATH = "/data/ai_gm.db"

# #1382 — distinguishes "field omitted in PATCH" (leave as-is) from "field sent as
# null" (clear the override). None is a meaningful value, so it cannot be the default.
_UNSET = object()


def _normalize_rank_cost_json(raw: object) -> str | None:
    """#1382 — validate a per-skill rank cost override → canonical JSON string or None.

    Accepts a JSON string / dict / None / "". Requires a flat object of
    {rank(int>=1): cost(int>0)}. Empty object or blank → None (inherit global).
    Raises ValueError("invalid_rank_cost_json") on any malformed input so the
    endpoint can surface a 422 instead of persisting garbage.
    """
    if raw is None:
        return None
    data: object = raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            data = json.loads(s)
        except (json.JSONDecodeError, ValueError):
            raise ValueError("invalid_rank_cost_json") from None
    if not isinstance(data, dict):
        raise ValueError("invalid_rank_cost_json")
    out: dict[str, int] = {}
    for k, v in data.items():
        try:
            rank = int(k)
            cost = int(v)
        except (TypeError, ValueError):
            raise ValueError("invalid_rank_cost_json") from None
        if rank < 1 or cost <= 0:
            raise ValueError("invalid_rank_cost_json")
        out[str(rank)] = cost
    if not out:
        return None
    return json.dumps({k: out[k] for k in sorted(out, key=int)}, ensure_ascii=False)


# U10 — effect_schema.json = pojedyncze źródło prawdy formatu effect_json.
# Walidator wczytuje enumy stąd; literały poniżej to fallback gdy plik brak.
_EFFECT_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "effect_schema.json"


def _load_effect_schema() -> dict:
    try:
        return json.loads(_EFFECT_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_EFFECT_SCHEMA = _load_effect_schema()
KEY_RE = re.compile(r"^[a-z0-9_]{1,40}$")
# Akceptuje "d8", "2d6" oraz dice z modyfikatorem "2d4+2" / "1d4-1" — zgodnie z
# runtime rollerem (loot_service._roll_dice_value). U13 (#561): walidator U10 nie
# może odrzucać formatu, który silnik już obsługuje i którym seedują się mikstury.
DAMAGE_DIE_RE = re.compile(r"^\d*d\d+([+-]\d+)?$")
ALLOWED_CLASSES = {"warrior", "ranger", "scholar"}
ALLOWED_ITEM_TYPES = {"weapon", "armor", "consumable", "misc", "quest", "narrative", "relic"}
ALLOWED_WEAPON_TYPES = {"melee", "ranged", "spell"}
ALLOWED_TARGETING_TYPES = {"single", "aoe_radius"}
ALLOWED_DAMAGE_TYPES = {"physical", "magic", "fire", "poison", "misc"}
ALLOWED_TIERS = {"weak", "standard", "elite", "boss"}
ALLOWED_EFFECT_TYPES = {"heal_hp", "restore_mana", "remove_condition", "add_condition", "stat_buff", "misc"}
ALLOWED_EFFECT_TARGETS = {"self", "ally", "any"}
# Enumy effect_json — wczytane z effect_schema.json (single source); fallback gdy plik brak.
ALLOWED_EFFECT_JSON_CATEGORIES = set(_EFFECT_SCHEMA.get("categories") or {
    "character_condition",
    "gear_bonus",
    "consumable_immediate",
    "aura",
})
ALLOWED_EFFECT_JSON_TYPES = set(_EFFECT_SCHEMA.get("effect_types") or {
    "periodic_save",
    "static_stat_modifier",
    "heal_hp",
    "restore_mana",
    "apply_condition",
    "remove_condition",
    "block_action",
    "narrative_only",
    # F1 (#461) — gear combat effects (Effect Object schema)
    "damage_bonus",
    "heal_on_hit",
    "ac_bonus",
    # S8 (#603) — damage-over-time prymityw (on_fire 2d6/turę itd.)
    "dot",
    # S9 (#604) / S10 (#605) — kondycje z poziomami / narastający DOT
    "stacking_levels",
    "escalating_dot",
    # S11–S13 (#606–#608) — przerzut / dodatkowa akcja / on_expire / rzut ratunkowy przy 0 HP
    "reroll",
    "extra_action",
    "on_expire_apply",
    "on_zero_hp_save",
})
ALLOWED_EFFECT_JSON_TICKS = set(_EFFECT_SCHEMA.get("ticks") or {"start_turn", "each_round", "on_use"})
# S11 (#606) — tryby i zakresy efektu `reroll` (single source: effect_schema.json).
ALLOWED_REROLL_MODES = set(_EFFECT_SCHEMA.get("reroll_modes") or {"player_keep_best", "forced_keep_worst"})
ALLOWED_REROLL_SCOPES = set(_EFFECT_SCHEMA.get("reroll_scopes") or {"skill_test", "attack", "all"})
# S12 (#607) — rodzaje dodatkowej akcji efektu `extra_action` (single source: effect_schema.json).
ALLOWED_ACTION_KINDS = set(_EFFECT_SCHEMA.get("action_kinds") or {"move_only"})
# S13 (#608) — dozwolone skutki efektu `on_zero_hp_save` (single source: effect_schema.json).
ALLOWED_SAVE_RESULTS = set(_EFFECT_SCHEMA.get("save_results") or {"stay_at_1hp"})
# S18 (#613) — dozwolone zachowania efektu `behavior_override` (single source: effect_schema.json).
ALLOWED_BEHAVIORS = set(_EFFECT_SCHEMA.get("behaviors") or {"random_table_k4", "attack_nearest", "flee"})
# 7 statystyk (U10: LCK dodane — kontrakt 7 stat z CLAUDE.md). Porównanie po upper().
ALLOWED_EFFECT_JSON_STATS = set(_EFFECT_SCHEMA.get("stats") or {"STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"})
# U10 — cele pochodne dla static_stat_modifier (ac/attack_bonus/damage_bonus/initiative). Porównanie po lower().
ALLOWED_EFFECT_JSON_STAT_TARGETS = {
    str(s).strip().lower() for s in (_EFFECT_SCHEMA.get("stat_targets") or
    {"ac", "attack_bonus", "damage_bonus", "initiative", "save"})
}
_EFFECT_JSON_TOP_LEVEL_KEYS = set(_EFFECT_SCHEMA.get("top_level_keys") or {"schema_version", "effect_category", "effects", "cure"})
_EFFECT_JSON_EFFECT_KEYS = set(_EFFECT_SCHEMA.get("effect_keys") or {"type", "condition_key", "dc_key", "stat", "value", "tick", "expires", "duration_rounds", "damage_type", "result"})
_EFFECT_JSON_CATEGORY_TYPES = {
    cat: set(types) for cat, types in (_EFFECT_SCHEMA.get("category_types") or {
        "character_condition": {"periodic_save", "static_stat_modifier", "block_action", "narrative_only", "dot", "stacking_levels", "escalating_dot", "reroll", "extra_action", "on_expire_apply", "on_zero_hp_save", "condition_immunity", "behavior_override"},
        "gear_bonus": {"static_stat_modifier", "narrative_only", "damage_bonus", "heal_on_hit", "ac_bonus", "apply_condition"},
        "consumable_immediate": {"heal_hp", "restore_mana", "apply_condition", "remove_condition", "narrative_only"},
        "aura": {
            "periodic_save",
            "static_stat_modifier",
            "apply_condition",
            "remove_condition",
            "block_action",
            "narrative_only",
        },
    }).items()
}


def _fetch_all(query: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _fetch_one(conn: sqlite3.Connection, query: str, params: tuple) -> dict | None:
    row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def _audit(
    conn: sqlite3.Connection,
    table_name: str,
    row_key: str,
    operation: str,
    old_values: dict | None,
    new_values: dict | None,
) -> None:
    conn.execute(
        """
        INSERT INTO admin_audit_log (table_name, row_key, operation, old_values, new_values)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            table_name,
            row_key,
            operation,
            json.dumps(old_values, ensure_ascii=False) if old_values is not None else None,
            json.dumps(new_values, ensure_ascii=False) if new_values is not None else None,
        ),
    )


def _validate_key(key: str) -> str:
    k = (key or "").strip()
    if not KEY_RE.fullmatch(k):
        raise ValueError("invalid_key")
    return k


def _validate_damage_die(damage_die: str) -> str:
    d = (damage_die or "").strip().lower()
    if not DAMAGE_DIE_RE.fullmatch(d):
        raise ValueError("invalid_damage_die")
    return d


def _serialize_allowed_classes(values: list[str] | None) -> str:
    """JSON array for allowed_classes; empty or None becomes '[]'."""
    if values is None:
        return "[]"
    if not isinstance(values, list):
        raise ValueError("invalid_allowed_classes")
    if len(values) == 0:
        return "[]"
    return _validate_allowed_classes(values)


def _validate_allowed_classes(values: list[str]) -> str:
    if not isinstance(values, list) or not values:
        raise ValueError("invalid_allowed_classes")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = str(raw).strip().lower()
        if item not in ALLOWED_CLASSES:
            raise ValueError("invalid_allowed_classes")
        if item not in seen:
            normalized.append(item)
            seen.add(item)
    return json.dumps(normalized, ensure_ascii=False)


def _normalize_effect_json(effect_json: str) -> str:
    try:
        parsed = json.loads(effect_json)
    except Exception as exc:
        raise ValueError("invalid_effect_json") from exc
    errors = validate_effect_json_payload(parsed)
    if errors:
        raise ValueError("invalid_effect_json_schema")
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def validate_effect_json_payload(payload: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["effect_json must be a JSON object"]

    extra_top = sorted(set(payload.keys()) - _EFFECT_JSON_TOP_LEVEL_KEYS)
    if extra_top:
        errors.append(f"unknown top-level keys: {', '.join(extra_top)}")

    schema_version = payload.get("schema_version")
    if schema_version != 1:
        errors.append("schema_version must equal 1")

    category = str(payload.get("effect_category") or "").strip().lower()
    if category not in ALLOWED_EFFECT_JSON_CATEGORIES:
        errors.append(
            "effect_category must be one of: "
            + ", ".join(sorted(ALLOWED_EFFECT_JSON_CATEGORIES))
        )

    effects = payload.get("effects")
    if not isinstance(effects, list) or len(effects) < 1:
        errors.append("effects must be a non-empty array")
        return errors

    for idx, effect in enumerate(effects):
        prefix = f"effects[{idx}]"
        if not isinstance(effect, dict):
            errors.append(f"{prefix} must be an object")
            continue

        extra_effect_keys = sorted(set(effect.keys()) - _EFFECT_JSON_EFFECT_KEYS)
        if extra_effect_keys:
            errors.append(f"{prefix} has unknown keys: {', '.join(extra_effect_keys)}")

        effect_type = str(effect.get("type") or "").strip().lower()
        if effect_type not in ALLOWED_EFFECT_JSON_TYPES:
            errors.append(
                f"{prefix}.type must be one of: "
                + ", ".join(sorted(ALLOWED_EFFECT_JSON_TYPES))
            )
            continue

        if category in _EFFECT_JSON_CATEGORY_TYPES and effect_type not in _EFFECT_JSON_CATEGORY_TYPES[category]:
            errors.append(f"{prefix}.type={effect_type} is not allowed for effect_category={category}")

        condition_key = effect.get("condition_key")
        if condition_key is not None and not KEY_RE.fullmatch(str(condition_key).strip().lower()):
            errors.append(f"{prefix}.condition_key must be lowercase_snake_case")

        dc_key = effect.get("dc_key")
        if dc_key is not None and not KEY_RE.fullmatch(str(dc_key).strip().lower()):
            errors.append(f"{prefix}.dc_key must be lowercase_snake_case")

        stat = effect.get("stat")
        if stat is not None:
            raw_stat = str(stat).strip()
            # Bazowe statystyki porównujemy po upper(), cele pochodne po lower().
            if raw_stat.upper() not in ALLOWED_EFFECT_JSON_STATS and raw_stat.lower() not in ALLOWED_EFFECT_JSON_STAT_TARGETS:
                allowed = sorted(ALLOWED_EFFECT_JSON_STATS) + sorted(ALLOWED_EFFECT_JSON_STAT_TARGETS)
                errors.append(f"{prefix}.stat must be one of: {', '.join(allowed)}")

        tick = effect.get("tick")
        if tick is not None:
            tick_norm = str(tick).strip().lower()
            if tick_norm not in ALLOWED_EFFECT_JSON_TICKS:
                errors.append(f"{prefix}.tick must be one of: {', '.join(sorted(ALLOWED_EFFECT_JSON_TICKS))}")

        expires = effect.get("expires")
        if expires is not None:
            expires_norm = str(expires).strip().lower()
            if expires_norm not in {"save_success", "manual"}:
                if not expires_norm.startswith("duration_rounds:"):
                    errors.append(
                        f"{prefix}.expires must be save_success, manual, or duration_rounds:N"
                    )
                else:
                    rounds_str = expires_norm.split(":", 1)[1].strip()
                    if not rounds_str.isdigit() or int(rounds_str) < 1:
                        errors.append(f"{prefix}.expires duration_rounds must be >= 1")

        skill = effect.get("skill")
        if skill is not None and not KEY_RE.fullmatch(str(skill).strip().lower()):
            errors.append(f"{prefix}.skill must be lowercase_snake_case")

        value = effect.get("value")
        if effect_type == "static_stat_modifier":
            if not isinstance(value, (int, float)):
                errors.append(f"{prefix}.value must be a number for static_stat_modifier")
            if stat is None:
                errors.append(f"{prefix}.stat is required for static_stat_modifier")
        elif effect_type == "static_skill_modifier":
            # #1302 — passive skill bonus from equipped gear (relic grants a skill).
            if not isinstance(value, (int, float)):
                errors.append(f"{prefix}.value must be a number for static_skill_modifier")
            if not skill or not str(skill).strip():
                errors.append(f"{prefix}.skill is required for static_skill_modifier")
        elif effect_type in {"heal_hp", "restore_mana"}:
            if not isinstance(value, (int, float, str)):
                errors.append(f"{prefix}.value must be a number or dice string for {effect_type}")
            elif isinstance(value, str):
                dice = value.strip().lower()
                if not dice or not DAMAGE_DIE_RE.fullmatch(dice):
                    errors.append(f"{prefix}.value must be a number or dice string like 2d4 for {effect_type}")
        elif effect_type in {"apply_condition", "remove_condition"}:
            if not condition_key or not str(condition_key).strip():
                errors.append(f"{prefix}.condition_key is required for {effect_type}")
        elif effect_type == "periodic_save":
            if tick is None:
                errors.append(f"{prefix}.tick is required for periodic_save")
            if expires is None:
                errors.append(f"{prefix}.expires is required for periodic_save")
            if dc_key is None and not isinstance(value, (int, float)):
                errors.append(f"{prefix} requires dc_key or numeric value for periodic_save")
        elif effect_type == "dot":
            # S8 (#603) — damage-over-time: value = liczba lub dice ("2d6"); tick wymagany.
            if not isinstance(value, (int, float, str)):
                errors.append(f"{prefix}.value must be a number or dice string for dot")
            elif isinstance(value, str):
                dice = value.strip().lower()
                if not dice or not DAMAGE_DIE_RE.fullmatch(dice):
                    errors.append(f"{prefix}.value must be a number or dice string like 2d6 for dot")
            if tick is None:
                errors.append(f"{prefix}.tick is required for dot")
            damage_type = effect.get("damage_type")
            if damage_type is not None and str(damage_type).strip().lower() not in ALLOWED_DAMAGE_TYPES:
                errors.append(f"{prefix}.damage_type must be one of: {', '.join(sorted(ALLOWED_DAMAGE_TYPES))}")
        elif effect_type == "escalating_dot":
            # S10 (#605) — DOT narastający w czasie (np. hemorrhage 1d4/turę, +1d4 co 3 tury).
            # value = kość startowa (liczba lub dice), escalate_every_rounds = int ≥ 1,
            # escalate_dice = dice przyrostu, tick wymagany.
            if not isinstance(value, (int, float, str)):
                errors.append(f"{prefix}.value must be a number or dice string for escalating_dot")
            elif isinstance(value, str):
                dice = value.strip().lower()
                if not dice or not DAMAGE_DIE_RE.fullmatch(dice):
                    errors.append(f"{prefix}.value must be a number or dice string like 1d4 for escalating_dot")
            every = effect.get("escalate_every_rounds")
            if not isinstance(every, int) or isinstance(every, bool) or every < 1:
                errors.append(f"{prefix}.escalate_every_rounds must be an integer >= 1 for escalating_dot")
            esc_dice = effect.get("escalate_dice")
            if not isinstance(esc_dice, str) or not DAMAGE_DIE_RE.fullmatch(str(esc_dice).strip().lower()):
                errors.append(f"{prefix}.escalate_dice must be a dice string like 1d4 for escalating_dot")
            if tick is None:
                errors.append(f"{prefix}.tick is required for escalating_dot")
            damage_type = effect.get("damage_type")
            if damage_type is not None and str(damage_type).strip().lower() not in ALLOWED_DAMAGE_TYPES:
                errors.append(f"{prefix}.damage_type must be one of: {', '.join(sorted(ALLOWED_DAMAGE_TYPES))}")
        elif effect_type == "stacking_levels":
            # S9 (#604) — kondycja z poziomami (np. exhausted): max_level + per_level_effects
            # (skalowane ×poziom) + opcjonalne threshold_effects {poziom: efekt}.
            max_level = effect.get("max_level")
            if not isinstance(max_level, int) or isinstance(max_level, bool) or max_level < 1:
                errors.append(f"{prefix}.max_level must be an integer >= 1 for stacking_levels")
            ple = effect.get("per_level_effects")
            if not isinstance(ple, list) or len(ple) < 1:
                errors.append(f"{prefix}.per_level_effects must be a non-empty array for stacking_levels")
            else:
                for j, sub in enumerate(ple):
                    errors.extend(_validate_stacking_sub_effect(sub, f"{prefix}.per_level_effects[{j}]"))
            thr = effect.get("threshold_effects")
            if thr is not None:
                if not isinstance(thr, dict):
                    errors.append(f"{prefix}.threshold_effects must be an object {{level: effect}}")
                else:
                    for lvl_key, sub in thr.items():
                        if not str(lvl_key).isdigit() or int(lvl_key) < 1:
                            errors.append(f"{prefix}.threshold_effects keys must be positive integers")
                        errors.extend(_validate_stacking_sub_effect(sub, f"{prefix}.threshold_effects[{lvl_key}]"))
        elif effect_type == "reroll":
            # S11 (#606) — przerzut testu: mode (player_keep_best/forced_keep_worst) wymagany,
            # scope (skill_test/attack/all) opcjonalny (domyślnie skill_test), uses ≥ 0 opcjonalne.
            mode = effect.get("mode")
            if str(mode or "").strip().lower() not in ALLOWED_REROLL_MODES:
                errors.append(
                    f"{prefix}.mode must be one of: " + ", ".join(sorted(ALLOWED_REROLL_MODES))
                    + " for reroll"
                )
            scope = effect.get("scope")
            if scope is not None and str(scope).strip().lower() not in ALLOWED_REROLL_SCOPES:
                errors.append(
                    f"{prefix}.scope must be one of: " + ", ".join(sorted(ALLOWED_REROLL_SCOPES))
                    + " for reroll"
                )
            uses = effect.get("uses")
            if uses is not None and (not isinstance(uses, int) or isinstance(uses, bool) or uses < 0):
                errors.append(f"{prefix}.uses must be an integer >= 0 for reroll")
        elif effect_type == "extra_action":
            # S12 (#607) — dodatkowa akcja w turze (np. hasted): action_kind opcjonalny
            # (domyślnie move_only — jedyny dozwolony na start; pełna akcja ataku odłożona).
            action_kind = effect.get("action_kind")
            if action_kind is not None and str(action_kind).strip().lower() not in ALLOWED_ACTION_KINDS:
                errors.append(
                    f"{prefix}.action_kind must be one of: " + ", ".join(sorted(ALLOWED_ACTION_KINDS))
                    + " for extra_action"
                )
        elif effect_type == "on_expire_apply":
            # S12 (#607) — przy wygaśnięciu kondycji nakłada inną (np. hasted→exhausted):
            # condition_key wymagany, value = poziom (opcjonalny int ≥ 1, domyślnie 1).
            if not condition_key or not str(condition_key).strip():
                errors.append(f"{prefix}.condition_key is required for on_expire_apply")
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
                errors.append(f"{prefix}.value must be an integer >= 1 for on_expire_apply")
        elif effect_type == "on_zero_hp_save":
            # S13 (#608) — rzut ratunkowy gdy HP spadłoby do ≤0 (np. blessed CON DC 12 → 1 HP):
            # stat wymagany, DC z dc_key lub numerycznego value, result z enuma save_results,
            # uses opcjonalny int ≥ 1 (domyślnie 1).
            if stat is None:
                errors.append(f"{prefix}.stat is required for on_zero_hp_save")
            if dc_key is None and not isinstance(value, (int, float)):
                errors.append(f"{prefix} requires dc_key or numeric value (DC) for on_zero_hp_save")
            result = effect.get("result")
            if result is not None and str(result).strip().lower() not in ALLOWED_SAVE_RESULTS:
                errors.append(
                    f"{prefix}.result must be one of: " + ", ".join(sorted(ALLOWED_SAVE_RESULTS))
                    + " for on_zero_hp_save"
                )
            uses = effect.get("uses")
            if uses is not None and (not isinstance(uses, int) or isinstance(uses, bool) or uses < 1):
                errors.append(f"{prefix}.uses must be an integer >= 1 for on_zero_hp_save")
        elif effect_type == "condition_immunity":
            # S14 (#609) — odporność na kondycje: immune_to = niepusta lista kluczy kondycji
            # (lowercase_snake_case). Aktor z aktywną kondycją niosącą ten efekt nie przyjmuje
            # kondycji z listy; nałożenie kondycji z immune_to zdejmuje już aktywne wpisy z listy.
            immune_to = effect.get("immune_to")
            if not isinstance(immune_to, list) or len(immune_to) < 1:
                errors.append(f"{prefix}.immune_to must be a non-empty array of condition keys for condition_immunity")
            else:
                for k in immune_to:
                    if not isinstance(k, str) or not KEY_RE.fullmatch(k.strip().lower()):
                        errors.append(f"{prefix}.immune_to entries must be lowercase_snake_case condition keys")
        elif effect_type == "behavior_override":
            # S18 (#613) — kondycja steruje turą aktora: behavior z enuma (random_table_k4 =
            # k4 1 stoi/2 atak losowego celu/3 ucieczka/4 normalnie; attack_nearest = atak
            # najbliższego niezależnie od frakcji; flee = ucieczka/zmiana strefy).
            behavior = effect.get("behavior")
            if str(behavior or "").strip().lower() not in ALLOWED_BEHAVIORS:
                errors.append(
                    f"{prefix}.behavior must be one of: " + ", ".join(sorted(ALLOWED_BEHAVIORS))
                    + " for behavior_override"
                )
        elif effect_type == "untargetable":
            # S19 (#614) — aktor pomijany przy wyborze celu (np. hidden). Bez dodatkowych pól.
            pass
        elif effect_type == "ambush_bonus":
            # S19 (#614) — +Nk6 do pierwszego ataku z ukrycia (value = kość lub liczba), konsumuje kondycję.
            if not isinstance(value, (int, float, str)) or isinstance(value, bool):
                errors.append(f"{prefix}.value must be a number or dice string for ambush_bonus")
            elif isinstance(value, str):
                dice = value.strip().lower()
                if not dice or not DAMAGE_DIE_RE.fullmatch(dice):
                    errors.append(f"{prefix}.value must be a number or dice string like 2d6 for ambush_bonus")
        elif effect_type in {"block_action", "narrative_only"}:
            pass
        elif effect_type in {"damage_bonus", "heal_on_hit", "ac_bonus"}:
            if not isinstance(value, (int, float)):
                errors.append(f"{prefix}.value must be a number for {effect_type}")

    # S10 (#605) — opcjonalny top-level `cure: {skill, dc}` na kondycji: deklaratywne
    # "udany SKILL_TEST tym skillem zdejmuje kondycję" (DC z zamka {8,12,16,20,24}).
    cure = payload.get("cure")
    if cure is not None:
        if not isinstance(cure, dict):
            errors.append("cure must be an object {skill, dc}")
        else:
            extra_cure = sorted(set(cure.keys()) - {"skill", "dc"})
            if extra_cure:
                errors.append(f"cure has unknown keys: {', '.join(extra_cure)}")
            cure_skill = cure.get("skill")
            if not isinstance(cure_skill, str) or not KEY_RE.fullmatch(cure_skill.strip().lower()):
                errors.append("cure.skill must be a lowercase_snake_case skill key")
            cure_dc = cure.get("dc")
            if cure_dc not in {8, 12, 16, 20, 24}:
                errors.append("cure.dc must be one of the locked DC values: 8, 12, 16, 20, 24")

    # S14 (#609) — opcjonalny top-level `broken_by: [klucz, ...]` na kondycji: nałożenie
    # którejkolwiek z tych kondycji na nosiciela natychmiast zdejmuje tę kondycję
    # (np. rage broken_by [stunned, confused]).
    broken_by = payload.get("broken_by")
    if broken_by is not None:
        if not isinstance(broken_by, list) or len(broken_by) < 1:
            errors.append("broken_by must be a non-empty array of condition keys")
        else:
            for k in broken_by:
                if not isinstance(k, str) or not KEY_RE.fullmatch(k.strip().lower()):
                    errors.append("broken_by entries must be lowercase_snake_case condition keys")

    # S19 (#614) — opcjonalny top-level `granted_by: {skill, dc}` na kondycji: ODWROTNOŚĆ `cure`.
    # Udany SKILL_TEST tym skillem NAKŁADA kondycję (np. hidden granted_by stealth DC 14).
    # DC z zamka {8,12,16,20,24} — mechanika decyduje, nie LLM.
    granted_by = payload.get("granted_by")
    if granted_by is not None:
        if not isinstance(granted_by, dict):
            errors.append("granted_by must be an object {skill, dc}")
        else:
            extra_gb = sorted(set(granted_by.keys()) - {"skill", "dc"})
            if extra_gb:
                errors.append(f"granted_by has unknown keys: {', '.join(extra_gb)}")
            gb_skill = granted_by.get("skill")
            if not isinstance(gb_skill, str) or not KEY_RE.fullmatch(gb_skill.strip().lower()):
                errors.append("granted_by.skill must be a lowercase_snake_case skill key")
            gb_dc = granted_by.get("dc")
            # DC progu skradania — int ≥ 1. NIE jest zamknięte do skali {8,12,16,20,24}: design doc
            # FAZY S używa progów pośrednich (np. stealth/save DC 14, jak periodic_save w S18).
            if not isinstance(gb_dc, int) or isinstance(gb_dc, bool) or gb_dc < 1:
                errors.append("granted_by.dc must be an integer >= 1")

    # S19 (#614) — opcjonalny top-level `detect_dc`: DC rzutu WIS wroga przy aktywnym poszukiwaniu
    # ukrytego gracza (untargetable). Liczba całkowita ≥ 1.
    detect_dc = payload.get("detect_dc")
    if detect_dc is not None and (not isinstance(detect_dc, int) or isinstance(detect_dc, bool) or detect_dc < 1):
        errors.append("detect_dc must be an integer >= 1")

    return errors


def _validate_stacking_sub_effect(sub: object, prefix: str) -> list[str]:
    """S9 (#604) — minimalna walidacja efektu zagnieżdżonego w stacking_levels.
    Wspierane: static_stat_modifier (per_level) i block_action (threshold)."""
    errs: list[str] = []
    if not isinstance(sub, dict):
        return [f"{prefix} must be an object"]
    sub_type = str(sub.get("type") or "").strip().lower()
    if sub_type == "static_stat_modifier":
        if sub.get("stat") is None:
            errs.append(f"{prefix}.stat is required for static_stat_modifier")
        elif str(sub.get("stat")).strip().upper() not in ALLOWED_EFFECT_JSON_STATS \
                and str(sub.get("stat")).strip().lower() not in ALLOWED_EFFECT_JSON_STAT_TARGETS:
            errs.append(f"{prefix}.stat is not a valid stat")
        if not isinstance(sub.get("value"), (int, float)) or isinstance(sub.get("value"), bool):
            errs.append(f"{prefix}.value must be a number for static_stat_modifier")
    elif sub_type in {"block_action", "narrative_only"}:
        pass
    else:
        errs.append(f"{prefix}.type must be static_stat_modifier, block_action or narrative_only")
    return errs


def normalize_effect_json_value(effect_json: object) -> str:
    if isinstance(effect_json, str):
        return _normalize_effect_json(effect_json)
    try:
        errors = validate_effect_json_payload(effect_json)
        if errors:
            raise ValueError("invalid_effect_json_schema")
        return json.dumps(effect_json, ensure_ascii=False, separators=(",", ":"))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("invalid_effect_json") from exc


def _validate_item_type(item_type: str) -> str:
    t = (item_type or "").strip().lower()
    if t not in ALLOWED_ITEM_TYPES:
        raise ValueError("invalid_item_type")
    return t


def _validate_weapon_type(v: str) -> str:
    t = (v or "").strip().lower()
    if t not in ALLOWED_WEAPON_TYPES:
        raise ValueError("invalid_weapon_type")
    return t


def _validate_targeting(v: str) -> str:
    t = (v or "").strip().lower()
    if t not in ALLOWED_TARGETING_TYPES:
        raise ValueError("invalid_targeting")
    return t


def _normalize_magic_school(v: str | None) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if len(s) > 80:
        raise ValueError("invalid_magic_school")
    return s


def _validate_targeting_fields(targeting: str, aoe_radius_m: float | None) -> tuple[str, float | None]:
    t = _validate_targeting(targeting)
    if t == "single":
        return t, None
    if aoe_radius_m is None:
        raise ValueError("invalid_aoe_radius_m")
    r = float(aoe_radius_m)
    if not (r > 0):
        raise ValueError("invalid_aoe_radius_m")
    return t, r


def _validate_damage_type(v: str) -> str:
    t = (v or "").strip().lower()
    if t not in ALLOWED_DAMAGE_TYPES:
        raise ValueError("invalid_damage_type")
    return t


def _validate_tier(v: str) -> str:
    t = (v or "").strip().lower()
    if t not in ALLOWED_TIERS:
        raise ValueError("invalid_tier")
    return t


def _validate_drop_chance(v: float | None, *, current: float | None = None) -> float:
    if v is None:
        return float(current if current is not None else 1.0)
    x = float(v)
    if x < 0.0 or x > 1.0 or x != x:  # NaN
        raise ValueError("invalid_drop_chance")
    return x


def _validate_effect_type(v: str) -> str:
    t = (v or "").strip().lower()
    if t not in ALLOWED_EFFECT_TYPES:
        raise ValueError("invalid_effect_type")
    return t


def _validate_effect_target(v: str) -> str:
    t = (v or "").strip().lower()
    if t not in ALLOWED_EFFECT_TARGETS:
        raise ValueError("invalid_effect_target")
    return t


def _validate_proficiency_classes(values: list[str] | None) -> str:
    """DEPRECATED 8H — alias for allowed_classes; kept for backward compat with older callers."""
    if values is None:
        raise ValueError("invalid_proficiency_classes")
    if len(values) == 0:
        return "[]"
    return _validate_allowed_classes(values)


def _validate_conditions_immune(values: list[str] | None) -> str:
    if values is None:
        return "[]"
    if not isinstance(values, list):
        raise ValueError("invalid_conditions_immune")
    out: list[str] = []
    for raw in values:
        k = str(raw).strip().lower()
        if not KEY_RE.fullmatch(k):
            raise ValueError("invalid_conditions_immune")
        out.append(k)
    return json.dumps(out, ensure_ascii=False)


def _validate_enemy_skills_json(values: dict[str, int] | None) -> str:
    if values is None:
        return "{}"
    if not isinstance(values, dict):
        raise ValueError("invalid_skills_json")
    out: dict[str, int] = {}
    for raw_k, raw_v in values.items():
        k = str(raw_k).strip().lower()
        if not KEY_RE.fullmatch(k):
            raise ValueError("invalid_skills_json")
        try:
            out[k] = int(raw_v)
        except (TypeError, ValueError):
            raise ValueError("invalid_skills_json") from None
    return json.dumps(out, ensure_ascii=False)


def _validate_effect_dice(effect_dice: str | None) -> str | None:
    if effect_dice is None or not str(effect_dice).strip():
        return None
    return _validate_damage_die(str(effect_dice))


def _normalize_item_row(row: dict) -> dict:
    """Audit-friendly dict: bool is_active, allowed_classes as list."""
    out = dict(row)
    out["is_active"] = bool(out.get("is_active", 1))
    raw_ac = out.get("allowed_classes")
    if isinstance(raw_ac, str):
        try:
            out["allowed_classes"] = json.loads(raw_ac or "[]")
        except Exception:
            out["allowed_classes"] = []
    elif raw_ac is None and "proficiency_classes" in out:
        try:
            out["allowed_classes"] = json.loads(out.get("proficiency_classes") or "[]")
        except Exception:
            out["allowed_classes"] = []
        out.pop("proficiency_classes", None)
    elif raw_ac is None:
        out["allowed_classes"] = []
    return out


def _legacy_effect_fields_from_json(effect_json: object) -> dict[str, object]:
    from app.services.effect_json_migration import legacy_effect_fields_from_json

    legacy = legacy_effect_fields_from_json(effect_json) or {}
    return {
        "effect_type": legacy.get("effect_type"),
        "effect_dice": legacy.get("effect_dice"),
        "effect_bonus": int(legacy.get("effect_bonus") or 0),
        "effect_target": str(legacy.get("effect_target") or "self"),
    }


def _normalize_legacy_item_effect_json(
    *,
    current_effect_json: str | None,
    effect_type: str | None,
    effect_dice: str | None,
    effect_bonus: int | None,
    effect_target: str | None,
) -> str | None:
    from app.services.effect_json_migration import normalize_flat_effect_to_json

    if effect_type is None and effect_dice is None and effect_bonus is None and effect_target is None:
        return current_effect_json

    current = _legacy_effect_fields_from_json(current_effect_json)
    if effect_type is not None:
        current["effect_type"] = str(effect_type).strip().lower() or None
    if effect_dice is not None:
        current["effect_dice"] = _validate_effect_dice(effect_dice) if str(effect_dice).strip() else None
    if effect_bonus is not None:
        current["effect_bonus"] = int(effect_bonus)
    if effect_target is not None:
        current["effect_target"] = str(effect_target).strip().lower() or "self"

    if not current.get("effect_type"):
        return None

    normalized = normalize_flat_effect_to_json(
        current.get("effect_type"),
        current.get("effect_dice"),
        current.get("effect_bonus"),
        current.get("effect_target"),
    )
    if normalized:
        return normalized
    raise ValueError("legacy_effect_requires_effect_json")


def list_stats() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, description, sort_order, locked_at
        FROM game_config_stats
        ORDER BY sort_order ASC, key ASC
        """
    )


def list_skills() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at, description, trigger_keywords, rank_cost_json
        FROM game_config_skills
        ORDER BY sort_order ASC, key ASC
        """
    )


def list_dc() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, value, sort_order, locked_at, description
        FROM game_config_dc
        ORDER BY sort_order ASC, key ASC
        """
    )


def list_xp_rewards() -> list[dict]:
    """[T12 / S10e] Katalog nagród XP."""
    try:
        return _fetch_all(
            """
            SELECT key, category, label, description, xp_amount, is_active,
                   sort_order, locked_at, created_at, updated_at
            FROM game_config_xp_rewards
            ORDER BY category ASC, sort_order ASC, key ASC
            """
        )
    except sqlite3.OperationalError:
        return []


def list_xp_awards() -> list[dict]:
    """XP award events (game_config_xp_awards) — read-only catalog for admin view."""
    try:
        return _fetch_all(
            """
            SELECT id, category, source_key, label, description, xp_amount,
                   is_active, is_locked, locked_at, created_at, updated_at
            FROM game_config_xp_awards
            ORDER BY category ASC, source_key ASC
            """
        )
    except sqlite3.OperationalError:
        return []


def update_xp_award(award_id: int, *, xp_amount: int | None, is_active: int | None) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT id, category, source_key, label, description, xp_amount,
                   is_active, is_locked, locked_at, created_at, updated_at
            FROM game_config_xp_awards WHERE id = ?
            """,
            (award_id,),
        )
        if not current:
            raise KeyError("not_found")
        new_amount = int(xp_amount) if xp_amount is not None else int(current["xp_amount"] or 0)
        if new_amount < 0:
            raise ValueError("invalid_xp_amount")
        new_active = int(is_active) if is_active is not None else int(current["is_active"] or 1)
        conn.execute(
            "UPDATE game_config_xp_awards SET xp_amount = ?, is_active = ?, updated_at = datetime('now') WHERE id = ?",
            (new_amount, new_active, award_id),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT id, category, source_key, label, description, xp_amount,
                   is_active, is_locked, locked_at, created_at, updated_at
            FROM game_config_xp_awards WHERE id = ?
            """,
            (award_id,),
        )
        _audit(conn, "game_config_xp_awards", str(award_id), "UPDATE", current, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_xp_reward(
    key: str,
    *,
    label: str | None,
    description: str | None,
    xp_amount: int | None,
    is_active: int | None,
    sort_order: int | None,
    force: bool,
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, category, label, description, xp_amount, is_active,
                   sort_order, locked_at, created_at, updated_at
            FROM game_config_xp_rewards WHERE key = ?
            """,
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        new_amount = (
            int(xp_amount) if xp_amount is not None else int(current["xp_amount"] or 0)
        )
        if new_amount < 0:
            raise ValueError("invalid_xp_amount")

        updates = {
            "label": label if label is not None else current["label"],
            "description": description if description is not None else current.get("description"),
            "xp_amount": new_amount,
            "is_active": int(is_active) if is_active is not None else int(current["is_active"] or 1),
            "sort_order": (
                int(sort_order) if sort_order is not None else int(current["sort_order"] or 0)
            ),
        }
        conn.execute(
            """
            UPDATE game_config_xp_rewards
            SET label = ?, description = ?, xp_amount = ?, is_active = ?, sort_order = ?,
                updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                updates["label"],
                updates["description"],
                updates["xp_amount"],
                updates["is_active"],
                updates["sort_order"],
                key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, category, label, description, xp_amount, is_active,
                   sort_order, locked_at, created_at, updated_at
            FROM game_config_xp_rewards WHERE key = ?
            """,
            (key,),
        )
        _audit(conn, "game_config_xp_rewards", key, "UPDATE", current, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def list_affixes() -> list[dict]:
    """F2 (#462): affix catalog (game_config_affixes) with typed Effect Objects."""
    try:
        rows = _fetch_all(
            """
            SELECT key, name, tier, allowed_item_types, effect_json, is_active,
                   created_at, updated_at
            FROM game_config_affixes
            ORDER BY tier ASC, key ASC
            """
        )
    except sqlite3.OperationalError:
        return []
    for row in rows:
        row["is_active"] = bool(row.get("is_active"))
    return rows


def create_affix(
    *,
    key: str,
    name: str,
    tier: int = 1,
    allowed_item_types: str = "weapon",
    effect_json: str | None = None,
    is_active: bool = True,
) -> dict:
    """F3 (#463): create a new affix record in game_config_affixes."""
    k = _validate_key(key)
    n = (name or "").strip()
    if not n:
        raise ValueError("invalid_name")
    t = int(tier) if tier is not None else 1
    if t < 1 or t > 5:
        raise ValueError("invalid_tier")
    # validate effect_json if provided
    if effect_json is not None:
        raw = effect_json if isinstance(effect_json, str) else json.dumps(effect_json)
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raise ValueError("invalid_effect_json")
        errs = validate_effect_json_payload(parsed)
        if errs:
            raise ValueError("invalid_effect_json")
        effect_json = raw
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = conn.execute("SELECT key FROM game_config_affixes WHERE key=?", (k,)).fetchone()
        if existing:
            raise ValueError("affix_exists")
        conn.execute(
            """
            INSERT INTO game_config_affixes (key, name, tier, allowed_item_types, effect_json, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (k, n, t, allowed_item_types or "weapon", effect_json, 1 if is_active else 0),
        )
        _audit(conn, "game_config_affixes", k, "INSERT", None, {
            "key": k, "name": n, "tier": t, "allowed_item_types": allowed_item_types,
            "effect_json": effect_json, "is_active": is_active,
        })
        conn.commit()
        row = conn.execute(
            "SELECT key, name, tier, allowed_item_types, effect_json, is_active, created_at, updated_at FROM game_config_affixes WHERE key=?",
            (k,),
        ).fetchone()
        result = dict(row)
        result["is_active"] = bool(result.get("is_active"))
        return result
    finally:
        conn.close()


def update_affix(
    key: str,
    *,
    name: str | None = None,
    tier: int | None = None,
    allowed_item_types: str | None = None,
    effect_json: str | None = None,
    is_active: bool | None = None,
) -> dict:
    """F3 (#463): patch an existing affix record."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        old = conn.execute(
            "SELECT key, name, tier, allowed_item_types, effect_json, is_active FROM game_config_affixes WHERE key=?",
            (key,),
        ).fetchone()
        if not old:
            raise KeyError(key)
        updates: list[str] = []
        params: list = []
        if name is not None:
            n = name.strip()
            if not n:
                raise ValueError("invalid_name")
            updates.append("name=?"); params.append(n)
        if tier is not None:
            t = int(tier)
            if t < 1 or t > 5:
                raise ValueError("invalid_tier")
            updates.append("tier=?"); params.append(t)
        if allowed_item_types is not None:
            updates.append("allowed_item_types=?"); params.append(allowed_item_types)
        if effect_json is not None:
            raw = effect_json if isinstance(effect_json, str) else json.dumps(effect_json)
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                raise ValueError("invalid_effect_json")
            errs = validate_effect_json_payload(parsed)
            if errs:
                raise ValueError("invalid_effect_json")
            updates.append("effect_json=?"); params.append(raw)
        if is_active is not None:
            updates.append("is_active=?"); params.append(1 if is_active else 0)
        if updates:
            updates.append("updated_at=datetime('now')")
            params.append(key)
            conn.execute(f"UPDATE game_config_affixes SET {', '.join(updates)} WHERE key=?", params)
            _audit(conn, "game_config_affixes", key, "UPDATE", dict(old), None)
            conn.commit()
        row = conn.execute(
            "SELECT key, name, tier, allowed_item_types, effect_json, is_active, created_at, updated_at FROM game_config_affixes WHERE key=?",
            (key,),
        ).fetchone()
        result = dict(row)
        result["is_active"] = bool(result.get("is_active"))
        return result
    finally:
        conn.close()


def delete_affix(key: str) -> None:
    """F3 (#463): remove an affix from game_config_affixes."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        old = conn.execute("SELECT key FROM game_config_affixes WHERE key=?", (key,)).fetchone()
        if not old:
            raise KeyError(key)
        _audit(conn, "game_config_affixes", key, "DELETE", {"key": key}, None)
        conn.execute("DELETE FROM game_config_affixes WHERE key=?", (key,))
        conn.commit()
    finally:
        conn.close()


def list_weapons() -> list[dict]:
    rows = _fetch_all(
        """
        SELECT key, label, damage_die, weapon_type, linked_stat, allowed_classes,
               two_handed, finesse, light, range_m, targeting, aoe_radius_m, magic_school, value_gp, weight_kg,
               ammo_key,
               description, note, effect_json, source_exclusive, weapon_slot,
               is_active, locked_at, created_at, updated_at,
               image_url, image_gen_prompt,
               COALESCE(campaign_id, NULL) AS campaign_id,
               COALESCE(review_status, 'permanent') AS review_status
        FROM game_config_weapons
        WHERE COALESCE(review_status, 'permanent') = 'permanent' OR is_active = 0
        ORDER BY key ASC
        """
    )
    for row in rows:
        raw_ac = row.get("allowed_classes") or "[]"
        try:
            row["allowed_classes"] = json.loads(raw_ac)
        except (json.JSONDecodeError, TypeError):
            row["allowed_classes"] = [s.strip() for s in str(raw_ac).split(",") if s.strip()]
        row["two_handed"] = bool(row.get("two_handed"))
        row["finesse"] = bool(row.get("finesse"))
    return rows


def list_enemies() -> list[dict]:
    rows = _fetch_all(
        """
        SELECT key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
               tier, attacks_per_turn, damage_bonus, damage_type,
               xp_award, conditions_immune, skills_json, stats_json, loot_table_key, drop_chance, note,
               description, is_active, locked_at, created_at, updated_at, loot_tier,
               image_url, image_url_raw, image_gen_prompt,
               COALESCE(min_level, 1) AS min_level, max_level,
               terrain_tags, world_scope, review_status
        FROM game_config_enemies
        ORDER BY key ASC
        """
    )
    for row in rows:
        try:
            row["conditions_immune"] = json.loads(row.get("conditions_immune") or "[]")
        except Exception:
            row["conditions_immune"] = []
        try:
            parsed_sk = json.loads(row.get("skills_json") or "{}")
            row["skills_json"] = parsed_sk if isinstance(parsed_sk, dict) else {}
        except Exception:
            row["skills_json"] = {}
        try:
            parsed_st = json.loads(row.get("stats_json") or "{}")
            row["stats_json"] = parsed_st if isinstance(parsed_st, dict) else {}
        except Exception:
            row["stats_json"] = {}
        if row.get("drop_chance") is None:
            row["drop_chance"] = 1.0
        else:
            row["drop_chance"] = float(row["drop_chance"])
    return rows


def list_conditions() -> list[dict]:
    rows = _fetch_all(
        """
        SELECT key, label, effect_json, description, is_active, stackable, auto_remove,
               locked_at, created_at, updated_at
        FROM game_config_conditions
        ORDER BY key ASC
        """
    )
    for row in rows:
        row["stackable"] = bool(row.get("stackable"))
    return rows


def update_stat(
    key: str,
    *,
    label: str | None,
    description: str | None,
    sort_order: int | None,
    force: bool,
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            "SELECT key, label, description, sort_order, locked_at FROM game_config_stats WHERE key = ?",
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        updates = {
            "label": label if label is not None else current["label"],
            "description": description if description is not None else current["description"],
            "sort_order": sort_order if sort_order is not None else current["sort_order"],
        }
        conn.execute(
            """
            UPDATE game_config_stats
            SET label = ?, description = ?, sort_order = ?
            WHERE key = ?
            """,
            (updates["label"], updates["description"], updates["sort_order"], key),
        )
        new_row = _fetch_one(
            conn,
            "SELECT key, label, description, sort_order, locked_at FROM game_config_stats WHERE key = ?",
            (key,),
        )
        _audit(conn, "game_config_stats", key, "UPDATE", current, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_skill(
    key: str,
    *,
    label: str | None,
    linked_stat: str | None,
    rank_ceiling: int | None,
    sort_order: int | None,
    description: str | None,
    trigger_keywords: str | None = None,
    rank_cost_json: object = _UNSET,
    force: bool,
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at, description, trigger_keywords, rank_cost_json
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        final_linked_stat = linked_stat if linked_stat is not None else current["linked_stat"]
        stat_exists = _fetch_one(conn, "SELECT key FROM game_config_stats WHERE key = ?", (final_linked_stat,))
        if not stat_exists:
            raise ValueError("invalid_linked_stat")

        final_rank = rank_ceiling if rank_ceiling is not None else current["rank_ceiling"]
        if final_rank < 1:
            raise ValueError("invalid_rank_ceiling")

        # #1382 — sentinel: only touch the override when the caller sends the field.
        if rank_cost_json is _UNSET:
            final_rank_cost = current.get("rank_cost_json")
        else:
            final_rank_cost = _normalize_rank_cost_json(rank_cost_json)

        updates = {
            "label": label if label is not None else current["label"],
            "linked_stat": final_linked_stat,
            "rank_ceiling": final_rank,
            "sort_order": sort_order if sort_order is not None else current["sort_order"],
            "description": description if description is not None else current.get("description"),
            "trigger_keywords": trigger_keywords if trigger_keywords is not None else current.get("trigger_keywords"),
            "rank_cost_json": final_rank_cost,
        }
        conn.execute(
            """
            UPDATE game_config_skills
            SET label = ?, linked_stat = ?, rank_ceiling = ?, sort_order = ?, description = ?, trigger_keywords = ?, rank_cost_json = ?
            WHERE key = ?
            """,
            (
                updates["label"],
                updates["linked_stat"],
                updates["rank_ceiling"],
                updates["sort_order"],
                updates["description"],
                updates["trigger_keywords"],
                updates["rank_cost_json"],
                key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at, description, trigger_keywords, rank_cost_json
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        _audit(conn, "game_config_skills", key, "UPDATE", current, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_dc(
    key: str,
    *,
    label: str | None,
    value: int | None,
    sort_order: int | None,
    description: str | None,
    force: bool,
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            "SELECT key, label, value, sort_order, locked_at, description FROM game_config_dc WHERE key = ?",
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        updates = {
            "label": label if label is not None else current["label"],
            "value": value if value is not None else current["value"],
            "sort_order": sort_order if sort_order is not None else current["sort_order"],
            "description": description if description is not None else current.get("description"),
        }
        if updates["value"] < 1:
            raise ValueError("invalid_dc_value")

        conn.execute(
            """
            UPDATE game_config_dc
            SET label = ?, value = ?, sort_order = ?, description = ?
            WHERE key = ?
            """,
            (updates["label"], updates["value"], updates["sort_order"], updates["description"], key),
        )
        new_row = _fetch_one(
            conn,
            "SELECT key, label, value, sort_order, locked_at, description FROM game_config_dc WHERE key = ?",
            (key,),
        )
        _audit(conn, "game_config_dc", key, "UPDATE", current, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def create_skill(
    *,
    key: str,
    label: str,
    linked_stat: str,
    rank_ceiling: int = 5,
    sort_order: int | None = None,
    description: str | None = None,
    trigger_keywords: str | None = None,
    rank_cost_json: object = _UNSET,
) -> dict:
    if rank_ceiling < 1:
        raise ValueError("invalid_rank_ceiling")

    # #1382 — normalize/validate override up front (raises invalid_rank_cost_json).
    norm_rank_cost = None if rank_cost_json is _UNSET else _normalize_rank_cost_json(rank_cost_json)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_skills WHERE key = ?", (key,))
        if existing:
            raise ValueError("skill_exists")

        stat_exists = _fetch_one(conn, "SELECT key FROM game_config_stats WHERE key = ?", (linked_stat,))
        if not stat_exists:
            raise ValueError("invalid_linked_stat")

        if sort_order is None:
            mx = conn.execute("SELECT COALESCE(MAX(sort_order), -1) AS m FROM game_config_skills").fetchone()
            so = int(mx["m"]) + 1
        else:
            so = int(sort_order)

        conn.execute(
            """
            INSERT INTO game_config_skills (key, label, linked_stat, rank_ceiling, sort_order, locked_at, description, trigger_keywords, rank_cost_json)
            VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (key, label, linked_stat, rank_ceiling, so, description or "", trigger_keywords, norm_rank_cost),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at, description, trigger_keywords, rank_cost_json
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        _audit(conn, "game_config_skills", key, "INSERT", None, new_row)
        # Auto-seed skill_counters with DC 12 default so new skills work in tests immediately
        try:
            conn.execute(
                """INSERT OR IGNORE INTO skill_counters (player_skill_key, counter_type, counter_key, default_dc)
                   VALUES (?, 'dc', NULL, 12)""",
                (key,),
            )
        except Exception:
            pass
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def _character_uses_skill(conn: sqlite3.Connection, skill_key: str) -> tuple[int, int | None]:
    rows = conn.execute("SELECT id, sheet_json FROM characters").fetchall()
    for row in rows:
        sheet_raw = row["sheet_json"] or "{}"
        try:
            parsed = json.loads(sheet_raw)
        except Exception:
            parsed = {}
        skills = parsed.get("skills") if isinstance(parsed, dict) else None
        if isinstance(skills, dict) and skill_key in skills:
            return row["id"], int(skills.get(skill_key) or 0)
    return 0, None


def delete_skill(key: str, *, force: bool) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        character_id, rank = _character_uses_skill(conn, key)
        if character_id:
            raise LookupError(f"skill_in_use:{character_id}:{rank}")

        conn.execute("DELETE FROM game_config_skills WHERE key = ?", (key,))
        _audit(conn, "game_config_skills", key, "DELETE", current, None)
        conn.commit()
    finally:
        conn.close()


_VALID_WEAPON_SLOT = {"main_hand", "two_handed", "off_hand_only", "either"}


def create_weapon(
    *,
    key: str,
    label: str,
    damage_die: str,
    linked_stat: str,
    allowed_classes: list[str],
    is_active: bool = True,
    description: str = "",
    weapon_type: str = "melee",
    two_handed: bool = False,
    finesse: bool = False,
    range_m: int | None = None,
    targeting: str = "single",
    aoe_radius_m: float | None = None,
    magic_school: str | None = None,
    value_gp: int = 0,
    weight_kg: float = 0.0,
    note: str | None = None,
    effect_json: str | None = None,
    weapon_slot: str | None = None,
    light: bool | None = None,
) -> dict:
    safe_key = _validate_key(key)
    safe_damage_die = _validate_damage_die(damage_die)
    safe_allowed_classes = _validate_allowed_classes(allowed_classes)
    safe_weapon_type = _validate_weapon_type(weapon_type)
    safe_targeting, safe_aoe_radius_m = _validate_targeting_fields(targeting, aoe_radius_m)
    safe_magic_school = _normalize_magic_school(magic_school)
    if int(value_gp) < 0:
        raise ValueError("invalid_value_gp")
    if weight_kg < 0:
        raise ValueError("invalid_weight_kg")

    # Stage 5 follow-up: validate weapon_slot if supplied; auto-derive from
    # two_handed boolean otherwise (back-compat). Then sync the boolean to match.
    if weapon_slot is None:
        final_weapon_slot = "two_handed" if two_handed else "main_hand"
    else:
        final_weapon_slot = str(weapon_slot).strip().lower()
        if final_weapon_slot not in _VALID_WEAPON_SLOT:
            raise ValueError("invalid_weapon_slot")
        # Keep the legacy boolean in sync with the new enum.
        two_handed = (final_weapon_slot == "two_handed")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_weapons WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("weapon_exists")
        stat_exists = _fetch_one(conn, "SELECT key FROM game_config_stats WHERE key = ?", (linked_stat,))
        if not stat_exists:
            raise ValueError("invalid_linked_stat")

        conn.execute(
            """
            INSERT INTO game_config_weapons (
                key, label, damage_die, weapon_type, linked_stat, allowed_classes,
                two_handed, finesse, light, range_m, targeting, aoe_radius_m, magic_school,
                value_gp, weight_kg, description, note, effect_json, weapon_slot,
                is_active, locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (
                safe_key,
                label,
                safe_damage_die,
                safe_weapon_type,
                linked_stat,
                safe_allowed_classes,
                1 if two_handed else 0,
                1 if finesse else 0,
                None if light is None else (1 if light else 0),
                range_m,
                safe_targeting,
                safe_aoe_radius_m,
                safe_magic_school,
                int(value_gp),
                float(weight_kg),
                description or "",
                note,
                effect_json,
                final_weapon_slot,
                1 if is_active else 0,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, damage_die, weapon_type, linked_stat, allowed_classes,
                   two_handed, finesse, light, range_m, targeting, aoe_radius_m, magic_school,
                   value_gp, weight_kg, description, note, effect_json, weapon_slot,
                   is_active, locked_at, created_at, updated_at
            FROM game_config_weapons WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["allowed_classes"] = json.loads(new_row.get("allowed_classes") or "[]")
            new_row["two_handed"] = bool(new_row.get("two_handed"))
            new_row["finesse"] = bool(new_row.get("finesse"))
        _audit(conn, "game_config_weapons", safe_key, "CREATE", None, new_row)
        # U11c dual-write: re-read legacy row → upsert game_items
        from app.services.game_items_service import sync_from_legacy
        sync_from_legacy(conn, "game_config_weapons", safe_key)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_weapon(
    key: str,
    *,
    label: str | None,
    damage_die: str | None,
    linked_stat: str | None,
    allowed_classes: list[str] | None,
    is_active: bool | None,
    force: bool,
    description: str | None = None,
    weapon_type: str | None = None,
    two_handed: bool | None = None,
    finesse: bool | None = None,
    range_m: int | None = None,
    targeting: str | None = None,
    aoe_radius_m: float | None = None,
    magic_school: str | None = None,
    value_gp: int | None = None,
    weight_kg: float | None = None,
    note: str | None = None,
    effect_json: str | None = None,
    weapon_slot: str | None = None,
    rarity: int | None = None,
    light: bool | None = None,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, damage_die, weapon_type, linked_stat, allowed_classes,
                   two_handed, finesse, light, range_m, targeting, aoe_radius_m, magic_school,
                   value_gp, weight_kg, description, note, effect_json, weapon_slot,
                   rarity, is_active, locked_at, created_at, updated_at
            FROM game_config_weapons WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        final_damage_die = _validate_damage_die(damage_die) if damage_die is not None else current["damage_die"]
        final_linked_stat = linked_stat if linked_stat is not None else current["linked_stat"]
        stat_exists = _fetch_one(conn, "SELECT key FROM game_config_stats WHERE key = ?", (final_linked_stat,))
        if not stat_exists:
            raise ValueError("invalid_linked_stat")
        final_allowed_classes = (
            _validate_allowed_classes(allowed_classes)
            if allowed_classes is not None
            else current.get("allowed_classes") or "[]"
        )
        final_is_active = (1 if is_active else 0) if is_active is not None else current.get("is_active", 1)
        final_weapon_type = (
            _validate_weapon_type(weapon_type) if weapon_type is not None else current.get("weapon_type") or "melee"
        )
        final_desc = description if description is not None else (current.get("description") or "")
        final_two = (1 if two_handed else 0) if two_handed is not None else int(current.get("two_handed", 0))
        final_finesse = (1 if finesse else 0) if finesse is not None else int(current.get("finesse", 0))
        # #1397: light może być jawnie NULL (fallback na finesse) — nie zerujemy przy braku zmiany.
        final_light = (1 if light else 0) if light is not None else current.get("light")
        if range_m is not None:
            final_range_m = int(range_m)
        else:
            final_range_m = current.get("range_m")
        final_targeting = (
            _validate_targeting(targeting) if targeting is not None else str(current.get("targeting") or "single")
        )
        if aoe_radius_m is not None:
            final_aoe_radius_m = float(aoe_radius_m)
        else:
            final_aoe_radius_m = current.get("aoe_radius_m")
        final_targeting, final_aoe_radius_m = _validate_targeting_fields(final_targeting, final_aoe_radius_m)
        if magic_school is not None:
            final_magic_school = _normalize_magic_school(magic_school)
        else:
            final_magic_school = _normalize_magic_school(current.get("magic_school"))
        final_value_gp = int(value_gp) if value_gp is not None else int(current.get("value_gp") or 0)
        if final_value_gp < 0:
            raise ValueError("invalid_value_gp")
        final_weight_kg = (
            float(weight_kg) if weight_kg is not None else float(current.get("weight_kg") or 0.0)
        )
        if final_weight_kg < 0:
            raise ValueError("invalid_weight_kg")
        final_note = note if note is not None else current.get("note")
        final_effect_json = effect_json if effect_json is not None else current.get("effect_json")
        # Stage 5 follow-up: weapon_slot — validate + keep two_handed boolean in sync.
        if weapon_slot is not None:
            ws_clean = str(weapon_slot).strip().lower()
            if ws_clean not in _VALID_WEAPON_SLOT:
                raise ValueError("invalid_weapon_slot")
            final_weapon_slot = ws_clean
            final_two = 1 if ws_clean == "two_handed" else 0
        else:
            final_weapon_slot = current.get("weapon_slot") or ("two_handed" if final_two else "main_hand")

        if rarity is not None:
            final_rarity = int(rarity)
            if not 1 <= final_rarity <= 5:
                raise ValueError("invalid_rarity")
        else:
            final_rarity = current.get("rarity")

        conn.execute(
            """
            UPDATE game_config_weapons
            SET label = ?, damage_die = ?, weapon_type = ?, linked_stat = ?, allowed_classes = ?,
                two_handed = ?, finesse = ?, light = ?, range_m = ?, targeting = ?, aoe_radius_m = ?, magic_school = ?,
                value_gp = ?, weight_kg = ?, description = ?, note = ?, effect_json = ?, weapon_slot = ?,
                rarity = ?, is_active = ?, updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                final_damage_die,
                final_weapon_type,
                final_linked_stat,
                final_allowed_classes,
                final_two,
                final_finesse,
                final_light,
                final_range_m,
                final_targeting,
                final_aoe_radius_m,
                final_magic_school,
                final_value_gp,
                final_weight_kg,
                final_desc,
                final_note,
                final_effect_json,
                final_weapon_slot,
                final_rarity,
                final_is_active,
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, damage_die, weapon_type, linked_stat, allowed_classes,
                   two_handed, finesse, light, range_m, targeting, aoe_radius_m, magic_school,
                   value_gp, weight_kg, description, note, effect_json, weapon_slot,
                   rarity, is_active, locked_at, created_at, updated_at
            FROM game_config_weapons WHERE key = ?
            """,
            (safe_key,),
        )
        old_for_audit = dict(current)
        old_for_audit["allowed_classes"] = json.loads(old_for_audit.get("allowed_classes") or "[]")
        old_for_audit["two_handed"] = bool(old_for_audit.get("two_handed"))
        old_for_audit["finesse"] = bool(old_for_audit.get("finesse"))
        if new_row:
            new_row["allowed_classes"] = json.loads(new_row.get("allowed_classes") or "[]")
            new_row["two_handed"] = bool(new_row.get("two_handed"))
            new_row["finesse"] = bool(new_row.get("finesse"))
        _audit(conn, "game_config_weapons", safe_key, "UPDATE", old_for_audit, new_row)
        # U11c dual-write: re-read legacy row → upsert game_items
        from app.services.game_items_service import sync_from_legacy
        sync_from_legacy(conn, "game_config_weapons", safe_key)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def _character_uses_weapon(conn: sqlite3.Connection, weapon_key: str) -> int:
    rows = conn.execute("SELECT id, sheet_json FROM characters").fetchall()
    for row in rows:
        sheet_raw = row["sheet_json"] or "{}"
        try:
            parsed = json.loads(sheet_raw)
        except Exception:
            parsed = {}
        if not isinstance(parsed, dict):
            continue
        if parsed.get("weapon") == weapon_key or parsed.get("equipped_weapon") == weapon_key:
            return int(row["id"])
        weapons = parsed.get("weapons")
        if isinstance(weapons, list) and weapon_key in weapons:
            return int(row["id"])
        if isinstance(weapons, dict) and weapon_key in weapons:
            return int(row["id"])
    return 0


def delete_weapon(key: str, *, force: bool) -> None:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, damage_die, linked_stat, allowed_classes, is_active, locked_at, created_at, updated_at
            FROM game_config_weapons WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        character_id = _character_uses_weapon(conn, safe_key)
        if character_id:
            raise LookupError(f"weapon_in_use:{character_id}")

        loot_ref = conn.execute(
            """
            SELECT COUNT(*) AS c FROM game_config_loot_entries
            WHERE weapon_key IS NOT NULL AND weapon_key = ?
            """,
            (safe_key,),
        ).fetchone()
        if loot_ref and int(loot_ref["c"]) > 0:
            raise ValueError("in_use")

        conn.execute("DELETE FROM game_config_weapons WHERE key = ?", (safe_key,))
        raw_ac = current.get("allowed_classes") or "[]"
        try:
            current["allowed_classes"] = json.loads(raw_ac)
        except (json.JSONDecodeError, TypeError):
            current["allowed_classes"] = [s.strip() for s in str(raw_ac).split(",") if s.strip()]
        _audit(conn, "game_config_weapons", safe_key, "DELETE", current, None)
        # U11c dual-write: remove from game_items
        from app.services.game_items_service import delete_from_game_items
        delete_from_game_items(conn, safe_key)
        conn.commit()
    finally:
        conn.close()


def create_enemy(
    *,
    key: str,
    label: str,
    hp_base: int,
    ac_base: int,
    attack_bonus: int,
    damage_die: str,
    description: str | None = None,
    is_active: bool = True,
    tier: str = "standard",
    attacks_per_turn: int = 1,
    damage_bonus: int = 0,
    damage_type: str = "physical",
    xp_award: int = 0,
    conditions_immune: list[str] | None = None,
    loot_table_key: str | None = None,
    drop_chance: float = 1.0,
    note: str | None = None,
    dex_modifier: int = 0,
    skills_json: dict[str, int] | None = None,
    stats_json: dict[str, int] | None = None,
) -> dict:
    safe_key = _validate_key(key)
    safe_drop = _validate_drop_chance(drop_chance)
    safe_damage_die = _validate_damage_die(damage_die)
    if hp_base < 1:
        raise ValueError("invalid_hp_base")
    if ac_base < 1:
        raise ValueError("invalid_ac_base")
    if attack_bonus < 0:
        raise ValueError("invalid_attack_bonus")
    if attacks_per_turn < 1:
        raise ValueError("invalid_attacks_per_turn")
    if xp_award < 0:
        raise ValueError("invalid_xp_award")
    safe_tier = _validate_tier(tier)
    safe_damage_type = _validate_damage_type(damage_type)
    ci_json = _validate_conditions_immune(conditions_immune if conditions_immune is not None else [])
    safe_skills_json = _validate_enemy_skills_json(skills_json)
    # S2: admin may pass explicit stats; otherwise derive 7 stats from the archetype
    # heuristic (key/label keywords). Admin still creates an enemy with 4 numbers.
    if stats_json is not None:
        safe_stats_json = validate_stats_json(stats_json)
    else:
        safe_stats_json = json.dumps(stats_for_actor(safe_key, label), ensure_ascii=False)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_enemies WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("enemy_exists")
        if loot_table_key:
            lk = _validate_key(loot_table_key)
            lt = _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (lk,))
            if not lt:
                raise ValueError("invalid_loot_table_key")
            loot_table_key = lk
        else:
            # auto-create a loot table for this enemy
            auto_lt_key = f"loot_{safe_key}"
            if not _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (auto_lt_key,)):
                conn.execute(
                    "INSERT INTO game_config_loot_tables (key, label, description, is_active) VALUES (?, ?, '', 1)",
                    (auto_lt_key, f"Łupy: {label}"),
                )
            loot_table_key = auto_lt_key
        conn.execute(
            """
            INSERT INTO game_config_enemies (
                key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
                tier, attacks_per_turn, damage_bonus, damage_type,
                xp_award, conditions_immune, skills_json, stats_json, loot_table_key, drop_chance, note,
                description, is_active, locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (
                safe_key,
                label,
                hp_base,
                ac_base,
                attack_bonus,
                int(dex_modifier or 0),
                safe_damage_die,
                safe_tier,
                attacks_per_turn,
                damage_bonus,
                safe_damage_type,
                xp_award,
                ci_json,
                safe_skills_json,
                safe_stats_json,
                loot_table_key,
                safe_drop,
                note,
                description,
                1 if is_active else 0,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
                   tier, attacks_per_turn, damage_bonus, damage_type,
                   xp_award, conditions_immune, skills_json, stats_json, loot_table_key, drop_chance, note,
                   description, is_active, locked_at, created_at, updated_at
            FROM game_config_enemies WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            try:
                new_row["conditions_immune"] = json.loads(new_row.get("conditions_immune") or "[]")
            except Exception:
                new_row["conditions_immune"] = []
            try:
                parsed_sk = json.loads(new_row.get("skills_json") or "{}")
                new_row["skills_json"] = parsed_sk if isinstance(parsed_sk, dict) else {}
            except Exception:
                new_row["skills_json"] = {}
            try:
                parsed_st = json.loads(new_row.get("stats_json") or "{}")
                new_row["stats_json"] = parsed_st if isinstance(parsed_st, dict) else {}
            except Exception:
                new_row["stats_json"] = {}
            if new_row.get("drop_chance") is not None:
                new_row["drop_chance"] = float(new_row["drop_chance"])
        _audit(conn, "game_config_enemies", safe_key, "CREATE", None, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_enemy(
    key: str,
    *,
    label: str | None,
    hp_base: int | None,
    ac_base: int | None,
    attack_bonus: int | None,
    damage_die: str | None,
    description: str | None,
    is_active: bool | None,
    force: bool,
    tier: str | None = None,
    attacks_per_turn: int | None = None,
    damage_bonus: int | None = None,
    damage_type: str | None = None,
    xp_award: int | None = None,
    conditions_immune: list[str] | None = None,
    loot_table_key: str | None = None,
    note: str | None = None,
    drop_chance: float | None = None,
    dex_modifier: int | None = None,
    skills_json: dict[str, int] | None = None,
    stats_json: dict[str, int] | None = None,
    image_url: str | None = None,
    image_url_raw: str | None = None,
    image_gen_prompt: str | None = None,
    min_level: int | None = None,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
                   tier, attacks_per_turn, damage_bonus, damage_type,
                   xp_award, conditions_immune, skills_json, stats_json, loot_table_key, drop_chance, note,
                   description, is_active, locked_at, created_at, updated_at,
                   image_url, image_url_raw, image_gen_prompt,
                   COALESCE(min_level, 1) AS min_level
            FROM game_config_enemies WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        final_hp_base = hp_base if hp_base is not None else current["hp_base"]
        final_ac_base = ac_base if ac_base is not None else current["ac_base"]
        final_attack_bonus = attack_bonus if attack_bonus is not None else current["attack_bonus"]
        final_dex_modifier = dex_modifier if dex_modifier is not None else int(current.get("dex_modifier") or 0)
        final_damage_die = _validate_damage_die(damage_die) if damage_die is not None else current["damage_die"]
        if final_hp_base < 1:
            raise ValueError("invalid_hp_base")
        if final_ac_base < 1:
            raise ValueError("invalid_ac_base")
        if final_attack_bonus < 0:
            raise ValueError("invalid_attack_bonus")

        final_tier = _validate_tier(tier) if tier is not None else (current.get("tier") or "standard")
        final_attacks = attacks_per_turn if attacks_per_turn is not None else int(current.get("attacks_per_turn") or 1)
        final_dmg_bonus = damage_bonus if damage_bonus is not None else int(current.get("damage_bonus") or 0)
        final_dmg_type = (
            _validate_damage_type(damage_type) if damage_type is not None else (current.get("damage_type") or "physical")
        )
        final_xp = xp_award if xp_award is not None else int(current.get("xp_award") or 0)
        if final_attacks < 1:
            raise ValueError("invalid_attacks_per_turn")
        if final_xp < 0:
            raise ValueError("invalid_xp_award")
        final_ci = (
            _validate_conditions_immune(conditions_immune)
            if conditions_immune is not None
            else (current.get("conditions_immune") or "[]")
        )
        final_skills = (
            _validate_enemy_skills_json(skills_json)
            if skills_json is not None
            else (current.get("skills_json") or "{}")
        )
        final_stats = (
            validate_stats_json(stats_json)
            if stats_json is not None
            else (current.get("stats_json") or "{}")
        )
        final_loot = current.get("loot_table_key")
        if loot_table_key is not None:
            if loot_table_key == "":
                final_loot = None
            else:
                lk = _validate_key(loot_table_key)
                lt = _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (lk,))
                if not lt:
                    raise ValueError("invalid_loot_table_key")
                final_loot = lk
        final_note = note if note is not None else current.get("note")
        cur_drop = float(current.get("drop_chance") if current.get("drop_chance") is not None else 1.0)
        final_drop = _validate_drop_chance(drop_chance, current=cur_drop)

        final_image_url = image_url if image_url is not None else current.get("image_url")
        final_image_url_raw = image_url_raw if image_url_raw is not None else current.get("image_url_raw")
        final_image_gen_prompt = image_gen_prompt if image_gen_prompt is not None else current.get("image_gen_prompt")
        final_min_level = max(1, int(min_level)) if min_level is not None else int(current.get("min_level") or 1)

        conn.execute(
            """
            UPDATE game_config_enemies
            SET label = ?, hp_base = ?, ac_base = ?, attack_bonus = ?, dex_modifier = ?, damage_die = ?,
                tier = ?, attacks_per_turn = ?, damage_bonus = ?, damage_type = ?,
                xp_award = ?, conditions_immune = ?, skills_json = ?, stats_json = ?, loot_table_key = ?, drop_chance = ?, note = ?,
                description = ?, is_active = ?, image_url = ?, image_url_raw = ?, image_gen_prompt = ?,
                min_level = ?,
                updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                final_hp_base,
                final_ac_base,
                final_attack_bonus,
                final_dex_modifier,
                final_damage_die,
                final_tier,
                final_attacks,
                final_dmg_bonus,
                final_dmg_type,
                final_xp,
                final_ci,
                final_skills,
                final_stats,
                final_loot,
                final_drop,
                final_note,
                description if description is not None else current.get("description"),
                (1 if is_active else 0) if is_active is not None else current.get("is_active", 1),
                final_image_url,
                final_image_url_raw,
                final_image_gen_prompt,
                final_min_level,
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
                   tier, attacks_per_turn, damage_bonus, damage_type,
                   xp_award, conditions_immune, skills_json, stats_json, loot_table_key, drop_chance, note,
                   description, is_active, locked_at, created_at, updated_at,
                   image_url, image_url_raw, image_gen_prompt,
                   COALESCE(min_level, 1) AS min_level
            FROM game_config_enemies WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            try:
                new_row["conditions_immune"] = json.loads(new_row.get("conditions_immune") or "[]")
            except Exception:
                new_row["conditions_immune"] = []
            try:
                parsed_sk = json.loads(new_row.get("skills_json") or "{}")
                new_row["skills_json"] = parsed_sk if isinstance(parsed_sk, dict) else {}
            except Exception:
                new_row["skills_json"] = {}
            try:
                parsed_st = json.loads(new_row.get("stats_json") or "{}")
                new_row["stats_json"] = parsed_st if isinstance(parsed_st, dict) else {}
            except Exception:
                new_row["stats_json"] = {}
            if new_row.get("drop_chance") is not None:
                new_row["drop_chance"] = float(new_row["drop_chance"])
        cur_audit = dict(current)
        try:
            cur_audit["conditions_immune"] = json.loads(cur_audit.get("conditions_immune") or "[]")
        except Exception:
            cur_audit["conditions_immune"] = []
        try:
            parsed_cur_sk = json.loads(cur_audit.get("skills_json") or "{}")
            cur_audit["skills_json"] = parsed_cur_sk if isinstance(parsed_cur_sk, dict) else {}
        except Exception:
            cur_audit["skills_json"] = {}
        try:
            parsed_cur_st = json.loads(cur_audit.get("stats_json") or "{}")
            cur_audit["stats_json"] = parsed_cur_st if isinstance(parsed_cur_st, dict) else {}
        except Exception:
            cur_audit["stats_json"] = {}
        _audit(conn, "game_config_enemies", safe_key, "UPDATE", cur_audit, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def delete_enemy(key: str, *, force: bool) -> None:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, description, is_active, locked_at, created_at, updated_at
            FROM game_config_enemies WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        conn.execute("DELETE FROM game_config_enemies WHERE key = ?", (safe_key,))
        _audit(conn, "game_config_enemies", safe_key, "DELETE", current, None)
        conn.commit()
    finally:
        conn.close()


def create_condition(
    *,
    key: str,
    label: str,
    effect_json: str,
    description: str | None = None,
    is_active: bool = True,
    stackable: bool = False,
    auto_remove: str | None = None,
) -> dict:
    safe_key = _validate_key(key)
    safe_effect_json = _normalize_effect_json(effect_json)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_conditions WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("condition_exists")
        conn.execute(
            """
            INSERT INTO game_config_conditions (
                key, label, effect_json, description, is_active, stackable, auto_remove,
                locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (safe_key, label, safe_effect_json, description, 1 if is_active else 0, 1 if stackable else 0, auto_remove),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, effect_json, description, is_active, stackable, auto_remove,
                   locked_at, created_at, updated_at
            FROM game_config_conditions WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["stackable"] = bool(new_row.get("stackable"))
        _audit(conn, "game_config_conditions", safe_key, "CREATE", None, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_condition(
    key: str,
    *,
    label: str | None,
    effect_json: str | None,
    description: str | None,
    is_active: bool | None,
    force: bool,
    stackable: bool | None = None,
    auto_remove: str | None = None,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, effect_json, description, is_active, stackable, auto_remove,
                   locked_at, created_at, updated_at
            FROM game_config_conditions WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        final_effect_json = (
            _normalize_effect_json(effect_json)
            if effect_json is not None
            else current.get("effect_json") or "{}"
        )
        final_stackable = (1 if stackable else 0) if stackable is not None else int(current.get("stackable", 0))
        if auto_remove is not None:
            final_auto = auto_remove.strip() if isinstance(auto_remove, str) and auto_remove.strip() else None
        else:
            final_auto = current.get("auto_remove")

        conn.execute(
            """
            UPDATE game_config_conditions
            SET label = ?, effect_json = ?, description = ?, is_active = ?, stackable = ?, auto_remove = ?,
                updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                final_effect_json,
                description if description is not None else current.get("description"),
                (1 if is_active else 0) if is_active is not None else current.get("is_active", 1),
                final_stackable,
                final_auto,
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, effect_json, description, is_active, stackable, auto_remove,
                   locked_at, created_at, updated_at
            FROM game_config_conditions WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["stackable"] = bool(new_row.get("stackable"))
        cur_audit = dict(current)
        cur_audit["stackable"] = bool(cur_audit.get("stackable"))
        _audit(conn, "game_config_conditions", safe_key, "UPDATE", cur_audit, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def delete_condition(key: str, *, force: bool) -> None:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, effect_json, description, is_active, locked_at, created_at, updated_at
            FROM game_config_conditions WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        conn.execute("DELETE FROM game_config_conditions WHERE key = ?", (safe_key,))
        _audit(conn, "game_config_conditions", safe_key, "DELETE", current, None)
        conn.commit()
    finally:
        conn.close()


_VALID_ARMOR_COVERAGE = {"head", "torso", "limb_arm", "limb_leg", "full", "hands", "feet", "back"}


def list_items() -> list[dict]:
    rows = _fetch_all(
        """
        SELECT key, label, item_type, description, value_gp, weight_kg,
               allowed_classes, ac_bonus, armor_coverage,
               charges, effect_json, ai_generated, approved,
               note, is_active, locked_at, created_at, updated_at,
               image_url, image_gen_prompt
        FROM game_config_items
        ORDER BY item_type ASC, label COLLATE NOCASE ASC, key ASC
        """
    )
    for row in rows:
        row.update(_legacy_effect_fields_from_json(row.get("effect_json")))
        row["is_active"] = bool(row.get("is_active", 1))
        try:
            row["allowed_classes"] = json.loads(row.get("allowed_classes") or "[]")
        except Exception:
            row["allowed_classes"] = []
    return rows


def create_item(
    *,
    key: str,
    label: str,
    item_type: str = "misc",
    description: str = "",
    value_gp: int = 0,
    weight_kg: float = 0.0,
    allowed_classes: list[str] | None = None,
    ac_bonus: int = 0,
    armor_coverage: str | None = None,
    effect_type: str | None = None,
    effect_dice: str | None = None,
    effect_bonus: int = 0,
    effect_target: str = "self",
    charges: int = 1,
    effect_json: str | None = None,
    ai_generated: int = 0,
    approved: int = 1,
    note: str | None = None,
    is_active: bool = True,
) -> dict:
    safe_key = _validate_key(key)
    safe_type = _validate_item_type(item_type)
    if value_gp < 0:
        raise ValueError("invalid_value_gp")
    if weight_kg < 0:
        raise ValueError("invalid_weight_kg")
    if int(ac_bonus) < 0:
        raise ValueError("invalid_ac_bonus")
    final_charges = int(charges)
    if final_charges < 1:
        raise ValueError("invalid_charges")
    # Stage 5 E1: armor_coverage — only meaningful for armor; default 'torso'.
    if safe_type == "armor":
        final_coverage = (armor_coverage or "torso").strip().lower()
        if final_coverage not in _VALID_ARMOR_COVERAGE:
            raise ValueError("invalid_armor_coverage")
    else:
        final_coverage = None
    ac_json = _serialize_allowed_classes(allowed_classes)
    if effect_json is None:
        eff = _normalize_legacy_item_effect_json(
            current_effect_json=None,
            effect_type=effect_type,
            effect_dice=effect_dice,
            effect_bonus=effect_bonus,
            effect_target=effect_target,
        )
    elif isinstance(effect_json, str) and not effect_json.strip():
        eff = None
    else:
        eff = _normalize_effect_json(effect_json)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_items WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("item_exists")
        conn.execute(
            """
            INSERT INTO game_config_items (
                key, label, item_type, description, value_gp, weight_kg,
                allowed_classes, ac_bonus, armor_coverage,
                charges, effect_json, ai_generated, approved,
                note, is_active, locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (
                safe_key,
                label,
                safe_type,
                description or "",
                int(value_gp),
                float(weight_kg),
                ac_json,
                int(ac_bonus),
                final_coverage,
                final_charges,
                eff,
                int(ai_generated),
                int(approved),
                note,
                1 if is_active else 0,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, item_type, description, value_gp, weight_kg,
                   allowed_classes, ac_bonus, armor_coverage,
                   charges, effect_json, ai_generated, approved,
                   note, is_active, locked_at, created_at, updated_at
            FROM game_config_items WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row.update(_legacy_effect_fields_from_json(new_row.get("effect_json")))
            new_row["is_active"] = bool(new_row.get("is_active", 1))
            try:
                new_row["allowed_classes"] = json.loads(new_row.get("allowed_classes") or "[]")
            except Exception:
                new_row["allowed_classes"] = []
        _audit(conn, "game_config_items", safe_key, "CREATE", None, new_row)
        # U11c dual-write: re-read legacy row → upsert game_items
        from app.services.game_items_service import sync_from_legacy
        sync_from_legacy(conn, "game_config_items", safe_key)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_item(
    key: str,
    *,
    label: str | None,
    item_type: str | None,
    description: str | None,
    value_gp: int | None,
    effect_json: str | None,
    is_active: bool | None,
    force: bool,
    allowed_classes: list[str] | None = None,
    weight_kg: float | None = None,
    ac_bonus: int | None = None,
    armor_coverage: str | None = None,
    effect_type: str | None = None,
    effect_dice: str | None = None,
    effect_bonus: int | None = None,
    effect_target: str | None = None,
    charges: int | None = None,
    ai_generated: int | None = None,
    approved: int | None = None,
    note: str | None = None,
    rarity: int | None = None,
    image_url: str | None = None,
    image_gen_prompt: str | None = None,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, item_type, description, value_gp, weight_kg,
                   allowed_classes, ac_bonus, armor_coverage,
                   charges, effect_json, ai_generated, approved,
                   note, rarity, is_active, locked_at, created_at, updated_at,
                   image_url, image_gen_prompt
            FROM game_config_items WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        final_type = _validate_item_type(item_type) if item_type is not None else current["item_type"]
        final_label = label if label is not None else current["label"]
        final_desc = description if description is not None else current.get("description") or ""
        final_gp = int(value_gp) if value_gp is not None else int(current["value_gp"])
        final_wkg = float(weight_kg) if weight_kg is not None else float(current.get("weight_kg") or 0.0)
        if final_gp < 0:
            raise ValueError("invalid_value_gp")
        if final_wkg < 0:
            raise ValueError("invalid_weight_kg")

        if effect_json is None:
            final_effect = _normalize_legacy_item_effect_json(
                current_effect_json=current.get("effect_json"),
                effect_type=effect_type,
                effect_dice=effect_dice,
                effect_bonus=effect_bonus,
                effect_target=effect_target,
            )
        elif isinstance(effect_json, str) and not effect_json.strip():
            final_effect = None
        else:
            final_effect = _normalize_effect_json(effect_json)

        final_active = (1 if is_active else 0) if is_active is not None else int(current.get("is_active", 1))
        if allowed_classes is not None:
            final_ac = _serialize_allowed_classes(allowed_classes)
        else:
            final_ac = current.get("allowed_classes") or "[]"
        final_ac_bonus = int(ac_bonus) if ac_bonus is not None else int(current.get("ac_bonus") or 0)
        if final_ac_bonus < 0:
            raise ValueError("invalid_ac_bonus")

        # Stage 5 E1: armor_coverage. Only meaningful for armor.
        if armor_coverage is not None:
            coverage_clean = str(armor_coverage).strip().lower()
            if final_type == "armor":
                if coverage_clean not in _VALID_ARMOR_COVERAGE:
                    raise ValueError("invalid_armor_coverage")
                final_coverage = coverage_clean
            else:
                final_coverage = None  # discard for non-armor types
        elif final_type == "armor":
            # No new value but type is armor — keep existing or default to torso.
            final_coverage = current.get("armor_coverage") or "torso"
        else:
            final_coverage = None

        final_charges = int(charges) if charges is not None else int(current.get("charges") or 1)
        if final_charges < 1:
            raise ValueError("invalid_charges")
        final_ai = int(ai_generated) if ai_generated is not None else int(current.get("ai_generated") or 0)
        _cur_appr = current.get("approved")
        final_appr = int(approved) if approved is not None else (int(_cur_appr) if _cur_appr is not None else 1)
        final_note = note if note is not None else current.get("note")
        if rarity is not None:
            final_rarity = int(rarity)
            if not 1 <= final_rarity <= 5:
                raise ValueError("invalid_rarity")
        else:
            final_rarity = current.get("rarity")
        final_image_url = image_url if image_url is not None else current.get("image_url")
        final_image_gen_prompt = image_gen_prompt if image_gen_prompt is not None else current.get("image_gen_prompt")

        conn.execute(
            """
            UPDATE game_config_items
            SET label = ?, item_type = ?, description = ?, value_gp = ?, weight_kg = ?,
                allowed_classes = ?, ac_bonus = ?, armor_coverage = ?,
                charges = ?, effect_json = ?, ai_generated = ?, approved = ?,
                note = ?, rarity = ?, is_active = ?, image_url = ?, image_gen_prompt = ?,
                updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                final_label,
                final_type,
                final_desc,
                final_gp,
                final_wkg,
                final_ac,
                final_ac_bonus,
                final_coverage,
                final_charges,
                final_effect,
                final_ai,
                final_appr,
                final_note,
                final_rarity,
                final_active,
                final_image_url,
                final_image_gen_prompt,
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, item_type, description, value_gp, weight_kg,
                   allowed_classes, ac_bonus, armor_coverage,
                   charges, effect_json, ai_generated, approved,
                   note, rarity, is_active, locked_at, created_at, updated_at,
                   image_url, image_gen_prompt
            FROM game_config_items WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row.update(_legacy_effect_fields_from_json(new_row.get("effect_json")))
            new_row["is_active"] = bool(new_row.get("is_active", 1))
            try:
                new_row["allowed_classes"] = json.loads(new_row.get("allowed_classes") or "[]")
            except Exception:
                new_row["allowed_classes"] = []
        _audit(conn, "game_config_items", safe_key, "UPDATE", dict(current), new_row)
        # U11c dual-write: re-read legacy row → upsert game_items
        from app.services.game_items_service import sync_from_legacy
        sync_from_legacy(conn, "game_config_items", safe_key)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def delete_item(key: str, *, force: bool) -> None:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, item_type, description, value_gp, weight_kg,
                   allowed_classes, ac_bonus,
                   charges, effect_json, ai_generated, approved,
                   note, is_active, locked_at, created_at, updated_at
            FROM game_config_items WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        ref = conn.execute(
            "SELECT COUNT(*) AS c FROM game_config_loot_entries WHERE item_key IS NOT NULL AND item_key = ?",
            (safe_key,),
        ).fetchone()
        if ref and int(ref["c"]) > 0:
            raise ValueError("in_use")
        conn.execute("DELETE FROM game_config_items WHERE key = ?", (safe_key,))
        cur_dict = _normalize_item_row(dict(current))
        _audit(conn, "game_config_items", safe_key, "DELETE", cur_dict, None)
        # U11c dual-write: remove from game_items
        from app.services.game_items_service import delete_from_game_items
        delete_from_game_items(conn, safe_key)
        conn.commit()
    finally:
        conn.close()


def _consumable_row_as_legacy_dict(row: dict) -> dict:
    """API shape expected by older admin clients: base_price mirrors value_gp."""
    out = dict(row)
    out["base_price"] = int(out.get("value_gp") or 0)
    out["is_active"] = bool(out.get("is_active", 1))
    return out


def list_consumables() -> list[dict]:
    """DEPRECATED 8H — consumables live in game_config_items with item_type='consumable'."""
    rows = _fetch_all(
        """
        SELECT key, label, description, effect_json, weight_kg, charges, value_gp,
               note, is_active, locked_at, created_at, updated_at,
               image_url, image_gen_prompt
        FROM game_config_items
        WHERE item_type = 'consumable'
        ORDER BY label COLLATE NOCASE ASC, key ASC
        """
    )
    out: list[dict] = []
    for row in rows:
        payload = dict(row)
        payload.update(_legacy_effect_fields_from_json(payload.get("effect_json")))
        out.append(_consumable_row_as_legacy_dict(payload))
    return out


def create_consumable(
    *,
    key: str,
    label: str,
    description: str = "",
    effect_type: str = "misc",
    effect_dice: str | None = None,
    effect_bonus: int = 0,
    effect_target: str = "self",
    weight_kg: float = 0.0,
    charges: int = 1,
    base_price: int = 0,
    note: str | None = None,
    is_active: bool = True,
) -> dict:
    """DEPRECATED 8H — creates a row in game_config_items (item_type='consumable')."""
    effect_json = _normalize_legacy_item_effect_json(
        current_effect_json=None,
        effect_type=effect_type,
        effect_dice=effect_dice,
        effect_bonus=effect_bonus,
        effect_target=effect_target,
    )
    created = create_item(
        key=key,
        label=label,
        item_type="consumable",
        description=description or "",
        value_gp=int(base_price),
        effect_json=effect_json,
        is_active=is_active,
        weight_kg=float(weight_kg),
        allowed_classes=[],
        ac_bonus=0,
        charges=int(charges),
        ai_generated=0,
        approved=1,
        note=note,
    )
    return _consumable_row_as_legacy_dict(created)


def update_consumable(
    key: str,
    *,
    label: str | None,
    description: str | None,
    effect_type: str | None,
    effect_dice: str | None,
    effect_bonus: int | None,
    effect_target: str | None,
    weight_kg: float | None,
    charges: int | None,
    base_price: int | None,
    note: str | None,
    is_active: bool | None,
    new_key: str | None = None,
    effect_json: str | None = None,
    rarity: int | None = None,
    force: bool,
) -> dict:
    """DEPRECATED 8H — updates game_config_items row for consumable catalog entries."""
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, description, effect_json, weight_kg, charges, value_gp,
                   note, is_active, locked_at, created_at, updated_at
            FROM game_config_items
            WHERE key = ? AND item_type = 'consumable'
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        nk_req = (new_key or "").strip() if new_key is not None else ""
        if nk_req:
            nk = _validate_key(nk_req)
            if nk != safe_key:
                if _fetch_one(conn, "SELECT key FROM game_config_items WHERE key = ?", (nk,)):
                    raise ValueError("consumable_exists")
                loot_cols = {r[1] for r in conn.execute("PRAGMA table_info(game_config_loot_entries)").fetchall()}
                if "item_key" in loot_cols:
                    conn.execute(
                        "UPDATE game_config_loot_entries SET item_key = ? WHERE item_key = ?",
                        (nk, safe_key),
                    )
                conn.execute(
                    "UPDATE game_config_items SET key = ? WHERE key = ? AND item_type = 'consumable'",
                    (nk, safe_key),
                )
                # U11c dual-write: drop old game_items key (new one re-synced by update_item below)
                from app.services.game_items_service import delete_from_game_items
                delete_from_game_items(conn, safe_key)
                safe_key = nk
                conn.commit()

        updated = update_item(
            safe_key,
            label=label,
            item_type=None,
            description=description,
            value_gp=base_price,
            effect_json=effect_json,
            is_active=is_active,
            force=force,
            weight_kg=weight_kg,
            allowed_classes=None,
            ac_bonus=None,
            effect_type=effect_type,
            effect_dice=effect_dice,
            effect_bonus=effect_bonus,
            effect_target=effect_target,
            charges=charges,
            ai_generated=None,
            approved=None,
            note=note,
            rarity=rarity,
        )
        return _consumable_row_as_legacy_dict(updated)
    finally:
        conn.close()


def delete_consumable(key: str, *, force: bool) -> None:
    """DEPRECATED 8H — deletes consumable row from game_config_items."""
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, description, effect_json, weight_kg, charges, value_gp,
                   note, is_active, locked_at, created_at, updated_at
            FROM game_config_items
            WHERE key = ? AND item_type = 'consumable'
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        ref = conn.execute(
            "SELECT COUNT(*) AS c FROM game_config_loot_entries WHERE item_key IS NOT NULL AND item_key = ?",
            (safe_key,),
        ).fetchone()
        if ref and int(ref["c"]) > 0:
            raise ValueError("in_use")
        conn.execute("DELETE FROM game_config_items WHERE key = ? AND item_type = 'consumable'", (safe_key,))
        cur_dict = _consumable_row_as_legacy_dict(dict(current))
        _audit(conn, "game_config_items", safe_key, "DELETE", cur_dict, None)
        # U11c dual-write: remove from game_items
        from app.services.game_items_service import delete_from_game_items
        delete_from_game_items(conn, safe_key)
        conn.commit()
    finally:
        conn.close()


def list_loot_tables() -> list[dict]:
    rows = _fetch_all(
        """
        SELECT key, label, description, is_active, gold_min, gold_max, locked_at, created_at, updated_at
        FROM game_config_loot_tables
        ORDER BY label COLLATE NOCASE ASC, key ASC
        """
    )
    for row in rows:
        row["is_active"] = bool(row.get("is_active", 1))
        row["gold_min"] = int(row.get("gold_min") or 0)
        row["gold_max"] = int(row.get("gold_max") or 0)
    return rows


def create_loot_table(
    *,
    key: str,
    label: str,
    description: str = "",
    is_active: bool = True,
    gold_min: int = 0,
    gold_max: int = 0,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("loot_table_exists")
        gmin = int(gold_min or 0)
        gmax = int(gold_max or 0)
        if gmin < 0 or gmax < 0:
            raise ValueError("invalid_gold_range")
        if gmin > gmax:
            raise ValueError("invalid_gold_range")
        conn.execute(
            """
            INSERT INTO game_config_loot_tables (
                key, label, description, is_active, gold_min, gold_max, locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (safe_key, label, description or "", 1 if is_active else 0, gmin, gmax),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, description, is_active, gold_min, gold_max, locked_at, created_at, updated_at
            FROM game_config_loot_tables WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["is_active"] = bool(new_row.get("is_active", 1))
            new_row["gold_min"] = int(new_row.get("gold_min") or 0)
            new_row["gold_max"] = int(new_row.get("gold_max") or 0)
        _audit(conn, "game_config_loot_tables", safe_key, "CREATE", None, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_loot_table(
    key: str,
    *,
    label: str | None,
    description: str | None,
    is_active: bool | None,
    gold_min: int | None = None,
    gold_max: int | None = None,
    new_key: str | None = None,
    force: bool,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, description, is_active, gold_min, gold_max, locked_at, created_at, updated_at
            FROM game_config_loot_tables WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        old_for_audit = dict(current)
        nk_req = (new_key or "").strip() if new_key is not None else ""
        if nk_req:
            nk = _validate_key(nk_req)
            if nk != safe_key:
                if _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (nk,)):
                    raise ValueError("loot_table_exists")
                conn.execute(
                    "UPDATE game_config_enemies SET loot_table_key = ? WHERE loot_table_key = ?",
                    (nk, safe_key),
                )
                conn.execute(
                    "UPDATE game_config_loot_entries SET loot_table_key = ? WHERE loot_table_key = ?",
                    (nk, safe_key),
                )
                conn.execute(
                    "UPDATE game_config_loot_tables SET key = ? WHERE key = ?",
                    (nk, safe_key),
                )
                safe_key = nk
        final_gold_min = int(current.get("gold_min") or 0) if gold_min is None else int(gold_min)
        final_gold_max = int(current.get("gold_max") or 0) if gold_max is None else int(gold_max)
        if final_gold_min < 0 or final_gold_max < 0 or final_gold_min > final_gold_max:
            raise ValueError("invalid_gold_range")
        conn.execute(
            """
            UPDATE game_config_loot_tables
            SET label = ?, description = ?, is_active = ?, gold_min = ?, gold_max = ?, updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                description if description is not None else current.get("description") or "",
                (1 if is_active else 0) if is_active is not None else int(current.get("is_active", 1)),
                final_gold_min,
                final_gold_max,
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, description, is_active, gold_min, gold_max, locked_at, created_at, updated_at
            FROM game_config_loot_tables WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["is_active"] = bool(new_row.get("is_active", 1))
            new_row["gold_min"] = int(new_row.get("gold_min") or 0)
            new_row["gold_max"] = int(new_row.get("gold_max") or 0)
        audit_row_key = str(new_row["key"]) if new_row else safe_key
        _audit(conn, "game_config_loot_tables", audit_row_key, "UPDATE", old_for_audit, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def delete_loot_table(key: str, *, force: bool) -> None:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, description, is_active, locked_at, created_at, updated_at
            FROM game_config_loot_tables WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        conn.execute("DELETE FROM game_config_loot_entries WHERE loot_table_key = ?", (safe_key,))
        conn.execute("DELETE FROM game_config_loot_tables WHERE key = ?", (safe_key,))
        cur_dict = dict(current)
        cur_dict["is_active"] = bool(cur_dict.get("is_active", 1))
        _audit(conn, "game_config_loot_tables", safe_key, "DELETE", cur_dict, None)
        conn.commit()
    finally:
        conn.close()


_LOOT_ENTRY_SELECT = """
    SELECT e.id, e.loot_table_key, e.item_key, e.consumable_key, e.weapon_key, e.recipe_key,
           e.weight, e.qty_min, e.qty_max,
           i.label AS item_label,
           c.label AS consumable_label,
           w.label AS weapon_label,
           rc.label AS recipe_label,
           COALESCE(i.label, c.label, w.label, rc.label) AS source_label,
           CASE
               WHEN e.weapon_key IS NOT NULL THEN 'weapon'
               WHEN e.consumable_key IS NOT NULL THEN 'consumable'
               WHEN e.recipe_key IS NOT NULL THEN 'recipe'
               WHEN i.item_type = 'consumable' THEN 'consumable'
               WHEN e.item_key IS NOT NULL THEN 'item'
               ELSE 'item'
           END AS source_type,
           COALESCE(e.item_key, e.consumable_key, e.weapon_key, e.recipe_key) AS source_key
    FROM game_config_loot_entries e
    LEFT JOIN game_config_items i ON i.key = e.item_key
    LEFT JOIN game_config_consumables c ON c.key = e.consumable_key
    LEFT JOIN game_config_weapons w ON w.key = e.weapon_key
    LEFT JOIN game_config_recipes rc ON rc.key = e.recipe_key
"""


def list_loot_entries(loot_table_key: str) -> list[dict]:
    safe_key = _validate_key(loot_table_key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        parent = _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (safe_key,))
        if not parent:
            raise ValueError("loot_table_not_found")
        rows = conn.execute(
            _LOOT_ENTRY_SELECT + " WHERE e.loot_table_key = ? ORDER BY source_label COLLATE NOCASE ASC, source_key ASC",
            (safe_key,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_loot_entry(
    loot_table_key: str,
    *,
    item_key: str | None = None,
    consumable_key: str | None = None,
    weapon_key: str | None = None,
    recipe_key: str | None = None,
    weight: int,
    qty_min: int,
    qty_max: int,
) -> dict:
    lt = _validate_key(loot_table_key)
    ik = _validate_key(item_key) if item_key and str(item_key).strip() else None
    ck = _validate_key(consumable_key) if consumable_key and str(consumable_key).strip() else None
    wk = _validate_key(weapon_key) if weapon_key and str(weapon_key).strip() else None
    rk = _validate_key(recipe_key) if recipe_key and str(recipe_key).strip() else None
    if sum(1 for x in (ik, ck, wk, rk) if x is not None) != 1:
        raise ValueError("invalid_loot_entry_source")
    if weight < 1 or weight > 100:
        raise ValueError("invalid_weight")
    if qty_min < 1 or qty_max < 1 or qty_min > qty_max:
        raise ValueError("invalid_qty_range")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        parent = _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (lt,))
        if not parent:
            raise ValueError("loot_table_not_found")
        if ik is not None:
            if not _fetch_one(conn, "SELECT key FROM game_config_items WHERE key = ?", (ik,)):
                raise ValueError("item_not_found")
            conn.execute(
                """
                INSERT INTO game_config_loot_entries (loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max)
                VALUES (?, ?, NULL, NULL, ?, ?, ?)
                ON CONFLICT(loot_table_key, item_key) WHERE item_key IS NOT NULL DO UPDATE SET
                    weight = excluded.weight, qty_min = excluded.qty_min, qty_max = excluded.qty_max
                """,
                (lt, ik, weight, qty_min, qty_max),
            )
            row = _fetch_one(conn, _LOOT_ENTRY_SELECT + " WHERE e.loot_table_key = ? AND e.item_key = ?", (lt, ik))
        elif ck is not None:
            if not _fetch_one(conn, "SELECT key FROM game_config_consumables WHERE key = ?", (ck,)):
                raise ValueError("consumable_not_found")
            conn.execute(
                """
                INSERT INTO game_config_loot_entries (loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max)
                VALUES (?, NULL, ?, NULL, ?, ?, ?)
                ON CONFLICT(loot_table_key, consumable_key) WHERE consumable_key IS NOT NULL DO UPDATE SET
                    weight = excluded.weight, qty_min = excluded.qty_min, qty_max = excluded.qty_max
                """,
                (lt, ck, weight, qty_min, qty_max),
            )
            row = _fetch_one(conn, _LOOT_ENTRY_SELECT + " WHERE e.loot_table_key = ? AND e.consumable_key = ?", (lt, ck))
        elif wk is not None:
            if not _fetch_one(conn, "SELECT key FROM game_config_weapons WHERE key = ?", (wk,)):
                raise ValueError("weapon_not_found")
            conn.execute(
                """
                INSERT INTO game_config_loot_entries (loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max)
                VALUES (?, NULL, NULL, ?, ?, ?, ?)
                ON CONFLICT(loot_table_key, weapon_key) WHERE weapon_key IS NOT NULL DO UPDATE SET
                    weight = excluded.weight, qty_min = excluded.qty_min, qty_max = excluded.qty_max
                """,
                (lt, wk, weight, qty_min, qty_max),
            )
            row = _fetch_one(conn, _LOOT_ENTRY_SELECT + " WHERE e.loot_table_key = ? AND e.weapon_key = ?", (lt, wk))
        else:
            # #1375: receptura jako drop lootu (4-way XOR recipe_key).
            if not _fetch_one(conn, "SELECT key FROM game_config_recipes WHERE key = ?", (rk,)):
                raise ValueError("recipe_not_found")
            conn.execute(
                """
                INSERT INTO game_config_loot_entries (loot_table_key, item_key, consumable_key, weapon_key, recipe_key, weight, qty_min, qty_max)
                VALUES (?, NULL, NULL, NULL, ?, ?, ?, ?)
                ON CONFLICT(loot_table_key, recipe_key) WHERE recipe_key IS NOT NULL DO UPDATE SET
                    weight = excluded.weight, qty_min = excluded.qty_min, qty_max = excluded.qty_max
                """,
                (lt, rk, weight, qty_min, qty_max),
            )
            row = _fetch_one(conn, _LOOT_ENTRY_SELECT + " WHERE e.loot_table_key = ? AND e.recipe_key = ?", (lt, rk))
        conn.commit()
        return dict(row) if row else {}
    finally:
        conn.close()


def delete_loot_entry_by_id(loot_table_key: str, entry_id: int) -> None:
    lt = _validate_key(loot_table_key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = _fetch_one(
            conn,
            "SELECT id, loot_table_key, item_key, consumable_key, weapon_key FROM game_config_loot_entries WHERE id = ? AND loot_table_key = ?",
            (int(entry_id), lt),
        )
        if not cur:
            raise KeyError("not_found")
        conn.execute("DELETE FROM game_config_loot_entries WHERE id = ? AND loot_table_key = ?", (int(entry_id), lt))
        _audit(conn, "game_config_loot_entries", f"{lt}:id:{entry_id}", "DELETE", dict(cur), None)
        conn.commit()
    finally:
        conn.close()


def delete_loot_entry(
    loot_table_key: str,
    item_key: str | None = None,
    consumable_key: str | None = None,
    weapon_key: str | None = None,
) -> None:
    lt = _validate_key(loot_table_key)
    ik = _validate_key(item_key) if item_key and str(item_key).strip() else None
    ck = _validate_key(consumable_key) if consumable_key and str(consumable_key).strip() else None
    wk = _validate_key(weapon_key) if weapon_key and str(weapon_key).strip() else None
    if sum(1 for x in (ik, ck, wk) if x is not None) != 1:
        raise ValueError("invalid_loot_entry_source")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if ik is not None:
            cur = _fetch_one(conn, "SELECT id, loot_table_key, item_key, consumable_key, weapon_key FROM game_config_loot_entries WHERE loot_table_key = ? AND item_key = ?", (lt, ik))
            audit_id = f"{lt}:item:{ik}"
        elif ck is not None:
            cur = _fetch_one(conn, "SELECT id, loot_table_key, item_key, consumable_key, weapon_key FROM game_config_loot_entries WHERE loot_table_key = ? AND consumable_key = ?", (lt, ck))
            audit_id = f"{lt}:consumable:{ck}"
        else:
            cur = _fetch_one(conn, "SELECT id, loot_table_key, item_key, consumable_key, weapon_key FROM game_config_loot_entries WHERE loot_table_key = ? AND weapon_key = ?", (lt, wk))
            audit_id = f"{lt}:weapon:{wk}"
        if not cur:
            raise KeyError("not_found")
        conn.execute("DELETE FROM game_config_loot_entries WHERE id = ?", (cur["id"],))
        _audit(conn, "game_config_loot_entries", audit_id, "DELETE", dict(cur), None)
        conn.commit()
    finally:
        conn.close()


def _validate_starter_items_json(raw: str | None) -> str:
    if raw is None or not str(raw).strip():
        return "[]"
    try:
        data = json.loads(str(raw))
    except json.JSONDecodeError as e:
        raise ValueError("invalid_starter_items_json") from e
    if not isinstance(data, list):
        raise ValueError("invalid_starter_items_json")
    out: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError("invalid_starter_items_json")
        wk_raw = entry.get("weapon_key")
        ik_raw = entry.get("item_key")
        ck_raw = entry.get("consumable_key")
        wk = str(wk_raw).strip() if wk_raw is not None and str(wk_raw).strip() else None
        ik = str(ik_raw).strip() if ik_raw is not None and str(ik_raw).strip() else None
        ck = str(ck_raw).strip() if ck_raw is not None and str(ck_raw).strip() else None
        if ck and ik and ck != ik:
            raise ValueError("invalid_starter_items_json")
        if ck and not ik:
            ik = ck
        if sum(1 for x in (wk, ik) if x) != 1:
            raise ValueError("invalid_starter_items_json")
        if wk:
            _validate_key(wk)
        else:
            _validate_key(str(ik))
        clean: dict = {}
        if wk:
            clean["weapon_key"] = wk
        else:
            clean["item_key"] = str(ik)
        if entry.get("quantity") is not None:
            q = int(entry["quantity"])
            if q < 1:
                raise ValueError("invalid_starter_items_json")
            clean["quantity"] = q
        out.append(clean)
    return json.dumps(out, ensure_ascii=False)


def list_archetypes() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, description, starter_items_json, starter_gold_gp, is_active,
               locked_at, created_at, updated_at
        FROM game_config_archetypes
        ORDER BY key ASC
        """
    )


def update_archetype(
    key: str,
    *,
    label: str | None = None,
    description: str | None = None,
    starter_items_json: str | None = None,
    starter_gold_gp: int | None = None,
    is_active: bool | None = None,
    force: bool = False,
) -> dict:
    _ = force
    safe_key = str(key or "").strip().lower()
    if not KEY_RE.match(safe_key):
        raise ValueError("invalid_key")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        old = _fetch_one(conn, "SELECT * FROM game_config_archetypes WHERE key = ?", (safe_key,))
        if not old:
            raise KeyError("not_found")
        if old.get("locked_at") and not force:
            raise PermissionError("locked")

        body: dict[str, object] = {}
        if label is not None:
            body["label"] = str(label).strip()
        if description is not None:
            body["description"] = str(description)
        if starter_items_json is not None:
            body["starter_items_json"] = _validate_starter_items_json(starter_items_json)
        if starter_gold_gp is not None:
            g = int(starter_gold_gp)
            if g < 0:
                raise ValueError("invalid_starter_gold_gp")
            body["starter_gold_gp"] = g
        if is_active is not None:
            body["is_active"] = 1 if is_active else 0
        if not body:
            return dict(old)

        sets = ", ".join(f"{k} = ?" for k in body)
        vals = list(body.values())
        vals.append(safe_key)
        conn.execute(
            f"UPDATE game_config_archetypes SET {sets}, updated_at = datetime('now') WHERE key = ?",
            vals,
        )
        new_row = _fetch_one(conn, "SELECT * FROM game_config_archetypes WHERE key = ?", (safe_key,))
        _audit(conn, "game_config_archetypes", safe_key, "UPDATE", old, new_row)
        conn.commit()
        return dict(new_row or {})
    finally:
        conn.close()
