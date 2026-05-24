"""Build campaign transcript from SQLite and call LLM for summary text."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Literal

from app.history_summary_prompt_loader import HISTORY_SUMMARY_PROMPT_TEXT
from app.services.history_summary_dual_prompt import (
    build_dual_single_messages,
    leaked_plan_tokens_in_player_summary,
    parse_dual_json_response,
)
from app.services.gm_plan_schema import format_gm_plan_block
from app.services.llm_service import generate_chat
from app.services.summary_settings_service import (
    DEFAULT_SUMMARY_ROLLUP_COOLDOWN_TURNS,
    META_KEY_SUMMARY_ROLLUP_COOLDOWN,
    get_summary_rollup_cooldown_turns,
)
from app.services.user_llm_settings import get_user_llm_settings_full


DB_PATH = "/data/ai_gm.db"

# [T02 / S11b] Rollup storage: public-facing vs GM-only context (separate rows).
SummaryAudience = Literal["player", "gm"]
SUMMARY_AUDIENCE_PLAYER: SummaryAudience = "player"
SUMMARY_AUDIENCE_GM: SummaryAudience = "gm"
PLAYER_SUMMARY_SYSTEM_APPEND = """

## AUDIENCE: PLAYER
- Tworzysz wyłącznie wersję dla gracza / jawny notatnik kampanii.
- Bazuj tylko na faktach z transkryptu dostarczonego w wiadomości użytkownika.
- Nie odwołuj się do ukrytego planu MG, wewnętrznych notatek ani danych spoza transkryptu.
- Jeśli czegoś nie ma w transkrypcie, pomiń to zamiast dopowiadać.
""".strip()
GM_SUMMARY_SYSTEM_APPEND = """

## AUDIENCE: GM
- Tworzysz prywatną wersję MG / kontekst dla silnika i panelu admin.
- Możesz łączyć fakty z transkryptu z blokiem PLAN_MG, jeśli został dołączony.
- Wolno wskazywać tropy, cele sceny i konsekwencje, które nie padły jeszcze wprost w dialogu.
- Zachowaj rozdział: to nie jest tekst dla gracza.
""".strip()


def _normalize_audience(audience: str) -> SummaryAudience:
    a = (audience or "").strip().lower()
    if a == SUMMARY_AUDIENCE_PLAYER:
        return SUMMARY_AUDIENCE_PLAYER
    if a == SUMMARY_AUDIENCE_GM:
        return SUMMARY_AUDIENCE_GM
    raise ValueError("audience must be 'player' or 'gm'")


def _fetch_campaign(conn: sqlite3.Connection, campaign_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, title, system_id, model_id, owner_user_id, language, mode, status, created_at,
               gm_plan_json
        FROM campaigns WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()
    return dict(row) if row else None


def count_narrative_turns(conn: sqlite3.Connection, campaign_id: int) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM campaign_turns
        WHERE campaign_id = ? AND route = 'narrative'
        """,
        (campaign_id,),
    ).fetchone()
    return int(row["n"] or 0) if row else 0


# --- T10: optional background POST …/history/summary/ensure every N narrative turns ---
META_KEY_SUMMARY_AUTO_ENSURE_EVERY_N = "summary_auto_ensure_every_n_narrative_turns"
DEFAULT_SUMMARY_AUTO_ENSURE_EVERY_N_NARRATIVE_TURNS = 10


def get_summary_auto_ensure_every_n_narrative_turns(conn: sqlite3.Connection) -> int:
    """
    Co ile tur narracyjnych z uruchamiać automatyczne ensure (T10).
    0 = wyłączone. Brak wiersza w meta → domyślnie co N tur (DEFAULT_SUMMARY_AUTO_ENSURE_EVERY_N_NARRATIVE_TURNS).
    """
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ? LIMIT 1",
            (META_KEY_SUMMARY_AUTO_ENSURE_EVERY_N,),
        ).fetchone()
        if row:
            raw_val = row["value"] if hasattr(row, "keys") else row[0]
            if raw_val is not None:
                n = int(str(raw_val).strip())
                if n == 0:
                    return 0
                return max(1, min(500, n))
    except (sqlite3.OperationalError, ValueError, TypeError):
        pass
    return DEFAULT_SUMMARY_AUTO_ENSURE_EVERY_N_NARRATIVE_TURNS


