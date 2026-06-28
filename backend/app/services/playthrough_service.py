"""#1012 — Playthrough anti-stall detector + autopilot mode.

Goal: let a fully-automated Playwright playthrough reach the victory overlay
without a human nudge. Two mechanisms:

1. **Anti-stall detector** — each narrative turn we compute a *progress
   signature*. Progress (per the #1010/#1011 critical-path model) means one of:
     • a new *critical* (non-optional) beat was visited,
     • the act pointer advanced,
     • a *main* quest changed (new main quest, or one completed).
   A skipped/optional beat is NEITHER progress NOR a stall trigger — the player
   legally bypasses it. When the signature is unchanged for
   `STALL_TURN_THRESHOLD` turns we inject an escalating directive that pushes the
   narrator toward the active act's critical beat_keys, and emit a
   `playthrough_stall` telemetry event with a classified cause.

2. **Autopilot** (`AI_TEST_MODE=1`) — keeps the automated run alive: protects a
   `[TEST]` hero from a death-loop (HP restore), shortens narration, and offers a
   deterministic gate choice.

Everything here is best-effort: a failure must never break the narrative turn.
"""

from __future__ import annotations

import json
import os
import sqlite3

import structlog

from app.services.event_logger import write_game_event
from app.services.campaign_plan_runtime import (
    get_plan,
    get_active_act_critical_beat_keys,
    find_orphan_beats,
    is_plan_complete,
)

logger = structlog.get_logger()

# Turns without story progress before the anti-stall directive fires.
# Starting value — mirrors STORY_STALE (C1) so the two escalations line up.
STALL_TURN_THRESHOLD = 5

# Restore a [TEST] hero to full HP once it drops to/below this fraction of max,
# so an automated run never gets stuck in a death-loop. Starting value.
TEST_HERO_HP_FLOOR_FRACTION = 0.5

# Deterministic gate option for autopilot (D1 #1000 gate: strike uses prose).
AUTOPILOT_GATE_CHOICE = "strike"


# ── Progress signature ───────────────────────────────────────────────────────

def _count_visited_critical_beats(plan: dict | None) -> int:
    """Count visited non-optional dict beats across ALL acts.

    Skipped (`skipped=True`, never `visited`) and optional beats are excluded —
    they are not story progress.
    """
    if not isinstance(plan, dict):
        return 0
    acts = plan.get("acts")
    if not isinstance(acts, list):
        return 0
    n = 0
    for act in acts:
        if not isinstance(act, dict):
            continue
        for beat in act.get("key_beats", []):
            if not isinstance(beat, dict):
                continue
            if beat.get("optional") is True:
                continue
            if beat.get("visited") is True:
                n += 1
    return n


def _main_quest_signature(
    conn: sqlite3.Connection, campaign_id: int, character_id: int
) -> tuple[int, int]:
    """(total main quests, completed main quests) for the campaign+character.

    Any new main quest or a main-quest completion shifts one of these numbers,
    so the pair captures every kind of main-quest progress. Side quests are
    deliberately ignored.
    """
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM character_quests "
            "WHERE character_id=? AND campaign_id=? AND COALESCE(quest_type,'main')='main'",
            (character_id, campaign_id),
        ).fetchone()[0]
        done = conn.execute(
            "SELECT COUNT(*) FROM character_quests "
            "WHERE character_id=? AND campaign_id=? AND COALESCE(quest_type,'main')='main' "
            "AND status='completed'",
            (character_id, campaign_id),
        ).fetchone()[0]
        return int(total), int(done)
    except sqlite3.Error:
        return 0, 0


def compute_progress_signature(
    conn: sqlite3.Connection, campaign_id: int, character_id: int
) -> str:
    """Opaque token whose change == story progress (critical beat / act / main quest)."""
    plan = get_plan(campaign_id, conn)
    crit = _count_visited_critical_beats(plan)
    active_act = int(plan.get("active_act", 1)) if isinstance(plan, dict) else 1
    q_total, q_done = _main_quest_signature(conn, campaign_id, character_id)
    return f"{crit}|{active_act}|{q_total}|{q_done}"


