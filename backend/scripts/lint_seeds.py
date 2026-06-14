#!/usr/bin/env python3
"""U13 (#561) — seed_lint CLI (wersja w obrazie backendu).

Przepuszcza seedy data/seeds/01–15 przez świeżą bazę + run_lint (U12) + walidatory U10.

Uruchom w kontenerze backendu (tak woła deploy_dev.sh — seedy kopiowane do /tmp/seeds):
    docker compose -f docker-compose.dev.yml cp data/seeds backend:/tmp/seeds
    docker compose -f docker-compose.dev.yml exec -T backend python scripts/lint_seeds.py --seeds-dir /tmp/seeds

Exit code: 0 = czysto, 1 = tylko warnings, 2 = errors / odrzucony plik.

Bliźniacza kopia (do uruchamiania z korzenia repo na hoście): repo-root scripts/lint_seeds.py.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# W obrazie cwd=/app, kod w /app/app/... — dołóż /app do ścieżki dla pewności.
_APP_ROOT = Path(__file__).resolve().parent.parent  # /app
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.services.seed_lint_service import lint_seeds, format_report  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Lint seedów treści (U13)")
    ap.add_argument("--seeds-dir", default=None,
                    help="katalog z plikami seedów NN_*.sql (domyślnie auto: data/seeds)")
    ap.add_argument("--source-db", default=None,
                    help="baza źródłowa schematu (domyślnie żywa DB)")
    args = ap.parse_args()

    result = lint_seeds(seeds_dir=args.seeds_dir, source_schema_db=args.source_db)
    print(format_report(result))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
