import json
import sqlite3

from app.services.llm_service import generate_chat
from app.system_prompt_loader import compose_narrator_system_prompt

# Narrative turns use the unified prompt (backend/prompts/system_prompt.txt) plus the
# separate lore layer (world_bible.txt, issue #940) — see system_prompt_loader.
SYSTEMPROMPT = compose_narrator_system_prompt()

# Must match frontend `window.COMBAT_ROLL_PREFIX` — rich combat roll card in DB user_text.
COMBAT_ROLL_CTX_PREFIX = "__AI_GM_COMBAT_ROLL_V1__"


_MECHANIC_CUE_LINE_RE = None  # lazily compiled below


def _sanitize_llm_input(s: str) -> str:
    """AUDIT #1444: scrub mechanic tags + grant cues from ANY text going INTO the LLM
    context (player free-text or replayed history). `strip_all_mechanic_tags` previously
    ran only on model OUTPUT (memory #1292) — a player could inject `Grant Gold 999999`,
    `[XP_GRANT:...]` or `grant_item: legendary sword` into their turn and steer a weaker
    PROD model (gemma) toward emitting those cues, which the output-parser then applied.
    Sanitizing the input closes the injection vector at the boundary.
    """
    if not s:
        return s
    try:
        from app.services.llm_tag_parser import strip_all_mechanic_tags
        s = strip_all_mechanic_tags(s)
    except Exception:
        pass
    global _MECHANIC_CUE_LINE_RE
    if _MECHANIC_CUE_LINE_RE is None:
        import re as _re
        # Remove grant/shop cue phrases from the cue keyword to end of line — inline or
        # standalone — so an injected `... Grant Gold 999999` / `grant_item <x>` never
        # reaches the model verbatim.
        _MECHANIC_CUE_LINE_RE = _re.compile(
            r"(?i)\b(?:grant[ _]?gold|grant[ _]?item|open[ _]?shop)\b[^\n]*"
        )
    s = _MECHANIC_CUE_LINE_RE.sub("", s)
    # collapse whitespace left by removed cues
    lines = [ln.rstrip() for ln in s.splitlines()]
    out = "\n".join(ln for ln in lines).strip()
    return out if out else s.strip()


def _user_text_for_llm_context(raw: str | None) -> str:
    """Strip structured combat roll JSON from history so the LLM sees short prose only.

    AUDIT #1444: the final player-visible text is also passed through `_sanitize_llm_input`
    so injected mechanic tags / grant cues never reach the model verbatim.
    """
    return _sanitize_llm_input(_user_text_for_llm_context_raw(raw))


