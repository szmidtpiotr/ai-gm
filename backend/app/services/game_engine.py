import random
import re
import sqlite3
import json

from app.core.logging import get_logger
from app.core.turn_engine import buildmessages, loadrecentturns
from app.services.config_service import build_runtime_config_block
from app.services.gm_plan_schema import format_gm_plan_block
from app.services.dice import infer_roll_type, parse_character_sheet
from app.services.llm_service import generate_chat
from app.services.solo_death_service import DEATH_SAVE_FAILURE_THRESHOLD


logger = get_logger(__name__)


def build_travel_hint_block(discovered_hexes: list[dict] | None, turns_at_location: int, max_pills: int = 5) -> str | None:
    """Build [TRAVEL_HINT: ...] block from discovered nearby locations.

    Returns None if:
    - turns_at_location < 5 (STORY_STALE not active yet)
    - discovered_hexes is empty or None

    Otherwise returns: [TRAVEL_HINT: [Loc1] [Loc2] ... — wskaż bohaterowi bezpieczne kierunki]
    Pills limited to max_pills (default 5) to avoid LLM distraction.
    """
    if turns_at_location < 5 or not discovered_hexes:
        return None

    limited = discovered_hexes[:max_pills]
    pills = " ".join([f"[{hex.get('name', 'Unknown')}]" for hex in limited])
    return f"[TRAVEL_HINT: {pills} — wskaż bohaterowi bezpieczne kierunki]"


def resolve_enemy_loot(enemy_key: str) -> list[dict]:
    """
    Roll this enemy's drop_chance, then weight-pick one row from its loot table.
    Returns [{source_type, source_key, qty}, ...] with no duplicated catalog data.
    """
    from app.services.admin_config import DB_PATH, list_loot_entries

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT loot_table_key, drop_chance FROM game_config_enemies WHERE key = ?",
            (enemy_key,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return []
    lt = row["loot_table_key"]
    if not lt:
        return []
    dc = float(row["drop_chance"] if row["drop_chance"] is not None else 1.0)
    if random.random() > dc:
        return []

    entries = list_loot_entries(str(lt))
    if not entries:
        return []
    total_w = sum(max(1, int(e.get("weight") or 0)) for e in entries)
    if total_w < 1:
        return []
    r = random.random() * total_w
    acc = 0.0
    chosen = entries[-1]
    for e in entries:
        w = max(1, int(e.get("weight") or 0))
        acc += w
        if r < acc:
            chosen = e
            break
    st = str(chosen.get("source_type") or "item")
    if st == "item":
        sk = chosen.get("item_key")
    elif st == "consumable":
        sk = chosen.get("consumable_key")
    else:
        sk = chosen.get("weapon_key")
    qmin = max(1, int(chosen.get("qty_min") or 1))
    qmax = max(qmin, int(chosen.get("qty_max") or qmin))
    qty = random.randint(qmin, qmax)
    return [{"source_type": st, "source_key": sk, "qty": qty}]


# Heuristic: player message may signal attack intent (Polish + common enemy words).
_COMBAT_VERB_HINT = re.compile(
    r"(atak|ataku|ciach|cios|tnę|doby|broń|miecz|topór|łuk|kusz|"
    r"noż|walcz|strzel|rzucam|pięści|bandyt|straż|goblin|ork|"
    r"przeciwn|wrog|zabij|zran|uderz|tnij|rani)",
    re.IGNORECASE,
)


def _inactive_combat_tag_reminder(user_text: str | None) -> str:
    """
    When no active combat in DB, the model often obeys FORMAT CUE (Roll …) instead of [COMBAT_START].
    Append a high-salience block so Phase 8 combat can start from GM text.
    """
    lines = (
        "[MECHANIKA — WALKA W SYSTEMIE: NIEAKTYWNA]\n"
        "W tej kampanii nie ma jeszcze aktywnej walki w silniku. Gdy w TEJ odpowiedzi dochodzi do pierwszego starcia "
        "(wrogowie atakują, leci pocisk, bójka, gracz dobiera broń by uderzyć lub strzelić w cel), "
        "OSTATNIA linia całej odpowiedzi MUSI być wyłącznie tagiem w osobnej linii: [COMBAT_START:klucz] "
        "(patrz INICJOWANIE WALKI, PRZYPADEK 2, sekcja HIERARCHIA).\n"
        "Zabronione jako ostatnia linia w tej sytuacji: jakakolwiek linia «Roll … d20» ze słownika — w tym Initiative i Attack."
    )
    if user_text and _COMBAT_VERB_HINT.search(user_text):
        lines += (
            "\n\n[TREŚĆ TURY GRACZA — możliwy atak]\n"
            "Wiadomość gracza sugeruje przemoc lub atak. Jeśli przechodzisz do walki, w TEJ odpowiedzi zakończ "
            "[COMBAT_START:…], a nie linią Roll ze słownika."
        )
    return lines


import re as _re_skill
_SKILL_VERB_HINT = _re_skill.compile(
    r"\b(próbuj|próbować|spróbuj|staram|chcę|zamiarzam|usiłuj|"
    r"skrad|przekrad|przekonaj|perswad|oszuk|zastraszy|przeszuk|spost|zauważ|"
    r"wytrop|przetrwaj|wylecz|zidentyfik|zbadaj|ident|użyj|kradnę|włamuj|wyważam|"
    r"skaczę|wspinaj|bieg|uciekam|uchylam|unikam|"
    r"kuj|wykuj|wykuć|oceniam|oszacuj|napraw|naprawiam|konstruuj|tworzę|robię|"
    r"rzemiosł|kowalstwo|alchemi|leczę|badan|tropię|ukryj|ukrywam|szpieg)\b",
    _re_skill.IGNORECASE,
)

import unicodedata as _unicodedata


def _normalize_risk_text(text: str) -> str:
    """Lowercase + strip accents for keyword matching."""
    nfkd = _unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not _unicodedata.combining(c))


