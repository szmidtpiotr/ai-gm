"""TDD #796 — G18: Tiered round summaries (layer 0/1/2) for MP campaigns."""
import json
import sqlite3
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ── Minimal DB schema ─────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS campaign_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'open',
    deadline TEXT,
    narrative_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS campaign_round_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    character_id INTEGER,
    character_name TEXT NOT NULL DEFAULT '',
    action_text TEXT NOT NULL DEFAULT '',
    initiative_roll INTEGER NOT NULL DEFAULT 10,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS campaign_round_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    layer INTEGER NOT NULL,
    round_from INTEGER NOT NULL,
    round_to INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_crs_campaign_layer
    ON campaign_round_summaries(campaign_id, layer);
"""


def _make_db(tmp_path):
    db_path = str(tmp_path / "test_796.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    return db_path


def _seed_rounds(db_path, campaign_id, count, start=1):
    """Insert `count` completed rounds with dummy narrative."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    for i in range(start, start + count):
        conn.execute(
            "INSERT INTO campaign_rounds (campaign_id, round_number, status, narrative_json) "
            "VALUES (?, ?, 'done', ?)",
            (campaign_id, i, json.dumps({"narrative": f"Narracja rundy {i}", "roll_facts": [], "player_notes": {}})),
        )
    conn.commit()
    conn.close()


