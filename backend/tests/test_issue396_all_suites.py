"""TDD: Issue #396 — All ux suites grouped (regression/acceptance/admin3) in Playwright panel."""
import hashlib
import sqlite3
import sys

sys.path.insert(0, "/app")

import pytest
from fastapi.testclient import TestClient
from app.main import app

DB_PATH = "/data/ai_gm.db"
_TEST_ADMIN_TOKEN = "tdd_test_token_396_suites"
client = TestClient(app)


def _admin_hash() -> str:
    return hashlib.sha256(_TEST_ADMIN_TOKEN.encode()).hexdigest()


@pytest.fixture(autouse=True)
def setup_teardown():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO admin_tokens (token_hash, label) VALUES (?, 'tdd_396')",
            (_admin_hash(),),
        )
        conn.commit()
    finally:
        conn.close()
    yield
    conn2 = sqlite3.connect(DB_PATH)
    try:
        conn2.execute("DELETE FROM admin_tokens WHERE token_hash = ?", (_admin_hash(),))
        conn2.commit()
    finally:
        conn2.close()


def _auth():
    return {"Authorization": f"Bearer {_TEST_ADMIN_TOKEN}"}


def _get_specs() -> list:
    resp = client.get("/api/test_runner/playwright-specs", headers=_auth())
    assert resp.status_code == 200
    data = resp.json()
    if data.get("error"):
        pytest.skip(f"test-agent not reachable: {data['error'][:100]}")
    return data.get("specs", [])


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_specs_endpoint_accessible():
    """GET /playwright-specs z tokenem → 200."""
    resp = client.get("/api/test_runner/playwright-specs", headers=_auth())
    assert resp.status_code == 200


def test_specs_have_group_field():
    """Każdy spec ma pole 'group' — z #396 recursive scan po ux/**."""
    specs = _get_specs()
    if not specs:
        pytest.skip("No specs returned")
    for spec in specs:
        assert "group" in spec, f"Spec missing 'group': {spec}"


def test_regression_group_exists():
    """Group 'regression' istnieje w wynikach (ux/regression/*.spec.js)."""
    specs = _get_specs()
    groups = {s.get("group") for s in specs}
    assert "regression" in groups, f"'regression' group missing, found: {groups}"


def test_admin3_group_exists():
    """Group 'admin3' istnieje (ux/admin3/admin3_smoke.spec.js z #396)."""
    specs = _get_specs()
    groups = {s.get("group") for s in specs}
    assert "admin3" in groups, f"'admin3' group missing, found: {groups}"


def test_multiple_groups_returned():
    """Więcej niż jeden group — nie tylko regression."""
    specs = _get_specs()
    groups = {s.get("group") for s in specs}
    assert len(groups) > 1, f"Expected multiple groups (regression + admin3), got: {groups}"


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_regression_specs_still_discoverable():
    """Stare regression speci (issue_NNN) nadal widoczne — nie zniknęły po zmianie."""
    specs = _get_specs()
    regression_specs = [s for s in specs if s.get("group") == "regression"]
    assert len(regression_specs) > 5, \
        f"Expected many regression specs, found only {len(regression_specs)}: {regression_specs}"


def test_spec_entries_have_required_fields():
    """Każdy spec ma pola: file (lub path), group, description lub name."""
    specs = _get_specs()
    for spec in specs:
        has_path = "file" in spec or "path" in spec or "name" in spec or "filename" in spec
        assert has_path, f"Spec missing path/file/name/filename field: {spec}"
        assert "group" in spec, f"Spec missing group: {spec}"