def _detect_risky_intent(conn, user_text: str) -> "dict | None":
    """Check user_text against game_config_skill_risk_categories keywords.

    Returns {"category_key", "skill_key", "default_dc"} or None.
    Table is seeded by U7 migration; graceful fallback if table missing.
    """
    if not user_text or not conn:
        return None
    try:
        rows = conn.execute(
            "SELECT category_key, skill_key, default_dc, keywords "
            "FROM game_config_skill_risk_categories WHERE enabled=1"
        ).fetchall()
    except Exception:
        return None

    normalized = _normalize_risk_text(user_text)
    for row in rows:
        raw_kws = (row["keywords"] if hasattr(row, "__getitem__") else row[3]) or ""
        skill_key = row["skill_key"] if hasattr(row, "__getitem__") else row[1]
        default_dc = row["default_dc"] if hasattr(row, "__getitem__") else row[2]
        category_key = row["category_key"] if hasattr(row, "__getitem__") else row[0]
        for kw in raw_kws.split(","):
            kw = _normalize_risk_text(kw.strip())
            if kw and kw in normalized:
                return {
                    "category_key": category_key,
                    "skill_key": skill_key,
                    "default_dc": int(default_dc),
                }
    return None


def _skill_test_tag_instruction(conn, campaign_id: int, user_text: str | None) -> str | None:
    """
    Inject skill test instructions when player text hints at a skill use.
    Loads skills from DB with descriptions so LLM picks the right custom key.
    """
    if not user_text:
        return None
    if not _SKILL_VERB_HINT.search(user_text):
        return None

    # Load skills from DB with descriptions — crucial so LLM knows WHEN to use custom skills
    skill_lines = []
    try:
        if conn:
            rows = conn.execute(
                "SELECT key, label, linked_stat, description FROM game_config_skills "
                "ORDER BY sort_order"
            ).fetchall()
            for r in rows:
                desc = str(r["description"] or "").strip()
                desc_part = f" — {desc[:60]}" if desc else ""
                skill_lines.append(f"  {r['key']} ({r['label']}, {r['linked_stat']}){desc_part}")
    except Exception:
        skill_lines = ["  stealth, lockpick, perception, persuasion, athletics, arcana, medicine, lore"]

    skills_block = "\n".join(skill_lines)

    return (
        "[MECHANIKA — TESTY UMIEJĘTNOŚCI — WAŻNE]\n"
        "Wiadomość gracza wymaga testu umiejętności. Użyj pola roll_cue w JSON:\n"
        "  \"roll_cue\": \"Roll <klucz_umiejętności> d20\"\n\n"
        "ZASADA: używaj DOKŁADNIE tych kluczy (key) z listy poniżej. "
        "NIE używaj angielskich odpowiedników z D&D (np. 'Investigation', 'Athletics' itp.) "
        "— użyj polskiego klucza z listy.\n\n"
        "DOSTĘPNE UMIEJĘTNOŚCI:\n"
        f"{skills_block}\n\n"
        "Przykłady:\n"
        "  \"roll_cue\": \"Roll stealth d20\"       ← skradanie\n"
        "  \"roll_cue\": \"Roll kowalstwo d20\"     ← ocena/naprawa broni, wykuwanie\n"
        "  \"roll_cue\": \"Roll persuasion d20\"    ← przekonywanie NPC\n"
        "  \"roll_cue\": \"Roll perception d20\"    ← spostrzeżenie czegoś\n\n"
        "Nie opisuj wyniku rzutu w narracji — gracz sam rzuci kością."
    )


