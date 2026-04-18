"""OOC /helpme advisor — osobny prompt i kontekst; trasy `helpme` nie trafiają do historii narracyjnej."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from app.helpme_prompt_loader import load_helpme_prompt_text
from app.services.dice import parse_character_sheet
from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full


def _load_last_narrative_exchanges(conn: sqlite3.Connection, campaign_id: int, limit: int = 5) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT user_text, assistant_text
        FROM campaign_turns
        WHERE campaign_id = ? AND route = 'narrative' AND (
            (user_text IS NOT NULL AND TRIM(user_text) != '')
            OR (assistant_text IS NOT NULL AND TRIM(assistant_text) != '')
        )
        ORDER BY id DESC
        LIMIT ?
        """,
        (campaign_id, limit),
    ).fetchall()
    return list(reversed(rows))


def _format_recent_messages(rows: list[sqlite3.Row]) -> str:
    if not rows:
        return "(brak ostatnich tur narracyjnych)"
    parts: list[str] = []
    for i, r in enumerate(rows, start=1):
        u = (r["user_text"] or "").strip()
        a = (r["assistant_text"] or "").strip()
        block = f"--- Wymiana {i} ---\n"
        if u:
            block += f"Gracz: {u}\n"
        if a:
            block += f"GM (narracja): {a}\n"
        parts.append(block.rstrip())
    return "\n\n".join(parts)


def _scene_line(character: sqlite3.Row) -> str:
    loc = (character["location"] or "").strip() if character["location"] is not None else ""
    if loc:
        return loc
    sheet_raw = character["sheet_json"] or ""
    if not sheet_raw.strip():
        return "(nieznana — brak lokacji i pustej karty)"
    try:
        data = json.loads(sheet_raw)
    except json.JSONDecodeError:
        return "(karta: surowy JSON, nie udało się sparsować)"
    if isinstance(data, dict):
        for key in ("current_scene", "scene", "location", "place", "where"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return "(scena nie zapisana w polu location ani typowych kluczach sheet_json)"


def _stats_summary(character: sqlite3.Row) -> str:
    sheet_raw = character["sheet_json"] or ""
    if not sheet_raw.strip():
        return "(brak sheet_json)"
    sheet = parse_character_sheet(sheet_raw)
    if not sheet:
        return f"(surowa karta, skrót): {sheet_raw[:1200]}"
    lines: list[str] = []
    name = character["name"] or "Postać"
    lines.append(f"Imię: {name}")
    stats = sheet.get("stats") if isinstance(sheet.get("stats"), dict) else {}
    if stats:
        lines.append("Statystyki: " + ", ".join(f"{k}={v}" for k, v in sorted(stats.items())[:12]))
    hp = sheet.get("hp")
    if hp is not None:
        lines.append(f"HP: {hp}")
    ac = sheet.get("ac")
    if ac is not None:
        lines.append(f"AC: {ac}")
    inv = sheet.get("inventory")
    if inv:
        lines.append("Ekwipunek (skrót): " + re.sub(r"\s+", " ", str(inv))[:400])
    return "\n".join(lines) if len(lines) > 1 else (lines[0] if lines else "(pusta karta)")


def run_helpme_advisor(
    *,
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    character: sqlite3.Row,
    topic: str,
    user_id: int,
    model: str | None = None,
) -> dict[str, Any]:
    """Jednorazowe wywołanie LLM z promptem OOC; narracyjny system_prompt nie jest używany."""
    recent = _load_last_narrative_exchanges(conn, int(campaign["id"]), limit=5)
    recent_block = _format_recent_messages(recent)
    scene = _scene_line(character)
    stats_block = _stats_summary(character)
    lang = (campaign["language"] or "pl").strip() if campaign["language"] else "pl"
    system_id = (campaign["system_id"] or "fantasy").strip() if campaign["system_id"] else "fantasy"

    ctx = (
        f"System gry (metadane): {system_id}\n"
        f"Język sesji: {lang}\n\n"
        f"Aktualna scena / lokacja (best effort):\n{scene}\n\n"
        f"Karta postaci (skrót):\n{stats_block}\n\n"
        f"Ostatnie wymiany narracyjne (max 5, tylko route=narrative):\n{recent_block}\n"
    )

    base = load_helpme_prompt_text().rstrip()
    system_content = (
        f"{base}\n\n"
        f"--- KONTEKST (tylko informacja dla Ciebie; nie jest to dialog IC) ---\n{ctx}"
    )

    t = (topic or "").strip()
    if t:
        user_content = f"Pytanie / prośba gracza (OOC):\n{t}"
    else:
        user_content = (
            "Gracz wywołał /helpme bez dodatkowego pytania. "
            "Jako doradca OOC: krótko podaj praktyczne opcje mechaniczne / taktyczne (2–4 zdania), "
            "bez narracji sceny — wyłącznie na podstawie kontekstu powyżej."
        )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    llm_config = get_user_llm_settings_full(user_id)
    resolved = (model or "").strip() or None
    reply = generate_chat(messages=messages, model=resolved, llm_config=llm_config)
    text = (reply or "").strip()
    if not text:
        raise RuntimeError("empty_helpme_response")
    return {"message": text}
