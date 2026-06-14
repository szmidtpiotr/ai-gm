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
