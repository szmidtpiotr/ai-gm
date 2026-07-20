"""#1493 — AI_TEST_MODE=1 na DEV nie może zmieniać gry ani otwierać jej na świat.

Dwa skutki uboczne trybu testowego, wykryte przy przeglądzie po #1487/#1488:
  1. dyrektywa autopilota skracała narrację KAŻDEJ tury (nie tylko bohaterów [TEST]),
  2. `/api/debug/*` był publicznie dostępny bez logowania.
"""
import re
from pathlib import Path

import pytest

import app as app_pkg

APP_DIR = Path(app_pkg.__file__ or next(iter(app_pkg.__path__))).resolve()
if APP_DIR.is_file():
    APP_DIR = APP_DIR.parent
REPO = APP_DIR.parent.parent


def test_autopilot_narration_directive_is_gated_on_test_hero():
    """Dyrektywa „narracja 1-2 zdania" tylko dla bohatera [TEST], nigdy dla gracza."""
    src = (APP_DIR / "services" / "game_engine.py").read_text(encoding="utf-8")
    idx = src.find("build_autopilot_narration_directive()")
    assert idx > 0, "nie znaleziono wywołania dyrektywy autopilota"
    guard = src[max(0, idx - 600):idx]
    assert "is_test_hero(character)" in guard, (
        "dyrektywa autopilota bez sprawdzenia is_test_hero — skróciłaby narrację "
        "każdej tury na DEV (AI_TEST_MODE=1)"
    )


def test_hero_protection_never_touches_a_real_character():
    from app.services import playthrough_service as pts

    assert pts.is_test_hero({"name": "[TEST] Bohater"}) is True
    assert pts.is_test_hero({"name": "Eldric"}) is False
    assert pts.is_test_hero(None) is False


def _nginx_conf() -> Path | None:
    """Obraz backendu nie zawiera frontendu — wtedy test nie ma czego sprawdzać."""
    for candidate in (REPO / "frontend" / "nginx.conf", Path("/app/frontend/nginx.conf")):
        if candidate.is_file():
            return candidate
    return None


def test_debug_router_is_not_exposed_publicly_by_nginx():
    """Nginx wpuszcza /api/debug/ tylko z sieci kontenerów."""
    path = _nginx_conf()
    if path is None:
        pytest.skip("frontend/nginx.conf niedostępny w tym środowisku (obraz backendu)")
    conf = path.read_text(encoding="utf-8")
    block = re.search(r"location /api/debug/ \{(.*?)\n    \}", conf, re.S)
    assert block, "brak osobnego bloku location /api/debug/ w nginx.conf"
    body = block.group(1)
    assert "deny all;" in body, "blok /api/debug/ bez `deny all` — publicznie otwarty"
    assert "allow 172.16.0.0/12;" in body, "test-agent (sieć docker) musi mieć dostęp"


def test_stub_llm_requires_admin():
    """Podmiana odpowiedzi GM dla całego procesu = tylko admin."""
    src = (APP_DIR / "routers" / "debug.py").read_text(encoding="utf-8")
    idx = src.find('@router.post("/stub_llm")')
    assert idx > 0
    handler = src[idx:idx + 1400]
    assert "require_admin_role" in handler, "stub_llm bez wymogu admina"


@pytest.mark.parametrize("path", ["/api/debug/settings/feature_flags", "/api/debug/player_state"])
def test_debug_paths_still_mounted_for_tooling(path):
    """Blokada jest sieciowa — endpointy mają dalej istnieć dla test-agenta."""
    from app.main import app

    routes = {getattr(r, "path", "") for r in app.routes}
    assert path in routes, f"{path} zniknął — Playwright i MCP na nim polegają"