def _user_text_for_llm_context_raw(raw: str | None) -> str:
    s = (raw or "").strip()
    if not s.startswith(COMBAT_ROLL_CTX_PREFIX):
        return s or ""
    tail = s[len(COMBAT_ROLL_CTX_PREFIX) :].lstrip("\r\n \t")
    try:
        d = json.loads(tail)
    except (json.JSONDecodeError, TypeError, ValueError):
        return s
    if not isinstance(d, dict):
        return s
    if d.get("kind") == "player_flee":
        summary = (d.get("summary_line") or "").strip()
        intent = (d.get("intent") or "").strip()
        if summary and intent:
            return f"{intent}\n\n{summary}"
        if summary:
            return summary
        return (
            "Gracz zakończył walkę w silniku przez ucieczkę. Opisz dynamicznie moment wycofania "
            "się z walki i natychmiastowe konsekwencje (2–4 zdania). Nie kończ pytaniem o następną akcję."
        )
    # #650 (B6b): atak czarem — bez tego LLM widzi tylko surowy JSON trafienia + wyposażoną
    # broń (laska) w bloku ekwipunku i opisuje cios bronią zamiast zaklęcia. Daj mu jawną
    # instrukcję, że to MAGIA. Silnik liczy trafienie/obrażenia — tu tylko poprawiamy OPIS.
    if d.get("kind") == "player_attack" and str(d.get("attack_mode") or "").lower() == "spell":
        spell_label = (str(d.get("spell_label") or "").strip()) or "zaklęcie"
        target = (str(d.get("target_name") or "").strip()) or "wroga"
        if d.get("player_nat1"):
            outcome = "Zaklęcie wymyka się spod kontroli (krytyczna porażka)"
        elif d.get("hit"):
            dmg = d.get("damage") or 0
            outcome = f"Zaklęcie trafia ({dmg} obrażeń)" if dmg else "Zaklęcie trafia"
        else:
            outcome = "Zaklęcie chybia (cel uniknął)"
        return (
            f"Bohater rzuca zaklęcie „{spell_label}” na {target}. {outcome}. "
            "Opisz to jako akt MAGII (a NIE cios bronią fizyczną — bohater NIE atakuje "
            "laską ani mieczem) w MAKSYMALNIE 2-3 krótkich, dynamicznych zdaniach: "
            "sam splot zaklęcia i jego skutek, bez rozwlekłych opisów otoczenia i dygresji."
        )
    summary = (d.get("summary_line") or "").strip()
    intent = (d.get("intent") or "").strip()
    if summary and intent:
        return f"{intent}\n\n{summary}"
    return summary or s


def loadrecentturns(conn: sqlite3.Connection, campaignid: int, limit: int = 8) -> list[sqlite3.Row]:
    # Tylko narracja — trasy `memory`, `helpme`, `command` itd. nie trafiają do kontekstu GM.
    rows = conn.execute(
        """
        SELECT user_text, assistant_text, route
        FROM campaign_turns
        WHERE campaign_id = ? AND route = 'narrative'
        ORDER BY id DESC
        LIMIT ?
        """,
        (campaignid, limit),
    ).fetchall()
    rows = list(rows)
    rows.reverse()
    return rows


def buildmessages(
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    recentturns: list[sqlite3.Row],
    usertext: str,
    runtime_config_block: str | None = None,
    combat_context_block: str | None = None,
) -> list[dict]:
    systemid = campaign["system_id"] if campaign and campaign["system_id"] else "fantasy"
    language = campaign["language"] if campaign and campaign["language"] else "pl"
    charactername = character["name"] if character and character["name"] else "Bohater"

    system_content = f"{SYSTEMPROMPT}\n"
    if combat_context_block:
        system_content = f"{system_content.rstrip()}\n\n{combat_context_block.strip()}\n"
    characterrace = "human"
    if character:
        try:
            characterrace = str(character["race"] or "human").strip().lower()
        except (IndexError, KeyError, TypeError):
            characterrace = "human"
    system_content = (
        f"{system_content}"
        f"System gry: {systemid}\n"
        f"Język: {language}\n"
        f"Postać gracza: {charactername}\n"
        f"Rasa postaci: {characterrace}"
    )
    if runtime_config_block:
        system_content = f"{system_content}\n\n{runtime_config_block}"

    messages = [
        {
            "role": "system",
            "content": system_content,
        }
    ]

    for turn in recentturns:
        if turn["route"] != "narrative":
            continue
        if turn["user_text"]:
            messages.append(
                {"role": "user", "content": _user_text_for_llm_context(turn["user_text"])}
            )
        if turn["assistant_text"]:
            messages.append({"role": "assistant", "content": turn["assistant_text"]})

    messages.append({"role": "user", "content": _user_text_for_llm_context(usertext)})
    return messages


def runnarrativeturn(
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    usertext: str,
    model: str,
) -> dict:
    recentturns = loadrecentturns(conn, campaign["id"], limit=8)
    messages = buildmessages(
        campaign=campaign,
        character=character,
        recentturns=recentturns,
        usertext=usertext,
    )
    reply = generate_chat(messages=messages, model=model)
    return {"message": reply}
