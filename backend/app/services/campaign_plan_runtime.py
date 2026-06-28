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
import re
import sqlite3
import structlog

from app.services.event_logger import write_game_event

logger = structlog.get_logger()

# E6 (#421) — narrator emits [ARC_ADVANCE: arc_key] to jump the active arc.
_ARC_ADVANCE_RE = re.compile(r"\[ARC_ADVANCE:\s*([^\]\s]+)\s*\]", re.IGNORECASE)


def parse_arc_advance_tags(text: str | None) -> list[str]:
    """Extract arc keys from [ARC_ADVANCE: key] tags in narrator output."""
    if not text:
        return []
    return [m.group(1).strip() for m in _ARC_ADVANCE_RE.finditer(text)]


def advance_arc(campaign_id: int, arc_id: str, conn: sqlite3.Connection) -> bool:
    """E6 (#421) — Advance the GM plan to a named arc.

    Closes the currently active arc, activates the target arc and repoints
    `active_arc_id`. No-op (returns False) when the target arc does not exist
    or is already active. Uses the canonical `arcs` dict shape.
    """
    if not arc_id:
        return False
    from app.services.gm_plan_schema import normalize_gm_plan

    row = conn.execute(
        "SELECT gm_plan_json FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    if not row:
        return False
    plan = normalize_gm_plan(row[0] if not isinstance(row, sqlite3.Row) else row["gm_plan_json"])
    arcs = plan.get("arcs")
    if not isinstance(arcs, dict) or arc_id not in arcs:
        return False
    if plan.get("active_arc_id") == arc_id:
        return False

    prev = plan.get("active_arc_id")
    if prev and prev in arcs and isinstance(arcs[prev], dict):
        arcs[prev]["status"] = "closed"
    if isinstance(arcs[arc_id], dict):
        arcs[arc_id]["status"] = "active"
    plan["active_arc_id"] = arc_id

    conn.execute(
        "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
        (json.dumps(plan, ensure_ascii=False), campaign_id),
    )
    conn.commit()
    logger.info("arc_advanced", campaign_id=campaign_id, arc_id=arc_id, prev=prev)
    return True


# ── Plan access ────────────────────────────────────────────────────────────

def get_plan(campaign_id: int, conn: sqlite3.Connection) -> dict:
    """Load and parse gm_plan_json for a campaign."""
    row = conn.execute(
        "SELECT gm_plan_json FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    if not row or not row[0]:
        return {}
    try:
        plan = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return {}
    # Template plans store beats under "arcs" (list); V2 runtime reads "acts" (list).
    if isinstance(plan.get("arcs"), list) and not plan.get("acts"):
        plan["acts"] = plan["arcs"]
    return plan


def save_plan(campaign_id: int, plan: dict, conn: sqlite3.Connection) -> None:
    # #1010 — warn (non-blocking) when the plan contains orphan beats that can
    # never complete; surfaces the #1009 victory blocker at its source.
    try:
        orphans = find_orphan_beats(plan)
        if orphans:
            logger.warning(
                "gm_plan_orphan_beats",
                campaign_id=campaign_id,
                orphan_beat_keys=orphans,
            )
    except Exception:
        pass
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
        current_act = int(plan.get("active_act", 1))
        skipped_keys = _check_and_advance_act(plan, conn)
        save_plan(campaign_id, plan, conn)
        _cancel_quests_for_skipped(campaign_id, skipped_keys, conn)
        logger.info("beat_visited", campaign_id=campaign_id, beat_key=beat_key)
        write_game_event(
            "beat_complete",
            int(campaign_id),
            None,
            None,
            {"beat_key": beat_key, "act": current_act, "turn": turn_number},
        )

    return changed


def _check_and_advance_act(plan: dict, conn: sqlite3.Connection) -> list[str]:
    """Advance to next act once its *critical* beats are visited (#1010 refinement).

    Critical-path model: an act closes when every non-optional (`optional != True`)
    beat is visited; optional beats never block. An all-optional act falls back to
    "every beat required" so it cannot auto-close empty. On close, still-unvisited
    beats are tagged `skipped=True` (never `visited`) for honest telemetry.

    Returns the beat_keys newly marked `skipped` so the caller can cancel any
    side-quests pinned to them (#1011 refinement). Empty list when nothing closed.
    """
    active_idx = int(plan.get("active_act", 1)) - 1
    acts = plan.get("acts", [])
    if active_idx >= len(acts):
        return []

    current_act = acts[active_idx]
    beats = current_act.get("key_beats", [])

    # Check if all beats visited (skip if no structured beats)
    if not beats:
        return []

    # Critical beats = non-optional dict beats. If the act has none (all optional),
    # fall back to every dict beat so it cannot close with everything skipped.
    dict_beats = [b for b in beats if isinstance(b, dict)]
    critical = [b for b in dict_beats if b.get("optional") is not True]
    blocking = critical if critical else dict_beats

    # String beats are legacy / non-blocking (treated visited, as before).
    all_visited = all(b.get("visited", False) for b in blocking) if blocking else all(
        not isinstance(b, dict) for b in beats
    )

    skipped_keys: list[str] = []
    if all_visited and not current_act.get("completed"):
        current_act["completed"] = True
        # Honest telemetry: unvisited beats at close are skipped, not visited.
        for b in dict_beats:
            if not b.get("visited") and not b.get("skipped"):
                b["skipped"] = True
                key = b.get("beat_key")
                if key:
                    skipped_keys.append(str(key))
        if active_idx + 1 < len(acts):
            plan["active_act"] = active_idx + 2  # 1-indexed
            logger.info("act_advanced", new_act=plan["active_act"])

    return skipped_keys


def _cancel_quests_for_skipped(
    campaign_id: int, skipped_keys: list[str], conn: sqlite3.Connection
) -> None:
    """#1011 — auto-cancel side-quests pinned to beats skipped on act close.

    Best-effort: a stale beat_key column or quest-service import error must never
    block beat completion.
    """
    if not skipped_keys:
        return
    try:
        from app.services.quest_persist_service import cancel_quests_for_skipped_beats
        cancel_quests_for_skipped_beats(conn, campaign_id, skipped_keys)
    except Exception as _q_err:
        logger.warning("cancel_skipped_quests_error", campaign_id=campaign_id, error=str(_q_err))


# ── T38 (#1009): deterministic campaign victory ───────────────────────────


def is_plan_complete(plan: dict | None) -> bool:
    """True when every act in the GM-plan roadmap is completed.

    An act flips `completed=True` only once all its `key_beats` are visited
    (see `_check_and_advance_act`). So "all acts completed" == "all scenes
    traversed". Returns False for empty/absent plans so a fresh campaign with
    no roadmap can never be auto-won.
    """
    if not isinstance(plan, dict):
        return False
    acts = plan.get("acts")
    if not isinstance(acts, list) or not acts:
        return False
    return all(isinstance(a, dict) and a.get("completed") for a in acts)


def maybe_complete_campaign(
    campaign_id: int,
    character_id: int,
    turn_number: int,
    conn: sqlite3.Connection,
) -> bool:
    """T38 spinacz — flip campaign to 'completed' when the agreed victory
    definition holds: all acts/scenes traversed AND zero active quests.

    Idempotent: no-op if the campaign already has a terminal status. On success
    also clears `session_flags.quest_suggest_needed` so the #991 quest-dead guard
    does not push a new quest after the finale, and logs a `campaign_complete`
    game event. Returns True only on the transition.
    """
    row = conn.execute(
        "SELECT status FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    if not row:
        return False
    status = str((row["status"] if isinstance(row, sqlite3.Row) else row[0]) or "").lower()
    if status in ("completed", "ended", "archived", "discarded"):
        return False

    if not is_plan_complete(get_plan(campaign_id, conn)):
        return False

    # #1011 refinement: only active *main* quests block victory. Side quests are
    # optional threads — a legally-skipped side quest must not strand the finale.
    active_quests = conn.execute(
        "SELECT COUNT(*) FROM character_quests "
        "WHERE character_id = ? AND campaign_id = ? AND status = 'active' "
        "AND COALESCE(quest_type, 'main') = 'main'",
        (character_id, campaign_id),
    ).fetchone()[0]
    if active_quests > 0:
        return False

    conn.execute(
        "UPDATE campaigns SET status = 'completed' WHERE id = ?", (campaign_id,)
    )
    # Drop the quest-dead nudge so the narrator is not told to invent a new quest.
    try:
        sf_row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if sf_row:
            raw = sf_row["session_flags"] if isinstance(sf_row, sqlite3.Row) else sf_row[0]
            sf = json.loads(raw or "{}")
            if sf.pop("quest_suggest_needed", None) is not None:
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                    (json.dumps(sf, ensure_ascii=False), campaign_id),
                )
    except Exception as _sf_err:
        logger.warning("victory_clear_quest_flag_error", error=str(_sf_err))
    conn.commit()

    write_game_event(
        "campaign_complete",
        int(campaign_id),
        int(character_id),
        None,
        {"turn": turn_number, "trigger": "all_acts_and_quests"},
    )
    logger.info(
        "campaign_completed",
        campaign_id=campaign_id,
        character_id=character_id,
        turn=turn_number,
    )
    return True


# ── Beat reachability (#1010): expose beat_keys + orphan validator ─────────


def get_active_act_beat_keys(plan: dict | None) -> list[str]:
    """#1010 — beat_keys of the active act's *unvisited* key_beats.

    These are exactly the keys the narrator may close with [BEAT_COMPLETE:key].
    Follows the `active_act` pointer (1-indexed). Returns [] for empty/absent
    plans so a planless campaign never advertises phantom beats.
    """
    if not isinstance(plan, dict):
        return []
    acts = plan.get("acts")
    if not isinstance(acts, list) or not acts:
        return []
    idx = int(plan.get("active_act", 1)) - 1
    if idx < 0 or idx >= len(acts):
        return []
    act = acts[idx]
    if not isinstance(act, dict):
        return []
    out: list[str] = []
    for beat in act.get("key_beats", []):
        if isinstance(beat, dict) and not beat.get("visited"):
            key = beat.get("beat_key")
            if key:
                out.append(str(key))
    return out


def get_active_act_critical_beat_keys(plan: dict | None) -> list[str]:
    """#1012 — beat_keys of the active act's *unvisited, non-optional* key_beats.

    The anti-stall escalation pushes the narrator toward the critical path only;
    a legally-skippable optional beat must never be advertised as a required goal.
    Subset of `get_active_act_beat_keys` filtered to `optional != True`.
    """
    if not isinstance(plan, dict):
        return []
    acts = plan.get("acts")
    if not isinstance(acts, list) or not acts:
        return []
    idx = int(plan.get("active_act", 1)) - 1
    if idx < 0 or idx >= len(acts):
        return []
    act = acts[idx]
    if not isinstance(act, dict):
        return []
    out: list[str] = []
    for beat in act.get("key_beats", []):
        if not isinstance(beat, dict):
            continue
        if beat.get("visited") or beat.get("optional") is True:
            continue
        key = beat.get("beat_key")
        if key:
            out.append(str(key))
    return out


def get_beat_completion_context_block(campaign_id: int, conn: sqlite3.Connection) -> str:
    """#1010 — narrator-facing block listing the active act's open beat_keys plus
    the [BEAT_COMPLETE] instruction. Empty when nothing is open.

    Without this the narrator never sees the exact keys, so it cannot emit a valid
    [BEAT_COMPLETE:beat_key] for scenes that have no mechanical objective_type.
    """
    keys = get_active_act_beat_keys(get_plan(campaign_id, conn))
    if not keys:
        return ""
    listing = ", ".join(keys)
    return (
        "## Sceny do domknięcia (beat_key)\n"
        f"Otwarte sceny tego aktu: {listing}\n"
        "Gdy któraś z tych scen zostanie FABULARNIE domknięta, osadź w narracji tag "
        "[BEAT_COMPLETE:beat_key] z DOKŁADNYM kluczem z powyższej listy (skopiuj 1:1). "
        "Emituj tylko przy pełnym domknięciu sceny, nie przy częściowym postępie."
    )


def find_orphan_beats(plan: dict | None) -> list[str]:
    """#1010 — beat_keys that can never complete by any path.

    An orphan beat has neither an `objective_type` (auto-complete via game event)
    NOR an explicit `narrative_close` marker (intentionally closed by the narrator's
    [BEAT_COMPLETE] tag). Such a beat strands its act forever → blocks victory (#1009).
    Returned for warning at plan create/save time.
    """
    if not isinstance(plan, dict):
        return []
    acts = plan.get("acts")
    if not isinstance(acts, list):
        return []
    orphans: list[str] = []
    for act in acts:
        if not isinstance(act, dict):
            continue
        for beat in act.get("key_beats", []):
            if not isinstance(beat, dict):
                continue
            # #1010 refinement: an optional beat is intentionally skippable —
            # it never strands the act, so it is never an orphan.
            if beat.get("optional") is True:
                continue
            if beat.get("objective_type") in _OBJECTIVE_TYPES:
                continue
            if beat.get("narrative_close"):
                continue
            orphans.append(str(beat.get("beat_key") or "<no-key>"))
    return orphans


# ── Beat auto-complete by objective (U8 #532) ─────────────────────────────

_OBJECTIVE_TYPES = frozenset({"kill_enemy", "visit_location", "talk_to_npc", "find_item"})


def auto_complete_beats_by_event(
    campaign_id: int,
    event_type: str,
    target_name: str,
    turn_number: int,
    conn: sqlite3.Connection,
) -> bool:
    """U8 — Auto-complete beats whose objective_type+objective_value matches the event.

    Returns True if at least one beat was newly completed, False otherwise.
    Beat without objective_type is ignored — still requires LLM [BEAT_COMPLETE] tag.
    Uses _keyword_match from quest_checker (prefix-based Polish declension support).
    """
    if event_type not in _OBJECTIVE_TYPES or not target_name:
        return False

    from app.services.quest_checker import _keyword_match

    plan = get_plan(campaign_id, conn)
    if not plan:
        return False

    changed = False
    for act in plan.get("acts", []):
        for beat in act.get("key_beats", []):
            if not isinstance(beat, dict):
                continue
            if beat.get("visited"):
                continue
            if beat.get("objective_type") != event_type:
                continue
            obj_value = beat.get("objective_value") or ""
            # Empty/missing objective_value = wildcard: any target of the right type matches.
            # Non-empty: must match via keyword (Polish declension supported).
            if obj_value and not _keyword_match(obj_value, target_name):
                continue
            beat["visited"] = True
            beat["visited_at_turn"] = turn_number
            changed = True
            logger.info(
                "beat_auto_completed",
                campaign_id=campaign_id,
                beat_key=beat.get("beat_key"),
                event_type=event_type,
                target=target_name,
            )

    if changed:
        skipped_keys = _check_and_advance_act(plan, conn)
        save_plan(campaign_id, plan, conn)
        _cancel_quests_for_skipped(campaign_id, skipped_keys, conn)

    return changed


# ── HF-11 (#553): talk_to_npc auto-complete in the LIVE narrative tor ──────
#
# The original DIALOGUE hook (#550) lived in turn_pipeline._auto_complete_beats_by_mechanic,
# but process_v2_turn is never called by the live narrative tor (game_engine.run_narrative_turn
# → api/turns.py). So talk_to_npc beats only completed via the LLM [BEAT_COMPLETE] tag.
# This helper detects NPC engagement directly from the real signals available in the live tor.

# Polish diacritics → ASCII so free-text "sołtysem" matches scene NPC key "soltys_brzezino".
_PL_DIAC = str.maketrans(
    "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
    "acelnoszzACELNOSZZ",
)


def _strip_pl(s: str) -> str:
    return (s or "").translate(_PL_DIAC).lower()


def auto_complete_talk_to_npc(
    campaign_id: int,
    player_text: str | None,
    location_key: str | None,
    dialogue_npc_key: str | None,
    turn_number: int,
    conn: sqlite3.Connection,
) -> bool:
    """HF-11 — complete talk_to_npc beats from live-tor NPC engagement signals.

    Detects the engaged NPC from, in priority order:
      1. Button DIALOGUE — `dialogue_npc_key` already carries the exact scene NPC key.
      2. Free text — a scene NPC key/role token (diacritic-normalized) appears in the
         player's message (e.g. "rozmawiam z sołtysem" → soltys_brzezino).
    Then fires auto_complete_beats_by_event('talk_to_npc', engaged_key). Wildcard beats
    (empty objective_value) complete on any engagement; named beats still require a match.
    Returns True if at least one beat was newly completed.
    """
    engaged: str | None = None

    if dialogue_npc_key:
        engaged = dialogue_npc_key.strip() or None

    if not engaged and player_text and location_key:
        norm_text = _strip_pl(player_text)
        try:
            rows = conn.execute(
                "SELECT npc_key FROM location_npc_assignments"
                " WHERE location_key = ? AND COALESCE(is_active, 1) = 1",
                (location_key,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        for r in rows:
            key = r["npc_key"] if isinstance(r, sqlite3.Row) else r[0]
            if not key:
                continue
            # Role tokens from the key: 'soltys_brzezino' → ['soltys', 'brzezino'].
            # A token of length ≥4 appearing in the normalized player text = engagement.
            for tok in _strip_pl(key).split("_"):
                if len(tok) >= 4 and tok in norm_text:
                    engaged = key
                    break
            if engaged:
                break

    if not engaged:
        return False

    return auto_complete_beats_by_event(
        campaign_id, "talk_to_npc", engaged, turn_number, conn
    )


# ── NPC alive tracking ────────────────────────────────────────────────────

def mark_npc_dead(campaign_id: int, npc_key: str, conn: sqlite3.Connection) -> str:
    """
    Mark NPC as dead in campaign plan. Returns their deviation_consequence.
    Also sets global is_dead=1 on the npcs table (F19).
    """
    plan = get_plan(campaign_id, conn)
    consequence = "ignore"

    for npc in plan.get("key_npcs", []):
        if npc.get("key") == npc_key or npc.get("npc_key") == npc_key:
            npc["alive"] = False
            consequence = npc.get("deviation_consequence", "ignore")
            break

    save_plan(campaign_id, plan, conn)

    # F19: propagate death globally
    try:
        from app.services.npc_global_death_service import mark_npc_dead_global
        mark_npc_dead_global(conn, npc_key)
    except Exception:
        pass

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

    # E9 (#424) — story gravity: nudge the narrator when a beat has stalled.
    try:
        from app.services.story_gravity_service import compute_story_gravity
        g = compute_story_gravity(campaign_id, conn)
        if g.get("hint"):
            lines.append(g["hint"])
    except Exception:
        pass

    return "\n".join(lines)
