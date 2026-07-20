"""#1487 Faza 1 — ścieżka do bazy ma JEDNO źródło: ``core.db_runtime.resolve_db_path``.

Dopóki moduły miały ``/data/ai_gm.db`` wpisane na sztywno, testy pisały do żywej bazy
DEV niezależnie od ``AI_TEST_DB_PATH`` — stąd nawracające fale śmieci (#941, #1382,
#1407, #1480). Ten test pilnuje, żeby literał nie wrócił tylnymi drzwiami.
"""
import ast
from pathlib import Path

import pytest

import app as app_pkg

# `app` jest pakietem namespace (brak __init__.py) — __file__ bywa None, __path__ nie.
APP_DIR = Path(app_pkg.__file__ or next(iter(app_pkg.__path__))).resolve()
if APP_DIR.is_file():
    APP_DIR = APP_DIR.parent
LITERAL = "/data/ai_gm.db"
# Jedyne miejsce, które ZNA fizyczną ścieżkę — reszta pyta jego.
ALLOWED = {APP_DIR / "core" / "db_runtime.py"}


def _docstring_nodes(tree):
    """Węzły będące docstringami — wolno im wspominać ścieżkę w prozie."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                out.add(id(body[0].value))
    return out


def _offenders():
    hits = []
    for path in sorted(APP_DIR.rglob("*.py")):
        if path in ALLOWED:
            continue
        src = path.read_text(encoding="utf-8")
        if LITERAL not in src:
            continue
        tree = ast.parse(src)
        skip = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and LITERAL in node.value
                and id(node) not in skip
            ):
                rel = path.relative_to(APP_DIR)
                hits.append(f"{rel}:{node.lineno}")
    return hits


def test_no_hardcoded_db_path_in_app_code():
    offenders = _offenders()
    assert not offenders, (
        "Literał ścieżki do bazy w kodzie — użyj resolve_db_path() "
        "(inaczej testy piszą do żywej bazy DEV):\n  " + "\n  ".join(offenders)
    )


def test_resolve_db_path_follows_env(monkeypatch):
    from app.core import db_runtime

    monkeypatch.setenv("AI_TEST_MODE", "1")
    monkeypatch.setenv("AI_TEST_DB_PATH", "/tmp/probe_1487.db")
    assert db_runtime.resolve_db_path() == "/tmp/probe_1487.db"

    monkeypatch.delenv("AI_TEST_MODE")
    assert db_runtime.resolve_db_path() == db_runtime.DEFAULT_DB_PATH


@pytest.mark.parametrize(
    "module_name,attr",
    [
        ("app.services.xp_service", "DB_PATH"),
        ("app.services.spell_service", "DB_PATH"),
        ("app.services.economy_service", "DB_PATH"),
        ("app.migrations_admin", "DB_PATH"),
        ("app.routers.admin", "ADMIN_SQLITE_PATH"),
    ],
)
def test_modules_resolve_path_not_literal(module_name, attr):
    """Stała modułowa musi pochodzić z resolvera, nie z literału.

    Wartość liczona przy imporcie, więc w normalnym runtime wychodzi ta sama ścieżka
    co zawsze — różnica pojawia się dopiero, gdy proces dostanie AI_TEST_DB_PATH.
    """
    import importlib

    from app.core.db_runtime import resolve_db_path

    mod = importlib.import_module(module_name)
    assert str(getattr(mod, attr)) == resolve_db_path()
