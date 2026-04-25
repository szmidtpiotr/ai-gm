import json
from dataclasses import dataclass

from app.services.llm_service import generate_chat
from app.services.location_integrity_config import get_effective_flag


@dataclass
class LocationIntent:
    action: str | None  # 'move' | 'create' | None
    target_label: str
    target_key: str | None
    parent_key: str | None
    description: str | None


def _extract_json_object(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(raw[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


def _intent_from_payload(payload: dict) -> LocationIntent | None:
    li = payload.get("location_intent")
    if not isinstance(li, dict):
        return None
    target_label = str(li.get("target_label") or "").strip()
    if not target_label:
        return None
    action = str(li.get("action") or "").strip().lower() or None
    if action not in {"move", "create"}:
        action = None
    target_key = str(li.get("target_key") or "").strip() or None
    parent_key = str(li.get("parent_key") or "").strip() or None
    description = str(li.get("description") or "").strip() or None
    return LocationIntent(
        action=action,
        target_label=target_label,
        target_key=target_key,
        parent_key=parent_key,
        description=description,
    )


def _fallback_prompt_parse(gm_response: str, llm_config: dict[str, str] | None) -> LocationIntent | None:
    messages = [
        {
            "role": "system",
            "content": (
                "Przeanalizuj narrację i odpowiedz TYLKO w JSON: "
                '{"moved": true/false, "target_label": "nazwa lub null"}'
            ),
        },
        {"role": "user", "content": f"Narracja: {gm_response}"},
    ]
    out = generate_chat(messages=messages, llm_config=llm_config)
    parsed = _extract_json_object(out)
    if not isinstance(parsed, dict):
        return None
    moved = bool(parsed.get("moved"))
    target_label = str(parsed.get("target_label") or "").strip()
    if not moved or not target_label:
        return None
    return LocationIntent(
        action="move",
        target_label=target_label,
        target_key=None,
        parent_key=None,
        description=None,
    )


def parse_location_intent(
    gm_response: str,
    campaign_id: int,
    llm_config: dict[str, str] | None = None,
) -> LocationIntent | None:
    if not gm_response:
        return None

    json_enabled = get_effective_flag("location_parser_json_enabled", campaign_id)
    fallback_enabled = get_effective_flag("location_parser_fallback_enabled", campaign_id)

    if json_enabled:
        try:
            payload = _extract_json_object(gm_response)
            if isinstance(payload, dict):
                intent = _intent_from_payload(payload)
                if intent:
                    return intent
        except Exception:
            # Parser errors must not stop gameplay.
            pass

    if fallback_enabled:
        try:
            return _fallback_prompt_parse(gm_response, llm_config=llm_config)
        except Exception:
            return None
    return None
