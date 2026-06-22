"""TDD: Issue #818 (H4) — content/offline LLM profile (admin AI Kreator → Ollama .170)
separated from the live-gameplay LLM preset.

Cel: generacja treści w adminie (Smart Entry / Kreator / Forge) idzie na lokalny
Ollama (.170), a narracja rozgrywki zostaje na aktywnym presecie (chmura). Wybór
profilu treści NIE może mutować runtime rozgrywki ani z niego wyciekać.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services import llm_service as ls


@pytest.fixture(autouse=True)
def _isolate_runtime(monkeypatch):
    """Each test starts with a clean runtime + no CONTENT_LLM_* / LLM_* env leakage."""
    for var in (
        "CONTENT_LLM_PROVIDER", "CONTENT_LLM_BASE_URL", "CONTENT_LLM_MODEL",
        "CONTENT_LLM_API_KEY", "CONTENT_LLM_ENABLED",
        "LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    ls.set_runtime_config("", "", "", "")
    ls._hydrate_attempted = True  # block DB hydration in tests
    yield
    ls.set_runtime_config("", "", "", "")


# ─── Test główny — profil treści jest offline i niezależny od presetu rozgrywki ──

def test_content_profile_is_offline_ollama_regardless_of_gameplay_preset():
    """Gameplay = openai (chmura), a profil treści i tak ma być lokalnym Ollama."""
    ls.set_runtime_config("openai", "https://api.openai.com", "gpt-4.1-mini", "sk-secret")

    content = ls.resolve_content_llm_config()

    assert content["provider"] == "ollama"
    assert "11434" in content["base_url"]            # lokalny endpoint Ollama
    assert content["model"]                          # jakiś model treści ustawiony
    # nie wyciągamy klucza chmury do profilu lokalnego
    assert content.get("api_key", "") != "sk-secret"


def test_content_profile_routes_generate_chat_to_offline_endpoint():
    """generate_chat z profilem treści musi rozwiązać się na endpoint Ollama .170,
    nie na aktywny preset rozgrywki (openai)."""
    ls.set_runtime_config("openai", "https://api.openai.com", "gpt-4.1-mini", "sk-secret")

    effective = ls.get_effective_config(ls.resolve_content_llm_config(), strict=True)

    assert effective["provider"] == "ollama"
    assert "11434" in effective["base_url"]


def test_content_model_overridable_via_env(monkeypatch):
    """Admin/serwer może wskazać model treści przez CONTENT_LLM_MODEL."""
    monkeypatch.setenv("CONTENT_LLM_MODEL", "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M")
    monkeypatch.setenv("CONTENT_LLM_BASE_URL", "http://192.168.1.170:11434")
    content = ls.resolve_content_llm_config()
    assert content["model"] == "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M"
    assert content["base_url"] == "http://192.168.1.170:11434"


# ─── Brak wycieku — profil treści nie mutuje runtime rozgrywki ───────────────────

def test_resolving_content_profile_does_not_mutate_gameplay_runtime():
    """Po rozwiązaniu profilu treści narracja gracza dalej idzie na openai."""
    ls.set_runtime_config("openai", "https://api.openai.com", "gpt-4.1-mini", "sk-secret")

    _ = ls.resolve_content_llm_config()
    _ = ls.get_effective_config(ls.resolve_content_llm_config(), strict=True)

    gameplay = ls.get_effective_config(strict=True)  # bez llm_config = rozgrywka
    assert gameplay["provider"] == "openai"
    assert gameplay["model"] == "gpt-4.1-mini"


# ─── Backward compatibility — istniejące rozwiązywanie configu bez zmian ─────────

def test_explicit_llm_config_override_still_works():
    """Stary mechanizm: jawny llm_config wciąż nadpisuje preset (bez regresji)."""
    ls.set_runtime_config("openai", "https://api.openai.com", "gpt-4.1-mini", "sk-secret")
    eff = ls.get_effective_config(
        {"provider": "ollama", "model": "gemma4:12b", "base_url": "http://192.168.1.170:11434"},
        strict=True,
    )
    assert eff["provider"] == "ollama"
    assert eff["model"] == "gemma4:12b"


def test_gameplay_preset_unaffected_when_no_content_env_set():
    """Bez CONTENT_LLM_* aktywny preset rozgrywki nadal rozwiązuje się normalnie."""
    ls.set_runtime_config("openai", "https://api.openai.com", "gpt-4.1-mini", "sk-secret")
    gameplay = ls.get_effective_config(strict=True)
    assert gameplay["provider"] == "openai"
