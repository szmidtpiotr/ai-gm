"""TDD: Issue #792 — G8 dwuprzebiegowe rzuty w rundzie MP.

Planer LLM → kod rzuca resolve_roll → narrator LLM z wynikami jako faktami.
"""
import json
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/app")

from app.services import multiplayer_round_service as mrs


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _sheet(dex=10, str_val=10, skills=None):
    return json.dumps({
        "stats": {
            "STR": str_val, "DEX": dex, "CON": 10,
            "INT": 10, "WIS": 10, "CHA": 10, "LCK": 10,
        },
        "skills": skills or {},
    })


def _make_round_row(**overrides):
    data = {"status": "narrating", "campaign_id": 1, "round_number": 1}
    data.update(overrides)
    r = MagicMock()
    r.__getitem__ = lambda self, k: data.get(k)
    r.__bool__ = lambda self: True
    return r


def _make_action_row(char_name="Aldric", char_id=201, user_id=101, initiative=10, action="Idę"):
    data = {
        "character_name": char_name, "action_text": action,
        "user_id": user_id, "initiative_roll": initiative, "character_id": char_id,
    }
    r = MagicMock()
    r.__getitem__ = lambda self, k: data.get(k)
    return r


def _make_sheet_row(sheet_json):
    r = MagicMock()
    r.__getitem__ = lambda self, k: {"sheet_json": sheet_json}.get(k)
    return r


def _setup_db_mock(mock_db, round_row, action_rows, sheet_by_char_id, saved_data=None):
    """Wire a mock _db() to return appropriate rows for each SQL query."""
    mock_conn = MagicMock()
    mock_db.return_value = mock_conn

    def execute_side(sql, *args, **kwargs):
        result = MagicMock()
        result.fetchone.return_value = None
        result.fetchall.return_value = []

        if "UPDATE campaign_rounds" in sql and "narrative_json" in sql and saved_data is not None:
            payload = args[0][0] if args and args[0] else None
            saved_data["json"] = payload

        elif "campaign_rounds" in sql and "WHERE" in sql and "UPDATE" not in sql:
            result.fetchone.return_value = round_row

        elif "campaign_round_actions" in sql and "SELECT" in sql:
            result.fetchall.return_value = action_rows

        elif "characters" in sql and "sheet_json" in sql:
            char_id = args[0][0] if args and args[0] else 0
            result.fetchone.return_value = sheet_by_char_id.get(int(char_id))

        return result

    mock_conn.execute.side_effect = execute_side
    return mock_conn


def _setup_llm_mock(mock_llm, *responses):
    """Wire llm_service to return responses in order from OpenAIDriver."""
    mock_cfg = {"provider": "openai", "base_url": "", "model": "gpt-4", "api_key": ""}
    mock_llm.get_effective_config.return_value = mock_cfg
    driver = MagicMock()
    driver.generate_chat.side_effect = list(responses)
    mock_llm.OpenAIDriver.return_value = driver
    return driver


# ─── RED: Core G8 behaviours ─────────────────────────────────────────────────

def test_g8_trigger_narration_makes_two_llm_calls():
    """trigger_narration must make exactly 2 LLM calls: planner then narrator."""
    planner_out = json.dumps([{"character_name": "Aldric", "test": "stealth", "dc": 12}])
    narrator_out = json.dumps({"narrative": "Aldric skrada się.", "player_notes": {}})

    saved = {}
    with patch("app.services.multiplayer_round_service._db") as mock_db, \
         patch("app.services.multiplayer_round_service.llm_service") as mock_llm:

        _setup_db_mock(
            mock_db,
            _make_round_row(),
            [_make_action_row(char_id=201)],
            {201: _make_sheet_row(_sheet(dex=14))},
            saved,
        )
        summary_out = json.dumps({"summary": "Krótkie podsumowanie."})
        driver = _setup_llm_mock(mock_llm, planner_out, narrator_out, summary_out)

        mrs.trigger_narration(1)

    assert driver.generate_chat.call_count >= 2, (
        f"Expected at least 2 LLM calls (planner + narrator), got {driver.generate_chat.call_count}"
    )


