"""
[T01 / S11b] Dual rollup experiment: one LLM call returning JSON vs two calls.

Used to validate variant A (single prompt, two fields) before persisting dual
rows in DB (T02). Parsing and leak heuristics are unit-tested without a live LLM.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Variant A — one completion, strict JSON (Polish instructions; model may still reply in wrong shape — tests cover parser).
DUAL_SINGLE_SYSTEM_PROMPT = """Jesteś narzędziem do podziału podsumowania kampanii RPG na DWA bloki.

## Wyjście
Odpowiedz WYŁĄCZNIE jednym obiektem JSON (bez markdown, bez komentarzy przed/po), dokładnie w formacie:
{"player_summary":"...","gm_notes":"..."}

## player_summary (dla gracza / notatnik)
- Bazuj WYŁĄCZNIE na sekcji TRANSKRYPT poniżej.
- NIE dodawaj imion, miejsc ani faktów, które NIE występują w TRANSKRYPCIE — nawet jeśli pojawią się w PLANIE MG.
- Nie oceniaj gracza; trzecia osoba; zwięźle, struktura jak w dobrym recapie sesji.

## gm_notes (dla Mistrza Gry / silnik)
- Możesz łączyć TRANSKRYPT z PLANEM MG (jeśli plan nie jest pusty).
- Tutaj dozwolone są spostrzeżenia fabularne i tropy z planu, które nie padły jeszcze w czacie.

## PLAN MG (opcjonalnie)
Jeśli w wiadomości użytkownika jest blok [PLAN_MG]…[/PLAN_MG], traktuj go jako kontekst TYLKO dla pola gm_notes — nigdy jako źródło faktów do player_summary.
"""


def build_dual_single_messages(
    *,
    transcript: str,
    gm_plan_excerpt: str | None,
) -> list[dict[str, str]]:
    """Messages for variant A: one `generate_chat` call → JSON with two fields."""
    plan = (gm_plan_excerpt or "").strip()
    if plan:
        user_body = (
            "[PLAN_MG]\n"
            + plan
            + "\n[/PLAN_MG]\n\n"
            "[TRANSKRYPT]\n"
            + transcript.strip()
        )
    else:
        user_body = "[PLAN_MG]\n(brak)\n[/PLAN_MG]\n\n[TRANSKRYPT]\n" + transcript.strip()
    return [
        {"role": "system", "content": DUAL_SINGLE_SYSTEM_PROMPT},
        {"role": "user", "content": user_body},
    ]


def parse_dual_json_response(raw: str) -> tuple[str, str]:
    """
    Parse model output into (player_summary, gm_notes).
    Accepts optional ```json ... ``` fence.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    data: Any = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("dual_summary_not_object")
    ps = (data.get("player_summary") or data.get("player") or "").strip()
    gn = (data.get("gm_notes") or data.get("gm_summary") or "").strip()
    if not ps and not gn:
        raise ValueError("dual_summary_empty")
    return ps, gn


def _token_candidates(text: str) -> set[str]:
    """Rough word tokens: 4+ Unicode letters (PL diacritics included)."""
    return {m.group(0).lower() for m in re.finditer(r"(?u)[^\W\d_]{4,}", text)}


def plan_tokens_not_in_transcript(gm_plan: str, transcript: str) -> set[str]:
    """Tokens that appear in plan but not in transcript (lowercase)."""
    in_plan = _token_candidates(gm_plan)
    blob = transcript.lower()
    return {t for t in in_plan if t not in blob}


def leaked_plan_tokens_in_player_summary(
    player_summary: str,
    gm_plan: str,
    transcript: str,
) -> list[str]:
    """
    Heuristic: plan-only tokens (length >= 4) that show up in player_summary.
    Used to flag variant A failures in experiments/tests.
    """
    suspicious = plan_tokens_not_in_transcript(gm_plan, transcript)
    if not suspicious:
        return []
    ps_lower = player_summary.lower()
    return sorted(t for t in suspicious if t in ps_lower)
