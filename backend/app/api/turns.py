import json
import os
import random
import re
import sqlite3
import uuid

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.logging import bind_context, get_logger

try:
    from structlog.contextvars import get_contextvars as _structlog_get_contextvars
except Exception:  # pragma: no cover
    _structlog_get_contextvars = None

from app.core.turn_engine import COMBAT_ROLL_CTX_PREFIX
from app.services.opening_context import build_opening_plan_context
from app.services.dice import (
    ROLL_CARD_PREFIX,
    build_roll_card_payload,
    format_roll_for_llm,
    parse_character_sheet,
    parse_roll_command,
    roll_d20,
    resolve_dc_for_roll,
    resolve_roll,
    resolve_test_name,
)
from app.services.game_engine import build_narrative_messages, run_narrative_turn
from app.services.helpme_advisor_service import run_helpme_advisor
from app.services.llm_service import (
    generate_chat,
    generate_chat_stream,
    get_effective_config,
    get_health,
)
from app.api.slash_command_registry import COMMAND_REGISTRY
from app.services.client_ui_config import (
    get_public_help_command_texts,
    is_slash_command_enabled,
    slash_registry_key_for_dispatch,
)
from app.services.solo_death_service import apply_death_save_outcome, end_solo_campaign_on_death
from app.services.user_llm_settings import get_user_llm_settings_full
from app.services.location_config_service import get_bool_flag
from app.services.location_intent_parser import LocationIntent, parse as parse_location_intent
from app.services.location_validator import validate_move, log_integrity_violation
from app.services.turn.turn_commands import (
    HANDLED_COMMANDS as _TURN_HANDLED_COMMANDS,
    _export_session_to_file,
    handle as _handle_turn_command,
)
from app.services.turn.turn_skill_router import (
    _commit_pending_skill_test,
    route_skill_turn as _route_skill_turn,
)
from app.services.turn.turn_gate import check_gate_and_record as _check_gate_and_record
from app.services.turn.turn_intent import (
    detect_risky_intent as _detect_risky_intent_turn,
    snapshot_hex as _snapshot_hex,
    check_hex_enter_trigger as _check_hex_enter_trigger,
    apply_u7_safety_net as _apply_u7_safety_net,
)
from app.services.turn.turn_gambling import (
    apply_gamble_outcome_in_skill_resolution as _apply_gamble_in_skill,
    build_gamble_narrator_ctx as _build_gamble_narrator_ctx,
)
from app.services.turn.turn_tags import (
    is_combat_class_skill as _is_combat_class_skill,
    intercept_narrator_skill_tags as _intercept_narrator_skill_tags,
    persist_narrative_turn as _persist_narrative_turn,
)
from app.services.weapon_rules import is_attack_test, resolve_attack_roll_for_weapon, resolve_sheet_weapon
from app.services.world_service import process_create_tags, get_current_location_info
from app.services.suggested_actions import build_suggested_actions
from app.services.intent_parser import ParsedIntent

router = APIRouter()
DB_PATH = "/data/ai_gm.db"

# Skill keys that represent combat-class weapon modifiers / catch-all combat
# verbs / meta-combat mechanics rather than standalone skill checks. Their
# trigger_keywords are combat verbs ("atakuję", "uderzam"), weapon names
# ("miecz dwuręczny", "łucznik"), or combat-flow words ("inicjatywa",
# "refleks") — any of which would otherwise spawn a phantom skill test with
# hallucinated combat narration when no enemy is in the location. Combat
# intent must route through the intent parser → combat_start (or be a no-op
# in NARRATIVE state), never through skill_test.
# (Issue #20 + two_handed/initiative audit regression.)
# _COMBAT_CLASS_SKILLS and _is_combat_class_skill moved to turn_tags.py (R1.4)
logger = get_logger(__name__)


COMBAT_START_RE  = re.compile(r"\[COMBAT_START:([^\]]+)\]", re.IGNORECASE)
DUNGEON_CLEAR_RE = re.compile(r"\[DUNGEON_CLEAR:([^\]]+)\]", re.IGNORECASE)
# Stage 3 Z4 — [APPLY_CONDITION:condition_key:enemy_key]
APPLY_CONDITION_RE = re.compile(r"\[APPLY_CONDITION:\s*([^:\s\]]+)\s*:\s*([^\]\s][^\]]*?)\s*\]", re.IGNORECASE)
GRANT_ITEM_RE    = re.compile(r"^Grant Item\s+(.+)$", re.IGNORECASE)
GRANT_GOLD_RE = re.compile(r"^Grant Gold\s+([+-]?\d+)$", re.IGNORECASE)
OPEN_SHOP_RE = re.compile(r"^Open Shop\s+(\S+)$", re.IGNORECASE)


def _should_emit_open_shop_in_mode(npc_key: str | None, campaign_mode: str) -> bool:
    """Return True only when npc_key is set and campaign is NOT in dungeon mode (#742)."""
    return bool(npc_key) and str(campaign_mode or "solo").lower() != "dungeon"


# K2 fix helpers ──────────────────────────────────────────────────────────────
_PL_NORMALIZE = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")

# #567: generic placeholder enemies — never selected by narrative substring matching
# (a literal "Wróg"/"enemy" leaking into play reads as a bug to the player).
_GENERIC_ENEMY_KEYS = {"enemy", "unknown_attacker", "przeciwnik"}
_GENERIC_ENEMY_LABELS = {"wrog", "enemy", "przeciwnik", "napastnik"}


def _normalize_pl(text: str) -> str:
    return text.lower().translate(_PL_NORMALIZE)


def _kw_matches(kw: str, normalized_text: str) -> bool:
    """Match keyword allowing Polish verb conjugation stem variations (issue #237).

    Polish verbs conjugate with stem changes: "nasłuchuję" (I listen) vs "nasłuchując"
    (gerund: listening) have different stems after normalization.

    Solution: find word in text that shares a common prefix with kw of ≥5 chars.
    E.g., "nasluchuje" and "nasluchujac" both start with "nasluch" (7 chars).

    Regex: word-boundary-start + keyword_prefix(≥5) + optional extra chars + word-boundary-end
    """
    # Use at least 5 chars of the keyword to avoid false matches
    prefix_len = max(5, len(kw) - 2)  # Allow 1-2 char differences in stem endings
    prefix = kw[:prefix_len]

    return bool(re.search(
        r"(?<![a-zA-Z0-9_])" + re.escape(prefix) + r"[a-z]*(?![a-zA-Z0-9_])",
        normalized_text
    ))


def _text_is_action_attempt(text: str) -> bool:
    """
    False for messages that are clearly questions or passive descriptions.
    Prevents noun trigger-keywords from firing on ambient narrative text.
    """
    stripped = text.strip()
    # Questions are never action attempts in the pre-LLM scanner
    if stripped.endswith("?"):
        return False
    return True


_READING_PHRASES = (
    "na glos", "glosno", "co tam jest napisane", "co jest napisane",
    "tresc", "co tam pisze", "co pisze", "co tam mowi",
)
_READING_VERBS = (
    "czytam", "odczytuje", "czytaj", "spogladam na", "patrze na",
)
_READING_TARGETS = (
    "napis", "inskrypcj", "ksieg", "ksiazk", "zwoj", "pergamin",
    "list", "notatk", "mape", "tabliczk", "rune",
)


def _is_reading_context(text: str) -> bool:
    """Detect pure reading/examining actions so they bypass keyword-based skill routing.

    Why: reading should never trigger a roll (system prompt rule, issue #12 BUG-02).
    The pre-LLM keyword scanner matches words like ``odczytuje`` (arcana keyword) which
    is also a normal reading verb in Polish. Without this guard, "odczytuję napis na
    głos" wrongly fires an Arkana skill test before the LLM ever sees the request.
    """
    norm = _normalize_pl(text)
    if any(p in norm for p in _READING_PHRASES):
        return True
    has_verb = any(v in norm for v in _READING_VERBS)
    has_target = any(t in norm for t in _READING_TARGETS)
    return has_verb and has_target


# ── Compound action detector (issue #241) ───────────────────────────────────
# When a player sends multi-intent text (NPC dialogue + movement + skill check),
# the pre-LLM keyword scanner must be bypassed so the LLM handles all parts.
_COMPOUND_CONNECTORS = (
    " i ", " potem ", " nastepnie ", " po czym ",
    " a potem ", " a nastepnie ", " i ide ", " i wracam ",
    " i pytam ", " i mowie ", " i wychodze ",
)
_COMPOUND_DIALOGUE_MARKERS = (
    "mowie", "pytam", "powiedzi", "powiedzial",
    "krzycze", "odpowiadam", "zwracam sie", "mowię",
)


def _is_compound_action(text: str) -> bool:
    """Return True when text contains multiple distinct player intents.

    Compound = has a sequence connector (i/potem/po czym) AND a dialogue marker
    (mówię/pytam/powiedziałem). In that case the pre-LLM keyword scanner is
    bypassed so the LLM can narrate all parts of the turn, not just the
    first matched skill keyword.
    """
    norm = _normalize_pl(text or "")
    if not any(c in norm for c in _COMPOUND_CONNECTORS):
        return False
    return any(d in norm for d in _COMPOUND_DIALOGUE_MARKERS)


# ── Combat-keyword fallback (issue #135) ────────────────────────────────────
# When the player declares an attack in Polish and the LLM forgot to emit
# [COMBAT_START:enemy_key], inject the tag post-hoc so the combat engine
# actually starts. Pre-existing system prompt rule covered most cases but
# Polish narrative mode still slipped through ~5% of the time. Without this
# fallback the entire fight plays out as cinematic prose with zero HP / dice.
_COMBAT_INTENT_VERBS = (
    # atakować
    "atakuj", "atakuje", "zaatakuj", "zaatakuje",
    # uderzać / bić
    "uderzam", "uderzac", "uderz", "bij", "bije", "bije sie", "bijac",
    # walczyć
    "walcze", "walczy",
    # machać / zamachiwać (swing) — "machając młotem", "zamach mieczem"
    "macha", "machac", "macham", "machajac", "zamach", "wymach",
    # ciąć / kroić
    "tne", "tnac", "siekam", "siekan",
    # kłuć / pchnąć / dźgać / ugodzić
    "klue", "klu ", "pcham", "pchnij", "dzgam", "dzgac", "ugadzam", "ugodzam",
    # strzelać / miotać
    "strzelam", "strzelac", "miotam", "wypalac",
    # rzucać się / skakać na
    "rzucam sie na", "rzucam sie", "skacze na", "skacze",
    # nacierać / szarżować / ruszać na
    "naciera", "nacierac", "szarzuje", "szarze", "ruszam na", "ruszam sie na",
    # kopać / obalać
    "kopie", "kopnij", "obalam",
    # wyciągać broń / brać zamach
    "wyciagam bron", "biore zamach", "wyjmuje bron", "chwytam za bron",
    # cios / wymierzać / zadawać
    "cios", "zadaje cios", "wyprowadzam cios", "wymierzam", "wymierz",
    # zabijać / ranić
    "zabijam", "zabije", "ranie", "ranic",
    # inne
    "obalam", "przewracam", "powalem",
    # pchnąć nożem / inne bronie
    "pcham noz", "klu sztyletem",
)

# Weapon stems that signal combat context when combined with a motion verb.
_COMBAT_WEAPON_STEMS = (
    "mlot", "miecz", "sztylet", "szabl", "topor", "kord", "wloczni",
    "bron", "luk", "kusza", "kij", "maczug", "berlo", "rapier", "buz", "noz",
    "halabard", "morgenszt", "cep",
)
_COMBAT_MOTION_STEMS = (
    "macha", "uderz", "wymach", "wymierz", "zamach", "cios",
    "rzuc", "pchn", "dzgn", "kluj", "siekn", "walcz", "ataku",
    "nacier", "szarz", "rusz", "skacz",
)


# #535 — negation guard. "nie atakuję" / "nic nie atakuję" / "nie walczę"
# must NOT count as attack intent. Operates on normalised text (no PL diacritics,
# lowercase), so verb stems are diacritic-free. The negating "nie" must directly
# precede the attack verb (optionally via "chcę/będę/zamierzam" or "nikogo/nic"),
# so a real attack later in the sentence ("nie rozmawiam, atakuję") is preserved.
_NEGATION_ATTACK_RE = re.compile(
    r"\bnie\s+(?:chce\s+|bede\s+|zamierzam\s+|mam\s+zamiaru\s+)?"
    r"(?:nikogo\s+|nic\s+|niczego\s+)?"
    r"(atakuj|zaatakuj|uderz|strzel|walcz|bij|tne|tnac|kluj|dzga|szarz|nacier|rzuc|macha|kop|sieka)",
)


def _player_combat_intent(text: str) -> bool:
    """Detect explicit attack declaration in player text.

    Two paths:
    1. Direct verb match against _COMBAT_INTENT_VERBS.
    2. Weapon-context: player mentions a weapon item + a motion/action stem
       (catches "machając młotem", "wymachuję toporem", "uderzyłem berłem").

    #535: a negated attack verb ("nie atakuję", "nic nie atakuję") suppresses
    intent unless an un-negated attack verb also appears.
    """
    norm = _normalize_pl(text or "")
    if _NEGATION_ATTACK_RE.search(norm):
        # Remove the negated clause and re-test; if an un-negated attack verb
        # remains ("nie rozmawiam, atakuję"), intent still holds.
        stripped = _NEGATION_ATTACK_RE.sub(" ", norm)
        if not (any(v in stripped for v in _COMBAT_INTENT_VERBS)
                or (any(ws in stripped for ws in _COMBAT_WEAPON_STEMS)
                    and any(ms in stripped for ms in _COMBAT_MOTION_STEMS))):
            return False
    if any(v in norm for v in _COMBAT_INTENT_VERBS):
        return True
    has_weapon = any(ws in norm for ws in _COMBAT_WEAPON_STEMS)
    has_motion = any(ms in norm for ms in _COMBAT_MOTION_STEMS)
    return has_weapon and has_motion


# #773 — subdue/grapple intent (obezwładnienie poza walką). Mirror of the combat-intent
# detection but for NON-LETHAL takedowns ("obezwładniam", "przyciskam do ściany",
# "zakuwam w kajdany"). Per #773 comment: such an aggressive non-lethal declaration must
# route through the #780 advantage gate, NOT auto-fire [COMBAT_START] (casus Mizela #99791).
# Stems run on normalised text (no PL diacritics). Word-boundary-safe forms avoid fragment
# collisions: `zaku[cw]`/`sku[cw]` match "zakuć"/"skuwam" but NOT "zakup"/"skupiam" (#766).
_SUBDUE_INTENT_RE = re.compile(
    r"(obezwladn|schwyt|chwyt|chwyc|pochwyc|przypr|przypier|przycisk|przycisn"
    r"|unieruch|przytrzym|zaku[cw]|sku[cw]|powstrzym)"
)
_NEGATION_SUBDUE_RE = re.compile(
    r"\bnie\s+(?:chce\s+|bede\s+|zamierzam\s+|mam\s+zamiaru\s+)?"
    r"(?:go\s+|ja\s+|jej\s+|jego\s+|ich\s+|nikogo\s+|nic\s+|niczego\s+)?"
    r"(obezwladn|schwyt|chwyt|chwyc|pochwyc|przypr|przypier|przycisk|przycisn"
    r"|unieruch|przytrzym|zaku[cw]|sku[cw]|powstrzym)"
)


def _subdue_intent(text: str) -> bool:
    """Detect a non-lethal subdue/grapple declaration in player text.

    #535-style negation guard: a negated subdue verb ("nie chwytam", "nie obezwładniam")
    suppresses intent unless an un-negated subdue verb also remains.
    """
    norm = _normalize_pl(text or "")
    if not _SUBDUE_INTENT_RE.search(norm):
        return False
    if _NEGATION_SUBDUE_RE.search(norm):
        stripped = _NEGATION_SUBDUE_RE.sub(" ", norm)
        if not _SUBDUE_INTENT_RE.search(stripped):
            return False
    return True


def _resolve_enemy_key_from_context(
    conn: sqlite3.Connection,
    campaign_id: int,
    assistant_text: str,
) -> str:
    """Best-effort enemy_key resolution from the current GM response + last
    few turns. Falls back to `unknown_attacker` if nothing matches.

    Priority:
    1. active_encounter in session_flags — uses injected enemy_key directly
    2. game_config_enemies.label substring match in narrative
    """
    import json as _json
    # Priority 1: active_encounter enemy_key (injected encounter still in flags)
    try:
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if gs:
            flags = _json.loads(gs["session_flags"] or "{}")
            enc = flags.get("active_encounter")
            if enc and isinstance(enc, dict):
                enemies = enc.get("enemies") or []
                for e in enemies:
                    ek = str(e.get("enemy_key") or "").strip()
                    if ek:
                        return ek
    except Exception:
        pass

    haystack_parts: list[str] = [str(assistant_text or "")]
    try:
        rows = conn.execute(
            "SELECT assistant_text FROM campaign_turns WHERE campaign_id = ? ORDER BY id DESC LIMIT 3",
            (campaign_id,),
        ).fetchall()
        for r in rows:
            haystack_parts.append(str(r[0] or ""))
    except sqlite3.OperationalError:
        pass
    haystack = _normalize_pl(" ".join(haystack_parts))
    if not haystack.strip():
        return "unknown_attacker"
    try:
        enemy_rows = conn.execute(
            "SELECT key, label FROM game_config_enemies WHERE is_active = 1"
        ).fetchall()
    except sqlite3.OperationalError:
        return "unknown_attacker"
    best_key = None
    for er in enemy_rows:
        # #567: skip generic placeholder enemies. The seed enemy key='enemy'/label='Wróg'
        # would otherwise match the Polish word "wróg" ("enemy") in ANY combat narration
        # ("atakuję wroga"), spawning a literal enemy named "Wróg". Placeholders are not
        # content — fall through to 'unknown_attacker' (named "Napastnik" downstream).
        if str(er["key"] or "").strip().lower() in _GENERIC_ENEMY_KEYS:
            continue
        label = _normalize_pl(str(er["label"] or ""))
        key_norm = _normalize_pl(str(er["key"] or ""))
        if label in _GENERIC_ENEMY_LABELS:
            continue
        # Substring on the label OR direct mention of the key in narrative.
        if label and len(label) >= 4 and label in haystack:
            best_key = er["key"]
            break
        if key_norm and len(key_norm) >= 4 and key_norm in haystack:
            best_key = er["key"]
            break
    return best_key or "unknown_attacker"


