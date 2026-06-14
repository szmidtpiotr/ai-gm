"""U18 (#570) — Player journal (Dziennik gracza).

Composes a read-only journal payload from three existing stores. The journal
NEVER writes state — it only surfaces what the mechanics already track, so the
player can verify "what did I promise Marta" and catch GM/LLM drift.

Sections:
  - quests    (Zadania)  ← character_quests        (active + completed)
  - threads   (Wątki)    ← narrative_state.seeds    (player_visible only)
  - chronicle (Kronika)  ← narrative_state.events + completed beats,
                           reverse-chronological, each entry tagged with a turn.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

# Numbers Policy (#570): starting cap on chronicle entries returned to the UI.
MAX_CHRONICLE = 50

# Numbers Policy (#571 / U19): starting values for the "Poprzednio…" recap card.
RECAP_THRESHOLD_HOURS = 24      # show the card only after a >24h real-time gap
RECAP_RECENT_TURNS = 2          # how many last turns to surface in the card


def _load_narrative_state(conn: sqlite3.Connection, campaign_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not row:
        return {}
    raw = row[0] if not hasattr(row, "keys") else row["session_flags"]
    try:
        flags = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    ns = flags.get("narrative_state") or {}
    return ns if isinstance(ns, dict) else {}


def _load_quests(conn: sqlite3.Connection, campaign_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT title, narrative, status, quest_type, created_turn, completed_turn
             FROM character_quests
            WHERE campaign_id = ?
         ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, created_turn""",
        (campaign_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r) if hasattr(r, "keys") else {
            "title": r[0], "narrative": r[1], "status": r[2],
            "quest_type": r[3], "created_turn": r[4], "completed_turn": r[5],
        }
        out.append(d)
    return out


