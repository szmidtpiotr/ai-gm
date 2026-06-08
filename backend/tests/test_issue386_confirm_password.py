"""TDD: Issue #386 D11 — confirm password field in register form."""
import sys
import urllib.request

sys.path.insert(0, "/app")

import pytest

FRONTEND_URL = "http://frontend:80"


def _fetch_html(path: str = "/") -> str:
    with urllib.request.urlopen(f"{FRONTEND_URL}{path}", timeout=5) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _fetch_js(path: str) -> str:
    with urllib.request.urlopen(f"{FRONTEND_URL}{path}", timeout=5) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_register_form_has_confirm_password_field():
    """Formularz rejestracji zawiera pole 'Powtórz hasło'."""
    html = _fetch_html("/")
    assert "register-password-confirm" in html, (
        "register form must have #register-password-confirm field"
    )


def test_register_form_confirm_field_is_password_type():
    """Pole potwierdzenia hasła jest typu password."""
    html = _fetch_html("/")
    assert 'id="register-password-confirm"' in html, "confirm field must exist with correct id"
    idx = html.find('id="register-password-confirm"')
    context = html[max(0, idx - 150):idx + 300]
    assert 'type="password"' in context, f"confirm field must be type=password, context: {context}"


def test_app_js_validates_password_match():
    """app.js zawiera walidację zgodności haseł przy rejestracji."""
    js = _fetch_js("/front/js/app.js")
    assert "register-password-confirm" in js, (
        "app.js must reference register-password-confirm for validation"
    )


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_register_form_still_has_original_password_field():
    """Oryginalne pole hasła nadal istnieje."""
    html = _fetch_html("/")
    assert 'id="register-password"' in html, "original #register-password field must still exist"


def test_register_error_message_element_exists():
    """Element komunikatu błędu (#register-error) nadal istnieje."""
    html = _fetch_html("/")
    assert 'id="register-error"' in html, "#register-error element must exist"