def _ensure_combat_start_tag(
    conn: sqlite3.Connection,
    campaign_id: int,
    player_text: str,
    assistant_text: str,
) -> str:
    """If player declared combat intent and the GM response is missing both
    a [COMBAT_START:…] tag AND a `Roll Initiative d20` cue, append a tag so
    the combat engine fires. No-op when a tag/cue is already present or when
    a combat is already active.
    """
    # Trigger when the PLAYER declares an attack (#535: negation already filtered
    # by _player_combat_intent) OR when the GM narration itself initiates combat
    # against the player without emitting a tag (#520 reverse direction).
    player_intent = _player_combat_intent(player_text)
    narrative_combat = bool(_AGGRESSION_NARRATIVE_RE.search(_normalize_pl(assistant_text or "")))
    if not player_intent and not narrative_combat:
        return assistant_text
    if COMBAT_START_RE.search(assistant_text or ""):
        return assistant_text
    if re.search(r"Roll\s+Initiative\s+d20", assistant_text or "", re.IGNORECASE):
        return assistant_text
    try:
        active = conn.execute(
            "SELECT id FROM active_combat WHERE campaign_id = ? AND status = 'active' LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if active:
            return assistant_text
    except sqlite3.OperationalError:
        pass
    enemy_key = _resolve_enemy_key_from_context(conn, campaign_id, assistant_text)
    # #596/#535: never inject a tag for an enemy that is not actually present in the
    # scene/narration. Validation rejects stale/off-scene/friendly targets, so a
    # peaceful "nic nie atakuję" turn or an absent goblin can no longer spawn a fight.
    _valid, _reason = _validate_combat_start_target(conn, campaign_id, enemy_key, assistant_text)
    if not _valid:
        logger.info(
            "combat_start_tag_injection_skipped",
            campaign_id=campaign_id,
            enemy_key=enemy_key,
            reason=_reason,
            player_snippet=(player_text or "")[:80],
        )
        return assistant_text
    logger.info(
        "combat_start_tag_injected",
        campaign_id=campaign_id,
        enemy_key=enemy_key,
        trigger="player_intent" if player_intent else "narrative_combat",
        player_snippet=(player_text or "")[:80],
    )
    sep = "\n\n" if not (assistant_text or "").endswith("\n") else ""
    return f"{assistant_text or ''}{sep}[COMBAT_START:{enemy_key}]"


# 9A-4c+ — gdy model nie generuje cue, dołącz „Open Shop” na podstawie intencji gracza i NPC w scenie.
# #766: \b word boundaries prevent fragment matches (skUPiam→kup, s-CEN-a→cen, przyg-LAD-am→lad).
_TRADE_USER_INTENT_RE = re.compile(
    r"\b("
    r"kupuj|kupic|kupie|kup\b"
    r"|sprzedaj|sprzedac|sprzedaje|sprzeda"
    r"|handlu|handel"
    r"|sklep"
    r"|pokaz\b"
    r"|towar"
    r"|masz\s+do"
    r"|cena\b|cenie\b|ceny\b|cennik"
    r"|koszt"
    r"|zapla"
    r"|asorty|ofert|kram"
    r"|lada"
    r"|kupiec|kupca"
    r"|merch|targ"
    r")",
    re.IGNORECASE,
)
GM_ROLL_CARD_PREFIX = "__AI_GM_GM_ROLL_V1__"
# Short assistant line when combat victory follow-up skips the LLM (see create_turn_stream).
COMBAT_VICTORY_STREAM_STUB = "Walka dobiegła końca."


def _strip_json_code_fence(text: str) -> str:
    """Remove markdown ```json fences that some LLMs add around JSON."""
    value = (text or "").strip()
    value = re.sub(r"^```(?:json)?\s*\n?", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\n?```\s*$", "", value)
    return value.strip()


def _get_session_id_for_campaign(conn: sqlite3.Connection, campaign_id: int) -> int | str | None:
    row = conn.execute(
        """
        SELECT id FROM game_sessions
        WHERE campaign_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (campaign_id,),
    ).fetchone()
    if row:
        return row["id"]
    return None


def _inject_location_blocked(assistant_response: str, reason: str) -> str:
    # BUG-07: do not leak the technical reason tag into player-visible narrative.
    # Just null the location_intent so the bogus move isn't persisted; the block
    # is already logged server-side in `_process_location_intent` (location_move_blocked).
    data = json.loads(_strip_json_code_fence(assistant_response))
    data["location_intent"] = None
    return json.dumps(data, ensure_ascii=False)


def _inject_pre_llm_unknown_location_denial(
    conn: sqlite3.Connection,
    campaign_id: int,
    user_text: str,
    messages: list[dict],
) -> bool:
    """
    Tryb bez auto-create: jeśli ruch zostałby zablokowany jako nieznana lokalizacja,
    wstrzykuj instrukcję do system promptu PRZED LLM zamiast doklejać [LOCATION_BLOCKED]
    po wygenerowanej narracji.

    Returns:
        True gdy dodano blok [SYSTEM] i należy pominąć późniejszy post-processing
        `_process_location_intent` dla tej tury stream.
    """
    if not user_text.strip() or not messages:
        return False
    session_id = _get_session_id_for_campaign(conn, campaign_id)
    if session_id is None:
        return False
    if not get_bool_flag("location_integrity_enabled", session_id, default=True):
        return False
    # Tryb B: auto-create — zostawiamy dotychczasowy post-hook na odpowiedzi GM
    if get_bool_flag("location_auto_create_enabled", session_id, default=True):
        return False

    try:
        intent = parse_location_intent(user_text, session_id)
    except Exception as exc:
        logger.error("pre_llm_location_intent_parse_error", error=str(exc), campaign_id=campaign_id)
        return False

    if not intent or intent.action not in ("move", "create"):
        return False

    try:
        vr = validate_move(session_id, intent, campaign_id=campaign_id, auto_create_enabled=False)
    except Exception as exc:
        logger.error("pre_llm_location_validate_error", error=str(exc), campaign_id=campaign_id)
        return False

    if vr.allowed:
        return False

    reason = (vr.block_reason or "").lower()
    if "nieznana" not in reason:
        return False

    block = (
        f"\n[SYSTEM: Gracz próbuje przemieścić się do lokalizacji '{intent.target_label}', "
        "która nie istnieje w bazie lokalizacji. Odmów mu narracyjnie — "
        "opisz przeszkodę, mur, mgłę, strażnika lub inną fabularną blokadę. "
        "NIE opisuj dotarcia do celu.]"
    )
    first = messages[0]
    if isinstance(first, dict) and first.get("role") == "system":
        first["content"] = f"{first.get('content', '').rstrip()}{block}"
    else:
        messages.insert(0, {"role": "system", "content": block.strip()})
    logger.info(
        "pre_llm_unknown_location_injection",
        campaign_id=campaign_id,
        session_id=session_id,
        target_label=intent.target_label,
    )
    return True


def _process_location_intent(
    conn: sqlite3.Connection,
    campaign_id: int,
    assistant_response: str,
    *,
    skip_post_process: bool = False,
) -> str:
    """
    Parse GM location_intent, validate it, update current_location_id, and inject
    [LOCATION_BLOCKED] into JSON narrative when movement is rejected.
    """
    if skip_post_process:
        return assistant_response

    session_id = _get_session_id_for_campaign(conn, campaign_id)
    if not get_bool_flag("location_integrity_enabled", session_id, default=True):
        return assistant_response

    clean_response = _strip_json_code_fence(assistant_response)
    try:
        intent = parse_location_intent(clean_response, session_id)
    except Exception as exc:
        logger.error("location_intent_parse_hook_error", error=str(exc), campaign_id=campaign_id)
        return assistant_response

    if not intent or intent.action not in ("move", "create"):
        return assistant_response

    try:
        override_auto_create = intent.action == "create"
        result = validate_move(
            session_id,
            intent,
            campaign_id=campaign_id,
            auto_create_enabled=True if override_auto_create else None,
        )
        if result.allowed and result.resolved_location_id and session_id is not None:
            conn.execute(
                "UPDATE game_sessions SET current_location_id = ? WHERE id = ?",
                (result.resolved_location_id, session_id),
            )
            conn.execute(
                "UPDATE game_locations SET usage_count = usage_count + 1 WHERE id = ?",
                (result.resolved_location_id,),
            )
            # #825: clear scene_enemies/scene_npcs on any narrative location change.
            # Pre-spawn enemies (no hp) from a prior encounter must not follow the
            # player into the new location — hex-travel already did this; now narrative
            # movement (tavern room entry, etc.) does too.
            conn.execute(
                "UPDATE game_sessions SET scene_enemies = '[]', scene_npcs = '[]' WHERE campaign_id = ?",
                (campaign_id,),
            )
            # Also sync current_hex so the world map pin follows narrative movement
            try:
                import json as _jloc
                _loc_row = conn.execute(
                    "SELECT key FROM game_locations WHERE id = ?",
                    (result.resolved_location_id,),
                ).fetchone()
                if _loc_row and _loc_row["key"]:
                    _hex_row = conn.execute(
                        "SELECT q, r FROM world_hexes WHERE location_key = ? AND is_active = 1 LIMIT 1",
                        (_loc_row["key"],),
                    ).fetchone()
                    if _hex_row:
                        _gs_sf = conn.execute(
                            "SELECT id, session_flags FROM game_sessions WHERE id = ?",
                            (session_id,),
                        ).fetchone()
                        if _gs_sf:
                            _sf_loc = _jloc.loads(_gs_sf["session_flags"] or "{}")
                            _sf_loc["current_hex"] = {"q": int(_hex_row["q"]), "r": int(_hex_row["r"])}
                            conn.execute(
                                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                                (_jloc.dumps(_sf_loc, ensure_ascii=False), _gs_sf["id"]),
                            )
            except Exception as _hex_sync_err:
                logger.warning("hex_sync_on_location_move_failed", error=str(_hex_sync_err))
            # Link new gm_runtime location to the current world_hex so it appears on the admin map
            if result.is_new_location:
                try:
                    _loc_key_row = conn.execute(
                        "SELECT key FROM game_locations WHERE id = ? LIMIT 1",
                        (result.resolved_location_id,),
                    ).fetchone()
                    _gs_for_hex = conn.execute(
                        "SELECT session_flags FROM game_sessions WHERE id = ? LIMIT 1",
                        (session_id,),
                    ).fetchone()
                    if _loc_key_row and _gs_for_hex:
                        import json as _jnewloc
                        _sf_for_hex = _jnewloc.loads(_gs_for_hex["session_flags"] or "{}")
                        _cur_hex = _sf_for_hex.get("current_hex")
                        if _cur_hex and isinstance(_cur_hex, dict):
                            _nhq, _nhr = int(_cur_hex.get("q", 0)), int(_cur_hex.get("r", 0))
                            conn.execute(
                                """UPDATE world_hexes SET location_key = ?
                                   WHERE q = ? AND r = ? AND is_active = 1
                                   AND (location_key IS NULL OR location_key = '')""",
                                (_loc_key_row["key"], _nhq, _nhr),
                            )
                            # BUG-186: stamp hex coords onto game_locations so player hex map resolves
                            conn.execute(
                                "UPDATE game_locations SET world_hex_q = ?, world_hex_r = ? WHERE key = ? AND world_hex_q IS NULL",
                                (_nhq, _nhr, _loc_key_row["key"]),
                            )
                            # Also update hex_type from location biome if hex is still default 'plains'
                            try:
                                loc_biome = conn.execute(
                                    "SELECT biome FROM game_locations WHERE key = ?", (_loc_key_row["key"],)
                                ).fetchone()
                                biome = (loc_biome["biome"] if loc_biome else None) or ""
                                BIOME_TO_HEX_TYPE = {
                                    "forest": "forest",
                                    "swamp": "swamp",
                                    "mountain": "mountains",
                                    "mountains": "mountains",
                                    "urban": "town",
                                    "dungeon": "dungeon",
                                    "ruin": "ruins",
                                    "underground": "dungeon",
                                    "coast": "plains",
                                    "desert": "plains",
                                    "tundra": "plains",
                                    "rural": "plains",
                                    "plains": "plains",
                                }
                                mapped_type = BIOME_TO_HEX_TYPE.get(biome.lower())
                                if mapped_type and mapped_type != "plains":
                                    conn.execute(
                                        "UPDATE world_hexes SET hex_type = ? WHERE q = ? AND r = ? AND hex_type = 'plains'",
                                        (mapped_type, _nhq, _nhr),
                                    )
                            except Exception:
                                pass
                except Exception as _newloc_hex_err:
                    logger.warning("new_location_hex_link_failed", error=str(_newloc_hex_err))
            conn.commit()
            logger.info(
                "location_updated_from_gm_response",
                campaign_id=campaign_id,
                session_id=session_id,
                location_id=result.resolved_location_id,
                is_new=result.is_new_location,
            )
        elif not result.allowed:
            logger.warning(
                "location_move_blocked",
                campaign_id=campaign_id,
                session_id=session_id,
                attempted=intent.target_label,
                reason=result.block_reason,
            )
            try:
                return _inject_location_blocked(
                    clean_response,
                    result.block_reason or "Walidacja lokalizacji nie powiodła się",
                )
            except Exception:
                return assistant_response
    except Exception as exc:
        logger.error("location_integrity_processing_error", error=str(exc), campaign_id=campaign_id)

    return assistant_response


# #520 — GM narration that initiates combat against the player. Used to (a) inject
# a [COMBAT_START] tag when the LLM forgot it, and (b) treat a generic
# (unknown_attacker) target as "present" when the prose clearly shows an aggressor.
# Normalised text (lowercase, no PL diacritics).
_AGGRESSION_NARRATIVE_RE = re.compile(
    r"(rzuca(?:ja)?\s+sie\s+na\s+(?:ciebie|was)"
    r"|atakuj[ae]\s+(?:ci[ęe]|was|cie)"
    r"|naciera(?:ja)?\s+na\s+(?:ciebie|was)"
    r"|szarzuj[ae]\s+na\s+(?:ciebie|was)"
    r"|rusza(?:ja)?\s+na\s+(?:ciebie|was)"
    r"|skacze\s+na\s+(?:ciebie|was)"
    r"|ciska\s+sie\s+na\s+(?:ciebie|was)"
    r"|dobywa(?:ja)?\s+(?:broni|miecza|noza|sztyletu|topora)"
    r"|wyciaga(?:ja)?\s+(?:noz|miecz|sztylet|bron)"
    r"|siega(?:ja)?\s+po\s+(?:bron|noz|miecz|sztylet)"
    r"|unosi\s+bron"
    r"|wyprowadza\s+cios"
    r"|zamierza\s+sie\s+(?:na\s+(?:ciebie|was)|bronia)"
    r"|warczy\s+i\s+(?:rusza|naciera))",
)


def _enemy_present_in_narrative(narr_norm: str, label: str, key: str) -> bool:
    """True if the enemy's label or key is mentioned in the (normalised) narration."""
    label_n = _normalize_pl(label or "")
    key_n = _normalize_pl(key or "")
    if label_n and len(label_n) >= 4 and label_n not in _GENERIC_ENEMY_LABELS and label_n in narr_norm:
        return True
    if key_n and len(key_n) >= 4 and key_n not in _GENERIC_ENEMY_KEYS and key_n in narr_norm:
        return True
    return False


def _validate_combat_start_target(
    conn: sqlite3.Connection,
    campaign_id: int,
    enemy_key: str,
    assistant_text: str = "",
    source: str = "injected",
) -> tuple:
    """Unified combat-start target guard — #534 / #596 / #535 / #520.

    `source` controls strictness:
      - 'llm'      → the GM itself emitted [COMBAT_START]. The GM authored both the
                     tag and the narration, so a catalog enemy is trusted; only a
                     friendly/quest-giver NPC (#534) or an unknown target is rejected.
      - 'injected' → the backend is GUESSING from the player's words ("atakuję X").
                     The player can name any creature, so a bare name-mention in the
                     narration is unreliable (the GM may have *denied* it:
                     "w kuźni nie ma żadnego goblina"). The target must be genuinely
                     present: in scene_enemies, OR named in the narration alongside a
                     real aggression cue, OR a generic key backed by aggression.

    A target is valid only when it is genuinely PRESENT in the encounter:
      1. listed in scene_enemies (authoritative), OR
      2. (llm) a catalog enemy, OR (injected) a catalog enemy named in this turn's
         narration together with an aggression cue, OR
      3. a generic key (unknown_attacker) backed by aggressive narration.
    A bare catalog hit with no scene/narrative presence is REJECTED (#596) — this
    is what let a dead/absent wolf (#535) or an off-scene goblin (#596) start a fight.
    A friendly/quest-giver NPC is always rejected (#534).

    Returns (is_valid, rejection_reason).
    rejection_reason:
      '' | 'combat_target_friendly_npc' | 'combat_target_not_present'
         | 'combat_target_unknown'
    """
    import json as _vj
    key_lower = enemy_key.lower()
    narr_norm = _normalize_pl(assistant_text or "")

    # 1. scene_enemies — authoritative "these combatants are in the scene" → valid.
    try:
        se_row = conn.execute(
            "SELECT scene_enemies FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if se_row and se_row["scene_enemies"]:
            scene_enemies = _vj.loads(se_row["scene_enemies"] or "[]")
            for e in scene_enemies:
                if (e.get("key") or "").lower() == key_lower:
                    return (True, "")
                if (e.get("name") or "").lower() == key_lower:
                    return (True, "")
    except Exception:
        pass

    # 2. Friendly NPC (scene_npcs / campaign_known_npcs) → never a valid target (#534).
    try:
        sn_row = conn.execute(
            "SELECT scene_npcs FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if sn_row and sn_row["scene_npcs"]:
            scene_npcs = _vj.loads(sn_row["scene_npcs"] or "[]")
            for npc in scene_npcs:
                if (npc.get("key") or "").lower() == key_lower:
                    return (False, "combat_target_friendly_npc")
                if (npc.get("name") or npc.get("label") or "").lower() == key_lower:
                    return (False, "combat_target_friendly_npc")
    except Exception:
        pass
    try:
        npc_row = conn.execute(
            "SELECT id FROM campaign_known_npcs WHERE campaign_id = ? AND LOWER(npc_name) = ? LIMIT 1",
            (campaign_id, key_lower),
        ).fetchone()
        if npc_row:
            return (False, "combat_target_friendly_npc")
    except Exception:
        pass

    # LLM-authored tag: after the friendly-NPC gate, trust the GM completely.
    # initiate_combat() creates a pending_review row for keys not yet in catalog,
    # so any non-NPC key is safe to proceed with. The catalog-existence guard only
    # matters for the backend's own injected tags (source='injected').
    if source == "llm":
        return (True, "")

    has_aggression = bool(_AGGRESSION_NARRATIVE_RE.search(narr_norm))

    # 3. Generic injected key (unknown_attacker/enemy) → valid only if the prose
    #    actually shows an aggressor (#520), otherwise it is a phantom (#535).
    if key_lower in _GENERIC_ENEMY_KEYS:
        if has_aggression:
            return (True, "")
        return (False, "combat_target_not_present")

    # 4. Catalog enemy.
    try:
        er = conn.execute(
            "SELECT key, label FROM game_config_enemies WHERE LOWER(key) = ? LIMIT 1",
            (key_lower,),
        ).fetchone()
        if er:
            if source == "llm":
                # GM deliberately tagged this enemy — trust it (friendly NPCs already
                # filtered above). Covers legit GM ambushes.
                return (True, "")
            # Backend-injected (player-named): the GM may have *denied* the enemy
            # ("nie ma żadnego goblina") while still mentioning its name. Require the
            # name AND a genuine aggression cue so a denial can't spawn a phantom (#596).
            if _enemy_present_in_narrative(narr_norm, er["label"] or "", er["key"] or "") and has_aggression:
                return (True, "")
            return (False, "combat_target_not_present")
    except Exception:
        pass

    return (False, "combat_target_unknown")


def _maybe_start_combat_from_gm_tag(
    campaign_id: int, character_id: int, assistant_text: str,
    turn_log_id: "int | None" = None, turn_number: int = 0,
) -> "dict | None":
    """Parse [COMBAT_START:...] from GM text and initiate combat if allowed."""
    match = COMBAT_START_RE.search(assistant_text or "")
    if not match:
        logger.info("combat_gm_tag_absent", campaign_id=campaign_id)
        return None

    enemy_keys_raw = match.group(1)
    enemy_keys = [k.strip() for k in enemy_keys_raw.split(",") if k.strip()]

    if not enemy_keys:
        logger.warning("combat_gm_tag_empty", campaign_id=campaign_id)
        return None

    from app.services import combat_service as cs

    existing = cs.get_active_combat(campaign_id)
    if existing:
        logger.info("combat_gm_tag_skip_already_active", campaign_id=campaign_id)
        return None

    # HF-7 (#534): validate targets before initiating combat
    try:
        import json as _hfj
        with sqlite3.connect(DB_PATH) as _hfconn:
            _hfconn.row_factory = sqlite3.Row
            from app.services.llm_tag_parser import log_tag_error as _hf_lte
            for _ek in enemy_keys:
                _valid, _reason = _validate_combat_start_target(_hfconn, campaign_id, _ek, assistant_text, source="llm")
                if not _valid:
                    _hf_lte(_hfconn, campaign_id, turn_number, match.group(0), _reason)
                    logger.warning(
                        "combat_gm_tag_rejected_hf7",
                        campaign_id=campaign_id,
                        enemy_key=_ek,
                        reason=_reason,
                    )
                    # Append U6-style correction to stored turn narration
                    if turn_log_id:
                        from app.services.combat_service import combat_correction_message
                        _target_name = _ek.replace("_", " ").title()
                        # #780: uczciwy komunikat — nie kłamie o „nieosiągalności" celu
                        _corr = combat_correction_message(_reason, _target_name)
                        _turn_row = _hfconn.execute(
                            "SELECT assistant_text FROM campaign_turns WHERE id = ?",
                            (turn_log_id,),
                        ).fetchone()
                        if _turn_row:
                            _new_text = (_turn_row["assistant_text"] or "").rstrip() + "\n\n" + _corr
                            _hfconn.execute(
                                "UPDATE campaign_turns SET assistant_text = ? WHERE id = ?",
                                (_new_text, turn_log_id),
                            )
                            _hfconn.commit()
                    return None
    except Exception as _hf_err:
        logger.warning("combat_gm_tag_validation_error", error=str(_hf_err))

    try:
        combat_state = cs.initiate_combat(campaign_id, character_id, enemy_keys)
        logger.info(
            "combat_gm_tag_started",
            campaign_id=campaign_id,
            enemy_keys=enemy_keys,
            combat_id=combat_state.get("id"),
        )
        # Stage 3 Z4 — apply pending zaskoczony from pre-combat stealth success
        try:
            import json as _pjson
            with sqlite3.connect(DB_PATH) as _pconn:
                _pconn.row_factory = sqlite3.Row
                _gs = _pconn.execute(
                    "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                    (campaign_id,),
                ).fetchone()
                _sf = _pjson.loads(_gs["session_flags"] or "{}") if _gs else {}
                if _sf.get("pending_zaskoczony"):
                    for _ek in enemy_keys:
                        cs.apply_condition_to_combatant(campaign_id, _ek, "zaskoczony")
                    _sf.pop("pending_zaskoczony", None)
                    _pconn.execute(
                        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                        (_pjson.dumps(_sf, ensure_ascii=False), campaign_id),
                    )
                    _pconn.commit()
                    logger.info("combat_gm_tag_pending_zaskoczony_applied",
                                campaign_id=campaign_id, enemy_keys=enemy_keys)
        except Exception as _pz_err:
            logger.warning("combat_gm_tag_pending_zaskoczony_error", error=str(_pz_err))
        return combat_state
    except ValueError as e:
        logger.warning(
            "combat_gm_tag_rejected",
            campaign_id=campaign_id,
            error_message=str(e),
        )
        return None
    except Exception as e:
        logger.error("combat_gm_tag_error", campaign_id=campaign_id, error_message=str(e))
        return None


def _handle_dungeon_clear_tag(
    campaign_id: int, character_id: int, assistant_text: str
) -> dict | None:
    """Parse [DUNGEON_CLEAR:key] from GM text and record dungeon completion."""
    match = DUNGEON_CLEAR_RE.search(assistant_text or "")
    if not match:
        return None
    dungeon_key = match.group(1).strip()
    if not dungeon_key:
        return None
    try:
        from app.services.dungeon_service import complete_dungeon, check_cooldown
        cd = check_cooldown(character_id, dungeon_key)
        if cd.get("on_cooldown"):
            logger.info("dungeon_clear_tag_skip_cooldown", campaign_id=campaign_id, dungeon_key=dungeon_key)
            return None
        result = complete_dungeon(character_id, dungeon_key)
        logger.info("dungeon_clear_tag_recorded", campaign_id=campaign_id, dungeon_key=dungeon_key)
        return result
    except Exception as e:
        logger.error("dungeon_clear_tag_error", campaign_id=campaign_id, dungeon_key=dungeon_key, error=str(e))
        return None


def _truncate_for_story_log(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + "…[truncated]"


def _maybe_advance_combat_after_player_narrative(campaign_id: int) -> dict | None:
    """
    After the player's narrative message is resolved and GM text is saved, advance combat
    initiative when it was the player's turn (so the next actor can act).
    """
    logger.info("combat_advance_check", campaign_id=campaign_id)
    from app.services import combat_service as cs

    combat = cs.get_active_combat(campaign_id)
    if not combat or combat.get("status") != "active":
        logger.info(
            "combat_advance_skip",
            campaign_id=campaign_id,
            reason="no_active_or_not_active",
        )
        return None
    if str(combat.get("current_turn") or "") != "player":
        logger.info(
            "combat_advance_skip",
            campaign_id=campaign_id,
            reason="not_player_turn",
            current_turn=combat.get("current_turn"),
        )
        return None
    try:
        new_turn = cs.advance_turn(campaign_id)
    except ValueError:
        logger.warning("combat_advance_failed", campaign_id=campaign_id)
        return None
    logger.info(
        "combat_advance_ok",
        campaign_id=campaign_id,
        new_combat_turn=new_turn,
    )
    return {"combat_advanced": True, "new_combat_turn": new_turn}


def _maybe_handle_blocked_player_combat_turn(
    *,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    user_text: str,
    turn_id: str,
) -> dict | None:
    from app.services import combat_service as cs

    # #566: combat-roll follow-ups ([GM_ROLL] colour narration the combat UI posts after
    # an attack resolves) must NEVER be blocked as "narrative during combat" — they are
    # generated by the system, not typed by the player. Without this guard the
    # non-streaming /turns path returns "Walka trwa!" the moment the attack passes the
    # turn to the enemy. The streaming path already skips the block (current_turn=='player').
    if str(user_text or "").startswith(COMBAT_ROLL_CTX_PREFIX):
        return None

    combat = cs.get_active_combat(campaign_id)
    if not combat or str(combat.get("status") or "") != "active":
        return None
    # Block narrative during ALL active combat turns (player or enemy)


    turn_effects = cs.evaluate_current_turn_conditions(campaign_id)
    condition_blocked = bool(turn_effects.get("blocked"))
    # S18 (#613): kondycja sterująca turą gracza (confused/panicked behavior_override). Tura NIE jest
    # przejmowana w całości (UX) — pokazujemy banner z wynikiem k4/ucieczki; gracz wciąż gra przez UI walki.
    fb = turn_effects.get("forced_behavior")
    fb_banner = ""
    if isinstance(fb, dict) and str(fb.get("actor_id") or "") == "player":
        fb_banner = str(turn_effects.get("message") or "").strip()
    if not condition_blocked:
        # BUG-186: narrative must not process during active combat even when no condition blocks
        assistant_text = "Walka trwa! Użyj interfejsu walki, by wykonać akcję bojową."
        if fb_banner:
            assistant_text = f"{fb_banner}\n{assistant_text}"
    else:
        assistant_text = str(
            turn_effects.get("message") or "Warunek blokuje akcję bohatera w tej turze."
        ).strip()
        if not assistant_text:
            assistant_text = "Warunek blokuje akcję bohatera w tej turze."

    log = create_turn_log(
        conn=conn,
        campaign_id=campaign_id,
        character_id=character_id,
        user_text=user_text,
        assistant_text=assistant_text,
        route="narrative",
    )
    log_narrative_turn_structured(
        route="narrative",
        campaign_id=campaign_id,
        character_id=character_id,
        turn_row=log,
        user_text=user_text,
        assistant_text=assistant_text,
    )
    # Only advance when a real condition (stun/paralysis) blocks the player.
    # "Walka trwa!" is not a blocking condition — no turn consumed.
    combat_extra = _maybe_advance_combat_after_player_narrative(campaign_id) if condition_blocked else None

    out: dict[str, Any] = {
        "id": log["id"],
        "campaign_id": log["campaign_id"],
        "turn_number": log["turn_number"],
        "created_at": log["created_at"],
        "route": "narrative",
        "result": {"message": assistant_text},
        "turn_id": turn_id,
        "combat_state": cs.get_active_combat(campaign_id),
    }
    if combat_extra:
        out.update(combat_extra)
    return out


def _trace_ids_for_story_log() -> tuple[str, str]:
    if _structlog_get_contextvars is None:
        return "", ""
    try:
        ctx = _structlog_get_contextvars() or {}
        return str(ctx.get("turn_id") or ""), str(ctx.get("ui_trace_id") or "")
    except Exception:
        return "", ""


def log_narrative_turn_structured(
    *,
    route: str,
    campaign_id: int,
    character_id: int | None,
    turn_row: dict,
    user_text: str,
    assistant_text: str,
) -> None:
    """
    Emit one structured JSON log line for Loki/Grafana without syncing SQLite to
    the observability VM. Disable with NARRATIVE_STORY_LOG=0.

    Optional: NARRATIVE_LOG_MAX_CHARS caps user_text / assistant_text size (0 = no cap).
    """
    if route != "narrative":
        return
    if os.getenv("NARRATIVE_STORY_LOG", "1").strip().lower() in ("0", "false", "no"):
        return
    try:
        max_chars = int(os.getenv("NARRATIVE_LOG_MAX_CHARS", "0") or "0")
    except ValueError:
        max_chars = 0
    tid, ui_tid = _trace_ids_for_story_log()
    try:
        # Convert Row to dict if needed (some code paths pass sqlite3.Row)
        if not isinstance(turn_row, dict):
            turn_row = dict(turn_row) if hasattr(turn_row, 'keys') else {}

        logger.info(
            "narrative_turn",
            campaign_id=str(campaign_id),
            character_id="" if character_id is None else str(character_id),
            db_turn_id="" if turn_row.get("id") is None else str(turn_row.get("id")),
            turn_number="" if turn_row.get("turn_number") is None else str(turn_row.get("turn_number")),
            created_at=turn_row.get("created_at"),
            turn_id=tid,
            ui_trace_id=ui_tid,
            user_text=_truncate_for_story_log(user_text or "", max_chars),
            assistant_text=_truncate_for_story_log(assistant_text or "", max_chars),
        )
    except Exception:
        # Never fail a turn because logging broke
        pass


def log_memory_turn_structured(
    *,
    campaign_id: int,
    character_id: int | None,
    turn_row: dict,
    user_text: str,
    assistant_text: str,
) -> None:
    """Emit JSON log line for /mem turns (Loki: event=memory_turn). Same opt-out as narrative."""
    if os.getenv("NARRATIVE_STORY_LOG", "1").strip().lower() in ("0", "false", "no"):
        return
    try:
        max_chars = int(os.getenv("NARRATIVE_LOG_MAX_CHARS", "0") or "0")
    except ValueError:
        max_chars = 0
    tid, ui_tid = _trace_ids_for_story_log()
    try:
        # Convert Row to dict if needed
        if not isinstance(turn_row, dict):
            turn_row = dict(turn_row) if hasattr(turn_row, 'keys') else {}

        logger.info(
            "memory_turn",
            campaign_id=str(campaign_id),
            character_id="" if character_id is None else str(character_id),
            db_turn_id="" if turn_row.get("id") is None else str(turn_row.get("id")),
            turn_number="" if turn_row.get("turn_number") is None else str(turn_row.get("turn_number")),
            created_at=turn_row.get("created_at"),
            turn_id=tid,
            ui_trace_id=ui_tid,
            user_text=_truncate_for_story_log(user_text or "", max_chars),
            assistant_text=_truncate_for_story_log(assistant_text or "", max_chars),
        )
    except Exception:
        pass


class TurnCreate(BaseModel):
    character_id: int
    text: str
    system: str | None = None
    engine: str | None = None
    game_id: int | None = None
    input_type: str = "free_text"   # "free_text" | "structured"
    skip_narrative: bool = False     # player toggle: skip LLM narration for combat rolls


class SearchPayload(BaseModel):
    character_id: int
    target: str | None = None
    context: dict | None = None


def _start_turn_trace(campaign_id: int, character_id: int | None, route: str) -> str:
    turn_id = str(uuid.uuid4())
    context: dict[str, str] = {
        "turn_id": turn_id,
        "campaign_id": str(campaign_id),
        "turn_route": route,
    }
    if character_id is not None:
        context["character_id"] = str(character_id)
    bind_context(**context)
    return turn_id


def _with_turn_trace(payload: dict, turn_id: str) -> dict:
    return {**payload, "turn_id": turn_id}


def _record_turn_decision_safe(
    campaign_id, character_id, user_text, *, route, gate_blocked, gate_reason,
    handler, conn=None,
):
    """#762: zapis decyzji silnika (intent keyword-only — bez LLM, bez kosztu). Best-effort."""
    try:
        from app.services.decision_log_service import record_turn_decision
        # #762: intent_service.parse_intent — keyword-only (zero kosztu LLM), ale daje
        # znormalizowany action_type + confidence (0.8 keyword / 0.4 fallback) + target.
        action_type = None
        confidence = None
        target = None
        try:
            from app.services.intent_service import parse_intent
            _pi = parse_intent(user_text, campaign_id)
            action_type = _pi.action_type
            confidence = _pi.confidence
            target = _pi.target
        except Exception:
            from app.services.gate_service import classify_intent_stub
            action_type = (classify_intent_stub(user_text) or {}).get("action_type")
        tn = None
        if conn is not None:
            try:
                tn = conn.execute(
                    "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
                    (campaign_id,),
                ).fetchone()[0]
            except Exception:
                tn = None
        record_turn_decision(
            campaign_id=campaign_id, character_id=character_id, turn_number=tn,
            user_text=user_text, action_type=action_type, confidence=confidence, route=route,
            gate_blocked=gate_blocked, gate_reason=gate_reason, handler=handler,
            raw_intent=action_type, meta={"target": target} if target else None,
        )
    except Exception:
        pass


def _structured_action_to_tag(action_str: str) -> str:
    """
    T33: Convert a structured button-click payload into an [ACTION:...] tag
    that the intent parser / turn pipeline already understands.

    Examples:
      "MOVEMENT:forest_clearing" → "[ACTION:MOVEMENT:target=forest_clearing]"
      "DIALOGUE:innkeeper_boris" → "[ACTION:DIALOGUE:target=innkeeper_boris]"
      "REST:long"               → "[ACTION:REST:type=long]"
      "SEARCH"                  → "[ACTION:SEARCH]"
      "ATTACK"                  → "[ACTION:ATTACK]"
      "FLEE"                    → "[ACTION:FLEE]"
      "ITEM_USE"                → "[ACTION:ITEM_USE]"
    Unknown payloads are returned unchanged (fall through to normal parse).
    """
    s = (action_str or "").strip()
    if ":" in s:
        head, _, tail = s.partition(":")
        head = head.upper()
        tail = tail.strip()
        if head == "MOVEMENT":
            return f"[ACTION:MOVEMENT:destination_key={tail}]"
        if head == "DIALOGUE":
            return f"[ACTION:DIALOGUE:npc_key={tail}]"
        if head == "REST":
            return f"[ACTION:REST:rest_type={tail}]"
        if head == "EXAMINE":
            return f"[ACTION:EXAMINE:target={tail}]"
        # Generic fallback with param
        return f"[ACTION:{head}:target={tail}]"
    # No-param actions
    upper = s.upper()
    if upper in ("SEARCH", "ATTACK", "FLEE", "ITEM_USE", "ITEM_PICKUP"):
        return f"[ACTION:{upper}]"
    # Unknown — return as-is
    return s


def _safe_int(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _player_ac_from_sheet_fallback(sheet: dict) -> int:
    if not isinstance(sheet, dict):
        return 12
    defense = sheet.get("defense")
    if isinstance(defense, dict):
        for key in ("base", "ac", "total", "value"):
            if defense.get(key) is not None:
                return _safe_int(defense.get(key), 12)
    for key in ("ac", "armor_class", "player_ac"):
        if sheet.get(key) is not None:
            return _safe_int(sheet.get(key), 12)
    if isinstance(defense, (int, float, str)):
        return _safe_int(defense, 12)
    return 12


def _resolve_player_ac(campaign_id: int) -> int:
    from app.services import combat_service as cs

    combat = cs.get_active_combat(campaign_id) or cs.load_combat_snapshot(campaign_id)
    if isinstance(combat, dict):
        for combatant in combat.get("combatants") or []:
            if isinstance(combatant, dict) and str(combatant.get("type") or "") == "player":
                defense = combatant.get("defense")
                if defense is not None:
                    return _safe_int(defense, 12)

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE campaign_id = ? ORDER BY id ASC LIMIT 1",
            (campaign_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return 12
    return _player_ac_from_sheet_fallback(parse_character_sheet(row["sheet_json"]))


def _find_enemy_for_gm_roll(campaign_id: int, payload: dict) -> dict | None:
    from app.services import combat_service as cs

    target_name = str(payload.get("target_name") or payload.get("enemy_name") or "").strip()
    enemy_key = str(payload.get("enemy_key") or "").strip()
    target_id = str(payload.get("target_id") or "").strip()
    combat = cs.get_active_combat(campaign_id) or cs.load_combat_snapshot(campaign_id)
    combatants = combat.get("combatants") if isinstance(combat, dict) else []

    enemies = [c for c in combatants or [] if isinstance(c, dict) and c.get("type") == "enemy"]

    def _hp_ok(e: dict) -> bool:
        return _safe_int(e.get("hp_current"), 0) > 0

    def _first_in_turn_order(pool: list[dict]) -> dict | None:
        if not pool:
            return None
        if len(pool) == 1:
            return pool[0]
        turn_order = combat.get("turn_order") if isinstance(combat, dict) else []
        pool_ids = {str(e.get("id") or "") for e in pool}
        for turn_id in turn_order or []:
            tid = str(turn_id)
            if tid in pool_ids:
                for e in pool:
                    if str(e.get("id") or "") == tid:
                        return e
        return pool[0]

    if enemies:
        if target_id:
            for enemy in enemies:
                if str(enemy.get("id") or "") == target_id:
                    return enemy

        if enemy_key:
            keyed = [e for e in enemies if str(e.get("enemy_key") or "").strip() == enemy_key]
            living_keyed = [e for e in keyed if _hp_ok(e)]
            pool = living_keyed if living_keyed else keyed
            picked = _first_in_turn_order(pool)
            if picked is not None:
                return picked

        if target_name:
            target_name_l = target_name.lower()
            named = [
                e
                for e in enemies
                if str(e.get("name") or "").strip().lower() == target_name_l
            ]
            living_named = [e for e in named if _hp_ok(e)]
            pool_n = living_named if living_named else named
            picked_n = _first_in_turn_order(pool_n)
            if picked_n is not None:
                return picked_n

        turn_order = combat.get("turn_order") if isinstance(combat, dict) else []
        for turn_id in turn_order or []:
            for enemy in enemies:
                if str(enemy.get("id") or "") == str(turn_id) and _hp_ok(enemy):
                    return enemy
        for enemy in enemies:
            if _hp_ok(enemy):
                return enemy
        return enemies[0]

    if not target_name and not enemy_key:
        return None
    return {
        "name": target_name or "Wróg",
        "enemy_key": enemy_key,
        "attack_bonus": 2,
        "dex_modifier": 0,
    }


def _resolve_gm_roll(enemy: dict) -> dict:
    raw = random.randint(1, 20)
    modifier = _safe_int(enemy.get("attack_bonus"), 2)
    total = raw + modifier
    player_ac = _safe_int(enemy.get("_player_ac", enemy.get("player_ac")), 12)

    if raw == 20:
        verdict = "crit"
    elif raw == 1:
        verdict = "fumble"
    elif total >= player_ac:
        verdict = "hit"
    else:
        verdict = "miss"

    enemy_name = str(enemy.get("name") or enemy.get("enemy_key") or "Wróg").strip() or "Wróg"
    return {
        "skill": f"Atak — {enemy_name}",
        "dice": "1d20",
        "raw": raw,
        "modifier": modifier,
        "total": total,
        "verdict": verdict,
    }


def _resolve_gm_dodge_roll(enemy: dict, player_hit_roll: int, player_raw_d20: int | None = None) -> dict:
    from app.services.combat_service import compute_player_attack_dodge_outcome

    raw = random.randint(1, 20)
    dex_mod = _safe_int(enemy.get("dex_modifier"), 0)
    dodged, _hit, total = compute_player_attack_dodge_outcome(
        _safe_int(player_hit_roll, 0),
        raw,
        dex_mod,
        player_raw_d20,
    )
    auto_hit = player_raw_d20 == 20

    if auto_hit:
        verdict = "hit"
    elif raw == 20:
        verdict = "perfect_dodge"
    elif raw == 1:
        verdict = "fumble_dodge"
    elif dodged:
        verdict = "dodged"
    else:
        verdict = "hit"

    enemy_name = str(enemy.get("name") or enemy.get("enemy_key") or "Przeciwnik").strip() or "Przeciwnik"
    return {
        "skill": f"Unik — {enemy_name}",
        "dice": "d20",
        "raw": raw,
        "modifier": dex_mod,
        "total": total,
        "verdict": verdict,
        "dodged": dodged,
        "player_roll": player_hit_roll,
    }


def _stream_combat_roll_extras(campaign_id: int, user_text_val: str) -> tuple[dict | None, dict | None]:
    """
    For combat follow-up turns (COMBAT_ROLL prefix): optional GM attack roll bubble payload
    and optional combat-ended hint for the client (victory after last kill).
    """
    s = (user_text_val or "").strip()
    if not s.startswith(COMBAT_ROLL_CTX_PREFIX):
        return None, None
    tail = s[len(COMBAT_ROLL_CTX_PREFIX) :].lstrip("\r\n \t")
    try:
        payload = json.loads(tail)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, None
    # player_flee (and other kinds): no [GM_ROLL] / [COMBAT_ENDED] — flee ends via /combat/flee
    if not isinstance(payload, dict) or payload.get("kind") != "player_attack":
        return None, None
    gm_roll: dict | None = None
    enemy = _find_enemy_for_gm_roll(campaign_id, payload)
    if enemy:
        player_hit_roll = _safe_int(payload.get("total", payload.get("roll_result")), 0)
        pr = payload.get("d20", payload.get("raw_d20"))
        player_raw_d20: int | None
        if pr in (None, ""):
            player_raw_d20 = None
        else:
            player_raw_d20 = _safe_int(pr, 0)
            if player_raw_d20 == 0:
                player_raw_d20 = None
        if player_raw_d20 != 1 and player_hit_roll > 0:
            gm_roll = _resolve_gm_dodge_roll(dict(enemy), player_hit_roll, player_raw_d20)
    combat_ended: dict | None = None
    if payload.get("combat_victory"):
        name = (
            (payload.get("target_name") or payload.get("enemy_name") or "Wróg").strip() or "Wróg"
        )
        if enemy:
            name = str(enemy.get("name") or enemy.get("enemy_key") or name).strip() or name
        combat_ended = {"reason": "enemy_killed", "enemy_name": name}
    logger.info(
        "combat_roll_extras_result",
        campaign_id=campaign_id,
        gm_roll="present" if gm_roll else "absent",
        combat_ended="present" if combat_ended else "absent",
    )
    return gm_roll, combat_ended


def _build_combat_narrative_stub(user_text_val: str) -> str:
    """Mechanical summary when LLM narration is skipped for a combat roll."""
    s = (user_text_val or "").strip()
    if s.startswith(COMBAT_ROLL_CTX_PREFIX):
        tail = s[len(COMBAT_ROLL_CTX_PREFIX):].lstrip("\r\n \t")
        try:
            pl = json.loads(tail)
            if isinstance(pl, dict) and pl.get("kind") == "player_attack":
                hit = pl.get("hit")
                damage = int(pl.get("damage") or 0)
                target = (pl.get("target_name") or "wróg").strip()
                nat20 = int(pl.get("d20") or 0) == 20
                nat1 = int(pl.get("d20") or 0) == 1
                if nat1:
                    return "Krytyczna porażka!"
                if hit and nat20:
                    return f"Trafienie krytyczne! {damage} obrażeń — {target} pada."
                if hit:
                    return f"Cios trafia — {damage} obrażeń ({target})."
                return "Pudło."
        except Exception:
            pass
    return "Akcja rozliczona."


_SKIP_COMBAT_NARRATIVE_META_KEY = "skip_combat_narrative_global"


def _get_skip_combat_narrative_global() -> bool:
    try:
        from app.db.database import get_db as _gdb
        c = _gdb()
        try:
            row = c.execute(
                "SELECT value FROM game_config_meta WHERE key = ?",
                (_SKIP_COMBAT_NARRATIVE_META_KEY,),
            ).fetchone()
            return str((row[0] if row else "") or "").strip().lower() in ("1", "true", "yes")
        finally:
            c.close()
    except Exception:
        return False


def _parse_post_loot_summary_payload(user_text_val: str) -> dict | None:
    s = (user_text_val or "").strip()
    if not s.startswith(COMBAT_ROLL_CTX_PREFIX):
        return None
    tail = s[len(COMBAT_ROLL_CTX_PREFIX) :].lstrip("\r\n \t")
    try:
        payload = json.loads(tail)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("kind") != "post_loot_summary":
        return None
    return payload


def _render_post_loot_summary_text(payload: dict) -> str:
    items_raw = payload.get("claimed_items")
    items = items_raw if isinstance(items_raw, list) else []
    normalized: list[str] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or "").strip()
        if not label:
            continue
        qty = _safe_int(raw.get("quantity"), 1)
        qty = qty if qty > 0 else 1
        if qty > 1:
            normalized.append(f"{label} ×{qty}")
        else:
            normalized.append(label)
    gold_gp = _safe_int(payload.get("gold_gp"), 0)
    if gold_gp < 0:
        gold_gp = 0

    if normalized and gold_gp > 0:
        return (
            "Przeglądasz pobojowisko i zabezpieczasz zdobycz: "
            + ", ".join(normalized)
            + f" oraz {gold_gp} GP. "
            "Po chwili ciszy rozglądasz się po okolicy, gotów na kolejny ruch."
        )
    if normalized:
        return (
            "Przeglądasz pobojowisko i zabezpieczasz zdobycz: "
            + ", ".join(normalized)
            + ". Po chwili ciszy rozglądasz się po okolicy, gotów na kolejny ruch."
        )
    if gold_gp > 0:
        return (
            f"Przeglądasz pobojowisko i zbierasz {gold_gp} GP. "
            "Po chwili ciszy rozglądasz się po okolicy, gotów na kolejny ruch."
        )
    return "Po walce rozglądasz się po okolicy."


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _atak_command_response_for_api(campaign_id: int) -> dict:
    """Wynik /atak i /walka w API — zależny od włączenia /atak w konfiguracji slash (admin)."""
    if not is_slash_command_enabled("/atak"):
        return {
            "route": "command",
            "command": "atak",
            "combat_active": False,
            "combat_state": None,
            "feature_disabled": True,
            "message": "Komenda /atak jest wyłączona przez administratora.",
        }
    return _atak_command_result(campaign_id)


def _atak_command_result(campaign_id: int) -> dict:
    """Stan aktywnej walki dla /atak (oraz aliasu /walka) — bez LLM, bez zmian w DB walki."""
    from app.services import combat_service as cs

    combat = cs.get_active_combat(campaign_id)
    if combat:
        return {
            "route": "command",
            "command": "atak",
            "combat_active": True,
            "combat_state": combat,
        }
    return {
        "route": "command",
        "command": "atak",
        "combat_active": False,
        "combat_state": None,
        "message": "Nie trwa żadna walka.",
    }


def validate_roll_cue_name(assistant_text: str) -> str | None:
    lines = (assistant_text or "").splitlines()
    if not lines:
        return None
    last_line = (lines[-1] or "").strip()
    cue_match = re.match(r"^Roll (.+?) (d\d+)$", last_line, re.I)
    if not cue_match:
        return None
    raw_test_name = (cue_match.group(1) or "").strip()
    canonical = resolve_test_name(raw_test_name)
    if canonical is None:
        logger.warning("unknown_llm_roll_cue_ignored", raw_test_name=raw_test_name)
    return canonical


def parse_grant_item_cue(assistant_text: str) -> str | None:
    lines = (assistant_text or "").splitlines()
    if not lines:
        return None
    last_line = (lines[-1] or "").strip()
    cue_match = GRANT_ITEM_RE.match(last_line)
    if not cue_match:
        return None
    label = (cue_match.group(1) or "").strip()
    return label or None


def strip_last_grant_item_cue(assistant_text: str) -> str:
    lines = (assistant_text or "").splitlines()
    if not lines:
        return assistant_text or ""
    if not GRANT_ITEM_RE.match((lines[-1] or "").strip()):
        return assistant_text or ""
    return "\n".join(lines[:-1]).rstrip()


def parse_grant_gold_cue(assistant_text: str) -> int | None:
    lines = (assistant_text or "").splitlines()
    if not lines:
        return None
    last_line = (lines[-1] or "").strip()
    cue_match = GRANT_GOLD_RE.match(last_line)
    if not cue_match:
        return None
    amount_raw = (cue_match.group(1) or "").strip()
    try:
        amount = int(amount_raw)
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def strip_last_grant_gold_cue(assistant_text: str) -> str:
    lines = (assistant_text or "").splitlines()
    if not lines:
        return assistant_text or ""
    if not GRANT_GOLD_RE.match((lines[-1] or "").strip()):
        return assistant_text or ""
    return "\n".join(lines[:-1]).rstrip()


def parse_open_shop_cue(assistant_text: str) -> str | None:
    lines = (assistant_text or "").splitlines()
    if not lines:
        return None
    last_line = (lines[-1] or "").strip()
    cue_match = OPEN_SHOP_RE.match(last_line)
    if not cue_match:
        return None
    npc_key = str(cue_match.group(1) or "").strip()
    return npc_key or None


def strip_last_open_shop_cue(assistant_text: str) -> str:
    lines = (assistant_text or "").splitlines()
    if not lines:
        return assistant_text or ""
    if not OPEN_SHOP_RE.match((lines[-1] or "").strip()):
        return assistant_text or ""
    return "\n".join(lines[:-1]).rstrip()


def _extract_narrative_for_cues(text: str) -> tuple[str, dict | None]:
    """
    If text is JSON containing `narrative`, return (narrative, parsed_dict).
    Otherwise return (text, None) as plain-text fallback.

    The SSE streaming path encodes newlines as \\n then decodes them back to
    literal newline characters before this function is called. Literal newlines
    inside JSON string values are technically invalid per spec, so json.loads
    rejects them. We use strict=False to allow literal control characters inside
    strings so that grant_item and other top-level fields are extracted correctly.
    """
    _decoder = json.JSONDecoder(strict=False)
    stripped = _strip_json_code_fence(text)
    try:
        parsed = _decoder.decode(stripped)
        if isinstance(parsed, dict) and "narrative" in parsed:
            return str(parsed.get("narrative") or ""), parsed
    except (ValueError, TypeError):
        pass
    return text, None


def _repack_narrative(_original_text: str, narrative: str, parsed: dict | None) -> str:
    """
    Put cleaned narrative back into JSON if input was JSON; otherwise return narrative.
    """
    if parsed is None:
        return narrative
    try:
        parsed["narrative"] = narrative
        return json.dumps(parsed, ensure_ascii=False)
    except Exception:
        return narrative


def _current_location_key(conn: sqlite3.Connection, campaign_id: int) -> str | None:
    sid = _get_session_id_for_campaign(conn, campaign_id)
    if sid is None:
        return None
    row = conn.execute(
        """
        SELECT gl.key
        FROM game_sessions gs
        LEFT JOIN game_locations gl ON gl.id = gs.current_location_id
        WHERE gs.id = ?
        """,
        (sid,),
    ).fetchone()
    if row and row["key"]:
        return str(row["key"])
    return None


def _shop_npc_keys_in_scene(conn: sqlite3.Connection, current_key: str | None) -> list[str]:
    """Active NPCs with is_shop=1 at current location (+ globals), same filter as [NPC CONTEXT]."""
    if current_key:
        rows = conn.execute(
            """
            SELECT n.key
            FROM npcs n
            WHERE COALESCE(n.is_active, 1) = 1
              AND COALESCE(n.is_shop, 0) = 1
              AND (
                EXISTS (
                    SELECT 1 FROM npc_locations nl
                    WHERE nl.npc_id = n.id AND nl.location_key = ?
                )
                OR NOT EXISTS (
                    SELECT 1 FROM npc_locations nl2 WHERE nl2.npc_id = n.id
                )
              )
            ORDER BY n.key COLLATE NOCASE
            """,
            (current_key,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT n.key
            FROM npcs n
            WHERE COALESCE(n.is_active, 1) = 1
              AND COALESCE(n.is_shop, 0) = 1
              AND NOT EXISTS (
                  SELECT 1 FROM npc_locations nl WHERE nl.npc_id = n.id
              )
            ORDER BY n.key COLLATE NOCASE
            """
        ).fetchall()
    return [str(r["key"]) for r in rows]


def _pick_shop_npc_key(narrative: str, keys: list[str]) -> str | None:
    if not keys:
        return None
    nlow = (narrative or "").lower()
    for key in keys:
        short = key.split("_")[-1]
        if short and short in nlow:
            return key
    for key in keys:
        if key.replace("_", "") in nlow.replace("_", ""):
            return key
    return None  # #766: no blanket fallback — only open shop when narrative names a known NPC


def maybe_append_open_shop_fallback(
    conn: sqlite3.Connection,
    campaign_id: int,
    user_text: str,
    assistant_after_combat_strip: str,
) -> str:
    """
    If the model omits `Open Shop`, but the player's line is a trade intent and a shop NPC
    is in scene, append `Open Shop <npc_key>` as the last line of `narrative` (JSON or plain).
    """
    raw = (assistant_after_combat_strip or "").strip()
    ut = (user_text or "").strip()
    if not raw or not ut:
        return assistant_after_combat_strip
    if not _TRADE_USER_INTENT_RE.search(ut):
        return assistant_after_combat_strip

    narrative, parsed = _extract_narrative_for_cues(raw)
    if parse_open_shop_cue((narrative or "").strip()):
        return assistant_after_combat_strip

    loc_key = _current_location_key(conn, campaign_id)
    keys = _shop_npc_keys_in_scene(conn, loc_key)
    if not keys:
        return assistant_after_combat_strip

    chosen = _pick_shop_npc_key(narrative or "", keys)
    if not chosen:
        return assistant_after_combat_strip

    new_narr = (narrative or "").rstrip() + f"\nOpen Shop {chosen}"
    logger.info(
        "open_shop_fallback_injected",
        campaign_id=campaign_id,
        npc_key=chosen,
        location_key=loc_key,
    )
    return _repack_narrative(raw, new_narr.strip(), parsed)


def _parse_grant_item_entry(x: object) -> tuple[str, str | None] | None:
    """Parse a single grant_item element into (label, description|None). Returns None if invalid."""
    if isinstance(x, dict):
        label = str(x.get("label") or "").strip()
        desc = str(x.get("description") or "").strip() or None
        return (label, desc) if label else None
    if isinstance(x, str) and x.strip():
        return (x.strip(), None)
    return None


_MONETARY_BAG_RE = re.compile(
    r'\b(mieszek|sakiewka|trzos|sakwa|woreczek)\b',
    re.IGNORECASE,
)
_MONETARY_CONTENT_RE = re.compile(
    r'\b(monet|zapłat|złot|gold|gp)\w*\b',
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r'\b(\d+)\b')


def _monetary_item_gold(label: str, description: str | None) -> int | None:
    """Return gold amount if label is a monetary purse/bag; None if it's a regular item.

    Requires bag keyword in label AND money keyword in label+description to avoid
    false-positives like 'Pusty mieszek' (empty bag = narrative prop, not currency).
    """
    combined = (label or "") + " " + (description or "")
    if not (_MONETARY_BAG_RE.search(label or "") and _MONETARY_CONTENT_RE.search(combined)):
        return None
    m = _AMOUNT_RE.search(combined)
    return int(m.group(1)) if m else 10


def extract_grant_cues(
    assistant_text: str,
) -> tuple[str, list[str], int | None, str | None, dict[str, str | None]]:
    """
    Collect GM grant cues from the end of assistant text.
    Returns: cleaned_text, grant_item_labels, grant_gold_amount, open_shop_npc_key, grant_item_descriptions.
    grant_item_descriptions maps label → description (or None) for narrative items.
    Handles: roll_cue "Grant Item X", grant_item "X"/"obj", grant_item [...]s, last-line cues.
    """
    clean_text = (assistant_text or "").rstrip()
    grant_item_labels: list[str] = []
    grant_item_descriptions: dict[str, str | None] = {}
    grant_gold_amount: int | None = None
    # Bag-converted gold (#775) — explicit Grant Gold N always wins over bag conversion
    _bag_gold: int | None = None
    open_shop_npc_key: str | None = None

    def _add_entry(entry: tuple[str, str | None] | None) -> None:
        nonlocal _bag_gold
        if entry and entry[0] not in grant_item_labels:
            gold = _monetary_item_gold(entry[0], entry[1])
            if gold is not None:
                # Safety-net: monetary bag → grant_gold fallback (#775)
                if _bag_gold is None:
                    _bag_gold = gold
                return
            grant_item_labels.append(entry[0])
            grant_item_descriptions[entry[0]] = entry[1]

    # JSON-mode GM response
    try:
        payload = json.loads(_strip_json_code_fence(clean_text))
    except Exception:
        payload = None
    if isinstance(payload, dict):
        # Check dedicated grant_item field (string, object, or array) — LLM alternate format
        raw_gi = payload.get("grant_item")
        if raw_gi:
            if isinstance(raw_gi, list):
                for x in raw_gi:
                    _add_entry(_parse_grant_item_entry(x))
            else:
                _add_entry(_parse_grant_item_entry(raw_gi))
            # Clear grant_item from payload whether converted to gold or kept as item
            payload["grant_item"] = None
            clean_text = json.dumps(payload, ensure_ascii=False)

        roll_cue = str(payload.get("roll_cue") or "").strip()
        if roll_cue:
            rc_item = parse_grant_item_cue(roll_cue)
            if rc_item and rc_item not in grant_item_labels:
                gold = _monetary_item_gold(rc_item, None)
                if gold is not None:
                    if _bag_gold is None:
                        _bag_gold = gold
                else:
                    grant_item_labels.append(rc_item)
                    grant_item_descriptions.setdefault(rc_item, None)
            if grant_gold_amount is None:
                grant_gold_amount = parse_grant_gold_cue(roll_cue)
            if open_shop_npc_key is None:
                open_shop_npc_key = parse_open_shop_cue(roll_cue)
            if rc_item or grant_gold_amount is not None or open_shop_npc_key:
                payload["roll_cue"] = None
                clean_text = json.dumps(payload, ensure_ascii=False)

    for _ in range(4):
        maybe_item = parse_grant_item_cue(clean_text)
        if maybe_item and maybe_item not in grant_item_labels:
            gold = _monetary_item_gold(maybe_item, None)
            clean_text = strip_last_grant_item_cue(clean_text)
            if gold is not None:
                # Safety-net: monetary bag → grant_gold fallback (#775)
                if _bag_gold is None:
                    _bag_gold = gold
            else:
                grant_item_labels.append(maybe_item)
                # Plain-text cues carry no description
                grant_item_descriptions.setdefault(maybe_item, None)
            continue
        if grant_gold_amount is None:
            maybe_gold = parse_grant_gold_cue(clean_text)
            if maybe_gold is not None:
                grant_gold_amount = maybe_gold
                clean_text = strip_last_grant_gold_cue(clean_text)
                continue
        if open_shop_npc_key is None:
            maybe_shop = parse_open_shop_cue(clean_text)
            if maybe_shop:
                open_shop_npc_key = maybe_shop
                clean_text = strip_last_open_shop_cue(clean_text)
                continue
        break
    # Bag-converted gold fills in only if no explicit Grant Gold cue was found (#775)
    if grant_gold_amount is None and _bag_gold is not None:
        grant_gold_amount = _bag_gold
    return clean_text, grant_item_labels, grant_gold_amount, open_shop_npc_key, grant_item_descriptions


def _resolve_grant_catalog_item(conn: sqlite3.Connection, label: str) -> dict[str, str] | None:
    """Map Grant Item cue label to game_config_items (active, approved)."""
    lab = str(label or "").strip()
    if not lab:
        return None
    try:
        row = conn.execute(
            """
            SELECT key, label
            FROM game_config_items
            WHERE lower(label) = lower(?) AND is_active = 1 AND COALESCE(approved, 1) = 1
            LIMIT 1
            """,
            (lab,),
        ).fetchone()
        if row:
            return {"item_key": str(row["key"]), "label": str(row["label"])}
        row = conn.execute(
            """
            SELECT key, label
            FROM game_config_items
            WHERE lower(label) LIKE lower(?) AND is_active = 1 AND COALESCE(approved, 1) = 1
            LIMIT 1
            """,
            (f"%{lab}%",),
        ).fetchone()
        if row:
            return {"item_key": str(row["key"]), "label": str(row["label"])}
    except sqlite3.OperationalError:
        return None
    return None


def apply_grant_gold_to_character(
    conn: sqlite3.Connection, *, character_id: int, amount: int,
    source: str = "narrative_gold_grant", campaign_id: int | None = None,
) -> int | None:
    if int(amount) <= 0:
        return None
    row = conn.execute(
        """
        UPDATE characters
        SET gold_gp = COALESCE(gold_gp, 0) + ?
        WHERE id = ?
        RETURNING gold_gp, campaign_id
        """,
        (int(amount), int(character_id)),
    ).fetchone()
    if not row:
        return None
    try:
        from app.services.economy_service import journal_gold_delta
        journal_gold_delta(
            conn, int(character_id), int(amount), source,
            campaign_id=campaign_id if campaign_id is not None else row["campaign_id"],
        )
    except Exception:
        pass
    return int(row["gold_gp"] or 0)


# Keep for backward compat — no longer called for new items
def append_narrative_item_to_sheet(
    conn: sqlite3.Connection,
    *,
    character_id: int,
    label: str,
    source: str = "gm",
    given_at: str | None = None,
) -> None:
    """Deprecated: use _grant_narrative_item_to_inventory instead."""
    _grant_narrative_item_to_inventory(conn, character_id=character_id, label=label,
                                       source=source, given_at=given_at)


# ── Narrative Items — T46 ─────────────────────────────────────────────────────

WEAPON_LABEL_KEYWORDS = [
    "miecz", "sztylet", "włócznia", "topór", "łuk", "kusza",
    "nóż", "halabarda", "buzdygan", "rapier", "laska", "różdżka",
    "broń", "ostrze", "spear", "sword", "dagger", "axe", "bow",
    "siekiera", "oszczep", "bełt", "pika", "kopja",
]


def _is_weapon_label(label: str) -> bool:
    l = label.lower()
    return any(kw in l for kw in WEAPON_LABEL_KEYWORDS)


def _grant_narrative_item_to_inventory(
    conn: sqlite3.Connection,
    *,
    character_id: int,
    label: str,
    source: str = "gm",
    item_type: str = "narrative",
    description: str | None = None,
    given_at: str | None = None,
) -> None:
    """Store a free-form narrative item directly in character_inventory (T46)."""
    meta: dict = {"item_type": item_type}
    if description:
        meta["description"] = description
    if given_at:
        meta["given_at"] = given_at
    # inv_xor CHECK constraint requires exactly one key to be non-NULL.
    # Use '__narrative__' sentinel so narrative items satisfy the constraint
    # without needing a real game_config_items entry.
    conn.execute(
        """INSERT INTO character_inventory
           (character_id, label, item_key, weapon_key, consumable_key,
            quantity, equipped, source, meta_json)
           VALUES (?, ?, '__narrative__', NULL, NULL, 1, 0, ?, ?)""",
        (int(character_id), str(label).strip(), str(source or "gm"),
         json.dumps(meta, ensure_ascii=False)),
    )
    logger.info("narrative_item_granted_to_inventory", character_id=character_id, label=label)


def _grant_narrative_weapon(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
    label: str,
    source: str = "gm",
) -> str | None:
    """
    Create a pending game_config_weapons entry for a narrative weapon and grant it
    to character_inventory via weapon_key so the player can equip it immediately.
    Returns the new weapon key, or None on failure.
    """
    import re as _re
    import time as _time
    # Normalise label to a safe key
    slug = _re.sub(r"[^a-z0-9]+", "_", label.lower().strip())[:30].strip("_")
    key = f"narrative_{slug}_{campaign_id}_{int(_time.time()) % 100000}"

    try:
        # Check if weapon table has campaign_id column yet
        cols = {r[1] for r in conn.execute("PRAGMA table_info(game_config_weapons)").fetchall()}
        has_campaign_col = "campaign_id" in cols
        has_review_col = "review_status" in cols

        if has_campaign_col and has_review_col:
            conn.execute(
                """INSERT OR IGNORE INTO game_config_weapons
                   (key, label, weapon_type, damage_die, linked_stat, allowed_classes,
                    description, ai_generated, approved, campaign_id, review_status,
                    is_active, value_gp, weight_kg)
                   VALUES (?, ?, 'melee', '1d6', 'STR', '[]', ?, 1, 0, ?, 'pending_review', 1, 0, 1.0)""",
                (key, label, f"Narracyjna broń: {label}", int(campaign_id)),
            )
        else:
            # Fallback if migration hasn't run yet
            conn.execute(
                """INSERT OR IGNORE INTO game_config_weapons
                   (key, label, weapon_type, damage_die, linked_stat, allowed_classes,
                    description, ai_generated, approved, is_active, value_gp, weight_kg)
                   VALUES (?, ?, 'melee', '1d6', 'STR', '[]', ?, 1, 0, 1, 0, 1.0)""",
                (key, label, f"Narracyjna broń: {label}"),
            )

        # Grant via normal weapon_key path (store original label for display)
        conn.execute(
            """INSERT INTO character_inventory
               (character_id, weapon_key, item_key, consumable_key, label,
                quantity, equipped, source, meta_json)
               VALUES (?, ?, NULL, NULL, ?, 1, 0, ?, ?)""",
            (int(character_id), key, str(label), str(source or "gm"),
             json.dumps({"narrative_weapon": True, "original_label": label}, ensure_ascii=False)),
        )
        logger.info("narrative_weapon_created", key=key, label=label, campaign_id=campaign_id)
        return key
    except Exception as e:
        logger.warning("narrative_weapon_create_failed", label=label, error=str(e))
        # Fall back to plain narrative item
        _grant_narrative_item_to_inventory(conn, character_id=character_id, label=label,
                                           source=source, item_type="narrative",
                                           description="Znaleziona broń")
        return None


# U6 (#530): visual triage helper — common junk-word stems mark a pending item
# as 'trivial' so the admin can skim past leaves/stones/twigs in the review queue.
# Stems (prefix match) so Polish inflection is covered (piasek/piasku/piaskiem).
# False positives are harmless (badge only, item still reviewable).
_TRIVIAL_ITEM_STEMS = (
    "kamie", "kamyk", "kamycz", "gałąz", "gałęz", "patyk",
    "liść", "liści", "listek", "listk", "piasek", "piask", "piach",
    "pył", "kurz", "szmat", "sznur", "odłam", "okruch", "okrusz",
    "drzazg", "traw", "słom", "sian", "błot", "glin", "skorup",
    "muszl", "piór", "desk", "drewienk", "węgiel", "węgl",
    "popiół", "popiol", "śmieć", "śmieci", "gruz", "żwir",
    "korek", "kork", "szyszk", "żołądź", "żołędz", "chwast",
)


def _is_trivial_item_label(label: str) -> bool:
    """True when the label looks like worthless junk (see _TRIVIAL_ITEM_STEMS)."""
    words = re.findall(r"[a-ząćęłńóśźż]+", str(label or "").lower())
    return any(w.startswith(stem) for w in words for stem in _TRIVIAL_ITEM_STEMS)


def _grant_pending_item(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
    label: str,
    source: str = "gm",
    description: str | None = None,
) -> str | None:
    """D1 (#376) — Pending flow for items.

    When the GM grants an item whose key is unknown (not a weapon, not in the
    catalog), create a pending_review entry in game_config_items so it lands in
    the admin review queue, then grant it to the player via item_key so it shows
    up in the inventory immediately. Mirrors _grant_narrative_weapon.

    Returns the new item key, or None on failure (caller falls back to a plain
    narrative inventory row).
    """
    import re as _re
    import time as _time
    slug = _re.sub(r"[^a-z0-9]+", "_", label.lower().strip())[:30].strip("_")
    key = f"narrative_item_{slug}_{campaign_id}_{int(_time.time()) % 100000}"
    desc = description or f"Narracyjny przedmiot: {label}"
    pending_category = "trivial" if _is_trivial_item_label(label) else "standard"

    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(game_config_items)").fetchall()}
        has_campaign_col = "campaign_id" in cols
        has_review_col = "review_status" in cols
        has_category_col = "pending_category" in cols

        if has_campaign_col and has_review_col and has_category_col:
            conn.execute(
                """INSERT OR IGNORE INTO game_config_items
                   (key, label, item_type, description, value_gp,
                    ai_generated, approved, campaign_id, review_status, is_active,
                    pending_category)
                   VALUES (?, ?, 'misc', ?, 0, 1, 0, ?, 'pending_review', 1, ?)""",
                (key, label, desc, int(campaign_id), pending_category),
            )
        elif has_campaign_col and has_review_col:
            conn.execute(
                """INSERT OR IGNORE INTO game_config_items
                   (key, label, item_type, description, value_gp,
                    ai_generated, approved, campaign_id, review_status, is_active)
                   VALUES (?, ?, 'misc', ?, 0, 1, 0, ?, 'pending_review', 1)""",
                (key, label, desc, int(campaign_id)),
            )
        else:
            # Fallback if migration hasn't run yet — approved=0 still marks it pending.
            conn.execute(
                """INSERT OR IGNORE INTO game_config_items
                   (key, label, item_type, description, value_gp,
                    ai_generated, approved, is_active)
                   VALUES (?, ?, 'misc', ?, 0, 1, 0, 1)""",
                (key, label, desc),
            )

        # Grant via normal item_key path (store original label for display)
        conn.execute(
            """INSERT INTO character_inventory
               (character_id, item_key, weapon_key, consumable_key, label,
                quantity, equipped, source, meta_json)
               VALUES (?, ?, NULL, NULL, ?, 1, 0, ?, ?)""",
            (int(character_id), key, str(label), str(source or "gm"),
             json.dumps({"pending_item": True, "original_label": label}, ensure_ascii=False)),
        )
        logger.info("pending_item_created", key=key, label=label, campaign_id=campaign_id)
        return key
    except Exception as e:
        logger.warning("pending_item_create_failed", label=label, error=str(e))
        # Fall back to plain narrative item
        _grant_narrative_item_to_inventory(conn, character_id=character_id, label=label,
                                           source=source, item_type="narrative",
                                           description=description)
        return None


def _sheet_current_hp(sheet: dict) -> int | None:
    if not isinstance(sheet, dict):
        return None
    for k in ("current_hp", "hp", "health"):
        if k in sheet and sheet[k] is not None:
            try:
                return int(sheet[k])
            except (TypeError, ValueError):
                continue
    return None


def _clean_model_hint(m: str | None) -> str | None:
    """Normalize model hints — treat 'default' sentinel as absent."""
    v = (m or "").strip()
    return v if v and v != "default" else None


def resolve_model_name(
    requested_model: str | None,
    campaign_model: str | None,
    llm_config: dict[str, str] | None = None,
) -> str:
    req = _clean_model_hint(requested_model)
    cam = _clean_model_hint(campaign_model)
    effective = get_effective_config(llm_config)
    # For OpenAI and Azure the caller specifies the model/deployment by name directly —
    # no need to validate against a remote list (Azure catalogs show model IDs, not deployment names).
    if effective["provider"] in ("openai", "azure"):
        return (req or cam or effective["model"]).strip()

    # For Ollama and other self-hosted providers, validate against the live model list
    # so the UI can fall back to whatever is actually pulled locally.
    health = get_health(llm_config)
    available = health.get("models") or []
    if not available:
        return (req or cam or effective["model"]).strip()
    if req and req in available:
        return req
    if cam and cam in available:
        return cam
    if effective["model"] in available:
        return effective["model"]
    return available[0]


def get_campaign_or_404(conn: sqlite3.Connection, campaign_id: int):
    campaign = conn.execute(
        "SELECT * FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def get_character_or_404(
    conn: sqlite3.Connection, campaign_id: int, character_id: int
):
    character = conn.execute(
        "SELECT * FROM characters WHERE id = ? AND campaign_id = ?",
        (character_id, campaign_id),
    ).fetchone()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character


def get_active_campaign_or_gone(conn: sqlite3.Connection, campaign_id: int):
    """404 if missing, 410 if campaign has ended (solo death / GM-ended)."""
    campaign = get_campaign_or_404(conn, campaign_id)
    if str(campaign["status"] or "").lower() == "ended":
        raise HTTPException(status_code=410, detail="This campaign has ended.")
    return campaign


def _narrative_turn_count(conn: sqlite3.Connection, campaign_id: int) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM campaign_turns
        WHERE campaign_id = ? AND route = 'narrative'
        """,
        (campaign_id,),
    ).fetchone()
    return int(row["n"] or 0) if row else 0


def _require_gm_plan_before_narrative_llm(
    conn: sqlite3.Connection, campaign_id: int, campaign: sqlite3.Row
) -> None:
    """
    T05: ensure gm_plan_json is ready before running the narrative LLM.
    If plan is missing, auto-generate it now (on-demand, first turn triggers it).
    Pre-built campaigns (template_id set) keep the template plan untouched and
    use generate_opening_scene() which reads key_locations for a location-specific intro.
    """
    from app.services.gm_plan_schema import gm_plan_is_ready
    import json as _j

    try:
        raw = campaign["gm_plan_json"]
    except (KeyError, IndexError):
        raw = None

    # Pre-built campaigns: the template plan is authoritative — never overwrite it.
    # Use the dedicated opening-scene generator which reads key_locations from the plan.
    try:
        template_id = campaign["template_id"]
    except (KeyError, IndexError):
        template_id = None

    if template_id and raw and raw.strip() not in ("", "{}"):
        if _narrative_turn_count(conn, campaign_id) == 0:
            try:
                from app.services.turn_pipeline import generate_opening_scene
                from app.services.user_llm_settings import get_user_llm_settings_full
                char_row = conn.execute(
                    "SELECT id, user_id FROM characters WHERE campaign_id = ? AND is_active = 1 LIMIT 1",
                    (campaign_id,),
                ).fetchone()
                if char_row:
                    _llm_cfg = get_user_llm_settings_full(int(char_row["user_id"] or 0))
                    _model = _llm_cfg.get("model") or "gemma3:1b"
                    generate_opening_scene(campaign_id, int(char_row["id"]), _model, _llm_cfg, conn)
                    logger.info("prebuilt_opening_scene_generated", campaign_id=campaign_id)
            except Exception as _oe:
                logger.warning("prebuilt_opening_scene_failed", campaign_id=campaign_id, error=str(_oe))
        return  # template plan is the plan — never fall through to overwrite

    if gm_plan_is_ready(raw):
        return
    if _narrative_turn_count(conn, campaign_id) > 0:
        return
    # Dungeon-mode campaigns don't need a GM plan — tile sequence IS the plan
    if str(campaign["mode"] or "solo").lower() == "dungeon":
        return

    # Plan not ready and no turns yet — auto-generate now
    try:
        from app.services.gm_plan_generation_service import generate_initial_gm_plan_with_retries
        from app.services.user_llm_settings import get_user_llm_settings_full

        # Find the character for this campaign to build char summary
        char_row = conn.execute(
            "SELECT id, user_id, name, sheet_json, location FROM characters WHERE campaign_id = ? AND is_active = 1 LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not char_row:
            return  # no character yet, skip

        user_id = int(char_row["user_id"] or 0)
        llm_config = get_user_llm_settings_full(user_id)
        model = llm_config.get("model") or "gemma3:1b"

        import json as _j
        sheet = _j.loads(char_row["sheet_json"] or "{}")
        archetype = str(sheet.get("archetype", "warrior")).lower()
        archetype_label = "Uczony" if archetype == "scholar" else "Wojownik"
        stats = sheet.get("stats") or {}
        stat_lines = ", ".join(f"{k}:{v}" for k, v in stats.items()) if stats else ""
        # Prefer the session's current_location (set by resolve_starting_hex) over the
        # characters.location column (often NULL when frontend omits it).
        _sess_loc = conn.execute(
            """SELECT gl.label FROM game_sessions gs
               JOIN game_locations gl ON gl.id = gs.current_location_id
               WHERE gs.campaign_id = ? AND gl.label IS NOT NULL
               LIMIT 1""",
            (campaign_id,),
        ).fetchone()
        _location_label = (_sess_loc["label"] if _sess_loc else None) or char_row["location"] or "nieznane miejsce"
        char_summary = (
            f"Postać: {char_row['name'] or 'Bohater'}, Archetyp: {archetype_label}"
            + (f", Statystyki: {stat_lines}" if stat_lines else "")
            + f", Lokalizacja startowa: {_location_label}."
        )
        gm_ready, _ = generate_initial_gm_plan_with_retries(
            conn,
            campaign_id=campaign_id,
            campaign_title=str(campaign["title"] or f"Kampania {campaign_id}"),
            campaign_language="pl",
            system_id="fantasy",
            char_summary=char_summary,
            user_id=user_id,
            model=model,
            llm_config=llm_config,
            max_attempts=2,
        )
        logger.info("gm_plan_auto_generated_on_first_turn", campaign_id=campaign_id)

        # Also generate opening scene so player sees a welcome message
        # Skip for dungeon-mode campaigns — enter_dungeon already provides room_narrative
        _camp_mode = str(campaign["mode"] or "solo").lower() if campaign else "solo"
        if gm_ready and _camp_mode != "dungeon":
            try:
                from app.services.llm_service import generate_chat as _gen
                from app.system_prompt_loader import SYSTEM_PROMPT_TEXT as _OPENING_SYS
                _gm_row_t = conn.execute(
                    "SELECT gm_plan_json FROM campaigns WHERE id = ? LIMIT 1",
                    (campaign_id,),
                ).fetchone()
                _plan_ctx_t = build_opening_plan_context(
                    _gm_row_t["gm_plan_json"] if _gm_row_t else None
                )
                _opening_prompt = (
                    f"{char_summary}{_plan_ctx_t}\n\n"
                    "To jest pierwsza chwila przygody. Zacznij sesję od klimatycznego opisu miejsca, "
                    "w którym bohater się znajduje — miejsce MUSI pasować do kontekstu kampanii. "
                    "Nie pytaj gracza o plany - po prostu opisz scenę "
                    "i zostaw otwarte zakończenie zachęcające do działania."
                )
                _opening = (_gen(
                    messages=[{"role": "system", "content": _OPENING_SYS},
                               {"role": "user", "content": _opening_prompt}],
                    model=model, llm_config=llm_config,
                ) or "").strip()
                if _opening:
                    _nt = int((conn.execute(
                        "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
                        (campaign_id,),
                    ).fetchone()[0]) or 1)
                    conn.execute(
                        """INSERT INTO campaign_turns
                           (campaign_id, character_id, turn_number, user_text, route, assistant_text)
                           VALUES (?,?,?,?,?,?)""",
                        (campaign_id, int(char_row["id"] or 0),
                         _nt, "", "narrative", _opening),
                    )
                    conn.commit()
                    logger.info("opening_scene_generated_on_first_turn", campaign_id=campaign_id)
            except Exception as _oe:
                logger.warning("opening_scene_auto_failed", campaign_id=campaign_id, error=str(_oe))
    except Exception as _plan_err:
        logger.warning("gm_plan_auto_generation_failed", campaign_id=campaign_id, error=str(_plan_err))
        # Don't block — let the turn proceed without a plan rather than permanent error


def get_next_turn_number(conn: sqlite3.Connection, campaign_id: int) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(turn_number), 0) AS max_turn
        FROM campaign_turns
        WHERE campaign_id = ?
        """,
        (campaign_id,),
    ).fetchone()
    return int(row["max_turn"] or 0) + 1


def create_turn_log(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int | None,
    user_text: str,
    assistant_text: str | None,
    route: str,
):
    cur = conn.cursor()
    turn_number = get_next_turn_number(conn, campaign_id)

    # D3 (#378) — NPC_MEMORY tags: capture remembered facts, then strip the raw
    # `[NPC_MEMORY:...]` tag from the stored/displayed narrative so the player
    # never sees it. Facts are persisted below (narrative branch).
    _npc_memory_pairs: list[tuple[str, str]] = []
    if assistant_text:
        from app.services.npc_memory_service import (
            parse_npc_memory_tags,
            strip_npc_memory_tags,
        )
        _npc_memory_pairs = parse_npc_memory_tags(assistant_text)
        if _npc_memory_pairs:
            assistant_text = strip_npc_memory_tags(assistant_text)

    # D6 (#381) — Narrative State tags: capture key events + planted seeds, then
    # strip the raw [NARRATIVE_EVENT/SEED:...] tags from the displayed narrative.
    _narr_events: list[tuple[str, str]] = []
    _narr_seeds: list[tuple[str, str]] = []
    if assistant_text:
        from app.services.narrative_state_service import (
            parse_narrative_event_tags,
            parse_narrative_seed_tags,
            strip_narrative_tags,
        )
        _narr_events = parse_narrative_event_tags(assistant_text)
        _narr_seeds = parse_narrative_seed_tags(assistant_text)
        if _narr_events or _narr_seeds:
            assistant_text = strip_narrative_tags(assistant_text)

    cur.execute(
        """
        INSERT INTO campaign_turns (
            campaign_id,
            character_id,
            user_text,
            route,
            assistant_text,
            turn_number
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (campaign_id, character_id, user_text, route, assistant_text, turn_number),
    )

    turn_id = cur.lastrowid

    row = cur.execute(
        """
        SELECT id, campaign_id, turn_number, created_at
        FROM campaign_turns
        WHERE id = ?
        """,
        (turn_id,),
    ).fetchone()

    conn.commit()

    if route == "narrative":
        # T10 — po zapisie tury narracyjnej: co N tur (game_config_meta) uruchom ensure w tle.
        from app.services.summary_ensure_automation import (
            schedule_after_narrative_turn_committed,
        )

        schedule_after_narrative_turn_committed(campaign_id)

    # BUG-02: auto-advance the in-game clock per turn type.
    # Routes that should NOT tick: meta/slash commands, opening turn, rolls
    # (the player just rolled dice — no in-world time passed).
    try:
        from app.services.clock_config_service import get_clock_config
        from app.services.clock_service import advance_clock

        cfg = get_clock_config()
        default_min = 0
        if route == "narrative":
            default_min = cfg["narrative_min"]
        elif route == "combat":
            default_min = cfg["combat_min"]
        elif route == "travel":
            default_min = cfg["travel_min"]

        # LLM override: only honored for narrative turns. The MG can request a
        # larger advance ("rozmowa trwała godzinę" → 60). Smaller values are
        # ignored — backend default is the floor so quick turns still tick.
        llm_min = 0
        if route == "narrative" and assistant_text:
            try:
                _adata = json.loads(_strip_json_code_fence(assistant_text))
                if isinstance(_adata, dict):
                    # #758: explicit target time-of-day jump ("czekam do zmroku").
                    # Engine computes minutes to the start of the requested phase.
                    _tod = _adata.get("advance_to_time_of_day")
                    if _tod:
                        from app.services.clock_service import (
                            get_clock_state,
                            minutes_to_reach_phase,
                        )

                        _cur = get_clock_state(campaign_id, conn=conn)
                        llm_min = max(
                            llm_min, minutes_to_reach_phase(_cur["hour"], str(_tod))
                        )
                    # Raw minutes override. Clamp 0-1440 (24h) so "czekam do jutra"
                    # is not silently truncated to 8h (#758).
                    _raw = _adata.get("time_advance_minutes")
                    if _raw is not None:
                        llm_min = max(llm_min, max(0, min(int(_raw), 1440)))
            except Exception:
                pass

        effective_min = max(default_min, llm_min)
        if effective_min > 0:
            advance_clock(
                campaign_id,
                minutes=effective_min,
                reason=f"turn_{route}",
                conn=conn,
            )
            conn.commit()
    except Exception as _clk_err:
        logger.warning(
            "clock_auto_advance_failed",
            campaign_id=campaign_id,
            route=route,
            error=str(_clk_err),
        )

    # C1: track consecutive turns without hex change for STORY_STALE injection.
    # Compares current_hex with _prev_turn_hex stored at end of previous turn.
    # On change: reset counter to 0. Same hex: increment. Context injector reads
    # turns_at_location and fires [STORY_STALE:…] when >= threshold (default 5).
    if route in ("narrative", "combat", "travel"):
        try:
            _sf_c1_row = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if _sf_c1_row:
                _sf_c1 = json.loads(_sf_c1_row["session_flags"] or "{}")
                _curr_hex_c1 = _sf_c1.get("current_hex")
                _prev_hex_c1 = _sf_c1.get("_prev_turn_hex")
                if _curr_hex_c1 != _prev_hex_c1:
                    _sf_c1["turns_at_location"] = 0
                else:
                    _sf_c1["turns_at_location"] = _sf_c1.get("turns_at_location", 0) + 1
                _sf_c1["_prev_turn_hex"] = _curr_hex_c1
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                    (json.dumps(_sf_c1, ensure_ascii=False), campaign_id),
                )
                conn.commit()
        except Exception as _c1_err:
            logger.warning(
                "turns_at_location_update_failed",
                campaign_id=campaign_id,
                route=route,
                error=str(_c1_err),
            )

    # BUG-03: persist NPCs from MG response. The narrator may emit `npc_met`
    # (first encounter) and/or `npc_update` (relation/notes change). Both are
    # optional and only on narrative turns; everything else is a no-op.
    if route == "narrative" and assistant_text:
        try:
            from app.services.npc_memory_service import (
                record_npc_met,
                update_npc_relation,
            )

            _ndata = json.loads(_strip_json_code_fence(assistant_text))
            if isinstance(_ndata, dict):
                _turn_num = int(row["turn_number"])
                _met_raw = _ndata.get("npc_met")
                _met_entries = _met_raw if isinstance(_met_raw, list) else (
                    [_met_raw] if isinstance(_met_raw, dict) else []
                )
                for _e in _met_entries:
                    if not isinstance(_e, dict):
                        continue
                    _name = str(_e.get("name") or "").strip()
                    if not _name:
                        continue
                    _met_res = record_npc_met(
                        campaign_id=campaign_id,
                        name=_name,
                        role=(str(_e.get("role")).strip() if _e.get("role") else None),
                        first_met_location=(str(_e.get("location")).strip() if _e.get("location") else None),
                        first_met_turn=_turn_num,
                        notes=(str(_e.get("notes")).strip() if _e.get("notes") else None),
                        conn=conn,
                    )
                    # BUG-06 / XS6: +5 XP for first encounter with a named NPC
                    if _met_res.get("ok") and _met_res.get("new") and character_id is not None:
                        try:
                            from app.services.xp_sources import grant_first_npc_talk
                            _npc_key = _name.lower().replace(" ", "_")
                            grant_first_npc_talk(conn, int(character_id), campaign_id, _npc_key, _turn_num)
                        except Exception as _xp_err:
                            logger.warning("xs6_npc_xp_failed", error=str(_xp_err))

                _upd_raw = _ndata.get("npc_update")
                _upd_entries = _upd_raw if isinstance(_upd_raw, list) else (
                    [_upd_raw] if isinstance(_upd_raw, dict) else []
                )
                for _e in _upd_entries:
                    if not isinstance(_e, dict):
                        continue
                    _name = str(_e.get("name") or "").strip()
                    if not _name:
                        continue
                    _rel = _e.get("relation_status")
                    res = update_npc_relation(
                        campaign_id=campaign_id,
                        name=_name,
                        relation_status=(str(_rel).strip().lower() if _rel else None),
                        notes=(str(_e.get("notes")).strip() if _e.get("notes") else None),
                        conn=conn,
                    )
                    # If the MG sent an update for someone not yet recorded, fall
                    # through to record_npc_met so we don't drop the relation hint.
                    if not res.get("ok") and res.get("reason") == "not_found":
                        record_npc_met(
                            campaign_id=campaign_id,
                            name=_name,
                            first_met_turn=_turn_num,
                            notes=(str(_e.get("notes")).strip() if _e.get("notes") else None),
                            conn=conn,
                        )
                        if _rel:
                            update_npc_relation(
                                campaign_id=campaign_id,
                                name=_name,
                                relation_status=str(_rel).strip().lower(),
                                conn=conn,
                            )
                conn.commit()
        except Exception as _npc_err:
            logger.warning(
                "npc_memory_persist_failed",
                campaign_id=campaign_id,
                error=str(_npc_err),
            )

    # D3 (#378) — persist explicit NPC_MEMORY facts (accumulate into NPC notes,
    # injected on next visit via format_known_npcs_block). Independent of the
    # JSON-envelope parsing above so plain-text narratives still work.
    if route == "narrative" and _npc_memory_pairs:
        try:
            from app.services.npc_memory_service import append_npc_memory

            for _nm_name, _nm_fact in _npc_memory_pairs:
                append_npc_memory(
                    campaign_id=campaign_id, name=_nm_name, memory=_nm_fact, conn=conn
                )
            conn.commit()
            logger.info(
                "npc_memory_tag_persisted",
                campaign_id=campaign_id,
                count=len(_npc_memory_pairs),
            )
        except Exception as _nm_err:
            logger.warning(
                "npc_memory_tag_persist_failed",
                campaign_id=campaign_id,
                error=str(_nm_err),
            )

    # D6 (#381) — persist Narrative State into session_flags (World State), so the
    # compressed block can be injected on later turns for continuity.
    if route == "narrative" and (_narr_events or _narr_seeds):
        try:
            import json as _ns_json
            from app.services.narrative_state_service import apply_narrative_tags

            gs = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if gs:
                sf = _ns_json.loads(gs["session_flags"] or "{}")
                sf["narrative_state"] = apply_narrative_tags(
                    sf.get("narrative_state"),
                    events=_narr_events, seeds=_narr_seeds, turn=int(turn_number),
                )
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                    (_ns_json.dumps(sf, ensure_ascii=False), campaign_id),
                )
                conn.commit()
                logger.info(
                    "narrative_state_updated", campaign_id=campaign_id,
                    events=len(_narr_events), seeds=len(_narr_seeds),
                )
        except Exception as _ns_err:
            logger.warning(
                "narrative_state_persist_failed",
                campaign_id=campaign_id,
                error=str(_ns_err),
            )

    # BUG-01: remove items when GM signals the player handed/lost one.
    # Only on narrative turns and only when we have a character to update.
    if route == "narrative" and assistant_text and character_id is not None:
        try:
            _rdata = json.loads(_strip_json_code_fence(assistant_text))
            if isinstance(_rdata, dict):
                _ri_raw = _rdata.get("remove_item")
                _ri_entries = _ri_raw if isinstance(_ri_raw, list) else (
                    [_ri_raw] if isinstance(_ri_raw, dict) else []
                )
                for _ri in _ri_entries:
                    if not isinstance(_ri, dict):
                        continue
                    _label = str(_ri.get("label") or "").strip()
                    if not _label:
                        continue
                    _inv_row = conn.execute(
                        """
                        SELECT id, quantity FROM character_inventory
                        WHERE character_id = ? AND LOWER(label) = LOWER(?)
                        LIMIT 1
                        """,
                        (int(character_id), _label),
                    ).fetchone()
                    if not _inv_row:
                        logger.warning(
                            "remove_item_not_found",
                            campaign_id=campaign_id,
                            character_id=character_id,
                            label=_label,
                        )
                        continue
                    if int(_inv_row["quantity"] or 1) > 1:
                        conn.execute(
                            "UPDATE character_inventory SET quantity = quantity - 1 WHERE id = ?",
                            (_inv_row["id"],),
                        )
                    else:
                        conn.execute(
                            "DELETE FROM character_inventory WHERE id = ?",
                            (_inv_row["id"],),
                        )
                    logger.info(
                        "remove_item_applied",
                        campaign_id=campaign_id,
                        character_id=character_id,
                        label=_label,
                    )
                conn.commit()
        except Exception as _ri_err:
            logger.warning(
                "remove_item_persist_failed",
                campaign_id=campaign_id,
                error=str(_ri_err),
            )

    # BUG-04: parse gm_note (per-turn), scene_advance, and gm_plan_update from LLM response.
    # All fields are optional. Only runs on narrative turns.
    if route == "narrative" and assistant_text:
        try:
            from app.services.gm_plan_schema import normalize_gm_plan
            _pdata = json.loads(_strip_json_code_fence(assistant_text))
            if isinstance(_pdata, dict):
                _gm_note = str(_pdata.get("gm_note") or "").strip()
                _scene_advance = bool(_pdata.get("scene_advance"))
                _plan_update = _pdata.get("gm_plan_update")

                if _gm_note or _scene_advance or isinstance(_plan_update, dict):
                    _turn_num = int(row["turn_number"])
                    _camp_row = conn.execute(
                        "SELECT gm_plan_json FROM campaigns WHERE id = ?",
                        (campaign_id,),
                    ).fetchone()
                    _plan = normalize_gm_plan(_camp_row["gm_plan_json"] if _camp_row else None)
                    _ep = dict(_plan.get("engine_private") or {})

                    if _gm_note:
                        _buf = list(_ep.get("gm_note_buffer") or [])
                        _buf.append({"turn": _turn_num, "note": _gm_note})
                        if len(_buf) > 30:
                            _buf = _buf[-30:]
                        _ep["gm_note_buffer"] = _buf

                    if _scene_advance:
                        _aa = _plan.get("active_arc_id")
                        if _aa and isinstance(_plan.get("arcs"), dict) and _aa in _plan["arcs"]:
                            _plan["arcs"][_aa]["current_scene_ordinal"] = (
                                int(_plan["arcs"][_aa].get("current_scene_ordinal") or 0) + 1
                            )

                    if isinstance(_plan_update, dict):
                        _aa = _plan.get("active_arc_id")
                        if _aa and isinstance(_plan.get("arcs"), dict) and _aa in _plan["arcs"]:
                            _arc = _plan["arcs"][_aa]
                            _rn = str(_plan_update.get("roadmap_note") or "").strip()
                            if _rn:
                                _old_rm = str(_arc.get("roadmap") or "").strip()
                                _arc["roadmap"] = (
                                    _old_rm + f"\n\n[T{_turn_num}] " + _rn
                                ).strip()
                            _goals_done = [
                                str(g).strip().lower()
                                for g in (_plan_update.get("scene_goals_done") or [])
                                if g
                            ]
                            if _goals_done:
                                _arc["scene_goals"] = [
                                    g for g in (_arc.get("scene_goals") or [])
                                    if not any(d in g.lower() for d in _goals_done)
                                ]
                            for _ng in (_plan_update.get("scene_goals_add") or []):
                                _ns = str(_ng).strip()
                                if _ns:
                                    _arc.setdefault("scene_goals", []).append(_ns)
                            if bool(_plan_update.get("scene_advance")):
                                _arc["current_scene_ordinal"] = (
                                    int(_arc.get("current_scene_ordinal") or 0) + 1
                                )
                        _ep["last_plan_updated_turn"] = _turn_num

                    _plan["engine_private"] = _ep
                    conn.execute(
                        "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
                        (json.dumps(_plan, ensure_ascii=False), campaign_id),
                    )
                    conn.commit()
        except Exception as _plan_err:
            logger.warning(
                "gm_plan_update_hook_failed",
                campaign_id=campaign_id,
                error=str(_plan_err),
            )

    return {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "turn_number": row["turn_number"],
        "created_at": row["created_at"],
    }


# ---------------------------------------------------------------------------
# Helper: export session to text file
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GET turns list
# ---------------------------------------------------------------------------

@router.get("/campaigns/{campaign_id}/turns")
def list_campaign_turns(
    campaign_id: int, limit: int = Query(default=30, ge=1, le=100)
):
    conn = get_db()
    try:
        get_active_campaign_or_gone(conn, campaign_id)

        rows = conn.execute(
            """
            SELECT
                t.id,
                t.campaign_id,
                t.character_id,
                t.user_text,
                t.route,
                t.assistant_text,
                t.created_at,
                t.turn_number,
                c.name AS character_name
                ,c.user_id AS character_user_id
            FROM campaign_turns t
            LEFT JOIN characters c ON c.id = t.character_id
            WHERE t.campaign_id = ?
            ORDER BY t.turn_number DESC
            LIMIT ?
            """,
            (campaign_id, limit),
        ).fetchall()

        turns = []
        for row in rows:
            r_route = row["route"]
            turns.append(
                {
                    "id": row["id"],
                    "turn_number": row["turn_number"],
                    "campaign_id": row["campaign_id"],
                    "character_id": row["character_id"],
                    "character_name": row["character_name"],
                    "character_user_id": row["character_user_id"],
                    "user_text": row["user_text"],
                    "assistant_text": row["assistant_text"],
                    "route": r_route,
                    "ooc": r_route == "helpme",
                    "created_at": row["created_at"],
                }
            )

        turns.reverse()

        return {
            "campaign_id": campaign_id,
            "turns": turns,
            "count": len(turns),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Debug log endpoint — T44 / Bug reporting
# ---------------------------------------------------------------------------

@router.get("/campaigns/{campaign_id}/turns/debug-log")
def get_debug_log(campaign_id: int, limit: int = Query(default=5, ge=1, le=20)):
    """
    Returns last N turns enriched with inventory events, combat events and hero state.
    Includes both machine-readable JSON and pre-formatted human text for GitHub issues.
    """
    conn = get_db()
    try:
        campaign = get_active_campaign_or_gone(conn, campaign_id)

        # Hero state
        char_row = conn.execute(
            "SELECT id, name, sheet_json, gold_gp FROM characters WHERE campaign_id = ? AND is_active = 1 LIMIT 1",
            (campaign_id,),
        ).fetchone()
        hero = {}
        if char_row:
            try:
                sh = json.loads(char_row["sheet_json"] or "{}")
            except Exception:
                sh = {}
            hero = {
                "id": char_row["id"],
                "name": char_row["name"],
                "archetype": sh.get("archetype", "?"),
                "level": sh.get("level", 1),
                "hp": sh.get("current_hp"),
                "max_hp": sh.get("max_hp"),
                "gold_gp": char_row["gold_gp"],
                "conditions": sh.get("conditions", []),
            }

        # Turns
        turn_rows = conn.execute(
            """SELECT t.id, t.turn_number, t.user_text, t.assistant_text, t.route, t.created_at
               FROM campaign_turns t
               WHERE t.campaign_id = ?
               ORDER BY t.turn_number DESC LIMIT ?""",
            (campaign_id, limit),
        ).fetchall()
        turn_rows = list(reversed(turn_rows))

        # Inventory changes — items acquired/removed near each turn
        inv_rows = conn.execute(
            """SELECT id, label, item_key, weapon_key, consumable_key, quantity, source,
                      acquired_at, meta_json
               FROM character_inventory
               WHERE character_id = ?
               ORDER BY id DESC LIMIT 50""",
            (hero.get("id", 0),),
        ).fetchall() if hero else []

        # Combat turns for this campaign
        combat_rows = conn.execute(
            """SELECT turn_number, actor, event_type, roll_value, damage, hp_after,
                      target_name, hit, narrative
               FROM combat_turns
               WHERE campaign_id = ?
               ORDER BY turn_number ASC, id ASC""",
            (campaign_id,),
        ).fetchall() if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='combat_turns'"
        ).fetchone() else []

        # Index combat rows by turn_number
        combat_by_turn: dict[int, list] = {}
        for cr in combat_rows:
            tn = int(cr["turn_number"] or 0)
            combat_by_turn.setdefault(tn, []).append(dict(cr))

        # Parse assistant_text cues
        def _parse_cues(raw: str) -> dict:
            cues: dict = {}
            if not raw:
                return cues
            # JSON wrapper
            try:
                d = json.loads(raw)
                if isinstance(d, dict):
                    if d.get("roll_cue"):
                        rc = str(d["roll_cue"])
                        if rc.lower().startswith("grant item "):
                            cues["grant_item"] = rc[11:].strip()
                        elif rc.lower().startswith("grant gold "):
                            cues["grant_gold"] = rc[11:].strip()
                        else:
                            cues["roll_cue"] = rc
                    li = d.get("location_intent")
                    if li and isinstance(li, dict) and li.get("action"):
                        cues["location"] = f"{li['action']}→{li.get('target_label','?')}"
            except Exception:
                pass
            # Inline tags
            import re as _re
            m = _re.search(r'\[COMBAT_START:([^\]]+)\]', raw)
            if m:
                cues["combat_start"] = m.group(1)
            if raw.startswith("[Rzut:") or "[Rzut:" in raw[:40]:
                m2 = _re.search(r'\[Rzut:\s*(.+?)\s*[—-]\s*(\d+)\]', raw)
                if m2:
                    cues["skill_roll"] = f"{m2.group(1)} d20={m2.group(2)}"
            return cues

        # Build turn objects
        turns_out = []
        for tr in turn_rows:
            tn = int(tr["turn_number"] or 0)
            raw = tr["assistant_text"] or ""
            cues = _parse_cues(raw)

            # Inventory events near this turn (by source=gm and timing heuristic)
            inv_events = []
            for inv in inv_rows:
                src = str(inv["source"] or "")
                if src in ("gm", "gm_grant_item", "loot", "dungeon"):
                    label = inv["label"] or inv["item_key"] or inv["weapon_key"] or "?"
                    qty = int(inv["quantity"] or 1)
                    try:
                        meta = json.loads(inv["meta_json"] or "{}")
                    except Exception:
                        meta = {}
                    inv_events.append({
                        "action": "added",
                        "label": label,
                        "quantity": qty,
                        "source": src,
                        "item_type": meta.get("item_type", "item"),
                    })

            turn_obj = {
                "turn_id": tr["id"],
                "turn_number": tn,
                "timestamp": tr["created_at"],
                "route": tr["route"],
                "player_input": tr["user_text"],
                "gm_raw": raw,
                "cues": cues,
                "combat_events": combat_by_turn.get(tn, []),
                "inventory_events": inv_events,
            }
            turns_out.append(turn_obj)
            # Only attach inventory once (for last turn batch)
            inv_rows = []

        # Human-readable text
        lines = [
            f"AI-GM DEBUG LOG | Campaign #{campaign_id} | {hero.get('name','?')} ({hero.get('archetype','?')} Poz.{hero.get('level',1)}) | {__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
            f"HP: {hero.get('hp','?')}/{hero.get('max_hp','?')} | Gold: {hero.get('gold_gp','?')} GP | Last {len(turns_out)} turns",
            "=" * 64,
        ]
        for t in turns_out:
            lines.append(f"\n[T{t['turn_number']} | id:{t['turn_id']} | {t['route']} | {t['timestamp']}]")
            pi = str(t["player_input"] or "").replace("\n", " ")
            if not pi.startswith("__AI_GM"):
                lines.append(f"GRACZ: {pi}")
            if t["cues"]:
                for k, v in t["cues"].items():
                    lines.append(f"CUE/{k.upper()}: {v}")
            for ce in t["combat_events"]:
                hit_str = "HIT" if ce.get("hit") else "MISS"
                dmg = f" dmg={ce.get('damage','?')}" if ce.get("damage") else ""
                hp = f" hp_after={ce.get('hp_after','?')}" if ce.get("hp_after") else ""
                lines.append(f"COMBAT [{ce.get('event_type','?')}] {ce.get('actor','?')} vs {ce.get('target_name','?')} roll={ce.get('roll_value','?')} {hit_str}{dmg}{hp}")
            for ie in t["inventory_events"]:
                qty = f" ×{ie['quantity']}" if ie.get("quantity", 1) > 1 else ""
                lines.append(f"ITEM+: {ie['label']}{qty} [{ie.get('item_type','?')} source:{ie['source']}]")
            if t["gm_raw"]:
                lines.append(f"GM_RAW: {t['gm_raw'][:500]}{'...' if len(t['gm_raw'])>500 else ''}")
        lines.append("\n" + "=" * 64)
        lines.append(f"HERO_STATE: {json.dumps(hero)}")

        human_text = "\n".join(lines)

        return {
            "campaign_id": campaign_id,
            "hero": hero,
            "turns": turns_out,
            "human_text": human_text,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Export session endpoint
# ---------------------------------------------------------------------------

@router.post("/campaigns/{campaign_id}/export")
def export_session(campaign_id: int):
    """Exports the full session to a .txt file under /data/exports/"""
    conn = get_db()
    try:
        get_campaign_or_404(conn, campaign_id)
        filepath = _export_session_to_file(conn, campaign_id)
        return {"status": "ok", "file": filepath}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# POST turn (non-streaming)
# ---------------------------------------------------------------------------

@router.post("/campaigns/{campaign_id}/turns")
def create_turn(
    campaign_id: int,
    payload: TurnCreate,
    x_ollama_base_url: str | None = Header(default=None),
):
    conn = get_db()
    turn_id = _start_turn_trace(campaign_id, payload.character_id, "turn")
    try:
        campaign = get_active_campaign_or_gone(conn, campaign_id)
        character = get_character_or_404(conn, campaign_id, payload.character_id)

        # E5 (#420) — block turns for dead heroes
        if ("status" in character.keys() and character["status"] == "dead"):
            raise HTTPException(
                status_code=423,
                detail="Cannot continue — hero is dead. Create a new hero to resume.",
            )

        llm_config = get_user_llm_settings_full(character["user_id"])
        text = (payload.text or "").strip()

        # F13 (#473): expire rentals whose turn window has passed before processing this turn
        try:
            from app.services.rental_service import expire_rentals, get_current_turn as _get_cur_turn
            _cur_turn = _get_cur_turn(conn, campaign_id)
            if _cur_turn > 0:
                _expired = expire_rentals(conn, campaign_id, _cur_turn)
                if _expired:
                    logger.info("rentals_expired", campaign_id=campaign_id, count=_expired)
        except Exception as _rental_err:
            logger.warning("rental_expire_error", error=str(_rental_err))

        # Special opening turn — trigger plan gen + return opening scene
        if text == "__AI_GM_OPEN":
            _require_gm_plan_before_narrative_llm(conn, campaign_id, campaign)
            _opening_turn = conn.execute(
                "SELECT assistant_text FROM campaign_turns WHERE campaign_id = ? "
                "AND (user_text = '' OR user_text IS NULL) AND route = 'narrative' LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if _opening_turn:
                return {"prose": _opening_turn["assistant_text"], "turn_number": 1,
                        "route": "narrative", "result": {"message": _opening_turn["assistant_text"]}}
            # Resolve model once for any opening-LLM paths below
            _opening_model = resolve_model_name(
                requested_model=payload.engine,
                campaign_model=campaign["model_id"],
                llm_config=llm_config,
            )
            _camp_mode_open = str(campaign["mode"] or "solo").lower()

            # Dungeon-mode campaigns: generate LLM opening using tile context
            if _camp_mode_open == "dungeon":
                try:
                    _opening_result = run_narrative_turn(
                        conn=conn,
                        campaign=campaign,
                        character=character,
                        user_text="Opisz klimatycznie komnatę w której właśnie stanąłem, wciągnij mnie w atmosferę lochu.",
                        model=_opening_model,
                        ollama_base_url=None,
                        llm_config=llm_config,
                        roll_result_message=None,
                        roll_result_data=None,
                    )
                    _opening_text = (_opening_result.get("message") or "").strip()
                    if _opening_text:
                        _nt = int((conn.execute(
                            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
                            (campaign_id,),
                        ).fetchone()[0]) or 1)
                        conn.execute(
                            "INSERT INTO campaign_turns (campaign_id, character_id, turn_number, user_text, route, assistant_text) "
                            "VALUES (?,?,?,?,?,?)",
                            (campaign_id, int(character["id"] or 0), _nt, "", "narrative", _opening_text),
                        )
                        conn.commit()
                        return {"prose": _opening_text, "turn_number": _nt,
                                "route": "narrative", "result": {"message": _opening_text}}
                except Exception as _de:
                    logger.warning("dungeon_opening_llm_failed", campaign_id=campaign_id, error=str(_de))

            # Non-dungeon fallback: opening should have been created by
            # _require_gm_plan_before_narrative_llm above. If not (LLM failure,
            # missing plan, etc.), generate one inline so the player never sees
            # a vanishing typing indicator with no message.
            try:
                from app.services.llm_service import generate_chat as _gen
                from app.system_prompt_loader import SYSTEM_PROMPT_TEXT as _OPENING_SYS
                import json as _j_open
                _sheet_open = _j_open.loads(character["sheet_json"] or "{}")
                _name_open = character["name"] or "Bohater"
                _arch_open = str(_sheet_open.get("archetype", "warrior")).lower()
                _arch_lbl = "Uczony" if _arch_open == "scholar" else "Wojownik"
                _loc_open = character["location"] or "nieznane miejsce"
                _opening_prompt = (
                    f"Postać: {_name_open}, Archetyp: {_arch_lbl}, Lokalizacja: {_loc_open}.\n\n"
                    "To jest pierwsza chwila przygody. Zacznij sesję od klimatycznego opisu miejsca, "
                    "w którym bohater się znajduje. Nie pytaj gracza o plany - po prostu opisz scenę "
                    "i zostaw otwarte zakończenie zachęcające do działania."
                )
                _opening_fb = (_gen(
                    messages=[{"role": "system", "content": _OPENING_SYS},
                              {"role": "user", "content": _opening_prompt}],
                    model=_opening_model, llm_config=llm_config,
                ) or "").strip()
                if _opening_fb:
                    _nt_fb = int((conn.execute(
                        "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
                        (campaign_id,),
                    ).fetchone()[0]) or 1)
                    conn.execute(
                        "INSERT INTO campaign_turns (campaign_id, character_id, turn_number, user_text, route, assistant_text) "
                        "VALUES (?,?,?,?,?,?)",
                        (campaign_id, int(character["id"] or 0), _nt_fb, "", "narrative", _opening_fb),
                    )
                    conn.commit()
                    logger.info("opening_scene_inline_fallback_generated", campaign_id=campaign_id)
                    return {"prose": _opening_fb, "turn_number": _nt_fb,
                            "route": "narrative", "result": {"message": _opening_fb}}
            except Exception as _fb_err:
                logger.warning("opening_inline_fallback_failed", campaign_id=campaign_id, error=str(_fb_err))

            return {"prose": None, "turn_number": 0, "route": "narrative", "result": {}}

        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        roll_request = parse_roll_command(text)
        roll_result_message = None
        roll_result_data = None
        user_text_stored = text
        if roll_request:
            if not is_slash_command_enabled("/roll"):
                raise HTTPException(
                    status_code=403,
                    detail="Komenda /roll jest wyłączona przez administratora.",
                )
            character_sheet = parse_character_sheet(character["sheet_json"])
            if roll_request.get("skill") == "death_save":
                hp_chk = _sheet_current_hp(character_sheet)
                if hp_chk is not None and hp_chk > 0:
                    logger.warning(
                        "death_save_rejected",
                        character_id=payload.character_id,
                        hp=hp_chk,
                    )
                    raise HTTPException(
                        status_code=400,
                        detail="Nieprawidłowy rzut: death_save przy HP > 0",
                    )
            if is_attack_test(roll_request.get("skill")):
                weapon_row = resolve_sheet_weapon(conn, character_sheet, int(payload.character_id))
                raw_roll = roll_request.get("raw_roll")
                roll_result = resolve_attack_roll_for_weapon(
                    character_sheet,
                    raw_roll=int(raw_roll) if raw_roll is not None else roll_d20(),
                    weapon_row=weapon_row,
                )
                roll_result["dc"] = resolve_dc_for_roll(roll_request.get("dc"))
                if roll_result["dc"] is not None:
                    roll_result["success"] = roll_result["total"] >= int(roll_result["dc"])
            else:
                roll_result = resolve_roll(
                    character_sheet=character_sheet,
                    test_name=roll_request["skill"],
                    raw_roll=roll_request.get("raw_roll"),
                    dc=resolve_dc_for_roll(roll_request.get("dc")),
                )
            roll_result_data = roll_result
            roll_result_message = format_roll_for_llm(roll_result)
            user_text_stored = ROLL_CARD_PREFIX + "\n" + json.dumps(
                build_roll_card_payload(
                    roll_result,
                    character_name=(character["name"] or "Bohater"),
                    replay_command=text.strip(),
                ),
                ensure_ascii=False,
            )

        # XS9/XS10/XS11: pending XP for successful skill check by DC range
        if (roll_result_data and roll_result_data.get("success")
                and roll_result_data.get("test") != "death_save"):
            _dc_val = roll_result_data.get("dc")
            if _dc_val and int(_dc_val) >= 12:
                try:
                    from app.services.xp_sources import grant_skill_dc_success
                    _tn9 = conn.execute(
                        "SELECT COALESCE(MAX(turn_number),1) FROM campaign_turns WHERE campaign_id=?",
                        (campaign_id,),
                    ).fetchone()[0]
                    grant_skill_dc_success(conn, int(payload.character_id), campaign_id, int(_dc_val), _tn9)
                    conn.commit()
                except Exception:
                    pass

        if roll_result_data and roll_result_data.get("test") == "death_save":
            sheet_dict = parse_character_sheet(character["sheet_json"])
            new_sheet, died_here = apply_death_save_outcome(sheet_dict, roll_result_data)
            conn.execute(
                """
                UPDATE characters SET sheet_json = ?
                WHERE id = ? AND campaign_id = ?
                """,
                (
                    json.dumps(new_sheet, ensure_ascii=False),
                    payload.character_id,
                    campaign_id,
                ),
            )
            conn.commit()
            # XS14: grant pending XP when player survives a death save
            if not died_here:
                try:
                    from app.services.xp_sources import grant_death_save_survived
                    _tn14 = conn.execute(
                        "SELECT COALESCE(MAX(turn_number),1) FROM campaign_turns WHERE campaign_id=?",
                        (campaign_id,),
                    ).fetchone()[0]
                    grant_death_save_survived(conn, int(payload.character_id), campaign_id, _tn14)
                    conn.commit()
                except Exception:
                    pass
            character = get_character_or_404(conn, campaign_id, payload.character_id)
            if died_here:
                loc = (character["location"] or "unknown place").strip()
                dr = f"Failed three death saves ({loc})"
                epitaph = end_solo_campaign_on_death(
                    conn,
                    campaign_id=campaign_id,
                    character_row=character,
                    death_reason=dr,
                )
                # J2: write history row + queue chapter summary generation
                try:
                    from app.services.chapter_summary_service import close_campaign_with_summary
                    _ch_sheet = json.loads(character["sheet_json"] or "{}")
                    _ch_xp = int(_ch_sheet.get("xp_lifetime_earned") or 0)
                    _ch_gold = int(_ch_sheet.get("gold_gp") or _ch_sheet.get("gold") or 0)
                    _ch_turns = conn.execute(
                        "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ? AND route = 'narrative'",
                        (campaign_id,),
                    ).fetchone()[0]
                    close_campaign_with_summary(
                        conn,
                        campaign_id=campaign_id,
                        character_id=int(payload.character_id),
                        outcome="death",
                        user_id=int(character["user_id"]),
                        xp_earned=_ch_xp,
                        gold_at_end=_ch_gold,
                        turns_count=int(_ch_turns or 0),
                    )
                except Exception as _j2_err:
                    logger.warning("j2_death_history_failed", error=str(_j2_err))
                user_line = user_text_stored if roll_request else (roll_result_message or text)
                log = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=user_line,
                    assistant_text=epitaph,
                    route="narrative",
                )
                log_narrative_turn_structured(
                    route="narrative",
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    turn_row=log,
                    user_text=user_line,
                    assistant_text=epitaph,
                )
                return {
                    "id": log["id"],
                    "campaign_id": log["campaign_id"],
                    "turn_number": log["turn_number"],
                    "created_at": log["created_at"],
                    "route": "narrative",
                    "result": {"message": epitaph},
                    "campaign_ended": True,
                    "turn_id": turn_id,
                }

        if text.startswith("/") and not roll_request:
            route = "command"
            cmd = text.split(" ", 1)[0].lower()
            _is_admin_user = False
            try:
                _u_row = conn.execute(
                    "SELECT COALESCE(is_admin, 0) AS is_admin FROM users WHERE id = ? LIMIT 1",
                    (character["user_id"],),
                ).fetchone()
                _is_admin_user = bool(_u_row and int(_u_row["is_admin"] or 0))
            except Exception:
                pass
            sk_dispatch = slash_registry_key_for_dispatch(text, is_admin=_is_admin_user)
            # Alias support: rewrite cmd + text to canonical first-token so the
            # per-command branches below (cmd == '/mem', etc.) match. The user's
            # original text remains in user_text for logging.
            if sk_dispatch:
                _canon = sk_dispatch.split(" ", 1)[0].lower()
                if _canon != cmd:
                    rest = text[len(cmd):]
                    text = _canon + rest
                    cmd = _canon
            if (
                sk_dispatch
                and not is_slash_command_enabled(sk_dispatch)
                and cmd not in ("/atak", "/walka")
            ):
                token = sk_dispatch.split()[0].lstrip("/") or "cmd"
                result = {
                    "command": token,
                    "disabled": True,
                    "message": "Ta komenda została wyłączona przez administratora.",
                }
                log = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=text,
                    assistant_text=json.dumps(result, ensure_ascii=False),
                    route=route,
                )
                return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)

            # /help
            if cmd == "/help":
                result = {
                    "command": "help",
                    "commands": get_public_help_command_texts(),
                }
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)

            # /name
            if cmd == "/name":
                new_name = text[5:].strip()
                if not new_name:
                    raise HTTPException(status_code=400, detail="Character name is required")
                conn.execute(
                    "UPDATE characters SET name = ? WHERE id = ? AND campaign_id = ?",
                    (new_name, payload.character_id, campaign_id),
                )
                conn.commit()
                result = {"command": "name", "character_name": new_name}
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)

            # /quest, /export, /move — handled by turn_commands module
            _tc_result = _handle_turn_command(
                conn=conn,
                campaign_id=campaign_id,
                character_id=payload.character_id,
                text=text,
                cmd=cmd,
                turn_id=turn_id,
                create_turn_log=create_turn_log,
                _with_turn_trace=_with_turn_trace,
            )
            if _tc_result is not None:
                return _tc_result

            # /sheet
            if cmd == "/sheet":
                result = {
                    "command": "sheet",
                    "character": {
                        "id": character["id"],
                        "name": character["name"],
                        "campaign_id": character["campaign_id"],
                        "user_id": character["user_id"],
                        "system_id": character["system_id"],
                        "sheet_json": character["sheet_json"],
                        "location": character["location"],
                        "is_active": character["is_active"],
                        "created_at": character["created_at"],
                    },
                }
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)

            # /history
            if cmd == "/history":
                rows = conn.execute(
                    """
                    SELECT turn_number, user_text, assistant_text, created_at
                    FROM campaign_turns
                    WHERE campaign_id = ?
                    ORDER BY turn_number DESC
                    LIMIT 10
                    """,
                    (campaign_id,),
                ).fetchall()
                history = [
                    {
                        "turn": r["turn_number"],
                        "player": r["user_text"],
                        "gm": r["assistant_text"],
                        "at": r["created_at"],
                    }
                    for r in reversed(rows)
                ]
                result = {"command": "history", "turns": history}
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)

            # /helpme — OOC advisor (route=helpme; nie wchodzi do kontekstu narracji)
            if cmd == "/helpme":
                topic = re.sub(r"^/helpme\s*", "", text, count=1, flags=re.I).strip()
                owner_id = int(campaign["owner_user_id"])
                llm_owner = get_user_llm_settings_full(owner_id)
                model_h = resolve_model_name(
                    requested_model=payload.engine,
                    campaign_model=campaign["model_id"],
                    llm_config=llm_owner,
                )
                try:
                    out = run_helpme_advisor(
                        conn=conn,
                        campaign=campaign,
                        character=character,
                        topic=topic,
                        user_id=owner_id,
                        model=model_h,
                    )
                except RuntimeError as e:
                    raise HTTPException(status_code=502, detail=str(e)) from None
                msg = (out.get("message") or "").strip()
                if not msg:
                    raise HTTPException(status_code=502, detail="Empty /helpme response")
                log = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=text.strip(),
                    assistant_text=msg,
                    route="helpme",
                )
                return {
                    "id": log["id"],
                    "campaign_id": log["campaign_id"],
                    "turn_number": log["turn_number"],
                    "created_at": log["created_at"],
                    "route": "helpme",
                    "ooc": True,
                    "result": {"message": msg},
                    "turn_id": turn_id,
                }

            # /atak — stan silnika walki; /walka pozostaje aliasem (to samo zachowanie)
            if cmd in ("/atak", "/walka"):
                result = _atak_command_response_for_api(campaign_id)
                log = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=text,
                    assistant_text=json.dumps(result, ensure_ascii=False),
                    route=route,
                )
                return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)

            # Unknown command
            result = {"command": cmd, "message": f"Unknown command '{cmd}'. Type /help for a list."}
            log = create_turn_log(
                conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
            )
            return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)

        _require_gm_plan_before_narrative_llm(conn, campaign_id, campaign)

        _skill_pending_narrator = None  # set if narrator embeds [SKILL_TEST]/[TRAP] tag

        # ── Skill routing (R1.2 — #872) ─────────────────────────────────────
        _skill_result = _route_skill_turn(
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            text=text,
            turn_id=turn_id,
            character=character,
            llm_config=llm_config,
            create_turn_log=create_turn_log,
            _with_turn_trace=_with_turn_trace,
            _normalize_pl=_normalize_pl,
            _kw_matches=_kw_matches,
            _text_is_action_attempt=_text_is_action_attempt,
            _is_reading_context=_is_reading_context,
            _is_compound_action=_is_compound_action,
        )
        if _skill_result is not None:
            return _skill_result

        route = "narrative"
        model = resolve_model_name(
            requested_model=payload.engine,
            campaign_model=campaign["model_id"],
            llm_config=llm_config,
        )

        blocked_turn = _maybe_handle_blocked_player_combat_turn(
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            user_text=user_text_stored if roll_request else text,
            turn_id=turn_id,
        )
        if blocked_turn is not None:
            return blocked_turn

        # ── T33: Structured action bypass — convert button-click payload to ACTION tag ──
        narrative_text = text
        if payload.input_type == "structured" and not roll_request:
            narrative_text = _structured_action_to_tag(text)
            logger.info("structured_action_converted", original=text, converted=narrative_text)

        # ── B3: Gate Mechanic — validate against World State before LLM ─────
        _gate_blocked_response = _check_gate_and_record(
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            narrative_text=narrative_text,
            roll_request=roll_request,
            turn_id=turn_id,
            record_turn_decision_fn=_record_turn_decision_safe,
            with_turn_trace_fn=_with_turn_trace,
        )
        if _gate_blocked_response is not None:
            return _gate_blocked_response

        # ── U7: detect risky intent before LLM ───────────────────────────────
        _risky_intent_match = _detect_risky_intent_turn(conn, narrative_text, roll_request)

        # U30 (#578): directional-move fast-path on the JSON tor — parity with
        # create_turn_stream. Resolve travel mechanically BEFORE the LLM so "idę na północ"
        # moves the hex here too (not only in the streaming player UI).
        _u30_move_executed = False
        _u30_system_fact = None
        if not roll_request:
            try:
                from app.services.turn_pipeline import execute_directional_travel as _u30_exec
                _u30_res = _u30_exec(
                    conn, campaign_id, payload.character_id,
                    json.loads(character["sheet_json"] or "{}"), narrative_text,
                )
                _u30_move_executed = bool(_u30_res.get("executed"))
                _u30_system_fact = _u30_res.get("system_fact")
            except Exception as _u30_err:
                logger.warning("u30_directional_fastpath_error", error=str(_u30_err), campaign_id=campaign_id)

        result = run_narrative_turn(
            conn=conn,
            campaign=campaign,
            character=character,
            user_text=narrative_text,
            model=model,
            ollama_base_url=x_ollama_base_url,
            llm_config=llm_config,
            roll_result_message=roll_result_message,
            roll_result_data=roll_result_data,
            extra_system=_u30_system_fact,
        )

        assistant_text = (result.get("message") or "").strip()
        if not assistant_text:
            raise HTTPException(status_code=500, detail="Empty narrative response")

        # Snapshot hex before location intent (for hex_enter encounter trigger)
        _hex_before_enc = _snapshot_hex(conn, campaign_id)

        assistant_text = _process_location_intent(
            conn=conn,
            campaign_id=campaign_id,
            assistant_response=assistant_text,
        )

        # Hex-enter encounter trigger: fire when current_hex changed
        _check_hex_enter_trigger(conn, campaign_id, _hex_before_enc)

        # ── [SKILL_TEST:] / [TRAP:] tag interception (R1.4 — #874) ─────────────
        _char_sh = json.loads(character["sheet_json"] or "{}")
        assistant_text, _skill_pending_narrator = _intercept_narrator_skill_tags(
            assistant_text=assistant_text,
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            character_sheet=_char_sh,
        )

        # ── U7: safety net — force skill test if risky intent + LLM omitted tag ──
        _u7_forced = _apply_u7_safety_net(
            conn=conn,
            campaign_id=campaign_id,
            character=character,
            assistant_text=assistant_text,
            risky_intent_match=_risky_intent_match,
            skill_pending_narrator=_skill_pending_narrator,
            commit_pending_skill_test_fn=_commit_pending_skill_test,
        )
        if _u7_forced is not None:
            _skill_pending_narrator = _u7_forced

        from app.services import combat_service as _cs

        combat_before = _cs.get_active_combat(campaign_id)
        combat_was_active = bool(combat_before) and str(
            combat_before.get("current_turn") or ""
        ) == "player"

        clean_assistant = COMBAT_START_RE.sub("", assistant_text).rstrip()
        # [DUNGEON_CLEAR:key] — strip tag and record completion
        _dungeon_clear_result = _handle_dungeon_clear_tag(campaign_id, payload.character_id, clean_assistant)
        clean_assistant = DUNGEON_CLEAR_RE.sub("", clean_assistant).rstrip()
        # Stage 3 Z4 — [APPLY_CONDITION:zaskoczony:enemy_key] from stealth-success narration
        try:
            from app.services.combat_service import apply_condition_to_combatant
            from app.services.llm_tag_parser import (
                get_rejection_correction as _ac_corr,
                log_tag_error as _ac_lte,
            )
            _ac_invalid = False
            for _ac in APPLY_CONDITION_RE.finditer(clean_assistant):
                _cond_key = _ac.group(1).strip()
                _enemy_ref = _ac.group(2).strip()
                _ac_res = apply_condition_to_combatant(campaign_id, _enemy_ref, _cond_key)
                logger.info("apply_condition_tag", campaign_id=campaign_id,
                            condition=_cond_key, enemy_ref=_enemy_ref, result=_ac_res)
                # S8 (#603): nieznany klucz kondycji → invalid_reference (U5/U6)
                if isinstance(_ac_res, dict) and _ac_res.get("reason") == "invalid_reference":
                    _ac_invalid = True
                    _ac_tn = conn.execute(
                        "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
                        (campaign_id,),
                    ).fetchone()[0]
                    _ac_lte(conn, campaign_id, _ac_tn, _ac.group(0), "invalid_reference")
            clean_assistant = APPLY_CONDITION_RE.sub("", clean_assistant).rstrip()
            if _ac_invalid:
                _ac_fix = _ac_corr("APPLY_CONDITION")
                if _ac_fix:
                    _ac_narr, _ac_pjson = _extract_narrative_for_cues(clean_assistant)
                    clean_assistant = _repack_narrative(
                        clean_assistant, _ac_narr.rstrip() + "\n\n" + _ac_fix, _ac_pjson)
        except Exception as _ac_err:
            logger.warning("apply_condition_tag_error", error=str(_ac_err))
            clean_assistant = APPLY_CONDITION_RE.sub("", clean_assistant).rstrip()
        clean_assistant = maybe_append_open_shop_fallback(conn, campaign_id, text, clean_assistant)
        _narrative_for_cues, _parsed_json = _extract_narrative_for_cues(clean_assistant)
        (
            _narrative_for_cues,
            grant_item_labels,
            grant_gold_amount,
            open_shop_npc_key,
            grant_item_descriptions,
        ) = extract_grant_cues(_narrative_for_cues)
        # Also check top-level grant_item in parsed JSON — extract_grant_cues only sees
        # the plain narrative text and can't find fields in the outer JSON object.
        if isinstance(_parsed_json, dict):
            _raw_gi_json = _parsed_json.get("grant_item")
            _entries_json: list = (_raw_gi_json if isinstance(_raw_gi_json, list) else [_raw_gi_json]) if _raw_gi_json else []
            for _x in _entries_json:
                _entry = _parse_grant_item_entry(_x)
                if _entry and _entry[0] not in grant_item_labels:
                    grant_item_labels.append(_entry[0])
                    grant_item_descriptions[_entry[0]] = _entry[1]
        grant_item_label = grant_item_labels[0] if grant_item_labels else None  # compat
        clean_assistant = _repack_narrative(clean_assistant, _narrative_for_cues, _parsed_json)
        # Inject _debug into assistant JSON for frontend debug block
        _mr = result.get("mechanic_result") if isinstance(result, dict) else None
        if _mr and isinstance(_mr, dict):
            try:
                _dbg_payload = {k: _mr[k] for k in ("roll", "total", "dc", "outcome", "action_type") if k in _mr}
                _ca_parsed = json.loads(_strip_json_code_fence(clean_assistant))
                if isinstance(_ca_parsed, dict):
                    _ca_parsed["_debug"] = _dbg_payload
                    clean_assistant = json.dumps(_ca_parsed, ensure_ascii=False)
            except Exception:
                pass
        validate_roll_cue_name(clean_assistant.strip())

        # ── roll_cue skill test intercept ─────────────────────────────────────
        # When narrator emits roll_cue:"Roll Arcana d20" (not an attack), convert
        # it to skill_test_pending so the Roll Popup appears.
        # Issue #53 fix 3: when LLM emits plain text (no JSON envelope), scan the
        # narrative tail for a trailing "Roll <skill> d20" line — same intercept
        # path, just sourced from raw text instead of the parsed JSON field.
        # K2 guard: suppress LLM-emitted roll_cue when player asked a question —
        # questions cannot be action attempts even if the LLM hallucinates a roll.
        _raw_cue = ""
        if _text_is_action_attempt(text) and _parsed_json and not _skill_pending_narrator:
            _raw_cue = str(_parsed_json.get("roll_cue") or "").strip()
        elif not _parsed_json and not _skill_pending_narrator:
            import re as _rc_re_pre
            _tail_text = (clean_assistant or "").rstrip()
            # Take the last non-empty line and check if it matches Roll <skill> d20
            for _line in reversed(_tail_text.splitlines()):
                _line_s = _line.strip()
                if not _line_s:
                    continue
                if _rc_re_pre.match(r"^Roll\s+.+?\s+d\d+$", _line_s, _rc_re_pre.IGNORECASE):
                    _raw_cue = _line_s
                    logger.info("roll_cue_plain_text_fallback", cue=_raw_cue)
                break  # only inspect the last non-empty line
        if (_parsed_json or _raw_cue) and not _skill_pending_narrator:
            if _raw_cue:
                import re as _rc_re
                _cm = _rc_re.match(r"^Roll (.+?) d\d+$", _raw_cue, _rc_re.IGNORECASE)
                if _cm:
                    _cue_name = _cm.group(1).strip()
                    _canonical = resolve_test_name(_cue_name)
                    # Fallback 1: custom skill by exact key match
                    if _canonical is None:
                        _norm_cue = _cue_name.lower().replace(" ", "_")
                        try:
                            _cue_db = conn.execute(
                                "SELECT key FROM game_config_skills WHERE key = ? LIMIT 1",
                                (_norm_cue,),
                            ).fetchone()
                            if _cue_db:
                                _canonical = _norm_cue
                        except Exception:
                            pass
                    # Fallback 2: check trigger_keywords — admin-defined keywords that
                    # deterministically override whatever skill the LLM picked.
                    # Both player text and keywords are normalized to ASCII so that
                    # Polish chars (ń→n, ć→c, ę→e, ó→o, ą→a, ł→l, ś→s, ź/ż→z) match.
                    try:
                        _txt_norm = _normalize_pl(text or "")
                        # Same combat-class exclusion as the pre-LLM scan above.
                        _kw_rows = conn.execute(
                            "SELECT key, trigger_keywords FROM game_config_skills "
                            "WHERE trigger_keywords IS NOT NULL AND trigger_keywords != '' "
                            "AND key NOT IN ('attack', 'ranged_attack', 'two_handed', 'melee_attack', 'spell_attack', 'initiative')"
                        ).fetchall()
                        for _kr in _kw_rows:
                            _raw_kws = (_kr["trigger_keywords"] or "").replace(",", " ")
                            # K2 fix: exact word boundary, same as pre-LLM scanner
                            _kws = [k.strip().lower().translate(_PL_NORMALIZE)
                                    for k in _raw_kws.split()
                                    if k.strip() and len(k.strip()) >= 5]
                            if any(_kw_matches(kw, _txt_norm) for kw in _kws):
                                _canonical = _kr["key"]
                                break
                    except Exception as _kw_err:
                        logger.warning("trigger_keywords_error: %s", str(_kw_err))
                    logger.info("skill_test_canonical_resolved",
                                cue=_cue_name, canonical=_canonical, txt_norm=_txt_norm[:40])
                    if _canonical and not is_attack_test(_canonical) and not _is_combat_class_skill(_canonical):
                        # It's a non-combat skill — show Roll Popup. Combat-class
                        # skills (attack/ranged_attack/two_handed/...) skip this path;
                        # they belong in real combat resolution, not phantom skill tests.
                        from app.services.skill_service import calc_skill_modifier_info, _skill_label, _get_counter
                        import uuid as _uuid3
                        _char_sh2 = json.loads(character["sheet_json"] or "{}")
                        _sk2 = _canonical
                        _skill_pending_narrator = {
                            "skill_test_id": f"st-{_uuid3.uuid4().hex[:8]}",
                            "skill_key": _sk2,
                            "skill_label": _skill_label(_sk2),
                            "counter": _get_counter(conn, _sk2),
                            "modifier_breakdown": calc_skill_modifier_info(_char_sh2, _sk2),
                        }
                        # Store in session
                        try:
                            _gs3 = conn.execute(
                                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                                (campaign_id,),
                            ).fetchone()
                            if _gs3:
                                _sf3 = json.loads(_gs3["session_flags"] or "{}")
                                _sf3 = _commit_pending_skill_test(_skill_pending_narrator, _sf3)
                                conn.execute(
                                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                                    (json.dumps(_sf3, ensure_ascii=False), campaign_id),
                                )
                                conn.commit()
                        except Exception as _e3:
                            logger.warning("roll_cue_session_store_error: %s", str(_e3))

        # T10: Process [CREATE_LOCATION/NPC/ENEMY] tags → pending_review queue
        try:
            process_create_tags(assistant_text or "", conn, campaign_id)
        except Exception as _pct_err:
            logger.warning("process_create_tags_error", error=str(_pct_err))

        # XS1/XS2-XS8/XS12/XS15/XS6: narrative tag XP sources
        try:
            import re as _xs_re
            from app.services.xp_sources import (
                process_narrative_xp_tags,
                grant_first_location_visit,
                grant_first_npc_talk,
                grant_session_start,
                grant_beat_complete,
            )
            from app.services.narrative_state_service import strip_narrative_tags
            _xp_char_id = int(payload.character_id)
            _xp_turn = conn.execute(
                "SELECT COALESCE(MAX(turn_number),1) FROM campaign_turns WHERE campaign_id=?",
                (campaign_id,),
            ).fetchone()[0]
            _xp_total = 0
            # XS15: session start bonus — checked before this turn is written
            _xp_total += grant_session_start(conn, _xp_char_id, campaign_id, _xp_turn)
            # XS6: first NPC dialogue
            _dlg_m = _xs_re.match(r"^DIALOGUE:(.+)$", text.strip(), _xs_re.I)
            if _dlg_m:
                _xp_total += grant_first_npc_talk(
                    conn, _xp_char_id, campaign_id, _dlg_m.group(1).strip(), _xp_turn
                )
            # XS1: [BEAT_COMPLETE:key] tag in narrative
            for _bm in _xs_re.finditer(r"\[BEAT_COMPLETE:\s*([^\]\s]+)\s*\]", assistant_text or "", _xs_re.I):
                _xp_total += grant_beat_complete(conn, _xp_char_id, campaign_id, _bm.group(1), _xp_turn)
            # E6 (#421): [ARC_ADVANCE:key] tag — jump the active GM-plan arc
            try:
                from app.services.campaign_plan_runtime import parse_arc_advance_tags as _paat, advance_arc as _adv_arc
                for _arc_key in _paat(assistant_text or ""):
                    _adv_arc(campaign_id, _arc_key, conn)
            except Exception as _arc_err:
                logger.warning("arc_advance_error", error=str(_arc_err))
            # XS2-XS4/XS7-XS8/XS12: bulk narrative tag parser
            _tag_r = process_narrative_xp_tags(
                assistant_text or "", conn, _xp_char_id, campaign_id, _xp_turn
            )
            _xp_total += _tag_r["total_granted"]
            # XS5: first macro-location visit
            _loc_r5 = conn.execute(
                "SELECT gl.key FROM game_sessions gs "
                "JOIN game_locations gl ON gl.id = gs.current_location_id "
                "WHERE gs.campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if _loc_r5:
                _xp_total += grant_first_location_visit(
                    conn, _xp_char_id, campaign_id, _loc_r5["key"], _xp_turn
                )
            # HF-11 (#553): talk_to_npc beat auto-complete in the live narrative tor
            # (process_v2_turn's DIALOGUE hook is never reached). Detect NPC engagement
            # from the button DIALOGUE key or a free-text scene-NPC keyword match.
            try:
                from app.services.campaign_plan_runtime import auto_complete_talk_to_npc
                _dlg_key = _dlg_m.group(1).strip() if _dlg_m else None
                _loc_key_for_beat = _loc_r5["key"] if _loc_r5 else None
                auto_complete_talk_to_npc(
                    campaign_id, text, _loc_key_for_beat, _dlg_key, _xp_turn, conn
                )
            except Exception as _b11_err:
                logger.warning("talk_beat_autocomplete_error", error=str(_b11_err))
            if _xp_total:
                conn.commit()
        except Exception as _xs_err:
            logger.warning("narrative_xp_hooks_error", error=str(_xs_err))

        # Strip GM-only directive tags from player-visible text after XP processing
        try:
            from app.services.narrative_state_service import strip_narrative_tags as _strip_tags
            _narrative_part, _parsed_part = _extract_narrative_for_cues(clean_assistant)
            _stripped = _strip_tags(_narrative_part)
            clean_assistant = _repack_narrative(clean_assistant, _stripped, _parsed_part)
        except Exception as _strip_err:
            logger.warning("narrative_tag_strip_error", error=str(_strip_err))

        # U30.4 (#578): anti-desync guard — flag when the narrator claims travel but no
        # mechanical move happened this turn. Records `travel_narrated_without_move`.
        try:
            from app.services.turn_pipeline import guard_travel_desync as _u30_guard
            _u30_guard_narr, _ = _extract_narrative_for_cues(clean_assistant)
            _u30_guard_turn = conn.execute(
                "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
                (campaign_id,),
            ).fetchone()[0]
            _u30_guard(conn, campaign_id, _u30_guard_narr, _u30_move_executed, _u30_guard_turn)
        except Exception as _u30_guard_err:
            logger.warning("u30_desync_guard_error", error=str(_u30_guard_err))

        # C10: parse QUEST_SUGGEST tags → active_quests, strip from narrative (non-streaming path)
        try:
            from app.services.quest_suggest_parser import parse_quest_suggest as _pqs_ns, strip_quest_suggest_tags as _sqs_ns
            from app.services.world_state_service import get_world_state_flags as _gwsf_ns, set_world_state_flags as _swsf_ns
            from app.services.quest_persist_service import persist_quest_to_character_quests as _pqdb_ns
            _narr_qs_ns, _pjson_qs_ns = _extract_narrative_for_cues(clean_assistant)
            _new_quests_ns = _pqs_ns(_narr_qs_ns)
            if _new_quests_ns:
                _existing_ns = _gwsf_ns(campaign_id).get("active_quests", [])
                _seen_ns = {q.get("title", "") for q in _existing_ns}
                _to_add_ns = [q for q in _new_quests_ns if q["title"] not in _seen_ns]
                if _to_add_ns:
                    _swsf_ns(campaign_id, active_quests=_existing_ns + _to_add_ns)
                    # HF-2: persist to character_quests for /quest command and stats
                    for _q_ns in _to_add_ns:
                        _pqdb_ns(conn, character_id=payload.character_id, campaign_id=campaign_id, quest=_q_ns)
            clean_assistant = _repack_narrative(clean_assistant, _sqs_ns(_narr_qs_ns), _pjson_qs_ns)
        except Exception as _qse_ns:
            logger.warning("quest_suggest_nonstream_error", error=str(_qse_ns))

        # C12/F4: parse [SPEND_GOLD:key] → deduct gold or inject refusal text
        try:
            from app.services.spend_gold_service import apply_spend_gold_to_narrative as _apply_sg_ns
            _sg_ns_narr, _sg_ns_pjson = _extract_narrative_for_cues(clean_assistant)
            _sg_ns_clean = _apply_sg_ns(_sg_ns_narr, conn, payload.character_id)
            clean_assistant = _repack_narrative(clean_assistant, _sg_ns_clean, _sg_ns_pjson)
        except Exception as _sg_ns_err:
            logger.warning("spend_gold_nonstream_error", error=str(_sg_ns_err))

        # U6 (#530): pre-check grant_item_labels — items going to pending get narration correction
        try:
            from app.services.llm_tag_parser import (
                get_rejection_correction as _u6_corr,
                log_tag_error as _u6_lte,
                save_rejected_tags as _u6_srt,
                clear_rejected_tags as _u6_crt,
                find_unknown_tags as _u6_fut,
            )
            _u6_turn_n = conn.execute(
                "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
                (campaign_id,),
            ).fetchone()[0]
            _u6_rejected: list = []
            # Decision 2026-06-12 (Piotr): pending-item flow is ACCEPTED behaviour
            # (item reaches inventory, admin reviews later) — NOT a tag error.
            # No llm_tag_errors entry, no last_rejected_tags signal to the LLM.
            # Narration correction only for trivial junk (a quest key must stay uncorrected).
            for _u6_gil in grant_item_labels:
                _u6_resolved = _resolve_grant_catalog_item(conn, _u6_gil)
                if not _u6_resolved and not _is_weapon_label(_u6_gil) \
                        and _is_trivial_item_label(_u6_gil):
                    _u6_fix = _u6_corr("GRANT_ITEM")
                    if _u6_fix:
                        # Append correction inside the narrative field (not the raw JSON wrapper)
                        _u6_narr, _u6_pjson = _extract_narrative_for_cues(clean_assistant)
                        _u6_narr_fixed = _u6_narr.rstrip() + "\n\n" + _u6_fix
                        clean_assistant = _repack_narrative(clean_assistant, _u6_narr_fixed, _u6_pjson)
            for _u6_utag in _u6_fut(clean_assistant):
                _u6_lte(conn, campaign_id, _u6_turn_n, _u6_utag, "unknown_tag")
                _u6_rejected.append(f"unknown:{_u6_utag}")
            conn.commit()
            if _u6_rejected:
                _u6_srt(conn, campaign_id, _u6_rejected)
            else:
                _u6_crt(conn, campaign_id)
        except Exception as _u6_err:
            logger.warning("u6_rejection_correction_error", error=str(_u6_err))

        log = _persist_narrative_turn(
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            user_text=user_text_stored if roll_request else text,
            assistant_text=clean_assistant,
            route=route,
            create_turn_log_fn=create_turn_log,
            log_narrative_fn=log_narrative_turn_structured,
        )
        for _gil in grant_item_labels:
            _gil_desc = grant_item_descriptions.get(_gil)
            _resolved = _resolve_grant_catalog_item(conn, _gil)
            if _resolved:
                from app.services.loot_service import grant_loot_to_character
                grant_loot_to_character(int(payload.character_id),
                                        [{"item_key": _resolved["item_key"], "quantity": 1}],
                                        source="gm_grant_item")
                logger.info("grant_item_catalog", character_id=payload.character_id,
                            item_key=_resolved["item_key"], label=_gil)
            elif _is_weapon_label(_gil):
                _grant_narrative_weapon(conn, campaign_id=campaign_id,
                                        character_id=payload.character_id, label=_gil, source="gm")
            else:
                # D1 (#376) — unknown item → pending_review catalog entry + admin queue
                _grant_pending_item(conn, campaign_id=campaign_id,
                                    character_id=payload.character_id,
                                    label=_gil, source="gm", description=_gil_desc)
        if grant_item_labels:
            conn.commit()
            from app.services.event_logger import write_game_event as _wge_j
            for _ge_lbl_j in grant_item_labels:
                try:
                    _wge_j("item_grant", campaign_id, payload.character_id,
                           character.get("user_id"),
                           {"item_label": _ge_lbl_j, "source": "gm_grant_item"},
                           conn=conn)
                    conn.commit()
                except Exception:
                    pass
        if grant_gold_amount is not None:
            new_total = apply_grant_gold_to_character(
                conn,
                character_id=payload.character_id,
                amount=grant_gold_amount,
            )
            conn.commit()
            logger.info(
                "grant_gold_applied",
                campaign_id=campaign_id,
                character_id=payload.character_id,
                amount=grant_gold_amount,
                new_total_gp=new_total,
            )
            try:
                from app.services.event_logger import write_game_event as _wge_j2
                _wge_j2("gold_grant", campaign_id, payload.character_id,
                        character.get("user_id"),
                        {"amount": grant_gold_amount, "new_total_gp": new_total},
                        conn=conn)
                conn.commit()
            except Exception:
                pass

        # N-turns encounter trigger: every 5 peaceful turns since last combat
        try:
            # D7 (#382) — interwał z configu (admin3-editable), default 20 (był 5 — za często).
            try:
                from app.services.encounter_config_service import get_encounter_config as _get_enc_cfg
                _n_turns_interval = int(_get_enc_cfg().get("n_turns_interval", 20))
            except Exception:
                _n_turns_interval = 20
            _last_combat_turn = conn.execute(
                "SELECT COALESCE(MAX(turn_number), 0) FROM campaign_turns WHERE campaign_id=? AND route='combat'",
                (campaign_id,),
            ).fetchone()[0]
            _peaceful_since = conn.execute(
                "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id=? AND turn_number > ? AND route != 'combat'",
                (campaign_id, _last_combat_turn),
            ).fetchone()[0]
            if _peaceful_since > 0 and _peaceful_since % _n_turns_interval == 0:
                from app.services.encounter_service import maybe_inject_encounter as _mie2
                _gs_nturn = conn.execute(
                    "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1", (campaign_id,)
                ).fetchone()
                if _gs_nturn:
                    _sf_nturn = json.loads(_gs_nturn["session_flags"] or "{}")
                    _hex_nturn = _sf_nturn.get("current_hex")
                    _mie2(
                        conn, campaign_id, "n_turns",
                        q=int(_hex_nturn.get("q", 0)) if _hex_nturn else None,
                        r=int(_hex_nturn.get("r", 0)) if _hex_nturn else None,
                    )
        except Exception as _n_enc_err:
            logger.warning("n_turns_encounter_trigger_error", error=str(_n_enc_err))

        # F8 (#468) + U24 (#574): robbery counterplay — kara z możliwością reakcji.
        #   Tura 1 (warning): sygnał ostrzegawczy w narracji, złoto nietknięte.
        #   Tura 2 (defense): rzut obronny d20+stat vs DC wg poziomu; sukces = brak
        #   straty, porażka = 20% (apply_robbery). Sukces LUB porażka konsumuje
        #   limit 1/24h (record_robbery_trigger). Próg biedy i limit 24h egzekwuje
        #   iniekcja (encounter_service) — tu rozstrzygamy już dopuszczony napad.
        try:
            from app.services.robbery_service import (
                is_robbery_encounter, apply_robbery as _apply_rob,
                robbery_defense_dc, roll_robbery_defense, record_robbery_trigger,
                DEFAULT_DEFENSE_STAT,
            )
            _gs_rob = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1", (campaign_id,)
            ).fetchone()
            if _gs_rob:
                _sf_rob = json.loads(_gs_rob["session_flags"] or "{}")
                _enc_rob = _sf_rob.get("active_encounter")
                if is_robbery_encounter(_enc_rob):
                    if str(_enc_rob.get("robbery_state") or "") != "warned":
                        # ── Tura ostrzeżenia: zasiej sygnał, NIE zabieraj złota ──
                        _enc_rob["robbery_state"] = "warned"
                        _sf_rob["active_encounter"] = _enc_rob
                        conn.execute(
                            "UPDATE game_sessions SET session_flags=? WHERE campaign_id=?",
                            (json.dumps(_sf_rob, ensure_ascii=False), campaign_id),
                        )
                        conn.commit()
                        _warn_hint = (
                            "Masz nieprzyjemne wrażenie, że ktoś cię obserwuje — "
                            "w tłumie/cieniu czai się ktoś, kto wypatruje twojej sakiewki. "
                            "Bądź czujny w następnej chwili."
                        )
                        clean_assistant = (clean_assistant or "") + f"\n\n*{_warn_hint}*"
                        logger.info("robbery_warning_emitted", campaign_id=campaign_id,
                                    char_id=payload.character_id)
                    else:
                        # ── Tura rozstrzygnięcia: rzut obronny ──
                        _stat = str(_enc_rob.get("defense_stat") or DEFAULT_DEFENSE_STAT)
                        _lvl = 1
                        try:
                            _ch_row = conn.execute(
                                "SELECT sheet_json FROM characters WHERE id=?", (payload.character_id,)
                            ).fetchone()
                            if _ch_row:
                                _lvl = max(1, int((json.loads(_ch_row["sheet_json"] or "{}")).get("level") or 1))
                        except Exception:
                            _lvl = 1
                        _dc = robbery_defense_dc(_lvl)
                        _def = roll_robbery_defense(conn, payload.character_id, _stat, _dc)
                        _sf_rob.pop("active_encounter", None)
                        record_robbery_trigger(_sf_rob)  # konsumuje limit 1/24h
                        if _def["success"]:
                            _rob_result = {"ok": True, "defended": True, "defense": _def}
                            _rob_hint = (
                                f"Zauważyłeś zagrożenie w porę ({_stat} {_def['total']} ≥ {_dc}) "
                                f"i udało ci się uniknąć napadu — twoja sakiewka jest bezpieczna."
                            )
                        else:
                            _steal = _apply_rob(conn, payload.character_id)
                            _rob_result = {"ok": True, "defended": False, "defense": _def, "steal": _steal}
                            _rob_hint = _steal.get("narrative_hint", "") if _steal.get("ok") else ""
                        conn.execute(
                            "UPDATE game_sessions SET session_flags=? WHERE campaign_id=?",
                            (json.dumps(_sf_rob, ensure_ascii=False), campaign_id),
                        )
                        conn.commit()
                        if _rob_hint:
                            clean_assistant = (clean_assistant or "") + f"\n\n*{_rob_hint}*"
                        logger.info("robbery_encounter_resolved", campaign_id=campaign_id,
                                    char_id=payload.character_id, result=_rob_result)
        except Exception as _rob_err:
            logger.warning("robbery_encounter_error", error=str(_rob_err))

        # Issue #135 — inject [COMBAT_START] when player declared attack but
        # LLM omitted the tag. Keeps combat engine engaged in Polish narrative mode.
        assistant_text = _ensure_combat_start_tag(conn, campaign_id, text, assistant_text)

        new_combat = _maybe_start_combat_from_gm_tag(
            campaign_id, payload.character_id, assistant_text,
            turn_log_id=log.get("id") if log else None,
            turn_number=log.get("turn_number", 0) if log else 0,
        )
        combat_extra = None
        if combat_was_active and not new_combat:
            combat_extra = _maybe_advance_combat_after_player_narrative(campaign_id)

        # Extract travel_hint from JSON field (preferred) or legacy [TRAVEL_HINT:] tag
        import re as _re
        _travel_hint_label: str | None = None
        if isinstance(_parsed_json, dict):
            _th = _parsed_json.get("travel_hint")
            if _th and isinstance(_th, str):
                _travel_hint_label = _th.strip()
        if not _travel_hint_label:
            _travel_hint_match = _re.search(r'\[TRAVEL_HINT:([^\]]+)\]', clean_assistant or '')
            if _travel_hint_match:
                _travel_hint_label = _travel_hint_match.group(1).strip()
                clean_assistant = _re.sub(r'\s*\[TRAVEL_HINT:[^\]]+\]', '', clean_assistant).strip()

        result_out = (
            {**result, "message": clean_assistant} if isinstance(result, dict) else result
        )

        # ── T33: Build suggested actions for hybrid input UI ─────────────────
        _suggested_actions: list[dict] = []
        try:
            _sf_for_sa = {}
            _gs_for_sa = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if _gs_for_sa:
                _sf_for_sa = json.loads(_gs_for_sa["session_flags"] or "{}")
            _game_state_for_sa = _sf_for_sa.get("state", "NARRATIVE")
            # If combat just started, use COMBAT state
            if new_combat:
                _game_state_for_sa = "COMBAT"
            # Parse LLM-suggested actions from GM JSON if present
            _llm_suggested: list[dict] | None = None
            if isinstance(_parsed_json, dict):
                _raw_llm_sa = _parsed_json.get("suggested_actions")
                if isinstance(_raw_llm_sa, list):
                    _llm_suggested = _raw_llm_sa
            _suggested_actions = build_suggested_actions(
                conn=conn,
                campaign_id=campaign_id,
                character_id=payload.character_id,
                game_state=_game_state_for_sa,
                session_flags=_sf_for_sa,
                llm_suggested=_llm_suggested,
                travel_hint=_travel_hint_label,
            )
        except Exception as _sa_err:
            logger.warning("suggested_actions_build_error", error=str(_sa_err))

        # U32: travel escalation level (0=none, 1=highlight pills, 2=banner)
        _turns_stale = int(_sf_for_sa.get("turns_at_location", 0) or 0)
        _travel_escalation_level = 2 if _turns_stale >= 10 else (1 if _turns_stale >= 5 else 0)

        # L13c (#689): inside an active tile dungeon — no overworld travel UI.
        # Suppress the anti-stuck travel banner and drop travel-type suggested
        # actions; dungeon movement is via the D-pad / tile actions only.
        _drun_sa = (_sf_for_sa.get("dungeon_run") or {})
        if (_drun_sa.get("system") == "tiles_v2"
                and not _drun_sa.get("completed") and not _drun_sa.get("failed")):
            _travel_escalation_level = 0
            _suggested_actions = [
                a for a in _suggested_actions
                if isinstance(a, dict) and a.get("type") != "travel"
            ]

        out: dict = {
            "id": log["id"],
            "campaign_id": log["campaign_id"],
            "turn_number": log["turn_number"],
            "created_at": log["created_at"],
            "route": "narrative",
            "result": result_out,
            "prose": clean_assistant,
            "turn_id": turn_id,
            "suggested_actions": _suggested_actions,
            "travel_escalation_level": _travel_escalation_level,
        }
        if _skill_pending_narrator:
            out["skill_test_pending"] = _skill_pending_narrator
        if new_combat is not None:
            out["combat_state"] = new_combat
        if combat_extra:
            out.update(combat_extra)
        if _should_emit_open_shop_in_mode(open_shop_npc_key, campaign["mode"]):
            out["open_shop"] = open_shop_npc_key
        # Hex travel signal: frontend uses this to auto-update map pin
        if _hex_after_enc and _hex_before_enc and _hex_after_enc != _hex_before_enc:
            out["hex_changed"] = {"from": _hex_before_enc, "to": _hex_after_enc}
        if _dungeon_clear_result:
            out["dungeon_cleared"] = _dungeon_clear_result

        # #773 (1A) — deklaracja obezwładnienia poza walką → bramka intencji (#780)
        # zamiast cichego COMBAT_START. Agresywna deklaracja non-lethal („obezwładniam",
        # „przyciskam do ściany") nie wybucha śmiertelną walką — silnik STOP i pyta gracza.
        if new_combat is None and not combat_was_active and _subdue_intent(text):
            try:
                from app.services.combat_service import build_advantage_gate
                _sub_gate = build_advantage_gate("grapple")
                if _sub_gate:
                    out["advantage_gate"] = _sub_gate
            except Exception as _sub_err:
                logger.warning("subdue_gate_build_error", error=str(_sub_err))

        # B5: auto-save World State snapshot after each narrative turn
        try:
            from app.services.world_state_service import auto_save_snapshot as _ws_snap, get_world_state_flags as _gwsf_out
            _ws_snap(campaign_id)
            out["active_quests"] = _gwsf_out(campaign_id).get("active_quests", [])
        except Exception as _ws_err:
            logger.warning("world_state_snapshot_error", error=str(_ws_err))

        # E25 + U20 (#572): inject onboarding cards for first-time mechanic triggers
        try:
            # U20: signal NPC dialogue this turn so the crafter card can trigger
            try:
                _dlg_seen = bool(locals().get("_dlg_m"))
                _txt_norm = _normalize_pl(text or "")
                if _dlg_seen or any(d in _txt_norm for d in _COMPOUND_DIALOGUE_MARKERS):
                    out["npc_dialogue"] = True
            except Exception:
                pass
            from app.services.onboarding_service import inject_onboarding_to_out as _ob_inject
            _ob_inject(out, user_id=int(character["user_id"]), conn=conn, character=character)
        except Exception as _ob_err:
            logger.warning("onboarding_injection_error", error=str(_ob_err))
            out.setdefault("onboarding_cards", [])

        return out

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# POST turn streaming (SSE)
# ---------------------------------------------------------------------------

@router.post("/campaigns/{campaign_id}/turns/stream")
def create_turn_stream(
    campaign_id: int,
    payload: TurnCreate,
    x_ollama_base_url: str | None = Header(default=None),
    ui_trace_id: str | None = Header(default=None, alias="X-UI-Trace-Id"),
):
    """
    Streaming version of the turn endpoint.
    Returns a text/event-stream (SSE) response.
    Each chunk: 'data: <token>\\n\\n'
    Final chunk: 'data: [DONE]\\n\\n'
    The full assembled text is saved to campaign_turns after streaming completes.
    """
    conn = get_db()
    turn_id = _start_turn_trace(campaign_id, payload.character_id, "turn_stream")
    ui_tid = (ui_trace_id or "").strip()[:128]
    if ui_tid:
        bind_context(ui_trace_id=ui_tid)
    logger.info(
        "turn_stream_open",
        campaign_id=campaign_id,
        character_id=payload.character_id,
    )
    stream_headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "X-Turn-Id": turn_id,
    }
    try:
        campaign = get_active_campaign_or_gone(conn, campaign_id)
        character = get_character_or_404(conn, campaign_id, payload.character_id)
        llm_config = get_user_llm_settings_full(character["user_id"])
        text = (payload.text or "").strip()

        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        if re.match(r"^/helpme(\s|$)", text, re.I):
            topic = re.sub(r"^/helpme\s*", "", text, count=1, flags=re.I).strip()
            owner_id = int(campaign["owner_user_id"])
            llm_owner = get_user_llm_settings_full(owner_id)
            model_h = resolve_model_name(
                requested_model=payload.engine,
                campaign_model=campaign["model_id"],
                llm_config=llm_owner,
            )
            try:
                out = run_helpme_advisor(
                    conn=conn,
                    campaign=campaign,
                    character=character,
                    topic=topic,
                    user_id=owner_id,
                    model=model_h,
                )
            except RuntimeError as e:
                err = str(e)

                def helpme_err_stream():
                    yield f"data: [ERROR] {err}\n\n"

                return StreamingResponse(
                    helpme_err_stream(),
                    media_type="text/event-stream",
                    headers=stream_headers,
                )

            msg = (out.get("message") or "").strip()
            if not msg:

                def helpme_empty_stream():
                    yield "data: [ERROR] Empty /helpme response\n\n"

                return StreamingResponse(
                    helpme_empty_stream(),
                    media_type="text/event-stream",
                    headers=stream_headers,
                )

            user_line = text.strip()
            create_turn_log(
                conn=conn,
                campaign_id=campaign_id,
                character_id=payload.character_id,
                user_text=user_line,
                assistant_text=msg,
                route="helpme",
            )

            def helpme_token_stream():
                safe = msg.replace("\\", "\\\\").replace("\n", "\\n")
                yield f"data: {safe}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                helpme_token_stream(),
                media_type="text/event-stream",
                headers=stream_headers,
            )

        roll_request = parse_roll_command(text)
        roll_result_message = None
        roll_result_data = None
        user_text_stored = text
        if roll_request:
            if not is_slash_command_enabled("/roll"):

                def roll_disabled_stream():
                    yield "data: [ERROR] Komenda /roll jest wyłączona przez administratora.\n\n"

                return StreamingResponse(
                    roll_disabled_stream(),
                    media_type="text/event-stream",
                    headers=stream_headers,
                )
            character_sheet = parse_character_sheet(character["sheet_json"])
            if roll_request.get("skill") == "death_save":
                hp_chk = _sheet_current_hp(character_sheet)
                if hp_chk is not None and hp_chk > 0:
                    logger.warning(
                        "death_save_rejected_stream",
                        character_id=payload.character_id,
                        hp=hp_chk,
                    )

                    def death_save_invalid_stream():
                        yield "data: [ERROR] Nieprawidłowy rzut: death_save przy HP > 0\n\n"

                    return StreamingResponse(
                        death_save_invalid_stream(),
                        media_type="text/event-stream",
                        headers=stream_headers,
                    )
            if is_attack_test(roll_request.get("skill")):
                weapon_row = resolve_sheet_weapon(conn, character_sheet, int(payload.character_id))
                raw_roll = roll_request.get("raw_roll")
                roll_result = resolve_attack_roll_for_weapon(
                    character_sheet,
                    raw_roll=int(raw_roll) if raw_roll is not None else roll_d20(),
                    weapon_row=weapon_row,
                )
                roll_result["dc"] = resolve_dc_for_roll(roll_request.get("dc"))
                if roll_result["dc"] is not None:
                    roll_result["success"] = roll_result["total"] >= int(roll_result["dc"])
            else:
                roll_result = resolve_roll(
                    character_sheet=character_sheet,
                    test_name=roll_request["skill"],
                    raw_roll=roll_request.get("raw_roll"),
                    dc=resolve_dc_for_roll(roll_request.get("dc")),
                )
            roll_result_data = roll_result
            roll_result_message = format_roll_for_llm(roll_result)
            user_text_stored = ROLL_CARD_PREFIX + "\n" + json.dumps(
                build_roll_card_payload(
                    roll_result,
                    character_name=(character["name"] or "Bohater"),
                    replay_command=text.strip(),
                ),
                ensure_ascii=False,
            )

        # XS9/XS10/XS11: pending XP for successful skill check by DC range
        if (roll_result_data and roll_result_data.get("success")
                and roll_result_data.get("test") != "death_save"):
            _dc_val = roll_result_data.get("dc")
            if _dc_val and int(_dc_val) >= 12:
                try:
                    from app.services.xp_sources import grant_skill_dc_success
                    _tn9 = conn.execute(
                        "SELECT COALESCE(MAX(turn_number),1) FROM campaign_turns WHERE campaign_id=?",
                        (campaign_id,),
                    ).fetchone()[0]
                    grant_skill_dc_success(conn, int(payload.character_id), campaign_id, int(_dc_val), _tn9)
                    conn.commit()
                except Exception:
                    pass

        if roll_result_data and roll_result_data.get("test") == "death_save":
            sheet_dict = parse_character_sheet(character["sheet_json"])
            new_sheet, died_here = apply_death_save_outcome(sheet_dict, roll_result_data)
            conn.execute(
                """
                UPDATE characters SET sheet_json = ?
                WHERE id = ? AND campaign_id = ?
                """,
                (
                    json.dumps(new_sheet, ensure_ascii=False),
                    payload.character_id,
                    campaign_id,
                ),
            )
            conn.commit()
            # XS14: grant pending XP when player survives a death save
            if not died_here:
                try:
                    from app.services.xp_sources import grant_death_save_survived
                    _tn14 = conn.execute(
                        "SELECT COALESCE(MAX(turn_number),1) FROM campaign_turns WHERE campaign_id=?",
                        (campaign_id,),
                    ).fetchone()[0]
                    grant_death_save_survived(conn, int(payload.character_id), campaign_id, _tn14)
                    conn.commit()
                except Exception:
                    pass
            character = get_character_or_404(conn, campaign_id, payload.character_id)
            if died_here:
                loc = (character["location"] or "unknown place").strip()
                dr = f"Failed three death saves ({loc})"
                epitaph = end_solo_campaign_on_death(
                    conn,
                    campaign_id=campaign_id,
                    character_row=character,
                    death_reason=dr,
                )
                # J2: write history row + queue chapter summary generation
                try:
                    from app.services.chapter_summary_service import close_campaign_with_summary
                    _ch_sheet = json.loads(character["sheet_json"] or "{}")
                    _ch_xp = int(_ch_sheet.get("xp_lifetime_earned") or 0)
                    _ch_gold = int(_ch_sheet.get("gold_gp") or _ch_sheet.get("gold") or 0)
                    _ch_turns = conn.execute(
                        "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ? AND route = 'narrative'",
                        (campaign_id,),
                    ).fetchone()[0]
                    close_campaign_with_summary(
                        conn,
                        campaign_id=campaign_id,
                        character_id=int(payload.character_id),
                        outcome="death",
                        user_id=int(character["user_id"]),
                        xp_earned=_ch_xp,
                        gold_at_end=_ch_gold,
                        turns_count=int(_ch_turns or 0),
                    )
                except Exception as _j2_err:
                    logger.warning("j2_death_history_failed_stream", error=str(_j2_err))
                user_line = user_text_stored if roll_request else (roll_result_message or text)
                log = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=user_line,
                    assistant_text=epitaph,
                    route="narrative",
                )
                log_narrative_turn_structured(
                    route="narrative",
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    turn_row=log,
                    user_text=user_line,
                    assistant_text=epitaph,
                )

                def death_token_stream():
                    safe = epitaph.replace("\\", "\\\\").replace("\n", "\\n")
                    yield f"data: {safe}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    death_token_stream(),
                    media_type="text/event-stream",
                    headers=stream_headers,
                )

        # Commands are not streamed (except /roll, which is turned into a narrative input)
        if text.startswith("/") and not roll_request:
            cmd = text.split(" ", 1)[0].lower()
            _is_admin_stream = False
            try:
                _ur = conn.execute(
                    "SELECT COALESCE(is_admin, 0) AS is_admin FROM users WHERE id = ? LIMIT 1",
                    (character["user_id"],),
                ).fetchone()
                _is_admin_stream = bool(_ur and int(_ur["is_admin"] or 0))
            except Exception:
                pass
            sk_stream = slash_registry_key_for_dispatch(text, is_admin=_is_admin_stream)
            # Alias support: rewrite cmd + text to canonical first-token
            if sk_stream:
                _canon_s = sk_stream.split(" ", 1)[0].lower()
                if _canon_s != cmd:
                    rest_s = text[len(cmd):]
                    text = _canon_s + rest_s
                    cmd = _canon_s
            if (
                sk_stream
                and not is_slash_command_enabled(sk_stream)
                and cmd not in ("/atak", "/walka")
            ):
                route_cmd = "command"
                token = sk_stream.split()[0].lstrip("/") or "cmd"
                result = {
                    "command": token,
                    "disabled": True,
                    "message": "Ta komenda została wyłączona przez administratora.",
                }
                log = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=text,
                    assistant_text=json.dumps(result, ensure_ascii=False),
                    route=route_cmd,
                )
                outer = _with_turn_trace({**log, "route": "command", "result": result}, turn_id)
                outer_json = json.dumps(outer, ensure_ascii=False)

                def disabled_cmd_stream():
                    yield f"data: [CMD_JSON]{outer_json}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    disabled_cmd_stream(),
                    media_type="text/event-stream",
                    headers=stream_headers,
                )

            if cmd in ("/atak", "/walka"):
                route_cmd = "command"
                result = _atak_command_response_for_api(campaign_id)
                log = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=text,
                    assistant_text=json.dumps(result, ensure_ascii=False),
                    route=route_cmd,
                )
                outer = _with_turn_trace({**log, "route": "command", "result": result}, turn_id)
                outer_json = json.dumps(outer, ensure_ascii=False)

                def atak_cmd_stream():
                    yield f"data: [CMD_JSON]{outer_json}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    atak_cmd_stream(),
                    media_type="text/event-stream",
                    headers=stream_headers,
                )

            # /quest, /export, /move — handled by turn_commands module
            if cmd in _TURN_HANDLED_COMMANDS:
                _tc_stream_result = _handle_turn_command(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    text=text,
                    cmd=cmd,
                    turn_id=turn_id,
                    create_turn_log=create_turn_log,
                    _with_turn_trace=_with_turn_trace,
                )
                if _tc_stream_result is not None:
                    _tc_outer_json = json.dumps(_tc_stream_result, ensure_ascii=False)

                    def _tc_cmd_stream():
                        yield f"data: [CMD_JSON]{_tc_outer_json}\n\n"
                        yield "data: [DONE]\n\n"

                    return StreamingResponse(
                        _tc_cmd_stream(),
                        media_type="text/event-stream",
                        headers=stream_headers,
                    )

            def command_stream():
                yield f"data: [CMD] {text}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(
                command_stream(),
                media_type="text/event-stream",
                headers=stream_headers,
            )

        # ── Pre-LLM keyword scan (streaming endpoint) ────────────────────────
        # Mirror of the same scanner in create_turn(); fires before the LLM
        # call so exploration actions that match trigger_keywords get a dice
        # prompt immediately instead of going straight to narrative.
        # Reading-context guard (issue #12 BUG-02) — see _is_reading_context().
        # #457 (SB-3/SB-4): check existing state — skip scan if already SKILL_TEST_PENDING.
        _s_sf_row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        _s_sf_state = "NARRATIVE"
        _s_sf_pending = {}
        if _s_sf_row:
            try:
                _s_sf = json.loads(_s_sf_row["session_flags"] or "{}")
                _s_sf_state = _s_sf.get("state", "NARRATIVE")
                _s_sf_pending = _s_sf.get("pending_skill_test") or {}
            except Exception:
                pass

        if _s_sf_state == "SKILL_TEST_PENDING" and _s_sf_pending:
            _log_re_s = create_turn_log(
                conn=conn,
                campaign_id=campaign_id,
                character_id=payload.character_id,
                user_text=text,
                assistant_text=None,
                route="skill_test",
            )
            conn.commit()
            _re_payload = json.dumps({
                "id": _log_re_s["id"],
                "campaign_id": _log_re_s["campaign_id"],
                "turn_number": _log_re_s["turn_number"],
                "created_at": _log_re_s["created_at"],
                "skill_test_pending": _s_sf_pending,
                "prose": None,
                "route": "skill_test",
                "turn_id": turn_id,
            }, ensure_ascii=False)

            def _pending_resuface_stream():
                yield f"data: [SKILL_TEST_PENDING]{_re_payload}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                _pending_resuface_stream(),
                media_type="text/event-stream",
                headers=stream_headers,
            )

        if not roll_request and not text.startswith("__AI_GM") and _text_is_action_attempt(text) and not _is_reading_context(text) and not _is_compound_action(text):
            try:
                _txt_s = _normalize_pl(text)
                _kw_rows_s = conn.execute(
                    "SELECT key, trigger_keywords FROM game_config_skills "
                    "WHERE trigger_keywords IS NOT NULL AND trigger_keywords != '' "
                    "AND key NOT IN ('attack', 'ranged_attack', 'two_handed', 'melee_attack', 'spell_attack', 'initiative')"
                ).fetchall()
                _pre_match_s = None
                for _kr_s in _kw_rows_s:
                    raw_kws_s = (_kr_s["trigger_keywords"] or "").replace(",", " ")
                    # K2 fix: exact word-boundary match (not prefix) — "legend" ≠ "legendzie"
                    _kws_s = [k.strip().lower().translate(_PL_NORMALIZE)
                              for k in raw_kws_s.split()
                              if k.strip() and len(k.strip()) >= 5]
                    if any(_kw_matches(kw, _txt_s) for kw in _kws_s):
                        _pre_match_s = _kr_s["key"]
                        break
                if _pre_match_s and not is_attack_test(_pre_match_s):
                    _active_combat_s = conn.execute(
                        "SELECT id FROM active_combat WHERE campaign_id = ? AND status = 'active' LIMIT 1",
                        (campaign_id,),
                    ).fetchone()
                    if not _active_combat_s:
                        from app.services.skill_service import calc_skill_modifier_info, _skill_label, _get_counter
                        import uuid as _uuid_s
                        _char_sh_s = json.loads(character["sheet_json"] or "{}")
                        _pending_s = {
                            "skill_test_id": f"st-{_uuid_s.uuid4().hex[:8]}",
                            "skill_key": _pre_match_s,
                            "skill_label": _skill_label(_pre_match_s),
                            "counter": _get_counter(conn, _pre_match_s),
                            "modifier_breakdown": calc_skill_modifier_info(_char_sh_s, _pre_match_s),
                        }
                        gs_row_s = conn.execute(
                            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                            (campaign_id,),
                        ).fetchone()
                        if gs_row_s:
                            _sf_s = json.loads(gs_row_s["session_flags"] or "{}")
                            _sf_s = _commit_pending_skill_test(_pending_s, _sf_s)
                            conn.execute(
                                "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                                (json.dumps(_sf_s, ensure_ascii=False), campaign_id),
                            )
                            conn.commit()
                        logger.info("skill_test_triggered_by_keywords_stream", skill=_pre_match_s, text_snippet=text[:40])
                        _done_kw = json.dumps({"skill_test_pending": _pending_s}, ensure_ascii=False)

                        # B5: auto-save World State snapshot on skill test trigger
                        try:
                            from app.services.world_state_service import auto_save_snapshot as _ws_snap_kw
                            _ws_snap_kw(campaign_id)
                        except Exception as _ws_kw_err:
                            logger.warning("world_state_snapshot_kw_error", error=str(_ws_kw_err))

                        def _skill_kw_stream():
                            yield f"data: [DONE]{_done_kw}\n\n"

                        return StreamingResponse(
                            _skill_kw_stream(),
                            media_type="text/event-stream",
                            headers=stream_headers,
                        )
            except Exception as _pre_err_s:
                logger.warning("pre_llm_keyword_scan_stream_error: %s", str(_pre_err_s))

        # #777: record turn decision in streaming path (was only in JSON path)
        if not roll_request:
            _record_turn_decision_safe(
                campaign_id, payload.character_id, text,
                route="narrative", gate_blocked=False, gate_reason=None,
                handler="narrative", conn=conn,
            )

        _require_gm_plan_before_narrative_llm(conn, campaign_id, campaign)

        model = resolve_model_name(
            requested_model=payload.engine,
            campaign_model=campaign["model_id"],
            llm_config=llm_config,
        )

        llm_user_text = roll_result_message or text
        messages = build_narrative_messages(
            conn=conn,
            campaign=campaign,
            character=character,
            user_text=text,
            roll_result_message=roll_result_message,
            roll_result_data=roll_result_data,
        )

        # U30 (#578): directional-move fast-path via the shared helper (same code as the
        # JSON tor in create_turn). Resolves travel mechanically BEFORE the LLM so the map
        # pin moves (#518/#544); the [SYSTEM] fact is injected into the narrator prompt.
        u30_travel_executed = False
        try:
            from app.services.turn_pipeline import execute_directional_travel as _u30_exec
            _u30_res = _u30_exec(
                conn, campaign_id, payload.character_id,
                json.loads(character["sheet_json"] or "{}"), text,
            )
            u30_travel_executed = bool(_u30_res.get("executed"))
            _u30_fact = _u30_res.get("system_fact")
            if _u30_fact:
                _first_mv = messages[0] if messages else None
                if isinstance(_first_mv, dict) and _first_mv.get("role") == "system":
                    _first_mv["content"] = f"{_first_mv.get('content', '').rstrip()}{_u30_fact}"
                else:
                    messages.insert(0, {"role": "system", "content": _u30_fact.strip()})
                logger.info(
                    "u30_directional_travel_stream",
                    campaign_id=campaign_id,
                    travel_ok=u30_travel_executed,
                )
        except Exception as _u30_err:
            logger.warning("u30_directional_fastpath_error", error=str(_u30_err), campaign_id=campaign_id)

        location_skip_post_location_hook = _inject_pre_llm_unknown_location_denial(
            conn, campaign_id, text, messages
        )
        if u30_travel_executed:
            # Travel already resolved mechanically — don't let the LLM's location_intent
            # post-hook re-route or overwrite current_hex this turn.
            location_skip_post_location_hook = True

        campaign_id_val = campaign_id
        character_id_val = payload.character_id
        user_text_val = user_text_stored if roll_request else llm_user_text
        gm_roll_pre_payload, combat_ended_pre_payload = _stream_combat_roll_extras(
            campaign_id_val, user_text_val
        )
        post_loot_summary_payload = _parse_post_loot_summary_payload(user_text_val)

        def token_generator():
            """
            Order: (1) optional [GM_ROLL], (2) optional [COMBAT_ENDED] before narrative,
            (3) LLM chunks — skipped when combat_victory follow-up (stub narrative only),
            (4) persist turn, (5) [COMBAT_STARTED] / [COMBAT], (6) [DONE].
            """
            from app.services import combat_service as cs_snap

            _stream_ctx = {
                "turn_id": turn_id,
                "campaign_id": str(campaign_id_val),
                "character_id": str(character_id_val),
                "turn_route": "turn_stream",
            }
            if ui_tid:
                _stream_ctx["ui_trace_id"] = ui_tid
            bind_context(**_stream_ctx)

            combat_before = cs_snap.get_active_combat(campaign_id_val)
            combat_was_active = bool(combat_before) and str(
                combat_before.get("current_turn") or ""
            ) == "player"

            if combat_was_active:
                blocked_conn = get_db()
                try:
                    blocked_turn = _maybe_handle_blocked_player_combat_turn(
                        conn=blocked_conn,
                        campaign_id=campaign_id_val,
                        character_id=character_id_val,
                        user_text=user_text_val,
                        turn_id=turn_id,
                    )
                finally:
                    blocked_conn.close()
                if blocked_turn is not None:
                    clean_text = str(
                        ((blocked_turn.get("result") or {}).get("message"))
                        or "Warunek blokuje akcję bohatera w tej turze."
                    )
                    yield f"data: {clean_text}\n\n"
                    combat_payload = {
                        "combat_advanced": bool(blocked_turn.get("combat_advanced")),
                        "new_combat_turn": blocked_turn.get("new_combat_turn"),
                    }
                    if combat_payload.get("combat_advanced") and combat_payload.get("new_combat_turn"):
                        yield f"data: [COMBAT]{json.dumps(combat_payload, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

            if gm_roll_pre_payload:
                logger.info("combat_gm_roll_emit", campaign_id=campaign_id_val)
                yield f"data: [GM_ROLL]{json.dumps(gm_roll_pre_payload, ensure_ascii=False)}\n\n"
            if combat_ended_pre_payload:
                logger.info("combat_ended_emit", campaign_id=campaign_id_val)
                yield f"data: [COMBAT_ENDED]{json.dumps(combat_ended_pre_payload, ensure_ascii=False)}\n\n"

            if combat_ended_pre_payload:
                clean_text = COMBAT_VICTORY_STREAM_STUB
                validate_roll_cue_name(clean_text.strip())
                persisted_assistant_text = clean_text
                if gm_roll_pre_payload:
                    persisted_assistant_text = (
                        f"{GM_ROLL_CARD_PREFIX}\n"
                        f"{json.dumps(gm_roll_pre_payload, ensure_ascii=False)}\n\n"
                        f"{clean_text}"
                    )
                save_conn = get_db()
                new_combat: dict | None = None
                combat_extra: dict | None = None
                try:
                    stream_log = create_turn_log(
                        conn=save_conn,
                        campaign_id=campaign_id_val,
                        character_id=character_id_val,
                        user_text=user_text_val,
                        assistant_text=persisted_assistant_text,
                        route="narrative",
                    )
                    log_narrative_turn_structured(
                        route="narrative",
                        campaign_id=campaign_id_val,
                        character_id=character_id_val,
                        turn_row=stream_log,
                        user_text=user_text_val,
                        assistant_text=clean_text,
                    )
                    # Issue #135 — inject [COMBAT_START] when player attacked but LLM omitted it.
                    clean_text = _ensure_combat_start_tag(save_conn, campaign_id_val, user_text_val, clean_text)
                    new_combat = _maybe_start_combat_from_gm_tag(
                        campaign_id_val, character_id_val, clean_text,
                        turn_log_id=stream_log.get("id") if stream_log else None,
                        turn_number=stream_log.get("turn_number", 0) if stream_log else 0,
                    )
                    if combat_was_active and not new_combat:
                        combat_extra = _maybe_advance_combat_after_player_narrative(
                            campaign_id_val
                        )
                finally:
                    save_conn.close()
                if new_combat:
                    yield f"data: [COMBAT_STARTED]{json.dumps(new_combat)}\n\n"
                if combat_extra:
                    yield f"data: [COMBAT]{json.dumps(combat_extra)}\n\n"
                # C11: kill quest auto-complete on enemy_killed
                _combat_done: dict = {}
                try:
                    from app.services.quest_checker import check_kill_quest as _ckq, parse_reward as _preward
                    from app.services.world_state_service import get_world_state_flags as _gwsf_cq, set_world_state_flags as _swsf_cq
                    from app.services.quest_persist_service import complete_quest_in_character_quests as _cqdb
                    _cq_quests = _gwsf_cq(campaign_id_val).get("active_quests", [])
                    _ek_name = (combat_ended_pre_payload or {}).get("enemy_name", "")
                    if _ek_name and _cq_quests:
                        _cq_updated, _cq_done = _ckq(_cq_quests, _ek_name)
                        if _cq_done:
                            _swsf_cq(campaign_id_val, active_quests=_cq_updated)
                            _rwd_conn = get_db()
                            try:
                                for _cq_item in _cq_done:
                                    _rwd = _preward(_cq_item.get("reward", ""))
                                    if _rwd["xp"] > 0:
                                        from app.services.xp_service import grant_character_xp as _gcxp
                                        _gcxp(_rwd_conn, character_id_val, _rwd["xp"], reason=f"quest_complete:{_cq_item['title']}")
                                    if _rwd["gold"] > 0:
                                        apply_grant_gold_to_character(_rwd_conn, character_id=character_id_val, amount=_rwd["gold"], source="quest_reward", campaign_id=campaign_id_val)
                                    logger.info("quest_completed_kill", campaign_id=campaign_id_val, title=_cq_item["title"])
                                    # HF-2: update character_quests to completed
                                    _cqdb(_rwd_conn, character_id=character_id_val, campaign_id=campaign_id_val, title=_cq_item["title"])
                                _rwd_conn.commit()
                            finally:
                                _rwd_conn.close()
                        _combat_done["active_quests"] = _cq_updated
                    elif _cq_quests:
                        _combat_done["active_quests"] = _cq_quests
                except Exception as _cqe:
                    logger.warning("kill_quest_check_error", error=str(_cqe))
                yield f"data: [DONE]{json.dumps(_combat_done, ensure_ascii=False)}\n\n"
                return

            if post_loot_summary_payload:
                clean_text = _render_post_loot_summary_text(post_loot_summary_payload)
                save_conn = get_db()
                try:
                    stream_log = create_turn_log(
                        conn=save_conn,
                        campaign_id=campaign_id_val,
                        character_id=character_id_val,
                        user_text=user_text_val,
                        assistant_text=clean_text,
                        route="narrative",
                    )
                    log_narrative_turn_structured(
                        route="narrative",
                        campaign_id=campaign_id_val,
                        character_id=character_id_val,
                        turn_row=stream_log,
                        user_text=user_text_val,
                        assistant_text=clean_text,
                    )
                finally:
                    save_conn.close()
                yield f"data: {clean_text}\n\n"
                yield "data: [DONE]\n\n"
                return

            # ── Skip-narrative fast path (player toggle or global admin flag) ──
            # Double-gated: BOTH input_type must be 'combat_roll' AND text must carry the
            # combat-roll prefix. Prevents global flag from accidentally silencing regular
            # narrative turns if somehow the prefix check is bypassed.
            _is_combat_roll = (
                payload.input_type == "combat_roll"
                and user_text_val.startswith(COMBAT_ROLL_CTX_PREFIX)
            )
            _skip_narrative = (payload.skip_narrative or _get_skip_combat_narrative_global()) and _is_combat_roll
            if _skip_narrative:
                clean_text = _build_combat_narrative_stub(user_text_val)
                save_conn = get_db()
                try:
                    create_turn_log(
                        conn=save_conn,
                        campaign_id=campaign_id_val,
                        character_id=character_id_val,
                        user_text=user_text_val,
                        assistant_text=clean_text,
                        route="narrative",
                    )
                finally:
                    save_conn.close()
                yield f"data: {clean_text}\n\n"
                yield "data: [DONE]\n\n"
                return

            collected: list[str] = []
            saw_done = False
            _sse_log = os.getenv("SSE_NARRATIVE_PROGRESS_LOG", "").strip().lower() in (
                "1",
                "true",
                "yes",
            )
            _sse_chunks = 0
            _sse_chars = 0
            for chunk in generate_chat_stream(
                messages=messages,
                model=model,
                llm_config=llm_config,
            ):
                if chunk.startswith("data: [ERROR]"):
                    yield chunk
                    return
                if chunk.startswith("data: [DONE]"):
                    saw_done = True
                    break
                token = chunk[6:].rstrip("\n")
                collected.append(token)
                if _sse_log:
                    _sse_chunks += 1
                    _sse_chars += len(token)
                    if _sse_chunks == 1 or _sse_chunks % 25 == 0:
                        logger.info(
                            "sse_narrative_progress",
                            campaign_id=campaign_id_val,
                            character_id=character_id_val,
                            token_chunks=_sse_chunks,
                            approx_chars=_sse_chars,
                        )
                yield chunk

            if not saw_done:
                logger.warning(
                    "stream_missing_done_marker",
                    campaign_id=campaign_id_val,
                )
                return

            full_raw = "".join(collected).replace("\\n", "\n")
            hook_conn = get_db()
            try:
                full_raw = _process_location_intent(
                    conn=hook_conn,
                    campaign_id=campaign_id_val,
                    assistant_response=full_raw,
                    skip_post_process=location_skip_post_location_hook,
                )
            finally:
                hook_conn.close()
            new_combat = None
            combat_extra = None
            _npc_dialogue_key = None
            if full_raw.strip():
                clean_text = COMBAT_START_RE.sub("", full_raw).rstrip()
                # Stage 3 Z4 — apply + strip [APPLY_CONDITION:condition_key:enemy_key]
                _ac_invalid_s = False
                try:
                    from app.services.combat_service import apply_condition_to_combatant
                    for _ac in APPLY_CONDITION_RE.finditer(clean_text):
                        _ac_res = apply_condition_to_combatant(
                            campaign_id_val, _ac.group(2).strip(), _ac.group(1).strip()
                        )
                        logger.info("apply_condition_tag_stream", campaign_id=campaign_id_val,
                                    condition=_ac.group(1), enemy_ref=_ac.group(2), result=_ac_res)
                        if isinstance(_ac_res, dict) and _ac_res.get("reason") == "invalid_reference":
                            _ac_invalid_s = True
                except Exception as _ace:
                    logger.warning("apply_condition_tag_stream_error", error=str(_ace))
                clean_text = APPLY_CONDITION_RE.sub("", clean_text).rstrip()
                fb = get_db()
                # S8 (#603): invalid_reference → llm_tag_errors + korekta U6 (streaming)
                if _ac_invalid_s:
                    try:
                        from app.services.llm_tag_parser import (
                            get_rejection_correction as _acs_corr,
                            log_tag_error as _acs_lte,
                        )
                        _acs_tn = fb.execute(
                            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
                            (campaign_id_val,),
                        ).fetchone()[0]
                        _acs_lte(fb, campaign_id_val, _acs_tn, "[APPLY_CONDITION]", "invalid_reference")
                        _acs_fix = _acs_corr("APPLY_CONDITION")
                        if _acs_fix:
                            _acs_narr, _acs_pjson = _extract_narrative_for_cues(clean_text)
                            clean_text = _repack_narrative(
                                clean_text, _acs_narr.rstrip() + "\n\n" + _acs_fix, _acs_pjson)
                    except Exception as _acse:
                        logger.warning("apply_condition_invalid_stream_error", error=str(_acse))
                try:
                    clean_text = maybe_append_open_shop_fallback(
                        fb, campaign_id_val, user_text_val, clean_text
                    )
                finally:
                    fb.close()
                _narrative_for_cues_s, _parsed_json_s = _extract_narrative_for_cues(clean_text)
                (
                    _narrative_for_cues_s,
                    grant_item_labels,
                    grant_gold_amount,
                    open_shop_npc_key,
                    grant_item_descriptions,
                ) = extract_grant_cues(_narrative_for_cues_s)
                # Also check top-level grant_item in parsed JSON (same fix as non-streaming path)
                if isinstance(_parsed_json_s, dict):
                    _raw_gi_s = _parsed_json_s.get("grant_item")
                    _entries_s: list = (_raw_gi_s if isinstance(_raw_gi_s, list) else [_raw_gi_s]) if _raw_gi_s else []
                    for _xs in _entries_s:
                        _entry_s = _parse_grant_item_entry(_xs)
                        if _entry_s and _entry_s[0] not in grant_item_labels:
                            grant_item_labels.append(_entry_s[0])
                            grant_item_descriptions[_entry_s[0]] = _entry_s[1]
                grant_item_label = grant_item_labels[0] if grant_item_labels else None  # compat
                clean_text = _repack_narrative(clean_text, _narrative_for_cues_s, _parsed_json_s)
                # Strip GM-only directive tags before saving (XP already processed from full_raw)
                try:
                    from app.services.narrative_state_service import strip_narrative_tags as _strip_tags_s
                    _narr_s, _pjson_s2 = _extract_narrative_for_cues(clean_text)
                    clean_text = _repack_narrative(clean_text, _strip_tags_s(_narr_s), _pjson_s2)
                except Exception as _ste:
                    logger.warning("narrative_tag_strip_stream_error", error=str(_ste))
                # U30.4 (#578): anti-desync guard on the streaming tor — flag when the
                # narrator claims travel but no mechanical move happened this turn.
                try:
                    from app.services.turn_pipeline import guard_travel_desync as _u30_guard_s
                    _u30s_narr, _ = _extract_narrative_for_cues(clean_text)
                    _u30s_turn = conn.execute(
                        "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
                        (campaign_id_val,),
                    ).fetchone()[0]
                    _u30_guard_s(conn, campaign_id_val, _u30s_narr, u30_travel_executed, _u30s_turn)
                except Exception as _u30gse:
                    logger.warning("u30_desync_guard_stream_error", error=str(_u30gse))
                # C10: parse QUEST_SUGGEST tags → active_quests, strip from narrative
                try:
                    from app.services.quest_suggest_parser import parse_quest_suggest as _pqs, strip_quest_suggest_tags as _sqs
                    from app.services.world_state_service import get_world_state_flags as _gwsf, set_world_state_flags as _swsf
                    from app.services.quest_persist_service import persist_quest_to_character_quests as _pqdb
                    _narr_qs, _pjson_qs = _extract_narrative_for_cues(clean_text)
                    _new_quests = _pqs(_narr_qs)
                    if _new_quests:
                        _existing = _gwsf(campaign_id_val).get("active_quests", [])
                        _seen_titles = {q.get("title", "") for q in _existing}
                        _to_add = [q for q in _new_quests if q["title"] not in _seen_titles]
                        if _to_add:
                            _swsf(campaign_id_val, active_quests=_existing + _to_add)
                            # HF-2: persist to character_quests for /quest command and stats
                            _qs_conn = get_db()
                            try:
                                for _q in _to_add:
                                    _pqdb(_qs_conn, character_id=character_id_val, campaign_id=campaign_id_val, quest=_q)
                            finally:
                                _qs_conn.close()
                    clean_text = _repack_narrative(clean_text, _sqs(_narr_qs), _pjson_qs)
                except Exception as _qse:
                    logger.warning("quest_suggest_parse_error", error=str(_qse))
                # C12/F4: parse [SPEND_GOLD:key] → deduct gold or inject refusal text
                try:
                    from app.services.spend_gold_service import apply_spend_gold_to_narrative as _apply_sg
                    _sg_conn = get_db()
                    try:
                        _sg_narr, _sg_pjson = _extract_narrative_for_cues(clean_text)
                        _sg_narr_clean = _apply_sg(_sg_narr, _sg_conn, character_id_val)
                        _sg_conn.commit()
                    finally:
                        _sg_conn.close()
                    clean_text = _repack_narrative(clean_text, _sg_narr_clean, _sg_pjson)
                except Exception as _sge:
                    logger.warning("spend_gold_parse_error", error=str(_sge))
                validate_roll_cue_name(clean_text.strip())
                if GM_ROLL_CARD_PREFIX in clean_text:
                    clean_text = re.sub(
                        rf"{re.escape(GM_ROLL_CARD_PREFIX)}\n.*?\n\n",
                        "",
                        clean_text,
                        flags=re.DOTALL,
                    ).strip()
                persisted_assistant_text = clean_text
                if gm_roll_pre_payload:
                    persisted_assistant_text = (
                        f"{GM_ROLL_CARD_PREFIX}\n"
                        f"{json.dumps(gm_roll_pre_payload, ensure_ascii=False)}\n\n"
                        f"{clean_text}"
                    )
                save_conn = get_db()
                try:
                    stream_log = create_turn_log(
                        conn=save_conn,
                        campaign_id=campaign_id_val,
                        character_id=character_id_val,
                        user_text=user_text_val,
                        assistant_text=persisted_assistant_text,
                        route="narrative",
                    )
                    log_narrative_turn_structured(
                        route="narrative",
                        campaign_id=campaign_id_val,
                        character_id=character_id_val,
                        turn_row=stream_log,
                        user_text=user_text_val,
                        assistant_text=clean_text,
                    )
                    # ── Streaming: [SKILL_TEST] tag + roll_cue intercept ──────────
                    # The non-streaming path calls intercept_skill_test_tag here.
                    # Streaming never did — so roll_cue/[SKILL_TEST] in LLM JSON
                    # responses silently fell through with no dice popup. (#237)
                    try:
                        from app.services.skill_service import (
                            intercept_skill_test_tag as _ists,
                            calc_skill_modifier_info as _csmi,
                            _skill_label as _sl,
                            _get_counter as _gc,
                        )
                        import uuid as _uuid_s
                        _char_sh_s = json.loads(character["sheet_json"] or "{}")
                        _sk_pending_s = None
                        # 1) [SKILL_TEST:key:DC] tag in narrative
                        _clean_after_tag, _sk_pending_s = _ists(
                            clean_text,
                            conn=save_conn,
                            campaign_id=campaign_id_val,
                            character_id=character_id_val,
                            user_text=user_text_val,
                        )
                        # 2) roll_cue in parsed JSON (if tag intercept didn't fire)
                        if not _sk_pending_s and _parsed_json_s and _text_is_action_attempt(user_text_val):
                            _raw_cue_s = str(_parsed_json_s.get("roll_cue") or "").strip()
                            if _raw_cue_s:
                                import re as _rc_re_s
                                _cm_s = _rc_re_s.match(r"^Roll (.+?) d\d+$", _raw_cue_s, _rc_re_s.IGNORECASE)
                                if _cm_s:
                                    _cue_name_s = _cm_s.group(1).strip()
                                    _canonical_s = resolve_test_name(_cue_name_s)
                                    if _canonical_s is None:
                                        _norm_s = _cue_name_s.lower().replace(" ", "_")
                                        _cue_db_s = save_conn.execute(
                                            "SELECT key FROM game_config_skills WHERE key = ? LIMIT 1",
                                            (_norm_s,),
                                        ).fetchone()
                                        if _cue_db_s:
                                            _canonical_s = _norm_s
                                    if _canonical_s and not is_attack_test(_canonical_s) and not _is_combat_class_skill(_canonical_s):
                                        _sk_pending_s = {
                                            "skill_test_id": f"st-{_uuid_s.uuid4().hex[:8]}",
                                            "skill_key": _canonical_s,
                                            "skill_label": _sl(_canonical_s),
                                            "counter": _gc(save_conn, _canonical_s),
                                            "modifier_breakdown": _csmi(_char_sh_s, _canonical_s),
                                        }
                        if _sk_pending_s and not _is_combat_class_skill(_sk_pending_s.get("skill_key", "")):
                            _gs_st_s = save_conn.execute(
                                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                                (campaign_id_val,),
                            ).fetchone()
                            if _gs_st_s:
                                _sf_st_s = json.loads(_gs_st_s["session_flags"] or "{}")
                                _sf_st_s = _commit_pending_skill_test(_sk_pending_s, _sf_st_s)
                                save_conn.execute(
                                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                                    (json.dumps(_sf_st_s, ensure_ascii=False), campaign_id_val),
                                )
                                save_conn.commit()
                                logger.info("stream_skill_test_pending_set",
                                            skill=_sk_pending_s.get("skill_key"),
                                            campaign_id=campaign_id_val)
                    except Exception as _sks_err:
                        logger.warning("stream_skill_test_intercept_error", error=str(_sks_err))
                    # ──────────────────────────────────────────────────────────────
                    # U6 (#530): detect items going to pending → correction + log
                    try:
                        from app.services.llm_tag_parser import (
                            get_rejection_correction as _u6s_corr,
                            log_tag_error as _u6s_lte,
                            save_rejected_tags as _u6s_srt,
                            clear_rejected_tags as _u6s_crt,
                            find_unknown_tags as _u6s_fut,
                        )
                        _u6s_turn_n = stream_log["turn_number"] if stream_log else 0
                        _u6s_rejected: list = []
                        _u6s_correction_parts: list = []
                        # Decision 2026-06-12 (Piotr): pending-item flow is ACCEPTED behaviour
                        # — no llm_tag_errors entry, no rejected-tags signal to the LLM.
                        # Narration correction only for trivial junk.
                        for _u6s_gil in grant_item_labels:
                            _u6s_resolved = _resolve_grant_catalog_item(save_conn, _u6s_gil)
                            if not _u6s_resolved and not _is_weapon_label(_u6s_gil) \
                                    and _is_trivial_item_label(_u6s_gil):
                                _u6s_fix = _u6s_corr("GRANT_ITEM")
                                if _u6s_fix:
                                    _u6s_correction_parts.append(_u6s_fix)
                        for _u6s_utag in _u6s_fut(clean_text):
                            _u6s_lte(save_conn, campaign_id_val, _u6s_turn_n, _u6s_utag, "unknown_tag")
                            _u6s_rejected.append(f"unknown:{_u6s_utag}")
                        if _u6s_correction_parts and stream_log:
                            # Append correction inside the narrative field (not the raw JSON wrapper)
                            _u6s_narr, _u6s_pjson = _extract_narrative_for_cues(persisted_assistant_text)
                            _u6s_narr_fixed = _u6s_narr.rstrip() + "\n\n" + "\n\n".join(_u6s_correction_parts)
                            _u6s_new_text = _repack_narrative(persisted_assistant_text, _u6s_narr_fixed, _u6s_pjson)
                            save_conn.execute(
                                "UPDATE campaign_turns SET assistant_text = ? WHERE id = ?",
                                (_u6s_new_text, stream_log["id"]),
                            )
                            # Expose for live-stream DONE payload (text already streamed without it)
                            _u6s_live_correction = "\n\n".join(_u6s_correction_parts)
                        save_conn.commit()
                        if _u6s_rejected:
                            _u6s_srt(save_conn, campaign_id_val, _u6s_rejected)
                        else:
                            _u6s_crt(save_conn, campaign_id_val)
                    except Exception as _u6s_err:
                        logger.warning("u6_stream_rejection_correction_error", error=str(_u6s_err))
                    # ──────────────────────────────────────────────────────────────
                    for _gil in grant_item_labels:
                        _gil_desc_s = grant_item_descriptions.get(_gil)
                        _resolved = _resolve_grant_catalog_item(save_conn, _gil)
                        if _resolved:
                            from app.services.loot_service import grant_loot_to_character
                            grant_loot_to_character(int(character_id_val),
                                                    [{"item_key": _resolved["item_key"], "quantity": 1}],
                                                    source="gm_grant_item")
                            logger.info("grant_item_catalog", character_id=character_id_val,
                                        item_key=_resolved["item_key"], label=_gil)
                        elif _is_weapon_label(_gil):
                            _grant_narrative_weapon(save_conn, campaign_id=campaign_id_val,
                                                    character_id=character_id_val, label=_gil, source="gm")
                        else:
                            # D1 (#376) — unknown item → pending_review catalog entry + admin queue
                            _grant_pending_item(
                                save_conn, campaign_id=campaign_id_val,
                                character_id=character_id_val, label=_gil, source="gm",
                                description=_gil_desc_s)
                    if grant_item_labels:
                        save_conn.commit()
                        from app.services.event_logger import write_game_event as _wge_s
                        for _ge_lbl in grant_item_labels:
                            try:
                                _wge_s("item_grant", campaign_id_val, character_id_val,
                                       character.get("user_id"),
                                       {"item_label": _ge_lbl, "source": "gm_grant_item"},
                                       conn=save_conn)
                                save_conn.commit()
                            except Exception:
                                pass
                    if grant_gold_amount is not None:
                        new_total = apply_grant_gold_to_character(
                            save_conn,
                            character_id=character_id_val,
                            amount=grant_gold_amount,
                        )
                        save_conn.commit()
                        logger.info(
                            "grant_gold_applied",
                            campaign_id=campaign_id_val,
                            character_id=character_id_val,
                            amount=grant_gold_amount,
                            new_total_gp=new_total,
                        )
                        try:
                            from app.services.event_logger import write_game_event as _wge_s2
                            _wge_s2("gold_grant", campaign_id_val, character_id_val,
                                    character.get("user_id"),
                                    {"amount": grant_gold_amount, "new_total_gp": new_total},
                                    conn=save_conn)
                            save_conn.commit()
                        except Exception:
                            pass
                    # XS1/XS2-XS8/XS12/XS15/XS6: narrative tag XP sources (stream handler)
                    try:
                        import re as _xs_re2
                        from app.services.xp_sources import (
                            process_narrative_xp_tags,
                            grant_first_location_visit,
                            grant_first_npc_talk,
                            grant_session_start,
                            grant_beat_complete,
                        )
                        _xp_char_id2 = int(character_id_val)
                        _xp_turn2 = save_conn.execute(
                            "SELECT COALESCE(MAX(turn_number),1) FROM campaign_turns WHERE campaign_id=?",
                            (campaign_id_val,),
                        ).fetchone()[0]
                        _xp_total2 = 0
                        _xp_total2 += grant_session_start(save_conn, _xp_char_id2, campaign_id_val, _xp_turn2)
                        _dlg_m2 = _xs_re2.match(r"^DIALOGUE:(.+)$", (user_text_val or "").strip(), _xs_re2.I)
                        if _dlg_m2:
                            _npc_dialogue_key = _dlg_m2.group(1).strip()
                            _xp_total2 += grant_first_npc_talk(
                                save_conn, _xp_char_id2, campaign_id_val, _npc_dialogue_key, _xp_turn2
                            )
                        for _bm2 in _xs_re2.finditer(r"\[BEAT_COMPLETE:\s*([^\]\s]+)\s*\]", full_raw or "", _xs_re2.I):
                            _xp_total2 += grant_beat_complete(save_conn, _xp_char_id2, campaign_id_val, _bm2.group(1), _xp_turn2)
                        # E6 (#421): [ARC_ADVANCE:key] tag in streaming path
                        try:
                            from app.services.campaign_plan_runtime import parse_arc_advance_tags as _paat2, advance_arc as _adv_arc2
                            for _arc_key2 in _paat2(full_raw or ""):
                                _adv_arc2(campaign_id_val, _arc_key2, save_conn)
                        except Exception as _arc_err2:
                            logger.warning("arc_advance_stream_error", error=str(_arc_err2))
                        _tag_r2 = process_narrative_xp_tags(
                            full_raw or "", save_conn, _xp_char_id2, campaign_id_val, _xp_turn2
                        )
                        _xp_total2 += _tag_r2["total_granted"]
                        _loc_r52 = save_conn.execute(
                            "SELECT gl.key FROM game_sessions gs "
                            "JOIN game_locations gl ON gl.id = gs.current_location_id "
                            "WHERE gs.campaign_id = ? LIMIT 1",
                            (campaign_id_val,),
                        ).fetchone()
                        if _loc_r52:
                            _xp_total2 += grant_first_location_visit(
                                save_conn, _xp_char_id2, campaign_id_val, _loc_r52["key"], _xp_turn2
                            )
                        # HF-11 (#553): talk_to_npc beat auto-complete (streaming tor)
                        try:
                            from app.services.campaign_plan_runtime import auto_complete_talk_to_npc
                            _dlg_key2 = _dlg_m2.group(1).strip() if _dlg_m2 else None
                            _loc_key_for_beat2 = _loc_r52["key"] if _loc_r52 else None
                            auto_complete_talk_to_npc(
                                campaign_id_val, user_text_val, _loc_key_for_beat2,
                                _dlg_key2, _xp_turn2, save_conn
                            )
                        except Exception as _b11_err2:
                            logger.warning("talk_beat_autocomplete_stream_error", error=str(_b11_err2))
                        if _xp_total2:
                            save_conn.commit()
                    except Exception as _xs_err2:
                        logger.warning("narrative_xp_hooks_stream_error", error=str(_xs_err2))
                    # BUG-04 (stream): parse gm_note / scene_advance / gm_plan_update
                    try:
                        from app.services.gm_plan_schema import normalize_gm_plan
                        _pdata4 = json.loads(_strip_json_code_fence(persisted_assistant_text or ""))
                        if isinstance(_pdata4, dict):
                            _gm_note4 = str(_pdata4.get("gm_note") or "").strip()
                            _scene_advance4 = bool(_pdata4.get("scene_advance"))
                            _plan_update4 = _pdata4.get("gm_plan_update")
                            if _gm_note4 or _scene_advance4 or isinstance(_plan_update4, dict):
                                _turn_num4 = save_conn.execute(
                                    "SELECT COALESCE(MAX(turn_number),1) FROM campaign_turns WHERE campaign_id=?",
                                    (campaign_id_val,),
                                ).fetchone()[0]
                                _camp_row4 = save_conn.execute(
                                    "SELECT gm_plan_json FROM campaigns WHERE id = ?",
                                    (campaign_id_val,),
                                ).fetchone()
                                _plan4 = normalize_gm_plan(_camp_row4["gm_plan_json"] if _camp_row4 else None)
                                _ep4 = dict(_plan4.get("engine_private") or {})
                                if _gm_note4:
                                    _buf4 = list(_ep4.get("gm_note_buffer") or [])
                                    _buf4.append({"turn": _turn_num4, "note": _gm_note4})
                                    if len(_buf4) > 30:
                                        _buf4 = _buf4[-30:]
                                    _ep4["gm_note_buffer"] = _buf4
                                if _scene_advance4:
                                    _aa4 = _plan4.get("active_arc_id")
                                    if _aa4 and isinstance(_plan4.get("arcs"), dict) and _aa4 in _plan4["arcs"]:
                                        _plan4["arcs"][_aa4]["current_scene_ordinal"] = (
                                            int(_plan4["arcs"][_aa4].get("current_scene_ordinal") or 0) + 1
                                        )
                                if isinstance(_plan_update4, dict):
                                    _aa4 = _plan4.get("active_arc_id")
                                    if _aa4 and isinstance(_plan4.get("arcs"), dict) and _aa4 in _plan4["arcs"]:
                                        for _k4, _v4 in _plan_update4.items():
                                            if _k4 in ("goal", "hooks", "notes") and _v4:
                                                _plan4["arcs"][_aa4][_k4] = _v4
                                _plan4["engine_private"] = _ep4
                                save_conn.execute(
                                    "UPDATE campaigns SET gm_plan_json=? WHERE id=?",
                                    (json.dumps(_plan4, ensure_ascii=False), campaign_id_val),
                                )
                                save_conn.commit()
                                logger.info("gm_note_buffer_updated_stream",
                                            campaign_id=campaign_id_val,
                                            note_len=len(_gm_note4),
                                            scene_advance=_scene_advance4)
                    except Exception as _gm4_err:
                        logger.warning("gm_note_stream_error", error=str(_gm4_err))
                    # Issue #135 — fallback inject for streaming narrative path too.
                    full_raw = _ensure_combat_start_tag(save_conn, campaign_id_val, user_text_val, full_raw)
                    new_combat = _maybe_start_combat_from_gm_tag(
                        campaign_id_val, character_id_val, full_raw,
                        turn_log_id=stream_log.get("id") if stream_log else None,
                        turn_number=stream_log.get("turn_number", 0) if stream_log else 0,
                    )
                    if combat_was_active and not new_combat:
                        combat_extra = _maybe_advance_combat_after_player_narrative(
                            campaign_id_val
                        )
                finally:
                    save_conn.close()
            else:
                open_shop_npc_key = None
            if new_combat:
                yield f"data: [COMBAT_STARTED]{json.dumps(new_combat)}\n\n"
            if combat_extra:
                yield f"data: [COMBAT]{json.dumps(combat_extra)}\n\n"
            if _should_emit_open_shop_in_mode(open_shop_npc_key, campaign["mode"]):
                yield f"data: [OPEN_SHOP]{json.dumps({'npc_key': open_shop_npc_key}, ensure_ascii=False)}\n\n"

            # V2: process [CREATE_*] / [NPC_KILLED] tags from accumulated text
            try:
                done_conn = sqlite3.connect(DB_PATH)
                done_conn.row_factory = sqlite3.Row
                try:
                    process_create_tags(full_raw or "", done_conn, campaign_id_val)
                    loc_info = get_current_location_info(done_conn, campaign_id_val)
                finally:
                    done_conn.close()
            except Exception:
                loc_info = None

            # Include current_location + any pending skill_test in DONE payload
            done_payload = {}
            if loc_info:
                done_payload["current_location"] = loc_info
            try:
                _sf_done_conn = sqlite3.connect(DB_PATH)
                _sf_done_conn.row_factory = sqlite3.Row
                try:
                    _sf_row = _sf_done_conn.execute(
                        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                        (campaign_id_val,),
                    ).fetchone()
                    if _sf_row:
                        _sf_done = json.loads(_sf_row["session_flags"] or "{}")
                        if _sf_done.get("pending_skill_test"):
                            done_payload["skill_test_pending"] = _sf_done["pending_skill_test"]
                        if _sf_done.get("state"):
                            done_payload["state"] = _sf_done["state"]
                    # T38: signal victory when [CAMPAIGN_END] tag fired this turn
                    _camp_row = _sf_done_conn.execute(
                        "SELECT status FROM campaigns WHERE id = ? LIMIT 1",
                        (campaign_id_val,),
                    ).fetchone()
                    if _camp_row and str(_camp_row["status"] or "").lower() in ("completed", "ended"):
                        done_payload["campaign_ended"] = True
                    # BUG-02: include current clock so frontend updates immediately
                    try:
                        from app.services.clock_service import get_clock_state as _gcs
                        done_payload["clock"] = _gcs(campaign_id_val, conn=_sf_done_conn)
                    except Exception:
                        pass
                finally:
                    _sf_done_conn.close()
            except Exception:
                pass
            if _npc_dialogue_key:
                try:
                    _npc_img_conn = sqlite3.connect(DB_PATH)
                    _npc_img_conn.row_factory = sqlite3.Row
                    try:
                        _npc_img_row = _npc_img_conn.execute(
                            "SELECT key, label, image_url FROM npcs WHERE key = ? AND is_active = 1 LIMIT 1",
                            (_npc_dialogue_key,),
                        ).fetchone()
                        if _npc_img_row and _npc_img_row["image_url"]:
                            yield f"data: [NPC_INTERACTION]{json.dumps({'key': _npc_img_row['key'], 'label': _npc_img_row['label'], 'image_url': _npc_img_row['image_url']}, ensure_ascii=False)}\n\n"
                    finally:
                        _npc_img_conn.close()
                except Exception:
                    pass
            # T33: build suggested actions and include in DONE payload
            try:
                _sa_conn = sqlite3.connect(DB_PATH)
                _sa_conn.row_factory = sqlite3.Row
                try:
                    _sf_sa: dict = {}
                    _sf_sa_row = _sa_conn.execute(
                        "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1",
                        (campaign_id_val,),
                    ).fetchone()
                    if _sf_sa_row:
                        _sf_sa = json.loads(_sf_sa_row["session_flags"] or "{}")
                    _gs_sa = _sf_sa.get("state", "NARRATIVE")
                    if new_combat:
                        _gs_sa = "COMBAT"
                    _llm_sa_s: list[dict] | None = None
                    _pjson_sa = locals().get("_parsed_json_s")
                    if isinstance(_pjson_sa, dict):
                        _raw_sa = _pjson_sa.get("suggested_actions")
                        if isinstance(_raw_sa, list):
                            _llm_sa_s = _raw_sa
                    done_payload["suggested_actions"] = build_suggested_actions(
                        conn=_sa_conn,
                        campaign_id=campaign_id_val,
                        character_id=character_id_val,
                        game_state=_gs_sa,
                        session_flags=_sf_sa,
                        llm_suggested=_llm_sa_s,
                    )
                    # U32: travel escalation level in streaming response
                    _turns_stale_s = int(_sf_sa.get("turns_at_location", 0) or 0)
                    done_payload["travel_escalation_level"] = 2 if _turns_stale_s >= 10 else (1 if _turns_stale_s >= 5 else 0)
                finally:
                    _sa_conn.close()
            except Exception:
                pass
            # #773 (1A) — subdue/grapple intent → bramka intencji (#780) w odpowiedzi stream.
            try:
                if new_combat is None and not combat_was_active and _subdue_intent(user_text_val):
                    from app.services.combat_service import build_advantage_gate as _bag_s
                    _sub_gate_s = _bag_s("grapple")
                    if _sub_gate_s:
                        done_payload["advantage_gate"] = _sub_gate_s
            except Exception as _sub_err_s:
                logger.warning("subdue_gate_build_error_stream", error=str(_sub_err_s))
            # B5: auto-save World State snapshot after each streaming narrative turn
            try:
                from app.services.world_state_service import auto_save_snapshot as _ws_snap_s, get_world_state_flags as _gwsf_done, set_world_state_flags as _swsf_done
                _ws_snap_s(campaign_id_val)
                _aq_current = _gwsf_done(campaign_id_val).get("active_quests", [])
                # C11: location quest auto-complete when player moves to a new location
                try:
                    _loc_name = (loc_info or {}).get("label", "") or (loc_info or {}).get("key", "")
                    if _loc_name and _aq_current:
                        from app.services.quest_checker import check_location_quest as _clq, parse_reward as _preward_loc
                        _lq_updated, _lq_done = _clq(_aq_current, _loc_name)
                        if _lq_done:
                            _swsf_done(campaign_id_val, active_quests=_lq_updated)
                            _aq_current = _lq_updated
                            _lrwd_conn = get_db()
                            try:
                                for _lq_item in _lq_done:
                                    _lrwd = _preward_loc(_lq_item.get("reward", ""))
                                    if _lrwd["xp"] > 0:
                                        from app.services.xp_service import grant_character_xp as _gcxp_l
                                        _gcxp_l(_lrwd_conn, character_id_val, _lrwd["xp"], reason=f"quest_complete:{_lq_item['title']}")
                                    if _lrwd["gold"] > 0:
                                        apply_grant_gold_to_character(_lrwd_conn, character_id=character_id_val, amount=_lrwd["gold"], source="quest_reward", campaign_id=campaign_id_val)
                                    logger.info("quest_completed_location", campaign_id=campaign_id_val, title=_lq_item["title"])
                                _lrwd_conn.commit()
                            finally:
                                _lrwd_conn.close()
                except Exception as _lqe:
                    logger.warning("location_quest_check_error", error=str(_lqe))
                # C10: include current active_quests in DONE payload
                done_payload["active_quests"] = _aq_current
            except Exception as _ws_err_s:
                logger.warning("world_state_snapshot_stream_error", error=str(_ws_err_s))

            # U30: include current_hex so frontend can sync map pin after each turn.
            # Computed BEFORE onboarding so the world_map card can trigger on it.
            try:
                _u30_conn = sqlite3.connect(DB_PATH)
                _u30_conn.row_factory = sqlite3.Row
                try:
                    _u30_extra = _build_done_extra_payload(campaign_id_val, _u30_conn)
                    done_payload.update(_u30_extra)
                finally:
                    _u30_conn.close()
            except Exception:
                pass

            # E25 + U20 (#572): inject onboarding cards into stream DONE payload
            try:
                from app.services.onboarding_service import inject_onboarding_to_out as _ob_inj_s
                _ob_dict = {
                    "result": {},
                    "skill_test_pending": done_payload.get("skill_test_pending"),
                    "combat_state": new_combat,
                    "current_hex": done_payload.get("current_hex"),
                }
                # U20: signal NPC dialogue so the crafter card can trigger
                try:
                    _utxt = _normalize_pl(user_text_val or "")
                    if (user_text_val or "").strip().upper().startswith("DIALOGUE:") or \
                       any(d in _utxt for d in _COMPOUND_DIALOGUE_MARKERS):
                        _ob_dict["npc_dialogue"] = True
                except Exception:
                    pass
                _ob_conn_s = sqlite3.connect(DB_PATH)
                _ob_conn_s.row_factory = sqlite3.Row
                _ob_inj_s(_ob_dict, user_id=int(character["user_id"]), conn=_ob_conn_s, character=character)
                done_payload["onboarding_cards"] = _ob_dict.get("onboarding_cards", [])
            except Exception:
                done_payload.setdefault("onboarding_cards", [])

            # U6 (#530): correction text computed after stream — frontend appends to bubble
            _u6s_na = locals().get("_u6s_live_correction")
            if _u6s_na:
                done_payload["narrative_append"] = _u6s_na

            # (legacy U30 block removed — current_hex now computed above before onboarding)
            if False:
                pass

            yield f"data: [DONE]{json.dumps(done_payload, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            token_generator(),
            media_type="text/event-stream",
            headers=stream_headers,
        )

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        conn.close()


@router.post("/campaigns/{campaign_id}/search")
def search_body_or_location(
    campaign_id: int,
    payload: SearchPayload,
):
    if not is_slash_command_enabled("/search"):
        raise HTTPException(
            status_code=403,
            detail="Komenda /search jest wyłączona przez administratora.",
        )
    conn = get_db()
    turn_id = _start_turn_trace(campaign_id, payload.character_id, "search")
    try:
        campaign = get_active_campaign_or_gone(conn, campaign_id)
        character = get_character_or_404(conn, campaign_id, payload.character_id)

        enemy_name = (payload.context or {}).get("enemy_name") or payload.target or "postać"

        if not payload.target:
            search_user_text = f"[Gracz przeszukuje: {enemy_name}]"
        else:
            search_user_text = f"[Gracz przeszukuje: {payload.target}]"

        llm_config = get_user_llm_settings_full(character["user_id"])
        model = resolve_model_name(
            requested_model=None,
            campaign_model=campaign["model_id"],
            llm_config=llm_config,
        )

        messages = build_narrative_messages(
            conn=conn,
            campaign=campaign,
            character=character,
            user_text=search_user_text,
            roll_result_message=None,
            roll_result_data=None,
        )

        answer = generate_chat(messages=messages, model=model, llm_config=llm_config)
        answer = (answer or "").strip()

        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            user_text=search_user_text,
            assistant_text=answer,
            route="narrative",
        )
        log_narrative_turn_structured(
            route="narrative",
            campaign_id=campaign_id,
            character_id=payload.character_id,
            turn_row=log,
            user_text=search_user_text,
            assistant_text=answer,
        )

        return {
            "answer": answer,
            "turn_number": log["turn_number"] if isinstance(log, dict) else None,
            "created_at": log["created_at"] if isinstance(log, dict) else None,
            "turn_id": turn_id,
        }
    finally:
        conn.close()


# ── Skill Test Resolution — Task 12 ──────────────────────────────────────────

class SkillTestResolvePayload(BaseModel):
    character_id: int
    skill_test_id: str
    d20_roll: int  # Stage 10-C+ — IGNORED: the authoritative roll is `pending.committed_d20`,
                   # rolled server-side at the moment the pending was committed. Kept in the
                   # schema for back-compat with old clients; not trusted for the outcome.


@router.post("/campaigns/{campaign_id}/skill-test/resolve")
def resolve_skill_test_endpoint(
    campaign_id: int,
    payload: SkillTestResolvePayload,
):
    """
    Player triggers resolution. Backend uses the server-committed d20 value
    (locked in when the pending was created) so a refresh-spammer cannot
    reroll. Returns prose + mechanic result.
    """
    import json as _json
    from app.services.skill_service import resolve_skill_test, build_skill_result_context
    from app.services.llm_service import generate_chat as _gen_chat
    from app.services.world_service import process_create_tags as _proc_tags, get_current_location_info

    conn = get_db()
    try:
        campaign = get_active_campaign_or_gone(conn, campaign_id)
        character = get_character_or_404(conn, campaign_id, payload.character_id)
        llm_config = get_user_llm_settings_full(character["user_id"])

        # Load session_flags and pending test
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            raise HTTPException(status_code=404, detail="No active game session")

        session_flags = _json.loads(gs["session_flags"] or "{}")
        pending = session_flags.get("pending_skill_test")
        if not pending:
            raise HTTPException(status_code=409, detail="No pending skill test in this session")
        if pending.get("skill_test_id") != payload.skill_test_id:
            raise HTTPException(status_code=409, detail="skill_test_id mismatch — wrong session?")

        # Stage 10-C+ cheat fix — use the SERVER-COMMITTED d20, not the client's claim.
        # Legacy pending dicts without `committed_d20` (pre-fix) fall back to the client value
        # and log a warning so we can spot any stale state.
        committed = pending.get("committed_d20")
        if committed is None:
            logger.warning(
                "skill_test_legacy_pending_no_committed_d20",
                campaign_id=campaign_id,
                skill_test_id=payload.skill_test_id,
                fallback_d20=payload.d20_roll,
            )
            committed = int(payload.d20_roll)
        committed = int(committed)
        if not (1 <= committed <= 20):
            raise HTTPException(status_code=500, detail=f"Invalid committed d20: {committed}")
        if committed != int(payload.d20_roll):
            logger.info(
                "skill_test_client_d20_overridden",
                campaign_id=campaign_id,
                committed=committed,
                client_claimed=int(payload.d20_roll),
            )

        # Resolve using the committed roll. S11 (#606): pass session_flags so a `cursed`
        # "zły omen" can force-reroll a favourable result (budget mutated into the dict
        # we persist below), and an `inspired` failure advertises reroll_available.
        result = resolve_skill_test(
            d20_roll=committed,
            pending=pending,
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            session_flags=session_flags,
        )

        # Clear pending state
        session_flags.pop("pending_skill_test", None)
        session_flags["state"] = "NARRATIVE"

        # S11 (#606): nieudany test z aktywnym `inspired` → stash kontekstu pod przerzut
        # gracza (keep-best). Endpoint /skill-test/reroll rzuca nowy serwerowy d20.
        if result.get("reroll_available"):
            session_flags["pending_reroll"] = {
                "skill_test_id": pending.get("skill_test_id"),
                "skill_key": result.get("skill_key"),
                "skill_label": result.get("skill_label"),
                "modifier": int(result.get("modifier", 0) or 0),
                "opponent_total": int(result.get("opponent_total", 0) or 0),
                "opponent_roll": result.get("opponent_roll"),
                "original_d20": int(result.get("d20_roll", 0) or 0),
                "condition_key": (result.get("reroll_available") or {}).get("condition_key"),
                "character_id": int(payload.character_id),
            }
        else:
            session_flags.pop("pending_reroll", None)

        # Stage 3 Z4 — stealth success → server-side zaskoczony
        # If active combat exists, apply zaskoczony to all alive enemies.
        # Otherwise, set session_flags.pending_zaskoczony=True so the
        # next [COMBAT_START:enemy_key] can pre-apply the condition.
        _stealth_applied: list[str] = []
        if str(pending.get("skill_key", "")).lower() == "stealth" and result.get("success") and not result.get("nat1"):
            try:
                from app.services.combat_service import get_active_combat, apply_condition_to_combatant
                _snap = get_active_combat(campaign_id)
                if _snap:
                    for _c in (_snap.get("combatants") or []):
                        if _c.get("type") == "player": continue
                        if int(_c.get("hp_current", 0) or 0) <= 0: continue
                        _ek = str(_c.get("enemy_key") or "")
                        if _ek:
                            _r = apply_condition_to_combatant(campaign_id, _ek, "zaskoczony")
                            if _r.get("ok"):
                                _stealth_applied.append(_ek)
                    logger.info("stealth_success_zaskoczony_applied",
                                campaign_id=campaign_id, enemies=_stealth_applied)
                else:
                    session_flags["pending_zaskoczony"] = True
                    logger.info("stealth_success_pending_zaskoczony", campaign_id=campaign_id)
            except Exception as _sa_err:
                logger.warning("stealth_zaskoczony_error", error=str(_sa_err))

        # S6 (#586) — haggling → jednorazowy rabat na najbliższą transakcję w sklepie.
        # Mechanika decyduje (stopień testu → mnożnik), LLM tylko narruje (CZĘŚĆ 10).
        if str(pending.get("skill_key", "")).lower() == "haggling":
            try:
                from app.services.haggle_service import apply_haggle_outcome
                _hg = apply_haggle_outcome(session_flags, result.get("outcome", "FAILURE"))
                logger.info("haggle_outcome_applied", campaign_id=campaign_id,
                            discount=_hg.get("discount"), blocked=_hg.get("blocked"))
            except Exception as _hg_err:
                logger.warning("haggle_outcome_error", error=str(_hg_err))

        # S7 (#601) — gamble → przepływ złota wg stopnia testu (S1). Stawka z pending
        # (zwalidowana przy intercepcie), złoto przez change_gold (U26). LLM narruje,
        # mechanika liczy (CZĘŚĆ 10). Krytyczna porażka → oskarżenie o oszustwo.
        _gamble_summary = _apply_gamble_in_skill(
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            pending=pending,
            session_flags=session_flags,
            result=result,
        )

        # S10 (#605) — deklaratywna ścieżka cure: udany SKILL_TEST oznaczony
        # cures_condition (z katalogu, np. medicine→hemorrhage) zdejmuje kondycję
        # z postaci. Mechanika decyduje (CZĘŚĆ 10); żadnego if skill_key == "medicine".
        _cured_condition = None
        _cure_key = str(pending.get("cures_condition") or "").strip().lower()
        if _cure_key and result.get("success") and not result.get("nat1"):
            try:
                from app.services.combat_service import remove_condition_from_character
                _n = remove_condition_from_character(conn, payload.character_id, campaign_id, _cure_key)
                if _n > 0:
                    _cured_condition = _cure_key
                logger.info("skill_test_cured_condition", campaign_id=campaign_id,
                            condition=_cure_key, removed=_n)
            except Exception as _cure_err:
                logger.warning("skill_test_cure_error", error=str(_cure_err))

        # S19 (#614) — deklaratywna ścieżka grant: udany SKILL_TEST oznaczony grants_condition_self
        # (z katalogu, np. stealth→hidden) NAKŁADA kondycję na postać. ODWROTNOŚĆ cure. Żaden if skill_key==.
        _granted_condition = None
        _grant_key = str(pending.get("grants_condition_self") or "").strip().lower()
        if _grant_key and result.get("success") and not result.get("nat1"):
            try:
                from app.services.combat_service import add_condition_to_character
                _gn = add_condition_to_character(conn, payload.character_id, campaign_id, _grant_key)
                if _gn > 0:
                    _granted_condition = _grant_key
                logger.info("skill_test_granted_condition", campaign_id=campaign_id,
                            condition=_grant_key, added=_gn)
            except Exception as _grant_err:
                logger.warning("skill_test_grant_error", error=str(_grant_err))

        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (_json.dumps(session_flags, ensure_ascii=False), campaign_id),
        )

        # Second narrator call
        skill_ctx = build_skill_result_context(result)
        nat_instruction = ""
        if result.get("nat20"):
            nat_instruction = "To był wyjątkowy sukces — pokaż coś nieoczekiwanego i korzystnego."
        elif result.get("nat1"):
            nat_instruction = "To był fumble — wprowadź komplikację, która stworzy przyszłe napięcie."

        # S7 (#601): gamble result feeds the narrator the gold flow (mechanika
        # already moved the gold via change_gold). Crit-fail → cheating accusation.
        skill_ctx += _build_gamble_narrator_ctx(_gamble_summary)

        # S11 (#606) — zły omen klątwy: udany test przerzucony na gorszy. Narrator dostaje
        # sygnał, by oddać złowrogi traf losu (BEZ podawania liczb/kości).
        if result.get("omen_applied"):
            skill_ctx += "\n[ZŁY OMEN] Klątwa zadziałała — w chwili sukcesu los obrócił się przeciw bohaterowi i wynik zmienił się na niekorzyść. Opisz złowrogi traf (cień klątwy), BEZ podawania liczb."

        # Inject in-game clock context so narrator matches actual time of day (#240)
        clock_hint = ""
        try:
            from app.services.clock_service import get_clock_state as _get_clock
            _clock = _get_clock(campaign_id, conn=conn)
            _hours = int(_clock.get("ingame_hours", 9) or 9)
            _mins = int(_clock.get("ingame_minutes", 0) or 0)
            _day = (_hours // 24) + 1
            _h = _hours % 24
            _hour_str = f"{_h:02d}:{_mins:02d}"
            if 5 <= _h < 9: _period = "świt"
            elif 9 <= _h < 13: _period = "rano"
            elif 13 <= _h < 17: _period = "południe"
            elif 17 <= _h < 20: _period = "popołudnie"
            elif 20 <= _h < 23: _period = "zmierzch"
            else: _period = "noc"
            clock_hint = f"[CZAS GRY] Dzień {_day}, {_hour_str} — {_period}. pora dnia MUSI być odzwierciedlona w narracji. "
        except Exception:
            pass

        # Inject current location + last turn context so narrator doesn't invent wrong setting (#1214)
        location_hint = ""
        last_turn_hint = ""
        try:
            _loc = get_current_location_info(conn, campaign_id)
            if _loc:
                location_hint = f"[LOKACJA] Bohater znajduje się w: {_loc['label']}. Narracja MUSI być osadzona w tej lokacji. "
        except Exception:
            pass
        try:
            _last = conn.execute(
                "SELECT assistant_text FROM campaign_turns WHERE campaign_id=? ORDER BY turn_number DESC LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if _last and _last[0]:
                _snippet = str(_last[0])[:400]
                last_turn_hint = f"[POPRZEDNIA NARRACJA (skrót)] {_snippet}\n\n"
        except Exception:
            pass

        # Stage 3 Z4 — stealth flavour hint when zaskoczony just applied
        stealth_hint = ""
        if _stealth_applied:
            stealth_hint = (
                " Cel/cele zostali zaskoczeni — opisz w narracji ich chwilową nieświadomość "
                "i przewagę gracza, ale NIE umieszczaj żadnych tagów w nawiasach kwadratowych."
            )
        elif str(pending.get("skill_key", "")).lower() == "stealth" and result.get("success"):
            stealth_hint = (
                " Skradanie się powiodło — opisz że bohater jest w cieniu, nieświadom wrogów; "
                "przewaga zaskoczenia zadziała w momencie rozpoczęcia walki."
            )

        narrator_prompt = (
            f"{last_turn_hint}"
            f"{skill_ctx}\n\n"
            f"{location_hint}"
            f"{clock_hint}"
            f"Napisz narrację wyniku testu umiejętności po polsku. "
            f"60-90 słów. Klimat dark fantasy. Nie wymieniaj liczb ani kości. "
            f"{nat_instruction}{stealth_hint}"
            f" ZAKAZANE: Nie używaj tagów [SKILL_TEST], [TRAP], roll_cue ani żadnych"
            f" znaczników mechanicznych — to jest wyłącznie narracja wyniku, nie nowy test."
        )
        try:
            prose_raw = _gen_chat(
                messages=[{"role": "user", "content": narrator_prompt}],
                llm_config=llm_config,
            ) or ""
        except Exception as e:
            logger.warning("skill_test_narrator_error", error=str(e))
            # Retry with server default (Ollama) if user config fails (e.g. quota/rate limit)
            try:
                from app.services.llm_service import get_effective_config as _get_eff
                _fallback_cfg = {"provider": "ollama", **_get_eff()}
                prose_raw = _gen_chat(
                    messages=[{"role": "user", "content": narrator_prompt}],
                    llm_config=_fallback_cfg,
                ) or ""
                logger.info("skill_test_narrator_fallback_ok")
            except Exception as e2:
                logger.warning("skill_test_narrator_fallback_error", error=str(e2))
                prose_raw = ""

        # Guard: if LLM returned None or empty (no exception raised), use a minimal
        # outcome line so the frontend always has prose to display. (#236)
        if not prose_raw.strip():
            _outcome_str = result.get("outcome", "")
            _skill_lbl = pending.get("skill_label") or pending.get("skill_key") or "Test"
            if result.get("nat20"):
                prose_raw = f"{_skill_lbl} — wyjątkowy sukces!"
            elif result.get("nat1"):
                prose_raw = f"{_skill_lbl} — fumble."
            elif "SUCCESS" in _outcome_str:
                prose_raw = f"{_skill_lbl} — sukces."
            else:
                prose_raw = f"{_skill_lbl} — niepowodzenie."
            logger.warning("skill_test_narrator_empty_fallback",
                           campaign_id=campaign_id, outcome=_outcome_str)

        prose, _ = _proc_tags(prose_raw, conn, campaign_id)

        # Log turn
        turn_number = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
            (campaign_id,),
        ).fetchone()[0]
        skill_label = pending.get("skill_label", pending.get("skill_key", "skill"))
        _mod = int(result.get("modifier") or 0)
        _total = int(result.get("player_total") or payload.d20_roll)
        if result.get("nat20"):
            _outcome = "Naturalny 20"
        elif result.get("nat1"):
            _outcome = "Naturalny 1"
        elif result.get("success"):
            _outcome = "Sukces"
        else:
            _outcome = "Porażka"
        _sign = "+" if _mod >= 0 else "−"
        # For opposed checks, append the opponent's result so the player knows why they succeeded/failed
        _opp_roll = result.get("opponent_roll")
        _opp_total = result.get("opponent_total")
        _counter = pending.get("counter", {})
        if _counter.get("counter_type") == "opposed" and _opp_roll is not None:
            _opp_key = _counter.get("counter_key", "przeciwnik")
            _opp_mod = (_opp_total or 0) - _opp_roll
            _opp_sign = "+" if _opp_mod >= 0 else "−"
            _opp_suffix = f" vs {_opp_key}: {_opp_roll} {_opp_sign}{abs(_opp_mod)} = {_opp_total}"
        else:
            _opp_suffix = ""
        _persisted_roll = (
            f"[Rzut: {skill_label} — {committed} {_sign}{abs(_mod)} = {_total}{_opp_suffix} — {_outcome}]"
        )
        conn.execute(
            """INSERT INTO campaign_turns
               (campaign_id, character_id, turn_number, user_text, assistant_text, route, created_at)
               VALUES (?,?,?,?,?,?,datetime('now'))""",
            (campaign_id, payload.character_id, turn_number,
             _persisted_roll, prose, "skill_test"),
        )
        conn.commit()

        # XS9/XS10/XS11: grant pending XP for successful skill check by DC
        if result.get("success") and not result.get("nat1"):
            try:
                _dc_val_st = None
                _counter = pending.get("counter") or {}
                if _counter.get("counter_type") == "dc":
                    _dc_val_st = _counter.get("dc")
                if _dc_val_st and int(_dc_val_st) >= 12:
                    from app.services.xp_sources import grant_skill_dc_success
                    grant_skill_dc_success(conn, int(payload.character_id), campaign_id, int(_dc_val_st), turn_number)
                    conn.commit()
            except Exception:
                pass

        char_state_row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (payload.character_id,)
        ).fetchone()
        char_sheet = _json.loads((char_state_row[0] if char_state_row else None) or "{}")
        current_loc = get_current_location_info(conn, campaign_id)

        # B5: auto-save World State snapshot after skill test resolves
        try:
            from app.services.world_state_service import auto_save_snapshot as _ws_snap_st
            _ws_snap_st(campaign_id)
        except Exception as _ws_err_st:
            logger.warning("world_state_snapshot_skilltest_error", error=str(_ws_err_st))

        _sa_after: list[dict] = []
        _travel_esc_st = 0
        try:
            _sf_st: dict = {}
            _sf_st_row = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if _sf_st_row:
                _sf_st = _json.loads(_sf_st_row[0] or "{}")
            _sa_after = build_suggested_actions(
                conn=conn,
                campaign_id=campaign_id,
                character_id=int(payload.character_id),
                game_state=_sf_st.get("state", "NARRATIVE"),
                session_flags=_sf_st,
            )
            _turns_stale_st = int(_sf_st.get("turns_at_location", 0) or 0)
            _travel_esc_st = 2 if _turns_stale_st >= 10 else (1 if _turns_stale_st >= 5 else 0)
        except Exception:
            pass

        # D1 (#780): bramka intencji — po sukcesie Stealth (przewaga pozycyjna bez
        # aktywnej walki) silnik STOP i pyta gracza zamiast cicho ustawiać flagę i
        # zależeć od LLM czy wybuchnie walka. Zwróć 3 przyciski do UI.
        _adv_gate = None
        try:
            from app.services.combat_service import build_advantage_gate
            if _sf_st.get("pending_zaskoczony"):
                _adv_gate = build_advantage_gate("stealth")
        except Exception as _gate_err:
            logger.warning("advantage_gate_build_error", error=str(_gate_err))

        _resp = {
            "prose": prose,
            "skill_test_result": result,
            "turn_number": turn_number,
            "suggested_actions": _sa_after,
            "travel_escalation_level": _travel_esc_st,
            "state": {
                "character_hp": char_sheet.get("current_hp"),
                "character_max_hp": char_sheet.get("max_hp"),
                "current_location": current_loc.get("key") if current_loc else None,
            },
        }
        if _adv_gate:
            _resp["advantage_gate"] = _adv_gate
        return _resp
    finally:
        conn.close()


class SkillTestRerollPayload(BaseModel):
    character_id: int
    skill_test_id: str


@router.post("/campaigns/{campaign_id}/skill-test/reroll")
def reroll_skill_test_endpoint(
    campaign_id: int,
    payload: SkillTestRerollPayload,
):
    """S11 (#606) — przerzut gracza (inspired, ``player_keep_best``).

    Po nieudanym teście z aktywnym ``inspired`` UI proponuje przerzut. Tu mechanika
    rzuca NOWY serwerowy d20, składa LEPSZY z dwóch (oryginał vs nowy), zużywa przerzut
    (zdejmuje inspired) i narruje wynik. Model committed-d20 zachowany — klient nie podaje
    rzutu, więc nie da się go nadużyć."""
    import json as _json
    import random as _random
    from app.services.skill_service import _derive_outcome, build_skill_result_context
    from app.services import reroll_service as _rr
    from app.services.llm_service import generate_chat as _gen_chat
    from app.services.world_service import process_create_tags as _proc_tags, get_current_location_info

    conn = get_db()
    try:
        campaign = get_active_campaign_or_gone(conn, campaign_id)
        character = get_character_or_404(conn, campaign_id, payload.character_id)
        llm_config = get_user_llm_settings_full(character["user_id"])

        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            raise HTTPException(status_code=404, detail="No active game session")
        session_flags = _json.loads(gs["session_flags"] or "{}")

        pr = session_flags.get("pending_reroll")
        if not pr:
            raise HTTPException(status_code=409, detail="No reroll available in this session")
        if pr.get("skill_test_id") != payload.skill_test_id:
            raise HTTPException(status_code=409, detail="skill_test_id mismatch — wrong reroll?")

        # Konsumuj przerzut (zdejmuje inspired gdy uses wyczerpane). Brak kondycji → 409.
        consumed = _rr.consume_player_reroll(conn, int(payload.character_id), campaign_id)
        if not consumed:
            session_flags.pop("pending_reroll", None)
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                (_json.dumps(session_flags, ensure_ascii=False), campaign_id),
            )
            conn.commit()
            raise HTTPException(status_code=409, detail="Reroll condition no longer active")

        modifier = int(pr.get("modifier", 0) or 0)
        opponent_total = int(pr.get("opponent_total", 0) or 0)
        original_d20 = int(pr.get("original_d20", 0) or 0)
        new_d20 = _random.randint(1, 20)
        kept_d20 = _rr.keep_better(original_d20, new_d20)
        derived = _derive_outcome(kept_d20, modifier, opponent_total)

        result = {
            "skill_key": pr.get("skill_key"),
            "skill_label": pr.get("skill_label", pr.get("skill_key")),
            "d20_roll": derived["d20_roll"],
            "modifier": modifier,
            "player_total": derived["player_total"],
            "opponent_total": opponent_total,
            "opponent_roll": pr.get("opponent_roll"),
            "margin": derived["margin"],
            "outcome": derived["outcome"],
            "nat20": derived["nat20"],
            "nat1": derived["nat1"],
            "success": derived["success"],
            "rerolled": True,
            "reroll_from_d20": original_d20,
            "reroll_new_d20": new_d20,
            "reroll_condition": consumed,
        }

        session_flags.pop("pending_reroll", None)
        session_flags["state"] = "NARRATIVE"
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (_json.dumps(session_flags, ensure_ascii=False), campaign_id),
        )

        skill_ctx = build_skill_result_context(result)
        skill_ctx += (
            "\n[PRZERZUT] Bohater wykorzystał przypływ inspiracji i przerzucił rzut — opisz "
            "ten drugi, pewniejszy wysiłek i jego wynik. BEZ podawania liczb i kości."
        )
        location_hint = ""
        try:
            _loc = get_current_location_info(conn, campaign_id)
            if _loc:
                location_hint = f"[LOKACJA] Bohater znajduje się w: {_loc['label']}. Narracja MUSI być osadzona w tej lokacji. "
        except Exception:
            pass

        narrator_prompt = (
            f"{skill_ctx}\n\n{location_hint}"
            f"Napisz narrację wyniku przerzuconego testu umiejętności po polsku. "
            f"60-90 słów. Klimat dark fantasy. Nie wymieniaj liczb ani kości. "
            f"ZAKAZANE: tagi [SKILL_TEST], [TRAP], roll_cue ani żadne znaczniki mechaniczne."
        )
        try:
            prose_raw = _gen_chat(messages=[{"role": "user", "content": narrator_prompt}], llm_config=llm_config) or ""
        except Exception as e:
            logger.warning("skill_reroll_narrator_error", error=str(e))
            prose_raw = ""
        if not prose_raw.strip():
            _lbl = result.get("skill_label") or "Test"
            prose_raw = f"{_lbl} — {'sukces' if result.get('success') else 'niepowodzenie'} po przerzucie."

        prose, _ = _proc_tags(prose_raw, conn, campaign_id)

        turn_number = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
            (campaign_id,),
        ).fetchone()[0]
        _outcome = "Sukces" if result.get("success") else "Porażka"
        _persisted_roll = (
            f"[Przerzut: {result.get('skill_label')} — {kept_d20} (z {original_d20}/{new_d20}) "
            f"+{modifier} = {derived['player_total']} — {_outcome}]"
        )
        conn.execute(
            """INSERT INTO campaign_turns
               (campaign_id, character_id, turn_number, user_text, assistant_text, route, created_at)
               VALUES (?,?,?,?,?,?,datetime('now'))""",
            (campaign_id, payload.character_id, turn_number, _persisted_roll, prose, "skill_reroll"),
        )
        conn.commit()

        char_state_row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (payload.character_id,)
        ).fetchone()
        char_sheet = _json.loads((char_state_row[0] if char_state_row else None) or "{}")
        current_loc = get_current_location_info(conn, campaign_id)

        return {
            "prose": prose,
            "skill_test_result": result,
            "turn_number": turn_number,
            "state": {
                "character_hp": char_sheet.get("current_hp"),
                "character_max_hp": char_sheet.get("max_hp"),
                "current_location": current_loc.get("key") if current_loc else None,
            },
        }
    finally:
        conn.close()


# ── Player World Map — Task 43 ────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/world-map")
def get_campaign_world_map(campaign_id: int, character_id: int = 0, parent_q: int = None, parent_r: int = None):
    """
    Player-facing hex world map with fog of war.
    Returns only discovered hexes + empty outlines for adjacent unvisited.
    Also includes current hex position from session_flags.
    """
    import json as _j
    import sqlite3 as _sq

    DB_PATH = "/data/ai_gm.db"
    conn = _sq.connect(DB_PATH)
    conn.row_factory = _sq.Row
    try:
        # Local submap mode — return all hexes for a specific city/castle
        if parent_q is not None and parent_r is not None:
            parent = conn.execute(
                "SELECT id, hex_type, label FROM world_hexes WHERE q = ? AND r = ? AND map_level = 0 LIMIT 1",
                (parent_q, parent_r),
            ).fetchone()
            if not parent:
                return {"hexes": [], "teleport_connections": [], "current_hex": None, "hex_types": {}, "local_mode": True, "parent_label": None}
            parent_id = parent["id"]
            local_hexes_rows = conn.execute(
                "SELECT q, r, hex_type, label, atmosphere FROM world_hexes WHERE parent_hex_id = ? AND map_level = 1 AND is_active = 1",
                (parent_id,),
            ).fetchall()
            # Auto-generate local submap on first zoom into a town/castle
            if not local_hexes_rows and parent["hex_type"] in ("town", "castle"):
                try:
                    from app.routers.hex_world import _auto_generate_local_hexes
                    _auto_generate_local_hexes(conn, parent_q, parent_r)
                    local_hexes_rows = conn.execute(
                        "SELECT q, r, hex_type, label, atmosphere FROM world_hexes WHERE parent_hex_id = ? AND map_level = 1 AND is_active = 1",
                        (parent_id,),
                    ).fetchall()
                except Exception:
                    pass
            local_hexes = [
                {"q": row["q"], "r": row["r"], "hex_type": row["hex_type"],
                 "label": row["label"], "status": "discovered"}
                for row in local_hexes_rows
            ]
            hex_types = {r["hex_type"]: dict(r) for r in conn.execute(
                "SELECT hex_type, label, map_color, map_icon FROM hex_type_config WHERE is_active = 1"
            ).fetchall()}
            return {
                "hexes": local_hexes,
                "teleport_connections": [],
                "current_hex": None,
                "hex_types": hex_types,
                "local_mode": True,
                "parent_label": parent["label"] or f"({parent_q},{parent_r})",
            }

        # Hex neighbour directions (flat-top)
        _DIRS = [(1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)]

        # All placed hexes (global layer)
        all_hexes = {
            (int(r["q"]), int(r["r"])): dict(r)
            for r in conn.execute(
                "SELECT q, r, hex_type, label, atmosphere, encounter_chance FROM world_hexes WHERE is_active = 1"
            ).fetchall()
        }

        # Current hex + auto-placement (must happen BEFORE building result_hexes)
        current_hex = None
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if gs:
            flags = _j.loads(gs["session_flags"] or "{}")
            current_hex = flags.get("current_hex")
            if not current_hex:
                # Auto-place: use proper resolve_starting_hex logic
                try:
                    from app.services.hex_travel_service import resolve_starting_hex
                    result = resolve_starting_hex(campaign_id, character_id, None, conn)
                    current_hex = {"q": result["q"], "r": result["r"]}
                except Exception:
                    pass

        # Campaign-specific discovered hexes
        discovered_coords = set()
        campaign_data = {}
        for row in conn.execute(
            "SELECT hex_q, hex_r, campaign_label, discovered FROM campaign_hex_data WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchall():
            q, r = int(row["hex_q"]), int(row["hex_r"])
            if row["discovered"]:
                discovered_coords.add((q, r))
            campaign_data[(q, r)] = dict(row)

        # Build result: discovered hexes + adjacent outlines
        result_hexes = []
        outline_coords = set()

        for coord in discovered_coords:
            hdata = all_hexes.get(coord, {})
            cd = campaign_data.get(coord, {})
            h = {
                "q": coord[0], "r": coord[1],
                "hex_type": hdata.get("hex_type", "plains"),
                "label": cd.get("campaign_label") or hdata.get("label"),
                "status": "discovered",
            }
            result_hexes.append(h)
            # Build adjacent unvisited outlines
            for dq, dr in _DIRS:
                nb = (coord[0]+dq, coord[1]+dr)
                if nb not in discovered_coords and nb in all_hexes:
                    outline_coords.add(nb)

        # Also expose all 6 neighbors of current hex so the player always sees
        # which directions they can travel from where they stand.
        # Real world_hexes neighbors → regular outline; phantom coords → 'unexplored'
        # (these will auto-generate a hex on travel via _auto_generate_hex).
        _unexplored_coords: set[tuple[int, int]] = set()
        if current_hex:
            ch = (int(current_hex["q"]), int(current_hex["r"]))
            for dq, dr in _DIRS:
                nb = (ch[0]+dq, ch[1]+dr)
                if nb not in discovered_coords:
                    if nb in all_hexes:
                        outline_coords.add(nb)
                    else:
                        _unexplored_coords.add(nb)

        for coord in outline_coords:
            result_hexes.append({"q": coord[0], "r": coord[1], "status": "outline",
                                  "hex_type": None, "label": None})
        for coord in _unexplored_coords:
            result_hexes.append({"q": coord[0], "r": coord[1], "status": "unexplored",
                                  "hex_type": None, "label": None})

        # Teleport connections (only where at least one endpoint is discovered)
        teleports = [dict(t) for t in conn.execute(
            "SELECT * FROM hex_teleport_connections WHERE is_active = 1"
        ).fetchall()]
        visible_teleports = [
            t for t in teleports
            if (t["from_q"], t["from_r"]) in discovered_coords
            or (t["to_q"], t["to_r"]) in discovered_coords
        ]

        # Hex type config for colours/icons
        hex_types = {r["hex_type"]: dict(r) for r in conn.execute(
            "SELECT hex_type, label, map_color, map_icon FROM hex_type_config WHERE is_active = 1"
        ).fetchall()}

        return {
            "hexes": result_hexes,
            "teleport_connections": visible_teleports,
            "current_hex": current_hex,
            "hex_types": hex_types,
        }
    finally:
        conn.close()


class HexTravelPayload(BaseModel):
    character_id: int
    destination_q: int
    destination_r: int


# ── U30: Unified travel endpoint ──────────────────────────────────────────────

class TravelPayload(BaseModel):
    character_id: int
    target_hex: dict | None = None           # {"q": int, "r": int}
    target_location_key: str | None = None   # resolved → hex via world_hexes.location_key


@router.post("/campaigns/{campaign_id}/travel")
def player_travel(campaign_id: int, payload: TravelPayload):
    """U30: Unified travel endpoint — accepts target_hex OR target_location_key."""
    import json as _j, sqlite3 as _sq
    from app.services.hex_travel_service import resolve_chain_travel, resolve_location_key_to_hex

    character_id = payload.character_id

    DB_PATH = "/data/ai_gm.db"
    conn = _sq.connect(DB_PATH)
    conn.row_factory = _sq.Row
    try:
        char = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? AND campaign_id = ?",
            (character_id, campaign_id),
        ).fetchone()
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        sheet = _j.loads(char["sheet_json"] or "{}")

        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        flags = _j.loads((gs["session_flags"] if gs else None) or "{}")
        ch = flags.get("current_hex")
        origin_exists = conn.execute(
            "SELECT 1 FROM world_hexes WHERE q=0 AND r=0 AND is_active=1"
        ).fetchone()

        # Resolve destination
        if payload.target_hex:
            dest_q = int(payload.target_hex.get("q", 0))
            dest_r = int(payload.target_hex.get("r", 0))
        elif payload.target_location_key:
            coords = resolve_location_key_to_hex(payload.target_location_key, conn)
            if coords is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Location '{payload.target_location_key}' not placed on any hex yet."
                )
            dest_q, dest_r = coords
        else:
            raise HTTPException(status_code=422, detail="Provide target_hex or target_location_key")

        from_hex = (int(ch["q"]), int(ch["r"])) if ch else ((0, 0) if origin_exists else (dest_q, dest_r))

        result = resolve_chain_travel(
            campaign_id=campaign_id, character_id=character_id,
            from_hex=from_hex, to_hex=(dest_q, dest_r),
            character_sheet=sheet, conn=conn,
        )

        try:
            from app.services.clock_service import advance_clock as _advance_clock
            travel_hours = float(result.get("total_hours") or 0.0)
            if travel_hours > 0:
                clock_state = _advance_clock(campaign_id, travel_hours, "travel", conn=conn)
                conn.commit()
                result["clock"] = clock_state
        except Exception as _clk_err:
            logger.warning("clock_advance_travel_failed", error=str(_clk_err), campaign_id=campaign_id)

        hex_row = conn.execute(
            "SELECT hex_type FROM world_hexes WHERE q=? AND r=? AND is_active=1 LIMIT 1",
            (dest_q, dest_r),
        ).fetchone()
        result["dungeon_prompt"] = bool(hex_row and hex_row["hex_type"] == "dungeon")

        # U31: exit old scene, load new scene if destination hex has a location
        try:
            from app.services.world_state_service import enter_location_scene, exit_location_scene
            exit_location_scene(campaign_id)
            dest_location_key = result.get("hex_data", {}).get("location_key")
            if dest_location_key:
                scene_result = enter_location_scene(campaign_id, dest_location_key)
                result["scene_loaded"] = scene_result
        except Exception as _scene_err:
            logger.warning("enter_location_scene_failed", error=str(_scene_err), campaign_id=campaign_id)

        # Record map travel as a narrative turn — without this the LLM conversation
        # history has no trace of the move and the narrator keeps describing the
        # previous location/terrain.
        if result.get("ok"):
            try:
                _hd = result.get("hex_data") or {}
                _arr = result.get("arrived_hex") or {}
                _terrain = _hd.get("hex_type") or "nieznany"
                _tcfg = conn.execute(
                    "SELECT label FROM hex_type_config WHERE hex_type = ?", (_terrain,)
                ).fetchone()
                _terrain_pl = (_tcfg["label"] if _tcfg else None) or _terrain
                _place = _hd.get("label") or ""
                _hours = result.get("total_hours") or 0
                _narr = f"Podróżujesz przez świat i docierasz do nowego miejsca. Teren: {_terrain_pl}."
                if _place:
                    _narr += f" Miejsce: {_place}."
                if _hours:
                    _narr += f" Droga zajęła {_hours} h."
                _tn_row = conn.execute(
                    "SELECT COALESCE(MAX(turn_number),0)+1 AS n FROM campaign_turns WHERE campaign_id = ?",
                    (campaign_id,),
                ).fetchone()
                conn.execute(
                    "INSERT INTO campaign_turns (campaign_id, character_id, user_text, route, assistant_text, turn_number) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        campaign_id, character_id,
                        "[Podróż mapą — przemieszczam się na nowy teren]",
                        "narrative",
                        _j.dumps({"narrative": _narr}, ensure_ascii=False),
                        int(_tn_row["n"]),
                    ),
                )
                conn.commit()
            except Exception as _trec_err:
                logger.warning("travel_turn_record_failed", error=str(_trec_err), campaign_id=campaign_id)

        return result
    finally:
        conn.close()


# ── U30: Helper to expose current_hex in [DONE] SSE payload ──────────────────

def _build_done_extra_payload(campaign_id: int, conn) -> dict:
    """U30: Return current_hex from session_flags for inclusion in [DONE] SSE metadata."""
    import json as _j
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if row:
            flags = _j.loads(row["session_flags"] or "{}")
            current_hex = flags.get("current_hex")
            if current_hex:
                return {"current_hex": current_hex}
    except Exception:
        pass
    return {}


@router.get("/campaigns/{campaign_id}/clock")
def get_campaign_clock(campaign_id: int):
    """Current in-game clock state for the campaign — Stage 2A T5.

    Returns `{ingame_hours, day, hour, hour_str, period, display}`.
    Frontend uses this to render the "Dzień 3, 14:00 Popołudnie" header.
    Returns a default state (hour 9 = start-of-campaign morning) if no
    session row exists yet.
    """
    from app.services.clock_service import get_clock_state
    return get_clock_state(campaign_id)


@router.post("/campaigns/{campaign_id}/hex-travel")
def player_hex_travel(campaign_id: int, payload: HexTravelPayload):
    """Player-initiated hex chain travel."""
    import json as _j, sqlite3 as _sq
    from app.services.hex_travel_service import resolve_chain_travel

    character_id = payload.character_id
    dest_q = payload.destination_q
    dest_r = payload.destination_r

    DB_PATH = "/data/ai_gm.db"
    conn = _sq.connect(DB_PATH)
    conn.row_factory = _sq.Row
    try:
        char = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? AND campaign_id = ?",
            (character_id, campaign_id),
        ).fetchone()
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        sheet = _j.loads(char["sheet_json"] or "{}")

        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        flags = _j.loads((gs["session_flags"] if gs else None) or "{}")
        ch = flags.get("current_hex")
        origin_exists = conn.execute(
            "SELECT 1 FROM world_hexes WHERE q=0 AND r=0 AND is_active=1"
        ).fetchone()
        from_hex = (int(ch["q"]), int(ch["r"])) if ch else ((0,0) if origin_exists else (dest_q, dest_r))

        result = resolve_chain_travel(
            campaign_id=campaign_id, character_id=character_id,
            from_hex=from_hex, to_hex=(dest_q, dest_r),
            character_sheet=sheet, conn=conn,
        )

        # T2: Advance the in-game clock by the hours travelled. resolve_chain_travel
        # already computed total_hours from the path + teleport edges; we just persist
        # it onto session_flags via the canonical helper.
        try:
            from app.services.clock_service import advance_clock as _advance_clock
            travel_hours = float(result.get("total_hours") or 0.0)
            if travel_hours > 0:
                clock_state = _advance_clock(campaign_id, travel_hours, "travel", conn=conn)
                conn.commit()  # _advance_clock uses caller conn, so we commit here
                result["clock"] = clock_state  # surface clock display + delta to client
        except Exception as _clk_err:  # noqa: BLE001 — log + degrade gracefully
            logger.warning("clock_advance_travel_failed", error=str(_clk_err), campaign_id=campaign_id)

        # E21: flag dungeon hexes so frontend auto-opens dungeon picker.
        # Check destination (not arrived_hex) — travel may fail but hex is still dungeon.
        hex_row = conn.execute(
            "SELECT hex_type FROM world_hexes WHERE q=? AND r=? AND is_active=1 LIMIT 1",
            (dest_q, dest_r),
        ).fetchone()
        result["dungeon_prompt"] = bool(hex_row and hex_row["hex_type"] == "dungeon")

        return result
    finally:
        conn.close()
