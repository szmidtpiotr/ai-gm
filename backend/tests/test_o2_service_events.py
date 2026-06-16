"""O2 — Tests for event hooks in combat/death/beat/llm services."""
import json
import sqlite3
from unittest.mock import MagicMock, patch, call


def _make_combat_row(combatants=None, round_n=3, campaign_id=42, character_id=7):
    """Build a MagicMock sqlite3.Row-like for active_combat."""
    combatants_json = json.dumps(combatants or [
        {"type": "enemy", "enemy_key": "goblin", "hp_current": 0, "id": "goblin_0"},
        {"type": "player", "id": "player", "hp_current": 8},
    ])
    data = {
        "id": 1,
        "campaign_id": campaign_id,
        "character_id": character_id,
        "round": round_n,
        "combatants": combatants_json,
    }
    row = MagicMock()
    row.__getitem__ = lambda self, k: data[k]
    row.keys.return_value = list(data.keys())
    return row


# ── Combat service hooks ──────────────────────────────────────────────────────

def test_log_combat_end_victory_writes_combat_victory_event():
    """_log_combat_end_event('victory') → write_game_event('combat_victory', ...)."""
    row = _make_combat_row()
    conn = MagicMock()

    with patch("app.services.combat_service.write_game_event") as mock_evt, \
         patch("app.services.combat_service.log_combat_turn"), \
         patch("app.services.combat_service._next_combat_log_sequence", return_value=1.0), \
         patch("app.services.combat_service.logger"):
        from app.services.combat_service import _log_combat_end_event
        _log_combat_end_event(conn, row, "victory")

    mock_evt.assert_called_once()
    args = mock_evt.call_args[0]
    assert args[0] == "combat_victory"
    assert args[1] == 42   # campaign_id
    assert args[2] == 7    # character_id
    payload = args[4]
    assert payload["enemies_killed"] == 1
    assert "goblin" in payload["enemy_keys"]
    assert payload["rounds"] == 3


def test_log_combat_end_fled_writes_combat_fled_event():
    """_log_combat_end_event('fled') → write_game_event('combat_fled', ...)."""
    row = _make_combat_row()
    conn = MagicMock()

    with patch("app.services.combat_service.write_game_event") as mock_evt, \
         patch("app.services.combat_service.log_combat_turn"), \
         patch("app.services.combat_service._next_combat_log_sequence", return_value=1.0), \
         patch("app.services.combat_service.logger"):
        from app.services.combat_service import _log_combat_end_event
        _log_combat_end_event(conn, row, "fled")

    mock_evt.assert_called_once()
    args = mock_evt.call_args[0]
    assert args[0] == "combat_fled"
    assert args[1] == 42


def test_log_combat_end_player_dead_does_not_write_game_event():
    """player_dead reason → no combat_victory/fled, just regular end log."""
    row = _make_combat_row()
    conn = MagicMock()

    with patch("app.services.combat_service.write_game_event") as mock_evt, \
         patch("app.services.combat_service.log_combat_turn"), \
         patch("app.services.combat_service._next_combat_log_sequence", return_value=1.0), \
         patch("app.services.combat_service.logger"):
        from app.services.combat_service import _log_combat_end_event
        _log_combat_end_event(conn, row, "player_dead")

    mock_evt.assert_not_called()


# ── Solo death service hook ───────────────────────────────────────────────────

def test_end_solo_campaign_on_death_writes_player_death_event():
    """end_solo_campaign_on_death → write_game_event('player_death', severity='warning')."""
    ch_row = MagicMock()
    sheet = {"archetype": "warrior", "death_save_count": 2}
    ch_row.__getitem__ = lambda self, k: {
        "name": "Aldric",
        "sheet_json": json.dumps(sheet),
        "user_id": 5,
        "id": 7,
    }[k]

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = MagicMock(
        __getitem__=lambda self, k: {"model_id": "ollama", "owner_user_id": 5}[k],
        __iter__=lambda self: iter([]),
    )

    with patch("app.services.solo_death_service.write_game_event") as mock_evt, \
         patch("app.services.solo_death_service.generate_epitaph_llm", return_value="Epitaf testowy"), \
         patch("app.services.solo_death_service.get_user_llm_settings_full", return_value={"model": "ollama"}), \
         patch("app.services.solo_death_service.logger"):
        from app.services.solo_death_service import end_solo_campaign_on_death
        end_solo_campaign_on_death(conn, campaign_id=42, character_row=ch_row, death_reason="Poległ w walce")

    mock_evt.assert_called_once()
    args = mock_evt.call_args[0]
    kwargs = mock_evt.call_args[1]
    assert args[0] == "player_death"
    assert args[1] == 42   # campaign_id
    assert args[2] == 7    # character_id
    assert args[3] == 5    # user_id
    payload = args[4]
    assert payload["cause"] == "Poległ w walce"
    assert kwargs.get("severity") == "warning"