def _seed_layer1_summaries(db_path, campaign_id, count, start=1):
    """Insert `count` layer-1 summaries."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    for i in range(start, start + count):
        conn.execute(
            "INSERT INTO campaign_round_summaries (campaign_id, layer, round_from, round_to, text) "
            "VALUES (?, 1, ?, ?, ?)",
            (campaign_id, i, i, f"Streszczenie rundy {i}"),
        )
    conn.commit()
    conn.close()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestLayer1GeneratedAfterRoundClose:
    """Layer-1 summary is created for a closed round."""

    def test_layer1_inserted(self, tmp_path):
        db_path = _make_db(tmp_path)
        campaign_id = 1

        import app.services.multiplayer_round_service as svc

        summary_text = "Gracze zaatakowali trolla i uciekli."

        with (
            patch.object(svc, "_db", lambda: _conn(db_path)),
            patch.object(svc, "_llm_call", return_value=summary_text),
            patch.object(svc, "llm_service") as mock_llm,
            patch.object(svc, "maybe_roll_chapter"),
        ):
            mock_llm.get_effective_config.return_value = {"provider": "openai", "base_url": "x", "model": "y", "api_key": "z"}
            mock_llm.OpenAIDriver.return_value = MagicMock()

            svc._generate_round_summary_layer1(
                campaign_id=campaign_id,
                round_id=1,
                round_number=3,
                narrative="Troll atakuje.",
                actions_block="Ares: atak mieczem.",
            )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM campaign_round_summaries WHERE campaign_id=? AND layer=1",
            (campaign_id,),
        ).fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0]["round_from"] == 3
        assert rows[0]["round_to"] == 3
        assert rows[0]["text"] == summary_text

    def test_layer1_calls_maybe_roll_chapter(self, tmp_path):
        db_path = _make_db(tmp_path)
        campaign_id = 1

        import app.services.multiplayer_round_service as svc

        with (
            patch.object(svc, "_db", lambda: _conn(db_path)),
            patch.object(svc, "_llm_call", return_value="streszczenie"),
            patch.object(svc, "llm_service") as mock_llm,
            patch.object(svc, "maybe_roll_chapter") as mock_chapter,
        ):
            mock_llm.get_effective_config.return_value = {"provider": "openai", "base_url": "x", "model": "y", "api_key": "z"}
            mock_llm.OpenAIDriver.return_value = MagicMock()

            svc._generate_round_summary_layer1(1, 1, 1, "narracja", "akcje")

        mock_chapter.assert_called_once_with(campaign_id)


class TestChapterRollup:
    """maybe_roll_chapter triggers at ≥10 uncovered layer-1 summaries."""

    def test_no_chapter_below_threshold(self, tmp_path):
        db_path = _make_db(tmp_path)
        campaign_id = 1
        _seed_layer1_summaries(db_path, campaign_id, 9)

        import app.services.multiplayer_round_service as svc

        with (
            patch.object(svc, "_db", lambda: _conn(db_path)),
            patch.object(svc, "_llm_call") as mock_llm_call,
            patch.object(svc, "llm_service") as mock_llm,
        ):
            mock_llm.get_effective_config.return_value = {"provider": "openai", "base_url": "x", "model": "y", "api_key": "z"}
            mock_llm.OpenAIDriver.return_value = MagicMock()
            svc.maybe_roll_chapter(campaign_id)

        # LLM should NOT have been called (no chapter created)
        mock_llm_call.assert_not_called()

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        chapters = conn.execute(
            "SELECT * FROM campaign_round_summaries WHERE campaign_id=? AND layer=2",
            (campaign_id,),
        ).fetchall()
        conn.close()
        assert len(chapters) == 0

    def test_chapter_created_at_threshold(self, tmp_path):
        db_path = _make_db(tmp_path)
        campaign_id = 1
        _seed_layer1_summaries(db_path, campaign_id, 10)

        import app.services.multiplayer_round_service as svc

        chapter_text = "Rozdział 1: Drużyna odkryła ruiny."

        with (
            patch.object(svc, "_db", lambda: _conn(db_path)),
            patch.object(svc, "_llm_call", return_value=chapter_text),
            patch.object(svc, "llm_service") as mock_llm,
        ):
            mock_llm.get_effective_config.return_value = {"provider": "openai", "base_url": "x", "model": "y", "api_key": "z"}
            mock_llm.OpenAIDriver.return_value = MagicMock()
            svc.maybe_roll_chapter(campaign_id)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        chapters = conn.execute(
            "SELECT * FROM campaign_round_summaries WHERE campaign_id=? AND layer=2",
            (campaign_id,),
        ).fetchall()
        conn.close()

        assert len(chapters) == 1
        assert chapters[0]["round_from"] == 1
        assert chapters[0]["round_to"] == 10
        assert chapters[0]["text"] == chapter_text

    def test_chapter_excludes_already_covered_layer1(self, tmp_path):
        """After a chapter covers rounds 1–10, a new batch of 10 is needed for next chapter."""
        db_path = _make_db(tmp_path)
        campaign_id = 1

        # Existing chapter covers 1–10
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO campaign_round_summaries (campaign_id, layer, round_from, round_to, text) "
            "VALUES (?, 2, 1, 10, 'Rozdział 1')",
            (campaign_id,),
        )
        conn.commit()
        conn.close()

        # Only 9 new layer-1 summaries after round 10
        _seed_layer1_summaries(db_path, campaign_id, 9, start=11)

        import app.services.multiplayer_round_service as svc

        with (
            patch.object(svc, "_db", lambda: _conn(db_path)),
            patch.object(svc, "_llm_call") as mock_llm_call,
            patch.object(svc, "llm_service") as mock_llm,
        ):
            mock_llm.get_effective_config.return_value = {"provider": "openai", "base_url": "x", "model": "y", "api_key": "z"}
            mock_llm.OpenAIDriver.return_value = MagicMock()
            svc.maybe_roll_chapter(campaign_id)

        mock_llm_call.assert_not_called()

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        chapters = conn.execute(
            "SELECT COUNT(*) AS n FROM campaign_round_summaries WHERE campaign_id=? AND layer=2",
            (campaign_id,),
        ).fetchone()
        conn.close()
        assert chapters["n"] == 1  # still only 1


class TestAssembleNarrationContext:
    """assemble_narration_context returns correct 2→1→0 order."""

    def test_empty_campaign_returns_empty_string(self, tmp_path):
        db_path = _make_db(tmp_path)
        campaign_id = 99

        import app.services.multiplayer_round_service as svc

        with patch.object(svc, "_db", lambda: _conn(db_path)):
            result = svc.assemble_narration_context(campaign_id)

        assert result == ""

    def test_only_raw_rounds(self, tmp_path):
        db_path = _make_db(tmp_path)
        campaign_id = 1
        _seed_rounds(db_path, campaign_id, 3)

        import app.services.multiplayer_round_service as svc

        with patch.object(svc, "_db", lambda: _conn(db_path)):
            result = svc.assemble_narration_context(campaign_id)

        assert "OSTATNIE RUNDY" in result
        assert "ROZDZIAŁY" not in result
        assert "STRESZCZENIA RUND" not in result
        assert "Narracja rundy 1" in result
        assert "Narracja rundy 3" in result
        # Header must be a prefix, not used as separator between parts
        assert result.startswith("[HISTORIA — OSTATNIE RUNDY]")

    def test_all_three_layers_present(self, tmp_path):
        db_path = _make_db(tmp_path)
        campaign_id = 1
        _seed_rounds(db_path, campaign_id, 3, start=12)
        _seed_layer1_summaries(db_path, campaign_id, 3, start=11)

        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO campaign_round_summaries (campaign_id, layer, round_from, round_to, text) "
            "VALUES (?, 2, 1, 10, 'Rozdział 1: Początek')",
            (campaign_id,),
        )
        conn.commit()
        conn.close()

        import app.services.multiplayer_round_service as svc

        with patch.object(svc, "_db", lambda: _conn(db_path)):
            result = svc.assemble_narration_context(campaign_id)

        assert "ROZDZIAŁY" in result
        assert "STRESZCZENIA RUND" in result
        assert "OSTATNIE RUNDY" in result
        # Order: chapters first, then summaries, then raw rounds
        pos_chapters = result.index("ROZDZIAŁY")
        pos_summaries = result.index("STRESZCZENIA RUND")
        pos_raw = result.index("OSTATNIE RUNDY")
        assert pos_chapters < pos_summaries < pos_raw

    def test_summaries_after_last_chapter_only(self, tmp_path):
        """Layer-1 summaries from before the last chapter must NOT appear."""
        db_path = _make_db(tmp_path)
        campaign_id = 1

        conn = sqlite3.connect(db_path)
        # Chapter covers 1–10
        conn.execute(
            "INSERT INTO campaign_round_summaries (campaign_id, layer, round_from, round_to, text) "
            "VALUES (?, 2, 1, 10, 'Rozdział')",
            (campaign_id,),
        )
        # Layer-1 summaries: 5 before chapter, 3 after
        for i in range(1, 6):
            conn.execute(
                "INSERT INTO campaign_round_summaries (campaign_id, layer, round_from, round_to, text) "
                "VALUES (?, 1, ?, ?, ?)",
                (campaign_id, i, i, f"Streszczenie rundy {i} (PRZED)"),
            )
        for i in range(11, 14):
            conn.execute(
                "INSERT INTO campaign_round_summaries (campaign_id, layer, round_from, round_to, text) "
                "VALUES (?, 1, ?, ?, ?)",
                (campaign_id, i, i, f"Streszczenie rundy {i} (PO)"),
            )
        conn.commit()
        conn.close()

        import app.services.multiplayer_round_service as svc

        with patch.object(svc, "_db", lambda: _conn(db_path)):
            result = svc.assemble_narration_context(campaign_id)

        assert "PRZED" not in result
        assert "PO" in result

    def test_raw_rounds_limited_to_3(self, tmp_path):
        db_path = _make_db(tmp_path)
        campaign_id = 1
        _seed_rounds(db_path, campaign_id, 6)

        import app.services.multiplayer_round_service as svc

        with patch.object(svc, "_db", lambda: _conn(db_path)):
            result = svc.assemble_narration_context(campaign_id)

        # Only rounds 4, 5, 6 should appear (last 3)
        assert "Narracja rundy 1" not in result
        assert "Narracja rundy 4" in result
        assert "Narracja rundy 6" in result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