# ── Stall detection ──────────────────────────────────────────────────────────

def _load_session_flags(conn: sqlite3.Connection, campaign_id: int):
    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not row:
        return None
    raw = row["session_flags"] if isinstance(row, sqlite3.Row) else row[0]
    try:
        return json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _save_session_flags(conn: sqlite3.Connection, campaign_id: int, sf: dict) -> None:
    conn.execute(
        "UPDATE game_sessions SET session_flags=? WHERE campaign_id=?",
        (json.dumps(sf, ensure_ascii=False), campaign_id),
    )
    conn.commit()


def classify_stall_cause(
    conn: sqlite3.Connection, campaign_id: int, character_id: int
) -> str:
    """Best-effort reason for a stall, ordered by actionability.

    - `orphan_beat`        — a critical beat can never close (no objective + no
                             narrative_close) → it strands the act.
    - `main_quest_hanging` — an active main quest exists but isn't advancing.
    - `no_open_critical_beat` — the active act has no open critical beat yet isn't
                             complete (reachability gap).
    - `narrator_loop`      — none of the above; the narrator just isn't pushing
                             (also covers the "no gate offered" case).
    """
    plan = get_plan(campaign_id, conn)
    if find_orphan_beats(plan):
        return "orphan_beat"
    try:
        active_main = conn.execute(
            "SELECT COUNT(*) FROM character_quests "
            "WHERE character_id=? AND campaign_id=? AND status='active' "
            "AND COALESCE(quest_type,'main')='main'",
            (character_id, campaign_id),
        ).fetchone()[0]
    except sqlite3.Error:
        active_main = 0
    if active_main > 0:
        return "main_quest_hanging"
    if not get_active_act_critical_beat_keys(plan) and not is_plan_complete(plan):
        return "no_open_critical_beat"
    return "narrator_loop"


def record_progress_and_detect_stall(
    conn: sqlite3.Connection, campaign_id: int, character_id: int, turn_number: int
) -> dict:
    """Update the per-campaign stall counter and report whether we are stalled.

    Stored in `session_flags.playthrough_stall = {sig, stall_turns}`. The first
    observation only records the baseline (never stalled). Each subsequent call
    with an unchanged signature increments the counter; any change resets it.
    Once `stall_turns >= STALL_TURN_THRESHOLD` we log + emit telemetry once per
    turn and return `stalled=True` with a classified cause.
    """
    result = {"stalled": False, "stall_turns": 0, "cause": None, "signature": ""}
    sf = _load_session_flags(conn, campaign_id)
    if sf is None:
        return result

    cur_sig = compute_progress_signature(conn, campaign_id, character_id)
    ps = sf.get("playthrough_stall") or {}
    prev_sig = ps.get("sig")

    if prev_sig is None:
        stall_turns = 0
    elif cur_sig != prev_sig:
        stall_turns = 0
    else:
        stall_turns = int(ps.get("stall_turns", 0)) + 1

    sf["playthrough_stall"] = {"sig": cur_sig, "stall_turns": stall_turns}
    try:
        _save_session_flags(conn, campaign_id, sf)
    except sqlite3.Error:
        pass

    stalled = stall_turns >= STALL_TURN_THRESHOLD
    cause = None
    if stalled:
        cause = classify_stall_cause(conn, campaign_id, character_id)
        logger.warning(
            "playthrough_stall",
            campaign_id=campaign_id,
            character_id=character_id,
            stall_turns=stall_turns,
            cause=cause,
            turn=turn_number,
        )
        write_game_event(
            "playthrough_stall",
            int(campaign_id),
            int(character_id),
            None,
            {"stall_turns": stall_turns, "cause": cause, "turn": turn_number},
            severity="warning",
        )

    result.update(
        stalled=stalled, stall_turns=stall_turns, cause=cause, signature=cur_sig
    )
    return result


