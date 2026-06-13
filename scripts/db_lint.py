#!/usr/bin/env python3
"""U12 (#559) — db_lint: audyt integralności bazy treści.

Uruchom w kontenerze backendu:
    docker exec ai-gm-dev-backend-1 python scripts/db_lint.py

Exit code: 0 = czysto, 1 = tylko warnings, 2 = errors.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Działa zarówno w repo (backend/app/...) jak i w kontenerze (/app/app/...).
_ROOT = Path(__file__).resolve().parent.parent
for _cand in (_ROOT / "backend", _ROOT):
    if (_cand / "app" / "services" / "db_lint_service.py").exists():
        sys.path.insert(0, str(_cand))
        break

from app.services.db_lint_service import run_lint, format_report  # noqa: E402


def main() -> int:
    result = run_lint()
    print(format_report(result))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
