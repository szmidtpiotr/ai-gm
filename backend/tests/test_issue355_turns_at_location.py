"""TDD: Issue #355 C1 — turns_at_location nie jest aktualizowane w streaming path.

Root cause: _update_turns_at_location() istnieje tylko w turn_pipeline.py.
create_turn_log() (używane przez streaming endpoint) nie aktualizuje
session_flags.turns_at_location → STORY_STALE block nigdy nie odpala.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def conn():
    from app.core.db_runtime import resolve_db_path
    c = sqlite3.connect(resolve_db_path())
    c.row_factory = sqlite3.Row
    yield c
    c.close()


@pytest.fixture
def campaign_and_session(conn):
    """Return (campaign_id, character_id) with active game_session. Reset turns_at_location."""
    camp_row = conn.execute(
        "SELECT id FROM campaigns WHERE status != 'deleted' LIMIT 1"
    ).fetchone()
    if not camp_row:
        pytest.skip("No campaign found")
    campaign_id = camp_row["id"]

    char_row = conn.execute(
        "SELECT id FROM characters WHERE campaign_id = ? AND is_active = 1 LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not char_row:
        char_row = conn.execute(
            "SELECT id FROM characters LIMIT 1"
        ).fetchone()
    if not char_row:
        pytest.skip("No character found")
    character_id = char_row["id"]

    gs_row = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not gs_row:
        pytest.skip("No game_session for campaign")

    original_flags = json.loads(gs_row["session_flags"] or "{}")
    original_turns_at = original_flags.get("turns_at_location")
    original_prev_hex = original_flags.get("_prev_turn_hex")

    # Set a known starting state
    flags = dict(original_flags)
    flags["turns_at_location"] = 0
    flags["_prev_turn_hex"] = {"q": 0, "r": 0}
    flags["current_hex"] = {"q": 0, "r": 0}
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(flags, ensure_ascii=False), campaign_id),
    )
    conn.commit()

    yield campaign_id, character_id

    # Restore
    restore_flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()["session_flags"] or "{}")
    if original_turns_at is None:
        restore_flags.pop("turns_at_location", None)
    else:
        restore_flags["turns_at_location"] = original_turns_at
    if original_prev_hex is None:
        restore_flags.pop("_prev_turn_hex", None)
    else:
        restore_flags["_prev_turn_hex"] = original_prev_hex
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(restore_flags, ensure_ascii=False), campaign_id),
    )
    conn.commit()


# ─── Test główny: create_turn_log aktualizuje turns_at_location ─────────────

def test_create_turn_log_increments_turns_at_location(conn, campaign_and_session):
    """create_turn_log must increment turns_at_location when hex doesn't change."""
    from app.api.turns import create_turn_log
    campaign_id, character_id = campaign_and_session

    # hex nie zmieniony (same hex = same as _prev_turn_hex)
    create_turn_log(
        conn=conn,
        campaign_id=campaign_id,
        character_id=character_id,
        user_text="Idę dalej",
        assistant_text="[NARRACJA] Bohater stoi w miejscu.",
        route="narrative",
    )

    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()["session_flags"] or "{}")
    assert flags.get("turns_at_location", 0) >= 1, (
        "turns_at_location must be >= 1 after narrative turn without movement"
    )


def test_create_turn_log_resets_turns_at_location_on_hex_change(conn, campaign_and_session):
    """create_turn_log must reset turns_at_location to 0 when hex changes."""
    from app.api.turns import create_turn_log
    campaign_id, character_id = campaign_and_session

    # Najpierw kilka tur bez ruchu
    for _ in range(3):
        create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=character_id,
            user_text="Czekam",
            assistant_text="[NARRACJA] Nic się nie dzieje.",
            route="narrative",
        )

    # Teraz symuluj zmianę hexu (aktualizuj current_hex w session_flags przed wywołaniem)
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()["session_flags"] or "{}")
    flags["current_hex"] = {"q": 5, "r": 3}  # inny hex niż _prev_turn_hex
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(flags, ensure_ascii=False), campaign_id),
    )
    conn.commit()

    create_turn_log(
        conn=conn,
        campaign_id=campaign_id,
        character_id=character_id,
        user_text="Ruszam do lasu",
        assistant_text="[NARRACJA] Bohater wchodzi do lasu.",
        route="narrative",
    )

    flags_after = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()["session_flags"] or "{}")
    assert flags_after.get("turns_at_location") == 0, (
        f"turns_at_location must reset to 0 after hex change, got {flags_after.get('turns_at_location')}"
    )


def test_story_stale_fires_after_threshold(conn, campaign_and_session):
    """After 5+ turns at same location, context_injector injects STORY_STALE."""
    from app.services.context_injector import ContextInjector
    campaign_id, character_id = campaign_and_session

    # Manually set turns_at_location >= threshold
    flags = json.loads(conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()["session_flags"] or "{}")
    flags["turns_at_location"] = 5
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(flags, ensure_ascii=False), campaign_id),
    )
    conn.commit()

    injector = ContextInjector(conn)
    stale_block = injector._build_stale_block(flags)
    assert "STORY_STALE" in stale_block, (
        f"Expected STORY_STALE in block, got: {stale_block!r}"
    )
    assert "5 tur" in stale_block


def test_story_stale_silent_below_threshold(conn, campaign_and_session):
    """Below threshold: no STORY_STALE injected."""
    from app.services.context_injector import ContextInjector
    campaign_id, character_id = campaign_and_session

    flags = {"turns_at_location": 4}
    injector = ContextInjector(conn)
    stale_block = injector._build_stale_block(flags)
    assert stale_block == "", f"Expected empty string below threshold, got: {stale_block!r}"