def test_g8_narrator_receives_roll_results_in_user_message():
    """Second LLM call (narrator) must receive roll results as immutable facts in user msg."""
    planner_out = json.dumps([
        {"character_name": "Aldric", "test": "stealth", "dc": 12},
        {"character_name": "Mira", "test": "persuasion", "dc": 16},
    ])
    narrator_out = json.dumps({"narrative": "Walka!", "player_notes": {}})

    captured = {}

    def fake_generate(base_url, model, messages, api_key=""):
        user_text = messages[-1]["content"] if messages else ""
        call_n = captured.get("call_count", 0)
        captured["call_count"] = call_n + 1
        # Call 1: planner (returns JSON list), Call 2: narrator (has roll results)
        # Call 3+: round summary or other — return safe fallback
        if call_n == 0:
            return planner_out
        if call_n == 1:
            captured["narrator_user"] = user_text
            return narrator_out
        return json.dumps({"summary": "."})  # safe fallback for extra calls (e.g. G18 summary)

    with patch("app.services.multiplayer_round_service._db") as mock_db, \
         patch("app.services.multiplayer_round_service.llm_service") as mock_llm:

        _setup_db_mock(
            mock_db,
            _make_round_row(),
            [
                _make_action_row("Aldric", 201, 101),
                _make_action_row("Mira", 202, 102),
            ],
            {
                201: _make_sheet_row(_sheet(dex=14)),
                202: _make_sheet_row(_sheet(str_val=12)),
            },
        )
        mock_cfg = {"provider": "openai", "base_url": "", "model": "gpt-4", "api_key": ""}
        mock_llm.get_effective_config.return_value = mock_cfg
        driver = MagicMock()
        driver.generate_chat.side_effect = fake_generate
        mock_llm.OpenAIDriver.return_value = driver

        mrs.trigger_narration(1)

    narrator_msg = captured.get("narrator_user", "")
    assert narrator_msg, "Narrator LLM was never called"
    # narrator message must include roll result data (DC + wynik)
    assert "12" in narrator_msg or "DC" in narrator_msg or "stealth" in narrator_msg.lower(), (
        f"Narrator user message doesn't contain roll result data.\nGot: {narrator_msg[:300]}"
    )


def test_g8_roll_facts_saved_in_narrative_json():
    """narrative_json stored in DB must include roll_facts list."""
    planner_out = json.dumps([{"character_name": "Aldric", "test": "stealth", "dc": 12}])
    narrator_out = json.dumps({
        "narrative": "🎲 Skradanie: 15 vs DC 12 ✓",
        "player_notes": {},
    })

    saved = {}
    with patch("app.services.multiplayer_round_service._db") as mock_db, \
         patch("app.services.multiplayer_round_service.llm_service") as mock_llm:

        _setup_db_mock(
            mock_db,
            _make_round_row(),
            [_make_action_row(char_id=201)],
            {201: _make_sheet_row(_sheet(dex=14))},
            saved,
        )
        _setup_llm_mock(mock_llm, planner_out, narrator_out)

        mrs.trigger_narration(1)

    assert saved.get("json"), "narrative_json was not saved to DB"
    data = json.loads(saved["json"])
    assert "roll_facts" in data, (
        f"roll_facts missing from narrative_json. Keys present: {list(data.keys())}"
    )
    facts = data["roll_facts"]
    assert isinstance(facts, list), f"roll_facts must be a list, got {type(facts)}"
    assert len(facts) == 1, f"Expected 1 roll_fact, got {len(facts)}: {facts}"
    f = facts[0]
    for key in ("character_name", "test", "raw", "total", "dc", "success", "is_nat20", "is_nat1"):
        assert key in f, f"roll_fact missing field '{key}'. Fact: {f}"


