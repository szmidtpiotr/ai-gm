"""
One-time migration: bcrypt-hash any user whose password_hash is not already a bcrypt hash.

Usage (inside backend container):
    python scripts/migrate_plaintext_passwords.py            # live run
    python scripts/migrate_plaintext_passwords.py --dry-run  # plan only, no writes

A bcrypt hash starts with '$2' (e.g. '$2b$12$...'). Rows that don't match are treated as
plain-text passwords (e.g. 'demo') and re-hashed with bcrypt rounds=12.

SHA-256 hex strings (len==64, all hex chars) cannot be reversed, so they are skipped with
a warning — those accounts must reset their password manually.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import bcrypt

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB = _BACKEND_ROOT / "data" / "ai_gm.db"
_DOCKER_DB = Path("/data/ai_gm.db")

BCRYPT_ROUNDS = 12


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value)


def migrate(db_path: Path, dry_run: bool) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE password_hash NOT LIKE '$2%'"
        ).fetchall()

        if not rows:
            print("No plain-text passwords found. All users already have bcrypt hashes.")
            return 0

        migrated = 0
        skipped = 0
        for row in rows:
            uid, username, stored = row["id"], row["username"], str(row["password_hash"] or "")
            if _is_sha256(stored):
                print(f"SKIP  id={uid} username={username!r}: SHA-256 hash detected — cannot reverse, manual reset required")
                skipped += 1
                continue

            new_hash = bcrypt.hashpw(stored.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("ascii")
            if dry_run:
                print(f"DRY   id={uid} username={username!r}: would hash plain-text '{stored}' → {new_hash[:20]}...")
            else:
                conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, uid))
                print(f"DONE  id={uid} username={username!r}: plain-text hashed → {new_hash[:20]}...")
            migrated += 1

        if not dry_run and migrated > 0:
            conn.commit()
            print(f"\nCommitted. Migrated={migrated} skipped={skipped}")
        elif dry_run:
            print(f"\nDry-run complete. Would migrate={migrated} would skip={skipped}")
        else:
            print(f"\nDone. Migrated={migrated} skipped={skipped}")

        return migrated
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate plain-text passwords to bcrypt")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")
    parser.add_argument("--db", type=Path, default=None, help="Override DB path")
    args = parser.parse_args()

    db = args.db or (_DOCKER_DB if _DOCKER_DB.exists() else _DEFAULT_DB)
    if not db.exists():
        print(f"ERROR: DB not found at {db}", file=sys.stderr)
        sys.exit(1)

    print(f"DB: {db}  dry_run={args.dry_run}\n")
    migrate(db, dry_run=args.dry_run)
