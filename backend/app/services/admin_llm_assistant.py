from __future__ import annotations

import json
from typing import Any


ADMIN_ASSISTANT_RESOURCE_PROMPTS: dict[str, dict[str, Any]] = {
    "skills": {
        "title": "Skill",
        "summary": "Create a gameplay skill entry.",
        "rules": [
            "Use lowercase snake_case for `key`.",
            "Pick an existing stat key for `linked_stat`: STR, DEX, CON, INT, WIS, CHA, LCK.",
            "Return a short admin-friendly description.",
        ],
        "fields": ["key", "label", "linked_stat", "rank_ceiling", "sort_order", "description"],
    },
    "weapons": {
        "title": "Weapon",
        "summary": "Create a weapon or spell-like weapon record.",
        "rules": [
            "Use lowercase snake_case for `key`.",
            "Use `weapon_type` from: melee, ranged, spell.",
            "Use `targeting` from: single, aoe_radius.",
            "Return `allowed_classes` as an array with warrior/ranger/scholar values.",
        ],
        "fields": [
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
            "targeting",
            "aoe_radius_m",
            "magic_school",
            "value_gp",
            "weight_kg",
            "note",
            "is_active",
        ],
    },
    "enemies": {
        "title": "Enemy",
        "summary": "Create an enemy catalog record.",
        "rules": [
            "Use lowercase snake_case for `key`.",
            "Use `tier` from: weak, standard, elite, boss.",
            "Use `damage_type` from: physical, magic, fire, poison, misc.",
            "Return `conditions_immune` as an array of condition keys.",
            "Return `skills_json` as an object mapping skill_key -> rank integer.",
        ],
        "fields": [
            "key",
            "label",
            "hp_base",
            "ac_base",
            "attack_bonus",
            "dex_modifier",
            "damage_die",
            "description",
            "tier",
            "attacks_per_turn",
            "damage_bonus",
            "damage_type",
            "xp_award",
            "conditions_immune",
            "skills_json",
            "loot_table_key",
            "drop_chance",
            "note",
            "is_active",
        ],
    },
    "conditions": {
        "title": "Condition",
        "summary": "Create a condition with effect_json schema v1.",
        "rules": [
            "Use lowercase snake_case for `key`.",
            "Return `effect_json` as a JSON object, not a string.",
            "Use `schema_version: 1`.",
            "Use `effect_category` from: character_condition, gear_bonus, consumable_immediate, aura.",
        ],
        "fields": ["key", "label", "effect_json", "description", "stackable", "auto_remove", "is_active"],
    },
    "items": {
        "title": "Item",
        "summary": "Create a catalog item record.",
        "rules": [
            "Use lowercase snake_case for `key`.",
            "Use `item_type` from: weapon, armor, consumable, misc, quest, narrative.",
            "Return `allowed_classes` as an array of warrior/ranger/scholar values.",
            "If the item has mechanics, prefer `effect_json` as a JSON object instead of legacy effect_* fields.",
        ],
        "fields": [
            "key",
            "label",
            "item_type",
            "description",
            "value_gp",
            "weight_kg",
            "allowed_classes",
            "ac_bonus",
            "charges",
            "effect_json",
            "note",
            "is_active",
        ],
    },
    "consumables": {
        "title": "Consumable",
        "summary": "Create a legacy consumable record for the admin item tab.",
        "rules": [
            "Use lowercase snake_case for `key`.",
            "Use `effect_type` from: heal_hp, restore_mana, remove_condition, add_condition, stat_buff, misc.",
            "If `effect_dice` is used, format it like 2d4.",
            "Use `effect_target` from: self, ally, any.",
        ],
        "fields": [
            "key",
            "label",
            "description",
            "effect_type",
            "effect_dice",
            "effect_bonus",
            "effect_target",
            "weight_kg",
            "charges",
            "value_gp",
            "note",
            "is_active",
        ],
    },
    "loot-tables": {
        "title": "Loot Table",
        "summary": "Create a loot table shell.",
        "rules": [
            "Use lowercase snake_case for `key`.",
            "Use non-negative integers for `gold_min` and `gold_max`.",
            "Keep `gold_min <= gold_max`.",
        ],
        "fields": ["key", "label", "description", "is_active", "gold_min", "gold_max"],
    },
}


def supported_admin_assistant_resources() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for resource, cfg in ADMIN_ASSISTANT_RESOURCE_PROMPTS.items():
        items.append(
            {
                "resource": resource,
                "title": str(cfg["title"]),
                "summary": str(cfg["summary"]),
            }
        )
    return items


def build_admin_assistant_messages(
    *,
    resource: str,
    history: list[dict[str, str]] | None,
    message: str,
) -> list[dict[str, str]]:
    cfg = ADMIN_ASSISTANT_RESOURCE_PROMPTS.get(resource)
    if not cfg:
        raise ValueError("unsupported_resource")

    rules = "\n".join(f"- {rule}" for rule in cfg.get("rules", []))
    fields = ", ".join(str(field) for field in cfg.get("fields", []))
    system = (
        "You are an RPG admin assistant helping an operator create structured catalog records.\n"
        f"Target resource: {cfg['title']}.\n"
        f"Goal: {cfg['summary']}\n"
        "You must return valid JSON only, with this exact object shape:\n"
        '{\n'
        '  "reply": "krótkie wyjaśnienie po polsku dla admina",\n'
        '  "draft": { ... resource payload ... }\n'
        '}\n'
        "LANGUAGE RULE (highest priority): This is a Polish-language dark fantasy RPG. "
        "ALL user-visible text fields MUST be written in Polish. "
        "This includes: `label`, `description`, `note`, `reply`, and any narrative text. "
        "Technical identifiers (`key`, `linked_stat`, `weapon_type`, `tier`, etc.) stay in English snake_case.\n"
        "Rules:\n"
        f"{rules}\n"
        f"Preferred fields for this resource: {fields}.\n"
        "Do not wrap the JSON in markdown fences. Do not add commentary outside JSON.\n"
        "If the user asks for changes, keep the previous intent from the conversation history and return a fully updated `draft` object."
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for item in history or []:
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message.strip()})
    return messages


def extract_admin_assistant_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty_llm_response")
    start = text.find("{")
    if start < 0:
        raise ValueError("missing_json_object")
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(text, start)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json_object") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid_json_object")
    reply = payload.get("reply")
    draft = payload.get("draft")
    if not isinstance(reply, str) or not reply.strip():
        raise ValueError("missing_reply")
    if not isinstance(draft, dict):
        raise ValueError("missing_draft")
    return {"reply": reply.strip(), "draft": draft}
