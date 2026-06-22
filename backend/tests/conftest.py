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
