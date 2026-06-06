"""C11: Quest auto-completion checker.

check_kill_quest(active_quests, enemy_name)     → (updated_quests, completed_quests)
check_location_quest(active_quests, loc_name)   → (updated_quests, completed_quests)
parse_reward(reward_text)                       → {"xp": N, "gold": N}
"""
from __future__ import annotations
import re
from typing import Optional


def parse_reward(reward_text: Optional[str]) -> dict:
    """Extract XP and gold amounts from freetext reward string."""
    if not reward_text:
        return {"xp": 0, "gold": 0}

    xp = 0
    gold = 0

    xp_match = re.search(r'(\d+)\s*(?:XP|xp|Xp)', reward_text)
    if xp_match:
        xp = int(xp_match.group(1))

    gold_match = re.search(r'(\d+)\s*(?:z[łl]otych|gold|gp|GP|złotych)', reward_text, re.IGNORECASE)
    if gold_match:
        gold = int(gold_match.group(1))

    return {"xp": xp, "gold": gold}


def _keyword_match(objective: str, name: str) -> bool:
    """True if any word from `name` matches a word in `objective` (case-insensitive).

    Uses prefix matching to handle Polish declension (Skrzypek / Skrzypa → stem skrzyp).
    A word matches if objective contains it exactly, or if they share a prefix of
    max(4, len(word)-2) characters.
    """
    obj_lower = objective.lower()
    for word in name.lower().split():
        if len(word) < 3:
            continue
        if word in obj_lower:
            return True
        # prefix match for declined forms
        prefix_len = max(4, len(word) - 2)
        if len(word) >= prefix_len:
            prefix = word[:prefix_len]
            for obj_word in obj_lower.split():
                if obj_word.startswith(prefix) or word.startswith(obj_word[:prefix_len]):
                    return True
    return False


def check_kill_quest(
    active_quests: Optional[list], enemy_name: str
) -> tuple[list, list]:
    """Mark quests whose objective matches enemy_name as completed.

    Returns (updated_quests, completed_quests). Does not mutate the input list.
    """
    if not active_quests:
        return [], []

    updated = []
    completed = []
    for q in active_quests:
        if q.get("status") == "active" and _keyword_match(q.get("objective", ""), enemy_name):
            q = dict(q, status="completed")
            completed.append(q)
        updated.append(q)
    return updated, completed


def check_location_quest(
    active_quests: Optional[list], location_name: str
) -> tuple[list, list]:
    """Mark quests whose objective matches location_name as completed.

    Returns (updated_quests, completed_quests). Does not mutate the input list.
    """
    if not active_quests:
        return [], []

    updated = []
    completed = []
    for q in active_quests:
        if q.get("status") == "active" and _keyword_match(q.get("objective", ""), location_name):
            q = dict(q, status="completed")
            completed.append(q)
        updated.append(q)
    return updated, completed
