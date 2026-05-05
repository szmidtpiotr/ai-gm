"""T20 — lightweight divergence heuristic between recent player actions and active GM plan."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from app.services.gm_plan_schema import normalize_gm_plan

_TOKEN_RE = re.compile(r"(?u)[^\W\d_]{4,}")
_STOPWORDS = {
    "ktory",
    "ktora",
    "ktore",
    "który",
    "która",
    "które",
    "oraz",
    "poniewaz",
    "ponieważ",
    "there",
    "about",
    "with",
    "from",
    "this",
    "that",
    "jest",
    "beda",
    "będą",
    "bylem",
    "byłem",
    "chce",
    "chcę",
}


def _token_candidates(text: str) -> set[str]:
    tokens = {m.group(0).lower() for m in _TOKEN_RE.finditer(str(text or ""))}
    return {t for t in tokens if t not in _STOPWORDS}


def _active_arc(plan: dict[str, Any]) -> dict[str, Any]:
    arcs = plan.get("arcs") if isinstance(plan.get("arcs"), dict) else {}
    active_id = plan.get("active_arc_id")
    if isinstance(active_id, str) and active_id.strip() and active_id in arcs and isinstance(arcs[active_id], dict):
        return arcs[active_id]
    if arcs:
        first = next(iter(arcs.values()))
        if isinstance(first, dict):
            return first
    return {}


def plan_focus_text(raw_plan: str | None) -> str:
    plan = normalize_gm_plan(raw_plan)
    arc = _active_arc(plan)
    chunks: list[str] = []
    roadmap = arc.get("roadmap")
    if roadmap and str(roadmap).strip():
        chunks.append(str(roadmap).strip())
    goals = arc.get("scene_goals")
    if isinstance(goals, list):
        chunks.extend(str(g).strip() for g in goals if g is not None and str(g).strip())
    hooks = arc.get("hooks")
    if isinstance(hooks, dict):
        for key in ("npcs", "locations"):
            values = hooks.get(key)
            if isinstance(values, list):
                chunks.extend(str(v).strip() for v in values if v is not None and str(v).strip())
    return "\n".join(chunks).strip()


def evaluate_plan_divergence(
    raw_plan: str | None,
    recent_player_texts: list[str],
) -> dict[str, Any]:
    plan_text = plan_focus_text(raw_plan)
    plan_tokens = _token_candidates(plan_text)
    player_blob = "\n".join(str(x or "").strip() for x in recent_player_texts if str(x or "").strip())
    player_tokens = _token_candidates(player_blob)

    if not plan_tokens:
        return {
            "status": "no_plan",
            "score": 0.0,
            "summary": "Brak wystarczającej treści w aktywnym planie MG do oceny dywergencji.",
            "matched_plan_tokens": [],
            "offroad_tokens": [],
            "recent_player_focus": sorted(player_tokens)[:8],
        }
    if not player_tokens:
        return {
            "status": "no_signal",
            "score": 0.0,
            "summary": "Brak wystarczających działań gracza w ostatnich turach do oceny dywergencji.",
            "matched_plan_tokens": [],
            "offroad_tokens": [],
            "recent_player_focus": [],
        }

    matched = sorted(plan_tokens & player_tokens)
    offroad = sorted(player_tokens - plan_tokens)
    overlap_ratio = len(matched) / max(1, len(player_tokens))
    offroad_score = len(offroad) / max(1, len(player_tokens))

    if matched and overlap_ratio >= 0.45:
        status = "aligned"
        score = round(overlap_ratio, 3)
        summary = "Ostatnie działania gracza są w większości zgodne z aktywnym planem / celami sceny."
    elif not matched and len(offroad) >= 3:
        status = "diverged"
        score = round(min(1.0, 0.6 + offroad_score / 2.0), 3)
        summary = "Gracz prawdopodobnie schodzi z osi aktywnego planu i ciągnie scenę w inny kierunek."
    else:
        status = "mixed"
        score = round(max(overlap_ratio, min(1.0, offroad_score)), 3)
        summary = "W działaniach gracza widać częściowe odejście od aktywnego planu; warto rozważyć korektę planu MG."

    return {
        "status": status,
        "score": score,
        "summary": summary,
        "matched_plan_tokens": matched[:8],
        "offroad_tokens": offroad[:8],
        "recent_player_focus": sorted(player_tokens)[:8],
    }


def recent_player_turn_texts(
    conn: sqlite3.Connection,
    campaign_id: int,
    *,
    limit: int = 4,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT user_text
        FROM campaign_turns
        WHERE campaign_id = ? AND route = 'narrative' AND COALESCE(TRIM(user_text), '') != ''
        ORDER BY turn_number DESC
        LIMIT ?
        """,
        (int(campaign_id), int(limit)),
    ).fetchall()
    texts = [str(r["user_text"] or "").strip() for r in rows if str(r["user_text"] or "").strip()]
    texts.reverse()
    return texts


def evaluate_campaign_plan_divergence(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    raw_plan: str | None,
    current_user_text: str | None = None,
    limit: int = 4,
) -> dict[str, Any]:
    texts = recent_player_turn_texts(conn, campaign_id, limit=limit)
    cur = str(current_user_text or "").strip()
    if cur:
        texts.append(cur)
    out = evaluate_plan_divergence(raw_plan, texts)
    out["recent_player_turns"] = texts[-limit:]
    return out


def divergence_prompt_block(result: dict[str, Any]) -> str:
    status = str(result.get("status") or "")
    if status not in {"mixed", "diverged"}:
        return ""
    matched = ", ".join(str(x) for x in (result.get("matched_plan_tokens") or [])[:6]) or "brak"
    offroad = ", ".join(str(x) for x in (result.get("offroad_tokens") or [])[:6]) or "brak"
    score = result.get("score")
    summary = str(result.get("summary") or "").strip()
    return (
        "## Heurystyka dywergencji gracza względem planu MG\n"
        f"- status: {status}\n"
        f"- score: {score}\n"
        f"- zgodne tokeny: {matched}\n"
        f"- poza planem: {offroad}\n"
        f"- interpretacja: {summary}\n"
        "To jest miękki sygnał. Nie blokuj gry; jeśli gracz konsekwentnie idzie w nowy kierunek, "
        "improwizuj fabularnie i dopuść aktualizację planu MG przez operatora."
    )