# ── Campaign plan beat_complete hook ─────────────────────────────────────────

def test_mark_beat_visited_writes_beat_complete_event():
    """mark_beat_visited newly marks beat → write_game_event('beat_complete', ...)."""
    plan = {
        "active_act": 1,
        "acts": [
            {"key_beats": [{"beat_key": "tavern_offer", "visited": False}]}
        ],
    }
    conn = MagicMock()

    with patch("app.services.campaign_plan_runtime.write_game_event") as mock_evt, \
         patch("app.services.campaign_plan_runtime.get_plan", return_value=plan), \
         patch("app.services.campaign_plan_runtime.save_plan"), \
         patch("app.services.campaign_plan_runtime.logger"):
        from app.services.campaign_plan_runtime import mark_beat_visited
        result = mark_beat_visited(42, "tavern_offer", 5, conn)

    assert result is True
    mock_evt.assert_called_once()
    args = mock_evt.call_args[0]
    assert args[0] == "beat_complete"
    assert args[1] == 42   # campaign_id
    payload = args[4]
    assert payload["beat_key"] == "tavern_offer"


def test_mark_beat_visited_already_done_does_not_write_event():
    """Already-visited beat → no event."""
    plan = {
        "active_act": 1,
        "acts": [{"key_beats": [{"beat_key": "tavern_offer", "visited": True}]}],
    }
    conn = MagicMock()

    with patch("app.services.campaign_plan_runtime.write_game_event") as mock_evt, \
         patch("app.services.campaign_plan_runtime.get_plan", return_value=plan), \
         patch("app.services.campaign_plan_runtime.logger"):
        from app.services.campaign_plan_runtime import mark_beat_visited
        result = mark_beat_visited(42, "tavern_offer", 5, conn)

    assert result is False
    mock_evt.assert_not_called()


# ── LLM service logging hook ──────────────────────────────────────────────────

def test_generate_chat_success_writes_llm_log():
    """generate_chat success → write_llm_log called with latency."""
    with patch("app.services.llm_service.write_llm_log") as mock_log, \
         patch("app.services.llm_service.get_effective_config", return_value={
             "provider": "ollama", "base_url": "http://x", "api_key": "", "model": "test"
         }), \
         patch("app.services.llm_service._resolve_model", return_value="test-model"), \
         patch("app.services.llm_service.OllamaDriver.generate_chat", return_value="Odpowiedź"), \
         patch("app.services.llm_service.logger"):
        from app.services.llm_service import generate_chat
        result = generate_chat([{"role": "user", "content": "test"}], call_type="narrator", campaign_id=42)

    assert result == "Odpowiedź"
    mock_log.assert_called_once()
    args = mock_log.call_args[0]
    assert args[0] == "narrator"
    assert args[1] == "test-model"
    assert args[2] >= 0   # latency_ms
    kwargs = mock_log.call_args[1]
    assert kwargs["campaign_id"] == 42
    assert kwargs["error"] is None


def test_generate_chat_timeout_writes_llm_log_with_error():
    """generate_chat timeout → write_llm_log with error='timeout', then raises."""
    import httpx
    with patch("app.services.llm_service.write_llm_log") as mock_log, \
         patch("app.services.llm_service.get_effective_config", return_value={
             "provider": "ollama", "base_url": "http://x", "api_key": "", "model": "test"
         }), \
         patch("app.services.llm_service._resolve_model", return_value="test-model"), \
         patch("app.services.llm_service.OllamaDriver.generate_chat", side_effect=httpx.TimeoutException("timeout")), \
         patch("app.services.llm_service.logger"):
        import pytest
        from app.services.llm_service import generate_chat
        with pytest.raises(RuntimeError, match="LLM timeout"):
            generate_chat([{"role": "user", "content": "test"}])

    mock_log.assert_called_once()
    kwargs = mock_log.call_args[1]
    assert kwargs["error"] == "timeout"