def evaluate_summary_rollup_cooldown(
    conn: sqlite3.Connection, campaign_id: int
) -> tuple[bool, int, int | None, int]:
    """
    Returns:
      allowed — LLM rollup may run (no anchor yet, or enough new narrative turns)
      cooldown_n — configured N
      last_anchor — value of campaigns.last_rollup_narrative_turn_count
      current_n — count_narrative_turns (total narrative rows for campaign)
    """
    cooldown_n = get_summary_rollup_cooldown_turns(conn)
    current_n = count_narrative_turns(conn, campaign_id)
    last_anchor: int | None = None
    try:
        row = conn.execute(
            "SELECT last_rollup_narrative_turn_count AS a FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if row and row["a"] is not None:
            last_anchor = int(row["a"])
    except sqlite3.OperationalError:
        last_anchor = None

    if last_anchor is None:
        return True, cooldown_n, None, current_n
    delta = current_n - last_anchor
    return (delta >= cooldown_n), cooldown_n, last_anchor, current_n


def turns_until_summary_rollup_allowed(
    cooldown_n: int, last_anchor: int | None, current_n: int
) -> int:
    """Narrative turns still needed before the next rollup is allowed."""
    if last_anchor is None:
        return 0
    delta = current_n - last_anchor
    return max(0, cooldown_n - delta)


def touch_rollup_cooldown_anchor(conn: sqlite3.Connection, campaign_id: int) -> None:
    """Record narrative turn count after a successful rollup LLM call (shared per campaign)."""
    n = count_narrative_turns(conn, campaign_id)
    try:
        conn.execute(
            "UPDATE campaigns SET last_rollup_narrative_turn_count = ? WHERE id = ?",
            (n, campaign_id),
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass


def fetch_narrative_turns(
    conn: sqlite3.Connection, campaign_id: int, max_turns: int
) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT turn_number, user_text, assistant_text, created_at
        FROM campaign_turns
        WHERE campaign_id = ? AND route = 'narrative'
        ORDER BY turn_number DESC
        LIMIT ?
        """,
        (campaign_id, max_turns),
    ).fetchall()
    return list(reversed(rows))


def format_transcript(turns: list[sqlite3.Row], campaign_title: str, language: str) -> str:
    lines = [
        f"Kampania: {campaign_title}",
        f"Język (meta): {language}",
        "",
        "--- Transkrypt (tylko tury narracyjne) ---",
        "",
    ]
    for t in turns:
        un = (t["user_text"] or "").strip()
        an = (t["assistant_text"] or "").strip()
        lines.append(f"[Tura {t['turn_number']}] ({t['created_at']})")
        lines.append(f"Gracz: {un}")
        lines.append(f"MG: {an}")
        lines.append("")
    return "\n".join(lines)


def generate_dual_summary_preview(
    *,
    campaign_id: int,
    user_id: int,
    max_turns: int = 200,
    gm_plan_max_chars: int = 12000,
) -> dict[str, Any]:
    """
    [T01] One LLM call → JSON player_summary + gm_notes. Does NOT persist.
    gm_plan_json from campaign is passed to the prompt for gm_notes only (rules in dual prompt).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        camp = _fetch_campaign(conn, campaign_id)
        if not camp:
            raise ValueError("campaign_not_found")
        turns = fetch_narrative_turns(conn, campaign_id, max_turns)
        if not turns:
            return {
                "player_summary": "",
                "gm_notes": "",
                "leaked_plan_tokens": [],
                "model_used": "",
                "included_turn_count": 0,
                "warning": "Brak tur narracyjnych do podsumowania.",
                "parse_error": None,
            }

        transcript = format_transcript(
            turns, camp["title"] or f"Kampania {campaign_id}", camp["language"] or "pl"
        )
        gm_plan_raw = str(camp.get("gm_plan_json") or "").strip()
        plan_excerpt: str | None
        if not gm_plan_raw or gm_plan_raw in ("{}", "null"):
            plan_excerpt = None
        else:
            plan_excerpt = gm_plan_raw[:gm_plan_max_chars]

        llm_config = get_user_llm_settings_full(user_id)
        model = (camp.get("model_id") or "").strip() or None
        messages = build_dual_single_messages(
            transcript=transcript, gm_plan_excerpt=plan_excerpt
        )
        raw = generate_chat(messages, model=model, llm_config=llm_config).strip()
        try:
            ps, gn = parse_dual_json_response(raw)
        except Exception as exc:  # noqa: BLE001 — surface parse errors to API
            return {
                "player_summary": "",
                "gm_notes": "",
                "leaked_plan_tokens": [],
                "model_used": model or llm_config.get("model", ""),
                "included_turn_count": len(turns),
                "warning": None,
                "parse_error": str(exc),
                "raw_preview": raw[:2000],
            }

        leaks = leaked_plan_tokens_in_player_summary(ps, gm_plan_raw, transcript)
        return {
            "player_summary": ps,
            "gm_notes": gn,
            "leaked_plan_tokens": leaks,
            "model_used": model or llm_config.get("model", ""),
            "included_turn_count": len(turns),
            "warning": None,
            "parse_error": None,
            "raw_preview": None,
        }
    finally:
        conn.close()


def generate_campaign_summary(
    *,
    campaign_id: int,
    user_id: int,
    max_turns: int = 200,
    audience: SummaryAudience = SUMMARY_AUDIENCE_PLAYER,
) -> dict[str, Any]:
    """
    user_id must match campaigns.owner_user_id (caller enforced in router).
    """
    aud = _normalize_audience(audience)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        camp = _fetch_campaign(conn, campaign_id)
        if not camp:
            raise ValueError("campaign_not_found")
        turns = fetch_narrative_turns(conn, campaign_id, max_turns)
        if not turns:
            return {
                "summary": "",
                "model_used": "",
                "included_turn_count": 0,
                "warning": "Brak tur narracyjnych do podsumowania.",
            }

        transcript = format_transcript(turns, camp["title"] or f"Kampania {campaign_id}", camp["language"] or "pl")
        gm_plan_raw = str(camp.get("gm_plan_json") or "").strip()
        llm_config = get_user_llm_settings_full(user_id)
        model = (camp.get("model_id") or "").strip() or None
        system_prompt = HISTORY_SUMMARY_PROMPT_TEXT
        user_content = transcript
        if aud == SUMMARY_AUDIENCE_PLAYER:
            system_prompt = f"{system_prompt.rstrip()}\n\n{PLAYER_SUMMARY_SYSTEM_APPEND}"
        else:
            system_prompt = f"{system_prompt.rstrip()}\n\n{GM_SUMMARY_SYSTEM_APPEND}"
            formatted_plan = format_gm_plan_block(gm_plan_raw)
            if formatted_plan:
                user_content = f"[PLAN_MG]\n{formatted_plan}\n[/PLAN_MG]\n\n[TRANSKRYPT]\n{transcript}"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": user_content,
            },
        ]
        summary = generate_chat(messages, model=model, llm_config=llm_config).strip()
        return {
            "summary": summary,
            "model_used": model or llm_config.get("model", ""),
            "included_turn_count": len(turns),
            "audience": aud,
        }
    finally:
        conn.close()