def _death_mechanica_system_append(
    character: sqlite3.Row | None, roll_result_data: dict | None
) -> str | None:
    """
    While the character has 1–2 death save failures, force the GM to end each non-roll
    narrative with 'Roll Death Save d20'. Skip when this turn is a death save resolution.
    """
    if not character:
        return None
    sheet = parse_character_sheet(character["sheet_json"])
    failures = int(sheet.get("death_save_failures") or 0)
    if failures < 1 or failures >= DEATH_SAVE_FAILURE_THRESHOLD:
        return None
    if roll_result_data and roll_result_data.get("test") == "death_save":
        return None
    return (
        "[MECHANIKA — STAN ŚMIERCI]\n"
        "Postać jest nieprzytomna i walczy o życie.\n"
        f"Liczba nieudanych rzutów śmierci: {failures} / {DEATH_SAVE_FAILURE_THRESHOLD}\n"
        "Zasada: na końcu KAŻDEJ tury (nie rzutu) musisz dodać dokładnie tę linię jako ostatnią:\n"
        "Roll Death Save d20\n"
        "Nie narruj wyzdrowienia. Nie kończ stanu śmierci fabularnie. Tylko rzut może zmienić ten stan."
    )


def _inject_dungeon_loch_context(run: dict, character, messages: list[dict]) -> None:
    """L13c (#689): inject the current tile-dungeon room as the overriding context.

    When the player is inside a tile dungeon, ALL overworld context (location, NPCs,
    ŚWIAT terrain, travel hints) is suppressed by the caller and this block replaces
    it — so the narrator colorizes the current dungeon room instead of inventing an
    overworld scene (e.g. a forest) or offering travel.
    """
    graph = run.get("graph") or {}
    nodes = graph.get("nodes") or {}
    positions = run.get("positions") or {}
    nid = next(iter(positions.values()), None) or graph.get("entry_node")
    node = nodes.get(nid) or {}
    content = node.get("content") or {}
    desc = content.get("room_description") or ""
    label = content.get("label") or "pomieszczenie lochu"
    open_doors = node.get("doors_open") or {}
    door_hints = node.get("door_hints") or {}
    PL = {"N": "północ", "S": "południe", "E": "wschód", "W": "zachód"}
    dirs = [d for d in ("N", "S", "E", "W") if open_doors.get(d)]
    door_str = ", ".join(
        (f"{PL[d]} ({door_hints[d]})" if door_hints.get(d) else PL[d]) for d in dirs
    ) or "brak otwartych drzwi"
    enemies = content.get("enemies") or []
    cleared = bool(node.get("cleared"))
    foes_line = (
        "W pomieszczeniu są wrogowie — trwa lub grozi walka.\n"
        if (enemies and not cleared)
        else "Pomieszczenie jest bezpieczne (wrogowie pokonani lub brak).\n"
    )
    block = (
        "[LOCH — NADRZĘDNY KONTEKST]\n"
        f"Bohater jest WEWNĄTRZ lochu, w pomieszczeniu: {label}.\n"
        f"Opis pomieszczenia: {desc}\n"
        f"Wyjścia (drzwi): {door_str}\n"
        f"{foes_line}"
        "ZASADY NARRACJI W LOCHU:\n"
        "- Opisuj WYŁĄCZNIE to pomieszczenie lochu. To NIE jest las, pole ani otwarty świat.\n"
        "- Nie wymyślaj nowych lokacji, NPC, podróży ani wyjść poza wymienione drzwi.\n"
        "- Koloryzuj 1–2 zdaniami zgodnie z opisem; nie zmieniaj faktów.\n"
        "- Ruch między pomieszczeniami i akcje (skrzynia, zagadka) obsługują przyciski UI, "
        "nie narracja. Jeśli gracz pyta „co dalej”, wskaż, że może wybrać drzwi przyciskami kierunków.\n"
        "[/LOCH]"
    )
    msg = {"role": "system", "content": block}
    ins_at = len(messages) - 1 if (messages and messages[-1].get("role") == "user") else len(messages)
    messages.insert(ins_at, msg)


_SWIAT_IMPERATIVE_OUTDOOR = (
    "POWYŻSZY BLOK ŚWIAT TO AKTUALNA POZYCJA BOHATERA — nadrzędny "
    "wobec wcześniejszych tur. Jeśli teren różni się od miejsca "
    "opisywanego w poprzednich turach, bohater PRZEMIEŚCIŁ SIĘ: "
    "opisuj OBECNY teren (zgodnie z `teren:` i `Atmosfera terenu:`), "
    "nie kontynuuj scenerii ze starych tur."
)


