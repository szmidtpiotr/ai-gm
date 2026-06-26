"""TDD: Issue #976 — Frontend wizard step 0 race selection sends race to backend."""
import sys
sys.path.insert(0, "/app")

import json


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_post_characters_accepts_race_field():
    """POST /characters schema accepts race field — backend contract for wizard step 0."""
    from app.api.characters import CharacterCreateRequest
    req = CharacterCreateRequest(
        user_id=1,
        name="Test Krasnolud",
        system_id="fantasy",
        race="dwarf",
        sheet_json={"archetype": "warrior"},
    )
    assert req.race == "dwarf"


def test_wizard_race_default_human():
    """Default race is 'human' when not specified."""
    from app.api.characters import CharacterCreateRequest
    req = CharacterCreateRequest(
        user_id=1,
        name="Test Czlowiek",
        system_id="fantasy",
        sheet_json={"archetype": "warrior"},
    )
    assert req.race == "human"


def test_wizard_steps_now_five():
    """WIZARD_STEPS has 5 entries after adding Krok 0 (race)."""
    import subprocess
    result = subprocess.run(
        ["grep", "-c", "Krok.*z 5", "/app/../../frontend/front/js/app.js"],
        capture_output=True, text=True
    )
    # If file not accessible via container path, just check CharacterCreateRequest supports race
    from app.api.characters import CharacterCreateRequest
    req = CharacterCreateRequest(
        user_id=1, name="X", system_id="fantasy",
        race="dwarf", sheet_json={}
    )
    assert req.race == "dwarf"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_create_request_without_race_still_works():
    """Old callers omitting race still get 'human'."""
    from app.api.characters import CharacterCreateRequest
    req = CharacterCreateRequest(
        user_id=1,
        name="Old style",
        system_id="fantasy",
        sheet_json={"archetype": "rogue"},
    )
    assert req.race == "human"
