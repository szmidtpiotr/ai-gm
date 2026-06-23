#!/usr/bin/env python3
"""Shared helpers for the game-smoke-mp scripts.

- API calls hit the DEV backend at :8100. Player/host identity is carried via the
  ?user_id= query param (backend's resolve_authed_user_id accepts it on DEV).
- Admin-only calls (create test users) use a dev-login bearer token (demo/demo).
- DB reads go through ssh + `docker exec sqlite3 -json` (NOT the sshfs mount). The backend
  runs SQLite in WAL mode; recent commits are NOT reliably visible through the network mount
  (stale reads), so all verification reads run inside the container against the live DB.
"""
import json
import subprocess
import urllib.error
import urllib.request

API_BASE = "http://192.168.1.61:8100"
SSH_HOST = "claude@192.168.1.61"
CONTAINER = "ai-gm-dev-backend-1"
DB_IN_CONTAINER = "/data/ai_gm.db"

ADMIN_USER = "demo"
ADMIN_PASS = "demo"


def _request(method: str, path: str, payload: dict | None = None,
             token: str | None = None, timeout: int = 90) -> tuple[int, dict]:
    url = f"{API_BASE}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"detail": raw[:300]}
    except Exception as e:
        return 0, {"error": str(e)}


def api_post(path, payload=None, token=None, user_id=None, timeout=90):
    if user_id is not None:
        sep = "&" if "?" in path else "?"
        path = f"{path}{sep}user_id={user_id}"
    return _request("POST", path, payload or {}, token, timeout)


def api_get(path, token=None, user_id=None, timeout=60):
    if user_id is not None:
        sep = "&" if "?" in path else "?"
        path = f"{path}{sep}user_id={user_id}"
    return _request("GET", path, None, token, timeout)


def api_delete(path, token=None, user_id=None, timeout=60):
    if user_id is not None:
        sep = "&" if "?" in path else "?"
        path = f"{path}{sep}user_id={user_id}"
    return _request("DELETE", path, None, token, timeout)


def admin_token() -> str | None:
    status, body = api_post("/api/admin/dev-login",
                            {"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=20)
    if status == 200 and body.get("token"):
        return body["token"]
    return None


def db_query(sql: str, timeout: int = 30) -> list[dict]:
    """Run a read-only query inside the backend container (live WAL) and return rows.

    SQL is piped via stdin to `sqlite3 -json` to avoid nested-quote escaping. Use literal
    integer ids; for string literals escape single quotes by doubling them (`_sq`).
    """
    cmd = ["ssh", SSH_HOST, f"docker exec -i {CONTAINER} sqlite3 -json {DB_IN_CONTAINER}"]
    res = subprocess.run(cmd, input=sql, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"db_query failed: {res.stderr[:200] or res.stdout[:200]}")
    out = res.stdout.strip()
    if not out:
        return []
    return json.loads(out)


def _sq(s: str) -> str:
    """Escape a string for safe inlining inside a single-quoted SQL literal."""
    return s.replace("'", "''")


def find_user_id(username: str) -> int | None:
    rows = db_query(f"SELECT id FROM users WHERE username='{_sq(username)}' LIMIT 1;")
    return rows[0]["id"] if rows else None


def find_hero_id(user_id: int, name: str) -> int | None:
    rows = db_query(
        f"SELECT id FROM characters WHERE user_id={int(user_id)} "
        f"AND name='{_sq(name)}' LIMIT 1;"
    )
    return rows[0]["id"] if rows else None
