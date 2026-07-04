"""Model-name curation helper.

The public `GET /api/models` endpoint was removed (#1178 — dead, zero UI
consumers; admin LLM UI resolves models via `/api/admin/*`). Only the curation
helper survives, imported by test_runner for its model-list preflight.
"""


def _curate_narration_models(provider: str, models: list[str]) -> list[str]:
    if not models:
        return []

    preferred_openai_order = [
        "OpenEuro-Polish",
        "gpt-4o",
        "gpt-4.1",
        "claude-sonnet-4-5",
        "claude-sonnet-4",
        "gemini-2.5-pro",
        "mistral-large-latest",
        "qwen-max",
        "qwen3-32b",
        "llama-3.3-70b-instruct",
    ]
    if provider == "openai":
        lower_map = {m.lower(): m for m in models}
        curated: list[str] = []
        for preferred in preferred_openai_order:
            key = preferred.lower()
            if key in lower_map and lower_map[key] not in curated:
                curated.append(lower_map[key])
        keyword_hits = [
            m
            for m in models
            if any(
                kw in m.lower()
                for kw in ("polish", "openeuro", "gpt-4o", "gpt-4.1", "claude-sonnet", "gemini-2.5-pro")
            )
        ]
        for m in keyword_hits:
            if m not in curated:
                curated.append(m)
        return curated[:20] if curated else models[:20]

    # For Ollama keep raw model list as-is (no curation/filtering).
    return models