def _load_completed_beats(conn: sqlite3.Connection, campaign_id: int) -> list[dict[str, Any]]:
    row = conn.execute(
        "SELECT gm_plan_json FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    if not row:
        return []
    raw = row[0] if not hasattr(row, "keys") else row["gm_plan_json"]
    try:
        plan = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return []
    beats: list[dict[str, Any]] = []
    for act in plan.get("acts", []) or []:
        if not isinstance(act, dict):
            continue
        for beat in act.get("key_beats", []) or []:
            if not isinstance(beat, dict) or not beat.get("visited"):
                continue
            text = (beat.get("description") or beat.get("title")
                    or beat.get("beat_key") or "").strip()
            if not text:
                continue
            beats.append({"text": text, "turn": int(beat.get("visited_at_turn") or 0)})
    return beats


def build_journal(campaign_id: int, conn: sqlite3.Connection) -> dict[str, Any]:
    """Compose the player journal payload (read-only)."""
    ns = _load_narrative_state(conn, campaign_id)

    # Zadania
    quests = _load_quests(conn, campaign_id)

    # Wątki — seeds the player is allowed to see (default visible when flag absent).
    threads: list[dict[str, Any]] = []
    for s in ns.get("seeds", []) or []:
        if not isinstance(s, dict):
            continue
        if s.get("player_visible", True) is False:
            continue
        threads.append({
            "key": s.get("key"),
            "hint": s.get("hint") or s.get("key"),
            "status": s.get("status") or "active",
            "turn": int(s.get("planted_turn") or 0),
        })

    # Kronika — events + completed beats, reverse-chronological.
    chronicle: list[dict[str, Any]] = []
    for e in ns.get("events", []) or []:
        if not isinstance(e, dict):
            continue
        text = (e.get("note") or e.get("key") or "").strip()
        if text:
            chronicle.append({"type": "event", "text": text, "turn": int(e.get("turn") or 0)})
    for b in _load_completed_beats(conn, campaign_id):
        chronicle.append({"type": "beat", "text": b["text"], "turn": b["turn"]})
    chronicle.sort(key=lambda x: x["turn"], reverse=True)
    chronicle = chronicle[:MAX_CHRONICLE]

    return {"quests": quests, "threads": threads, "chronicle": chronicle}


# ── U19 (#571): "Poprzednio w Twojej przygodzie…" recap ──────────────────────

def _clean_gm_text(raw: str) -> str:
    """Extract the player-facing narrative from a stored assistant_text.

    assistant_text may be a JSON envelope ({"narrative": "..."}) and/or carry
    [NARRATIVE_EVENT/SEED:...] tags — strip both so the recap shows clean prose.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and obj.get("narrative"):
                text = str(obj["narrative"]).strip()
        except (json.JSONDecodeError, TypeError):
            pass
    try:
        from app.services.narrative_state_service import strip_narrative_tags
        text = strip_narrative_tags(text)
    except Exception:
        pass
    return text


def _recent_turns(conn: sqlite3.Connection, campaign_id: int,
                  limit: int = RECAP_RECENT_TURNS) -> list[dict[str, Any]]:
    """Last N meaningful turns (newest first), for the recap card."""
    rows = conn.execute(
        """SELECT turn_number, user_text, assistant_text
             FROM campaign_turns
            WHERE campaign_id = ?
              AND route IN ('narrative', 'skill_check', 'combat')
         ORDER BY turn_number DESC, id DESC
            LIMIT ?""",
        (campaign_id, limit),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r) if hasattr(r, "keys") else {
            "turn_number": r[0], "user_text": r[1], "assistant_text": r[2],
        }
        user = (d.get("user_text") or "").strip()
        # Hide internal markers (__AI_GM_OPEN, combat-roll wrappers) from the player.
        if user.startswith("__AI_GM"):
            user = ""
        gm = _clean_gm_text(d.get("assistant_text") or "")
        out.append({
            "turn_number": int(d.get("turn_number") or 0),
            "player": user[:200],
            "gm": gm[:400],
        })
    return out


def _active_quests(conn: sqlite3.Connection, campaign_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT title, narrative
             FROM character_quests
            WHERE campaign_id = ? AND status = 'active'
         ORDER BY created_turn""",
        (campaign_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r) if hasattr(r, "keys") else {"title": r[0], "narrative": r[1]}
        out.append({"title": d.get("title"), "narrative": d.get("narrative")})
    return out


def _hours_since_last_turn(conn: sqlite3.Connection, campaign_id: int) -> tuple[float | None, str | None, int]:
    """Return (hours_since_last, last_turn_at, turn_count).

    Hours computed in SQL (julianday) so it is robust to the stored timestamp
    format and timezone (campaign_turns.created_at is UTC CURRENT_TIMESTAMP).
    """
    row = conn.execute(
        """SELECT COUNT(*) AS cnt,
                  MAX(created_at) AS last_at,
                  (julianday('now') - julianday(MAX(created_at))) * 24.0 AS hrs
             FROM campaign_turns
            WHERE campaign_id = ?""",
        (campaign_id,),
    ).fetchone()
    if not row:
        return None, None, 0
    d = dict(row) if hasattr(row, "keys") else {"cnt": row[0], "last_at": row[1], "hrs": row[2]}
    cnt = int(d.get("cnt") or 0)
    if cnt == 0:
        return None, None, 0
    hrs = d.get("hrs")
    return (float(hrs) if hrs is not None else None), d.get("last_at"), cnt


def build_recap(campaign_id: int, conn: sqlite3.Connection,
                threshold_hours: float = RECAP_THRESHOLD_HOURS) -> dict[str, Any]:
    """Compose the "Poprzednio…" recap payload (read-only).

    The TRIGGER is a pure mechanic decided here (backend): the card is shown only
    when the campaign has ≥1 turn AND the last turn is older than `threshold_hours`
    real hours. The card reuses already-stored state — the saved player summary,
    the last turns and the active quests — and NEVER calls the LLM, so it cannot
    desync from or rewrite game state (Zasady 1–5).
    """
    hours_since, last_at, turn_count = _hours_since_last_turn(conn, campaign_id)
    should_show = bool(
        turn_count >= 1 and hours_since is not None and hours_since > threshold_hours
    )

    summary: str | None = None
    try:
        from app.services.history_summary_service import (
            SUMMARY_AUDIENCE_PLAYER,
            fetch_latest_saved_summary,
        )
        saved = fetch_latest_saved_summary(conn, campaign_id, audience=SUMMARY_AUDIENCE_PLAYER)
        if saved:
            summary = (saved.get("summary_text") or "").strip() or None
    except Exception:
        summary = None

    return {
        "campaign_id": campaign_id,
        "should_show": should_show,
        "hours_since_last": round(hours_since, 1) if hours_since is not None else None,
        "last_turn_at": last_at,
        "turn_count": turn_count,
        "threshold_hours": threshold_hours,
        "summary": summary,
        "recent_turns": _recent_turns(conn, campaign_id),
        "active_quests": _active_quests(conn, campaign_id),
    }
