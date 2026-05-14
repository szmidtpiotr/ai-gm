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
from app.services.weapon_rules import is_attack_test, resolve_attack_roll_for_weapon, resolve_sheet_weapon
from app.services.world_service import process_create_tags, get_current_location_info

router = APIRouter()
DB_PATH = "/data/ai_gm.db"
logger = get_logger(__name__)


COMBAT_START_RE = re.compile(r"\[COMBAT_START:([^\]]+)\]", re.IGNORECASE)
GRANT_ITEM_RE = re.compile(r"^Grant Item\s+(.+)$", re.IGNORECASE)
GRANT_GOLD_RE = re.compile(r"^Grant Gold\s+([+-]?\d+)$", re.IGNORECASE)
OPEN_SHOP_RE = re.compile(r"^Open Shop\s+(\S+)$", re.IGNORECASE)
# 9A-4c+ — gdy model nie generuje cue, dołącz „Open Shop” na podstawie intencji gracza i NPC w scenie.
_TRADE_USER_INTENT_RE = re.compile(
    r"(kup|sprzed|towar|towary|towarem|handl|handel|sklep|poka|pokaz"
    r"|masz\s+do|cen|koszt|zapła|zapla|cennik|asorty|ofert|kram|lad|ladę|ladą|kupiec|merch)",
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
    data = json.loads(_strip_json_code_fence(assistant_response))
    narrative = str(data.get("narrative") or "").rstrip()
    data["narrative"] = f"{narrative}\n\n[LOCATION_BLOCKED: {reason}]".strip()
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


def _maybe_start_combat_from_gm_tag(
    campaign_id: int, character_id: int, assistant_text: str
) -> dict | None:
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

    try:
        combat_state = cs.initiate_combat(campaign_id, character_id, enemy_keys)
        logger.info(
            "combat_gm_tag_started",
            campaign_id=campaign_id,
            enemy_keys=enemy_keys,
            combat_id=combat_state.get("id"),
        )
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

    combat = cs.get_active_combat(campaign_id)
    if not combat or str(combat.get("status") or "") != "active":
        return None
    if str(combat.get("current_turn") or "") != "player":
        return None

    turn_effects = cs.evaluate_current_turn_conditions(campaign_id)
    if not turn_effects.get("blocked"):
        return None

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
    combat_extra = _maybe_advance_combat_after_player_narrative(campaign_id)

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
    """
    try:
        parsed = json.loads(_strip_json_code_fence(text))
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
    return keys[0]


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


def extract_grant_cues(assistant_text: str) -> tuple[str, str | None, int | None, str | None]:
    """
    Collect GM grant cues from the end of assistant text.
    Supports both cue kinds and both orders when they are in trailing lines.
    Returns cleaned_text, grant_item_label, grant_gold_amount, open_shop_npc_key.
    """
    clean_text = (assistant_text or "").rstrip()
    grant_item_label: str | None = None
    grant_gold_amount: int | None = None
    open_shop_npc_key: str | None = None

    # JSON-mode GM response may carry Grant cue in `roll_cue` instead of last text line.
    try:
        payload = json.loads(_strip_json_code_fence(clean_text))
    except Exception:
        payload = None
    if isinstance(payload, dict):
        roll_cue = str(payload.get("roll_cue") or "").strip()
        if roll_cue:
            if grant_item_label is None:
                grant_item_label = parse_grant_item_cue(roll_cue)
            if grant_gold_amount is None:
                grant_gold_amount = parse_grant_gold_cue(roll_cue)
            if open_shop_npc_key is None:
                open_shop_npc_key = parse_open_shop_cue(roll_cue)
            if open_shop_npc_key is None:
                open_shop_npc_key = parse_open_shop_cue(roll_cue)
            if (
                grant_item_label is not None
                or grant_gold_amount is not None
                or open_shop_npc_key is not None
            ):
                payload["roll_cue"] = None
                clean_text = json.dumps(payload, ensure_ascii=False)

    for _ in range(4):
        if grant_item_label is None:
            maybe_item = parse_grant_item_cue(clean_text)
            if maybe_item:
                grant_item_label = maybe_item
                clean_text = strip_last_grant_item_cue(clean_text)
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
    return clean_text, grant_item_label, grant_gold_amount, open_shop_npc_key


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
    conn: sqlite3.Connection, *, character_id: int, amount: int
) -> int | None:
    if int(amount) <= 0:
        return None
    row = conn.execute(
        """
        UPDATE characters
        SET gold_gp = COALESCE(gold_gp, 0) + ?
        WHERE id = ?
        RETURNING gold_gp
        """,
        (int(amount), int(character_id)),
    ).fetchone()
    if not row:
        return None
    return int(row["gold_gp"] or 0)


def append_narrative_item_to_sheet(
    conn: sqlite3.Connection,
    *,
    character_id: int,
    label: str,
    source: str = "gm",
    given_at: str | None = None,
) -> None:
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?",
        (character_id,),
    ).fetchone()
    if not row:
        return
    try:
        sheet = json.loads(row["sheet_json"] or "{}") if row["sheet_json"] else {}
    except Exception:
        sheet = {}
    if not isinstance(sheet, dict):
        sheet = {}
    items = sheet.get("narrative_items")
    if not isinstance(items, list):
        items = []
    entry = {"label": str(label).strip(), "source": str(source or "gm").strip() or "gm"}
    if given_at:
        entry["given_at"] = str(given_at).strip()
    items.append(entry)
    sheet["narrative_items"] = items
    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )


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
    if effective["provider"] == "openai":
        return (req or cam or effective["model"]).strip()

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
    T05: don't run player→LLM narrative until campaigns.gm_plan_json is substantive,
    but only when there are no narrative turns yet (new campaign / plan failure).
    """
    from app.services.gm_plan_schema import gm_plan_is_ready

    try:
        raw = campaign["gm_plan_json"]
    except (KeyError, IndexError):
        raw = None
    if gm_plan_is_ready(raw):
        return
    if _narrative_turn_count(conn, campaign_id) > 0:
        return
    raise HTTPException(
        status_code=409,
        detail=(
            "Plan kampanii MG nie jest jeszcze gotowy. Poczekaj na zakończenie generacji po utworzeniu postaci "
            "lub poproś właściciela o ponowienie: POST /api/campaigns/{id}/gm-plan/generate-initial?user_id=…"
        ),
    )


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

    return {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "turn_number": row["turn_number"],
        "created_at": row["created_at"],
    }


# ---------------------------------------------------------------------------
# Helper: export session to text file
# ---------------------------------------------------------------------------

def _export_session_to_file(conn: sqlite3.Connection, campaign_id: int) -> str:
    """Writes all turns for campaign_id to /data/exports/campaign_<id>_<ts>.txt"""
    import time

    rows = conn.execute(
        """
        SELECT turn_number, user_text, assistant_text, created_at
        FROM campaign_turns
        WHERE campaign_id = ?
        ORDER BY turn_number ASC
        """,
        (campaign_id,),
    ).fetchall()

    campaign = conn.execute(
        "SELECT title, system_id FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()

    export_dir = "/data/exports"
    os.makedirs(export_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    filename = f"{export_dir}/campaign_{campaign_id}_{ts}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        title = campaign["title"] if campaign else f"Campaign {campaign_id}"
        system = campaign["system_id"] if campaign else "unknown"
        f.write(f"=== {title} [{system}] ===\n")
        f.write(f"Exported: {ts}\n")
        f.write("=" * 60 + "\n\n")

        for row in rows:
            f.write(f"[Turn {row['turn_number']}] {row['created_at']}\n")
            f.write(f"PLAYER: {row['user_text']}\n")
            if row["assistant_text"]:
                f.write(f"GM:     {row['assistant_text']}\n")
            f.write("\n")

    return filename


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
        llm_config = get_user_llm_settings_full(character["user_id"])
        text = (payload.text or "").strip()

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
            sk_dispatch = slash_registry_key_for_dispatch(text)
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

            # /export
            if cmd == "/export":
                filepath = _export_session_to_file(conn, campaign_id)
                result = {"command": "export", "file": filepath}
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)

            # /move — zmiana lokalizacji (Phase 8D)
            if cmd == "/move":
                target_location = text[5:].strip()  # Usuń "/move "
                if not target_location:
                    raise HTTPException(status_code=400, detail="Podaj nazwę lokalizacji: /move [nazwa]")
                
                # Sprawdź czy Location Integrity jest włączone
                if not get_bool_flag("location_integrity_enabled", campaign_id, default=True):
                    # System wyłączony — prosta zmiana bez walidacji
                    result = {"command": "move", "location": target_location, "mode": "bypass"}
                    log = create_turn_log(
                        conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                        user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                    )
                    return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)
                
                # Walidacja przez Location Validator
                from dataclasses import dataclass
                
                intent = LocationIntent(action="move", target_label=target_location)
                result = validate_move(campaign_id, intent)
                
                if result.allowed:
                    # Aktualizuj lokalizację w sesji
                    if result.resolved_location_id:
                        conn.execute(
                            "UPDATE game_sessions SET current_location_id = ? WHERE id = ?",
                            (result.resolved_location_id, campaign_id)
                        )
                        conn.commit()
                        
                        # Pobierz nazwę nowej lokalizacji
                        loc_row = conn.execute(
                            "SELECT label FROM game_locations WHERE id = ?",
                            (result.resolved_location_id,)
                        ).fetchone()
                        loc_name = loc_row["label"] if loc_row else target_location
                    else:
                        loc_name = target_location
                    
                    response_msg = f"Przenosisz się do: {loc_name}"
                    if result.is_new_location:
                        response_msg += " (nowa lokalizacja utworzona)"
                    
                    result_data = {
                        "command": "move",
                        "location": loc_name,
                        "allowed": True,
                        "is_new": result.is_new_location
                    }
                else:
                    # Blokada — loguj próbę
                    log_integrity_violation(campaign_id, intent, result.block_reason or "Nieznany powód")
                    
                    response_msg = f"Nie możesz się tam przenieść: {result.block_reason}"
                    result_data = {
                        "command": "move",
                        "location": target_location,
                        "allowed": False,
                        "reason": result.block_reason
                    }
                
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=response_msg, route=route,
                )
                return _with_turn_trace({**log, "route": "command", "result": result_data}, turn_id)

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

        # ── Skill test — explicit __ACTION:SKILL_ATTEMPT:key pattern ─────────
        _skill_action_m = None
        if text.startswith("__ACTION:SKILL_ATTEMPT:"):
            _skill_action_m = text.split(":", 2)[2].strip().lower() if ":" in text[len("__ACTION:SKILL_ATTEMPT:"):] or True else None
            _skill_action_m = text[len("__ACTION:SKILL_ATTEMPT:"):].strip().lower() or None

        if _skill_action_m:
            from app.services.skill_service import calc_skill_modifier_info, _skill_label, _get_counter
            import uuid as _uuid
            char_sheet = json.loads(character["sheet_json"] or "{}")
            sk = _skill_action_m
            mod_info = calc_skill_modifier_info(char_sheet, sk)
            counter = _get_counter(conn, sk)
            _pending = {
                "skill_test_id": f"st-{_uuid.uuid4().hex[:8]}",
                "skill_key": sk,
                "skill_label": _skill_label(sk),
                "counter": counter,
                "modifier_breakdown": mod_info,
            }
            gs_row = conn.execute(
                "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if gs_row:
                _sf = json.loads(gs_row["session_flags"] or "{}")
                _sf["pending_skill_test"] = _pending
                _sf["state"] = "SKILL_TEST_PENDING"
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                    (json.dumps(_sf, ensure_ascii=False), campaign_id),
                )
                conn.commit()
            return _with_turn_trace({"skill_test_pending": _pending, "prose": None, "route": "skill_test"}, turn_id)

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

        result = run_narrative_turn(
            conn=conn,
            campaign=campaign,
            character=character,
            user_text=text,
            model=model,
            ollama_base_url=x_ollama_base_url,
            llm_config=llm_config,
            roll_result_message=roll_result_message,
            roll_result_data=roll_result_data,
        )

        assistant_text = (result.get("message") or "").strip()
        if not assistant_text:
            raise HTTPException(status_code=500, detail="Empty narrative response")
        assistant_text = _process_location_intent(
            conn=conn,
            campaign_id=campaign_id,
            assistant_response=assistant_text,
        )

        # ── [SKILL_TEST:] / [TRAP:] tag interception ─────────────────────────
        _skill_pending_narrator = None
        try:
            from app.services.skill_service import intercept_skill_test_tag, intercept_trap_tag, calc_skill_modifier_info
            import uuid as _uuid2
            _char_sh = json.loads(character["sheet_json"] or "{}")
            assistant_text, _skill_pending_narrator = intercept_skill_test_tag(
                assistant_text, conn, campaign_id, payload.character_id
            )
            if not _skill_pending_narrator:
                assistant_text, _skill_pending_narrator = intercept_trap_tag(
                    assistant_text, conn, campaign_id, payload.character_id, _char_sh
                )
            if _skill_pending_narrator:
                gs_row2 = conn.execute(
                    "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                    (campaign_id,),
                ).fetchone()
                if gs_row2:
                    _sf2 = json.loads(gs_row2["session_flags"] or "{}")
                    _sf2["pending_skill_test"] = _skill_pending_narrator
                    _sf2["state"] = "SKILL_TEST_PENDING"
                    conn.execute(
                        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                        (json.dumps(_sf2, ensure_ascii=False), campaign_id),
                    )
                    conn.commit()
        except Exception as _se:
            logger.warning("skill_tag_intercept_error: %s", str(_se))

        from app.services import combat_service as _cs

        combat_before = _cs.get_active_combat(campaign_id)
        combat_was_active = bool(combat_before) and str(
            combat_before.get("current_turn") or ""
        ) == "player"

        clean_assistant = COMBAT_START_RE.sub("", assistant_text).rstrip()
        clean_assistant = maybe_append_open_shop_fallback(conn, campaign_id, text, clean_assistant)
        _narrative_for_cues, _parsed_json = _extract_narrative_for_cues(clean_assistant)
        _narrative_for_cues, grant_item_label, grant_gold_amount, open_shop_npc_key = extract_grant_cues(
            _narrative_for_cues
        )
        clean_assistant = _repack_narrative(clean_assistant, _narrative_for_cues, _parsed_json)
        validate_roll_cue_name(clean_assistant.strip())

        # ── roll_cue skill test intercept ─────────────────────────────────────
        # When narrator emits roll_cue:"Roll Arcana d20" (not an attack), convert
        # it to skill_test_pending so the Roll Popup appears.
        if _parsed_json and not _skill_pending_narrator:
            _raw_cue = str(_parsed_json.get("roll_cue") or "").strip()
            if _raw_cue:
                import re as _rc_re
                _cm = _rc_re.match(r"^Roll (.+?) d\d+$", _raw_cue, _rc_re.IGNORECASE)
                if _cm:
                    _cue_name = _cm.group(1).strip()
                    _canonical = resolve_test_name(_cue_name)
                    if _canonical and not is_attack_test(_canonical):
                        # It's a skill, not an attack — show Roll Popup
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
                                _sf3["pending_skill_test"] = _skill_pending_narrator
                                _sf3["state"] = "SKILL_TEST_PENDING"
                                conn.execute(
                                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                                    (json.dumps(_sf3, ensure_ascii=False), campaign_id),
                                )
                                conn.commit()
                        except Exception as _e3:
                            logger.warning("roll_cue_session_store_error: %s", str(_e3))

        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            user_text=user_text_stored if roll_request else text,
            assistant_text=clean_assistant,
            route=route,
        )
        log_narrative_turn_structured(
            route=route,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            turn_row=log,
            user_text=user_text_stored if roll_request else text,
            assistant_text=clean_assistant,
        )
        if grant_item_label:
            resolved = _resolve_grant_catalog_item(conn, grant_item_label)
            if resolved:
                from app.services.loot_service import grant_loot_to_character

                grant_loot_to_character(
                    int(payload.character_id),
                    [{"item_key": resolved["item_key"], "quantity": 1}],
                    source="gm_grant_item",
                )
                logger.info(
                    "grant_item_catalog",
                    character_id=payload.character_id,
                    item_key=resolved["item_key"],
                    label=grant_item_label,
                )
            else:
                append_narrative_item_to_sheet(
                    conn,
                    character_id=payload.character_id,
                    label=grant_item_label,
                    source="gm",
                    given_at=f"turn:{log['turn_number']}",
                )
            conn.commit()
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

        new_combat = _maybe_start_combat_from_gm_tag(
            campaign_id, payload.character_id, assistant_text
        )
        combat_extra = None
        if combat_was_active and not new_combat:
            combat_extra = _maybe_advance_combat_after_player_narrative(campaign_id)

        result_out = (
            {**result, "message": clean_assistant} if isinstance(result, dict) else result
        )

        out: dict = {
            "id": log["id"],
            "campaign_id": log["campaign_id"],
            "turn_number": log["turn_number"],
            "created_at": log["created_at"],
            "route": "narrative",
            "result": result_out,
            "prose": clean_assistant,
            "turn_id": turn_id,
        }
        if _skill_pending_narrator:
            out["skill_test_pending"] = _skill_pending_narrator
        if new_combat is not None:
            out["combat_state"] = new_combat
        if combat_extra:
            out.update(combat_extra)
        if open_shop_npc_key:
            out["open_shop"] = open_shop_npc_key
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
            sk_stream = slash_registry_key_for_dispatch(text)
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

            def command_stream():
                yield f"data: [CMD] {text}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(
                command_stream(),
                media_type="text/event-stream",
                headers=stream_headers,
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

        location_skip_post_location_hook = _inject_pre_llm_unknown_location_denial(
            conn, campaign_id, text, messages
        )

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
                    new_combat = _maybe_start_combat_from_gm_tag(
                        campaign_id_val, character_id_val, clean_text
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
                yield "data: [DONE]\n\n"
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
            if full_raw.strip():
                clean_text = COMBAT_START_RE.sub("", full_raw).rstrip()
                fb = get_db()
                try:
                    clean_text = maybe_append_open_shop_fallback(
                        fb, campaign_id_val, user_text_val, clean_text
                    )
                finally:
                    fb.close()
                _narrative_for_cues_s, _parsed_json_s = _extract_narrative_for_cues(clean_text)
                (
                    _narrative_for_cues_s,
                    grant_item_label,
                    grant_gold_amount,
                    open_shop_npc_key,
                ) = extract_grant_cues(_narrative_for_cues_s)
                clean_text = _repack_narrative(clean_text, _narrative_for_cues_s, _parsed_json_s)
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
                    if grant_item_label:
                        resolved = _resolve_grant_catalog_item(save_conn, grant_item_label)
                        if resolved:
                            from app.services.loot_service import grant_loot_to_character

                            grant_loot_to_character(
                                int(character_id_val),
                                [{"item_key": resolved["item_key"], "quantity": 1}],
                                source="gm_grant_item",
                            )
                            logger.info(
                                "grant_item_catalog",
                                character_id=character_id_val,
                                item_key=resolved["item_key"],
                                label=grant_item_label,
                            )
                        else:
                            append_narrative_item_to_sheet(
                                save_conn,
                                character_id=character_id_val,
                                label=grant_item_label,
                                source="gm",
                                given_at=f"turn:{stream_log['turn_number']}",
                            )
                        save_conn.commit()
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
                    new_combat = _maybe_start_combat_from_gm_tag(
                        campaign_id_val, character_id_val, full_raw
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
            if open_shop_npc_key:
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

            # Include current_location in DONE payload
            done_payload = {}
            if loc_info:
                done_payload["current_location"] = loc_info
            if done_payload:
                yield f"data: [DONE]{json.dumps(done_payload, ensure_ascii=False)}\n\n"
            else:
                yield "data: [DONE]\n\n"

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
    d20_roll: int  # 1–20, client-generated


@router.post("/campaigns/{campaign_id}/skill-test/resolve")
def resolve_skill_test_endpoint(
    campaign_id: int,
    payload: SkillTestResolvePayload,
):
    """
    Player sends their d20 roll. Backend resolves the pending skill test,
    makes a second narrator LLM call, and returns prose + mechanic result.
    """
    import json as _json
    from app.services.skill_service import resolve_skill_test, build_skill_result_context
    from app.services.llm_service import generate_chat as _gen_chat
    from app.services.world_service import process_create_tags as _proc_tags, get_current_location_info

    if not (1 <= payload.d20_roll <= 20):
        raise HTTPException(status_code=400, detail="d20_roll must be 1–20")

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

        # Resolve
        result = resolve_skill_test(
            d20_roll=payload.d20_roll,
            pending=pending,
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
        )

        # Clear pending state
        session_flags.pop("pending_skill_test", None)
        session_flags["state"] = "NARRATIVE"
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

        narrator_prompt = (
            f"{skill_ctx}\n\n"
            f"Napisz narrację wyniku testu umiejętności po polsku. "
            f"60-90 słów. Klimat dark fantasy. Nie wymieniaj liczb ani kości. "
            f"{nat_instruction}"
        )
        try:
            prose_raw = _gen_chat(
                messages=[{"role": "user", "content": narrator_prompt}],
                llm_config=llm_config,
            ) or ""
        except Exception as e:
            logger.warning("skill_test_narrator_error", error=str(e))
            outcome = result.get("outcome", "")
            prose_raw = "Sukces!" if "SUCCESS" in outcome else "Niepowodzenie."

        prose, _ = _proc_tags(prose_raw, conn, campaign_id)

        # Log turn
        turn_number = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
            (campaign_id,),
        ).fetchone()[0]
        skill_label = pending.get("skill_label", pending.get("skill_key", "skill"))
        conn.execute(
            """INSERT INTO campaign_turns
               (campaign_id, character_id, turn_number, user_text, assistant_text, route, created_at)
               VALUES (?,?,?,?,?,?,datetime('now'))""",
            (campaign_id, payload.character_id, turn_number,
             f"[Rzut: {skill_label} — {payload.d20_roll}]", prose, "skill_test"),
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
