import json
import random
import uuid as _uuid

from app.core.logging import get_logger
from app.services.weapon_rules import is_attack_test

logger = get_logger(__name__)

_COMBAT_SKILL_EXCLUSIONS = (
    "attack", "ranged_attack", "two_handed", "melee_attack", "spell_attack", "initiative"
)


def _commit_pending_skill_test(pending: dict, session_flags: dict) -> dict:
    """Stage 10-C+ cheat fix — server-side d20 commitment.

    The d20 value is locked in at the moment the pending test is persisted.
    If the player refreshes the page mid-roll, they receive the SAME committed
    value next time the popup mounts — no reroll possible.

    Earlier versions trusted the client's `Math.random()` result, which let
    a refresh-spammer reroll until they got a high die.
    """
    if "committed_d20" not in pending:
        pending["committed_d20"] = random.randint(1, 20)
    session_flags["pending_skill_test"] = pending
    session_flags["state"] = "SKILL_TEST_PENDING"
    return session_flags


def route_skill_turn(
    *,
    conn,
    campaign_id,
    character_id,
    text,
    turn_id,
    character,
    llm_config,
    create_turn_log,
    _with_turn_trace,
    _normalize_pl,
    _kw_matches,
    _text_is_action_attempt,
    _is_reading_context,
    _is_compound_action,
):
    """Check if this turn should be routed through skill-test logic.

    Returns response dict if handled, None to continue to narrative.
    """
    # ── Skill test — explicit __ACTION:SKILL_ATTEMPT:key pattern ─────────
    _skill_action_m = None
    if text.startswith("__ACTION:SKILL_ATTEMPT:"):
        _skill_action_m = text.split(":", 2)[2].strip().lower() if ":" in text[len("__ACTION:SKILL_ATTEMPT:"):] or True else None
        _skill_action_m = text[len("__ACTION:SKILL_ATTEMPT:"):].strip().lower() or None

    if _skill_action_m:
        from app.services.skill_service import calc_skill_modifier_info, _skill_label, _get_counter
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
            _sf = _commit_pending_skill_test(_pending, _sf)
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                (json.dumps(_sf, ensure_ascii=False), campaign_id),
            )
            conn.commit()
        _stp_out = {"skill_test_pending": _pending, "prose": None, "route": "skill_test"}
        try:
            from app.services.onboarding_service import inject_onboarding_to_out as _ob_inj
            _ob_inj(_stp_out, user_id=int(character["user_id"]), conn=conn, character=character)
        except Exception:
            _stp_out.setdefault("onboarding_cards", [])
        return _with_turn_trace(_stp_out, turn_id)

    # ── Pre-LLM: scan player text against trigger_keywords ───────────────
    # If a keyword matches and we're not in combat, trigger skill test immediately.
    # Reading actions (issue #12 BUG-02) bypass this scanner so e.g. "odczytuję napis"
    # doesn't fire phantom Arkana — system prompt rule handles narration instead.
    # #457 (SB-4): skip scan when already SKILL_TEST_PENDING — re-firing would overwrite
    # the existing pending test and trap the player in an infinite keyword-scan loop.
    _kw_scan_sf_row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    _kw_scan_state = "NARRATIVE"
    if _kw_scan_sf_row:
        try:
            _kw_scan_state = json.loads(_kw_scan_sf_row["session_flags"] or "{}").get("state", "NARRATIVE")
        except Exception:
            pass
    _kw_scan_already_pending = _kw_scan_state == "SKILL_TEST_PENDING"

    # #457 (SB-3): when already SKILL_TEST_PENDING, re-surface existing pending test
    # without calling the narrative LLM. Player must resolve the roll before continuing.
    if _kw_scan_already_pending:
        _existing_sf = {}
        if _kw_scan_sf_row:
            try:
                _existing_sf = json.loads(_kw_scan_sf_row["session_flags"] or "{}")
            except Exception:
                pass
        _existing_pending = _existing_sf.get("pending_skill_test") or {}
        if _existing_pending:
            _sb5_committed = _existing_pending.get("committed_d20")
            if _sb5_committed is not None:
                # SB-5 fix: committed_d20 already set — auto-resolve inline instead of re-surfacing.
                # Player sent a regular turn while SKILL_TEST_PENDING; since the roll was locked in at
                # test creation, we can resolve immediately and return narrative prose.
                import json as _sb5_json
                from app.services.skill_service import resolve_skill_test as _sb5_rst, build_skill_result_context as _sb5_bsrc
                from app.services.llm_service import generate_chat as _sb5_gen
                from app.services.world_service import process_create_tags as _sb5_tags

                _sb5_committed = int(_sb5_committed)
                _sb5_res = _sb5_rst(
                    d20_roll=_sb5_committed,
                    pending=_existing_pending,
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=character_id,
                )

                # Clear pending state
                _existing_sf.pop("pending_skill_test", None)
                _existing_sf["state"] = "NARRATIVE"
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                    (_sb5_json.dumps(_existing_sf, ensure_ascii=False), campaign_id),
                )

                # Build narrator prompt
                _sb5_ctx = _sb5_bsrc(_sb5_res)
                _sb5_nat = ""
                if _sb5_res.get("nat20"):
                    _sb5_nat = "To był wyjątkowy sukces — pokaż coś nieoczekiwanego i korzystnego."
                elif _sb5_res.get("nat1"):
                    _sb5_nat = "To był fumble — wprowadź komplikację, która stworzy przyszłe napięcie."
                _sb5_prompt = (
                    f"{_sb5_ctx}\n\nNapisz narrację wyniku testu umiejętności po polsku. "
                    f"60-90 słów. Klimat dark fantasy. Nie wymieniaj liczb ani kości. "
                    f"{_sb5_nat}"
                    f" ZAKAZANE: Nie używaj tagów [SKILL_TEST], [TRAP], roll_cue ani żadnych znaczników mechanicznych."
                )
                try:
                    _sb5_prose_raw = _sb5_gen(
                        messages=[{"role": "user", "content": _sb5_prompt}],
                        llm_config=llm_config,
                    ) or ""
                except Exception:
                    _sb5_prose_raw = ""

                if not _sb5_prose_raw.strip():
                    _sb5_lbl = _existing_pending.get("skill_label") or _existing_pending.get("skill_key") or "Test"
                    if _sb5_res.get("nat20"): _sb5_prose_raw = f"{_sb5_lbl} — wyjątkowy sukces!"
                    elif _sb5_res.get("nat1"): _sb5_prose_raw = f"{_sb5_lbl} — fumble."
                    elif "SUCCESS" in str(_sb5_res.get("outcome", "")): _sb5_prose_raw = f"{_sb5_lbl} — sukces."
                    else: _sb5_prose_raw = f"{_sb5_lbl} — niepowodzenie."

                try:
                    _sb5_prose, _ = _sb5_tags(_sb5_prose_raw, conn, campaign_id)
                except Exception:
                    _sb5_prose = _sb5_prose_raw

                # Persist turn
                _sb5_tn = conn.execute(
                    "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
                    (campaign_id,),
                ).fetchone()[0]
                _sb5_lbl = _existing_pending.get("skill_label", _existing_pending.get("skill_key", "skill"))
                _sb5_mod = int(_sb5_res.get("modifier") or 0)
                _sb5_total = int(_sb5_res.get("player_total") or _sb5_committed)
                _sb5_sign = "+" if _sb5_mod >= 0 else "−"
                if _sb5_res.get("nat20"): _sb5_oc = "Naturalny 20"
                elif _sb5_res.get("nat1"): _sb5_oc = "Naturalny 1"
                elif _sb5_res.get("success"): _sb5_oc = "Sukces"
                else: _sb5_oc = "Porażka"
                _sb5_roll_str = f"[Rzut: {_sb5_lbl} — {_sb5_committed} {_sb5_sign}{abs(_sb5_mod)} = {_sb5_total} — {_sb5_oc}]"
                conn.execute(
                    """INSERT INTO campaign_turns
                       (campaign_id, character_id, turn_number, user_text, assistant_text, route, created_at)
                       VALUES (?,?,?,?,?,?,datetime('now'))""",
                    (campaign_id, character_id, _sb5_tn, _sb5_roll_str, _sb5_prose, "skill_test"),
                )
                conn.commit()

                try:
                    from app.services.world_state_service import auto_save_snapshot as _sb5_snap
                    _sb5_snap(campaign_id)
                except Exception:
                    pass

                return _with_turn_trace({
                    "prose": _sb5_prose,
                    "skill_test_result": _sb5_res,
                    "turn_number": _sb5_tn,
                    "route": "skill_test_auto_resolved",
                }, turn_id)
            else:
                # SB-3/SB-4: no committed_d20 — re-surface pending (backward compat)
                _log_re = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=character_id,
                    user_text=text,
                    assistant_text=None,
                    route="skill_test",
                )
                conn.commit()
                return _with_turn_trace({
                    "id": _log_re["id"],
                    "campaign_id": _log_re["campaign_id"],
                    "turn_number": _log_re["turn_number"],
                    "created_at": _log_re["created_at"],
                    "skill_test_pending": _existing_pending,
                    "prose": None,
                    "route": "skill_test",
                }, turn_id)

    if not _kw_scan_already_pending and not text.startswith("__AI_GM") and _text_is_action_attempt(text) and not _is_reading_context(text) and not _is_compound_action(text):
        try:
            # ── #616: deterministyczny tor hazardu (przed skanerem skilli/U7) ──
            # Gracz deklaruje stawkę ("stawiam 10 złota, gram w kości") → syntetyzuj
            # [GAMBLE:<stawka>:DC:<n>] i przepuść przez istniejący tor S7 ZANIM bramka
            # U7 / skaner skilli zżre turę generycznym testem (root cause #616). Mechanika
            # decyduje: walidacja stawki, limit gier na scenę i wypłata zostają w S7.
            from app.services.skill_service import detect_gamble_intent as _dgi_616
            _stake_616 = _dgi_616(text)
            if _stake_616 is not None:
                _active_combat_g = conn.execute(
                    "SELECT id FROM active_combat WHERE campaign_id = ? AND status = 'active' LIMIT 1",
                    (campaign_id,),
                ).fetchone()
                if not _active_combat_g:
                    from app.services.skill_service import (
                        intercept_skill_test_tag as _istt_616,
                        _get_counter as _gc_616,
                    )
                    _gdc_616 = int(_gc_616(conn, "gamble").get("dc", 12) or 12)
                    _synth_616 = f"[GAMBLE:{_stake_616}:DC:{_gdc_616}]"
                    _, _g_pending_616 = _istt_616(_synth_616, conn, campaign_id, character_id)
                    if _g_pending_616:
                        _gs_row_g = conn.execute(
                            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                            (campaign_id,),
                        ).fetchone()
                        if _gs_row_g:
                            _sf_g = json.loads(_gs_row_g["session_flags"] or "{}")
                            _sf_g = _commit_pending_skill_test(_g_pending_616, _sf_g)
                            conn.execute(
                                "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                                (json.dumps(_sf_g, ensure_ascii=False), campaign_id),
                            )
                            conn.commit()
                        logger.info("gamble_intent_routed", stake=_stake_616, dc=_gdc_616)
                        _log_g = create_turn_log(
                            conn=conn,
                            campaign_id=campaign_id,
                            character_id=character_id,
                            user_text=text,
                            assistant_text=None,
                            route="skill_test_keyword",
                        )
                        conn.commit()
                        return _with_turn_trace({
                            "id": _log_g["id"],
                            "campaign_id": _log_g["campaign_id"],
                            "turn_number": _log_g["turn_number"],
                            "created_at": _log_g["created_at"],
                            "skill_test_pending": _g_pending_616,
                            "prose": None,
                            "route": "skill_test_keyword",
                        }, turn_id)
                    # _g_pending_616 is None → stawka niepoprawna lub limit gier
                    # wyczerpany: NIE blokuj tury, spadnij do narracji (LLM narruje odmowę).
            _txt_pre = _normalize_pl(text)
            # Combat-class skills (attack / ranged_attack / two_handed) represent
            # weapon-modifier stats used during real combat resolution, not
            # standalone skill checks. Their trigger_keywords are combat verbs
            # and weapon names ("atakuję", "uderzam", "miecz dwuręczny", "łucznik")
            # which would otherwise spawn phantom skill tests outside combat,
            # producing GM narration that hallucinates an enemy. Exclude them
            # so player input routes through the intent parser → combat_start
            # path instead (issue #20 + Geralt two_handed regression).
            _kw_rows_pre = conn.execute(
                "SELECT key, trigger_keywords FROM game_config_skills "
                "WHERE trigger_keywords IS NOT NULL AND trigger_keywords != '' "
                "AND key NOT IN ('attack', 'ranged_attack', 'two_handed', 'melee_attack', 'spell_attack', 'initiative')"
            ).fetchall()
            _pre_match = None
            for _kr_pre in _kw_rows_pre:
                raw_kws = (_kr_pre["trigger_keywords"] or "").replace(",", " ")
                # Only use keywords ≥5 chars to avoid common particles like "sie", "cel"
                # K2 fix: use exact word-boundary match (not prefix) so "legend" does
                # not match "legendzie", "kronik" doesn't match "kroniki", etc.
                _kws_pre = [k.strip().lower().translate(str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ"))
                            for k in raw_kws.split()
                            if k.strip() and len(k.strip()) >= 5]
                if any(_kw_matches(kw, _txt_pre) for kw in _kws_pre):
                    _pre_match = _kr_pre["key"]
                    break
            if _pre_match and not is_attack_test(_pre_match):
                # Check not already in combat
                _active_combat_pre = conn.execute(
                    "SELECT id FROM active_combat WHERE campaign_id = ? AND status = 'active' LIMIT 1",
                    (campaign_id,),
                ).fetchone()
                if not _active_combat_pre:
                    from app.services.skill_service import calc_skill_modifier_info, _skill_label, _get_counter
                    import uuid as _uuid_pre
                    _char_sh_pre = json.loads(character["sheet_json"] or "{}")
                    _pending_pre = {
                        "skill_test_id": f"st-{_uuid_pre.uuid4().hex[:8]}",
                        "skill_key": _pre_match,
                        "skill_label": _skill_label(_pre_match),
                        "counter": _get_counter(conn, _pre_match),
                        "modifier_breakdown": calc_skill_modifier_info(_char_sh_pre, _pre_match),
                    }
                    gs_row_pre = conn.execute(
                        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                        (campaign_id,),
                    ).fetchone()
                    if gs_row_pre:
                        _sf_pre = json.loads(gs_row_pre["session_flags"] or "{}")
                        _sf_pre = _commit_pending_skill_test(_pending_pre, _sf_pre)
                        conn.execute(
                            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                            (json.dumps(_sf_pre, ensure_ascii=False), campaign_id),
                        )
                        conn.commit()
                    logger.info("skill_test_triggered_by_keywords", skill=_pre_match, text_snippet=text[:40])
                    # BUG-186: save turn row so turn_number is non-null
                    _log_pre = create_turn_log(
                        conn=conn,
                        campaign_id=campaign_id,
                        character_id=character_id,
                        user_text=text,
                        assistant_text=None,
                        route="skill_test_keyword",
                    )
                    conn.commit()
                    return _with_turn_trace({
                        "id": _log_pre["id"],
                        "campaign_id": _log_pre["campaign_id"],
                        "turn_number": _log_pre["turn_number"],
                        "created_at": _log_pre["created_at"],
                        "skill_test_pending": _pending_pre,
                        "prose": None,
                        "route": "skill_test_keyword",
                    }, turn_id)
        except Exception as _pre_err:
            logger.warning("pre_llm_keyword_scan_error: %s", str(_pre_err))

    return None