def test_g8_two_players_two_roll_facts():
    """With 2 planned tests for 2 players, roll_facts must have 2 entries."""
    planner_out = json.dumps([
        {"character_name": "Aldric", "test": "stealth", "dc": 12},
        {"character_name": "Mira", "test": "persuasion", "dc": 16},
    ])
    narrator_out = json.dumps({"narrative": "Aldric i Mira działają.", "player_notes": {}})

    saved = {}
    with patch("app.services.multiplayer_round_service._db") as mock_db, \
         patch("app.services.multiplayer_round_service.llm_service") as mock_llm:

        _setup_db_mock(
            mock_db,
            _make_round_row(),
            [
                _make_action_row("Aldric", 201, 101),
                _make_action_row("Mira", 202, 102),
            ],
            {
                201: _make_sheet_row(_sheet(dex=14)),
                202: _make_sheet_row(_sheet(str_val=12)),
            },
            saved,
        )
        _setup_llm_mock(mock_llm, planner_out, narrator_out)

        mrs.trigger_narration(1)

    data = json.loads(saved["json"])
    facts = data.get("roll_facts", [])
    assert len(facts) == 2, f"Expected 2 roll_facts, got {len(facts)}: {facts}"
    names = {f["character_name"] for f in facts}
    assert "Aldric" in names and "Mira" in names, f"Expected both players in roll_facts, got: {names}"


def test_g8_nat20_recorded_in_roll_facts():
    """Nat 20 roll must produce is_nat20=True in roll_facts (raw=20 from resolve_roll)."""
    planner_out = json.dumps([{"character_name": "Aldric", "test": "athletics", "dc": 24}])
    narrator_out = json.dumps({"narrative": "Krytyczny sukces!", "player_notes": {}})

    saved = {}
    with patch("app.services.multiplayer_round_service._db") as mock_db, \
         patch("app.services.multiplayer_round_service.llm_service") as mock_llm, \
         patch("app.services.dice.roll_d20", return_value=20):

        _setup_db_mock(
            mock_db,
            _make_round_row(),
            [_make_action_row(char_id=201)],
            {201: _make_sheet_row(_sheet())},
            saved,
        )
        _setup_llm_mock(mock_llm, planner_out, narrator_out)

        mrs.trigger_narration(1)

    data = json.loads(saved["json"])
    facts = data.get("roll_facts", [])
    assert facts, "roll_facts missing"
    f = facts[0]
    assert f["raw"] == 20, f"Expected raw=20, got {f['raw']}"
    assert f["is_nat20"] is True, f"Expected is_nat20=True, got {f}"


def test_g8_nat1_recorded_in_roll_facts():
    """Nat 1 roll must produce is_nat1=True in roll_facts."""
    planner_out = json.dumps([{"character_name": "Aldric", "test": "stealth", "dc": 1}])
    narrator_out = json.dumps({"narrative": "Totalny blamaż!", "player_notes": {}})

    saved = {}
    with patch("app.services.multiplayer_round_service._db") as mock_db, \
         patch("app.services.multiplayer_round_service.llm_service") as mock_llm, \
         patch("app.services.dice.roll_d20", return_value=1):

        _setup_db_mock(
            mock_db,
            _make_round_row(),
            [_make_action_row(char_id=201)],
            {201: _make_sheet_row(_sheet(dex=20))},
            saved,
        )
        _setup_llm_mock(mock_llm, planner_out, narrator_out)

        mrs.trigger_narration(1)

    data = json.loads(saved["json"])
    facts = data.get("roll_facts", [])
    assert facts, "roll_facts missing"
    f = facts[0]
    assert f["raw"] == 1, f"Expected raw=1, got {f['raw']}"
    assert f["is_nat1"] is True, f"Expected is_nat1=True, got {f}"


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_g8_empty_plan_still_produces_narrative():
    """When planner returns [] (no tests needed), narrator is still called; roll_facts=[]."""
    planner_out = json.dumps([])
    narrator_out = json.dumps({"narrative": "Gracze eksplorują w spokoju.", "player_notes": {}})

    saved = {}
    with patch("app.services.multiplayer_round_service._db") as mock_db, \
         patch("app.services.multiplayer_round_service.llm_service") as mock_llm:

        _setup_db_mock(
            mock_db,
            _make_round_row(),
            [_make_action_row()],
            {},
            saved,
        )
        _setup_llm_mock(mock_llm, planner_out, narrator_out)

        mrs.trigger_narration(1)

    assert saved.get("json"), "narrative_json was not saved"
    data = json.loads(saved["json"])
    assert data.get("narrative") == "Gracze eksplorują w spokoju."
    assert data.get("roll_facts") == [], f"Expected empty roll_facts, got: {data.get('roll_facts')}"
