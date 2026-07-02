"""TDD: Issue #1065 — paginacja historii tur kampanii (offset + total_count)."""
import sys
import os
import sqlite3
import pytest

sys.path.insert(0, "/app")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_admin_token():
    for creds in [{"username": "demo", "password": "demo"}, {"username": "admin", "password": "admin"}]:
        resp = client.post("/api/admin/dev-login", json=creds)
        if resp.status_code == 200:
            return resp.json().get("token")
    return None


def _campaign_with_turns(min_turns: int = 3):
    """Return (campaign_id, owner_user_id) for campaign with ≥min_turns."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT c.id, c.owner_user_id
               FROM campaigns c
               WHERE (SELECT COUNT(*) FROM campaign_turns ct WHERE ct.campaign_id = c.id) >= ?
               ORDER BY (SELECT COUNT(*) FROM campaign_turns ct WHERE ct.campaign_id = c.id) DESC
               LIMIT 1""",
            (min_turns,)
        ).fetchone()
        if not row:
            return None, None
        return int(row["id"]), int(row["owner_user_id"])
    finally:
        conn.close()


def _count_turns(campaign_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ?",
            (campaign_id,)
        ).fetchone()[0]
    finally:
        conn.close()


# ─── Player turns-history pagination ─────────────────────────────────────────

class TestPlayerTurnsHistoryPagination:
    """GET /api/campaigns/{id}/turns-history must support offset + return total_count."""

    def test_turns_history_returns_total_count(self):
        """Response must include total_count field (#1065)."""
        campaign_id, owner_uid = _campaign_with_turns(3)
        if not campaign_id:
            pytest.skip("No campaign with ≥3 turns found")

        resp = client.get(
            f"/api/campaigns/{campaign_id}/turns-history?limit=5&user_id={owner_uid}"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "total_count" in data, "Response must include total_count (#1065)"
        expected = _count_turns(campaign_id)
        assert data["total_count"] == expected, \
            f"total_count {data['total_count']} != DB count {expected}"

    def test_turns_history_offset_returns_different_page(self):
        """offset=N skips first N turns, returning a non-overlapping page (#1065)."""
        campaign_id, owner_uid = _campaign_with_turns(5)
        if not campaign_id:
            pytest.skip("No campaign with ≥5 turns found")

        r1 = client.get(
            f"/api/campaigns/{campaign_id}/turns-history?limit=2&offset=0&user_id={owner_uid}"
        )
        r2 = client.get(
            f"/api/campaigns/{campaign_id}/turns-history?limit=2&offset=2&user_id={owner_uid}"
        )
        assert r1.status_code == 200
        assert r2.status_code == 200

        nums_p1 = {t["turn_number"] for t in r1.json()["turns"]}
        nums_p2 = {t["turn_number"] for t in r2.json()["turns"]}

        if nums_p1 and nums_p2:
            assert not nums_p1 & nums_p2, \
                f"Pages overlap: {nums_p1 & nums_p2}"

    def test_turns_history_backward_compat_no_offset(self):
        """Existing calls without offset still work (default offset=0) (#1065)."""
        campaign_id, owner_uid = _campaign_with_turns(3)
        if not campaign_id:
            pytest.skip("No campaign with ≥3 turns found")

        resp = client.get(
            f"/api/campaigns/{campaign_id}/turns-history?limit=10&user_id={owner_uid}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "turns" in data
        assert "campaign_id" in data
        assert "title" in data
        assert "status" in data


# ─── Admin turns pagination ───────────────────────────────────────────────────

class TestAdminTurnsPagination:
    """GET /api/admin/campaigns/{id}/turns must support offset + return total_count."""

    def test_admin_turns_returns_total_count(self):
        """Admin turns endpoint must include total_count (#1065)."""
        campaign_id, _ = _campaign_with_turns(3)
        if not campaign_id:
            pytest.skip("No campaign with ≥3 turns")
        admin_token = _get_admin_token()
        if not admin_token:
            pytest.skip("No admin user / dev-login unavailable")

        resp = client.get(
            f"/api/admin/campaigns/{campaign_id}/turns?limit=5",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "total_count" in data, \
            "Admin turns response must include total_count (#1065)"
        assert isinstance(data["total_count"], int)
        assert data["total_count"] >= 3

    def test_admin_turns_offset_paginates(self):
        """Admin turns offset param returns different, non-overlapping pages (#1065)."""
        campaign_id, _ = _campaign_with_turns(5)
        if not campaign_id:
            pytest.skip("No campaign with ≥5 turns")
        admin_token = _get_admin_token()
        if not admin_token:
            pytest.skip("No admin user / dev-login unavailable")

        r1 = client.get(
            f"/api/admin/campaigns/{campaign_id}/turns?limit=2&offset=0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        r2 = client.get(
            f"/api/admin/campaigns/{campaign_id}/turns?limit=2&offset=2",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r1.status_code == 200
        assert r2.status_code == 200

        ids1 = {t["id"] for t in r1.json()["items"]}
        ids2 = {t["id"] for t in r2.json()["items"]}
        if ids1 and ids2:
            assert not ids1 & ids2, f"Paginated pages overlap: {ids1 & ids2}"

    def test_admin_turns_backward_compat(self):
        """Existing calls without offset still work (default offset=0) (#1065)."""
        campaign_id, _ = _campaign_with_turns(3)
        if not campaign_id:
            pytest.skip("No campaign with ≥3 turns")
        admin_token = _get_admin_token()
        if not admin_token:
            pytest.skip("No admin user / dev-login unavailable")

        resp = client.get(
            f"/api/admin/campaigns/{campaign_id}/turns?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)
