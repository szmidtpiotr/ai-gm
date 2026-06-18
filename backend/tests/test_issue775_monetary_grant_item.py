"""TDD: Issue #775 — monetary grant_item (mieszek z monetami) must convert to grant_gold."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.turns import extract_grant_cues


# ─── Safety-net: monetary bags convert to gold ────────────────────────────────

def test_monetary_bag_no_amount_defaults_to_ten():
    """'Ciężki mieszek z monetami' (no number) → grant_gold=10, NOT an item."""
    text = "Marta kiwa głową z uznaniem.\nGrant Item Ciężki mieszek z monetami"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert gold is not None, "monetary bag must convert to grant_gold"
    assert gold > 0, "grant_gold must be positive"
    assert "Ciężki mieszek z monetami" not in items, "monetary bag must NOT appear as item"


def test_monetary_bag_with_amount_extracted():
    """'Mieszek z 20 monetami' → grant_gold=20."""
    text = "Oto twoja zapłata.\nGrant Item Mieszek z 20 monetami"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert gold == 20, f"expected 20 GP, got {gold}"
    assert not items, "no regular items"


def test_sakiewka_z_zaplata_converts():
    """'Sakiewka z zapłatą' → grant_gold, not item."""
    text = "Dobra robota.\nGrant Item Sakiewka z zapłatą"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert gold is not None, "sakiewka z zapłatą must produce grant_gold"
    assert "Sakiewka z zapłatą" not in items


def test_maly_mieszek_z_zaplata():
    """'Mały mieszek z zapłatą' (exact bug from #99791) → grant_gold."""
    text = "Oto twoja zapłata za dostawę.\nGrant Item Mały mieszek z zapłatą"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert gold is not None, "Mały mieszek z zapłatą must be grant_gold"
    assert "Mały mieszek z zapłatą" not in items


def test_monetary_bag_in_json_grant_item_field():
    """JSON mode: grant_item='Ciężki mieszek z monetami' → grant_gold, no item."""
    import json
    payload = json.dumps({
        "narration": "Płatnicy przekazują ci nagrodę.",
        "grant_item": "Ciężki mieszek z monetami",
    })
    _, items, gold, _, _ = extract_grant_cues(payload)
    assert gold is not None, "JSON grant_item monetary bag must become grant_gold"
    assert "Ciężki mieszek z monetami" not in items


def test_json_grant_item_with_amount():
    """JSON mode: grant_item={label, description} with amount → correct gold."""
    import json
    payload = json.dumps({
        "narration": "Marta daje ci zapłatę.",
        "grant_item": {"label": "Mieszek z monetami", "description": "Zawiera 15 złotych"},
    })
    _, items, gold, _, _ = extract_grant_cues(payload)
    assert gold == 15, f"expected 15 GP extracted from description, got {gold}"
    assert "Mieszek z monetami" not in items


# ─── Backward compat: non-monetary items unchanged ────────────────────────────

def test_empty_bag_stays_item():
    """'Pusty mieszek' (no money word) must remain a regular item."""
    text = "Oto pusty mieszek na twoje zdobycze.\nGrant Item Pusty mieszek"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert "Pusty mieszek" in items, "empty bag must remain a regular item"
    assert gold is None, "no grant_gold for empty bag"


def test_regular_item_unaffected():
    """'Miecz żelazny' stays as regular item, not gold."""
    text = "Kowal wręcza ci broń.\nGrant Item Miecz żelazny"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert "Miecz żelazny" in items
    assert gold is None


def test_existing_grant_gold_not_overwritten():
    """If grant_gold already set, monetary bag doesn't overwrite it."""
    text = "Dostajesz nagrodę.\nGrant Gold 50\nGrant Item Ciężki mieszek z monetami"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert gold == 50, "explicit Grant Gold 50 must not be overwritten by bag conversion"
