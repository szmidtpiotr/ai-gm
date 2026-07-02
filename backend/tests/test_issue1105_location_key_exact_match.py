"""TDD: Issue #1105 — validate_move ignores intent.target_key and can teleport
the player to an unrelated location when the LLM's target_label diverges from
the DB label (e.g. GM said "Volhynia: Gospoda Szlaku" while the DB row is
labeled "Gospoda Szlaku" under a differently-named macro). An exact target_key
match must always win over fuzzy label guessing."""
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.migrations_admin import DB_PATH
from app.services.location_intent_parser import LocationIntent
from app.services.location_validator import validate_move

client = TestClient(app)


def get_admin_token():
    resp = client.post("/api/admin/dev-login", json={"username": "admin", "password": "admin"})
    if resp.status_code == 200:
        return resp.json()["token"]
    resp2 = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    return resp2.json()["token"]


def _create_location(token, key, label, location_type="macro", parent_id=None):
    resp = client.post(
        "/api/locations",
        json={"key": key, "label": label, "location_type": location_type, "parent_id": parent_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_session_without_current_location(campaign_id: int) -> int:
    """Session with current_location_id = NULL — mirrors the production 999989
    state where the LOC-3 graph guard fails open (empty available_keys) and
    validate_move falls into its 'brak aktualnej lokalizacji' branch."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO game_sessions (id, campaign_id, session_flags) VALUES (?, ?, '{}')",
            (campaign_id, campaign_id),
        )
        conn.commit()
    finally:
        conn.close()
    return campaign_id


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_exact_target_key_wins_over_fuzzy_label_mismatch():
    """#1105: intent.target_key that exactly matches a DB row must resolve to
    THAT row even when target_label (as phrased by the LLM) scores below the
    fuzzy threshold against the DB's stored label — never fall through to a
    different, unrelated location."""
    token = get_admin_token()
    ts = time.time()

    # Target sub-location: DB label is short ("Gospoda Szlaku"), but the GM's
    # narration phrases it with a region prefix ("Volhynia: Gospoda Szlaku"),
    # which scores well under FUZZY_MATCH_THRESHOLD=80 against the DB label.
    parent = _create_location(token, f"test_volhynia_{ts}", "Volhynia")
    target_key = f"test_gospoda_szlaku_{ts}"
    target = _create_location(
        token, target_key, "Gospoda Szlaku", location_type="sub", parent_id=parent["id"]
    )
    # Decoy: an unrelated macro location that must NEVER be picked.
    decoy = _create_location(token, f"test_tundra_mrozu_{ts}", "Tundra Wiecznego Mrozu")

    campaign_id = int(ts * 1000) % 2_000_000_000
    _make_session_without_current_location(campaign_id)

    intent = LocationIntent(
        action="move",
        target_label="Volhynia: Gospoda Szlaku",
        target_key=target_key,
    )

    result = validate_move(campaign_id, intent, campaign_id=campaign_id)

    assert result.allowed is True, f"move was blocked: {result.block_reason}"
    assert result.is_new_location is False, (
        "must reuse the existing DB row for target_key, not mint a duplicate 'zamiennik'"
    )
    assert result.resolved_location_id == target["id"], (
        f"expected exact-key target {target['id']} ({target_key}), "
        f"got {result.resolved_location_id} (decoy id={decoy['id']})"
    )
    assert result.resolved_location_id != decoy["id"]


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_fuzzy_label_match_still_works_without_target_key():
    """Legacy intents (no target_key) must still resolve via fuzzy label match."""
    token = get_admin_token()
    ts = time.time()

    label = f"Karczma Pod Unikalnym Szyldem {ts}"
    target = _create_location(token, f"test_karczma_{ts}", label)

    campaign_id = int(ts * 1000) % 2_000_000_000 + 1
    _make_session_without_current_location(campaign_id)

    intent = LocationIntent(action="move", target_label=label)

    result = validate_move(campaign_id, intent, campaign_id=campaign_id)

    assert result.allowed is True, f"move was blocked: {result.block_reason}"
    assert result.resolved_location_id == target["id"]
