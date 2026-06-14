#!/usr/bin/env python3
"""U13 (#561) — seed_lint CLI (wersja do uruchamiania z korzenia repo na hoście).

Działa zarówno w repo (backend/app/...) jak i w kontenerze (/app/app/...).
Wymaga środowiska z zależnościami backendu — w praktyce uruchamiana w kontenerze
(patrz backend/scripts/lint_seeds.py); ten plik jest twin-em dla wygody dev.

    python scripts/lint_seeds.py --seeds-dir data/seeds

Exit code: 0 = czysto, 1 = tylko warnings, 2 = errors / odrzucony plik.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _cand in (_ROOT / "backend", _ROOT):
    if (_cand / "app" / "services" / "seed_lint_service.py").exists():
        sys.path.insert(0, str(_cand))
        break

from app.services.seed_lint_service import lint_seeds, format_report  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Lint seedów treści (U13)")
    ap.add_argument("--seeds-dir", default=str(_ROOT / "data" / "seeds"),
                    help="katalog z plikami seedów NN_*.sql")
    ap.add_argument("--source-db", default=None,
                    help="baza źródłowa schematu (domyślnie żywa DB)")
    args = ap.parse_args()

    result = lint_seeds(seeds_dir=args.seeds_dir, source_schema_db=args.source_db)
    print(format_report(result))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
