#!/usr/bin/env python3
"""U12 (#560, ślad #559) — db_lint CLI (wersja w obrazie backendu).

Uruchom w kontenerze backendu (tak woła deploy_dev.sh):
    docker exec ai-gm-dev-backend-1 python scripts/db_lint.py
    docker compose -f docker-compose.dev.yml exec -T backend python scripts/db_lint.py

Exit code: 0 = czysto, 1 = tylko warnings, 2 = errors.

Bliźniacza kopia (do uruchamiania z korzenia repo na hoście): repo-root scripts/db_lint.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

# W obrazie cwd=/app, a kod jest w /app/app/... — dołóż /app do ścieżki dla pewności.
_APP_ROOT = Path(__file__).resolve().parent.parent  # /app
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.services.db_lint_service import run_lint, format_report  # noqa: E402


def main() -> int:
    result = run_lint()
    print(format_report(result))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
