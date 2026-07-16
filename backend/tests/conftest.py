import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


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
