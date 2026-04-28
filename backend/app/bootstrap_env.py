"""
Ładuje lokalne pliki KEY=VAL przed czytaniem flag w main.
Ustawia tylko zmienne, które nie mają jeszcze przypisanej *niepustej* wartości
(pusty string traktujemy jak brak — w Dockerze/CI często puste).

W monorepo (ai-gm/): <repo>/.env, <repo>/env.test
W katalogu backend/ (Docker WORKDIR /app, bez nadrzędnego klonu repozytorium w obrazie):
<backend>/.env, <backend>/env.test — stąd montowanie `env.test` w compose: ./env.test -> /app/env.test
"""
from __future__ import annotations

import os
from pathlib import Path


def _is_env_sealed(key: str) -> bool:
    """Czy pominąć plik: zmienna ma już niepustą wartość (np. AI_TEST_MODE=0 w systemd = świadome wyłączenie)."""
    val = os.environ.get(key)
    if val is None:
        return False
    if str(val).strip() == "":
        return False
    return True


def _load_one_file(path: Path) -> None:
    if not path.is_file():
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        if _is_env_sealed(key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ[key] = value


def load_repo_env() -> None:
    """
    Odpal na początku `main` — `__file__` to .../backend/app/bootstrap_env.py
    w repo: backend_root=.../ai-gm/backend NIE: w Docker tylko .../app, repo_root=parent(/app) może być „/” (bezużyteczne).
    """
    app_dir = Path(__file__).resolve().parent
    backend_root = app_dir.parent
    repo_root = backend_root.parent

    paths: list[Path] = [
        backend_root / ".env",
        backend_root / "env.test",
    ]
    # W dev z pełnego klona: ai-gm/ nad backend/
    try:
        if (
            str(repo_root) not in ("/", "")
            and repo_root.resolve() != backend_root.resolve()
        ):
            paths += [repo_root / ".env", repo_root / "env.test"]
    except OSError:
        pass
    for path in paths:
        _load_one_file(path)