def build_stall_directive(stall_turns: int, critical_beat_keys: list[str] | None) -> str:
    """Escalating system directive pushing the narrator toward the critical path.

    Intensity mirrors STORY_STALE: mild (<10), strong (10-14), critical (15+).
    Always names the critical beat_keys the narrator should drive toward.
    """
    keys = [k for k in (critical_beat_keys or []) if k]
    target = (
        f"Pchnij fabułę KONKRETNIE do otwartych scen krytycznych: {', '.join(keys)}."
        if keys
        else "Pchnij fabułę do głównego celu bieżącego aktu."
    )
    if stall_turns >= 15:
        urgency = (
            f"KRYTYCZNE! {stall_turns} tur bez postępu fabuły. "
            "Bohater MUSI natychmiast dostać konkretny krok prowadzący do celu aktu — "
            "wymuś wydarzenie lub jednoznaczny wybór (gate) TERAZ."
        )
    elif stall_turns >= 10:
        urgency = (
            f"PILNE! {stall_turns} tur bez postępu fabuły. "
            "Zaproponuj bohaterowi jednoznaczny, namacalny krok do przodu."
        )
    else:
        urgency = (
            f"{stall_turns} tur bez postępu fabuły — przestań kręcić się w miejscu."
        )
    return f"[PLAYTHROUGH_STALL: {urgency} {target}]"


# ── Autopilot ────────────────────────────────────────────────────────────────

def is_autopilot_active() -> bool:
    """Autopilot is gated on AI_TEST_MODE — only automated runs opt in."""
    return os.getenv("AI_TEST_MODE") == "1"


def is_test_hero(character) -> bool:
    """True for a disposable test hero (name prefixed `[TEST]`)."""
    if character is None:
        return False
    try:
        name = character["name"] if isinstance(character, sqlite3.Row) else character.get("name")
    except (KeyError, IndexError, TypeError):
        name = None
    return bool(name) and str(name).startswith("[TEST]")


def protect_test_hero_from_death(conn: sqlite3.Connection, character) -> bool:
    """Restore a low-HP [TEST] hero to full HP so autopilot never death-loops.

    No-op (returns False) unless autopilot is active AND the hero is a [TEST]
    hero AND its HP is at/below `TEST_HERO_HP_FLOOR_FRACTION` of max. A real
    player's hero is NEVER touched (see memory `feedback_smoke_test_db_cheat`).
    """
    if not is_autopilot_active() or not is_test_hero(character):
        return False
    try:
        cid = character["id"] if isinstance(character, sqlite3.Row) else character.get("id")
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id=?", (cid,)
        ).fetchone()
        if not row:
            return False
        raw = row["sheet_json"] if isinstance(row, sqlite3.Row) else row[0]
        sheet = json.loads(raw or "{}")
        cur = sheet.get("current_hp")
        mx = sheet.get("max_hp")
        if cur is None or mx is None:
            return False
        cur, mx = int(cur), int(mx)
        if mx <= 0:
            return False
        if cur > mx * TEST_HERO_HP_FLOOR_FRACTION:
            return False
        sheet["current_hp"] = mx
        conn.execute(
            "UPDATE characters SET sheet_json=? WHERE id=?",
            (json.dumps(sheet, ensure_ascii=False), cid),
        )
        conn.commit()
        logger.info(
            "autopilot_test_hero_revived", character_id=cid, from_hp=cur, to_hp=mx
        )
        return True
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError):
        return False


def autopilot_gate_choice() -> str:
    """Deterministic gate option for an automated playthrough (always the same)."""
    return AUTOPILOT_GATE_CHOICE


def build_autopilot_narration_directive() -> str:
    """Keep autopilot narration short so a long run stays fast and on-rails."""
    return (
        "[AUTOPILOT: tryb automatycznego przejazdu testowego — narracja maksymalnie "
        "zwięzła (1-2 zdania), zawsze zakończona jednoznacznym krokiem do przodu.]"
    )
