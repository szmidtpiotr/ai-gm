"""TDD: Issue #365 — C11 mechaniczne śledzenie postępu questów.

Tests for quest_checker.py:
- check_kill_quest(active_quests, enemy_name) → updated_quests, completed
- check_location_quest(active_quests, location_name) → updated_quests, completed
- parse_reward(reward_text) → {"xp": N, "gold": N}
"""
import sys
sys.path.insert(0, "/app")

from app.services.quest_checker import (
    check_kill_quest,
    check_location_quest,
    parse_reward,
)

# ─── parse_reward ────────────────────────────────────────────────────────────

def test_parse_reward_xp_only():
    """'50 XP' → xp=50, gold=0."""
    r = parse_reward("50 XP")
    assert r["xp"] == 50
    assert r["gold"] == 0


def test_parse_reward_gold_zlotych():
    """'30 złotych' → xp=0, gold=30."""
    r = parse_reward("30 złotych")
    assert r["xp"] == 0
    assert r["gold"] == 30


def test_parse_reward_gold_gp():
    """'20 GP' → xp=0, gold=20."""
    r = parse_reward("20 GP")
    assert r["xp"] == 0
    assert r["gold"] == 20


def test_parse_reward_both():
    """'50 XP i 30 złotych' → xp=50, gold=30."""
    r = parse_reward("50 XP i 30 złotych")
    assert r["xp"] == 50
    assert r["gold"] == 30


def test_parse_reward_empty():
    """Empty/None reward → xp=0, gold=0."""
    assert parse_reward("") == {"xp": 0, "gold": 0}
    assert parse_reward(None) == {"xp": 0, "gold": 0}


# ─── check_kill_quest ────────────────────────────────────────────────────────

def test_check_kill_quest_exact_match():
    """Quest objective contains enemy name (exact) → quest completed."""
    quests = [{"title": "Zabij Skrzypa", "objective": "zabij bandytę Skrzypa",
               "reward": "50 XP", "status": "active"}]
    updated, completed = check_kill_quest(quests, "Skrzypek")
    assert len(completed) == 1
    assert completed[0]["title"] == "Zabij Skrzypa"
    assert updated[0]["status"] == "completed"


def test_check_kill_quest_case_insensitive():
    """Matching should be case-insensitive."""
    quests = [{"title": "Zabij wilka", "objective": "Pokonaj WILKA leśnego",
               "reward": "30 XP", "status": "active"}]
    updated, completed = check_kill_quest(quests, "wilk leśny")
    assert len(completed) == 1


def test_check_kill_quest_no_match():
    """Enemy unrelated to quest → quest stays active."""
    quests = [{"title": "Zabij smoka", "objective": "zabij smoka górskiego",
               "reward": "200 XP", "status": "active"}]
    updated, completed = check_kill_quest(quests, "szczur")
    assert len(completed) == 0
    assert updated[0]["status"] == "active"


def test_check_kill_quest_already_completed_skipped():
    """Already completed quest is not touched."""
    quests = [{"title": "Stary quest", "objective": "zabij goblina",
               "reward": "10 XP", "status": "completed"}]
    updated, completed = check_kill_quest(quests, "goblin")
    assert len(completed) == 0


def test_check_kill_quest_empty_list():
    """Empty quest list → no crash."""
    updated, completed = check_kill_quest([], "goblin")
    assert updated == []
    assert completed == []


# ─── check_location_quest ───────────────────────────────────────────────────

def test_check_location_quest_match():
    """Quest objective contains location name → completed."""
    quests = [{"title": "Idź do karczmy", "objective": "dotrzyj do Karczmy Pod Koroną",
               "reward": "20 XP", "status": "active"}]
    updated, completed = check_location_quest(quests, "karczma pod koroną")
    assert len(completed) == 1
    assert updated[0]["status"] == "completed"


def test_check_location_quest_no_match():
    """Different location → quest stays active."""
    quests = [{"title": "Idź do zamku", "objective": "dotrzyj do zamku Skalna",
               "reward": "40 XP", "status": "active"}]
    updated, completed = check_location_quest(quests, "las mroczny")
    assert len(completed) == 0


def test_check_location_quest_empty_list():
    """Empty quests → no crash."""
    updated, completed = check_location_quest([], "las")
    assert updated == []
    assert completed == []


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_no_quests_no_crash():
    """Functions handle None gracefully."""
    u, c = check_kill_quest(None, "goblin")
    assert u == []
    assert c == []
