"""
Throwaway measurement harness for issue #940 token / prompt-cache audit.

Does NOT touch app code. Reuses the real effective LLM config + the real
composed narrator system prompt, fires a few raw /v1/chat/completions calls
with tiny max_tokens, and prints the usage block (incl. cached_tokens) so we
can see whether OpenAI is ALREADY caching our ~13k stable prefix.

Run inside the dev backend container:
    docker cp tools/measure_cache.py ai-gm-dev-backend-1:/app/measure_cache.py
    docker exec ai-gm-dev-backend-1 python /app/measure_cache.py
"""
import json
import time

import httpx

from app.services.llm_service import get_effective_config, _resolve_model
from app.system_prompt_loader import compose_narrator_system_prompt

eff = get_effective_config(None, strict=True)
provider = eff["provider"]
base_url = eff["base_url"]
api_key = eff["api_key"]
model = _resolve_model(None, eff)

print(f"provider={provider} model={model} base_url={base_url}")
if provider not in ("openai", "azure"):
    print("NOTE: effective provider is not OpenAI — cached_tokens only meaningful on OpenAI.")

SYS = compose_narrator_system_prompt()
# mimic turn_engine.buildmessages (non-combat): stable prefix first, dynamic last
sys_noncombat = (
    f"{SYS}\n"
    "System gry: fantasy\n"
    "Język: pl\n"
    "Postać gracza: Bohater"
)
# combat variant: combat block appended AFTER the stable system+lore prefix
combat_block = (
    "== KONTEKST WALKI ==\n"
    "Tura 3. Wrogowie: Goblin (HP 6/12, zwarcie). Bohater HP 18/22, strefa: zwarcie.\n"
    "Inicjatywa: Bohater, Goblin."
)
sys_combat = (
    f"{SYS.rstrip()}\n\n{combat_block}\n"
    "System gry: fantasy\n"
    "Język: pl\n"
    "Postać gracza: Bohater"
)

history = [
    {"role": "user", "content": "Rozglądam się po polanie."},
    {"role": "assistant", "content": "Mgła wisi nad mokrą trawą; w oddali skrzeczy ptak."},
]
user_text = "Idę w stronę traktu."


def call(label, system_content):
    # mirror the real OpenAIDriver payload exactly (temp 0.8, no max_tokens)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_content}, *history,
                     {"role": "user", "content": user_text}],
        "stream": False,
        "temperature": 0.8,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    t0 = time.perf_counter()
    with httpx.Client(timeout=120) as c:
        r = c.post(f"{base_url}/v1/chat/completions", json=payload, headers=headers)
        if r.status_code >= 400:
            print(f"[{label}] HTTP {r.status_code}: {r.text[:500]}")
            r.raise_for_status()
        data = r.json()
    dt = (time.perf_counter() - t0) * 1000
    u = data.get("usage", {}) or {}
    details = u.get("prompt_tokens_details", {}) or {}
    print(f"[{label}] {dt:6.0f}ms  prompt={u.get('prompt_tokens')}  "
          f"cached={details.get('cached_tokens')}  completion={u.get('completion_tokens')}  "
          f"total={u.get('total_tokens')}")
    return u


print("\n--- baseline: 3x identical non-combat (call1=cold, 2/3 should be cached) ---")
call("noncombat#1", sys_noncombat)
time.sleep(1)
call("noncombat#2", sys_noncombat)
time.sleep(1)
call("noncombat#3", sys_noncombat)

print("\n--- combat turn: dynamic block appended AFTER stable prefix ---")
call("combat#1", sys_combat)
time.sleep(1)
call("combat#2", sys_combat)

print("\n--- sanity: prefix mutated at very start (cache should DROP to 0) ---")
call("mutated", " " + sys_noncombat)

print("\ndone.")
