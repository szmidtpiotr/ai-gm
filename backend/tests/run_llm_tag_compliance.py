#!/usr/bin/env python3
"""
LLM Tag Compliance Test — AI-GM project

Tests whether GPT model variants correctly emit game-critical tags.
Run before adopting a cheaper model to catch regressions before they hit gameplay.

Each test is either CRITICAL (broken game) or INFO (degraded experience).
A model is safe to use only if all critical tests pass across all runs.

Usage:
  python backend/tests/run_llm_tag_compliance.py --api-key sk-...
  python backend/tests/run_llm_tag_compliance.py --api-key sk-... --models gpt-5.4,gpt-5.4-mini,gpt-5.4-nano
  python backend/tests/run_llm_tag_compliance.py --api-key sk-... --models gpt-5.4-mini --repeat 3
  python backend/tests/run_llm_tag_compliance.py --api-key sk-... --base-url https://api.llmapi.ai
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Callable

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.txt"
DEFAULT_BASE_URL = "https://api.openai.com"

VALID_ENEMY_KEYS = {
    "bandit", "goblin", "orc", "skeleton", "wolf",
    "troll", "guard", "old_man", "unknown_attacker", "enemy",
}


def _load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _call_model(base_url: str, api_key: str, model: str, messages: list[dict], timeout: int = 90) -> str:
    base = base_url.rstrip("/")
    # Avoid double /v1 if caller already includes it
    if not base.endswith("/v1"):
        base += "/v1"
    url = base + "/chat/completions"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0.7, "max_completion_tokens": 600},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_json(raw: str) -> dict | None:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def _build_messages(sys_prompt: str, extra_system: str = "", history: list | None = None, user_msg: str = "") -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": sys_prompt}]
    if extra_system:
        msgs.append({"role": "system", "content": extra_system})
    for h in (history or []):
        msgs.append(h)
    msgs.append({"role": "user", "content": user_msg})
    return msgs


# ──────────────────────────────────────────────────────── test registry ───

TESTS: list[dict] = []


def test(name: str, critical: bool = True, desc: str = ""):
    def decorator(fn: Callable) -> Callable:
        TESTS.append({"name": name, "fn": fn, "critical": critical, "desc": desc})
        return fn
    return decorator


# ─────────────────────────────────────────────────────────── test cases ───

@test("json_format", critical=True, desc="Every response must be valid JSON with 'narrative' field")
def t_json_format(base_url: str, api_key: str, model: str, sys_prompt: str) -> tuple[bool, str]:
    msgs = _build_messages(sys_prompt, user_msg="Rozglądam się po karczmie.")
    raw = _call_model(base_url, api_key, model, msgs)
    data = _parse_json(raw)
    if data is None:
        return False, f"NOT JSON — starts with: {raw[:100]!r}"
    if "narrative" not in data:
        return False, f"missing 'narrative' key, got: {sorted(data.keys())}"
    if not isinstance(data["narrative"], str) or not data["narrative"].strip():
        return False, "narrative is empty"
    if "location_intent" not in data:
        return False, f"missing 'location_intent' key — partial JSON compliance"
    return True, f"ok — keys={sorted(data.keys())}"


@test("no_roll_on_passive_look", critical=True,
      desc="'Rozglądam się' must NOT produce roll_cue (system prompt §BEZWZGLĘDNY ZAKAZ)")
def t_no_roll_passive(base_url: str, api_key: str, model: str, sys_prompt: str) -> tuple[bool, str]:
    msgs = _build_messages(sys_prompt, user_msg="Rozglądam się po sali karczmy. Co widzę dookoła?")
    raw = _call_model(base_url, api_key, model, msgs)
    data = _parse_json(raw)

    if data:
        rc = data.get("roll_cue")
        if rc and str(rc).strip():
            return False, f"bogus roll_cue on passive look: {rc!r}"
        return True, "ok — no roll_cue"

    # plain text fallback
    lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    if re.match(r"Roll\s+\w+\s+d20", last, re.IGNORECASE):
        return False, f"spurious Roll on passive look (last line): {last!r}"
    return True, "ok — no Roll in plain text"


@test("combat_start_on_attack", critical=True,
      desc="Player 'Atakuję!' must produce [COMBAT_START:key] or Roll Initiative d20")
def t_combat_start(base_url: str, api_key: str, model: str, sys_prompt: str) -> tuple[bool, str]:
    extra = (
        "[AVAILABLE CONTENT]\n"
        "Wrogowie w tym świecie (używaj WYŁĄCZNIE tych kluczy w [COMBAT_START:]):\n"
        "bandit — bandyta/zbir; goblin; orc; skeleton; wolf; troll; "
        "guard — strażnik; old_man — starzec; unknown_attacker; enemy\n"
    )
    history = [
        {"role": "assistant", "content": json.dumps({
            "narrative": "Stoisz w zadymionej karczmie. Przy barze siedzi bandzior z nożem za pasem, wpatrując się w ciebie wrogo.",
            "location_intent": None,
        })},
    ]
    msgs = _build_messages(sys_prompt, extra_system=extra, history=history, user_msg="Atakuję bandytę!")
    raw = _call_model(base_url, api_key, model, msgs)

    data = _parse_json(raw)
    if data:
        rc = str(data.get("roll_cue") or "")
        if re.search(r"\[COMBAT_START:[^\]]+\]", rc):
            return True, f"ok — roll_cue={rc!r}"
        if re.search(r"Roll Initiative d20", rc, re.IGNORECASE):
            return True, f"ok — fallback initiative: {rc!r}"
        # Check narrative — wrong position but may still parse
        narr = str(data.get("narrative") or "")
        if re.search(r"\[COMBAT_START:[^\]]+\]", narr):
            return False, f"COMBAT_START in narrative (not roll_cue) — wrong field: …{narr[-80:]!r}"
        return False, f"no COMBAT_START/Initiative — roll_cue={rc!r}"

    # plain text
    if re.search(r"\[COMBAT_START:[^\]]+\]", raw):
        return True, "ok — plain text COMBAT_START"
    if re.search(r"Roll Initiative d20", raw, re.IGNORECASE):
        return True, "ok — plain text Roll Initiative d20"
    return False, f"no combat tag — tail: {raw[-120:]!r}"


@test("combat_key_from_catalog", critical=True,
      desc="[COMBAT_START] key must be from catalog, not invented (e.g. 'zbir' not valid)")
def t_enemy_key(base_url: str, api_key: str, model: str, sys_prompt: str) -> tuple[bool, str]:
    extra = (
        "[AVAILABLE CONTENT]\n"
        "Wrogowie w tym świecie (klucze do [COMBAT_START:]):\n"
        "bandit — bandyta/zbir/rabus; goblin; orc; skeleton; wolf; "
        "troll; guard — strażnik; old_man — starzec; unknown_attacker; enemy\n"
    )
    history = [
        {"role": "assistant", "content": json.dumps({
            "narrative": "Trzej zbiry otaczają cię w ciemnej uliczce. Ich oczy błyszczą chciwością.",
            "location_intent": None,
        })}
    ]
    msgs = _build_messages(sys_prompt, extra_system=extra, history=history,
                           user_msg="Wyciągam miecz i atakuję!")
    raw = _call_model(base_url, api_key, model, msgs)

    m = re.search(r"\[COMBAT_START:([^\]]+)\]", raw)
    if not m:
        # Maybe Roll Initiative d20 — that's also acceptable
        if re.search(r"Roll Initiative d20", raw, re.IGNORECASE):
            return True, "ok — Roll Initiative d20 (no key to validate)"
        return False, "no COMBAT_START tag found"

    keys = [k.strip() for k in m.group(1).split(",")]
    bad = [k for k in keys if k not in VALID_ENEMY_KEYS]
    if bad:
        return False, f"invented key(s): {bad} (valid: bandit/goblin/orc/guard/…)"
    return True, f"ok — keys={keys}"


@test("stealth_roll_cue", critical=True,
      desc="'Skradam się' action → roll_cue must be exactly 'Roll Stealth d20'")
def t_stealth_cue(base_url: str, api_key: str, model: str, sys_prompt: str) -> tuple[bool, str]:
    history = [
        {"role": "assistant", "content": json.dumps({
            "narrative": "Strażnik patroluje ciemny korytarz zamku, niosąc pochodnię. Przechodzi powoli.",
            "location_intent": None,
        })}
    ]
    msgs = _build_messages(sys_prompt, history=history,
                           user_msg="Skradam się za strażnikiem, żeby go zaskoczyć.")
    raw = _call_model(base_url, api_key, model, msgs)

    data = _parse_json(raw)
    if data:
        rc = str(data.get("roll_cue") or "").strip()
        if re.fullmatch(r"Roll Stealth d20", rc, re.IGNORECASE):
            return True, f"ok — roll_cue={rc!r}"
        if rc:
            return False, f"wrong roll_cue={rc!r} (expected 'Roll Stealth d20')"
        return False, "missing roll_cue on stealth action"

    lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    if re.fullmatch(r"Roll Stealth d20", last, re.IGNORECASE):
        return True, f"ok — plain text last line: {last!r}"
    return False, f"wrong last line: {last!r}"


@test("open_shop_merchant", critical=True,
      desc="Merchant (is_shop=1) + trade intent → last narrative line: 'Open Shop <key>'")
def t_open_shop(base_url: str, api_key: str, model: str, sys_prompt: str) -> tuple[bool, str]:
    extra = (
        "[NPC CONTEXT]\n"
        "W scenie obecni NPC:\n"
        "- Aldric (key: merchant_aldric, npc_type: merchant, is_shop: 1) — handlarz bronią przy straganie.\n"
    )
    history = [
        {"role": "assistant", "content": json.dumps({
            "narrative": "Wchodzisz na rynek. Aldric krząta się przy swoim straganie z bronią i miksturami.",
            "location_intent": None,
        })}
    ]
    msgs = _build_messages(sys_prompt, extra_system=extra, history=history,
                           user_msg="Podchodzę do Aldrica. Co masz na sprzedaż?")
    raw = _call_model(base_url, api_key, model, msgs)

    data = _parse_json(raw)
    narr: str = data.get("narrative", "") if data else raw
    lines = [ln.strip() for ln in narr.strip().splitlines() if ln.strip()]
    last = lines[-1] if lines else ""

    m = re.match(r"Open Shop\s+(\S+)", last, re.IGNORECASE)
    if m:
        key = m.group(1)
        if key == "merchant_aldric":
            return True, f"ok — Open Shop {key}"
        return False, f"wrong key in: 'Open Shop {key}' (expected merchant_aldric)"

    # Look anywhere in the response — misplaced but maybe still parseable
    if re.search(r"Open Shop\s+merchant_aldric", narr, re.IGNORECASE):
        return False, f"Open Shop present but NOT as last narrative line — will be missed by parser"
    if re.search(r"Open Shop", narr, re.IGNORECASE):
        m2 = re.search(r"Open Shop\s+(\S+)", narr, re.IGNORECASE)
        return False, f"Open Shop with wrong key or position: {m2.group() if m2 else '?'!r}"
    return False, f"no 'Open Shop' — last line={last!r}"


@test("grant_item_pickup", critical=True,
      desc="Player picks up item → 'grant_item' JSON field or 'Grant Item' last-line cue")
def t_grant_item(base_url: str, api_key: str, model: str, sys_prompt: str) -> tuple[bool, str]:
    history = [
        {"role": "assistant", "content": json.dumps({
            "narrative": "Na drewnianym stole leży stary miecz, trochę zardzewiały, ale wciąż solidny.",
            "location_intent": None,
        })}
    ]
    msgs = _build_messages(sys_prompt, history=history, user_msg="Biorę miecz ze stołu.")
    raw = _call_model(base_url, api_key, model, msgs)

    data = _parse_json(raw)
    if data:
        gi = data.get("grant_item")
        if gi:
            return True, f"ok — grant_item={gi!r}"
        narr = str(data.get("narrative") or "")
        lines = [ln.strip() for ln in narr.strip().splitlines() if ln.strip()]
        last = lines[-1] if lines else ""
        if re.match(r"Grant Item\s+.+", last, re.IGNORECASE):
            return True, f"ok — old-style cue in narrative: {last!r}"
        return False, f"no grant_item field and no Grant Item cue"

    # plain text
    lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    if re.match(r"Grant Item\s+.+", last, re.IGNORECASE):
        return True, f"ok — plain text Grant Item: {last!r}"
    if re.search(r"grant.?item", raw, re.IGNORECASE):
        return False, "grant_item-like text found but wrong format"
    return False, "no grant_item signal"


@test("no_false_combat_on_dialogue", critical=True,
      desc="Dialogue / peaceful action must NOT trigger [COMBAT_START] or Roll Initiative")
def t_no_false_combat(base_url: str, api_key: str, model: str, sys_prompt: str) -> tuple[bool, str]:
    msgs = _build_messages(
        sys_prompt,
        user_msg="Podchodzę do karczmarza i mówię: Dobry wieczór, czy macie wolny pokój na noc?"
    )
    raw = _call_model(base_url, api_key, model, msgs)

    if re.search(r"\[COMBAT_START", raw, re.IGNORECASE):
        return False, f"false COMBAT_START on dialogue"
    if re.search(r"Roll Initiative d20", raw, re.IGNORECASE):
        return False, "false Roll Initiative on dialogue"
    return True, "ok — no spurious combat trigger"


@test("apply_condition_zaskoczony", critical=False,
      desc="Stealth success + attack → [APPLY_CONDITION:zaskoczony:guard] in narrative (INFO only)")
def t_apply_condition(base_url: str, api_key: str, model: str, sys_prompt: str) -> tuple[bool, str]:
    extra = (
        "[AVAILABLE CONTENT]\n"
        "Wrogowie w tym świecie: guard — strażnik/straż\n"
    )
    history = [
        {"role": "assistant", "content": json.dumps({
            "narrative": "Strażnik patroluje ciemny korytarz, niosąc pochodnię. Nie słyszy twoich kroków.",
            "location_intent": None,
        })}
    ]
    msgs = _build_messages(
        sys_prompt,
        extra_system=extra,
        history=history,
        user_msg=(
            "Skradam się za strażnikiem i atakuję go z zaskoczenia! "
            "Mój wynik testu Stealth: 14 — sukces (DC 8)."
        ),
    )
    raw = _call_model(base_url, api_key, model, msgs)

    if re.search(r"\[APPLY_CONDITION:zaskoczony:guard\]", raw, re.IGNORECASE):
        return True, "ok — APPLY_CONDITION:zaskoczony:guard present"
    m = re.search(r"\[APPLY_CONDITION:zaskoczony:([^\]]+)\]", raw, re.IGNORECASE)
    if m:
        return False, f"APPLY_CONDITION with wrong key: {m.group(1)!r} (expected guard)"
    if re.search(r"\[APPLY_CONDITION", raw):
        return False, "APPLY_CONDITION present but malformed"
    return False, "no [APPLY_CONDITION:zaskoczony:guard] — model skipped the tag"


# ─────────────────────────────────────────────────────────────── runner ───

def run_tests(base_url: str, api_key: str, models: list[str], repeat: int) -> None:
    sys_prompt = _load_system_prompt()

    # results[model][test_name] = list[(ok, detail)]
    results: dict[str, dict[str, list[tuple[bool, str]]]] = {m: {} for m in models}

    for model in models:
        print(f"\n{'═' * 64}")
        print(f"  Model: {model}")
        print(f"{'═' * 64}")

        for tc in TESTS:
            name = tc["name"]
            fn = tc["fn"]
            critical = tc["critical"]
            runs: list[tuple[bool, str]] = []

            for r in range(repeat):
                try:
                    ok, detail = fn(base_url, api_key, model, sys_prompt)
                    runs.append((ok, detail))
                    tag = "PASS" if ok else "FAIL"
                    crit_flag = "  ← CRITICAL" if (not ok and critical) else ""
                    run_label = f"[run {r + 1}/{repeat}]" if repeat > 1 else ""
                    print(f"  [{tag}] {name} {run_label}: {detail}{crit_flag}")
                except requests.HTTPError as e:
                    runs.append((False, f"HTTP {e.response.status_code}: {e.response.text[:120]}"))
                    print(f"  [ERR ] {name}: {runs[-1][1]}")
                except Exception as e:
                    runs.append((False, f"EXCEPTION: {e}"))
                    print(f"  [ERR ] {name}: {e}")

                if r < repeat - 1:
                    time.sleep(0.8)

            results[model][name] = runs
            time.sleep(0.5)

    # ── Summary ──────────────────────────────────────────────────────────────
    COL = 24
    print(f"\n\n{'═' * 64}")
    print("  SUMMARY")
    print(f"{'═' * 64}")
    print(f"  {'Test':<34}", end="")
    for m in models:
        print(f" {m[:COL]:<{COL}}", end="")
    print()
    print("  " + "-" * (34 + (COL + 1) * len(models)))

    for tc in TESTS:
        name = tc["name"]
        critical = tc["critical"]
        prefix = "* " if critical else "  "
        label = f"{prefix}{name}"
        print(f"  {label:<34}", end="")
        for m in models:
            runs = results[m].get(name, [])
            if not runs:
                print(f" {'N/A':<{COL}}", end="")
                continue
            passes = sum(1 for ok, _ in runs if ok)
            total = len(runs)
            if passes == total:
                sym = "✓"
            elif passes > 0:
                sym = "~"
            else:
                sym = "✗"
            print(f" {sym} {passes}/{total}{'':<{COL - 5}}", end="")
        print()

    print(f"\n  * = CRITICAL (gameplay breaks on failure)")

    # ── Verdict ───────────────────────────────────────────────────────────────
    print(f"\n{'═' * 64}")
    print("  VERDICT")
    print(f"{'═' * 64}")
    for m in models:
        all_runs = [(ok, tc) for tc in TESTS for ok, _ in results[m].get(tc["name"], [])]
        total = len(all_runs)
        passed = sum(1 for ok, _ in all_runs if ok)
        crit_fails = sum(
            1 for tc in TESTS if tc["critical"]
            for ok, _ in results[m].get(tc["name"], [])
            if not ok
        )
        pct = 100 * passed // total if total else 0
        if crit_fails == 0:
            verdict = "SAFE TO USE"
        else:
            verdict = f"BLOCKED — {crit_fails} critical failure(s)"
        print(f"  {m}: {pct}% ({passed}/{total}) — {verdict}")


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM tag compliance test for AI-GM")
    parser.add_argument("--api-key", required=True, help="OpenAI-compatible API key")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"API base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--models", default="gpt-5.4,gpt-5.4-mini,gpt-5.4-nano",
                        help="Comma-separated model names to test")
    parser.add_argument("--repeat", type=int, default=1,
                        help="Runs per test per model (higher = more reliable stats, slower)")
    args = parser.parse_args()

    if not args.api_key.strip():
        print("ERROR: --api-key required")
        return 1

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        print("ERROR: --models is empty")
        return 1

    print(f"Tag compliance test")
    print(f"  Base URL : {args.base_url}")
    print(f"  Models   : {models}")
    print(f"  Repeat   : {args.repeat}x per test")
    print(f"  Tests    : {len(TESTS)} ({sum(1 for t in TESTS if t['critical'])} critical)")

    run_tests(args.base_url, args.api_key, models, args.repeat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