def persist_summary(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    summary_text: str,
    model_used: str | None,
    included_turn_count: int,
    audience: SummaryAudience = SUMMARY_AUDIENCE_PLAYER,
) -> int:
    aud = _normalize_audience(audience)
    cur = conn.execute(
        """
        INSERT INTO campaign_ai_summaries (
            campaign_id, summary_text, model_used, included_turn_count, audience
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (campaign_id, summary_text, model_used or "", included_turn_count, aud),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def fetch_latest_saved_summary(
    conn: sqlite3.Connection,
    campaign_id: int,
    *,
    audience: SummaryAudience,
) -> dict[str, Any] | None:
    """Latest saved rollup for a single audience (separate history stacks per audience)."""
    aud = _normalize_audience(audience)
    row = conn.execute(
        """
        SELECT id, campaign_id, summary_text, model_used, included_turn_count, audience, created_at
        FROM campaign_ai_summaries
        WHERE campaign_id = ? AND audience = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (campaign_id, aud),
    ).fetchone()
    return dict(row) if row else None


def generate_and_persist_dual_summary(
    *,
    campaign_id: int,
    user_id: int,
    max_turns: int = 200,
) -> dict[str, Any]:
    """T36 — one LLM call → persist both player + gm summaries to campaign_ai_summaries.

    Returns {"player_saved": bool, "gm_saved": bool, "included_turn_count": int}.
    Best-effort: persists whatever is non-empty.
    """
    result = generate_dual_summary_preview(
        campaign_id=campaign_id,
        user_id=user_id,
        max_turns=max_turns,
    )
    if result.get("parse_error"):
        return {"player_saved": False, "gm_saved": False, "included_turn_count": 0,
                "warning": result.get("parse_error")}

    ps = (result.get("player_summary") or "").strip()
    gn = (result.get("gm_notes") or "").strip()
    turn_count = int(result.get("included_turn_count") or 0)
    model = str(result.get("model_used") or "")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    player_saved = gm_saved = False
    try:
        if ps:
            persist_summary(conn, campaign_id=campaign_id, summary_text=ps,
                            model_used=model, included_turn_count=turn_count,
                            audience=SUMMARY_AUDIENCE_PLAYER)
            player_saved = True
        if gn:
            persist_summary(conn, campaign_id=campaign_id, summary_text=gn,
                            model_used=model, included_turn_count=turn_count,
                            audience=SUMMARY_AUDIENCE_GM)
            gm_saved = True
    finally:
        conn.close()
    return {"player_saved": player_saved, "gm_saved": gm_saved,
            "included_turn_count": turn_count, "warning": result.get("warning")}


def fetch_latest_saved_summary_for_narrative(
    conn: sqlite3.Connection,
    campaign_id: int,
) -> dict[str, Any] | None:
    """
    Skrót dla promptu narracji: preferuj zapis **gm**; gdy brak (np. legacy), użyj **player**.
    """
    gm_row = fetch_latest_saved_summary(conn, campaign_id, audience=SUMMARY_AUDIENCE_GM)
    if gm_row and (gm_row.get("summary_text") or "").strip():
        return gm_row
    return fetch_latest_saved_summary(conn, campaign_id, audience=SUMMARY_AUDIENCE_PLAYER)
