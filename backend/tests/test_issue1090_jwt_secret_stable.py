"""TDD: Issue #1090 — JWT secret must come from env, not ephemeral hostname."""
import hashlib
import os
import sys

sys.path.insert(0, "/app")


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_jwt_secret_uses_env_when_set():
    """When JWT_SECRET env is set, _secret() returns it (not a derived fallback)."""
    expected = "test_stable_secret_abc123"
    original = os.environ.get("JWT_SECRET")
    try:
        os.environ["JWT_SECRET"] = expected
        from app.services import jwt_service
        result = jwt_service._secret()
        assert result == expected, (
            f"_secret() returned {result!r} instead of env value {expected!r}"
        )
    finally:
        if original is None:
            os.environ.pop("JWT_SECRET", None)
        else:
            os.environ["JWT_SECRET"] = original


def test_jwt_fallback_not_hostname_based():
    """Dev fallback must NOT use os.uname().nodename (ephemeral container hostname).

    The docstring promises a hash of the DB path — the code must match.
    Hostname changes on every docker rebuild → all tokens invalidated.
    """
    original = os.environ.get("JWT_SECRET")
    try:
        os.environ.pop("JWT_SECRET", None)
        # Reload module to get fresh _secret() call without env
        import importlib
        from app.services import jwt_service
        importlib.reload(jwt_service)

        fallback = jwt_service._secret()

        # The fallback MUST NOT be derived from hostname
        hostname = os.uname().nodename
        hostname_based = hashlib.sha256(
            (hostname + "::ai_gm::dev_jwt_fallback").encode("utf-8")
        ).hexdigest()
        assert fallback != hostname_based, (
            f"Fallback secret is still hostname-based ({hostname!r}). "
            "This means every docker rebuild invalidates all player tokens. "
            "Fix: use a stable seed (e.g. hash of DB path) instead of os.uname().nodename."
        )
    finally:
        if original is not None:
            os.environ["JWT_SECRET"] = original


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_tokens_survive_service_restart_with_env_set():
    """Tokens issued before and after module reload must verify — env secret is stable."""
    import importlib
    from app.services import jwt_service

    os.environ["JWT_SECRET"] = "stable_test_secret_xyz789"
    importlib.reload(jwt_service)

    token = jwt_service.issue_access_token(
        user_id=42, username="tester", role="player", is_admin=0
    )

    # Simulate restart: reload module
    importlib.reload(jwt_service)

    payload = jwt_service.verify_token(token, expected_type="access")
    assert payload["sub"] == "42", "Token must survive module reload when env secret is stable"

    # cleanup
    os.environ.pop("JWT_SECRET", None)
