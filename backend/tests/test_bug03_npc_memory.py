"""BUG-03 — campaign_known_npcs persistence + context injection."""

import sqlite3

import pytest

from app.services.npc_memory_service import (
    format_known_npcs_block,
    get_recent_known_npcs,
    record_npc_met,
    update_npc_relation,
)


CAMPAIGN_ID = 99903


@pytest.fixture
def clean_roster():
    conn = sqlite3.connect("/data/ai_gm.db")
    try:
        conn.execute("DELETE FROM campaign_known_npcs WHERE campaign_id = ?", (CAMPAIGN_ID,))
        conn.commit()
    finally:
        conn.close()
    yield CAMPAIGN_ID
    # leave rows behind on teardown for inspection if needed


def test_record_first_meeting_creates_row(clean_roster):
    res = record_npc_met(
        campaign_id=clean_roster,
        name="Marta",
        role="karczmarka",
        first_met_location="Pod Trzema Krukami",
        first_met_turn=3,
        notes="Wysoka, siwiejąca; pamięta klientów",
    )
    assert res["ok"]
    assert res["new"] is True
    rows = get_recent_known_npcs(clean_roster)
    assert len(rows) == 1
    assert rows[0]["npc_name"] == "Marta"
    assert rows[0]["role"] == "karczmarka"
    assert rows[0]["relation_status"] == "neutral"


def test_record_idempotent_on_same_name(clean_roster):
    record_npc_met(campaign_id=clean_roster, name="Marta", role="karczmarka", first_met_turn=1)
    res = record_npc_met(campaign_id=clean_roster, name="Marta", first_met_turn=5, notes="nowa notatka")
    assert res["ok"]
    assert res["new"] is False
    rows = get_recent_known_npcs(clean_roster)
    assert len(rows) == 1
    # notes updated, role preserved
    assert rows[0]["notes"] == "nowa notatka"
    assert rows[0]["role"] == "karczmarka"


def test_first_met_location_is_sticky(clean_roster):
    record_npc_met(
        campaign_id=clean_roster,
        name="Marta",
        first_met_location="Pod Trzema Krukami",
        first_met_turn=1,
    )
    record_npc_met(
        campaign_id=clean_roster,
        name="Marta",
        first_met_location="Inne miejsce",  # should be ignored
        first_met_turn=5,
    )
    rows = get_recent_known_npcs(clean_roster)
    assert rows[0]["first_met_location"] == "Pod Trzema Krukami"


def test_update_relation_to_hostile(clean_roster):
    record_npc_met(campaign_id=clean_roster, name="Marta", first_met_turn=1)
    res = update_npc_relation(
        campaign_id=clean_roster,
        name="Marta",
        relation_status="hostile",
        notes="Wyrzuciła gracza za awanturę",
    )
    assert res["ok"]
    rows = get_recent_known_npcs(clean_roster)
    assert rows[0]["relation_status"] == "hostile"
    assert "awanturę" in rows[0]["notes"]


def test_update_relation_rejects_invalid_status(clean_roster):
    record_npc_met(campaign_id=clean_roster, name="Marta", first_met_turn=1)
    res = update_npc_relation(campaign_id=clean_roster, name="Marta", relation_status="lover")
    assert not res["ok"]


def test_update_relation_returns_not_found_for_unknown(clean_roster):
    res = update_npc_relation(campaign_id=clean_roster, name="Eldran", relation_status="friendly")
    assert not res["ok"]
    assert res["reason"] == "not_found"


def test_get_recent_caps_at_limit(clean_roster):
    for i in range(15):
        record_npc_met(campaign_id=clean_roster, name=f"NPC_{i:02d}", first_met_turn=i)
    rows = get_recent_known_npcs(clean_roster, limit=10)
    assert len(rows) == 10


def test_get_recent_orders_by_updated_desc(clean_roster):
    # SQLite datetime('now') has 1-second resolution, so to test ordering we
    # need a small wait — in production turns are minutes apart so this is
    # not a real concern, but tests run sub-second.
    import time
    record_npc_met(campaign_id=clean_roster, name="A", first_met_turn=1)
    record_npc_met(campaign_id=clean_roster, name="B", first_met_turn=2)
    time.sleep(1.1)
    # touch A again — should move it to the top
    update_npc_relation(campaign_id=clean_roster, name="A", relation_status="hostile")
    rows = get_recent_known_npcs(clean_roster)
    assert rows[0]["npc_name"] == "A"
    assert rows[1]["npc_name"] == "B"


def test_format_known_npcs_block_empty_returns_empty_string():
    assert format_known_npcs_block([]) == ""


def test_format_known_npcs_block_renders_all_fields():
    rows = [
        {
            "npc_name": "Marta",
            "role": "karczmarka",
            "first_met_location": "Pod Trzema Krukami",
            "notes": "Wysoka, surowa",
            "relation_status": "friendly",
            "catalog_description": None,
        },
        {
            "npc_name": "Eldran",
            "role": "mag",
            "first_met_location": "Ruiny",
            "notes": None,
            "relation_status": "hostile",
            "catalog_description": None,
        },
    ]
    block = format_known_npcs_block(rows)
    assert "ZNANI NPC" in block
    assert "Marta (karczmarka)" in block
    assert "Pod Trzema Krukami" in block
    assert "przyjazny" in block
    assert "wrogi" in block
    assert "Wysoka, surowa" in block


def test_record_with_empty_name_rejected():
    res = record_npc_met(campaign_id=CAMPAIGN_ID, name="   ")
    assert not res["ok"]
