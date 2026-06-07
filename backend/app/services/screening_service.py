"""Auto-screening of the admin review queue — D4 (#379).

Two levels:
- L1 (`validate_level1`): mechanical validation — required fields, valid enums,
  sane numeric ranges. Deterministic, no LLM.
- L2 (`score_level2`): LLM scoring 0-100 of how well the record fits the game
  world. Injectable (`score_fn`) so it can be tested deterministically.

Decision (`decide_screening`): a record auto-approves only when it passes L1 AND
its L2 score is above the threshold (default 80). Anything else stays in the
admin queue. L1 is a hard gate — a high LLM score can never rescue a record that
fails mechanical validation.

`auto_screen_record` ties it together: load → L1 → (L2) → decide → approve.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Any, Callable

DEFAULT_THRESHOLD = 80

_VALID_TIERS = {"weak", "standard", "elite", "boss"}
_VALID_ITEM_TYPES = {"weapon", "armor", "consumable", "misc", "quest", "narrative"}
_VALID_STATS = {"STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"}
_DICE_RE = re.compile(r"^\d*d\d+$", re.IGNORECASE)

_TABLE_BY_TYPE = {
    "enemy": "game_config_enemies",
    "item": "game_config_items",
    "weapon": "game_config_weapons",
    "npc": "npcs",
    "location": "game_locations",
}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_level1(entity_type: str, record: dict) -> dict:
    """Level 1 — mechanical validation. Returns {passed: bool, errors: [str]}."""
    errors: list[str] = []
    label = str(record.get("label") or "").strip()
    if not label:
        errors.append("brak nazwy (label)")

    if entity_type == "enemy":
        if _as_int(record.get("hp_base")) <= 0:
            errors.append("hp_base musi być > 0")
        if _as_int(record.get("ac_base")) <= 0:
            errors.append("ac_base musi być > 0")
        if not _DICE_RE.match(str(record.get("damage_die") or "").strip()):
            errors.append("damage_die musi pasować do wzorca kości (np. d6, 2d8)")
        if str(record.get("tier") or "").strip().lower() not in _VALID_TIERS:
            errors.append("tier musi być jednym z: weak/standard/elite/boss")

    elif entity_type == "item":
        it = str(record.get("item_type") or "").strip().lower()
        if it and it not in _VALID_ITEM_TYPES:
            errors.append("item_type nieprawidłowy")
        if _as_int(record.get("value_gp")) < 0:
            errors.append("value_gp musi być >= 0")

    elif entity_type == "weapon":
        if not _DICE_RE.match(str(record.get("damage_die") or "").strip()):
            errors.append("damage_die nieprawidłowy")
        ls = str(record.get("linked_stat") or "").strip().upper()
        if ls and ls not in _VALID_STATS:
            errors.append("linked_stat nieprawidłowy")

    # npc / location: only a non-empty label is required at L1.

    return {"passed": len(errors) == 0, "errors": errors}


def _parse_score(raw: str) -> int:
    """Pull the first 0-100 integer out of an LLM reply; default 0 if none."""
    m = re.search(r"\b(100|\d{1,2})\b", str(raw or ""))
    if not m:
        return 0
    return max(0, min(100, int(m.group(1))))


def score_level2(
    entity_type: str,
    record: dict,
    *,
    score_fn: Callable[[str, dict], int] | None = None,
) -> int:
    """Level 2 — LLM fit score 0-100. `score_fn` overrides the LLM (tests)."""
    if score_fn is not None:
        try:
            return max(0, min(100, int(score_fn(entity_type, record))))
        except Exception:
            return 0

    from app.services.llm_service import generate_chat

    label = str(record.get("label") or record.get("key") or "?")
    desc = str(record.get("description") or record.get("note") or "")
    sys_msg = (
        "Jesteś kuratorem treści w mrocznym fantasy RPG. Oceń w skali 0-100, jak "
        "dobrze poniższy rekord pasuje do spójnego świata gry (nazwa, opis, ton). "
        "Odpowiedz WYŁĄCZNIE liczbą 0-100, bez słów."
    )
    user_msg = f"Typ: {entity_type}\nNazwa: {label}\nOpis: {desc}\nDane: {record}"
    try:
        raw = generate_chat(messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ])
        return _parse_score(raw)
    except Exception:
        # LLM unreachable → conservative: 0 (keeps record in the queue).
        return 0


def decide_screening(*, l1_passed: bool, score: int, threshold: int = DEFAULT_THRESHOLD) -> str:
    """Auto-approve only when L1 passed AND score strictly above threshold."""
    if l1_passed and int(score) > int(threshold):
        return "auto_approve"
    return "queue"


def _load_record(conn: sqlite3.Connection, entity_type: str, key: str) -> dict | None:
    table = _TABLE_BY_TYPE.get(entity_type)
    if not table:
        return None
    try:
        row = conn.execute(f"SELECT * FROM {table} WHERE key = ?", (key,)).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def auto_screen_record(
    conn: sqlite3.Connection,
    entity_type: str,
    key: str,
    *,
    score_fn: Callable[[str, dict], int] | None = None,
    threshold: int = DEFAULT_THRESHOLD,
) -> dict:
    """Run L1 + L2 on one pending record and auto-approve it if it clears both.

    Returns {decision, l1, score, key}. L1 failure short-circuits (no LLM call,
    no approval). On 'auto_approve' the record is promoted via approve_entity.
    """
    record = _load_record(conn, entity_type, key)
    if record is None:
        return {"decision": "queue", "l1": {"passed": False, "errors": ["nie znaleziono rekordu"]},
                "score": 0, "key": key}

    l1 = validate_level1(entity_type, record)
    if not l1["passed"]:
        return {"decision": "queue", "l1": l1, "score": 0, "key": key}

    score = score_level2(entity_type, record, score_fn=score_fn)
    decision = decide_screening(l1_passed=True, score=score, threshold=threshold)
    if decision == "auto_approve":
        from app.services.world_service import approve_entity
        approve_entity(conn, entity_type, key)
    return {"decision": decision, "l1": l1, "score": score, "key": key}
