import sqlite3
from fastapi import APIRouter

from app.services.admin_config import list_dc, list_skills, list_stats
from app.services.client_ui_config import get_public_slash_commands


router = APIRouter()
DB_PATH = "/data/ai_gm.db"


def _build_test_descriptions() -> dict[str, str]:
    stats = list_stats()
    skills = list_skills()
    dcs = list_dc()

    stats_by_key = {s.get("key"): (s.get("description") or s.get("label") or "") for s in stats}
    skills_by_key = {s.get("key"): (s.get("description") or s.get("label") or "") for s in skills}

    # Canonical save tests used in roll cues parsing.
    fortitude = stats_by_key.get("CON") or stats_by_key.get("STR") or ""
    reflex = stats_by_key.get("DEX") or ""
    willpower = stats_by_key.get("WIS") or stats_by_key.get("CHA") or ""
    arcane = stats_by_key.get("INT") or ""

    return {
        # Skill tests
        **skills_by_key,
        # Save tests (used by cues: Dex/Con/Wis/Int/Cha Save aliases)
        "fortitude_save": fortitude,
        "reflex_save": reflex,
        "willpower_save": willpower,
        "arcane_save": arcane,
    }


@router.get("/mechanics/metadata")
def get_mechanics_metadata():
    return {
        "test_descriptions": _build_test_descriptions(),
        "dc_tiers": {d.get("key"): (d.get("description") or d.get("label") or "") for d in list_dc()},
    }


@router.get("/mechanics/slash-commands")
def get_slash_commands_public():
    """Chat `/` autocomplete: tylko komendy włączone w adminie (Config → slash commands)."""
    return {"commands": get_public_slash_commands()}

