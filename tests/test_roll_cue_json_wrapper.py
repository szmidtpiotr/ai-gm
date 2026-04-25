"""Roll cue validation when assistant reply is JSON (narrative + location_intent)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api import turns as turns_api


def test_roll_cue_json_location_intent_null():
    payload = {
        "narrative": "Pierwsza linia.\n\nDruga.\nRoll Stealth d20",
        "location_intent": None,
    }
    assert turns_api.validate_roll_cue_name(json.dumps(payload, ensure_ascii=False)) == "stealth"


def test_roll_cue_json_location_intent_move():
    payload = {
        "narrative": "Idziesz.\n\nNapięcie.\nRoll Athletics d20",
        "location_intent": {
            "action": "move",
            "target_label": "Rynek",
            "target_key": "market_square",
        },
    }
    assert turns_api.validate_roll_cue_name(json.dumps(payload, ensure_ascii=False)) == "athletics"


def test_roll_cue_json_location_intent_create():
    payload = {
        "narrative": "Odkrywasz szczelinę.\n\nZimno.\nRoll Arcana d20",
        "location_intent": {
            "action": "create",
            "target_label": "Jaskinia",
            "parent_key": "city_varen",
            "description": "mroczna szczelina",
        },
    }
    assert turns_api.validate_roll_cue_name(json.dumps(payload, ensure_ascii=False)) == "arcana"


def test_roll_cue_from_narrative_not_outer_json_last_line():
    """Pretty-printed JSON ends with `}`; cue must come from narrative last line."""
    payload = {
        "narrative": "Opis.\n\nRoll Lore d20",
        "location_intent": None,
    }
    blob = json.dumps(payload, ensure_ascii=False, indent=2)
    assert blob.strip().splitlines()[-1].strip() == "}"
    assert turns_api.validate_roll_cue_name(blob) == "lore"


def test_roll_cue_fallback_raw_non_json():
    raw = "Narracja bez JSON.\n\nRoll Medicine d20"
    assert turns_api.validate_roll_cue_name(raw) == "medicine"


def test_json_without_narrative_falls_back_to_raw():
    """No narrative key: full string used; last line has no valid Roll cue."""
    assert turns_api.validate_roll_cue_name('{"foo": 1, "bar": 2}') is None
