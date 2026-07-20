"""O1+O2 — write_game_event() and write_llm_log() helpers. Best-effort: never raises."""
import json
import sqlite3
from app.core.db_runtime import resolve_db_path

DB_PATH = resolve_db_path()


def write_game_event(
    event_type,
    campaign_id,
    character_id,
    user_id,
    data,
    *,
    severity="info",
    conn=None,
):
    """Write a structured game event. Pass conn to reuse a transaction, else opens own."""
    _own = conn is None
    _c = None
    try:
        _c = conn or sqlite3.connect(DB_PATH)
        _c.execute(
            "INSERT INTO game_events "
            "(event_type, severity, campaign_id, character_id, user_id, event_data) "
            "VALUES (?,?,?,?,?,?)",
            (
                event_type,
                severity,
                campaign_id,
                character_id,
                user_id,
                json.dumps(data, ensure_ascii=False),
            ),
        )
        if _own:
            _c.commit()
    except Exception:
        pass
    finally:
        if _own and _c is not None:
            try:
                _c.close()
            except Exception:
                pass


def write_llm_log(
    call_type,
    model,
    latency_ms,
    *,
    campaign_id=None,
    prompt_tokens=0,
    completion_tokens=0,
    cache_hit=False,
    error=None,
    conn=None,
):
    """Write an LLM call log entry. Best-effort: never raises."""
    _own = conn is None
    _c = None
    try:
        _c = conn or sqlite3.connect(DB_PATH)
        _c.execute(
            "INSERT INTO llm_call_log "
            "(campaign_id, call_type, model, prompt_tokens, completion_tokens, latency_ms, cache_hit, error) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                campaign_id,
                call_type,
                model or "",
                prompt_tokens,
                completion_tokens,
                int(latency_ms),
                int(bool(cache_hit)),
                error,
            ),
        )
        if _own:
            _c.commit()
    except Exception:
        pass
    finally:
        if _own and _c is not None:
            try:
                _c.close()
            except Exception:
                pass
