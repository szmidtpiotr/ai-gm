from __future__ import annotations

import json
from typing import Any, Dict, Optional


CONSUMABLE_IMMEDIATE_EFFECTS = {"heal_hp", "restore_mana", "remove_condition", "add_condition"}


def _normalize_condition_key(value: Any) -> Optional[str]:
    key = str(value or "").strip().lower()
    if not key or key in {"self", "any"}:
        return None
    return key


def _effect_value(effect_dice: Any, effect_bonus: Any) -> int | str:
    dice = str(effect_dice or "").strip()
    if dice:
        return dice
    try:
        bonus = int(effect_bonus or 0)
    except (TypeError, ValueError):
        bonus = 0
    return bonus


def _decode_effect_json(raw: Any) -> Optional[dict[str, Any]]:
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


def convert_flat_effect_to_payload(
    effect_type: Any,
    effect_dice: Any,
    effect_bonus: Any,
    effect_target: Any,
) -> Optional[Dict[str, Any]]:
    """Return a consumable effect_json payload when it can be inferred from legacy columns."""
    raw_type = str(effect_type or "").strip().lower()
    if not raw_type or raw_type not in CONSUMABLE_IMMEDIATE_EFFECTS:
        return None

    if raw_type in {"heal_hp", "restore_mana"}:
        effect: Dict[str, Any] = {"type": raw_type}
        value = _effect_value(effect_dice, effect_bonus)
        effect["value"] = value
        return {
            "schema_version": 1,
            "effect_category": "consumable_immediate",
            "effects": [effect],
        }

    condition_key = _normalize_condition_key(effect_target)
    if not condition_key:
        return None

    if raw_type == "remove_condition":
        eff_type = "remove_condition"
    else:
        # convert legacy add_condition to new apply_condition type
        eff_type = "apply_condition"

    return {
        "schema_version": 1,
        "effect_category": "consumable_immediate",
        "effects": [
            {
                "type": eff_type,
                "condition_key": condition_key,
            }
        ],
    }


def normalize_flat_effect_to_json(
    effect_type: Any,
    effect_dice: Any,
    effect_bonus: Any,
    effect_target: Any,
) -> Optional[str]:
    payload = convert_flat_effect_to_payload(effect_type, effect_dice, effect_bonus, effect_target)
    if not payload:
        return None
    # Use admin_config for canonical formatting + validation
    from app.services.admin_config import normalize_effect_json_value

    return normalize_effect_json_value(payload)


def legacy_effect_fields_from_json(effect_json: Any) -> Optional[Dict[str, Any]]:
    """Best-effort legacy projection used by old admin/UI paths after T25 drops effect_* columns."""
    payload = _decode_effect_json(effect_json)
    if not payload:
        return None
    effects = payload.get("effects")
    if not isinstance(effects, list) or len(effects) != 1 or not isinstance(effects[0], dict):
        return None

    effect = effects[0]
    effect_type = str(effect.get("type") or "").strip().lower()
    out: Dict[str, Any] = {
        "effect_type": None,
        "effect_dice": None,
        "effect_bonus": 0,
        "effect_target": "self",
    }

    if effect_type in {"heal_hp", "restore_mana"}:
        out["effect_type"] = effect_type
        value = effect.get("value")
        if isinstance(value, str) and value.strip():
            out["effect_dice"] = value.strip()
        else:
            try:
                out["effect_bonus"] = int(value or 0)
            except (TypeError, ValueError):
                out["effect_bonus"] = 0
        return out

    if effect_type in {"apply_condition", "remove_condition"}:
        condition_key = _normalize_condition_key(effect.get("condition_key"))
        if not condition_key:
            return None
        out["effect_type"] = "add_condition" if effect_type == "apply_condition" else "remove_condition"
        out["effect_target"] = condition_key
        return out

    if effect_type == "static_stat_modifier":
        out["effect_type"] = "stat_buff"
        return out

    if effect_type == "narrative_only":
        out["effect_type"] = "misc"
        return out

    return None