def build_swiat_imperative(
    conn: sqlite3.Connection, current_location_id: int | None
) -> str:
    """#750 — Wybiera imperatyw dołączany pod blok === ŚWIAT ===.

    Gdy ``current_location_id`` wskazuje na sub-lokację (``location_type='sub'`` —
    wnętrze, np. karczma), bohater jest W POMIESZCZENIU na hexie, NIE na otwartym
    terenie. Twardy imperatyw „bohater PRZEMIEŚCIŁ SIĘ / opisuj teren" błędnie
    każe LLM porzucić scenę wnętrza i narratować teren hexa (np. las pod karczmą).
    W tym wypadku ŚWIAT zostaje jako kontekst otoczenia, ale bez nakazu zmiany
    scenerii. Dla otwartego terenu (macro / brak sub-lokacji) imperatyw bez zmian.
    """
    if not current_location_id:
        return _SWIAT_IMPERATIVE_OUTDOOR
    try:
        loc = conn.execute(
            "SELECT label, location_type FROM game_locations "
            "WHERE id = ? AND COALESCE(is_active, 1) = 1",
            (int(current_location_id),),
        ).fetchone()
    except Exception:
        return _SWIAT_IMPERATIVE_OUTDOOR
    if not loc or (loc["location_type"] or "") != "sub":
        return _SWIAT_IMPERATIVE_OUTDOOR

    label = loc["label"]
    loc_txt = f" „{label}”" if label else ""
    return (
        f"BOHATER JEST WEWNĄTRZ LOKACJI{loc_txt} (sub-lokacja na tym hexie). "
        "POWYŻSZY BLOK ŚWIAT to teren i otoczenie NA ZEWNĄTRZ — kontekst pomocniczy, "
        "NIE pozycja bohatera. Kontynuuj bieżącą scenę WEWNĄTRZ lokacji z poprzednich "
        "tur; NIE narratuj terenu hexa jako obecnego miejsca. Bohater opuszcza wnętrze "
        "dopiero gdy SAM zadeklaruje wyjście."
    )


def _inject_location_llm_context(
    conn: sqlite3.Connection, campaign_id: int, messages: list[dict]
) -> None:
    """8D-LOC-1: blok [LOCATION CONTEXT] jako druga wiadomość systemowa (po głównym system prompt)."""
    from app.services.location_config_service import get_bool_flag
    from app.services.location_context_injector import (
        build_location_context_block,
        get_session_id_for_campaign,
    )

    if not messages:
        return

    sid = get_session_id_for_campaign(conn, campaign_id)
    if sid is None:
        logger.info("location_context_skipped", session_id=None, reason="no_session")
        return
    if not get_bool_flag("location_integrity_enabled", sid, default=True):
        logger.info(
            "location_context_skipped", session_id=str(sid), reason="flag_disabled"
        )
        return

    try:
        loc_block = build_location_context_block(sid, conn)
        if loc_block:
            known_count = sum(
                1 for ln in loc_block.splitlines() if ln.startswith("  - { ")
            )
            messages.insert(1, {"role": "system", "content": loc_block})
            logger.info(
                "location_context_injected",
                session_id=str(sid),
                known_count=known_count,
            )
        else:
            logger.info(
                "location_context_skipped",
                session_id=str(sid),
                reason="no_current_location",
            )
    except Exception as exc:
        logger.warning(
            "location_context_injection_failed",
            session_id=str(sid),
            error=str(exc),
        )


