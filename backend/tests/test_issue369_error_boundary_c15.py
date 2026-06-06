"""TDD: Issue #369 — C15 error boundary: toast zamiast białego ekranu.

Tests verify:
- loadHeroes() has try/catch — no uncaught propagation on API failure
- apiRequest() catches network-level errors (TypeError / fetch failure)
- Unrecovered 401 triggers session-expired handler (not a raw throw)
- loadHeroes still loads heroes normally (backward compat)
"""
import re
import os

APP_JS = "/tmp/app_c15_test.js"


def _read_js() -> str:
    with open(APP_JS, encoding="utf-8") as f:
        return f.read()


def _extract_function_body(src: str, func_name: str) -> str:
    """Extract body of a named JS function by brace-counting."""
    pattern = re.compile(
        r"(?:async\s+)?function\s+" + re.escape(func_name) + r"\s*\([^)]*\)\s*\{"
    )
    m = pattern.search(src)
    if not m:
        return ""
    start = m.end() - 1
    depth = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start : i + 1]
    return src[start:]


# ─── C15.1: loadHeroes must have try/catch ──────────────────────────────────

def test_loadHeroes_has_try_catch():
    """loadHeroes must wrap apiRequest in try/catch so network failures show a toast."""
    src = _read_js()
    body = _extract_function_body(src, "loadHeroes")
    assert body, "loadHeroes nie znaleziono w app.js"
    assert "try" in body and "catch" in body, (
        "loadHeroes() nie ma try/catch — błąd API spowoduje biały ekran. "
        "Dodaj try/catch z showToast(..., 'error') na błąd."
    )


def test_loadHeroes_shows_toast_on_error():
    """loadHeroes catch block must call showToast to display the error."""
    src = _read_js()
    body = _extract_function_body(src, "loadHeroes")
    assert body, "loadHeroes nie znaleziono w app.js"
    # Find the catch block content
    catch_match = re.search(r"catch\s*\([^)]*\)\s*\{([^}]+)\}", body)
    assert catch_match, "loadHeroes catch block not found"
    catch_body = catch_match.group(1)
    assert "showToast" in catch_body, (
        "loadHeroes catch block nie wywołuje showToast — gracz nie dostanie komunikatu błędu."
    )


# ─── C15.2: apiRequest must catch network-level errors ──────────────────────

def test_apiRequest_handles_network_failure():
    """apiRequest must catch TypeError (network down) and convert to user-friendly error."""
    src = _read_js()
    body = _extract_function_body(src, "apiRequest")
    assert body, "apiRequest nie znaleziono w app.js"
    # Must have a try/catch around the fetch call (not just !response.ok check)
    assert "try" in body, (
        "apiRequest nie ma try/catch wokół fetch — błąd sieciowy (brak internetu) "
        "spowoduje nieobsłużony TypeError."
    )
    assert "catch" in body, (
        "apiRequest nie ma bloku catch — błąd sieciowy nie zostanie obsłużony."
    )


# ─── C15.3: unrecovered 401 must trigger session-expired handler ─────────────

def test_apiRequest_handles_unrecovered_401():
    """After a 401 that can't be refreshed, apiRequest must signal session expiry."""
    src = _read_js()
    body = _extract_function_body(src, "apiRequest")
    assert body, "apiRequest nie znaleziono w app.js"
    # Must either: call a logout/session-expired handler, OR set status=401 AND the
    # global error path checks for it. Simplest check: the number 401 appears in the
    # function with some session-related handling beyond just throw.
    # Check that a session-expired function exists or 401 is handled specially in throw path.
    has_session_handler = (
        "handleSessionExpired" in src
        or "sessionExpired" in src
        or "Sesja wygasła" in src
        or "session_expired" in src
        or "wygasła" in body
        or "wygasla" in body
    )
    assert has_session_handler, (
        "Brak obsługi wygasłej sesji (401) — po nieudanym odświeżeniu tokena gracz "
        "powinien dostać komunikat 'Sesja wygasła' i zostać wylogowany. "
        "Dodaj funkcję handleSessionExpired() lub obsługę 401 w apiRequest."
    )


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_apiRequest_still_throws_on_non_401_errors():
    """apiRequest must still throw on 4xx/5xx so callers can handle specific errors."""
    src = _read_js()
    body = _extract_function_body(src, "apiRequest")
    assert body, "apiRequest nie znaleziono w app.js"
    # Must still have throw for non-network errors
    assert "throw" in body, (
        "apiRequest nie rzuca błędów dla 4xx/5xx — callers nie mogą obsługiwać "
        "specyficznych błędów (np. 423 cooldown, 404 not found)."
    )


def test_loadHeroes_still_loads_heroes():
    """loadHeroes must still call apiRequest for heroes endpoint."""
    src = _read_js()
    body = _extract_function_body(src, "loadHeroes")
    assert body, "loadHeroes nie znaleziono w app.js"
    assert "heroes" in body and "apiRequest" in body, (
        "loadHeroes nie wywołuje apiRequest dla /heroes — backward compat broken."
    )
