"""TDD: Issue #1057 — narracja synchronizuje local_hex po ruchu fabularnym do sublokacji."""
import json
import sqlite3
import sys
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, "/app")


# ─── Test główny — sync sublokacji z istniejącym hexem ────────────────────────

def test_narrative_move_to_subloc_updates_local_hex():
    """Ruch narracyjny do istniejącej sublokacji ustawia session_flags.local_hex."""
    from app.api.turns import _sync_local_hex_narrative_move

    conn = MagicMock(spec=sqlite3.Connection)
    session_id = 42
    campaign_id = 99
    resolved_location_id = 7

    def mock_execute(query, params=()):
        m = MagicMock()
        q_lower = query.lower()
        if "game_locations" in q_lower:
            row = MagicMock()
            row.__getitem__ = lambda s, k: {
                "key": "kuznia_wujka",
                "location_type": "sub",
                "parent_key": "wolanka_hub",
            }.get(k)
            m.fetchone.return_value = row
        elif "session_flags" in q_lower and "select" in q_lower:
            row = MagicMock()
            row.__getitem__ = lambda s, k: {
                "session_flags": json.dumps({"current_hex": {"q": 21, "r": 1}}),
            }.get(k)
            m.fetchone.return_value = row
        else:
            m.fetchone.return_value = None
        return m

    conn.execute.side_effect = mock_execute

    local_hex_data = {"id": 55, "q": 0, "r": 0, "location_key": "kuznia_wujka"}

    with patch("app.services.local_hex_service.get_local_hex_for_subloc", return_value=local_hex_data):
        _sync_local_hex_narrative_move(conn, session_id, campaign_id, resolved_location_id)

    # Must have called UPDATE game_sessions SET session_flags
    update_calls = [
        c for c in conn.execute.call_args_list
        if "UPDATE" in str(c) and "session_flags" in str(c)
    ]
    assert len(update_calls) > 0, "Oczekiwano UPDATE game_sessions SET session_flags z local_hex"

    # Written flags must contain local_hex
    for c in update_calls:
        args = c.args if hasattr(c, "args") else c[0]
        # args[0] = query string, args[1] = params tuple (json_string, session_id)
        written_flags = json.loads(args[1][0])
        assert "local_hex" in written_flags, f"local_hex brak w zapisanych flags: {written_flags}"
        assert written_flags["local_hex"]["hex_id"] == 55


def test_narrative_move_to_subloc_no_hex_auto_creates():
    """Ruch narracyjny do sublokacji bez local_hex → auto_assign tworzy hex i ustawia local_hex."""
    from app.api.turns import _sync_local_hex_narrative_move

    conn = MagicMock(spec=sqlite3.Connection)

    def mock_execute(query, params=()):
        m = MagicMock()
        q_lower = query.lower()
        if "game_locations" in q_lower:
            row = MagicMock()
            row.__getitem__ = lambda s, k: {
                "key": "kopalnia_glowna",
                "location_type": "sub",
                "parent_key": "wolanka_hub",
            }.get(k)
            m.fetchone.return_value = row
        elif "session_flags" in q_lower and "select" in q_lower:
            row = MagicMock()
            row.__getitem__ = lambda s, k: {"session_flags": json.dumps({})}.get(k)
            m.fetchone.return_value = row
        else:
            m.fetchone.return_value = None
        return m

    conn.execute.side_effect = mock_execute

    created_hex = {"id": 99, "q": 1, "r": 0, "location_key": "kopalnia_glowna"}

    with patch("app.services.local_hex_service.get_local_hex_for_subloc", return_value=None), \
         patch("app.services.local_hex_service.auto_assign_local_hex", return_value=created_hex) as mock_auto:
        _sync_local_hex_narrative_move(conn, session_id=42, campaign_id=99, resolved_location_id=8)

    mock_auto.assert_called_once()
    update_calls = [
        c for c in conn.execute.call_args_list
        if "UPDATE" in str(c) and "session_flags" in str(c)
    ]
    assert len(update_calls) > 0, "Oczekiwano UPDATE session_flags z nowym local_hex"
    for c in update_calls:
        args = c.args if hasattr(c, "args") else c[0]
        written = json.loads(args[1][0])
        assert "local_hex" in written, f"local_hex brak: {written}"
        assert written["local_hex"]["hex_id"] == 99


def test_narrative_move_to_macro_clears_local_hex():
    """Ruch do lokacji makro (wyjście z osady) czyści local_hex z session_flags."""
    from app.api.turns import _sync_local_hex_narrative_move

    conn = MagicMock(spec=sqlite3.Connection)
    existing_flags = {
        "local_hex": {"hex_id": 55, "q": 0, "r": 0, "location_key": "kuznia_wujka"},
        "current_hex": {"q": 21, "r": 1},
    }

    def mock_execute(query, params=()):
        m = MagicMock()
        q_lower = query.lower()
        if "game_locations" in q_lower:
            row = MagicMock()
            row.__getitem__ = lambda s, k: {
                "key": "las_na_polnocy",
                "location_type": "macro",
                "parent_key": None,
            }.get(k)
            m.fetchone.return_value = row
        elif "session_flags" in q_lower and "select" in q_lower:
            row = MagicMock()
            row.__getitem__ = lambda s, k: {"session_flags": json.dumps(existing_flags)}.get(k)
            m.fetchone.return_value = row
        else:
            m.fetchone.return_value = None
        return m

    conn.execute.side_effect = mock_execute

    with patch("app.services.local_hex_service.get_local_hex_for_subloc") as mock_get:
        _sync_local_hex_narrative_move(conn, session_id=42, campaign_id=99, resolved_location_id=10)

    mock_get.assert_not_called()

    update_calls = [
        c for c in conn.execute.call_args_list
        if "UPDATE" in str(c) and "session_flags" in str(c)
    ]
    assert len(update_calls) > 0, "Oczekiwano UPDATE session_flags (kasowanie local_hex)"
    for c in update_calls:
        args = c.args if hasattr(c, "args") else c[0]
        written = json.loads(args[1][0])
        assert "local_hex" not in written, f"local_hex nie został wyczyszczony: {written}"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_sync_local_hex_handles_exception_gracefully():
    """Wyjątek w sync local_hex nie psuje reszty — try/except go łapie."""
    from app.api.turns import _sync_local_hex_narrative_move

    conn = MagicMock(spec=sqlite3.Connection)
    conn.execute.side_effect = Exception("DB error")

    # Musi NIE rzucić wyjątku
    try:
        _sync_local_hex_narrative_move(conn, session_id=42, campaign_id=99, resolved_location_id=1)
    except Exception as e:
        assert False, f"Wyjątek nie powinien wychodzić na zewnątrz: {e}"


def test_sync_local_hex_no_location_no_crash():
    """Gdy resolved_location nie istnieje w DB — brak błędu, session_flags bez zmian."""
    from app.api.turns import _sync_local_hex_narrative_move

    conn = MagicMock(spec=sqlite3.Connection)

    def mock_execute(query, params=()):
        m = MagicMock()
        m.fetchone.return_value = None
        return m

    conn.execute.side_effect = mock_execute

    _sync_local_hex_narrative_move(conn, session_id=42, campaign_id=99, resolved_location_id=999)

    update_calls = [
        c for c in conn.execute.call_args_list
        if "UPDATE" in str(c) and "session_flags" in str(c)
    ]
    assert len(update_calls) == 0, "Brak lokacji → zero UPDATE session_flags"
