import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# Tabele, które testy potrafią zaśmiecić na trwałe (#1487 Faza 3).
_WATCHED_TABLES = ("game_locations", "game_sessions", "characters", "users", "campaigns", "npcs")


def _live_db_or_none():
    """Ścieżka bazy, jeśli suita pracuje na ŻYWEJ bazie; None gdy na kopii (#1487)."""
    import os

    try:
        from app.core.db_runtime import DEFAULT_DB_PATH, resolve_db_path
    except Exception:
        return None
    if os.getenv("AI_GM_SUPPRESS_LIVE_DB_WARNING"):
        return None
    path = resolve_db_path()
    return path if path == DEFAULT_DB_PATH else None


def _table_counts(db_path):
    import sqlite3

    try:
        con = sqlite3.connect(db_path)
    except sqlite3.Error:
        return {}
    try:
        out = {}
        for t in _WATCHED_TABLES:
            try:
                out[t] = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            except sqlite3.Error:
                pass
        return out
    finally:
        con.close()


def pytest_sessionstart(session):
    """#1487 Faza 3 — zapamiętaj stan ŻYWEJ bazy przed przebiegiem.

    Od Fazy 2 domyślna droga (`scripts/test_dev.sh`) podaje testom kopię — wtedy nie
    ma czego pilnować. Liczymy tylko przy `--live` albo gołym `docker exec … pytest`,
    czyli dokładnie wtedy, gdy zostawione wiersze są trwałe.
    """
    db = _live_db_or_none()
    session.config._aigm_live_db = db
    session.config._aigm_counts_before = _table_counts(db) if db else {}


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Wypisz, co suita zostawiła w żywej bazie.

    Świadomie NIE kasujemy tutaj: reguły „co wolno usunąć" mieszkają w
    `scripts/cleanup_test_data.py` (z dry-runem), a kasowanie w teardownie potrafiłoby
    zabrać dane, których test nie tworzył.
    """
    db = getattr(config, "_aigm_live_db", None)
    if not db:
        return
    before = getattr(config, "_aigm_counts_before", {})
    after = _table_counts(db)
    grew = {t: n - before.get(t, 0) for t, n in after.items() if n > before.get(t, 0)}
    if not grew:
        return
    detail = ", ".join(f"{t} +{d}" for t, d in grew.items())
    terminalreporter.write_line("")
    terminalreporter.write_line(
        f"⚠️  Suita pisała do ŻYWEJ bazy ({db}) i zostawiła: {detail}", red=True, bold=True
    )
    terminalreporter.write_line(
        "    Użyj `./scripts/test_dev.sh` (izolowana kopia) albo posprzątaj: "
        "`python3 scripts/cleanup_test_data.py`"
    )


@pytest.fixture(autouse=True)
def _isolate_llm_runtime_state():
    """Isolate the process-wide ``llm_service`` module state around every test.

    Issue #930 [918-A3]: ``_runtime_config`` (the active LLM endpoint) and
    ``_hydrate_attempted`` (lazy "read the active preset from the DB yet?" flag)
    live at module scope, so they leak across tests and make a combined run
    order-dependent. Worse, when a test clears the runtime the resolver lazily
    hydrates from the *real* ``/data/ai_gm.db`` active preset — coupling test
    results to global DB state.

    Before each test we snapshot both, reset the runtime to empty and pre-block
    hydration (``_hydrate_attempted = True``) so no test silently reads the real
    preset; afterwards we restore the originals. A test that genuinely wants a
    runtime config still sets it explicitly via ``set_runtime_config``.
    """
    from app.services import llm_service as L

    saved_runtime = dict(L._runtime_config)
    saved_attempted = getattr(L, "_hydrate_attempted", False)

    L._runtime_config.clear()
    L._runtime_config.update({"provider": "", "base_url": "", "model": "", "api_key": ""})
    L._hydrate_attempted = True
    try:
        yield
    finally:
        L._runtime_config.clear()
        L._runtime_config.update(saved_runtime)
        L._hydrate_attempted = saved_attempted


@pytest.fixture(autouse=True)
def _cleanup_test_locations():
    """Delete any ``game_locations`` rows a test creates in the shared DB.

    Root cause of #1407 garbage: the suite has no isolated DB (conftest never
    monkeypatches the hardcoded ``DB_PATH``), so location tests that POST to
    ``/api/locations`` or call the validator wrote throwaway rows ("City A",
    "Parent To Delete", ``dup_test_<time>`` …) straight into ``/data/ai_gm.db``
    and never cleaned up — ~345 rows accumulated over many CI runs.

    Rather than a risky global path refactor (DB_PATH is imported in a dozen
    modules and shared with prod), snapshot the location keys before the test and
    hard-delete whatever is new afterwards. Reads the SAME path the endpoints use
    (``migrations_admin.DB_PATH``) so it cleans exactly what the test dirtied, and
    only ever removes rows the test itself introduced — pre-existing seed/canon
    rows are untouched.
    """
    import sqlite3

    try:
        from app.migrations_admin import DB_PATH
    except Exception:
        yield
        return

    def _keys() -> set:
        try:
            con = sqlite3.connect(DB_PATH)
            try:
                return {r[0] for r in con.execute("SELECT key FROM game_locations")}
            finally:
                con.close()
        except sqlite3.Error:
            return set()

    before = _keys()
    try:
        yield
    finally:
        new = _keys() - before
        if new:
            try:
                con = sqlite3.connect(DB_PATH)
                try:
                    con.executemany("DELETE FROM game_locations WHERE key = ?", [(k,) for k in new])
                    con.commit()
                finally:
                    con.close()
            except sqlite3.Error:
                pass
