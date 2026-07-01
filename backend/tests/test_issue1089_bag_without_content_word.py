"""TDD: Issue #1089 — monetary bag without content-word must convert to gold, not inventory item."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.turns import extract_grant_cues


# ─── RED: bags without money-content-word must still convert ─────────────────

def test_plain_bag_without_content_word_converts():
    """'Prosta sakiewka bandyty' (bag word, NO money content word) → grant_gold, NOT item."""
    text = "Bandyta upada. Przy nim leży mieszek.\nGrant Item Prosta sakiewka bandyty"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert gold is not None, "bag without content word must convert to grant_gold (#1089)"
    assert "Prosta sakiewka bandyty" not in items, "bag must not appear as inventory item"


def test_plain_bag_defaults_to_ten_gp():
    """'Prosta sakiewka bandyty' with no amount → defaults to 10 gp."""
    text = "Grant Item Prosta sakiewka bandyty"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert gold == 10, f"expected default 10 GP, got {gold}"


def test_json_plain_bag_without_content_word_converts():
    """JSON mode: grant_item='Prosta sakiewka bandyty' → grant_gold, no item."""
    import json
    payload = json.dumps({
        "narration": "Bandyta upada.",
        "grant_item": "Prosta sakiewka bandyty",
    })
    _, items, gold, _, _ = extract_grant_cues(payload)
    assert gold is not None, "JSON bag without content word must become grant_gold (#1089)"
    assert "Prosta sakiewka bandyty" not in items


def test_woreczek_without_content_word_converts():
    """'Woreczek bandyty' → grant_gold (no content word required)."""
    text = "Grant Item Woreczek bandyty"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert gold is not None, "woreczek without content word must convert"
    assert "Woreczek bandyty" not in items


# ─── Backward compat: non-monetary bags must remain as items ─────────────────

def test_travel_pouch_stays_as_item():
    """'Sakwa podróżna' (travel pouch, not money bag) must remain a regular item."""
    text = "Dostałeś w nagrodę wygodną torbę.\nGrant Item Sakwa podróżna"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert "Sakwa podróżna" in items, "travel pouch must remain as inventory item"
    assert gold is None, "travel pouch must not produce grant_gold"


def test_empty_bag_stays_as_item():
    """'Pusty mieszek' must remain a regular item (not converted to gold)."""
    text = "Oto pusty mieszek na twoje zdobycze.\nGrant Item Pusty mieszek"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert "Pusty mieszek" in items, "empty bag must remain as item"
    assert gold is None, "empty bag must not produce grant_gold"


def test_existing_bags_with_content_word_still_work():
    """'Ciężki mieszek z monetami' (has content word) must still convert correctly."""
    text = "Grant Item Ciężki mieszek z monetami"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert gold is not None, "bag with content word must still convert"
    assert "Ciężki mieszek z monetami" not in items


def test_regular_item_unaffected():
    """'Miecz żelazny' stays as regular item, not gold."""
    text = "Grant Item Miecz żelazny"
    _, items, gold, _, _ = extract_grant_cues(text)
    assert "Miecz żelazny" in items
    assert gold is None
