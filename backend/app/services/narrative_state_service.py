"""Narrative State — D6 (#381). Per game_mechanics.md CZĘŚĆ Y.

Layer 2 of the narrative context: what happened (`events`) + what was promised
or planted (`seeds`). The GM emits tags during a turn; the backend parses them,
accumulates them in a bounded NarrativeState structure, strips the tags from the
player-facing narrative, and injects a compressed block on later turns so the LLM
keeps continuity instead of forgetting after N turns.

Tags:
- [NARRATIVE_EVENT: key=..., note=...]  → key event (for the running summary)
- [NARRATIVE_SEED: key=..., hint=...]   → promise/hook to pay off later

NarrativeState shape:
    {events: [{key, note, turn}], seeds: [{key, hint, status, planted_turn}],
     chapter_summaries: [{turns, summary}], current_situation: str}
"""
from __future__ import annotations

import re
from typing import Any

NARRATIVE_EVENT_RE = re.compile(
    r"\[NARRATIVE_EVENT:\s*key=([^,\]]+?)\s*,\s*note=([^\]]+?)\s*\]", re.IGNORECASE
)
NARRATIVE_SEED_RE = re.compile(
    r"\[NARRATIVE_SEED:\s*key=([^,\]]+?)\s*,\s*hint=([^\]]+?)\s*\]", re.IGNORECASE
)
_ANY_NARRATIVE_RE = re.compile(r"\[NARRATIVE_(?:EVENT|SEED):[^\]]*\]", re.IGNORECASE)

MAX_EVENTS = 30
MAX_SEEDS = 20


def parse_narrative_event_tags(text: str) -> list[tuple[str, str]]:
    """Extract (key, note) pairs from [NARRATIVE_EVENT: key=..., note=...] tags."""
    out: list[tuple[str, str]] = []
    for m in NARRATIVE_EVENT_RE.finditer(text or ""):
        key = (m.group(1) or "").strip()
        note = (m.group(2) or "").strip()
        if key and note:
            out.append((key, note))
    return out


def parse_narrative_seed_tags(text: str) -> list[tuple[str, str]]:
    """Extract (key, hint) pairs from [NARRATIVE_SEED: key=..., hint=...] tags."""
    out: list[tuple[str, str]] = []
    for m in NARRATIVE_SEED_RE.finditer(text or ""):
        key = (m.group(1) or "").strip()
        hint = (m.group(2) or "").strip()
        if key and hint:
            out.append((key, hint))
    return out


def strip_narrative_tags(text: str) -> str:
    """Remove all [NARRATIVE_EVENT/SEED:...] tags from the player-facing narrative."""
    if not text:
        return text or ""
    return _ANY_NARRATIVE_RE.sub("", text).strip()


def empty_narrative_state() -> dict[str, Any]:
    return {"events": [], "seeds": [], "chapter_summaries": [], "current_situation": ""}


def apply_narrative_tags(
    state: dict | None,
    *,
    events: Any = (),
    seeds: Any = (),
    turn: int = 0,
    max_events: int = MAX_EVENTS,
    max_seeds: int = MAX_SEEDS,
) -> dict[str, Any]:
    """Accumulate parsed events/seeds into a NarrativeState (dedup by key, capped)."""
    st = dict(state or empty_narrative_state())
    st.setdefault("events", [])
    st.setdefault("seeds", [])
    st.setdefault("chapter_summaries", [])
    st.setdefault("current_situation", "")

    ev_keys = {e.get("key") for e in st["events"] if isinstance(e, dict)}
    for key, note in events:
        if key and key not in ev_keys:
            st["events"].append({"key": key, "note": note, "turn": int(turn)})
            ev_keys.add(key)
    st["events"] = st["events"][-max_events:]

    seed_keys = {s.get("key") for s in st["seeds"] if isinstance(s, dict)}
    for key, hint in seeds:
        if key and key not in seed_keys:
            st["seeds"].append(
                {"key": key, "hint": hint, "status": "active", "planted_turn": int(turn)}
            )
            seed_keys.add(key)
    st["seeds"] = st["seeds"][-max_seeds:]

    return st


def format_narrative_state_block(state: dict | None, *, max_events: int = 8, max_seeds: int = 6) -> str:
    """Render a compressed Polish NARRATIVE STATE block for context injection.

    Empty string when there is nothing to inject. Only `active` seeds are shown.
    """
    if not state:
        return ""
    events = [e for e in (state.get("events") or []) if isinstance(e, dict)][-max_events:]
    seeds = [s for s in (state.get("seeds") or [])
             if isinstance(s, dict) and str(s.get("status") or "active") == "active"][-max_seeds:]
    situation = str(state.get("current_situation") or "").strip()
    if not events and not seeds and not situation:
        return ""

    lines: list[str] = ["### NARRATIVE STATE (pamięć fabularna — zachowaj ciągłość)"]
    if situation:
        lines.append(f"Sytuacja: {situation}")
    if events:
        lines.append("Co się wydarzyło:")
        for e in events:
            lines.append(f"- {e.get('note') or e.get('key')}")
    if seeds:
        lines.append("Zasiane wątki (do wykorzystania):")
        for s in seeds:
            lines.append(f"- {s.get('hint') or s.get('key')}")
    return "\n".join(lines)
