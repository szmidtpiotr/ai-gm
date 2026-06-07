"""TDD: Issue #395 — active LLM preset is the single source of truth.

The game must always resolve LLM config from the active preset and must NEVER
silently fall back to the hardcoded Ollama / `gemma4:e4b` default — neither in
the running server nor in fresh processes (pytest, scripts) where "default"
mode must still mean "the active preset".
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if "httpx" not in sys.modules:
    from unittest.mock import MagicMock

    sys.modules["httpx"] = MagicMock()

import app.services.llm_service as L

HARDCODED_OLLAMA_MODEL = "gemma4:e4b"


@pytest.fixture
def clean_llm(monkeypatch):
    """Isolate the in-process LLM runtime + env between tests.

    By default skips DB hydration (so tests are hermetic); individual tests
    that exercise lazy-hydration re-enable it explicitly.
    """
    saved_runtime = dict(L._runtime_config)
    saved_attempted = getattr(L, "_hydrate_attempted", None)
    for key in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    L.set_runtime_config("", "", "", "")
    # Pretend hydration already ran and found nothing, so get_effective_config
    # does not touch the real DB unless a test opts in.
    monkeypatch.setattr(L, "_hydrate_attempted", True, raising=False)
    yield L
    L._runtime_config.clear()
    L._runtime_config.update(saved_runtime)
    if saved_attempted is not None:
        L._hydrate_attempted = saved_attempted


# ─── Test główny: anti-Frankenstein ──────────────────────────────────────────

def test_openai_preset_never_inherits_gemma_model(clean_llm, monkeypatch):
    """OpenAI active preset with an empty model must NOT borrow env gemma model.

    A coherent endpoint identity: provider+model come from the SAME source.
    """
    # Active preset = OpenAI but its model field is blank (misconfig).
    clean_llm.set_runtime_config(
        provider="openai", base_url="https://api.openai.com", model="", api_key="sk-test"
    )
    # A stale env model lingers — it belongs to Ollama and must never leak in.
    monkeypatch.setenv("LLM_MODEL", HARDCODED_OLLAMA_MODEL)

    eff = clean_llm.get_effective_config()

    assert eff["provider"] == "openai"
    assert eff["model"] != HARDCODED_OLLAMA_MODEL, (
        "OpenAI provider inherited the Ollama gemma model — Frankenstein config"
    )


def test_no_config_strict_raises_instead_of_ollama(clean_llm):
    """No preset + no env → strict resolution raises, never returns Ollama/gemma."""
    with pytest.raises(L.LLMConfigError):
        clean_llm.get_effective_config(strict=True)


def test_default_display_has_no_gemma_when_unconfigured(clean_llm):
    """Display/default config must not advertise a random hardcoded gemma model."""
    cfg = clean_llm.get_default_config(mask_api_key=True)
    assert cfg["model"] != HARDCODED_OLLAMA_MODEL
    assert cfg["provider"] != "ollama" or not cfg["model"], (
        "Unconfigured default still resolved to Ollama gemma"
    )


def test_fresh_process_lazy_hydrates_active_preset(clean_llm, monkeypatch):
    """A fresh process (empty runtime) must lazy-hydrate the active stored preset.

    Simulates pytest/scripts: runtime empty, hydration not yet attempted. The
    effective config must become the active preset (OpenAI), not hardcoded gemma.
    """
    # Allow hydration to run, and make the stored-preset hydrator set OpenAI.
    monkeypatch.setattr(L, "_hydrate_attempted", False, raising=False)
    import app.services.llm_admin_service as A

    def fake_hydrate():
        L.set_runtime_config(
            provider="openai",
            base_url="https://api.openai.com",
            model="gpt-4.1",
            api_key="sk-stored",
        )

    monkeypatch.setattr(A, "hydrate_runtime_from_stored_preset", fake_hydrate)

    eff = clean_llm.get_effective_config()

    assert eff["provider"] == "openai"
    assert eff["model"] == "gpt-4.1"


def test_generate_chat_refuses_when_unconfigured(clean_llm):
    """generate_chat must raise a clear config error, not attempt an Ollama call."""
    with pytest.raises((L.LLMConfigError, RuntimeError)) as exc:
        clean_llm.generate_chat(messages=[{"role": "user", "content": "hi"}])
    msg = str(exc.value).lower()
    assert "preset" in msg or "not configured" in msg or "no active" in msg, (
        f"Error did not point at missing LLM config: {exc.value!r}"
    )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_active_openai_preset_fully_resolves(clean_llm):
    """When the active preset is fully set, every field comes from it."""
    clean_llm.set_runtime_config(
        provider="openai", base_url="https://api.openai.com", model="gpt-4.1", api_key="sk-k"
    )
    eff = clean_llm.get_effective_config()
    assert eff["provider"] == "openai"
    assert eff["base_url"] == "https://api.openai.com"
    assert eff["model"] == "gpt-4.1"
    assert eff["api_key"] == "sk-k"


def test_per_user_custom_override_still_wins(clean_llm):
    """A per-user custom override (coherent unit) still beats the active preset."""
    clean_llm.set_runtime_config(
        provider="ollama", base_url="http://localhost:11434", model="gemma4:e4b", api_key=""
    )
    override = {
        "provider": "openai",
        "base_url": "https://api.openai.com",
        "model": "gpt-4o",
        "api_key": "sk-user",
    }
    eff = clean_llm.get_effective_config(override)
    assert eff["provider"] == "openai"
    assert eff["model"] == "gpt-4o"
    assert eff["model"] != HARDCODED_OLLAMA_MODEL


def test_ollama_preset_still_allowed(clean_llm):
    """Choosing Ollama explicitly must still work (it is a valid provider)."""
    clean_llm.set_runtime_config(
        provider="ollama",
        base_url="http://localhost:11434",
        model="jobautomation/OpenEuroLLM-Polish:latest",
        api_key="",
    )
    eff = clean_llm.get_effective_config()
    assert eff["provider"] == "ollama"
    assert eff["model"] == "jobautomation/OpenEuroLLM-Polish:latest"