def build_npc_context_block(conn: sqlite3.Connection, campaign_id: int) -> str | None:
    """
    Build [NPC CONTEXT] block for LLM:
    - location-assigned NPC for current location
    - global NPC (no rows in npc_locations)
    """
    from app.services.location_context_injector import get_session_id_for_campaign

    sid = get_session_id_for_campaign(conn, campaign_id)
    current_key: str | None = None
    if sid is not None:
        row = conn.execute(
            """
            SELECT gl.key
            FROM game_sessions gs
            LEFT JOIN game_locations gl ON gl.id = gs.current_location_id
            WHERE gs.id = ?
            """,
            (str(sid),),
        ).fetchone()
        if row and row["key"]:
            current_key = str(row["key"])

    if current_key:
        rows = conn.execute(
            """
            SELECT DISTINCT n.key, n.label, n.npc_type, n.description, n.personality_json
            FROM npcs n
            WHERE COALESCE(n.is_active, 1) = 1
              AND (
                EXISTS (
                    SELECT 1 FROM npc_locations nl
                    WHERE nl.npc_id = n.id AND nl.location_key = ?
                )
                OR NOT EXISTS (
                    SELECT 1 FROM npc_locations nl2 WHERE nl2.npc_id = n.id
                )
              )
            ORDER BY n.npc_type, n.label COLLATE NOCASE
            """,
            (current_key,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT n.key, n.label, n.npc_type, n.description, n.personality_json
            FROM npcs n
            WHERE COALESCE(n.is_active, 1) = 1
              AND NOT EXISTS (
                SELECT 1 FROM npc_locations nl WHERE nl.npc_id = n.id
              )
            ORDER BY n.npc_type, n.label COLLATE NOCASE
            """
        ).fetchall()

    if not rows:
        return None

    lines = ["[NPC CONTEXT]"]
    if current_key:
        lines.append(f'current_location_key: {json.dumps(current_key)}')
    else:
        lines.append("current_location_key: null")
    lines.append("npcs_in_scene:")

    for row in rows:
        personality = ""
        topics = ""
        secret = ""
        try:
            p = json.loads(row["personality_json"] or "{}")
            if isinstance(p, dict):
                personality = str(p.get("personality") or "").strip()
                tv = p.get("topics")
                if isinstance(tv, list):
                    topics = ", ".join(str(x).strip() for x in tv if str(x).strip())
                secret = str(p.get("secret") or "").strip()
        except Exception:
            personality = ""
            topics = ""
            secret = ""

        line = (
            f'- {row["label"]} ({row["npc_type"]})'
            f' [key={row["key"]}]'
        )
        if row["description"]:
            line += f": {row['description']}"
        if personality:
            line += f" | personality: {personality}"
        if topics:
            line += f" | topics: {topics}"
        if secret:
            line += f" | secret: {secret}"
        lines.append(line)
    return "\n".join(lines)


def _inject_npc_llm_context(
    conn: sqlite3.Connection, campaign_id: int, messages: list[dict]
) -> None:
    """9A-3: inject dynamic [NPC CONTEXT] as a system message."""
    if not messages:
        return
    try:
        npc_block = build_npc_context_block(conn, campaign_id)
        if not npc_block:
            logger.info("npc_context_skipped", campaign_id=campaign_id, reason="no_npcs")
            return
        insert_at = 2 if len(messages) > 1 and messages[1].get("role") == "system" else 1
        messages.insert(insert_at, {"role": "system", "content": npc_block})
        visible_count = sum(1 for ln in npc_block.splitlines() if ln.startswith("- "))
        logger.info("npc_context_injected", campaign_id=campaign_id, npc_count=visible_count)
    except sqlite3.OperationalError as exc:
        # 9A-3 should fail-open before 9A-1 migrations are applied.
        logger.info("npc_context_skipped", campaign_id=campaign_id, reason="schema_missing", error=str(exc))
    except Exception as exc:
        logger.warning("npc_context_injection_failed", campaign_id=campaign_id, error=str(exc))


def _inject_known_npc_memory_context(
    conn: sqlite3.Connection, campaign_id: int, messages: list[dict]
) -> None:
    """D3 (#378) — inject campaign_known_npcs facts into LLM context before each turn."""
    if not messages:
        return
    try:
        from app.services.npc_memory_service import get_recent_known_npcs, format_known_npcs_block
        rows = get_recent_known_npcs(campaign_id, conn=conn)
        block = format_known_npcs_block(rows)
        if not block:
            return
        insert_at = min(3, len(messages))
        messages.insert(insert_at, {"role": "system", "content": block})
        logger.info("npc_memory_context_injected", campaign_id=campaign_id, count=len(rows))
    except sqlite3.OperationalError as exc:
        logger.info("npc_memory_context_skipped", campaign_id=campaign_id, reason="schema_missing", error=str(exc))
    except Exception as exc:
        logger.warning("npc_memory_context_injection_failed", campaign_id=campaign_id, error=str(exc))


def _inject_campaign_s11_context(
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    messages: list[dict],
    *,
    current_user_text: str | None = None,
) -> None:
    """
    Append MG plan + latest AI summary to system prompt so LLM keeps arc beyond last N turns.
    """
    if not messages:
        return
    first = messages[0]
    if not isinstance(first, dict) or first.get("role") != "system":
        return

    cid = int(campaign["id"])
    keys = campaign.keys()
    raw_plan = campaign["gm_plan_json"] if "gm_plan_json" in keys else None

    block_parts: list[str] = []
    formatted = format_gm_plan_block(raw_plan)
    if formatted:
        block_parts.append(formatted)

    try:
        from app.services.history_summary_service import fetch_latest_saved_summary_for_narrative

        saved = fetch_latest_saved_summary_for_narrative(conn, cid)
    except sqlite3.OperationalError:
        saved = None

    if saved and (saved.get("summary_text") or "").strip():
        st = str(saved["summary_text"]).strip()
        tc = saved.get("included_turn_count")
        block_parts.append(
            f"## Dotychczasowa fabuła (skrót archiwalny, ~{tc} tur narracyjnych)\n{st}"
        )

    try:
        from app.services.gm_plan_divergence import (
            divergence_prompt_block,
            evaluate_campaign_plan_divergence,
        )

        divergence = evaluate_campaign_plan_divergence(
            conn,
            campaign_id=cid,
            raw_plan=raw_plan,
            current_user_text=current_user_text,
            limit=4,
        )
        divergence_block = divergence_prompt_block(divergence)
        if divergence_block:
            block_parts.append(divergence_block)
    except sqlite3.OperationalError:
        pass

    if not block_parts:
        return

    bundle = (
        "--- Kontekst kampanii (trzymaj spójność z planem i skrótem; improwizuj w ramach zasad silnika) ---\n\n"
        + "\n\n".join(block_parts)
    )
    first["content"] = f"{first.get('content', '').rstrip()}\n\n{bundle}"


def build_narrative_messages(
    conn: sqlite3.Connection | None,
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    user_text: str,
    roll_result_message: str | None = None,
    roll_result_data: dict | None = None,
) -> list[dict]:
    from app.services import combat_service as combat_svc

    has_db_conn = isinstance(conn, sqlite3.Connection)
    recent_turns = loadrecentturns(conn, campaign["id"], limit=8)
    final_user_text = roll_result_message if roll_result_message else user_text
    combat_block = combat_svc.get_combat_context_for_prompt(int(campaign["id"]))
    messages = buildmessages(
        campaign=campaign,
        character=character,
        recentturns=recent_turns,
        usertext=final_user_text,
        runtime_config_block=build_runtime_config_block(),
        combat_context_block=combat_block,
    )

    # L13c (#689): when inside an active tile dungeon, suppress overworld context
    # and inject the dungeon room instead (set below, used to gate ŚWIAT/STALE too).
    _in_dungeon = False

    if has_db_conn:
        _inject_campaign_s11_context(conn, campaign, messages, current_user_text=user_text)

        try:
            _dng_row = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (int(campaign["id"]),),
            ).fetchone()
            _dng_flags = json.loads((_dng_row["session_flags"] if _dng_row else None) or "{}")
            _drun = _dng_flags.get("dungeon_run") or {}
            _in_dungeon = (
                _drun.get("system") == "tiles_v2"
                and not _drun.get("completed")
                and not _drun.get("failed")
            )
        except Exception:
            _in_dungeon = False
            _drun = {}

        if _in_dungeon:
            _inject_dungeon_loch_context(_drun, character, messages)
        else:
            _inject_location_llm_context(conn, int(campaign["id"]), messages)
            _inject_npc_llm_context(conn, int(campaign["id"]), messages)
            _inject_known_npc_memory_context(conn, int(campaign["id"]), messages)

        # U29 fix: inject === ŚWIAT === block (hex terrain + locations) into the
        # streaming/narrative path. Inserted as a SEPARATE system message just before
        # the final user message — appended to the 40k-char head system prompt it gets
        # buried and 8 turns of story continuity win over it.
        # L13c (#689): skipped inside a dungeon (overworld terrain is irrelevant there).
        if messages and not _in_dungeon:
            try:
                _sw_row = conn.execute(
                    "SELECT session_flags, current_location_id FROM game_sessions WHERE campaign_id = ? "
                    "ORDER BY created_at DESC, id DESC LIMIT 1",
                    (int(campaign["id"]),),
                ).fetchone()
                _sw_flags = json.loads((_sw_row["session_flags"] if _sw_row else None) or "{}")
                _cur_loc_id = _sw_row["current_location_id"] if _sw_row else None
                _imperative = build_swiat_imperative(conn, _cur_loc_id)
                from app.services.location_context_injector import build_swiat_block
                _swiat = build_swiat_block(conn, _sw_flags, user_text)
                if _swiat:
                    _swiat_msg = {
                        "role": "system",
                        "content": f"{_swiat}\n\n{_imperative}",
                    }
                    _ins_at = len(messages) - 1 if messages[-1].get("role") == "user" else len(messages)
                    messages.insert(_ins_at, _swiat_msg)
            except Exception as _sw_err:
                logger.warning("swiat_block_inject_failed", error=str(_sw_err))
        if character and messages:
            from app.services.inventory_context_service import build_inventory_block
            inv_block = build_inventory_block(conn, int(character["id"]))
            if inv_block:
                first = messages[0]
                if isinstance(first, dict) and first.get("role") == "system":
                    first["content"] = f"{first.get('content', '').rstrip()}\n\n{inv_block}"

        # C1: inject STORY_STALE when player hasn't moved for >= 5 consecutive turns
        # Escalates in intensity: mild suggestion (5-9), strong push (10-14), critical (15+)
        # L13c (#689): skipped inside a dungeon (no overworld travel to push toward).
        if messages and not _in_dungeon:
            try:
                _sf_row = conn.execute(
                    "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                    (int(campaign["id"]),),
                ).fetchone()
                if _sf_row and _sf_row["session_flags"]:
                    _sf = json.loads(_sf_row["session_flags"] or "{}")
                    _stale = int(_sf.get("turns_at_location", 0))
                    if _stale >= 5:
                        first = messages[0]
                        if isinstance(first, dict) and first.get("role") == "system":
                            if _stale >= 15:
                                _stale_msg = (
                                    f"[STORY_STALE: {_stale} tur bez ruchu — KRYTYCZNE! "
                                    "Bohater MUSI natychmiast opuścić tę lokację! "
                                    "Śmierć czai się w każdej sekundzie zwłoki. "
                                    "Uruchom działanie lub scenę ucieczki TERAZ.]"
                                )
                            elif _stale >= 10:
                                _stale_msg = (
                                    f"[STORY_STALE: {_stale} tur bez ruchu — "
                                    "Sytuacja staje się niebezpieczna i naglna! "
                                    "Bohater POWINIEN KONIECZNIE opuścić tę lokację w następnej turze.]"
                                )
                            else:
                                _stale_msg = (
                                    f"[STORY_STALE: {_stale} tur bez ruchu — "
                                    "zasugeruj bohaterowi opuszczenie lokacji]"
                                )
                            first["content"] = (
                                f"{first.get('content', '').rstrip()}\n\n{_stale_msg}"
                            )

                            # C1 follow-up: inject TRAVEL_HINT with nearby discovered locations
                            # Try session_flags first, fallback to querying DB for nearby locations
                            _discovered = _sf.get("discovered_hexes", [])
                            if not _discovered and _sf.get("current_hex"):
                                _ch = _sf.get("current_hex", {})
                                _cq, _cr = int(_ch.get("q", 0)), int(_ch.get("r", 0))
                                # Query nearby game_locations within hex distance 2
                                try:
                                    _nearby_rows = conn.execute(
                                        """
                                        SELECT name, world_hex_q as q, world_hex_r as r
                                        FROM game_locations
                                        WHERE approved = 1
                                        AND (world_hex_q IS NOT NULL AND world_hex_r IS NOT NULL)
                                        AND abs(world_hex_q - ?) <= 2 AND abs(world_hex_r - ?) <= 2
                                        AND NOT (world_hex_q = ? AND world_hex_r = ?)
                                        ORDER BY abs(world_hex_q - ?) + abs(world_hex_r - ?)
                                        LIMIT 5
                                        """,
                                        (_cq, _cr, _cq, _cr, _cq, _cr),
                                    ).fetchall()
                                    _discovered = [
                                        {"q": int(r["q"]), "r": int(r["r"]), "name": r["name"]}
                                        for r in _nearby_rows
                                    ]
                                except Exception:
                                    pass
                            _travel_hint = build_travel_hint_block(_discovered, _stale)
                            if _travel_hint and isinstance(first, dict):
                                first["content"] = (
                                    f"{first.get('content', '').rstrip()}\n\n{_travel_hint}"
                                )
            except Exception as _c1_err:
                logger.warning("story_stale_inject_failed", error=str(_c1_err))

    combat_log_block = combat_svc.get_combat_turns_context_for_prompt(int(campaign["id"]))
    if combat_log_block and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            first["content"] = f"{first.get('content', '').rstrip()}\n\n{combat_log_block}"

    death_append = _death_mechanica_system_append(character, roll_result_data)

    if (
        not combat_block
        and not roll_result_message
        and not death_append
        and messages
    ):
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            extra = _inactive_combat_tag_reminder(user_text)
            snap = combat_svc.load_combat_snapshot(int(campaign["id"]))
            if snap and str(snap.get("status") or "") == "ended":
                er = snap.get("ended_reason") or "ended"
                extra += (
                    "\n\n[STAN SILNIKA WALKI — POPRZEDNIA SESJA ZAKOŃCZONA]\n"
                    f"W bazie jest zapis zakończonej walki (powód: {er}). Gracz NIE ma teraz aktywnej walki "
                    "w mechanice — każda **nowa** potyczka wymaga na końcu Twojej odpowiedzi linii "
                    "[COMBAT_START:klucz_wroga] (wg słownika wrogów), chyba że gracz sam uruchomi walkę "
                    "komendą /atak w czacie (odczyt stanu walki).\n"
                    "Nie kontynuuj w myśleniu starej sesji (inicjatywa, HP z poprzedniej walki) — to osobna walka."
                )
            first["content"] = f"{first.get('content', '').rstrip()}\n\n{extra}"

    if has_db_conn and not combat_block and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            enemy_catalog = combat_svc.get_enemy_catalog_for_prompt(conn)
            if enemy_catalog:
                first["content"] = f"{first.get('content', '').rstrip()}\n\n{enemy_catalog}"

    # 8H-4: item catalog — także podczas aktywnej walki (Grant Item / nagrody z katalogu)
    if has_db_conn and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            item_catalog = combat_svc.get_item_catalog_for_prompt(conn)
            if item_catalog:
                first["content"] = f"{first.get('content', '').rstrip()}\n\n{item_catalog}"

    if death_append and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            first["content"] = f"{first.get('content', '').rstrip()}\n\n{death_append}"

    # Skill test tag instruction — injected when player text hints at skill use
    if not combat_block and not roll_result_message and has_db_conn and messages:
        _st_block = _skill_test_tag_instruction(conn, int(campaign["id"]), user_text)
        if _st_block:
            messages.append({"role": "system", "content": _st_block})

    # U6 (#530): inject rejected tags from previous turn so LLM doesn't continue non-existent thread
    if has_db_conn and messages:
        try:
            from app.services.llm_tag_parser import get_last_rejected_tags as _u6_glrt
            _u6_rejected = _u6_glrt(conn, int(campaign["id"]))
            if _u6_rejected:
                first = messages[0]
                if isinstance(first, dict) and first.get("role") == "system":
                    _u6_block = "[Odrzucone tagi z poprzedniej tury: " + ", ".join(_u6_rejected) + "]"
                    first["content"] = f"{first.get('content', '').rstrip()}\n\n{_u6_block}"
        except Exception:
            pass

    if not roll_result_data or not messages:
        return messages

    _rt = roll_result_data.get("roll_type") or infer_roll_type(
        str(roll_result_data.get("test") or "")
    )
    _atk = _rt == "attack"
    if roll_result_data.get("is_nat20") and _atk:
        roll_context = (
            "ROLL RESULT: CRITICAL SUCCESS (Natural 20). "
            "Narrate a dramatic, exceptional success. "
            "If combat: double damage dice."
        )
    elif roll_result_data.get("is_nat1") and _atk:
        roll_context = (
            "ROLL RESULT: CRITICAL FAILURE (Natural 1). "
            "Narrate a failure with an unexpected complication or twist. "
            "Do not just say the player failed — add a narrative consequence."
        )
    else:
        weapon_bonus = int(roll_result_data.get("weapon_bonus") or 0)
        bonus_part = ""
        if weapon_bonus:
            bonus_part = f" + weapon: {weapon_bonus}"
        roll_context = (
            "ROLL RESULT: "
            f"{roll_result_data.get('test')} check — rolled {roll_result_data.get('total')} "
            f"(d20: {roll_result_data.get('raw')} + stat: {roll_result_data.get('stat_mod')} + "
            f"skill: {roll_result_data.get('skill_rank')} + proficiency: {roll_result_data.get('proficiency')}"
            f"{bonus_part})"
        )

    if roll_result_data.get("test") == "death_save":
        total_ds = int(roll_result_data.get("total") or 0)
        if total_ds >= 10 or roll_result_data.get("is_nat20"):
            roll_context += (
                "\n\n[USTABILIZOWANIE] Postać ustabilizowała się. Stan śmierci zakończony (mechanicznie: "
                "death_save_failures = 0). Zakończ ten stan w narracji; nie dodawaj na końcu linii "
                "\"Roll Death Save d20\"."
            )

    first = messages[0]
    if isinstance(first, dict) and first.get("role") == "system":
        first["content"] = f"{first.get('content', '').rstrip()}\n\n{roll_context}"
    return messages


def run_narrative_turn(
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    user_text: str,
    model: str,
    ollama_base_url: str | None = None,
    llm_config: dict[str, str] | None = None,
    roll_result_message: str | None = None,
    roll_result_data: dict | None = None,
    extra_system: str | None = None,
) -> dict:
    messages = build_narrative_messages(
        conn=conn,
        campaign=campaign,
        character=character,
        user_text=user_text,
        roll_result_message=roll_result_message,
        roll_result_data=roll_result_data,
    )
    # U30 (#578): inject a mechanically-resolved fact (e.g. directional travel already
    # executed) into the system prompt so the narrator describes the fact, not invents one.
    if extra_system:
        first = messages[0] if messages else None
        if isinstance(first, dict) and first.get("role") == "system":
            first["content"] = f"{first.get('content', '').rstrip()}{extra_system}"
        else:
            messages.insert(0, {"role": "system", "content": extra_system.strip()})
    reply = generate_chat(messages=messages, model=model, llm_config=llm_config)
    return {"message": reply}
