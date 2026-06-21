"""TDD: Issue #593 — Web Push stack wiring.

Backend skeleton existed; this guards: VAPID public key surfaced from config,
subscription validation, and graceful no-op when unconfigured.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402

from app.services import push_notification_service as pns  # noqa: E402


def test_vapid_public_key_reflects_config(monkeypatch):
    monkeypatch.setattr(pns, "_VAPID_PUBLIC_KEY", "BJxyz_publickey")
    assert pns.get_vapid_public_key() == "BJxyz_publickey"


def test_is_configured_requires_both_keys(monkeypatch):
    monkeypatch.setattr(pns, "_VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setattr(pns, "_VAPID_PUBLIC_KEY", "pub")
    assert pns._is_configured() is True
    monkeypatch.setattr(pns, "_VAPID_PUBLIC_KEY", "")
    assert pns._is_configured() is False


def test_send_push_noop_when_unconfigured(monkeypatch):
    """Unconfigured stack must not raise — just warn + return (no crash on turn end)."""
    monkeypatch.setattr(pns, "_VAPID_PRIVATE_KEY", "")
    monkeypatch.setattr(pns, "_VAPID_PUBLIC_KEY", "")
    # Should return None without touching DB / raising.
    assert pns.send_push(1, "t", "b") is None


def test_save_subscription_rejects_incomplete():
    with pytest.raises(ValueError):
        pns.save_subscription(1, {"endpoint": "", "keys": {}})


def test_pywebpush_importable():
    """#593: dependency must be installed in the image (was missing → ImportError no-op)."""
    import importlib
    assert importlib.util.find_spec("pywebpush") is not None


def test_configured_vapid_private_key_is_loadable():
    """#593: a configured VAPID_PRIVATE_KEY must actually load (a corrupt/truncated
    key silently breaks delivery). Skips when push isn't configured."""
    priv = os.getenv("VAPID_PRIVATE_KEY", "")
    if not priv:
        pytest.skip("VAPID not configured in this environment")
    from py_vapid import Vapid01
    # raw base64url scalar format used by send_push — must not raise
    Vapid01.from_raw(priv.encode())


# ─── Round 4: server-readiness diagnostics (end the blind remote-debug loop) ──

def test_get_diagnostics_reports_server_readiness(monkeypatch):
    """#593: a single call must report whether the server can actually push —
    so the on-screen panel can show config status instead of us guessing."""
    monkeypatch.setattr(pns, "_VAPID_PRIVATE_KEY", "x" * 43)
    monkeypatch.setattr(pns, "_VAPID_PUBLIC_KEY", "y" * 87)
    monkeypatch.setattr(pns, "_VAPID_EMAIL", "mailto:a@b.c")
    d = pns.get_diagnostics()
    assert d["configured"] is True
    assert d["public_key_len"] == 87
    assert d["private_key_len"] == 43
    assert d["has_email"] is True
    assert d["pywebpush_installed"] is True
    assert "private_key_loadable" in d  # may be False for the dummy key — key is presence


def test_diagnostics_never_leaks_secrets(monkeypatch):
    """Diagnostics is an UNAUTHENTICATED endpoint — it must expose lengths/bools,
    never the raw private key material."""
    monkeypatch.setattr(pns, "_VAPID_PRIVATE_KEY", "supersecretprivkey")
    d = pns.get_diagnostics()
    assert "supersecretprivkey" not in str(d)


def test_diagnostics_endpoint_returns_200():
    """#593: GET /api/push/diagnostics must be reachable for the UI panel."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        r = c.get("/api/push/diagnostics")
        assert r.status_code == 200
        body = r.json()
        assert "configured" in body
        assert "pywebpush_installed" in body
