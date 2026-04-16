"""Smoke test for Phase 7.5 provider abstraction.

Usage examples:
  python3 backend/tests/run_llm_provider_smoke.py --api-key "$LLM_API_KEY"
  python3 backend/tests/run_llm_provider_smoke.py --api-key "...token..." --model gpt-4o
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import requests


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}")
    return 1


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def _pick_campaign_and_character(base_api_url: str) -> tuple[int, int]:
    campaigns_resp = requests.get(f"{base_api_url}/campaigns", timeout=20)
    campaigns_resp.raise_for_status()
    campaigns = (campaigns_resp.json() or {}).get("campaigns") or []
    if not campaigns:
        raise RuntimeError("No campaigns available for turn smoke test")

    for camp in campaigns:
        campaign_id = int(camp["id"])
        chars_resp = requests.get(f"{base_api_url}/campaigns/{campaign_id}/characters", timeout=20)
        if not chars_resp.ok:
            continue
        characters = (chars_resp.json() or {}).get("characters") or []
        if characters:
            return campaign_id, int(characters[0]["id"])

    raise RuntimeError("No character found in any campaign for turn smoke test")


def _post_settings(base_api_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = requests.post(
        f"{base_api_url}/settings/llm",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json() or {}


def _stream_turn(base_api_url: str, campaign_id: int, payload: dict[str, Any], timeout: int = 120) -> str:
    with requests.post(
        f"{base_api_url}/campaigns/{campaign_id}/turns/stream",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=timeout,
        stream=True,
    ) as resp:
        resp.raise_for_status()
        chunks: list[str] = []
        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            if not raw_line.startswith("data: "):
                continue
            line = raw_line[6:]
            chunks.append(line)
            if line == "[DONE]" or line.startswith("[ERROR]"):
                break
    return "\n".join(chunks)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8000/api")
    parser.add_argument("--provider-base-url", default="https://api.llmapi.ai")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--ollama-base-url", default="http://192.168.1.170:11434")
    parser.add_argument("--ollama-model", default="gemma3:1b")
    args = parser.parse_args()

    if not args.api_key.strip():
        return _fail("--api-key cannot be empty")

    # Save runtime into known stable state at the end (best effort).
    reset_payload = {
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model": "gemma4:e4b",
        "api_key": "",
    }

    try:
        set_payload = {
            "provider": "openai",
            "base_url": args.provider_base_url,
            "model": args.model,
            "api_key": args.api_key,
        }
        post_data = _post_settings(args.api_url, set_payload)
        masked = ((post_data.get("settings") or {}).get("api_key") or "").strip()
        if not masked.endswith("..."):
            return _fail("settings api_key is not masked in response")
        _ok("POST /settings/llm accepted openai runtime config")

        settings_resp = requests.get(f"{args.api_url}/settings/llm", timeout=20)
        settings_resp.raise_for_status()
        settings = settings_resp.json() or {}
        if settings.get("provider") != "openai":
            return _fail(f"Expected provider=openai, got {settings.get('provider')!r}")
        _ok("GET /settings/llm returns openai provider")

        health_resp = requests.get(f"{args.api_url}/health", timeout=30)
        health_resp.raise_for_status()
        health = health_resp.json() or {}
        llm = health.get("llm") or {}
        if llm.get("provider") != "openai":
            return _fail(f"/health provider mismatch: {llm.get('provider')!r}")
        if llm.get("reachable") is not True:
            return _fail(f"/health llm not reachable: {llm.get('error')}")
        _ok("GET /health reports openai provider reachable")

        campaign_id, character_id = _pick_campaign_and_character(args.api_url)
        _ok(f"Using campaign {campaign_id}, character {character_id}")

        turn_payload = {
            "character_id": character_id,
            "text": "Powiedz krótko co widzę wokół siebie.",
            "engine": args.model,
        }
        turn_resp = requests.post(
            f"{args.api_url}/campaigns/{campaign_id}/turns",
            headers={"Content-Type": "application/json"},
            data=json.dumps(turn_payload),
            timeout=90,
        )
        if not turn_resp.ok:
            return _fail(f"Turn request failed: HTTP {turn_resp.status_code} {turn_resp.text[:180]}")

        turn_data = turn_resp.json() or {}
        message = (((turn_data.get("result") or {}).get("message")) or "").strip()
        if not message:
            return _fail("Turn response message is empty")
        _ok("POST /campaigns/{id}/turns returned narrative message via openai provider")

        stream_payload = {
            "character_id": character_id,
            "text": "Daj krótki opis otoczenia.",
            "engine": args.model,
        }
        stream_result = _stream_turn(args.api_url, campaign_id, stream_payload)
        if "[ERROR]" in stream_result:
            return _fail(f"OpenAI stream returned error: {stream_result}")
        if "[DONE]" not in stream_result:
            return _fail(f"OpenAI stream did not finish correctly: {stream_result[:180]}")
        _ok("POST /turns/stream works via openai provider")

        ollama_set_payload = {
            "provider": "ollama",
            "base_url": args.ollama_base_url,
            "model": args.ollama_model,
            "api_key": "",
        }
        _post_settings(args.api_url, ollama_set_payload)
        _ok("Switched runtime to ollama provider")

        ollama_health_resp = requests.get(f"{args.api_url}/health", timeout=30)
        ollama_health_resp.raise_for_status()
        ollama_health = (ollama_health_resp.json() or {}).get("llm") or {}
        if ollama_health.get("provider") != "ollama":
            return _fail(f"Expected provider=ollama after switch, got {ollama_health.get('provider')!r}")
        if ollama_health.get("reachable") is not True:
            return _fail(f"Ollama provider not reachable after switch: {ollama_health.get('error')}")
        _ok("GET /health reports ollama reachable after provider switch")

        ollama_turn_payload = {
            "character_id": character_id,
            "text": "Co słyszę w oddali?",
            "engine": args.ollama_model,
        }
        ollama_turn_resp = requests.post(
            f"{args.api_url}/campaigns/{campaign_id}/turns",
            headers={"Content-Type": "application/json"},
            data=json.dumps(ollama_turn_payload),
            timeout=90,
        )
        if not ollama_turn_resp.ok:
            return _fail(f"Ollama non-stream turn failed after switch: {ollama_turn_resp.status_code} {ollama_turn_resp.text[:180]}")
        _ok("POST /turns (non-stream) works via ollama after switching provider")

        ollama_stream_payload = {
            "character_id": character_id,
            "text": "Opisz drzwi przede mną.",
            "engine": args.ollama_model,
        }
        ollama_stream = _stream_turn(args.api_url, campaign_id, ollama_stream_payload)
        if "[ERROR]" in ollama_stream:
            return _fail(f"Ollama stream returned error after switch: {ollama_stream}")
        if "[DONE]" not in ollama_stream:
            return _fail(f"Ollama stream did not finish correctly: {ollama_stream[:180]}")
        _ok("POST /turns/stream works via ollama after provider switch")

        print("SUCCESS: Phase 7.5 smoke test passed.")
        return 0
    except Exception as exc:
        return _fail(str(exc))
    finally:
        try:
            _post_settings(args.api_url, reset_payload)
            _ok("Runtime LLM settings reset to ollama defaults")
        except Exception as reset_exc:
            print(f"WARN: failed to reset runtime LLM settings: {reset_exc}")


if __name__ == "__main__":
    raise SystemExit(main())
