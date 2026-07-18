"""#1215 — Szybkie akcje (chipy LLM pod composerem).

Testuje domieszkę chipów GENEROWANYCH PRZEZ LLM w build_suggested_actions:
twardy filtr zagadek/testów, cap quick_chips_max, bramkę globalną
quick_chips_enabled, znacznik source="llm" i dedup po action.

Izolacja: game_state="__ISOLATE__" nie jest w (COMBAT/NARRATIVE/DIALOGUE/"") →
gałąź rule-based zwraca [], więc na wyniku widać WYŁĄCZNIE ścieżkę merge LLM,
bez potrzeby seedowania tabel świata.
"""

import sqlite3

import pytest

from app.services.suggested_actions import (
    build_suggested_actions,
    _is_risky_suggestion,
    _quick_chips_config,
    QUICK_CHIPS_MAX_DEFAULT,
)

ISOLATE = "__ISOLATE__"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE game_config_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT)")
    yield c
    c.close()


def _set_meta(conn, **kv):
    for k, v in kv.items():
        conn.execute(
            "INSERT OR REPLACE INTO game_config_meta (key, value) VALUES (?, ?)",
            (k, str(v)),
        )
    conn.commit()


def _build(conn, llm):
    return build_suggested_actions(
        conn, campaign_id=1, character_id=1, game_state=ISOLATE,
        session_flags={}, llm_suggested=llm,
    )


# ── filtr twardy ──────────────────────────────────────────────────────────────

def test_risky_detector_riddle_with_and_without_diacritics():
    assert _is_risky_suggestion("Rozwiąż zagadkę", "Rozwiąż zagadkę") is True
    # gracz mobilny bez ogonków — musi też złapać (#1420 fold)
    assert _is_risky_suggestion("Rozwiaz zagadke", "Rozwiaz zagadke") is True
    assert _is_risky_suggestion("Podaj hasło", "Podaj haslo") is True
    assert _is_risky_suggestion("Wykonaj rzut na percepcję", "test") is True


def test_risky_detector_allows_obvious_actions():
    assert _is_risky_suggestion("Przeszukaj ciała", "Przeszukaj ciała") is False
    assert _is_risky_suggestion("Porozmawiaj z karczmarzem", "DIALOGUE:barkeep") is False
    assert _is_risky_suggestion("Odpocznij", "REST:long") is False


def test_filter_rejects_riddle_suggestions(conn):
    out = _build(conn, [
        {"label": "Rozwiąż zagadkę", "action": "Rozwiąż zagadkę"},
        {"label": "Rozwiaz zagadke", "action": "Rozwiaz zagadke bez ogonkow"},
        {"label": "Przeszukaj ciała", "action": "Przeszukaj ciała"},
    ])
    labels = [a["label"] for a in out]
    assert labels == ["Przeszukaj ciała"]


# ── cap ────────────────────────────────────────────────────────────────────────

def test_cap_respects_quick_chips_max(conn):
    _set_meta(conn, quick_chips_max=2)
    out = _build(conn, [
        {"label": "Akcja 1", "action": "a1"},
        {"label": "Akcja 2", "action": "a2"},
        {"label": "Akcja 3", "action": "a3"},
        {"label": "Akcja 4", "action": "a4"},
    ])
    assert len(out) == 2
    assert [a["action"] for a in out] == ["a1", "a2"]


def test_default_max_is_three(conn):
    out = _build(conn, [{"label": f"A{i}", "action": f"a{i}"} for i in range(5)])
    assert len(out) == QUICK_CHIPS_MAX_DEFAULT == 3


# ── bramka globalna ─────────────────────────────────────────────────────────────

def test_global_flag_off_drops_llm_chips(conn):
    _set_meta(conn, quick_chips_enabled=0)
    out = _build(conn, [{"label": "Przeszukaj", "action": "SEARCH2"}])
    assert out == []


def test_global_flag_on_by_default(conn):
    cfg = _quick_chips_config(conn)
    assert cfg == (True, 3)
    out = _build(conn, [{"label": "Przeszukaj", "action": "SEARCH2"}])
    assert len(out) == 1


# ── source + dedup ───────────────────────────────────────────────────────────────

def test_llm_chips_tagged_source(conn):
    out = _build(conn, [{"label": "Przeszukaj ciała", "action": "Przeszukaj ciała"}])
    assert out[0]["source"] == "llm"


def test_dedup_by_action(conn):
    out = _build(conn, [
        {"label": "Przeszukaj", "action": "SEARCH"},
        {"label": "Przeszukaj znowu", "action": "SEARCH"},
    ])
    assert len(out) == 1


def test_blank_label_or_action_skipped(conn):
    out = _build(conn, [
        {"label": "", "action": "x"},
        {"label": "y", "action": ""},
        {"label": "Dobra akcja", "action": "ok"},
    ])
    assert [a["action"] for a in out] == ["ok"]
