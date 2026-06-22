"""TDD: Issue #930 [918-A3] — order-independent isolation of shared module state.

Several tests pass solo but fail in a combined run because ``llm_service``
holds process-wide module state: ``_runtime_config`` (the active LLM endpoint)
and ``_hydrate_attempted`` (the lazy "did we read the active preset from the DB
yet?" flag). When a test clears the runtime, the resolver lazily hydrates from
the *real* ``/data/ai_gm.db`` active preset (e.g. an OpenAI endpoint), so the
result depends on global DB state and on whatever ran earlier — not on the test.

The fix is an autouse fixture in ``conftest.py`` that, around every test:
  * snapshots ``_runtime_config`` + ``_hydrate_attempted``,
  * resets the runtime to empty and pre-blocks hydration
    (``_hydrate_attempted = True``) so no test silently reads the real preset,
  * restores the originals afterwards.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import llm_service as L


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_runtime_state_clean_at_test_entry():
    """Every test must START with empty runtime config and hydration pre-blocked.

    This is the invariant that makes the suite order-independent: no matter what
    ran before, a test never inherits a leaked LLM endpoint nor triggers a lazy
    read of the real DB preset.
    """
    leaked = {k: v for k, v in L._runtime_config.items() if (v or "").strip()}
    assert leaked == {}, f"_runtime_config leaked into this test: {leaked}"
    assert L._hydrate_attempted is True, (
        "_hydrate_attempted must be pre-set True so resolution never lazily "
        "reads the real /data/ai_gm.db active preset during tests"
    )


def test_default_resolution_uses_env_not_real_db_preset(monkeypatch):
    """With runtime cleared, server-default resolution falls to LLM_* env vars.

    Mirrors the real victim ``test_default_mode_without_row_uses_server_env``:
    without isolation the lazy hydrate pulls the real active preset
    (e.g. api.openai.com) and shadows the env the test set up.
    """
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-issue930")
    monkeypatch.setenv("LLM_API_KEY", "env-secret-930")

    L.set_runtime_config("", "", "", "")
    cfg = L.get_default_config(mask_api_key=True)

    assert cfg["base_url"] == "https://api.example.test", cfg
    assert cfg["model"] == "gpt-issue930", cfg
    assert cfg["source"] == "env", cfg


def test_pollution_does_not_leak_out_of_this_test():
    """A test that dirties the shared runtime must not bleed into the next one.

    We assert our OWN entry is clean (proves nothing leaked IN), then pollute and
    leave cleanup entirely to the autouse fixture (the next test re-asserts clean).
    """
    leaked = {k: v for k, v in L._runtime_config.items() if (v or "").strip()}
    assert leaked == {}, f"runtime dirty on entry: {leaked}"

    L.set_runtime_config("openai", "https://polluted-930.test", "bad-model", "bad-key")
    L._hydrate_attempted = False
    assert L._runtime_config["base_url"] == "https://polluted-930.test"
    # No teardown here on purpose — the conftest autouse fixture owns the reset.


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_set_runtime_config_still_overrides_within_a_test():
    """Intentional in-test runtime config still works (fixture only resets at boundaries)."""
    L.set_runtime_config("openai", "https://runtime-930.test/v1", "rt-model", "rt-key")
    cfg = L.get_default_config(mask_api_key=False)
    assert cfg["source"] == "runtime", cfg
    assert cfg["base_url"] == "https://runtime-930.test", cfg
    assert cfg["model"] == "rt-model", cfg
