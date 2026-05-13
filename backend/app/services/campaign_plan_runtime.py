"""
Campaign Plan Runtime — V2 Phase 04 Task 13

Live campaign plan operations during gameplay:
- Beat completion detection + marking
- Act advancement
- Deviation tracking
- Compact narrator context block from plan
"""

from __future__ import annotations

import json
import sqlite3
import structlog

logger = structlog.get_logger()


# ── Plan access ────────────────────────────────────────────────────────────

def get_plan(campaign_id: int, conn: sqlite3.Connection) -> dict:
    """Load and parse gm_plan_json for a campaign."""
    row = conn.execute(
        "SELECT gm_plan_json FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    if not row or not row[0]:
        return {}
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return {}


def save_plan(campaign_id: int, plan: dict, conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
        (json.dumps(plan, ensure_ascii=False), campaign_id)
    )
    conn.commit()


# ── Beat tracking ─────────────────────────────────────────────────────────

def mark_beat_visited(
    campaign_id: int, beat_key: str, turn_number: int, conn: sqlite3.Connection
) -> bool:
    """
    Mark a key beat as visited. Returns True if newly marked, False if already visited.
    """
    plan = get_plan(campaign_id, conn)
    if not plan:
        return False

    changed = False
    active_act_idx = int(plan.get("active_act", 1)) - 1

    for act in plan.get("acts", []):
        for beat in act.get("key_beats", []):
            if isinstance(beat, dict) and beat.get("beat_key") == beat_key:
                if not beat.get("visited"):
                    beat["visited"] = True
                    beat["visited_at_turn"] = turn_number
                    changed = True
            elif isinstance(beat, str) and beat == beat_key:
                # Simple string format — convert to dict
                pass

    if changed:
        _check_and_advance_act(plan, conn)
        save_plan(campaign_id, plan, conn)
        logger.info("beat_visited", campaign_id=campaign_id, beat_key=beat_key)

    return changed


def _check_and_advance_act(plan: dict, conn: sqlite3.Connection) -> None:
    """Advance to next act if all key beats in current act are visited."""
    active_idx = int(plan.get("active_act", 1)) - 1
    acts = plan.get("acts", [])
    if active_idx >= len(acts):
        return

    current_act = acts[active_idx]
    beats = current_act.get("key_beats", [])

    # Check if all beats visited (skip if no structured beats)
    if not beats:
        return

    all_visited = all(
        b.get("visited", False) if isinstance(b, dict) else True
        for b in beats
    )

    if all_visited and not current_act.get("completed"):
        current_act["completed"] = True
        if active_idx + 1 < len(acts):
            plan["active_act"] = active_idx + 2  # 1-indexed
            logger.info("act_advanced", new_act=plan["active_act"])


# ── NPC alive tracking ────────────────────────────────────────────────────

def mark_npc_dead(campaign_id: int, npc_key: str, conn: sqlite3.Connection) -> str:
    """
    Mark NPC as dead in campaign plan. Returns their deviation_consequence.
    """
    plan = get_plan(campaign_id, conn)
    consequence = "ignore"

    for npc in plan.get("key_npcs", []):
        if npc.get("key") == npc_key or npc.get("npc_key") == npc_key:
            npc["alive"] = False
            consequence = npc.get("deviation_consequence", "ignore")
            break

    save_plan(campaign_id, plan, conn)
    return consequence


# ── Deviation tracking ────────────────────────────────────────────────────

def log_deviation(
    campaign_id: int, description: str, severity: str, conn: sqlite3.Connection
) -> None:
    """Add a deviation note to the campaign plan."""
    plan = get_plan(campaign_id, conn)
    if not plan:
        return

    deviations = plan.get("deviations", [])
    deviations.append({"description": description, "severity": severity})
    plan["deviations"] = deviations[-20:]  # keep last 20

    # Update deviation level
    if severity == "catastrophic":
        plan["deviation_level"] = "catastrophic"
    elif severity == "major" and plan.get("deviation_level", "normal") == "normal":
        plan["deviation_level"] = "major"
    elif severity == "minor" and plan.get("deviation_level", "normal") == "normal":
        plan["deviation_level"] = "minor"

    save_plan(campaign_id, plan, conn)


# ── Narrator context block ────────────────────────────────────────────────

def get_narrator_context_block(campaign_id: int, conn: sqlite3.Connection) -> str:
    """
    Build a compact campaign plan context block for the narrator.
    Includes: active act, recent beats, deviation status, key NPCs alive.
    """
    plan = get_plan(campaign_id, conn)
    if not plan:
        return ""

    lines = ["[CAMPAIGN CONTEXT]"]

    # Active act
    active_act_num = int(plan.get("active_act", 1))
    acts = plan.get("acts", [])
    if acts and active_act_num <= len(acts):
        act = acts[active_act_num - 1]
        lines.append(f"Act {active_act_num}: {act.get('title', '?')}")
        summary = str(act.get("summary", "")).strip()
        if summary:
            lines.append(f"Summary: {summary[:150]}")

        # Next unvisited beats
        beats = act.get("key_beats", [])
        unvisited = [
            b.get("beat_key", b) if isinstance(b, dict) else b
            for b in beats
            if not (b.get("visited", False) if isinstance(b, dict) else False)
        ][:3]
        if unvisited:
            lines.append(f"Next beats: {', '.join(str(b) for b in unvisited)}")

    # Deviation
    level = plan.get("deviation_level", "normal")
    if level != "normal":
        note = plan.get("deviation_note", "")
        lines.append(f"Deviation: {level}" + (f" — {note}" if note else ""))

    # Key NPCs alive
    npcs = plan.get("key_npcs", [])
    alive_npcs = [
        n.get("name", n.get("key", "?"))
        for n in npcs
        if n.get("alive", True) and n.get("importance") in ("critical", "supporting")
    ]
    if alive_npcs:
        lines.append(f"Key NPCs (alive): {', '.join(alive_npcs[:4])}")

    return "\n".join(lines)
