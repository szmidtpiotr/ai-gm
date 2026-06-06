"""C10: QUEST_SUGGEST tag parser.

Format: [QUEST_SUGGEST: title | objective | reward]

parse_quest_suggest() — extracts valid quest dicts from LLM narrative text.
strip_quest_suggest_tags() — removes all [QUEST_SUGGEST:...] tags from text.
"""
from __future__ import annotations
import re
from typing import Optional

_RE = re.compile(r'\[QUEST_SUGGEST:\s*([^|\]]+?)\s*\|\s*([^|\]]+?)\s*\|\s*([^|\]]+?)\s*\]', re.IGNORECASE)


def parse_quest_suggest(text: Optional[str]) -> list[dict]:
    """Return list of validated quest dicts found in text. Never raises."""
    if not text:
        return []
    quests = []
    for m in _RE.finditer(text):
        title     = m.group(1).strip()
        objective = m.group(2).strip()
        reward    = m.group(3).strip()
        if title and objective and reward:
            quests.append({
                "title":     title,
                "objective": objective,
                "reward":    reward,
                "status":    "active",
            })
    return quests


def strip_quest_suggest_tags(text: Optional[str]) -> str:
    """Remove [QUEST_SUGGEST:...] tags from text. Never raises."""
    if not text:
        return ""
    return _RE.sub("", text).strip()
