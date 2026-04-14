"""
LLM parameter configuration.
Edit this file to tweak model behaviour without touching game logic.
These values are passed to Ollama's 'options' block.

Environment variable overrides are also supported:
  LLM_TEMPERATURE, LLM_TOP_P, LLM_TOP_K, LLM_REPEAT_PENALTY, LLM_MAX_TOKENS
"""
import os


def get_llm_params() -> dict:
    return {
        # Controls randomness: lower = more focused, higher = more creative (0.0 – 2.0)
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.8")),
        # Nucleus sampling: only tokens covering this probability mass are considered (0.0 – 1.0)
        "top_p": float(os.getenv("LLM_TOP_P", "0.9")),
        # Top-K sampling: limits to K most likely next tokens (1 – 100)
        "top_k": int(os.getenv("LLM_TOP_K", "40")),
        # Penalises repeating the same words (1.0 = no penalty, >1.0 = discourage repeats)
        "repeat_penalty": float(os.getenv("LLM_REPEAT_PENALTY", "1.1")),
        # Maximum tokens to generate per response
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "512")),
    }
