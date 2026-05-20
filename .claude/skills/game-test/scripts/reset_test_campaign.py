#!/usr/bin/env python3
"""Reset the dedicated [TEST] campaign to a clean baseline.

Reads are done locally via sshfs (read-only). Writes are executed inside the
backend container via SSH+docker exec to avoid SQLite WAL corruption from
concurrent sshfs writers.

Behavior:
- Find campaign titled "[TEST]*" and character named "[TEST]*".
- Soft-delete any game_locations created by the GM during prior runs.
- Repoint game_sessions.current_location_id to the starting location.
- Print one JSON line on stdout.

Run from anywhere; requires sshfs DB mount at DB_LOCAL_PATH.
"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

DB_LOCAL_PATH = Path("/home/claude/projects/DEV_AIGM/data-dev/ai_gm.db")
CONTAINER = "ai-gm-dev-backend-1"
REMOTE_DB = "/data/ai_gm.db"
SSH_HOST = "claude@192.168.1.61"
DEFAULT_FALLBACK_START_KEY = "skraj_wioski"


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def read_db():
    """Open local sshfs mount read-only for queries."""
    if not DB_LOCAL_PATH.exists():
        return None
    db = sqlite3.connect(f"file:{DB_LOCAL_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def remote_sql(sql: str) -> bool:
    """Execute a SQL statement inside the backend container via SSH.
    Returns True on success, False on error.
    """
    cmd = [
        "ssh", SSH_HOST,
        f'docker exec {CONTAINER} python3 -c '
        f'"import sqlite3; db=sqlite3.connect(\\"{REMOTE_DB}\\"); db.execute({sql!r}); db.commit()"'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def remote_sql_multi(statements: list[str]) -> tuple[bool, str]:
    """Execute multiple SQL statements inside the container atomically.

    Writes a temp script via SSH+tee to avoid multi-layer quoting issues,
    runs it with docker exec, then removes it.
    """
    lines = ["import sqlite3"]
    lines.append("db = sqlite3.connect('/data/ai_gm.db')")
    for s in statements:
        # Escape backslashes and single quotes for the heredoc content
        safe = s.replace("\\", "\\\\").replace("'", "\\'")
        lines.append(f"db.execute('{safe}')")
    lines.append("db.commit()")
    script_body = "\n".join(lines)

    tmp = "/tmp/_gt_reset.py"
    # Write script via SSH heredoc (safe — script_body has no special shell chars after escaping)
    write_cmd = f"ssh {SSH_HOST} 'cat > {tmp}' << 'PYEOF'\n{script_body}\nPYEOF"
    r1 = subprocess.run(write_cmd, shell=True, capture_output=True, text=True)
    if r1.returncode != 0:
        return False, f"write failed: {r1.stderr}"

    run_cmd = ["ssh", SSH_HOST, f"docker cp {tmp} {CONTAINER}:{tmp} && docker exec {CONTAINER} python3 {tmp}"]
    r2 = subprocess.run(run_cmd, capture_output=True, text=True)

    # Cleanup
    subprocess.run(["ssh", SSH_HOST, f"rm -f {tmp}"], capture_output=True)
    subprocess.run(["ssh", SSH_HOST, f"docker exec {CONTAINER} rm -f {tmp}"], capture_output=True)

    return r2.returncode == 0, r2.stderr.strip()


def main() -> int:
    db = read_db()
    if db is None:
        emit({"error": f"DB not found at {DB_LOCAL_PATH}. Check sshfs mount."})
        return 2

    camp = db.execute(
        "SELECT id, title, status FROM campaigns "
        "WHERE title LIKE '[TEST]%' ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if not camp:
        emit({
            "bootstrap_required": True,
            "reason": "no_test_campaign",
            "instructions": (
                "Run this to bootstrap:\n"
                "  python3 scripts/bootstrap_test_campaign.py\n"
                "Or create manually via the player UI: campaign titled '[TEST] Tester', "
                "character named '[TEST] Tester'."
            ),
        })
        return 1

    char = db.execute(
        "SELECT id, name, status FROM characters "
        "WHERE campaign_id=? AND name LIKE '[TEST]%' ORDER BY id DESC LIMIT 1",
        (camp["id"],),
    ).fetchone()

    if not char:
        emit({
            "bootstrap_required": True,
            "reason": "no_test_character",
            "campaign_id": camp["id"],
            "instructions": (
                f"Campaign #{camp['id']} exists but has no '[TEST]*' character. "
                "Run scripts/bootstrap_test_campaign.py or create one via the UI."
            ),
        })
        return 1

    session = db.execute(
        "SELECT id FROM game_sessions WHERE campaign_id=? ORDER BY id DESC LIMIT 1",
        (camp["id"],),
    ).fetchone()

    if not session:
        emit({
            "bootstrap_required": True,
            "reason": "no_session",
            "campaign_id": camp["id"],
            "character_id": char["id"],
            "instructions": "Run scripts/bootstrap_test_campaign.py to materialize the session.",
        })
        return 1

    # Determine starting location
    start_key = DEFAULT_FALLBACK_START_KEY
    start = db.execute(
        "SELECT id, key, label FROM game_locations "
        "WHERE key=? AND COALESCE(is_active,1)=1",
        (start_key,),
    ).fetchone()
    if not start:
        start = db.execute(
            "SELECT id, key, label FROM game_locations "
            "WHERE COALESCE(is_active,1)=1 AND COALESCE(approved,1)=1 "
            "AND parent_id IS NULL ORDER BY id ASC LIMIT 1"
        ).fetchone()

    if not start:
        emit({
            "bootstrap_required": True,
            "reason": "no_starting_location",
            "instructions": "Seed at least one approved macro location via the Admin UI.",
        })
        return 1

    # Count GM locations to soft-delete (read locally)
    to_delete_count = db.execute(
        "SELECT COUNT(*) FROM game_locations "
        "WHERE source_campaign_id=? AND ai_generated=1 AND COALESCE(is_active,1)=1 AND id != ?",
        (camp["id"], start["id"]),
    ).fetchone()[0]

    # Perform writes via SSH (safe — no sshfs concurrent write)
    stmts = [
        f"UPDATE game_locations SET is_active=0 WHERE source_campaign_id={camp['id']} "
        f"AND ai_generated=1 AND COALESCE(is_active,1)=1 AND id != {start['id']}",
        f"UPDATE game_sessions SET current_location_id={start['id']} WHERE id='{session['id']}'",
    ]
    ok, err = remote_sql_multi(stmts)
    if not ok:
        emit({"error": f"Remote SQL failed: {err}"})
        return 2

    emit({
        "ok": True,
        "campaign_id": camp["id"],
        "campaign_title": camp["title"],
        "character_id": char["id"],
        "character_name": char["name"],
        "session_id": session["id"],
        "starting_location_id": start["id"],
        "starting_location_key": start["key"],
        "starting_location_label": start["label"],
        "soft_deleted_prior_locations": to_delete_count,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
